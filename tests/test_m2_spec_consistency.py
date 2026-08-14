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
    assert len(config["exceptions"]) == 5


def test_quarantine_uses_evidence_axis_and_covers_discard_interruptions() -> None:
    design = DESIGN_016.read_text(encoding="utf-8")
    quarantine = design.split("## §6 quarantine 解除と解放経路", 1)[1].split("## §7", 1)[0]
    for state in (
        "worktree-not-started", "worktree-resumable",
        "worktree-confirmed-done", "worktree-unresolved",
    ):
        assert f"`{state}`" in quarantine
    for evidence in ("intent", "instance nonce", "receipt"):
        assert evidence in quarantine
    assert "存在パターンだけ" in quarantine

    recovery = design.split("### step 契約", 1)[1].split("## §9", 1)[0]
    assert "(verify)" in recovery
    assert "(mutate)" in recovery
    assert "sync-main" not in recovery
    assert "result field" in recovery
    assert "mutating stepから宣言済みmutation target" in recovery


def test_instance_nonce_survives_registry_removal() -> None:
    design = DESIGN_016.read_text(encoding="utf-8")
    identity = design.split("### instance identity", 1)[1].split("### `worktree-dir`", 1)[0]
    assert "common-dir 配下の owner-only 証跡領域" in identity
    assert "registry entry 配下の owner-only file" not in identity


def test_guard_identity_uses_object_identity_and_ancestor_fallback() -> None:
    design = DESIGN_016.read_text(encoding="utf-8")
    guard = design.split("## §3 guard identity の拡張", 1)[1].split("## §4", 1)[0]
    assert "`st_dev + st_ino`だけ" in guard
    assert "canonical pathをkeyへ混ぜない" in guard
    assert "最も近い実在祖先" in guard
    assert "正規化相対path" in guard
    assert "instance nonceは世代検査用precondition" in guard


def test_worktree_content_cas_delegates_to_git_porcelain_v2() -> None:
    design = DESIGN_016.read_text(encoding="utf-8")
    cas = design.split("### `worktree-dir` の CAS 相当", 1)[1].split("## §6", 1)[0]
    assert "git status --porcelain=v2 --untracked-files=all -z" in cas
    assert "stdout bytesのdigest" in cas
    assert "racily-clean" in cas
    assert "untrackedもCAS対象" in cas
    assert "非ゼロ終了は`BLOCKED`" in cas


def test_worktree_state_is_physical_and_finish_predicate_is_explicit() -> None:
    design = DESIGN_016.read_text(encoding="utf-8")
    enum = design.split("### 閉集合", 1)[1].split("### 表記規則", 1)[0]
    assert "`ABSENT, CLEAN, DIRTY, MISMATCH`" in enum
    for moved in ("PR_OPEN", "MERGED_EXACT, REMOTE_ADVANCED", "FAILED_RETAINED`"):
        assert moved not in enum.split("| **worktree**", 1)[1].splitlines()[0]
    table = design.split("### worktree operation 許可決定表", 1)[1].split("### 表記規則", 1)[0]
    assert "| `worktree.finish` | `AUDITED` | `DIRTY` | `MERGED_EXACT` | なし | `BLOCKED` |" in table
    assert "退避receipt" in table
    assert "M2-FLT-050" in design
