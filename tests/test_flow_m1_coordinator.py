"""coordinator core（FLW-NFR-011）の単体テストと負の対照。

負の対照（拒否されなければならないもの）:
  - stale leader による採番
  - lease 満了だけを根拠とする guard token の再発行
  - runner の local clock 由来の時刻
  - 境界時刻ちょうどでの TTL 通過
  - USED_PENDING のまま残った nonce の再利用
"""

import inspect
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / "plugins" / "bitz-flow" / "skills" / "flow-core"
sys.path.insert(0, str(SKILL / "scripts"))

from flowlib import coordinator as C  # noqa: E402


class MemoryStore:
    """linearizable CAS を模した最小の store。"""

    def __init__(self):
        self._d: dict[str, tuple[object, int]] = {}

    def read(self, key):
        entry = self._d.get(key)
        return (None, 0) if entry is None else entry

    def compare_and_set(self, key, expected_version, value):
        _, version = self.read(key)
        if version != expected_version:
            return False
        self._d[key] = (value, version + 1)
        return True


class UnreachableStore:
    """partition 中の store。"""

    def read(self, key):
        raise ConnectionError("store unreachable")

    def compare_and_set(self, key, expected_version, value):
        raise ConnectionError("store unreachable")


class LostAckStore(MemoryStore):
    """CAS の ack を返さない store（書けたか確認できない）。"""

    def compare_and_set(self, key, expected_version, value):
        raise TimeoutError("ack lost")


class FixedClock:
    def __init__(self, start: datetime):
        self._now = start

    def now(self) -> datetime:
        return self._now

    def advance(self, **kwargs):
        self._now = self._now + timedelta(**kwargs)


T0 = datetime(2026, 8, 11, 0, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def clock():
    return FixedClock(T0)


@pytest.fixture
def coord(clock):
    return C.Coordinator(MemoryStore(), clock, epoch_id="e1", leader_epoch=3)


# --- attempt 採番 -------------------------------------------------------------


def test_attempt_ids_are_monotonic_without_gaps(coord):
    ids = []
    for _ in range(5):
        attempt, failure = coord.issue_attempt()
        assert failure is None
        ids.append(attempt.attempt_id)
    assert ids == [1, 2, 3, 4, 5]


def test_lease_is_24h_and_derived_from_authoritative_clock(coord, clock):
    attempt, failure = coord.issue_attempt()
    assert failure is None
    assert attempt.issued_at == T0
    assert attempt.expires_at == T0 + timedelta(seconds=C.LEASE_SECONDS)
    assert C.LEASE_SECONDS == 24 * 3600


def test_issue_attempt_takes_no_time_argument():
    """runner の local clock を正にする経路を構造的に持たない。"""
    params = set(inspect.signature(C.Coordinator.issue_attempt).parameters) - {"self"}
    assert params == set(), f"時刻を含む引数を受け取ってはならない: {params}"


def test_stale_leader_cannot_issue(clock):
    store = MemoryStore()
    C.Coordinator(store, clock, epoch_id="e2", leader_epoch=7).issue_attempt()

    stale = C.Coordinator(store, clock, epoch_id="e1", leader_epoch=3)
    attempt, failure = stale.issue_attempt()
    assert attempt is None
    assert failure.code == C.CODE_BLOCKED
    assert "stale leader" in failure.reason


def test_unreachable_store_does_not_issue_offline(clock):
    coord = C.Coordinator(UnreachableStore(), clock, epoch_id="e1", leader_epoch=1)
    attempt, failure = coord.issue_attempt()
    assert attempt is None
    assert failure.code == C.CODE_BLOCKED


def test_lost_ack_is_not_treated_as_success(clock):
    coord = C.Coordinator(LostAckStore(), clock, epoch_id="e1", leader_epoch=1)
    attempt, failure = coord.issue_attempt()
    assert attempt is None, "CAS の完了を確認できない間は採番済みとして扱わない"
    assert failure.code == C.CODE_BLOCKED


def test_concurrent_issue_does_not_duplicate_ids(clock):
    """同じ version を見た2者のうち、CAS が通る 1 者だけが採番できる。"""
    store = MemoryStore()
    a = C.Coordinator(store, clock, epoch_id="e1", leader_epoch=1)
    b = C.Coordinator(store, clock, epoch_id="e1", leader_epoch=1)

    first, _ = a.issue_attempt()
    # b は a の書き込み前の version を握っている状況を、直接 CAS で再現する。
    assert store.compare_and_set(C._STATE_KEY, 0, {"leader_epoch": 1, "attempt_counter": 99}) is False

    second, failure = b.issue_attempt()
    assert failure is None
    assert second.attempt_id == first.attempt_id + 1


# --- TTL ---------------------------------------------------------------------


def test_ttl_kinds_are_24h_and_7d():
    assert C.TTL_KINDS["qualification"] == 24 * 3600
    assert C.TTL_KINDS["evidence"] == 7 * 24 * 3600


@pytest.mark.parametrize("checkpoint", sorted(C.TTL_CHECKPOINTS))
def test_ttl_passes_before_expiry(coord, clock, checkpoint):
    clock.advance(hours=23)
    assert coord.check_ttl(issued_at=T0, kind="qualification", checkpoint=checkpoint) is None


@pytest.mark.parametrize("checkpoint", sorted(C.TTL_CHECKPOINTS))
def test_ttl_boundary_is_expired(coord, clock, checkpoint):
    """境界時刻ちょうどは満了として扱う（安全側）。"""
    clock.advance(seconds=C.QUALIFICATION_TTL_SECONDS)
    failure = coord.check_ttl(issued_at=T0, kind="qualification", checkpoint=checkpoint)
    assert failure is not None
    assert failure.code == C.CODE_BLOCKED


def test_evidence_ttl_is_checked_at_both_points(coord, clock):
    clock.advance(days=6)
    assert coord.check_ttl(issued_at=T0, kind="evidence", checkpoint="start") is None
    clock.advance(days=1)
    assert coord.check_ttl(issued_at=T0, kind="evidence", checkpoint="pre-mutation") is not None


def test_unknown_ttl_kind_and_checkpoint_are_rejected(coord):
    assert coord.check_ttl(issued_at=T0, kind="unknown", checkpoint="start").code == C.CODE_INVALID_INPUT
    assert (
        coord.check_ttl(issued_at=T0, kind="evidence", checkpoint="whenever").code
        == C.CODE_INVALID_INPUT
    )


# --- guard token -------------------------------------------------------------


FULL_PROOF = C.ReleaseProof(
    owner_process_exited=True,
    child_git_processes_exited=True,
    os_lock_released=True,
    reconcile_completed=True,
    old_token_quarantined=True,
)


def test_expired_lease_alone_does_not_reissue_guard(coord, clock):
    """lease 満了は再発行の根拠にならない。"""
    clock.advance(days=2)
    token, failure = coord.reissue_guard_token(target_key="index:abc", proof=C.ReleaseProof())
    assert token is None
    assert failure.code == C.CODE_BLOCKED
    assert failure.indefinite is True, "証明が無い間は無期限 BLOCKED が安全側の既定"


@pytest.mark.parametrize(
    "field",
    [
        "owner_process_exited",
        "child_git_processes_exited",
        "os_lock_released",
        "reconcile_completed",
        "old_token_quarantined",
    ],
)
def test_partial_proof_does_not_reissue_guard(coord, field):
    """1つでも欠けたら再発行しない。"""
    proof = C.ReleaseProof(**{f: (f != field) for f in
                              ("owner_process_exited", "child_git_processes_exited",
                               "os_lock_released", "reconcile_completed", "old_token_quarantined")})
    token, failure = coord.reissue_guard_token(target_key="index:abc", proof=proof)
    assert token is None
    assert field in failure.reason


def test_full_proof_reissues_monotonic_token(coord):
    first, failure = coord.reissue_guard_token(target_key="index:abc", proof=FULL_PROOF)
    assert failure is None and first == 1
    second, failure = coord.reissue_guard_token(target_key="index:abc", proof=FULL_PROOF)
    assert failure is None and second == 2


def test_guard_token_is_per_target(coord):
    a, _ = coord.reissue_guard_token(target_key="index:abc", proof=FULL_PROOF)
    b, _ = coord.reissue_guard_token(target_key="local-ref:refs/heads/main", proof=FULL_PROOF)
    assert a == b == 1, "target ごとに独立した系列である"


# --- 単回 nonce ---------------------------------------------------------------


def test_nonce_normal_lifecycle(coord):
    assert coord.begin_nonce("n1") is None
    assert coord.finish_nonce("n1", outcome=C.NONCE_USED_DONE) is None


def test_used_pending_nonce_cannot_be_reused(coord):
    """USED_PENDING のまま中断した nonce は reconcile 完了まで再利用不可。"""
    assert coord.begin_nonce("n1") is None
    failure = coord.begin_nonce("n1")
    assert failure is not None
    assert failure.code == C.CODE_BLOCKED
    assert failure.indefinite is True


def test_completed_nonce_cannot_be_reused(coord):
    coord.begin_nonce("n1")
    coord.finish_nonce("n1", outcome=C.NONCE_USED_DONE)
    failure = coord.begin_nonce("n1")
    assert failure is not None and failure.code == C.CODE_BLOCKED


def test_quarantined_nonce_cannot_be_reused(coord):
    coord.begin_nonce("n1")
    coord.finish_nonce("n1", outcome=C.NONCE_QUARANTINED)
    assert coord.begin_nonce("n1") is not None


def test_finish_requires_pending_state(coord):
    failure = coord.finish_nonce("never-started", outcome=C.NONCE_USED_DONE)
    assert failure is not None and failure.code == C.CODE_BLOCKED


def test_unknown_nonce_outcome_is_rejected(coord):
    coord.begin_nonce("n1")
    failure = coord.finish_nonce("n1", outcome="MAYBE")
    assert failure is not None and failure.code == C.CODE_INVALID_INPUT
