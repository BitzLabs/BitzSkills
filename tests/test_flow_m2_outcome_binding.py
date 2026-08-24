"""SI-FLW-088 — QUARANTINED を正常完了へ誤分類しないことを検証する。

`FLW-REV-027:SYN-005`（P1）。`worktree_recovery.audit()` の分類条件は
`report.state in {"RESULT_DURABLE", "DONE", "QUARANTINED"}` であり、**QUARANTINED が
完了判定の集合に入っていた**。

`RESULT_DURABLE` event の `postcondition_digest` は *予定* ではなく *実観測* の値である
（`quarantined_failure` が観測値をそのまま記録する）。したがって quarantine 後に
repository が変化していなければ現在 snapshot と一致し、`confirmed-complete` へ分類された。
運用者は隔離された操作を正常完了と誤認する。

本テストは `DONE` / `incomplete` / `quarantine` の**陽性・陰性対照**を置く。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "plugins" / "bitz-flow" / "skills" / "flow-core"
sys.path.insert(0, str(SKILL / "scripts"))

from flowlib import worktree_recovery as RC  # noqa: E402
from flowlib import worktree_runtime as R  # noqa: E402
from flowlib import worktree_transaction as T  # noqa: E402

DIGEST = "sha256:" + "a" * 64
EFFECTS = "sha256:" + "b" * 64


def _snapshot(suffix: str) -> R.RepositorySnapshot:
    return R.RepositorySnapshot(
        suffix * 40, "sha256:" + suffix * 64, "sha256:" + suffix * 64,
        "sha256:" + suffix * 64,
    )


def _authority(tmp_path: Path) -> T.TargetTransaction:
    root = tmp_path / "authority"
    root.mkdir(mode=0o700)
    return T.TargetTransaction(root, target_collision_key="target-1")


def _run_to_terminal(tmp_path: Path, *, terminal_state: str,
                     before: R.RepositorySnapshot,
                     after: R.RepositorySnapshot) -> T.TargetTransaction:
    """1 operation を終局まで進める。`after` が記録される postcondition になる。"""
    tx = _authority(tmp_path)
    lease = tx.acquire(operation_id=DIGEST, nonce="mutation-nonce")
    tx.prepare_intent(lease, planned_effects_digest=EFFECTS,
                      precondition_digest=before.digest)
    tx.mark_mutating(lease)
    tx.publish_result(lease, terminal_state=terminal_state,
                      postcondition_digest=after.digest)
    tx.release(lease)
    return tx


# --- 陰性対照: QUARANTINED を完了扱いしない ----------------------------------


def test_quarantined_is_never_confirmed_complete_even_when_snapshot_matches(tmp_path):
    """**本 issue の中心**。記録値と現在 snapshot が一致しても完了にしない。

    quarantine 直後は repository が変化していないため、記録された（実観測の）
    postcondition と現在 snapshot は必ず一致する。旧実装はこれを完了根拠にしていた。
    """
    before, after = _snapshot("1"), _snapshot("2")
    tx = _run_to_terminal(tmp_path, terminal_state="QUARANTINED",
                          before=before, after=after)
    report = RC.audit(tx, operation_id=DIGEST, observed_snapshot=after)
    assert report.transaction_state == "QUARANTINED"
    assert report.classification == RC.QUARANTINE, (
        "隔離された操作を正常完了と誤認させてはならない"
    )


def test_quarantined_with_a_changed_snapshot_is_also_quarantine(tmp_path):
    """snapshot が変化していても分類は quarantine のままであること。"""
    before, after = _snapshot("1"), _snapshot("2")
    tx = _run_to_terminal(tmp_path, terminal_state="QUARANTINED",
                          before=before, after=after)
    report = RC.audit(tx, operation_id=DIGEST, observed_snapshot=_snapshot("3"))
    assert report.classification == RC.QUARANTINE


# --- 陽性対照: DONE は完了になる ---------------------------------------------


def test_done_with_matching_postcondition_is_confirmed_complete(tmp_path):
    """正常完了を quarantine へ倒しすぎないこと（過剰な安全側倒しの検出）。"""
    before, after = _snapshot("1"), _snapshot("2")
    tx = _run_to_terminal(tmp_path, terminal_state="DONE",
                          before=before, after=after)
    report = RC.audit(tx, operation_id=DIGEST, observed_snapshot=after)
    assert report.transaction_state == "DONE"
    assert report.classification == RC.CONFIRMED_COMPLETE


def test_done_with_a_diverged_snapshot_is_not_confirmed_complete(tmp_path):
    """`DONE` でも予定 postcondition が成立していなければ完了にしないこと。"""
    before, after = _snapshot("1"), _snapshot("2")
    tx = _run_to_terminal(tmp_path, terminal_state="DONE",
                          before=before, after=after)
    report = RC.audit(tx, operation_id=DIGEST, observed_snapshot=_snapshot("9"))
    assert report.classification != RC.CONFIRMED_COMPLETE


# --- 陽性対照: 未着手は incomplete -------------------------------------------


def test_locked_only_is_confirmed_incomplete(tmp_path):
    """lock だけ取って停止した operation は incomplete であること。"""
    tx = _authority(tmp_path)
    lease = tx.acquire(operation_id=DIGEST, nonce="mutation-nonce")
    tx.release(lease)
    report = RC.audit(tx, operation_id=DIGEST, observed_snapshot=_snapshot("1"))
    assert report.classification == RC.CONFIRMED_INCOMPLETE


def test_intent_durable_with_unchanged_precondition_is_confirmed_incomplete(tmp_path):
    """intent 確定・mutation 未実施は incomplete であること（Git 副作用 0 件）。"""
    before = _snapshot("1")
    tx = _authority(tmp_path)
    lease = tx.acquire(operation_id=DIGEST, nonce="mutation-nonce")
    tx.prepare_intent(lease, planned_effects_digest=EFFECTS,
                      precondition_digest=before.digest)
    tx.release(lease)
    report = RC.audit(tx, operation_id=DIGEST, observed_snapshot=before)
    assert report.classification == RC.CONFIRMED_INCOMPLETE


# --- requested outcome の束縛 ------------------------------------------------


@pytest.mark.parametrize("terminal_state", ["DONE", "QUARANTINED"])
def test_result_event_binds_requested_outcome_and_planned_effects(tmp_path, terminal_state):
    """実観測値だけで完了を主張できないよう、要求された結末を束縛すること。"""
    before, after = _snapshot("1"), _snapshot("2")
    tx = _run_to_terminal(tmp_path, terminal_state=terminal_state,
                          before=before, after=after)
    report = tx.inspect(DIGEST)
    result = next(
        item["result"] for item in report.events
        if item["event"]["state"] == "RESULT_DURABLE"
    )
    assert result["terminal_state"] == terminal_state
    assert result["planned_effects_digest"] == EFFECTS
    assert result["postcondition_digest"] == after.digest


def test_result_durable_requesting_quarantine_is_not_completed(tmp_path):
    """終局 event 未着でも、要求された結末が quarantine なら完了へ倒さないこと。"""
    before, after = _snapshot("1"), _snapshot("2")
    tx = _run_to_terminal(tmp_path, terminal_state="QUARANTINED",
                          before=before, after=after)
    # 終局 event（QUARANTINED）だけを取り除き、RESULT_DURABLE 止まりを再現する。
    events = sorted(tx._event_dir(DIGEST).glob("*.json"))
    events[-1].unlink()
    report = RC.audit(tx, operation_id=DIGEST, observed_snapshot=after)
    assert report.transaction_state == "RESULT_DURABLE"
    assert report.classification != RC.CONFIRMED_COMPLETE
    assert report.classification == RC.QUARANTINE
