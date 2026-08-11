"""durable intent と quarantine ライフサイクル（FLW-NFR-007 / FLW-FR-013）の単体テスト。

負の対照: intent 永続化前の mutation 開始、既存 record の上書き、unresolved での解除、
旧 operation ID の再利用、期限切れ capability、nonce 再利用、PARTIAL / STALE からの自動再 apply。
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / "plugins" / "bitz-flow" / "skills" / "flow-core"
sys.path.insert(0, str(SKILL / "scripts"))

from flowlib import durable as D  # noqa: E402
from flowlib import intent as IN  # noqa: E402
from flowlib import result as R  # noqa: E402

T0 = datetime(2026, 8, 12, tzinfo=timezone.utc)
DIGEST = R.sha256_of(b"snapshot")
TRUSTED = ("key-1",)


class _Replica:
    def __init__(self, ack=True):
        self.ack = ack

    def append_wal(self, entry_bytes, digest):
        return self.ack


@pytest.fixture
def log(tmp_path):
    return D.DurableLog(tmp_path / "intent", replica=_Replica())


@pytest.fixture
def store(log):
    return IN.IntentStore(
        log,
        repo_identity={"local_common_dir": R.sha256_of(b"r"), "remote_repository": None},
        owner_process="proc-1",
    )


def _open(store, operation_id="op-1"):
    return store.open(
        operation_id=operation_id,
        targets=[{"kind": "index", "canonical_key": "index:abc:wt-1"}],
        snapshot_digest=DIGEST,
        expected_effect_digest=R.sha256_of(b"effects"),
    )


def _to(store, intent, *states, **kw):
    for state in states:
        failure = store.transition(intent, state, **kw)
        assert failure is None, f"{state}: {failure}"
    return intent


# --- 状態機械 ------------------------------------------------------------------


def test_states_are_the_closed_enum():
    assert IN.WRITE_STATES == (
        "PLANNED", "GUARDED", "PENDING_INTENT", "MUTATING", "RECONCILING",
        "DONE", "PARTIAL", "STALE", "QUARANTINED",
    )


def test_happy_path_reaches_done(store):
    intent = _open(store)
    _to(store, intent, IN.GUARDED, IN.PENDING_INTENT, IN.MUTATING, IN.RECONCILING)
    assert store.transition(intent, IN.DONE, receipt_digest=R.sha256_of(b"receipt")) is None
    assert intent.state == IN.DONE


@pytest.mark.parametrize(
    "path", [
        (IN.PENDING_INTENT,),          # GUARDED を飛ばす
        (IN.GUARDED, IN.MUTATING),     # PENDING_INTENT を飛ばす
        (IN.GUARDED, IN.PENDING_INTENT, IN.MUTATING, IN.DONE),  # RECONCILING を飛ばす
    ],
)
def test_illegal_transitions_are_rejected(store, path):
    intent = _open(store)
    failure = None
    for state in path:
        failure = store.transition(intent, state)
        if failure is not None:
            break
    assert failure is not None and failure.code == IN.CODE_INVALID_INPUT


def test_unknown_state_is_rejected(store):
    intent = _open(store)
    failure = store.transition(intent, "SOMEWHERE")
    assert failure.code == IN.CODE_INVALID_INPUT


def test_terminal_states_have_no_successor(store):
    intent = _open(store)
    _to(store, intent, IN.GUARDED, IN.PENDING_INTENT, IN.MUTATING, IN.RECONCILING, IN.PARTIAL)
    assert store.transition(intent, IN.MUTATING) is not None


# --- 永続化前の副作用を許さない -------------------------------------------------


def test_mutating_requires_durable_commit(tmp_path):
    """intent が永続化できなければ MUTATING へ進めない。"""
    log = D.DurableLog(tmp_path / "i", replica=_Replica(ack=False))
    store = IN.IntentStore(log, repo_identity={}, owner_process="p")
    intent = _open(store)
    assert store.transition(intent, IN.GUARDED) is None

    failure = store.transition(intent, IN.PENDING_INTENT)
    assert failure.code == IN.CODE_BLOCKED
    assert intent.commit is None
    assert intent.state == IN.GUARDED, "永続化に失敗した状態で PENDING_INTENT へ進めない"


def test_mutating_blocked_when_commit_missing(store, monkeypatch):
    intent = _open(store)
    _to(store, intent, IN.GUARDED, IN.PENDING_INTENT)
    intent.commit = None  # commit point の記録を失った状況
    failure = store.transition(intent, IN.MUTATING)
    assert failure.code == IN.CODE_BLOCKED
    assert "commit point" in failure.reason


def test_pending_intent_is_persisted_as_record(store, log):
    intent = _open(store)
    _to(store, intent, IN.GUARDED, IN.PENDING_INTENT)
    report, _ = log.scan()
    assert report.healthy
    assert report.entries[0]["intent_record_state"] == IN.RECORD_PENDING
    assert report.entries[0]["operation_id"] == "op-1"


def test_records_are_appended_not_overwritten(store, log):
    intent = _open(store)
    _to(store, intent, IN.GUARDED, IN.PENDING_INTENT, IN.MUTATING, IN.RECONCILING, IN.STALE)
    report, _ = log.scan()
    assert len(report.entries) >= 2
    assert report.entries[0]["intent_record_state"] == IN.RECORD_PENDING
    assert report.entries[-1]["intent_record_state"] == IN.RECORD_STALE


# --- 不変条件 ------------------------------------------------------------------


@pytest.mark.parametrize(
    "state,requires", [
        (IN.PLANNED, False), (IN.GUARDED, False),
        (IN.PENDING_INTENT, True), (IN.MUTATING, True), (IN.RECONCILING, True),
        (IN.PARTIAL, True), (IN.STALE, True), (IN.QUARANTINED, True),
    ],
)
def test_durable_intent_requirement_per_state(state, requires):
    intent = IN.WriteIntent("op", (), DIGEST, DIGEST, state=state)
    assert intent.requires_intent is requires


@pytest.mark.parametrize(
    "state,blocks", [
        (IN.PENDING_INTENT, True), (IN.MUTATING, True), (IN.RECONCILING, True),
        (IN.QUARANTINED, True), (IN.DONE, False), (IN.PLANNED, False),
    ],
)
def test_next_write_blocking_per_state(state, blocks):
    intent = IN.WriteIntent("op", (), DIGEST, DIGEST, state=state)
    assert intent.blocks_next_write is blocks


@pytest.mark.parametrize("state", [IN.PARTIAL, IN.STALE, IN.QUARANTINED])
def test_no_auto_reapply_from_unresolved_states(state):
    intent = IN.WriteIntent("op", (), DIGEST, DIGEST, state=state)
    assert intent.allows_auto_reapply is False


# --- 解除 ----------------------------------------------------------------------


def test_release_requires_done_and_receipt(store):
    intent = _open(store)
    _to(store, intent, IN.GUARDED, IN.PENDING_INTENT, IN.MUTATING, IN.RECONCILING)
    store.transition(intent, IN.DONE, receipt_digest=R.sha256_of(b"r"))
    assert store.release(intent) is None


def test_release_without_receipt_is_indeterminate(store):
    intent = _open(store)
    _to(store, intent, IN.GUARDED, IN.PENDING_INTENT, IN.MUTATING, IN.RECONCILING, IN.DONE)
    failure = store.release(intent)
    assert failure.code == IN.CODE_INDETERMINATE
    assert "DONE と推定しない" in failure.reason


@pytest.mark.parametrize("state", [IN.PARTIAL, IN.STALE, IN.QUARANTINED])
def test_unresolved_states_keep_their_intent(store, state):
    intent = _open(store)
    _to(store, intent, IN.GUARDED, IN.PENDING_INTENT, IN.MUTATING, IN.RECONCILING, state)
    failure = store.release(intent)
    assert failure.code == IN.CODE_BLOCKED
    assert "証跡として保持" in failure.reason


# --- quarantine 解除 -----------------------------------------------------------


def _quarantined(store):
    intent = _open(store)
    _to(store, intent, IN.GUARDED, IN.PENDING_INTENT, IN.MUTATING, IN.RECONCILING, IN.QUARANTINED)
    return intent


def test_unresolved_conclusion_cannot_release(store):
    intent = _quarantined(store)
    receipt, failure = store.quarantine_release(
        intent, conclusion="unresolved", evidence=[], approvers=["evaluation-reviewer"],
        reviewer="rev", old_token=1, new_token=2, at="2026-08-12T00:00:00Z",
    )
    assert receipt is None
    assert "unresolved は解除できない" in failure.reason


@pytest.mark.parametrize("conclusion", ["confirmed-done", "no-effect"])
def test_reviewer_only_conclusions_release(store, conclusion):
    intent = _quarantined(store)
    receipt, failure = store.quarantine_release(
        intent, conclusion=conclusion,
        evidence=IN.CONCLUSION_EVIDENCE[conclusion],
        approvers=["evaluation-reviewer"],
        reviewer="rev", old_token=1, new_token=2, at="2026-08-12T00:00:00Z",
    )
    assert failure is None
    assert receipt["release_conclusion"] == conclusion
    assert receipt["old_fencing_token"] == 1 and receipt["new_fencing_token"] == 2


def test_orphan_object_needs_repository_owner(store):
    intent = _quarantined(store)
    conclusion = "orphan-object-no-reachable-effect"
    receipt, failure = store.quarantine_release(
        intent, conclusion=conclusion, evidence=IN.CONCLUSION_EVIDENCE[conclusion],
        approvers=["evaluation-reviewer"], reviewer="rev",
        old_token=1, new_token=2, at="2026-08-12T00:00:00Z",
    )
    assert receipt is None
    assert "repository-owner" in failure.reason


def test_missing_evidence_blocks_release(store):
    intent = _quarantined(store)
    receipt, failure = store.quarantine_release(
        intent, conclusion="confirmed-done", evidence=["intent"],
        approvers=["evaluation-reviewer"], reviewer="rev",
        old_token=1, new_token=2, at="2026-08-12T00:00:00Z",
    )
    assert receipt is None
    assert "必須証跡が不足" in failure.reason


def test_release_receipt_is_appended_to_chain(store, log):
    intent = _quarantined(store)
    store.quarantine_release(
        intent, conclusion="no-effect", evidence=IN.CONCLUSION_EVIDENCE["no-effect"],
        approvers=["evaluation-reviewer"], reviewer="rev",
        old_token=1, new_token=2, at="2026-08-12T00:00:00Z",
    )
    report, _ = log.scan()
    assert report.healthy
    assert report.entries[-1]["intent_record_state"] == IN.RECORD_RELEASED


def test_non_quarantined_intent_cannot_be_released_that_way(store):
    intent = _open(store)
    receipt, failure = store.quarantine_release(
        intent, conclusion="no-effect", evidence=IN.CONCLUSION_EVIDENCE["no-effect"],
        approvers=["evaluation-reviewer"], reviewer="rev",
        old_token=1, new_token=2, at="2026-08-12T00:00:00Z",
    )
    assert receipt is None and failure.code == IN.CODE_INVALID_INPUT


# --- 解除後の mutation（capability）-------------------------------------------


def _capability(**overrides):
    base = dict(
        target="index:abc:wt-1",
        snapshot_digest=DIGEST,
        prior_operation_id="op-1",
        reviewer="rev",
        expires_at=T0 + timedelta(hours=1),
        nonce="n-1",
        key_id="key-1",
    )
    base.update(overrides)
    return IN.Capability(**base)


def _authorize(capability, **overrides):
    params = dict(
        target="index:abc:wt-1",
        snapshot_digest=DIGEST,
        new_operation_id="op-2",
        prior_operation_id="op-1",
        now=T0,
        trusted_key_ids=TRUSTED,
        nonce_state="UNUSED",
    )
    params.update(overrides)
    return IN.authorize_mutation(capability, **params)


def test_valid_capability_authorizes():
    assert _authorize(_capability()) is None


def test_reusing_prior_operation_id_is_rejected():
    failure = _authorize(_capability(), new_operation_id="op-1")
    assert failure.code == IN.CODE_BLOCKED
    assert "新しい operation ID" in failure.reason


def test_target_mismatch_is_rejected():
    failure = _authorize(_capability(target="index:other:wt-1"))
    assert "target が一致しない" in failure.reason


def test_snapshot_drift_is_rejected():
    failure = _authorize(_capability(), snapshot_digest=R.sha256_of(b"other"))
    assert "snapshot" in failure.reason


def test_expired_capability_is_rejected():
    failure = _authorize(_capability(), now=T0 + timedelta(hours=2))
    assert "有効期限" in failure.reason


def test_boundary_expiry_is_rejected():
    """境界時刻ちょうどは期限切れ扱い（安全側）。"""
    capability = _capability(expires_at=T0)
    assert _authorize(capability, now=T0) is not None


@pytest.mark.parametrize("state", ["USED_PENDING", "USED_DONE", "QUARANTINED"])
def test_nonce_reuse_is_rejected(state):
    failure = _authorize(_capability(), nonce_state=state)
    assert "nonce は再利用できない" in failure.reason


def test_revoked_key_is_rejected():
    failure = _authorize(_capability(key_id="key-old"))
    assert "署名鍵" in failure.reason


def test_unexpected_algorithm_is_rejected():
    failure = _authorize(_capability(algorithm="HMAC"))
    assert "署名方式" in failure.reason


def test_circular_prior_reference_is_rejected():
    failure = _authorize(_capability(prior_operation_id="op-x"), prior_operation_id="op-1")
    assert "旧 operation" in failure.reason
