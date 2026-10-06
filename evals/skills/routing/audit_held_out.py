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

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "evals/skills"))
import validate  # noqa: E402


def audit(contract_path: Path, case_path: Path) -> dict:
    contract = json.loads(contract_path.read_bytes())
    if contract["collectionVersion"] != "production-routing-held-out-collection-0.1.0":
        raise ValueError("unsupported collection")
    private_root = Path(contract["storageAuthorization"]["root"])
    # 実体へ解決してから比較すると、symlinkによる置換を見逃すため先に拒否する。
    if case_path != private_root / "cases.json":
        raise ValueError("unexpected case path")
    if any(path.is_symlink() for path in [case_path, private_root, *private_root.parents]):
        raise ValueError("symlink storage")
    if stat.S_IMODE(private_root.stat().st_mode) != 0o700:
        raise ValueError("private root permissions")
    if not case_path.is_file() or stat.S_IMODE(case_path.stat().st_mode) != 0o600:
        raise ValueError("case file permissions")
    if private_root.resolve().is_relative_to(ROOT):
        raise ValueError("public storage")
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
    if {c["caseId"] for c in cases} != {f"SE-{n}" for n in range(800, 812)}:
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
    return {
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = audit(Path(__file__).with_name("held-out-collection.json"), args.cases)
    except Exception as error:
        # schema診断などには非公開本文が混ざる。例外文字列・tracebackを公開しない。
        print(json.dumps({"status": "blocked", "errorType": type(error).__name__}))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
