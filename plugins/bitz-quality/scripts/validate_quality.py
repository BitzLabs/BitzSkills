#!/usr/bin/env python3
"""Validate document shape and consistency of declared facts; never infer quality."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from jsonschema import Draft202012Validator, RefResolver


ROOT = Path(__file__).resolve().parents[1]
BANDS = {"Q0": 0, "Q1": 1, "Q2": 2, "Q3": 3}
EXIT_CODES = {"passed": 0, "passed_with_warnings": 0, "failed": 1, "blocked": 2, "error": 3, None: 4}


def validate(kind: str, document: object) -> list[str]:
    if kind not in {"plan", "review"}:
        raise ValueError("unknown document kind")
    schema = json.loads((ROOT / "schemas" / f"quality-{kind}.schema.json").read_text(encoding="utf-8"))
    observation = json.loads((ROOT / "schemas/core-observation.schema.json").read_text(encoding="utf-8"))
    def reject_remote(uri):
        raise ValueError("only packaged local schemas are allowed")

    resolver = RefResolver.from_schema(schema, store={observation["$id"]: observation}, handlers={"http": reject_remote, "https": reject_remote, "file": reject_remote})
    errors = [f"schema: {'/'.join(map(str, e.absolute_path))}: {e.message}" for e in Draft202012Validator(schema, resolver=resolver).iter_errors(document)]
    if errors:
        return errors
    return validate_core_results(document) + (validate_plan(document) if kind == "plan" else validate_review(document))


def validate_core_results(document: dict) -> list[str]:
    errors = []
    for item in document["coreResults"]:
        if item["exitCode"] != EXIT_CODES[item["status"]]:
            errors.append("Core status and exit code contradict public contract")
        raw = item["rawResult"]
        if item["exitCode"] == 4:
            if raw is not None or item["status"] is not None or not item["stderr"]:
                errors.append("invalid invocation has no Core result/status and needs stderr evidence")
        elif raw is None or raw.get("operation") != item["operation"] or raw.get("status") != item["status"]:
            errors.append("Core observation must retain matching original operation and status")
        if item["role"] == "current_gate" and item["subjectCommit"] != document["subjectCommit"]:
            errors.append("current Core gate belongs to another subject commit")
        revision = raw.get("revision") if raw else None
        if revision and revision.get("commit") != item["subjectCommit"]:
            errors.append("Core observation subject contradicts original revision")
    return errors


def validate_plan(document: dict) -> list[str]:
    errors = []
    risk = document["risk"]
    band = risk["band"]
    areas = list(risk["areas"].values())
    if band is None or any(a["minimumBand"] is None for a in areas):
        if document["planningStatus"] == "proposed":
            errors.append("unknown risk needs information or blocked status")
    if band is not None:
        minimum = max((BANDS[a["minimumBand"]] for a in areas if a["minimumBand"] is not None), default=0)
        if BANDS[band] < minimum and risk["downgradeApproval"] is None:
            errors.append("risk downgrade requires explicit human approval record")
    if band in {"Q2", "Q3"}:
        if not document["independentReviewPlanned"]:
            errors.append("Q2/Q3 require independent quality review plan")
        if document["flow"] not in {"full", "spike"}:
            errors.append("Q2/Q3 require full flow or an isolated spike")
    ids = [e["evidenceId"] for e in document["evidencePlan"]]
    if len(ids) != len(set(ids)):
        errors.append("duplicate planned evidence id")
    if not any(e["priority"] == "required" for e in document["evidencePlan"]):
        errors.append("at least one required evidence item is necessary")
    if any(e["role"] == "current_gate" and e["exitCode"] != 0 for e in document["coreResults"]) and document["planningStatus"] == "proposed":
        errors.append("current Core non-success needs information or blocked planning status")
    for item in document["notRun"]:
        if not set(item["evidenceIds"]).issubset(ids):
            errors.append("unexecuted plan checks must refer to planned evidence ids")
    return errors


def validate_review(document: dict) -> list[str]:
    errors = []
    required = set(document["requiredEvidenceIds"])
    collected = document["collectedEvidence"]
    ids = [e["evidenceId"] for e in collected]
    if len(ids) != len(set(ids)):
        errors.append("duplicate collected evidence id")
    missing = required - set(ids)
    if set(document["missingEvidenceIds"]) != missing:
        errors.append("missing evidence ids must match uncollected required ids")
    if any(e["subjectCommit"] != document["subjectCommit"] for e in collected):
        errors.append("collected evidence belongs to another subject commit")
    independence = document["independence"]
    if independence["independent"] and independence["implementationRunId"] == independence["reviewRunId"]:
        errors.append("independent review requires another run id")
    critical = any(f["severity"] in {"critical", "major"} and not f["resolved"] for f in document["findings"])
    incomplete = bool(missing) or not independence["independent"] or document["subjectCommit"] is None or document["riskBand"] is None
    incomplete |= document["riskBand"] in {"Q2", "Q3"} and not document["qualityPlanPresent"]
    gates = [e for e in document["coreResults"] if e["role"] == "current_gate"]
    critical |= any(e["status"] == "failed" for e in gates)
    incomplete |= any(e["status"] in {"blocked", "error", None} for e in gates)
    incomplete |= not {"context", "check"}.issubset({e["operation"] for e in gates})
    for item in gates:
        raw = item["rawResult"] or {}
        if item["operation"] in {"context", "check", "verify"}:
            revision = raw.get("revision") or {}
            incomplete |= revision.get("commit") != document["subjectCommit"] or revision.get("dirty") is not False
        if item["operation"] == "context":
            incomplete |= raw.get("resolution", {}).get("complete") is not True or not raw.get("contextDigest")
    for item in document["notRerun"]:
        evidence_ids = set(item["evidenceIds"])
        if not evidence_ids.issubset(required | set(ids)):
            errors.append("unexecuted checks must refer to declared evidence ids")
        if not item["evidenceAvailable"] and evidence_ids.intersection(ids):
            errors.append("unavailable evidence cannot be declared collected")
    expected = "not_ready" if critical else "unknown" if incomplete else "ready_with_conditions" if document["conditions"] else "ready"
    if document["decision"] != expected:
        errors.append(f"decision contradicts declared facts; expected {expected}")
    if document["decision"] == "ready" and any(not f["resolved"] and f["severity"] == "minor" for f in document["findings"]):
        errors.append("unresolved minor finding needs an explicit noncritical condition")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=["plan", "review"])
    parser.add_argument("document", type=Path)
    args = parser.parse_args()
    try:
        errors = validate(args.kind, json.loads(args.document.read_text(encoding="utf-8")))
    except (OSError, ValueError) as error:
        errors = [f"input: {type(error).__name__}: {error}"]
    print(json.dumps({"status": "invalid" if errors else "valid", "scope": "format-and-declared-consistency", "certifiesQuality": False, "errors": errors}, ensure_ascii=False))
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
