#!/usr/bin/env python3
"""提案25のP0/P1を既存の受入fixtureと静的監査へ対応付ける。"""
from __future__ import annotations

import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "fixtures"))

from conformance.selection import step_ids
import conformance.diagnostic_coverage as diagnostic_coverage

SOURCE = Path("docs/04.提案資料/25_Core-1.0実装前最終reviewと修正提案.md")

FINDINGS = {
    "P0": {
        "FIN-FIX-001": {"allConformance": True},
        "FIN-DIAG-001": {"prefixes": ("SINGLE-089", "SINGLE-090", "SINGLE-091",
                                             "SINGLE-092", "SINGLE-093", "SINGLE-094",
                                             "SINGLE-095"),
                         "diagnosticCoverage": True},
        "FIN-EAI-001": {"prefixes": tuple(f"SINGLE-{number:03d}" for number in range(96, 104))},
        "FIN-OUT-001": {"prefixes": ("SINGLE-104", "SINGLE-105", "SINGLE-106")},
        "FIN-TARGET-001": {"prefixes": tuple(f"SINGLE-{number:03d}" for number in range(107, 114))},
        "FIN-FM-001": {"prefixes": tuple(f"SINGLE-{number:03d}" for number in range(114, 121))},
    },
    "P1": {
        "FIN-DIGEST-001": {"exact": ("SINGLE-042", "MULTI-002-01", "SINGLE-121",
                                      "SINGLE-122", "SINGLE-123", "SINGLE-124")},
        "FIN-IO-001": {"prefixes": ("SINGLE-125",)},
        "FIN-PROC-001": {"prefixes": ("SINGLE-126",)},
        "FIN-CLI-001": {"prefixes": ("SINGLE-127",)},
        "FIN-PERF-001": {"performance": True},
    },
}


def _source_findings(text: str, section: int) -> list[str]:
    pattern = rf"^### {section}\.\d+ `([^`]+)`:"
    return re.findall(pattern, text, re.MULTILINE)


def _matching_fixtures(identifiers: list[str], rule: dict) -> list[str]:
    selected = []
    for exact in rule.get("exact", ()):
        if exact in identifiers:
            selected.append(exact)
    for prefix in rule.get("prefixes", ()):
        selected.extend(identifier for identifier in identifiers
                        if identifier == prefix or identifier.startswith(prefix + "-"))
    return list(dict.fromkeys(selected))


def audit(root: Path = ROOT) -> dict:
    errors = []
    source = (root / SOURCE).read_text(encoding="utf-8")
    identifiers = step_ids(5)
    expected = {priority: list(findings) for priority, findings in FINDINGS.items()}
    actual = {"P0": _source_findings(source, 4), "P1": _source_findings(source, 5)}
    if actual != expected:
        errors.append(f"提案25のP0/P1集合が閉包定義と一致しません: {actual}")

    ledger = json.loads((root / "fixtures/conformance/diagnostic-coverage.json").read_text())
    diagnostic = diagnostic_coverage.validate(ledger=ledger, root=root)
    if diagnostic["semantic_coverage"] != "Passed" or diagnostic["openIssues"]:
        errors.append("診断の意味の網羅のレビューに未解決項目があります")

    rows = []
    for priority, findings in FINDINGS.items():
        for identifier, rule in findings.items():
            fixture_ids = identifiers if rule.get("allConformance") else _matching_fixtures(identifiers, rule)
            if not rule.get("performance") and not fixture_ids:
                errors.append(f"閉包fixtureがありません: {identifier}")
            for exact in rule.get("exact", ()):
                if exact not in fixture_ids:
                    errors.append(f"閉包fixtureが欠落しています: {identifier}: {exact}")
            for prefix in rule.get("prefixes", ()):
                if not any(value == prefix or value.startswith(prefix + "-") for value in fixture_ids):
                    errors.append(f"閉包fixture群が欠落しています: {identifier}: {prefix}")
            rows.append({
                "id": identifier,
                "priority": priority,
                "evidence": ("performance" if rule.get("performance") else
                             "all-conformance" if rule.get("allConformance") else
                             "conformance-and-diagnostic-audit" if rule.get("diagnosticCoverage") else
                             "conformance"),
                "fixtureIds": fixture_ids,
            })

    return {
        "status": "Passed" if not errors else "Failed",
        "source": SOURCE.as_posix(),
        "sourceFindings": actual,
        "diagnosticCoverage": diagnostic["semantic_coverage"],
        "fixtureCount": len(identifiers),
        "findings": rows,
        "errors": errors,
    }


def main() -> int:
    report = audit()
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if report["status"] == "Passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
