"""qualification の隔離 namespace（FLW-NFR-011 / FLW-NFR-012）の単体テストと負の対照。

負の対照: 推測可能な run ID、lease 未取得での払い出し、lease 切替後の mutation、
CAS 再照合なしの mutation、残存副作用がある状態の見逃し。
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "evals" / "flow-core" / "m1-eval"))

import isolation as I  # noqa: E402

T0 = datetime(2026, 8, 11, tzinfo=timezone.utc)
LEASE = I.Lease(lease_id="lease:e1:1", expires_at=T0 + timedelta(hours=24))
OTHER_LEASE = I.Lease(lease_id="lease:e1:2", expires_at=T0 + timedelta(hours=24))


@pytest.fixture
def allocator():
    return I.IsolationAllocator(owner="owner-1")


def _allocate(allocator, kind="Q-NORMAL", operation="git.commit"):
    scope, failure = allocator.allocate(
        platform="claude", operation=operation, trial_kind=kind, lease=LEASE
    )
    assert failure is None
    return scope


# --- run ID の推測不能性 -------------------------------------------------------


def test_run_id_is_not_guessable():
    ids = {I.new_run_id() for _ in range(200)}
    assert len(ids) == 200, "run ID が衝突している"
    assert all(len(i) == I.RUN_ID_BYTES * 2 for i in ids)
    assert I.RUN_ID_BYTES >= 16


def test_run_ids_are_not_sequential():
    a, b = I.new_run_id(), I.new_run_id()
    assert int(b, 16) - int(a, 16) not in (0, 1), "連番から次の run ID を推測できてはならない"


def test_same_cell_allocated_twice_gets_distinct_namespaces(allocator):
    first = _allocate(allocator)
    second = _allocate(allocator)
    assert first.namespace.run_id != second.namespace.run_id
    assert first.namespace.repo_namespace != second.namespace.repo_namespace
    assert first.namespace.remote_namespace != second.namespace.remote_namespace


def test_namespaces_are_independent_per_trial_kind(allocator):
    names = {
        _allocate(allocator, kind=kind).namespace.repo_namespace for kind in I.TRIAL_KINDS
    }
    assert len(names) == 3


def test_sandbox_boundary_combines_repo_and_remote(allocator):
    scope = _allocate(allocator)
    boundary = scope.namespace.sandbox_boundary
    assert scope.namespace.repo_namespace in boundary
    assert scope.namespace.remote_namespace in boundary


# --- lease 拘束 ----------------------------------------------------------------


def test_allocation_requires_a_lease(allocator):
    scope, failure = allocator.allocate(
        platform="claude", operation="git.commit", trial_kind="Q-NORMAL",
        lease=I.Lease(lease_id="", expires_at=T0),
    )
    assert scope is None
    assert failure.code == I.CODE_BLOCKED


def test_unknown_trial_kind_is_rejected(allocator):
    scope, failure = allocator.allocate(
        platform="claude", operation="git.commit", trial_kind="Q-WHATEVER", lease=LEASE
    )
    assert scope is None and failure.code == I.CODE_INVALID_INPUT


def test_same_lease_passes_check(allocator):
    scope = _allocate(allocator)
    assert allocator.check_lease(scope, LEASE) is None


def test_switched_lease_blocks(allocator):
    scope = _allocate(allocator)
    failure = allocator.check_lease(scope, OTHER_LEASE)
    assert failure.code == I.CODE_BLOCKED
    assert "切り替わった" in failure.reason


def test_missing_lease_blocks(allocator):
    scope = _allocate(allocator)
    assert allocator.check_lease(scope, None).code == I.CODE_BLOCKED


# --- mutation 直前の CAS 再照合 -------------------------------------------------


def test_guard_allows_mutation_when_ref_matches(allocator):
    scope = _allocate(allocator)
    assert allocator.guard_mutation(
        scope, current=LEASE, expected_ref="abc123", observed_ref="abc123"
    ) is None


def test_guard_blocks_when_ref_cannot_be_observed(allocator):
    scope = _allocate(allocator)
    failure = allocator.guard_mutation(
        scope, current=LEASE, expected_ref="abc123", observed_ref=None
    )
    assert failure.code == I.CODE_BLOCKED
    assert "再照合できない" in failure.reason


def test_guard_blocks_on_toctou(allocator):
    scope = _allocate(allocator)
    failure = allocator.guard_mutation(
        scope, current=LEASE, expected_ref="abc123", observed_ref="def456"
    )
    assert failure.code == I.CODE_BLOCKED
    assert "TOCTOU" in failure.reason


def test_guard_blocks_after_lease_switch(allocator):
    """lease が切り替わっていれば ref が一致していても mutation させない。"""
    scope = _allocate(allocator)
    failure = allocator.guard_mutation(
        scope, current=OTHER_LEASE, expected_ref="abc123", observed_ref="abc123"
    )
    assert failure.code == I.CODE_BLOCKED


# --- 残存副作用 ----------------------------------------------------------------


def test_clean_finish_has_no_residual(allocator):
    scope = _allocate(allocator)
    digest = I.fixture_digest([("a.txt", "d1")])
    scope.initial_digest = digest
    assert allocator.finish(scope, final_digest=digest) == []


def test_changed_fixture_is_reported_as_residual(allocator):
    scope = _allocate(allocator)
    scope.initial_digest = I.fixture_digest([("a.txt", "d1")])
    residual = allocator.finish(scope, final_digest=I.fixture_digest([("a.txt", "d2")]))
    assert residual and "初期状態へ戻っていない" in residual[0]
    assert "宣言外" in residual[0]


def test_declared_effects_are_still_residual(allocator):
    """宣言された effects であっても、戻っていない事実は隠さない。"""
    scope = _allocate(allocator)
    scope.initial_digest = I.fixture_digest([("a.txt", "d1")])
    residual = allocator.finish(
        scope, final_digest=I.fixture_digest([("a.txt", "d2")]), declared_effects=["stage a.txt"]
    )
    assert residual != []


def test_missing_initial_digest_is_residual_not_pass(allocator):
    """初期 digest が無いことを「副作用なし」と読み替えない。"""
    scope = _allocate(allocator)
    residual = allocator.finish(scope, final_digest=I.fixture_digest([("a.txt", "d1")]))
    assert residual and "判定できない" in residual[0]


def test_fixture_digest_is_order_independent():
    a = I.fixture_digest([("a.txt", "1"), ("b.txt", "2")])
    b = I.fixture_digest([("b.txt", "2"), ("a.txt", "1")])
    assert a == b
    assert a.startswith("sha256:")


# --- 解放 ----------------------------------------------------------------------


def test_release_is_idempotent_and_tracks_leaks(allocator):
    scope = _allocate(allocator)
    assert allocator.unreleased() == [scope.namespace.run_id]
    allocator.release(scope)
    allocator.release(scope)
    assert allocator.unreleased() == []
    assert scope.released is True


def test_unreleased_namespaces_are_visible(allocator):
    a = _allocate(allocator)
    _allocate(allocator)
    allocator.release(a)
    assert len(allocator.unreleased()) == 1
