"""`build_result` の非ok契約（cause/recovery_class/next_actions）を検査する。

以前は `worktree.*` の write 失敗系（apply 中の例外、承認モード不整合等）が
`summary` と `stage` だけを持ち、`cause` も `recovery_class` も `next_actions` も
空だった。recovery matrix（`references/recovery-matrix.md`）は文書にあっても
公開 result へ載っていなかった（`FLW-REV-019`）。`build_result` に検査を置き、
operation 個別のテストで担保する方式（新しい失敗経路を足すたびに同じ穴が再発する）
をやめる（`FLW-TSK-100`）。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parents[1] / "plugins" / "bitz-flow" / "skills" / "flow-core"
sys.path.insert(0, str(SKILL / "scripts"))

from flowlib import result as R  # noqa: E402


def _kwargs(**overrides):
    values = dict(
        operation="worktree.create",
        code="BLOCKED",
        repo="/tmp/repo",
        tool_version="0.0.0",
        started_at="2026-01-01T00:00:00Z",
        finished_at="2026-01-01T00:00:01Z",
        summary="blocked",
    )
    values.update(overrides)
    return values


# --- 陰性対照 — 3field を欠いた non-ok result は組み立て時に拒否される -------------


def test_non_ok_result_without_cause_is_rejected():
    with pytest.raises(ValueError, match="cause"):
        R.build_result(**_kwargs(
            data={"recovery_class": "human-stop", "required_human_input": "x"},
        ))


def test_non_ok_result_without_recovery_class_is_rejected():
    with pytest.raises(ValueError, match="recovery_class"):
        R.build_result(**_kwargs(data={"cause": "conflict"}))


def test_non_ok_result_with_an_unknown_recovery_class_is_rejected():
    with pytest.raises(ValueError, match="recovery_class"):
        R.build_result(**_kwargs(data={"cause": "conflict", "recovery_class": "bogus-class"}))


def test_human_stop_with_non_empty_next_actions_is_rejected():
    """`human-stop` は空 NEXT である（解除は operation ではなく人間の裁定）。"""
    with pytest.raises(ValueError, match="human-stop"):
        R.build_result(**_kwargs(
            data={"cause": "conflict", "recovery_class": "human-stop", "required_human_input": "x"},
            next_actions=[R.next_action("worktree", "audit")],
        ))


def test_human_stop_without_required_human_input_is_rejected():
    with pytest.raises(ValueError, match="required_human_input"):
        R.build_result(**_kwargs(data={"cause": "conflict", "recovery_class": "human-stop"}))


def test_non_human_stop_recovery_class_without_next_actions_is_rejected():
    """空であること自体が matrix（human-stop）から導かれた結論でなければならない。"""
    with pytest.raises(ValueError, match="next_actions"):
        R.build_result(**_kwargs(
            code="STALE",
            data={"cause": "snapshot-mismatch", "recovery_class": "replan-human"},
        ))


@pytest.mark.parametrize(
    "code", sorted(set(R.CODE_EXIT_CODES) - {"OK", "READY", "DONE", "APPROVAL_REQUIRED"})
)
def test_every_non_exempt_non_ok_code_requires_cause(code):
    """table駆動 — OK系・APPROVAL_REQUIRED以外の全codeで cause 欠落が FAIL すること。"""
    with pytest.raises(ValueError, match="cause"):
        R.build_result(**_kwargs(code=code, data={}))


# --- 陽性対照 — 3field を満たした non-ok result は組み立てられる -----------------


def test_valid_non_ok_result_with_human_stop_succeeds():
    result = R.build_result(**_kwargs(
        data={"cause": "conflict", "recovery_class": "human-stop", "required_human_input": "x"},
    ))
    assert result["code"] == "BLOCKED"
    assert result["data"]["cause"] == "conflict"
    assert result["data"]["recovery_class"] == "human-stop"
    assert result["next_actions"] == []


def test_valid_non_ok_result_with_populated_next_actions_succeeds():
    result = R.build_result(**_kwargs(
        code="STALE",
        data={"cause": "snapshot-mismatch", "recovery_class": "replan-human"},
        next_actions=[R.next_action("worktree", "create")],
    ))
    assert result["code"] == "STALE"
    assert result["next_actions"] == [{"domain": "worktree", "action": "create", "args": {}}]


def test_approval_required_is_exempt_from_the_cause_requirement():
    """`APPROVAL_REQUIRED` は診断された失敗ではなく通常の write フロー中断点。

    recovery-matrix.md の決定表もこの code の行を持たない。cause は免除するが
    recovery_class / next_actions（human-stop なら required_human_input）は免除しない。
    """
    result = R.build_result(**_kwargs(
        code="APPROVAL_REQUIRED",
        data={"recovery_class": "human-stop", "required_human_input": "confirm required"},
    ))
    assert result["data"]["cause"] is None
    assert result["code"] == "APPROVAL_REQUIRED"


def test_approval_required_still_requires_recovery_class():
    with pytest.raises(ValueError, match="recovery_class"):
        R.build_result(**_kwargs(code="APPROVAL_REQUIRED", data={}))


def test_ok_result_is_exempt_from_the_entire_gate():
    """陰性対照 — ok result（`OK`/`READY`/`DONE`）は検査の対象外であること。"""
    result = R.build_result(**_kwargs(code="OK", data={}))
    assert result["ok"] is True
    assert result["data"]["cause"] is None
    assert "recovery_class" not in result["data"]
