"""git.fetch / git.sync と REC-FETCH・REC-SYNC（FLW-FR-005 / FLW-NFR-003）。

remote はローカル bare リポジトリで代替し、外部ネットワークへは接続しない。

中心命題: **部分完了を自動で埋めない**。fetch の再実行も自動 branch 更新もしない。
"""

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / "plugins" / "bitz-flow" / "skills" / "flow-core"
sys.path.insert(0, str(SKILL / "scripts"))

from flowlib import git_sync as S  # noqa: E402
from flowlib import guard as GD  # noqa: E402


def _git(repo: Path, *args: str, check=True):
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=check
    )


@pytest.fixture
def remote(tmp_path):
    bare = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(bare)], check=True)
    return bare


@pytest.fixture
def repo(tmp_path, remote):
    path = tmp_path / "repo"
    path.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(path)], check=True)
    _git(path, "config", "user.email", "t@example.com")
    _git(path, "config", "user.name", "t")
    (path / "a.txt").write_text("base\n", encoding="utf-8")
    _git(path, "add", "a.txt")
    _git(path, "commit", "-qm", "chore: init")
    _git(path, "remote", "add", "origin", str(remote))
    _git(path, "push", "-q", "-u", "origin", "main")
    return path


@pytest.fixture
def common(repo):
    return repo / ".git"


def _advance_remote(remote: Path, tmp_path: Path, branch="main", message="chore: remote change"):
    """remote 側を進める（別 clone 経由）。"""
    work = tmp_path / f"pusher-{branch}-{message[-6:].replace(' ', '')}"
    subprocess.run(["git", "clone", "-q", str(remote), str(work)], check=True)
    _git(work, "config", "user.email", "o@example.com")
    _git(work, "config", "user.name", "o")
    _git(work, "checkout", "-q", "-B", branch)
    (work / f"{branch}.txt").write_text(message, encoding="utf-8")
    _git(work, "add", "-A")
    _git(work, "commit", "-qm", message)
    _git(work, "push", "-q", "origin", branch)


# --- plan ---------------------------------------------------------------------


def test_plan_requires_explicit_remote(repo, common):
    plan, failure = S.plan_fetch(repo, common, remote="")
    assert plan is None and failure.code == S.CODE_INVALID_INPUT


def test_plan_rejects_unknown_remote(repo, common):
    plan, failure = S.plan_fetch(repo, common, remote="nope")
    assert plan is None
    assert failure.cause == "remote-unavailable"


def test_plan_has_no_side_effect(repo, common):
    before = S.tracking_refs(repo, "origin")
    plan, failure = S.plan_fetch(repo, common, remote="origin")
    assert failure is None
    assert S.tracking_refs(repo, "origin") == before
    assert plan.effects


def test_plan_records_current_tracking_refs(repo, common):
    plan, _ = S.plan_fetch(repo, common, remote="origin")
    assert "refs/remotes/origin/main" in plan.tracking_before


# --- guard target --------------------------------------------------------------


def test_fetch_targets_cover_tracking_and_fetch_head(repo, common):
    plan, _ = S.plan_fetch(repo, common, remote="origin")
    targets = S.guard_targets_for_fetch(common, "origin", plan)
    kinds = {t.kind for t in targets}
    assert GD.KIND_FETCH_HEAD in kinds
    assert GD.KIND_REMOTE_TRACKING_REF in kinds


def test_targets_are_canonically_ordered(repo, common):
    plan, _ = S.plan_fetch(repo, common, remote="origin")
    targets = S.guard_targets_for_sync(common, "origin", "main", plan)
    keys = [t.canonical_key for t in targets]
    assert keys == sorted(keys)


def test_sync_targets_include_branch_and_index(repo, common):
    plan, _ = S.plan_fetch(repo, common, remote="origin")
    kinds = {t.kind for t in S.guard_targets_for_sync(common, "origin", "main", plan)}
    assert GD.KIND_LOCAL_REF in kinds and GD.KIND_INDEX in kinds


# --- fetch --------------------------------------------------------------------


def test_fetch_updates_tracking_refs(repo, common, remote, tmp_path):
    _advance_remote(remote, tmp_path)
    plan, _ = S.plan_fetch(repo, common, remote="origin")
    outcome, failure = S.apply_fetch(repo, common, plan)
    assert failure is None
    assert outcome.code == S.CODE_DONE
    assert "refs/remotes/origin/main" in outcome.updated_refs
    assert outcome.recovery == S.REC_FETCH


def test_fetch_with_nothing_to_do_is_done(repo, common):
    plan, _ = S.plan_fetch(repo, common, remote="origin")
    outcome, failure = S.apply_fetch(repo, common, plan)
    assert failure is None and outcome.code == S.CODE_DONE
    assert outcome.updated_refs == ()


def test_symbolic_ref_is_not_a_mutation_target(repo, common):
    """`refs/remotes/origin/HEAD` は既定 branch の別名であって mutation target ではない。

    新しめの Git は初回 fetch でこれを自動作成する。含めてしまうと「何も更新が無い fetch」でも
    ref が動いたように見え、sync が不必要に PARTIAL へ倒れる（CI の Git で実際に起きた）。
    """
    _git(repo, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")
    refs = S.tracking_refs(repo, "origin")
    assert "refs/remotes/origin/HEAD" not in refs
    assert "refs/remotes/origin/main" in refs

    plan, _ = S.plan_fetch(repo, common, remote="origin")
    outcome, failure = S.apply_fetch(repo, common, plan)
    assert failure is None and outcome.code == S.CODE_DONE
    assert outcome.updated_refs == ()


def test_sync_is_done_when_symbolic_ref_appears(repo, common):
    """symbolic ref の出現を「この branch の残作業」と数えない。"""
    _git(repo, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")
    plan, _ = S.plan_fetch(repo, common, remote="origin")
    outcome, failure = S.apply_sync(repo, common, plan, branch="main", upstream="origin/main")
    assert failure is None
    assert outcome.code == S.CODE_DONE
    assert outcome.remaining_steps == ()


def test_other_branch_update_is_not_this_branch_remaining(repo, common, remote, tmp_path):
    """別 branch が更新されても、追従済みの branch の残作業にはしない。"""
    _advance_remote(remote, tmp_path, branch="side", message="chore: side branch")
    plan, _ = S.plan_fetch(repo, common, remote="origin")
    outcome, failure = S.apply_sync(repo, common, plan, branch="main", upstream="origin/main")
    assert failure is None
    assert outcome.code == S.CODE_DONE
    assert outcome.remaining_steps == ()


def test_partial_ref_set_reports_completed_and_remaining(repo, common, remote, tmp_path):
    """M1-FLT 相当: 期待した ref のうち一部しか更新されなかった場合。"""
    _advance_remote(remote, tmp_path)
    plan, _ = S.plan_fetch(repo, common, remote="origin")
    outcome, failure = S.apply_fetch(
        repo, common, plan,
        expected_refs=["refs/remotes/origin/main", "refs/remotes/origin/never-exists"],
    )
    assert failure is None
    assert outcome.code == S.CODE_PARTIAL
    assert "update refs/remotes/origin/main" in outcome.completed_steps
    assert "update refs/remotes/origin/never-exists" in outcome.remaining_steps


def test_partial_does_not_propose_refetch(repo, common, remote, tmp_path):
    _advance_remote(remote, tmp_path)
    plan, _ = S.plan_fetch(repo, common, remote="origin")
    outcome, _ = S.apply_fetch(
        repo, common, plan, expected_refs=["refs/remotes/origin/missing"]
    )
    actions = S.next_actions_for(outcome)
    assert "git.fetch" not in actions, "fetch の再実行を次の一手にしない"
    assert set(actions) <= {"git.status", "git.branches"}


def test_fetch_reports_freshness(repo, common, remote, tmp_path):
    _advance_remote(remote, tmp_path)
    plan, _ = S.plan_fetch(repo, common, remote="origin")
    outcome, _ = S.apply_fetch(repo, common, plan)
    assert outcome.freshness["remote"] == "origin"


def test_fetch_failure_uses_vocabulary_cause(repo, common):
    plan, _ = S.plan_fetch(repo, common, remote="origin")
    _git(repo, "remote", "set-url", "origin", str(repo / "does-not-exist.git"))
    outcome, failure = S.apply_fetch(repo, common, plan)
    assert outcome is None
    assert failure.code == S.CODE_BLOCKED
    assert failure.cause in (
        "not-repository", "remote-unavailable", "permission-denied", "invalid-ref", "invalid-path",
    )


# --- sync ---------------------------------------------------------------------


def test_sync_fast_forwards(repo, common, remote, tmp_path):
    _advance_remote(remote, tmp_path)
    plan, _ = S.plan_fetch(repo, common, remote="origin")
    outcome, failure = S.apply_sync(repo, common, plan, branch="main", upstream="origin/main")
    assert failure is None
    assert outcome.code == S.CODE_DONE
    assert outcome.completed_steps == ("fetch", "branch-update")
    assert outcome.remaining_steps == ()


def test_sync_without_remote_change_is_done(repo, common):
    plan, _ = S.plan_fetch(repo, common, remote="origin")
    outcome, failure = S.apply_sync(repo, common, plan, branch="main", upstream="origin/main")
    assert failure is None
    assert outcome.code == S.CODE_DONE
    assert outcome.remaining_steps == ()


def test_non_fast_forward_stops_without_alternative(repo, common, remote, tmp_path):
    """ff できなければ停止する。merge / rebase を代替提示しない。"""
    _advance_remote(remote, tmp_path)
    (repo / "local.txt").write_text("local\n", encoding="utf-8")
    _git(repo, "add", "local.txt")
    _git(repo, "commit", "-qm", "chore: local diverge")

    plan, _ = S.plan_fetch(repo, common, remote="origin")
    outcome, failure = S.apply_sync(repo, common, plan, branch="main", upstream="origin/main")

    assert failure is None
    assert outcome.code == S.CODE_PARTIAL
    assert outcome.completed_steps == ("fetch",)
    assert outcome.remaining_steps == ("branch-update",)
    assert outcome.cause in ("non-fast-forward", "dirty", "conflict")

    actions = S.next_actions_for(outcome)
    for forbidden in ("git.merge", "git.rebase", "git.reset", "git.commit"):
        assert forbidden not in actions


def test_sync_does_not_auto_update_branch_on_partial(repo, common, remote, tmp_path):
    _advance_remote(remote, tmp_path)
    (repo / "local.txt").write_text("local\n", encoding="utf-8")
    _git(repo, "add", "local.txt")
    _git(repo, "commit", "-qm", "chore: local diverge")
    before = _git(repo, "rev-parse", "main").stdout.strip()

    plan, _ = S.plan_fetch(repo, common, remote="origin")
    S.apply_sync(repo, common, plan, branch="main", upstream="origin/main")

    assert _git(repo, "rev-parse", "main").stdout.strip() == before, "自動で branch を進めない"


def test_partial_next_actions_are_read_only(repo, common):
    outcome = S.SyncOutcome(
        code=S.CODE_PARTIAL, completed_steps=("fetch",), remaining_steps=("branch-update",),
        recovery=S.REC_SYNC,
    )
    actions = S.next_actions_for(outcome)
    assert actions and all(a.split(".")[1] in ("status", "branches") for a in actions)


def test_done_has_no_next_actions():
    outcome = S.SyncOutcome(
        code=S.CODE_DONE, completed_steps=("fetch", "branch-update"), remaining_steps=(),
        recovery=S.REC_SYNC,
    )
    assert S.next_actions_for(outcome) == ()


def test_recovery_ids_are_stable():
    assert S.REC_FETCH == "REC-FETCH"
    assert S.REC_SYNC == "REC-SYNC"
