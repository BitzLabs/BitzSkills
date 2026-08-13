import json
import re
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
FLOW_SPEC = REPO / "plugins" / "bitz-flow" / ".spec"
DESIGN_016 = FLOW_SPEC / "design" / "FLW-DSN-016.md"
ALLOWLIST = FLOW_SPEC / "consistency-exceptions.json"


def _fixture_max(text: str) -> int:
    numbers = [int(value) for value in re.findall(r"M2-FLT-(\d{3})", text)]
    assert numbers, "M2 fixture catalog is empty"
    return max(numbers)


def _declared_fixture_max(text: str) -> int | None:
    matches = re.findall(r"M2-FLT-001`?〜`?(\d{3})", text)
    return max(map(int, matches)) if matches else None


def _markdown_table_rows(section: str) -> list[str]:
    return [
        line
        for line in section.splitlines()
        if line.startswith("| `") and "|---" not in line
    ]


def _observed_exceptions() -> set[str]:
    design = DESIGN_016.read_text(encoding="utf-8")
    catalog_max = _fixture_max(design.split("## §9 fault fixture catalog", 1)[1])
    observed: set[str] = set()

    for path in [FLOW_SPEC / "design" / "FLW-DSN-014.md", FLOW_SPEC / "ROADMAP.md"]:
        declared = _declared_fixture_max(path.read_text(encoding="utf-8"))
        if declared is not None and declared != catalog_max:
            observed.add(f"fixture-range:{path.name}:{declared}!={catalog_max}")

    quarantine = design.split("## §6 quarantine 解除と解放経路", 1)[1].split("## §7", 1)[0]
    declared_match = re.search(r"worktree 用(\d+)区分", quarantine)
    assert declared_match, "quarantine declared count is missing"
    declared_count = int(declared_match.group(1))
    table_count = len(_markdown_table_rows(quarantine))
    if declared_count != table_count:
        observed.add(f"quarantine-count:declared-{declared_count}!=table-{table_count}")

    referenced = set(re.findall(r"\bREC-(?:WT|RM)-[A-Z-]+\b", design))
    recovery_section = design.split("## §8 M2 recovery matrix", 1)[1].split("## §9", 1)[0]
    defined = set(re.findall(r"\bREC-(?:WT|RM)-[A-Z-]+\b", recovery_section))
    for recovery_id in sorted(referenced - defined):
        observed.add(f"recovery-id:undefined:{recovery_id}")

    return observed


def test_m2_known_inconsistencies_are_exact_and_shrink_only() -> None:
    config = json.loads(ALLOWLIST.read_text(encoding="utf-8"))
    assert config["schema_version"] == 1
    assert config["additions_allowed"] is False
    expected = config["exceptions"]
    assert expected == sorted(set(expected)), "exception list must be unique and sorted"
    observed = _observed_exceptions()
    assert observed == set(expected), (
        "M2 consistency exceptions changed. New exceptions are forbidden; "
        "fixed exceptions must be removed from the allowlist in the same change. "
        f"new={sorted(observed - set(expected))}, stale={sorted(set(expected) - observed)}"
    )


def test_m2_exception_ids_are_scoped_to_the_accepted_issue() -> None:
    config = json.loads(ALLOWLIST.read_text(encoding="utf-8"))
    assert config["issue"] == "SI-FLW-052"
    assert len(config["exceptions"]) == 8
