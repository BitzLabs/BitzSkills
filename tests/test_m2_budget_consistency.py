import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
FLOW = REPO / "plugins" / "bitz-flow" / ".spec"
SDD_ROADMAP = REPO / "plugins" / "bitz-sdd" / ".spec" / "ROADMAP.md"
ALLOWLIST = FLOW / "budget-consistency-exceptions.json"
M2_MANIFEST = REPO / "evals" / "flow-core" / "m2-eval" / "run-manifest-m2-remediation.json"
M2_CONTROL_DECISION = FLOW / "reports" / "decision-2026-08-17-m2-integrity-boundary-and-control-plane.md"
M2_SCOPE_DECISION = FLOW / "reports" / "decision-2026-08-17-v2-operational-integrity-scope.md"


def _observed() -> set[str]:
    design = (FLOW / "design" / "FLW-DSN-014.md").read_text(encoding="utf-8")
    roadmap = (FLOW / "ROADMAP.md").read_text(encoding="utf-8")
    sdd_roadmap = SDD_ROADMAP.read_text(encoding="utf-8")
    observed: set[str] = set()

    if "3 + 3 = 6 PR" in design and "M3 budget — 8 PR / 26 session" not in design:
        observed.add("budget:m3-design:6pr-20session!=8pr-26session")
    if "M3: 6PR/20session" in roadmap and "M3: 8PR/26session" not in roadmap:
        observed.add("budget:m3-roadmap:6pr-20session!=8pr-26session")
    if "設計再整備 3 PR / 9 session" not in design and "設計再整備 3 PR / 9 session" not in roadmap:
        observed.add("budget:m2-design-rework:missing-3pr-9session")
    if (
        "bitz-flow V2" in sdd_roadmap
        and (
            "3 PR / 9 session" not in sdd_roadmap
            or "33 PR / 109 session" not in sdd_roadmap
        )
    ):
        observed.add("budget-reference:bitz-sdd-roadmap:missing-v2-total")
    return observed


def test_budget_exceptions_are_exact_and_shrink_only() -> None:
    config = json.loads(ALLOWLIST.read_text(encoding="utf-8"))
    expected = config["exceptions"]
    assert config["schema_version"] == 1
    assert config["additions_allowed"] is False
    assert expected == sorted(set(expected))
    observed = _observed()
    assert observed == set(expected), (
        "budget consistency exceptions changed; additions are forbidden and fixed "
        "exceptions must be removed in the same change: "
        f"new={sorted(observed - set(expected))}, stale={sorted(set(expected) - observed)}"
    )


def test_budget_exception_scope_is_fixed() -> None:
    config = json.loads(ALLOWLIST.read_text(encoding="utf-8"))
    assert config["issue"] == "SI-FLW-052"
    assert len(config["exceptions"]) == 0


def test_FLW_FR_012_m2_manifest_matches_the_current_control_decision() -> None:
    manifest = json.loads(M2_MANIFEST.read_text(encoding="utf-8"))
    entries = manifest["entries"]
    budget = manifest["budget"]

    assert manifest["schema"] == "bitz-flow/m2-remediation-run-manifest/v2"
    assert budget == {
        "mode": "unbounded",
        "scope": "M2 remediation / FLW-REV-018",
        "decision_ref": ".spec/reports/decision-2026-08-16-flw-rev-018-remediation.md",
        "exception_ref": ".spec/reports/decision-2026-08-17-si-flw-076-m2-budget-exception.md",
        "recalibration_pending": "FLW-REV-019:GP-006",
    }
    assert [entry["pr"] for entry in entries] == [289, 290, 291, 292, 293, 294]
    assert len({entry["pr"] for entry in entries}) == len(entries)
    assert [entry["pr"] for entry in entries if entry["sessions"] is None] == [294]
    assert next(entry for entry in entries if entry["pr"] == 294)["review_fixes"] == 16


def test_FLW_FR_012_m2_control_documents_hold_completion_and_recalibration() -> None:
    roadmap = (FLOW / "ROADMAP.md").read_text(encoding="utf-8")
    design = (FLOW / "design" / "FLW-DSN-014.md").read_text(encoding="utf-8")
    decision = M2_CONTROL_DECISION.read_text(encoding="utf-8")

    assert "FLW-REV-019" in roadmap
    assert "CONDITIONAL_PASS 3.41" in roadmap
    assert "Completion Gate は保留" in roadmap
    assert "FLW-REV-019:GP-006" in roadmap
    assert "FLW-REV-019:GP-006" in design
    assert "SI-FLW-074" in decision
    assert "GP-006" in decision


def test_FLW_FR_012_v2_scope_excludes_strong_tamper_resistance() -> None:
    roadmap = (FLOW / "ROADMAP.md").read_text(encoding="utf-8")
    design = (FLOW / "design" / "FLW-DSN-014.md").read_text(encoding="utf-8")
    issue = (FLOW / "spec-issues" / "SI-FLW-072.md").read_text(encoding="utf-8")
    decision = M2_SCOPE_DECISION.read_text(encoding="utf-8")

    decision_ref = ".spec/reports/decision-2026-08-17-v2-operational-integrity-scope.md"
    assert decision_ref in roadmap
    assert decision_ref in design
    assert decision_ref in issue
    assert "V2 の要件・設計・Completion Gate の前提に含めない" in decision
    assert "通常運用" in decision
    assert "将来この保証が必要になった場合だけ" in decision
    assert "V2 の対象外" in issue
