"""FLW-TSK-029: recovery class 決定器と、決定表 markdown との機械照合。

`references/recovery-matrix.md`（人間向け）と `flowlib/recovery.py` の MATRIX（機械可読）が
同じ決定表を表すことをここで固定する。片方だけを変更したら落ちる。
"""

import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / "plugins" / "bitz-flow" / "skills" / "flow-core"
sys.path.insert(0, str(SKILL / "scripts"))

from flowlib import recovery as RC  # noqa: E402

MATRIX_MD = SKILL / "references" / "recovery-matrix.md"
CATALOG_MD = SKILL / "references" / "operation-catalog.md"


def _decision_rows() -> list[tuple[str, str, str]]:
    lines = MATRIX_MD.read_text(encoding="utf-8").splitlines()
    start = next(i for i, l in enumerate(lines) if l.startswith("| operation | phase / stage"))
    rows = []
    for line in lines[start + 2:]:
        if not line.startswith("|"):
            break
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        rows.append(tuple(cells[:3]))
    return rows


# --- markdown との照合 --------------------------------------------------------


def test_matrix_matches_markdown_rows_in_order():
    assert [r.md_row for r in RC.MATRIX] == _decision_rows()


def test_matrix_keys_are_unique():
    keys = [(r.operations, r.phase, r.code) for r in RC.MATRIX]
    assert len(keys) == len(set(keys))


def test_recovery_classes_are_documented():
    text = MATRIX_MD.read_text(encoding="utf-8")
    for cls in RC.RECOVERY_CLASSES:
        assert f"`{cls}`" in text


def test_every_rule_uses_a_known_class():
    assert {r.recovery_class for r in RC.MATRIX} <= set(RC.RECOVERY_CLASSES)


def test_operations_match_catalog():
    """決定器が知る operation 集合が operation catalog と一致する。"""
    text = CATALOG_MD.read_text(encoding="utf-8")
    documented = set(re.findall(r"`((?:repo|git|worktree|issue|pr|release)\.[a-z-]+)`", text))
    known = set(RC.READ_OPERATIONS) | set(RC.WRITE_OPERATIONS)
    assert known == documented, f"catalog との差分: {known ^ documented}"


def test_unreachable_tuple_is_documented():
    text = MATRIX_MD.read_text(encoding="utf-8")
    assert "到達不能" in text
    assert ("git.commit", "PARTIAL") in RC.UNREACHABLE


def test_fail_closed_default_is_documented():
    text = MATRIX_MD.read_text(encoding="utf-8")
    assert "fail-closed" in text and "`human-stop`" in text


# --- decide -------------------------------------------------------------------


@pytest.mark.parametrize("rule", RC.MATRIX, ids=lambda r: f"{r.md_row[0]}|{r.phase}|{r.code}")
def test_every_matrix_row_decides_as_declared(rule):
    operation = rule.operations[0]
    if operation == RC.ANY_READ:
        operation = RC.READ_OPERATIONS[0]
    elif operation == RC.ANY_WRITE:
        operation = RC.WRITE_OPERATIONS[0]

    decision = RC.decide(operation=operation, phase=rule.phase, code=rule.code)
    assert decision.recovery_class == rule.recovery_class


def test_unregistered_tuple_fails_closed():
    decision = RC.decide(operation="git.commit", phase="no-such-phase", code="STALE")
    assert decision.recovery_class == RC.HUMAN_STOP
    assert decision.allowed_next == ()
    assert decision.stop_reason
    assert decision.required_human_input


def test_unknown_operation_fails_closed():
    decision = RC.decide(operation="git.rebase", phase="pre-apply", code="STALE")
    assert decision.stops and decision.allowed_next == ()


def test_unreachable_tuple_is_rejected_not_defaulted():
    decision = RC.decide(operation="git.commit", phase="post-apply", code="PARTIAL")
    assert decision.stops
    assert decision.quarantine_target is True
    assert "到達不能" in decision.stop_reason


def test_human_stop_returns_empty_next_actions():
    decision = RC.decide(
        operation="git.commit", phase="reconcile-impossible", code="INDETERMINATE"
    )
    assert decision.allowed_next == ()
    assert "mutation 全般" in decision.forbidden
    assert decision.quarantine_target is True


def test_unclassified_outcome_allows_bounded_recheck():
    decision = RC.decide(
        operation="git.stage", phase="post-apply", code=RC.UNCLASSIFIED_OUTCOME
    )
    assert decision.recovery_class == RC.RECONCILE_ONLY
    assert decision.max_postcondition_rechecks == RC.MAX_POSTCONDITION_RECHECKS == 2
    assert "command blind retry" in decision.forbidden


def test_specific_row_wins_over_generic_row():
    """同じ code でも、より具体的な phase の行で解決する。"""
    generic = RC.decide(operation="git.sync", phase="post-apply", code="PARTIAL")
    specific = RC.decide(operation="git.sync", phase="fetched-branch-not-updated", code="PARTIAL")
    assert generic.recovery_class == specific.recovery_class == RC.RECONCILE_ONLY
    assert "branch-update" in specific.allowed_next[0]


def test_read_and_write_rules_do_not_cross():
    """`全 read` の行が write に適用されない。"""
    decision = RC.decide(operation="git.commit", phase="pre-inspect", code="INVALID_INPUT")
    assert decision.stops, "read 用の既定行を write へ流用してはならない"


# --- next_actions のグラフ検査 -------------------------------------------------


def test_direct_mutation_is_rejected():
    reason = RC.validate_next_actions(code="PARTIAL", next_actions=["git.commit"])
    assert reason and "git.commit" in reason


def test_transitive_mutation_is_rejected():
    """1 段では read でも、辿ると mutation に届くグラフは不正。"""
    graph = {"git.status": ["git.diff-summary"], "git.diff-summary": ["git.stage"]}
    reason = RC.validate_next_actions(code="STALE", next_actions=["git.status"], graph=graph)
    assert reason and "git.stage" in reason


def test_read_only_graph_is_accepted():
    graph = {"git.status": ["git.diff-summary"], "git.diff-summary": []}
    assert RC.validate_next_actions(code="STALE", next_actions=["git.status"], graph=graph) is None


def test_cycle_in_graph_terminates():
    graph = {"git.status": ["repo.inspect"], "repo.inspect": ["git.status"]}
    assert RC.validate_next_actions(code="PARTIAL", next_actions=["git.status"], graph=graph) is None


def test_ok_code_is_not_restricted():
    assert RC.validate_next_actions(code="DONE", next_actions=["git.commit"]) is None


# --- write_state の射影 --------------------------------------------------------


@pytest.mark.parametrize(
    "write_state,expected_phase",
    [
        ("pending-intent", "pre-object-save"),
        ("mutating", "post-apply"),
        ("reconciling", "post-apply"),
    ],
)
def test_write_state_projects_to_matrix_phase(write_state, expected_phase):
    assert RC.project_write_state(write_state) == expected_phase


def test_unknown_write_state_projects_to_stop():
    assert RC.project_write_state("???") == "reconcile-impossible"
    decision = RC.decide(
        operation="git.commit", phase=RC.project_write_state("???"), code="INDETERMINATE"
    )
    assert decision.stops
