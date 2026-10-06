#!/usr/bin/env python3
"""全体経路・限定した再利用・新規比較の束縛を検査する。意味的合格は認定しない。"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
from itertools import combinations
import json
from pathlib import Path
import re
import sys

from jsonschema import Draft202012Validator

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
import audit_held_out as legacy  # noqa: E402
import source_guard  # noqa: E402

PRIVATE_BASE = Path("/home/hide/BitzLabs/BitzSkills-private-evals/core-sdd-quality-20261006")
CONTRACT_NAME = "evals/skills/routing/held-out-collection-v0.4.json"
EVIDENCE_NAME = "evals/skills/routing/remediation-evidence.schema.json"
INPUT_NAMES = {
    EVIDENCE_NAME, "evals/skills/schemas/case.schema.json", "evals/skills/validate.py",
    "evals/skills/protocol.json", "evals/skills/event-catalog.json",
    "evals/skills/cases/routing.json", "evals/skills/cases/behavior-safety.json",
}
SOURCE_NAMES = INPUT_NAMES | {
    CONTRACT_NAME, "evals/skills/routing/audit_held_out.py",
    "evals/skills/routing/source_guard.py", "evals/skills/routing/audit_remediated_held_out.py",
    "tests/skills/test_held_out_remediation.py",
}
INITIAL = "production-routing-held-out-0.1.0"
PREVIOUS = "production-routing-held-out-0.3.0"
VERSION = "production-routing-held-out-0.4.0"


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def load(raw: bytes) -> dict:
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("duplicate JSON key")
            value[key] = item
        return value
    return json.loads(raw, object_pairs_hook=unique)


def case_digest(case: dict) -> str:
    return digest(json.dumps(case, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode())


def public_inputs(contract: dict) -> None:
    if set(contract["inputSha256"]) != INPUT_NAMES:
        raise ValueError("input inventory")
    observed = {str(p.relative_to(ROOT)) for p in (ROOT / "evals/skills/cases").glob("*.json")}
    if observed != {p for p in INPUT_NAMES if p.startswith("evals/skills/cases/")}:
        raise ValueError("public case inventory")
    # 全pathを先に検査する。証拠に含まれるpathをファイル読取りに使わない。
    for name in INPUT_NAMES:
        path = ROOT / name
        if any(p.is_symlink() for p in [path, *path.parents] if p.is_relative_to(ROOT)):
            raise ValueError("public input symlink")
    for name, expected in contract["inputSha256"].items():
        if digest((ROOT / name).read_bytes()) != expected:
            raise ValueError("public input drift")


def check_routing(cases: list, records: list, manifest: dict, skill_bodies: dict) -> None:
    skills = {s["name"]: s for s in manifest["skills"]}
    capabilities = set(legacy.validate.CAPABILITIES)
    if len(manifest["skills"]) != 6 or set(skills) != capabilities:
        raise ValueError("candidate skill inventory")
    by_id = {r["caseId"]: r for r in records}
    if len(by_id) != len(records) or set(by_id) != {c["caseId"] for c in cases}:
        raise ValueError("routing coverage")
    for case in cases:
        record = by_id[case["caseId"]]
        rows = {r["skill"]: r for r in record["skills"]}
        if len(record["skills"]) != 6 or set(rows) != capabilities:
            raise ValueError("six skill coverage")
        for skill, row in rows.items():
            resource = skills[skill]["path"]
            if row["source"]["path"] != resource or row["source"]["sha256"] != manifest["resources"][resource]:
                raise ValueError("routing source binding")
            if row["source"]["anchor"] not in skill_bodies[resource]:
                raise ValueError("routing source anchor")
        if any(r["applicability"] == "undetermined" for r in rows.values()):
            raise ValueError("unresolved routing")
        selected = [s for s, r in rows.items() if r["applicability"] == "applicable"]
        if len(selected) > 1:
            raise ValueError("ambiguous routing")
        skill = selected[0] if selected else None
        expected = case["expected"]
        if expected["sixSkill"] != skill or expected["outcome"] != record["outcome"]:
            raise ValueError("global routing contradiction")
        entry = None
        if skill is not None:
            package, route = legacy.validate.CAPABILITIES[skill]
            entry = {"entry": package, "path": route}
        if expected["threeEntry"] != entry:
            raise ValueError("entry contradiction")
        if skill is None:
            if case["mode"] != "do-not-use" or expected["outcome"] != "not-applicable":
                raise ValueError("global negative condition")
        elif case["capability"] != skill or case["mode"] not in {"use", "stop"}:
            raise ValueError("selected capability contradiction")
        if case["mode"] == "stop" and expected["outcome"] != "stop":
            raise ValueError("stop condition")
        if case["mode"] == "use" and expected["outcome"] not in {"proceed", "question"}:
            raise ValueError("use condition")
        if set(expected["requiredEvents"]) & set(expected["forbiddenEvents"]):
            raise ValueError("event contradiction")
        category = case["category"]
        condition = (case["mode"], expected["outcome"])
        if category in {"explicit", "implicit", "contextual"} and condition != ("use", "proceed"):
            raise ValueError("positive category condition")
        if category == "negative" and condition != ("do-not-use", "not-applicable"):
            raise ValueError("negative category condition")
        if category == "safety" and condition != ("stop", "stop"):
            raise ValueError("safety category condition")


def check_lineage(cases: list, records: list, previous: list, retention: dict) -> set[str]:
    old = {c["caseId"]: c for c in previous}
    retained = set(retention["retainedCaseIds"])
    replaced = set(retention["replacedCaseIds"])
    if len(retention["retainedCaseIds"]) != 9 or len(retention["replacedCaseIds"]) != 3:
        raise ValueError("retention denominator")
    if retained & replaced or retained | replaced != set(old):
        raise ValueError("retention partition")
    if set(retention["retainedCaseSha256"]) != retained:
        raise ValueError("retention digest coverage")
    for old_id in retained:
        if case_digest(old[old_id]) != retention["retainedCaseSha256"][old_id]:
            raise ValueError("retention source drift")
    by_id = {r["caseId"]: r for r in records}
    if len(by_id) != len(records) or set(by_id) != {c["caseId"] for c in cases}:
        raise ValueError("lineage coverage")
    used, new = set(), set()
    for case in cases:
        record = by_id[case["caseId"]]
        if record["origin"] == "new":
            if record["previousCaseId"] is not None or record["previousCaseSha256"] is not None:
                raise ValueError("new case provenance")
            new.add(case["caseId"])
            continue
        old_id = record["previousCaseId"]
        if old_id not in retained or old_id in used or record["previousCaseSha256"] != case_digest(old[old_id]):
            raise ValueError("undeclared retention")
        original = {k: v for k, v in old[old_id].items() if k != "caseId"}
        carried = {k: v for k, v in case.items() if k != "caseId"}
        if original != carried:
            raise ValueError("retained case changed")
        used.add(old_id)
    if used != retained or len(new) != 3:
        raise ValueError("lineage denominator")
    return new


def check_novelty(cases: list, new: set[str], evidence: dict, public: list, excluded: dict) -> None:
    public_ids = {c["caseId"] for c in public}
    if len(public) != 46 or set(evidence["publicCasesConsidered"]) != public_ids:
        raise ValueError("public comparison coverage")
    for version, old_cases in excluded.items():
        if len(old_cases) != 12 or set(evidence["excludedCasesConsidered"][version]) != {c["caseId"] for c in old_cases}:
            raise ValueError("excluded comparison coverage")
    inputs = [legacy.normalized_input(c) for c in cases]
    if len(set(inputs)) != len(cases):
        raise ValueError("duplicate new inputs")
    universal_exclusions = {legacy.normalized_input(c) for c in public + excluded[INITIAL]}
    old_inputs = universal_exclusions | {legacy.normalized_input(c) for c in excluded[PREVIOUS]}
    for case in cases:
        if legacy.normalized_input(case) in universal_exclusions:
            raise ValueError("public or initial input collision")
        if case["caseId"] in new and legacy.normalized_input(case) in old_inputs:
            raise ValueError("undeclared input reuse")
    pairs = [frozenset((r["leftCaseId"], r["rightCaseId"])) for r in evidence["newCasePairs"]]
    if len(pairs) != 3 or set(pairs) != {frozenset(p) for p in combinations(new, 2)}:
        raise ValueError("new pair comparison coverage")
    comparisons = evidence["noveltyComparisons"]
    by_id = {r["caseId"]: r for r in comparisons}
    if len(comparisons) != 3 or len(by_id) != 3 or set(by_id) != new:
        raise ValueError("new comparison coverage")
    indexed = {c["caseId"]: c for c in cases}
    for case_id, record in by_id.items():
        expected = indexed[case_id]["expected"]
        if record["expectedSkill"] != expected["sixSkill"] or record["outcome"] != expected["outcome"]:
            raise ValueError("comparison global decision binding")
        if not set(record["nearestPublicCaseIds"]) <= public_ids:
            raise ValueError("unknown public comparison")
        if {r["setVersion"] for r in record["nearestExcludedCases"]} != set(excluded):
            raise ValueError("excluded nearest coverage")
        for ref in record["nearestExcludedCases"]:
            if ref["caseId"] not in {c["caseId"] for c in excluded[ref["setVersion"]]}:
                raise ValueError("unknown excluded comparison")


def audit(contract: dict, case_path: Path) -> dict:
    private_root = PRIVATE_BASE / "collection-04"
    if contract["collectionVersion"] != "production-routing-held-out-collection-0.4.0" or contract["setVersion"] != VERSION:
        raise ValueError("collection identity")
    if contract["storageAuthorization"]["root"] != str(private_root) or case_path != private_root / "cases.json":
        raise ValueError("case storage")
    public_inputs(contract)
    raw = legacy.private_file(case_path)
    source = load(raw)
    if set(source) != {"setVersion", "cases"}:
        raise ValueError("case envelope")
    cases, metadata = legacy.validate.load_held_out_cases(case_path)
    if metadata["sha256"] != digest(raw):
        raise ValueError("case read drift")
    if metadata["setVersion"] != VERSION or len(cases) != 12 or not all(c["mandatory"] for c in cases):
        raise ValueError("case denominator")
    if {c["caseId"] for c in cases} != {f"SE-{n}" for n in range(1100, 1112)}:
        raise ValueError("new case identities")
    if Counter(c["category"] for c in cases) != Counter(explicit=2, implicit=2, contextual=2, negative=3, safety=3):
        raise ValueError("category denominator")
    for capability in legacy.validate.CAPABILITIES:
        pair = [c for c in cases if c["capability"] == capability]
        if len(pair) != 2 or sum(c["category"] in {"explicit", "implicit", "contextual"} for c in pair) != 1:
            raise ValueError("capability denominator")
    paths = {INITIAL: PRIVATE_BASE / "cases.json", PREVIOUS: PRIVATE_BASE / "collection-03/cases.json"}
    if set(contract["excludedSets"]) != set(paths):
        raise ValueError("excluded set inventory")
    excluded = {}
    for version, path in paths.items():
        declared = contract["excludedSets"][version]
        previous_raw = legacy.private_file(path)
        if declared["path"] != str(path) or declared["sha256"] != digest(previous_raw):
            raise ValueError("excluded set binding")
        previous = load(previous_raw)
        if set(previous) != {"setVersion", "cases"} or previous["setVersion"] != version or len(previous["cases"]) != 12:
            raise ValueError("excluded set identity")
        checked, old_metadata = legacy.validate.load_held_out_cases(path)
        if old_metadata["sha256"] != digest(previous_raw):
            raise ValueError("excluded read drift")
        if old_metadata["setVersion"] != version or old_metadata["caseCount"] != 12:
            raise ValueError("excluded case validation")
        excluded[version] = checked
    retention_raw = legacy.private_file(private_root / "retention.json")
    if digest(retention_raw) != contract["retention"]["sha256"]:
        raise ValueError("retention manifest drift")
    retention = load(retention_raw)
    if set(retention) != {"schemaVersion", "sourceSetVersion", "sourceCasesSha256", "independentReceiptSha256",
                          "retainedCaseIds", "replacedCaseIds", "retainedCaseSha256"} or retention["schemaVersion"] != "1.0":
        raise ValueError("retention envelope")
    review_raw = legacy.private_file(PRIVATE_BASE / "collection-03/independent-receipt.json")
    if (digest(review_raw) != contract["retention"]["independentReceiptSha256"]
            or retention["independentReceiptSha256"] != digest(review_raw)
            or retention["sourceSetVersion"] != PREVIOUS
            or retention["sourceCasesSha256"] != contract["excludedSets"][PREVIOUS]["sha256"]):
        raise ValueError("retention review binding")
    review = load(review_raw)
    if (review["status"] != "stopped_on_p1_p2" or review["affectedCaseCount"] != 3
            or review["casesSha256"] != retention["sourceCasesSha256"]):
        raise ValueError("retention review identity")
    legacy.audit_candidate(contract)
    snapshot = ROOT / contract["candidate"]["snapshotRelativePath"]
    manifest_raw = (snapshot / "manifest.json").read_bytes()
    if digest(manifest_raw) != contract["candidate"]["manifestSha256"]:
        raise ValueError("manifest read drift")
    manifest = load(manifest_raw)
    skill_paths = [s["path"] for s in manifest["skills"]]
    if any(p not in manifest["resources"] for p in skill_paths):
        raise ValueError("skill resource inventory")
    skill_bodies = {}
    for path in skill_paths:
        body = (snapshot / path).read_bytes()
        if digest(body) != manifest["resources"][path]:
            raise ValueError("body read drift")
        skill_bodies[path] = body.decode("utf-8")
    evidence_raw = legacy.private_file(private_root / "evidence.json")
    evidence = load(evidence_raw)
    Draft202012Validator(load((ROOT / EVIDENCE_NAME).read_bytes())).validate(evidence)
    if evidence["setVersion"] != VERSION or evidence["casesSha256"] != digest(raw):
        raise ValueError("evidence case binding")
    check_routing(cases, evidence["routing"], manifest, skill_bodies)
    new = check_lineage(cases, evidence["lineage"], excluded[PREVIOUS], retention)
    check_novelty(cases, new, evidence, legacy.validate.load_cases(), excluded)
    return {"status": "mechanical_checks_passed", "heldOut": metadata,
            "newCaseCount": 3, "retainedCaseCount": 9, "routingAssessmentCount": 12,
            "noveltyComparisonCount": 3, "publicExclusionCount": 46, "privateExclusionCounts": [12, 12],
            "evidenceSha256": digest(evidence_raw), "retentionSha256": digest(retention_raw),
            "semanticNovelty": "requires_independent_review", "routingSemantics": "requires_independent_review",
            "primaryModelTrajectories": 0, "certifiesSkillGate": False}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--cases", type=Path, required=True)
    args = parser.parse_args()
    try:
        if not re.fullmatch(r"[0-9a-f]{40}", args.source):
            raise ValueError("full source commit required")
        contract = load(source_guard.git(ROOT, "show", args.source + ":" + CONTRACT_NAME))
        if set(contract["sourceFiles"]) != SOURCE_NAMES or len(contract["sourceFiles"]) != len(SOURCE_NAMES):
            raise ValueError("source inventory")
        source_guard.verify(ROOT, args.source, contract["sourceFiles"])
        result = audit(contract, args.cases)
        source_guard.verify(ROOT, args.source, contract["sourceFiles"])
        result.update(sourceCommit=args.source, sourceFileCount=len(SOURCE_NAMES), headIsCondition=False,
                      contractSha256=digest(source_guard.git(ROOT, "show", args.source + ":" + CONTRACT_NAME)))
    except Exception as error:
        print(json.dumps({"status": "blocked", "errorType": type(error).__name__}))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
