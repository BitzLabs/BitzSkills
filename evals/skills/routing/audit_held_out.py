#!/usr/bin/env python3
"""固定した初期保持集合を検査し、公開可能な集計だけを返す。"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import stat
import sys
import unicodedata

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "evals/skills"))
import validate  # noqa: E402


def private_file(path: Path) -> bytes:
    if any(p.is_symlink() for p in [path, *path.parents]):
        raise ValueError("symlink storage")
    if not path.is_file() or stat.S_IMODE(path.stat().st_mode) != 0o600:
        raise ValueError("private file permissions")
    if stat.S_IMODE(path.parent.stat().st_mode) != 0o700:
        raise ValueError("private root permissions")
    if path.resolve().is_relative_to(ROOT):
        raise ValueError("public storage")
    return path.read_bytes()


def normalized_input(case: dict) -> tuple:
    def normalize(value):
        return " ".join(unicodedata.normalize("NFKC", value).casefold().split())
    return normalize(case["prompt"]), tuple(sorted(normalize(c) for c in case["context"]))


def audit_candidate(contract: dict) -> None:
    relative = Path(contract["candidate"]["snapshotRelativePath"])
    if relative.is_absolute() or ".." in relative.parts or relative.parts[0] != ".venv":
        raise ValueError("snapshot path")
    snapshot = ROOT / relative
    if any(p.is_symlink() for p in [snapshot, *snapshot.parents]):
        raise ValueError("snapshot symlink")
    manifest_path = snapshot / "manifest.json"
    if manifest_path.is_symlink():
        raise ValueError("manifest symlink")
    raw = manifest_path.read_bytes()
    candidate = contract["candidate"]
    if hashlib.sha256(raw).hexdigest() != candidate["manifestSha256"]:
        raise ValueError("candidate manifest drift")
    manifest = json.loads(raw)
    if manifest["sourceCommit"] != candidate["sourceCommit"] or manifest["candidateVersion"] != candidate["candidateVersion"]:
        raise ValueError("candidate identity drift")
    if len(manifest["skills"]) != candidate["skillCount"] or len(manifest["resources"]) != candidate["resourceCount"]:
        raise ValueError("candidate denominator drift")
    # 名前を全件検査してから本文を読む。
    paths = []
    for name, digest in manifest["resources"].items():
        parts = name.split("/")
        if len(parts) < 3 or parts[0] != "resources" or parts[1] not in {"bitz-core", "bitz-sdd", "bitz-quality"}:
            raise ValueError("resource package")
        if "\\" in name or any(p in {"", ".", "..", ".git", ".env", ".credentials.json"} or p.startswith(".env.") for p in parts):
            raise ValueError("resource path")
        path = snapshot / name
        if any(p.is_symlink() for p in [path, *path.parents] if p.is_relative_to(snapshot)):
            raise ValueError("resource symlink")
        paths.append((path, digest))
    for path, digest in paths:
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError("candidate resource drift")


def audit_novelty(contract: dict, case_path: Path, cases: list) -> dict:
    audit_candidate(contract)
    excluded = contract["excludedSet"]
    previous_path = Path(excluded["path"])
    raw = private_file(previous_path)
    if hashlib.sha256(raw).hexdigest() != excluded["sha256"]:
        raise ValueError("excluded set drift")
    previous, metadata = validate.load_held_out_cases(previous_path)
    if metadata["setVersion"] != excluded["setVersion"] or metadata["caseCount"] != excluded["caseCount"]:
        raise ValueError("excluded set identity")
    public = validate.load_cases()
    if {c["caseId"] for c in cases} & {c["caseId"] for c in previous}:
        raise ValueError("excluded case identity collision")
    normalized = [normalized_input(c) for c in cases]
    excluded_inputs = {normalized_input(c) for c in public + previous}
    if len(set(normalized)) != len(cases) or set(normalized) & excluded_inputs:
        raise ValueError("normalized input collision")
    novelty_path = case_path.with_name("novelty.json")
    novelty_raw = private_file(novelty_path)
    novelty = json.loads(novelty_raw)
    schema_path = ROOT / "evals/skills/routing/novelty.schema.json"
    validator = Draft202012Validator(json.loads(schema_path.read_bytes()))
    validator.validate(novelty)
    if novelty["setVersion"] != contract["setVersion"] or novelty["casesSha256"] != hashlib.sha256(case_path.read_bytes()).hexdigest():
        raise ValueError("novelty binding")
    public_ids = {c["caseId"] for c in public}
    previous_ids = {c["caseId"] for c in previous}
    if set(novelty["publicCasesConsidered"]) != public_ids or set(novelty["excludedCasesConsidered"]) != previous_ids:
        raise ValueError("novelty exclusion coverage")
    records = novelty["comparisons"]
    if len(records) != len(cases) or {n["caseId"] for n in records} != {c["caseId"] for c in cases}:
        raise ValueError("novelty case coverage")
    for record in records:
        if not set(record["nearestPublicCaseIds"]) <= public_ids or not set(record["nearestExcludedCaseIds"]) <= previous_ids:
            raise ValueError("unknown comparison identity")
    return {"noveltySha256": hashlib.sha256(novelty_raw).hexdigest(), "publicExclusionCount": len(public),
            "previousExclusionCount": len(previous), "comparisonCount": len(records),
            "semanticNovelty": "requires_independent_review"}


def audit(contract_path: Path, case_path: Path) -> dict:
    contract = json.loads(contract_path.read_bytes())
    versions = {"production-routing-held-out-collection-0.1.0": 800,
                "production-routing-held-out-collection-0.2.0": 900}
    if contract["collectionVersion"] not in versions:
        raise ValueError("unsupported collection")
    private_root = Path(contract["storageAuthorization"]["root"])
    # 実体へ解決してから比較すると、symlinkによる置換を見逃すため先に拒否する。
    if case_path != private_root / "cases.json":
        raise ValueError("unexpected case path")
    private_file(case_path)
    for relative, expected in contract["inputSha256"].items():
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("invalid input path")
        if hashlib.sha256((ROOT / path).read_bytes()).hexdigest() != expected:
            raise ValueError("input drift")
    cases, metadata = validate.load_held_out_cases(case_path)
    if metadata["setVersion"] != contract["setVersion"]:
        raise ValueError("set version drift")
    if metadata["caseCount"] != 12 or contract["denominator"]["maxCases"] != 12:
        raise ValueError("case denominator")
    first_id = versions[contract["collectionVersion"]]
    if {c["caseId"] for c in cases} != {f"SE-{n}" for n in range(first_id, first_id + 12)}:
        raise ValueError("case identity")
    if not all(c["mandatory"] for c in cases):
        raise ValueError("optional case")
    expected_categories = Counter(explicit=2, implicit=2, contextual=2, negative=3, safety=3)
    if Counter(c["category"] for c in cases) != expected_categories:
        raise ValueError("category denominator")
    capabilities = set(validate.CAPABILITIES)
    for capability in capabilities:
        pair = [c for c in cases if c["capability"] == capability]
        if len(pair) != 2:
            raise ValueError("capability denominator")
        positives = [c for c in pair if c["category"] in {"explicit", "implicit", "contextual"}]
        boundaries = [c for c in pair if c["category"] in {"negative", "safety"}]
        if len(positives) != 1 or positives[0]["mode"] != "use" or positives[0]["expected"]["outcome"] != "proceed":
            raise ValueError("positive condition")
        if len(boundaries) != 1:
            raise ValueError("boundary condition")
        boundary = boundaries[0]
        required_outcome = {"do-not-use": "not-applicable", "stop": "stop"}.get(boundary["mode"])
        if required_outcome is None or boundary["expected"]["outcome"] != required_outcome:
            raise ValueError("boundary outcome")
    if any(c["capability"] not in capabilities for c in cases):
        raise ValueError("unknown capability")
    for case in cases:
        if set(case["expected"]["requiredEvents"]) & set(case["expected"]["forbiddenEvents"]):
            raise ValueError("event contradiction")
    result = {
        "status": "mechanical_checks_passed",
        "contractSha256": hashlib.sha256(contract_path.read_bytes()).hexdigest(),
        "heldOut": metadata,
        "categoryCounts": dict(sorted(expected_categories.items())),
        "capabilityCount": len(capabilities),
        "positiveCases": 6,
        "negativeOrStopCases": 6,
        "primaryModelTrajectories": 0,
        "certifiesSkillGate": False,
    }
    if first_id == 900:
        result["novelty"] = audit_novelty(contract, case_path, cases)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--collection", choices=["initial", "novelty"], default="initial")
    args = parser.parse_args()
    try:
        filename = "held-out-collection.json" if args.collection == "initial" else "held-out-collection-v0.2.json"
        result = audit(Path(__file__).with_name(filename), args.cases)
    except Exception as error:
        # schema診断などには非公開本文が混ざる。例外文字列・tracebackを公開しない。
        print(json.dumps({"status": "blocked", "errorType": type(error).__name__}))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
