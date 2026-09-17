"""review台帳の整合を検査する。散文から意味を推測しない。"""
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
        errors.append("条件の対応が重複しています")
    if set(mapped) != actual:
        errors.append(f"条件の対応が一致しません: 欠落={sorted(actual-set(mapped))}、未知={sorted(set(mapped)-actual)}")
    for path, expected in ledger["sources"].items():
        source = root / path
        if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != expected:
            errors.append(f"reviewが古くなっています: {path}")
    for group in ledger["groups"]:
        if not group["rationale"] or not group["sources"] or any(p not in ledger["sources"] for p in group["sources"]):
            errors.append(f"根拠文書または理由がありません: {group['id']}")
    # このreviewで解消した不整合について、独立に固定した期待値。
    expected_rows = {
        "CTX-COVERAGE-TEST-MUST": ("context, verify", "error", "blocked", "skip-target"),
        "CTX-COVERAGE-TEST-MUST-IMPLEMENT": ("context", "warning", "passed_with_warnings", "continue"),
        "CTX-COVERAGE-TEST-SHOULD": ("context, verify", "warning", "passed_with_warnings", "continue"),
        "MULTI-DEPENDENCY": ("context, verify", "error", "blocked", "skip-target"),
        "MULTI-DEPENDENCY-DOCTOR": ("doctor", "error", "blocked", "skip-check"),
        "VERIFY-CONFIG-UNTRACKED": ("verify", "error", "blocked", "skip-binding"),
        "VERIFY-TEST-OUTSIDE-CWD": ("verify", "error", "blocked", "skip-binding"),
    }
    by_id = {row[0]: row for row in rows}
    for identifier, expected in expected_rows.items():
        row = by_id.get(identifier)
        if row is None or tuple(row[index].strip() for index in (1, 3, 4, 6)) != expected:
            errors.append(f"意味の回帰があります: {identifier}")
    issues = ledger["openIssues"]
    if ledger["reviewStatus"] not in {"Pending", "Passed"}:
        errors.append("reviewStatusが不正です")
    if issues and ledger["reviewStatus"] != "Pending":
        errors.append("未解決の論点が残る場合は完了にできません")
    return {"conditions": len(actual), "mappedConditions": len(set(mapped)), "sourceDocuments": len(ledger["sources"]),
            "errors": errors, "semantic_coverage": "Passed" if not errors and not issues and ledger["reviewStatus"] == "Passed" else "Pending",
            "openIssues": issues}
