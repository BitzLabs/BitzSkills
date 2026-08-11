"""evidence ledger の合成と candidate 選択（FLW-NFR-011）。

中心命題: **結果の選り好みをさせない**。objective ごとの最初の適格 attempt を candidate に固定し、
後から来た良い結果で置換しない。
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "evals" / "flow-core" / "m1-eval"))

import ledger as L  # noqa: E402

RETRYABLE = ("instrument-unavailable", "environment-unavailable")


def _attempt(attempt_id, status=L.STATUS_PASS, **overrides):
    base = dict(
        attempt_id=attempt_id,
        objective_id="obj-1",
        epoch_id="e1",
        compatibility_key="sha256:k1",
        platform="claude",
        status=status,
        retryable_failure_codes=RETRYABLE,
    )
    base.update(overrides)
    return L.Attempt(**base)


@pytest.fixture
def ledger():
    return L.Ledger()


# --- 登録 ----------------------------------------------------------------------


def test_register_appends(ledger):
    assert ledger.register(_attempt(1)) is None
    assert len(ledger.entries) == 1


def test_duplicate_attempt_id_is_blocked(ledger):
    ledger.register(_attempt(1))
    failure = ledger.register(_attempt(1, status=L.STATUS_FAIL))
    assert failure.code == L.GATE_BLOCKED
    assert "重複" in failure.reason


def test_unknown_status_is_rejected(ledger):
    failure = ledger.register(_attempt(1, status="MAYBE"))
    assert failure is not None


# --- candidate は最初の適格 attempt --------------------------------------------


def test_first_eligible_attempt_becomes_candidate(ledger):
    ledger.register(_attempt(1, status=L.STATUS_FAIL))
    ledger.register(_attempt(2, status=L.STATUS_PASS, epoch_id="e2", compatibility_key="sha256:k2"))
    assert ledger.candidate_for("obj-1").attempt_id == 1


def test_started_attempt_is_not_a_candidate(ledger):
    ledger.register(_attempt(1, status=L.STATUS_STARTED))
    assert ledger.candidate_for("obj-1") is None


def test_unknown_attempt_is_not_a_candidate(ledger):
    ledger.register(_attempt(1, status=L.STATUS_STARTED))
    ledger.mark_unknown(1, reason="lease 満了")
    assert ledger.candidate_for("obj-1") is None


def test_candidates_are_per_objective(ledger):
    ledger.register(_attempt(1, objective_id="obj-1", status=L.STATUS_FAIL))
    ledger.register(_attempt(2, objective_id="obj-2", status=L.STATUS_PASS))
    assert ledger.candidate_for("obj-1").attempt_id == 1
    assert ledger.candidate_for("obj-2").attempt_id == 2


# --- FAIL を PASS へ置換しない --------------------------------------------------


def test_pass_cannot_replace_fail_in_same_epoch_and_key(ledger):
    ledger.register(_attempt(1, status=L.STATUS_FAIL))
    failure = ledger.register(_attempt(2, status=L.STATUS_PASS))
    assert failure.code == L.GATE_BLOCKED
    assert "新しい confirmation epoch" in failure.reason


def test_new_epoch_and_key_allows_reexecution(ledger):
    ledger.register(_attempt(1, status=L.STATUS_FAIL))
    failure = ledger.register(
        _attempt(2, status=L.STATUS_PASS, epoch_id="e2", compatibility_key="sha256:k2")
    )
    assert failure is None
    assert ledger.candidate_for("obj-1").attempt_id == 1, "candidate は最初の FAIL のまま"


def test_changing_only_the_key_does_not_reset_history(ledger):
    """key を変えただけで失敗履歴をリセットしない。"""
    ledger.register(_attempt(1, status=L.STATUS_FAIL))
    ledger.register(_attempt(2, status=L.STATUS_PASS, compatibility_key="sha256:k2"))
    assert ledger.candidate_for("obj-1").status == L.STATUS_FAIL


def test_changing_only_the_epoch_does_not_reset_history(ledger):
    ledger.register(_attempt(1, status=L.STATUS_FAIL))
    ledger.register(_attempt(2, status=L.STATUS_PASS, epoch_id="e2"))
    assert ledger.candidate_for("obj-1").status == L.STATUS_FAIL


# --- late-evidence --------------------------------------------------------------


def test_late_evidence_does_not_replace_candidate(ledger):
    ledger.register(_attempt(1, status=L.STATUS_STARTED))
    ledger.mark_unknown(1, reason="partition")
    ledger.register(_attempt(2, status=L.STATUS_PASS, late=True))

    assert ledger.candidate_for("obj-1") is None, "UNKNOWN のまま candidate を作らない"
    assert [a.attempt_id for a in ledger.late_evidence_for("obj-1")] == [2]


def test_late_evidence_is_still_recorded(ledger):
    ledger.register(_attempt(1, status=L.STATUS_PASS, late=True))
    assert len(ledger.entries) == 1
    assert ledger.candidate_for("obj-1") is None


# --- 再試行は1回だけ -------------------------------------------------------------


def test_instrument_failure_with_no_subject_event_may_retry(ledger):
    attempt = _attempt(1, status=L.STATUS_FAIL, failure_code="instrument-unavailable",
                       failure_axis=("instrument",), subject_events=0)
    ledger.register(attempt)
    assert ledger.may_retry(attempt).allowed is True


def test_subject_event_forbids_retry(ledger):
    """被測定物が動いた形跡があれば、それは測定結果である。"""
    attempt = _attempt(1, status=L.STATUS_FAIL, failure_code="instrument-unavailable",
                       subject_events=1)
    ledger.register(attempt)
    decision = ledger.may_retry(attempt)
    assert decision.allowed is False
    assert "測定結果" in decision.reason


def test_unknown_failure_forbids_retry(ledger):
    attempt = _attempt(1, status=L.STATUS_FAIL, failure_code=None)
    ledger.register(attempt)
    assert ledger.may_retry(attempt).allowed is False


def test_unbound_failure_code_forbids_retry(ledger):
    attempt = _attempt(1, status=L.STATUS_FAIL, failure_code="something-else")
    ledger.register(attempt)
    decision = ledger.may_retry(attempt)
    assert decision.allowed is False
    assert "事前拘束していない" in decision.reason


def test_competing_failure_axes_forbid_retry(ledger):
    attempt = _attempt(1, status=L.STATUS_FAIL, failure_code="instrument-unavailable",
                       failure_axis=("instrument", "subject"))
    ledger.register(attempt)
    assert ledger.may_retry(attempt).allowed is False


def test_retry_issues_exactly_one_successor(ledger):
    attempt = _attempt(1, status=L.STATUS_FAIL, failure_code="environment-unavailable",
                       failure_axis=("environment",))
    ledger.register(attempt)

    successor, failure = ledger.consume_retry(attempt, successor_id=2)
    assert failure is None
    assert successor.retry_of == 1 and successor.status == L.STATUS_STARTED

    again, failure = ledger.consume_retry(attempt, successor_id=3)
    assert again is None, "retry slot は単回"
    assert len(ledger.successors_of(1)) == 1


def test_successor_cannot_be_retried_again(ledger):
    attempt = _attempt(1, status=L.STATUS_FAIL, failure_code="environment-unavailable",
                       failure_axis=("environment",))
    ledger.register(attempt)
    successor, _ = ledger.consume_retry(attempt, successor_id=2)

    failed_successor = L.Attempt(
        **{**successor.__dict__, "status": L.STATUS_FAIL,
           "failure_code": "environment-unavailable", "failure_axis": ("environment",)}
    )
    assert ledger.may_retry(failed_successor).allowed is False


def test_original_attempt_is_kept_after_retry(ledger):
    attempt = _attempt(1, status=L.STATUS_FAIL, failure_code="instrument-unavailable",
                       failure_axis=("instrument",))
    ledger.register(attempt)
    ledger.consume_retry(attempt, successor_id=2)
    assert any(e.attempt_id == 1 for e in ledger.entries), "元 attempt を無効化しない"


def test_retried_attempt_is_not_the_candidate(ledger):
    attempt = _attempt(1, status=L.STATUS_FAIL, failure_code="instrument-unavailable",
                       failure_axis=("instrument",))
    ledger.register(attempt)
    ledger.consume_retry(attempt, successor_id=2)
    assert ledger.candidate_for("obj-1") is None, "non-candidate terminal として扱う"


# --- 訂正は追記 -----------------------------------------------------------------


def test_correction_is_appended_not_overwritten(ledger):
    ledger.register(_attempt(1, status=L.STATUS_FAIL, failure_code="instrument-unavailable"))
    ledger.append_correction(1, new_classification="environment-unavailable", rationale="再分析")

    original = next(e for e in ledger.entries if e.attempt_id == 1)
    assert original.failure_code == "instrument-unavailable", "旧 entry を書き換えない"
    assert ledger.corrections[-1]["classification"] == "environment-unavailable"


def test_mark_unknown_records_a_correction(ledger):
    ledger.register(_attempt(1, status=L.STATUS_STARTED))
    ledger.mark_unknown(1, reason="lease 満了")
    assert ledger.corrections[-1]["classification"] == L.STATUS_UNKNOWN


def test_terminal_attempt_cannot_become_unknown(ledger):
    ledger.register(_attempt(1, status=L.STATUS_PASS))
    failure = ledger.mark_unknown(1, reason="なんとなく")
    assert failure is not None


# --- 双方向照合 -----------------------------------------------------------------


def test_reconcile_passes_when_consistent(ledger):
    ledger.register(_attempt(1, platform="claude"))
    ledger.register(_attempt(2, platform="codex", objective_id="obj-2"))
    assert ledger.reconcile({"claude": [1], "codex": [2]}) is None


def test_unregistered_run_is_blocked(ledger):
    ledger.register(_attempt(1))
    failure = ledger.reconcile({"claude": [1, 99]})
    assert failure.code == L.GATE_BLOCKED
    assert "正本未取込" in failure.reason


def test_duplicate_in_partial_ledger_is_blocked(ledger):
    ledger.register(_attempt(1))
    failure = ledger.reconcile({"claude": [1, 1]})
    assert "重複" in failure.reason


def test_orphan_authoritative_entry_is_blocked(ledger):
    ledger.register(_attempt(1))
    ledger.register(_attempt(2, objective_id="obj-2"))
    failure = ledger.reconcile({"claude": [1]})
    assert "現れない attempt" in failure.reason


def test_gap_in_attempt_ids_is_blocked(ledger):
    ledger.register(_attempt(1))
    ledger.register(_attempt(3, objective_id="obj-3"))
    failure = ledger.reconcile({"claude": [1, 3]})
    assert "欠番" in failure.reason


def test_broken_chain_is_blocked(ledger):
    ledger.register(_attempt(1))
    failure = ledger.reconcile({"claude": [1]}, chain_intact=False)
    assert "hash-chain" in failure.reason
