"""Check review ledger integrity; does not infer semantics from prose."""
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "fixtures/conformance/diagnostic-coverage.json"
REGISTRY = "docs/03.詳細設計/00_共通契約/05_Diagnostic-registry.md"


def validate(ledger=None, root=ROOT):
    ledger = json.loads(LEDGER.read_text()) if ledger is None else ledger
    errors = []
    text = (root / REGISTRY).read_text()
    rows = re.findall(r"^\| `([^`]+)` \| ([^|]+) \| `([^`]+)` \| ([^|]+) \| ([^|]+) \| ([^|]+) \| `([^`]+)` \| (\d+) \| (.*)\|$", text, re.M)
    actual = {row[0] for row in rows}
    mapped = [identifier for group in ledger["groups"] for identifier in group["conditionIds"]]
    if len(mapped) != len(set(mapped)):
        errors.append("duplicate condition mapping")
    if set(mapped) != actual:
        errors.append(f"condition mapping mismatch: missing={sorted(actual-set(mapped))}, unknown={sorted(set(mapped)-actual)}")
    for path, expected in ledger["sources"].items():
        source = root / path
        if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != expected:
            errors.append(f"review stale: {path}")
    for group in ledger["groups"]:
        if not group["rationale"] or not group["sources"] or any(p not in ledger["sources"] for p in group["sources"]):
            errors.append(f"missing source/rationale: {group['id']}")
    # Independently fixed expectations for the inconsistencies resolved in this review.
    expected_rows = {
        "CTX-COVERAGE-TEST-MUST": ("context, verify", "error", "blocked", "skip-target"),
        "CTX-COVERAGE-TEST-MUST-IMPLEMENT": ("context", "warning", "passed_with_warnings", "continue"),
        "CTX-COVERAGE-TEST-SHOULD": ("context, verify", "warning", "passed_with_warnings", "continue"),
        "MONO-DEPENDENCY": ("context, verify", "error", "blocked", "skip-target"),
        "MONO-DEPENDENCY-DOCTOR": ("doctor", "error", "blocked", "skip-check"),
        "VERIFY-CONFIG-UNTRACKED": ("verify", "error", "blocked", "skip-binding"),
        "VERIFY-TEST-OUTSIDE-CWD": ("verify", "error", "blocked", "skip-binding"),
    }
    by_id = {row[0]: row for row in rows}
    for identifier, expected in expected_rows.items():
        row = by_id.get(identifier)
        if row is None or tuple(row[index].strip() for index in (1, 3, 4, 6)) != expected:
            errors.append(f"semantic regression: {identifier}")
    issues = ledger["openIssues"]
    if ledger["reviewStatus"] not in {"Pending", "Passed"}:
        errors.append("invalid reviewStatus")
    if issues and ledger["reviewStatus"] != "Pending":
        errors.append("open issues cannot be marked complete")
    return {"conditions": len(actual), "mappedConditions": len(set(mapped)), "sourceDocuments": len(ledger["sources"]),
            "errors": errors, "semantic_coverage": "Passed" if not errors and not issues and ledger["reviewStatus"] == "Passed" else "Pending",
            "openIssues": issues}
