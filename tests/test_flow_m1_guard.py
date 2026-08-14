"""target guard プロトコル（FLW-NFR-012 / FLW-NFR-006）の単体テストと負の対照。

負の対照: 逆順取得、family lock を先に取った状態からの guard 取得、fencing token 不一致での
mutation、canonical 化できない target、既存 pending / quarantine がある状態での新 intent。
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / "plugins" / "bitz-flow" / "skills" / "flow-core"
sys.path.insert(0, str(SKILL / "scripts"))

from flowlib import guard as GD  # noqa: E402


class _Tokens:
    """coordinator core の単調増加 fencing token を模す。"""

    def __init__(self):
        self._n = 0

    def __call__(self, canonical_key):
        self._n += 1
        return self._n


@pytest.fixture
def manager():
    return GD.TargetGuardManager()


@pytest.fixture
def tokens():
    return _Tokens()


@pytest.fixture
def repo(tmp_path):
    common = tmp_path / "repo" / ".git"
    common.mkdir(parents=True)
    return common


# --- canonical 化 -------------------------------------------------------------


def test_index_target_includes_worktree_id(repo):
    a = GD.canonical_index_target(repo, "wt-1")
    b = GD.canonical_index_target(repo, "wt-2")
    assert a.canonical_key != b.canonical_key, "worktree ごとに index は別 target"
    assert a.kind == GD.KIND_INDEX


def test_symlinked_path_converges_to_same_target(tmp_path, repo):
    link = tmp_path / "link-to-git"
    link.symlink_to(repo, target_is_directory=True)
    assert GD.canonical_index_target(repo, "wt-1") == GD.canonical_index_target(link, "wt-1")


def test_relative_path_converges_to_same_target(repo, monkeypatch):
    monkeypatch.chdir(repo.parent)
    assert GD.canonical_index_target(repo, "w") == GD.canonical_index_target(Path(".git"), "w")


def test_ref_shorthand_and_full_ref_converge(repo):
    a = GD.canonical_local_ref_target(repo, "main")
    b = GD.canonical_local_ref_target(repo, "refs/heads/main")
    assert a == b


def test_remote_target_ignores_local_identity_and_alias():
    """別 clone・別 remote alias からでも同じ remote ref は同一 target。"""
    a = GD.canonical_remote_ref_target("github.com", "R_kg123", "refs/heads/main")
    b = GD.canonical_remote_ref_target("GitHub.com", "R_kg123", "main")
    assert a == b


def test_remote_target_separates_different_repositories():
    a = GD.canonical_remote_ref_target("github.com", "R_kg123", "main")
    b = GD.canonical_remote_ref_target("github.com", "R_kg999", "main")
    assert a != b


def test_order_is_bytewise_ascending_and_dedups(repo):
    targets = [
        GD.canonical_local_ref_target(repo, "zeta"),
        GD.canonical_index_target(repo, "wt-1"),
        GD.canonical_local_ref_target(repo, "alpha"),
        GD.canonical_index_target(repo, "wt-1"),
    ]
    ordered = GD.order(targets)
    keys = [t.canonical_key for t in ordered]
    assert keys == sorted(keys)
    assert len(ordered) == 3, "alias / 重複は同一 target へ畳む"


# --- 取得順序 ------------------------------------------------------------------


def test_acquire_orders_targets_ascending(manager, tokens, repo):
    targets = [
        GD.canonical_local_ref_target(repo, "zeta"),
        GD.canonical_local_ref_target(repo, "alpha"),
    ]
    guard_set, failure = manager.acquire(targets, operation_id="op-1", next_token=tokens)
    assert failure is None
    keys = [t.canonical_key for t in guard_set.targets]
    assert keys == sorted(keys), "要求順に関わらず canonical 昇順で取得する"


def test_reverse_request_is_normalized_not_rejected(manager, tokens, repo):
    """M1-FLT-006: 逆順要求は canonical 順へ正規化する。"""
    targets = GD.order(
        [GD.canonical_local_ref_target(repo, "b"), GD.canonical_local_ref_target(repo, "a")]
    )
    guard_set, failure = manager.acquire(
        list(reversed(targets)), operation_id="op-1", next_token=tokens
    )
    assert failure is None
    assert [t.canonical_key for t in guard_set.targets] == [t.canonical_key for t in targets]


def test_family_lock_taken_first_is_rejected(manager, tokens, repo):
    guard_set, failure = manager.acquire(
        [GD.canonical_index_target(repo, "w")],
        operation_id="op-1",
        next_token=tokens,
        family_lock_already_held=True,
    )
    assert guard_set is None
    assert failure.code == GD.CODE_BLOCKED
    assert "先に取らなければならない" in failure.reason


def test_partial_failure_releases_in_reverse_with_no_side_effect(manager, tokens, repo):
    """途中失敗時は取得済みを解放し、副作用 0 で戻る。"""
    contested = GD.canonical_local_ref_target(repo, "b")
    first, _ = manager.acquire([contested], operation_id="op-holder", next_token=tokens)
    assert first is not None

    targets = [GD.canonical_local_ref_target(repo, "a"), contested]
    guard_set, failure = manager.acquire(targets, operation_id="op-2", next_token=tokens)
    assert guard_set is None and failure.code == GD.CODE_BLOCKED
    assert manager.held_targets() == [contested.canonical_key], "op-2 の取得分は残さない"


def test_empty_targets_rejected(manager, tokens):
    guard_set, failure = manager.acquire([], operation_id="op-1", next_token=tokens)
    assert guard_set is None and failure.code == GD.CODE_INVALID_INPUT


def test_unknown_identity_kind_rejected(manager, tokens):
    guard_set, failure = manager.acquire(
        [GD.Target("filesystem", "fs:/tmp")], operation_id="op-1", next_token=tokens
    )
    assert guard_set is None and failure.code == GD.CODE_INVALID_INPUT


def test_unresolvable_target_blocks(manager, tokens):
    guard_set, failure = manager.acquire(
        [GD.Target(GD.KIND_INDEX, "")], operation_id="op-1", next_token=tokens
    )
    assert guard_set is None
    assert failure.code == GD.CODE_BLOCKED
    assert "一意化できない" in failure.reason


# --- cross-family 競合（M1-FLT-005）--------------------------------------------


def test_cross_family_contention_allows_at_most_one_mutation(manager, tokens, repo):
    """stage と commit は family が違っても同じ index target で直列化される。"""
    index = GD.canonical_index_target(repo, "wt-1")
    stage, failure = manager.acquire(
        [index], operation_id="op-stage", next_token=tokens, family_lock="index"
    )
    assert failure is None

    commit, failure = manager.acquire(
        [index], operation_id="op-commit", next_token=tokens, family_lock="ref"
    )
    assert commit is None, "family が違っても同一 target の同時 mutation を許さない"
    assert failure.code == GD.CODE_BLOCKED

    manager.release(stage)
    commit, failure = manager.acquire(
        [index], operation_id="op-commit", next_token=tokens, family_lock="ref"
    )
    assert failure is None and commit is not None


def test_guard_key_excludes_operation_family(manager, tokens, repo):
    index = GD.canonical_index_target(repo, "wt-1")
    assert "stage" not in index.canonical_key and "commit" not in index.canonical_key


def test_same_remote_ref_from_different_clones_converges(manager, tokens):
    """M1-FLT-024: 別 clone から同じ remote ref を要求しても同時 publish は最大 1。"""
    target = GD.canonical_remote_ref_target("github.com", "R_1", "main")
    alias = GD.canonical_remote_ref_target("github.com", "R_1", "refs/heads/main")
    first, _ = manager.acquire([target], operation_id="op-a", next_token=tokens)
    assert first is not None
    second, failure = manager.acquire([alias], operation_id="op-b", next_token=tokens)
    assert second is None and failure.code == GD.CODE_BLOCKED


# --- 既存 pending / quarantine -------------------------------------------------


def test_pending_intent_blocks_new_intent(manager, tokens, repo):
    target = GD.canonical_index_target(repo, "w")
    manager.mark_pending(target, "op-old")
    guard_set, failure = manager.acquire([target], operation_id="op-new", next_token=tokens)
    assert guard_set is None
    assert "pending intent" in failure.reason


def test_quarantine_blocks_new_intent(manager, tokens, repo):
    target = GD.canonical_index_target(repo, "w")
    manager.mark_quarantined(target, "因果を一意化できない")
    guard_set, failure = manager.acquire([target], operation_id="op-new", next_token=tokens)
    assert guard_set is None
    assert "quarantine" in failure.reason


def test_cleared_target_can_be_acquired(manager, tokens, repo):
    target = GD.canonical_index_target(repo, "w")
    manager.mark_pending(target, "op-old")
    manager.clear(target)
    guard_set, failure = manager.acquire([target], operation_id="op-new", next_token=tokens)
    assert failure is None and guard_set is not None


# --- fencing の再照合 -----------------------------------------------------------


def test_verify_passes_while_holding(manager, tokens, repo):
    target = GD.canonical_index_target(repo, "w")
    guard_set, _ = manager.acquire([target], operation_id="op-1", next_token=tokens)
    assert manager.verify_before_mutation(guard_set, target) is None


def test_verify_rejects_unheld_target(manager, tokens, repo):
    target = GD.canonical_index_target(repo, "w")
    other = GD.canonical_local_ref_target(repo, "main")
    guard_set, _ = manager.acquire([target], operation_id="op-1", next_token=tokens)
    failure = manager.verify_before_mutation(guard_set, other)
    assert failure.code == GD.CODE_BLOCKED


def test_verify_rejects_after_owner_changed(manager, tokens, repo):
    target = GD.canonical_index_target(repo, "w")
    guard_set, _ = manager.acquire([target], operation_id="op-1", next_token=tokens)
    manager.release(guard_set)
    manager.acquire([target], operation_id="op-2", next_token=tokens)
    failure = manager.verify_before_mutation(guard_set, target)
    assert failure.code == GD.CODE_BLOCKED
    assert "所有者" in failure.reason


def test_verify_rejects_stale_fencing_token(manager, tokens, repo):
    """token が再発行されていれば、古い token を持つ operation は mutation できない。"""
    target = GD.canonical_index_target(repo, "w")
    guard_set, _ = manager.acquire([target], operation_id="op-1", next_token=tokens)
    manager._tokens[target.canonical_key] = guard_set.token_for(target.canonical_key) + 1
    failure = manager.verify_before_mutation(guard_set, target)
    assert failure.code == GD.CODE_BLOCKED
    assert "fencing token" in failure.reason


def test_release_is_idempotent(manager, tokens, repo):
    target = GD.canonical_index_target(repo, "w")
    guard_set, _ = manager.acquire([target], operation_id="op-1", next_token=tokens)
    manager.release(guard_set)
    manager.release(guard_set)
    assert manager.held_targets() == []


# --- capability ----------------------------------------------------------------


@pytest.mark.parametrize(
    "capability,missing",
    [
        (GD.Capability(advisory_lock=False), "advisory lock"),
        (GD.Capability(owner_only_area=False), "owner-only"),
        (GD.Capability(fsync=False), "fsync"),
    ],
)
def test_missing_local_capability_makes_write_unsupported(capability, missing, tokens, repo):
    manager = GD.TargetGuardManager(capability=capability)
    guard_set, failure = manager.acquire(
        [GD.canonical_index_target(repo, "w")], operation_id="op-1", next_token=tokens
    )
    assert guard_set is None
    assert failure.code == GD.CODE_UNSUPPORTED
    assert missing in failure.reason


def test_missing_remote_cas_only_affects_remote_targets(tokens, repo):
    manager = GD.TargetGuardManager(capability=GD.Capability(remote_cas=False))
    local, failure = manager.acquire(
        [GD.canonical_index_target(repo, "w")], operation_id="op-1", next_token=tokens
    )
    assert failure is None and local is not None

    remote, failure = manager.acquire(
        [GD.canonical_remote_ref_target("github.com", "R_1", "main")],
        operation_id="op-2",
        next_token=tokens,
    )
    assert remote is None and failure.code == GD.CODE_UNSUPPORTED


def test_guard_identity_kinds_are_closed():
    assert GD.GUARD_IDENTITY_KINDS == (
        "index", "local-ref", "remote-tracking-ref", "fetch-head", "remote-ref",
        "worktree-dir", "worktree-registry"
    )
