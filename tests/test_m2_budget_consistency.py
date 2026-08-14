import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
FLOW = REPO / "plugins" / "bitz-flow" / ".spec"
SDD_ROADMAP = REPO / "plugins" / "bitz-sdd" / ".spec" / "ROADMAP.md"
ALLOWLIST = FLOW / "budget-consistency-exceptions.json"


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
    if "bitz-flow V2" in sdd_roadmap and "3 PR / 9 session" not in sdd_roadmap:
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
    assert len(config["exceptions"]) == 1
