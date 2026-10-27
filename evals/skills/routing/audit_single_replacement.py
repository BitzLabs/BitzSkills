#!/usr/bin/env python3
"""集合0.5: 11件の不変な来歴と1件の測定可能な反実仮想を束縛する。"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys

from jsonschema import Draft202012Validator

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
import audit_remediated_held_out as previous  # noqa: E402

legacy, source_guard = previous.legacy, previous.source_guard
digest, load, case_digest = previous.digest, previous.load, previous.case_digest
PRIVATE_BASE = previous.PRIVATE_BASE
INITIAL, OLD = previous.INITIAL, previous.PREVIOUS
PREVIOUS, VERSION = previous.VERSION, "production-routing-held-out-0.5.0"
CONTRACT_NAME = "evals/skills/routing/held-out-collection-v0.5.json"
EVIDENCE_NAME = "evals/skills/routing/single-replacement-evidence.schema.json"
INPUT_NAMES = (previous.INPUT_NAMES - {previous.EVIDENCE_NAME}) | {EVIDENCE_NAME}
SOURCE_NAMES = INPUT_NAMES | {
    CONTRACT_NAME, "evals/skills/routing/audit_held_out.py", "evals/skills/routing/source_guard.py",
    "evals/skills/routing/audit_remediated_held_out.py", previous.EVIDENCE_NAME,
    "evals/skills/routing/audit_single_replacement.py", "tests/skills/test_held_out_remediation.py",
    "tests/skills/test_single_replacement.py",
}


def public_inputs(contract: dict) -> None:
    if set(contract["inputSha256"]) != INPUT_NAMES:
        raise ValueError("input inventory")
    found = {str(p.relative_to(ROOT)) for p in (ROOT / "evals/skills/cases").glob("*.json")}
    if found != {p for p in INPUT_NAMES if p.startswith("evals/skills/cases/")}:
        raise ValueError("public case inventory")
    for name in INPUT_NAMES:
        path = ROOT / name
        if any(p.is_symlink() for p in [path, *path.parents] if p.is_relative_to(ROOT)):
            raise ValueError("public input symlink")
    for name, expected in contract["inputSha256"].items():
        if digest((ROOT / name).read_bytes()) != expected:
            raise ValueError("public input drift")


def replacement_from_report(report: str, old: list) -> set[str]:
    # この旧報告の固定形式を読む。本文の意味を機械的に再採点しない。
    coverage = re.findall(r"^### (SE-[0-9]+)\s*$", report, re.M)
    failed = re.findall(r"^### (SE-[0-9]+)[^\n]*\bP2\b[^\n]*$", report, re.M)
    if len(coverage) != 12 or set(coverage) != {c["caseId"] for c in old} or len(failed) != 1:
        raise ValueError("previous report case coverage")
    if failed[0] not in set(coverage):
        raise ValueError("previous report affected identity")
    return set(failed)


def check_lineage(cases: list, records: list, old: list, retention: dict, failed: set[str]) -> set[str]:
    retained, replaced = set(retention["retainedCaseIds"]), set(retention["replacedCaseIds"])
    indexed = {c["caseId"]: c for c in old}
    if (len(retention["retainedCaseIds"]) != 11 or len(retention["replacedCaseIds"]) != 1
            or replaced != failed or retained & replaced or retained | replaced != set(indexed)):
        raise ValueError("retention partition")
    if set(retention["retainedCaseSha256"]) != retained:
        raise ValueError("retention digest coverage")
    for case_id in retained:
        if case_digest(indexed[case_id]) != retention["retainedCaseSha256"][case_id]:
            raise ValueError("retention source drift")
    by_id = {r["caseId"]: r for r in records}
    if len(by_id) != len(records) or set(by_id) != {c["caseId"] for c in cases}:
        raise ValueError("lineage coverage")
    used, new = set(), set()
    for case in cases:
        row = by_id[case["caseId"]]
        if row["origin"] == "new":
            if row["previousCaseId"] is not None or row["previousCaseSha256"] is not None:
                raise ValueError("new provenance")
            new.add(case["caseId"])
            continue
        old_id = row["previousCaseId"]
        if old_id not in retained or old_id in used or row["previousCaseSha256"] != case_digest(indexed[old_id]):
            raise ValueError("undeclared retention")
        if {k: v for k, v in case.items() if k != "caseId"} != {k: v for k, v in indexed[old_id].items() if k != "caseId"}:
            raise ValueError("retained case changed")
        used.add(old_id)
    if used != retained or len(new) != 1:
        raise ValueError("lineage denominator")
    return new


def check_counterfactual(case: dict, record: dict, manifest: dict, bodies: dict) -> None:
    proof = record["counterfactual"]
    before, after = proof["beforeDecision"], proof["afterDecision"]
    if before != case["expected"]:
        raise ValueError("counterfactual before binding")
    source = proof["source"]
    resources = {s["path"] for s in manifest["skills"]}
    if (source["path"] not in resources or source["sha256"] != manifest["resources"][source["path"]]
            or source["anchor"] not in bodies[source["path"]]):
        raise ValueError("counterfactual source binding")
    # eventの順序だけの差は採点上の差にしない。
    normalized = lambda d: {**d, "requiredEvents": sorted(set(d["requiredEvents"])),
                             "forbiddenEvents": sorted(set(d["forbiddenEvents"]))}
    before, after = normalized(before), normalized(after)
    for decision in [before, after]:
        skill = decision["sixSkill"]
        entry = None
        if skill is not None:
            package, path = legacy.validate.CAPABILITIES[skill]
            entry = {"entry": package, "path": path}
        if decision["threeEntry"] != entry or (skill is None) != (decision["outcome"] == "not-applicable"):
            raise ValueError("counterfactual decision route")
        if set(decision["requiredEvents"]) & set(decision["forbiddenEvents"]):
            raise ValueError("counterfactual event contradiction")
    changed = {key for key in before if before[key] != after[key]}
    if not changed:
        raise ValueError("counterfactual unmeasured difference")
    consequence = proof["measuredConsequence"]
    if consequence == "selection" and "sixSkill" not in changed:
        raise ValueError("counterfactual selection unchanged")
    if consequence != "selection" and not changed & {"outcome", "requiredEvents", "forbiddenEvents"}:
        raise ValueError("counterfactual consequence unobserved")
    if consequence == "question" and "question" not in {before["outcome"], after["outcome"]}:
        raise ValueError("counterfactual question missing")
    if consequence == "stop" and "stop" not in {before["outcome"], after["outcome"]}:
        raise ValueError("counterfactual stop missing")


def check_novelty(cases: list, new: set[str], evidence: dict, public: list, excluded: dict,
                  manifest: dict, bodies: dict) -> None:
    public_ids = {c["caseId"] for c in public}
    if len(public) != 46 or set(evidence["publicCasesConsidered"]) != public_ids:
        raise ValueError("public comparison coverage")
    for version, old in excluded.items():
        if len(old) != 12 or set(evidence["excludedCasesConsidered"][version]) != {c["caseId"] for c in old}:
            raise ValueError("excluded comparison coverage")
    values = [legacy.normalized_input(c) for c in cases]
    if len(set(values)) != 12:
        raise ValueError("duplicate inputs")
    forbidden = {legacy.normalized_input(c) for c in public + excluded[INITIAL]}
    all_old = forbidden | {legacy.normalized_input(c) for group in excluded.values() for c in group}
    for case in cases:
        if legacy.normalized_input(case) in forbidden:
            raise ValueError("public or initial input collision")
        if case["caseId"] in new and legacy.normalized_input(case) in all_old:
            raise ValueError("undeclared input reuse")
    records = evidence["noveltyComparisons"]
    if len(records) != 1 or {r["caseId"] for r in records} != new or evidence["newCasePairs"] != []:
        raise ValueError("new comparison coverage")
    row = records[0]
    case = next(c for c in cases if c["caseId"] == row["caseId"])
    if row["expectedSkill"] != case["expected"]["sixSkill"] or row["outcome"] != case["expected"]["outcome"]:
        raise ValueError("comparison global decision binding")
    if not set(row["nearestPublicCaseIds"]) <= public_ids:
        raise ValueError("unknown public comparison")
    if {r["setVersion"] for r in row["nearestExcludedCases"]} != set(excluded):
        raise ValueError("excluded nearest coverage")
    for ref in row["nearestExcludedCases"]:
        if ref["caseId"] not in {c["caseId"] for c in excluded[ref["setVersion"]]}:
            raise ValueError("unknown excluded comparison")
    check_counterfactual(case, row, manifest, bodies)


def audit(contract: dict, case_path: Path) -> dict:
    root = PRIVATE_BASE / "collection-05"
    if contract["collectionVersion"] != "production-routing-held-out-collection-0.5.0" or contract["setVersion"] != VERSION:
        raise ValueError("collection identity")
    if contract["storageAuthorization"]["root"] != str(root) or case_path != root / "cases.json":
        raise ValueError("case storage")
    public_inputs(contract)
    raw = legacy.private_file(case_path)
    if set(load(raw)) != {"setVersion", "cases"}:
        raise ValueError("case envelope")
    cases, metadata = legacy.validate.load_held_out_cases(case_path)
    if metadata["sha256"] != digest(raw):
        raise ValueError("case read drift")
    if metadata["setVersion"] != VERSION or len(cases) != 12 or not all(c["mandatory"] for c in cases):
        raise ValueError("case denominator")
    if {c["caseId"] for c in cases} != {f"SE-{i}" for i in range(1200, 1212)}:
        raise ValueError("case identities")
    if Counter(c["category"] for c in cases) != Counter(explicit=2, implicit=2, contextual=2, negative=3, safety=3):
        raise ValueError("category denominator")
    for skill in legacy.validate.CAPABILITIES:
        pair = [c for c in cases if c["capability"] == skill]
        if len(pair) != 2 or sum(c["category"] in {"explicit", "implicit", "contextual"} for c in pair) != 1:
            raise ValueError("capability denominator")
    paths = {INITIAL: PRIVATE_BASE / "cases.json", OLD: PRIVATE_BASE / "collection-03/cases.json",
             PREVIOUS: PRIVATE_BASE / "collection-04/cases.json"}
    if set(contract["excludedSets"]) != set(paths):
        raise ValueError("excluded inventory")
    excluded = {}
    for version, path in paths.items():
        declared = contract["excludedSets"][version]
        old_raw = legacy.private_file(path)
        if declared["path"] != str(path) or digest(old_raw) != declared["sha256"]:
            raise ValueError("excluded binding")
        if set(load(old_raw)) != {"setVersion", "cases"}:
            raise ValueError("excluded envelope")
        old, old_meta = legacy.validate.load_held_out_cases(path)
        if old_meta["sha256"] != digest(old_raw) or old_meta["setVersion"] != version or len(old) != 12:
            raise ValueError("excluded identity or read drift")
        excluded[version] = old
    retention_raw = legacy.private_file(root / "retention.json")
    retention = load(retention_raw)
    required = {"schemaVersion", "sourceSetVersion", "sourceCasesSha256", "independentReceiptSha256",
                "independentReportSha256", "retainedCaseIds", "replacedCaseIds", "retainedCaseSha256"}
    if set(retention) != required or retention["schemaVersion"] != "1.0" or digest(retention_raw) != contract["retention"]["sha256"]:
        raise ValueError("retention envelope or drift")
    review_raw = legacy.private_file(PRIVATE_BASE / "collection-04/independent-receipt.json")
    report_raw = legacy.private_file(PRIVATE_BASE / "collection-04/independent-review.md")
    if (digest(review_raw) != contract["retention"]["independentReceiptSha256"]
            or digest(review_raw) != retention["independentReceiptSha256"]
            or digest(report_raw) != contract["retention"]["independentReportSha256"]
            or digest(report_raw) != retention["independentReportSha256"]
            or retention["sourceSetVersion"] != PREVIOUS
            or retention["sourceCasesSha256"] != contract["excludedSets"][PREVIOUS]["sha256"]):
        raise ValueError("retention review binding")
    review = load(review_raw)
    if (review["status"] != "stopped_on_p2" or review["severityCounts"] != {"P1": 0, "P2": 1}
            or review["affectedCaseCount"] != 1 or review["routingSemanticsPassedCount"] != 12
            or review["novelNewCaseCount"] != 2 or review["casesSha256"] != retention["sourceCasesSha256"]
            or review["filesSha256"]["independent-review.md"] != digest(report_raw)):
        raise ValueError("retention review identity")
    failed = replacement_from_report(report_raw.decode("utf-8"), excluded[PREVIOUS])
    legacy.audit_candidate(contract)
    snapshot = ROOT / contract["candidate"]["snapshotRelativePath"]
    manifest_raw = (snapshot / "manifest.json").read_bytes()
    if digest(manifest_raw) != contract["candidate"]["manifestSha256"]:
        raise ValueError("manifest read drift")
    manifest = load(manifest_raw)
    bodies = {}
    for skill in manifest["skills"]:
        path = skill["path"]
        body = (snapshot / path).read_bytes()
        if digest(body) != manifest["resources"][path]:
            raise ValueError("body read drift")
        bodies[path] = body.decode("utf-8")
    evidence_raw = legacy.private_file(root / "evidence.json")
    evidence = load(evidence_raw)
    Draft202012Validator(load((ROOT / EVIDENCE_NAME).read_bytes())).validate(evidence)
    if evidence["setVersion"] != VERSION or evidence["casesSha256"] != digest(raw):
        raise ValueError("evidence case binding")
    previous.check_routing(cases, evidence["routing"], manifest, bodies)
    new = check_lineage(cases, evidence["lineage"], excluded[PREVIOUS], retention, failed)
    check_novelty(cases, new, evidence, legacy.validate.load_cases(), excluded, manifest, bodies)
    return {"status": "mechanical_checks_passed", "heldOut": metadata,
            "newCaseCount": 1, "retainedCaseCount": 11, "routingAssessmentCount": 12,
            "noveltyComparisonCount": 1, "counterfactualDecisionCount": 2,
            "publicExclusionCount": 46, "privateExclusionCounts": [12, 12, 12],
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
            raise ValueError("full source required")
        raw = source_guard.git(ROOT, "show", args.source + ":" + CONTRACT_NAME)
        contract = load(raw)
        if set(contract["sourceFiles"]) != SOURCE_NAMES or len(contract["sourceFiles"]) != len(SOURCE_NAMES):
            raise ValueError("source inventory")
        source_guard.verify(ROOT, args.source, contract["sourceFiles"])
        result = audit(contract, args.cases)
        source_guard.verify(ROOT, args.source, contract["sourceFiles"])
        result.update(sourceCommit=args.source, sourceFileCount=len(SOURCE_NAMES), headIsCondition=False,
                      contractSha256=digest(raw))
    except Exception as error:
        print(json.dumps({"status": "blocked", "errorType": type(error).__name__}))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
