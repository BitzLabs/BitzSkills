"""remote-write（FLW-FR-005 / FLW-CON-005 / FLW-CON-006）をローカル bare で検証する。

中心命題: remote への書き込みは手元から取り消せない。expected 値を apply 直前に再照会し、
force を提供せず、応答喪失時は成否を推定しない。
"""

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / "plugins" / "bitz-flow" / "skills" / "flow-core"
sys.path.insert(0, str(SKILL / "scripts"))

from flowlib import git_publish as P  # noqa: E402


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


def _advance_local(repo: Path, message="chore: local"):
    (repo / f"{abs(hash(message)) % 1000}.txt").write_text(message, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", message)


def _advance_remote(remote: Path, tmp_path: Path, message="chore: remote"):
    work = tmp_path / f"pusher{abs(hash(message)) % 1000}"
    subprocess.run(["git", "clone", "-q", str(remote), str(work)], check=True)
    _git(work, "config", "user.email", "o@example.com")
    _git(work, "config", "user.name", "o")
    (work / "r.txt").write_text(message, encoding="utf-8")
    _git(work, "add", "-A")
    _git(work, "commit", "-qm", message)
    _git(work, "push", "-q", "origin", "main")


def _remote_sha(remote: Path, ref="refs/heads/main") -> str | None:
    out = subprocess.run(
        ["git", "-C", str(remote), "rev-parse", "--verify", "--quiet", ref],
        capture_output=True, text=True,
    ).stdout.strip()
    return out or None


# --- capability ----------------------------------------------------------------


def test_without_remote_cas_publish_is_unsupported(repo):
    plan, failure = P.plan_publish(repo, remote="origin", branch="main", remote_cas=False)
    assert plan is None
    assert failure.code == P.CODE_UNSUPPORTED


# --- plan ----------------------------------------------------------------------


def test_plan_records_expected_head(repo, remote):
    plan, failure = P.plan_publish(repo, remote="origin", branch="main")
    assert failure is None
    assert plan.expected_head == _remote_sha(remote)
    assert plan.approval == P.APPROVAL_EXPLICIT_HUMAN


def test_plan_has_no_side_effect(repo, remote):
    before = _remote_sha(remote)
    P.plan_publish(repo, remote="origin", branch="main")
    assert _remote_sha(remote) == before


def test_plan_rejects_unknown_branch(repo):
    plan, failure = P.plan_publish(repo, remote="origin", branch="no-such")
    assert plan is None and failure.code == P.CODE_INVALID_INPUT


# --- 承認 -----------------------------------------------------------------------


def test_publish_requires_explicit_approval(repo, remote):
    _advance_local(repo)
    plan, _ = P.plan_publish(repo, remote="origin", branch="main")
    before = _remote_sha(remote)

    outcome, failure = P.apply_publish(repo, plan, approved=False)
    assert outcome is None
    assert failure.code == P.CODE_APPROVAL_REQUIRED
    assert _remote_sha(remote) == before, "承認前に remote を変えてはならない"


def test_delete_requires_independent_approval(repo, remote, tmp_path):
    _git(repo, "push", "-q", "origin", "HEAD:refs/heads/feature")
    plan, _ = P.plan_delete_remote_branch(repo, remote="origin", branch="feature")

    outcome, failure = P.apply_delete_remote_branch(repo, plan, approved=False)
    assert outcome is None and failure.code == P.CODE_APPROVAL_REQUIRED
    assert _remote_sha(remote, "refs/heads/feature") is not None


# --- publish -------------------------------------------------------------------


def test_publish_updates_remote_ref(repo, remote):
    _advance_local(repo)
    plan, _ = P.plan_publish(repo, remote="origin", branch="main")
    outcome, failure = P.apply_publish(repo, plan, approved=True)
    assert failure is None
    assert outcome.code == P.CODE_DONE
    assert _remote_sha(remote) == plan.local_head
    assert outcome.recovery == P.REC_PUSH


def test_stale_expected_head_stops_without_side_effect(repo, remote, tmp_path):
    """plan 後に remote が動いていたら push しない。"""
    _advance_local(repo)
    plan, _ = P.plan_publish(repo, remote="origin", branch="main")
    _advance_remote(remote, tmp_path)
    before = _remote_sha(remote)

    outcome, failure = P.apply_publish(repo, plan, approved=True)
    assert outcome is None
    assert failure.code == P.CODE_STALE
    assert failure.cause == "snapshot-mismatch"
    assert _remote_sha(remote) == before, "STALE 時に remote を変えてはならない"


def test_stale_next_action_is_requery_not_force(repo, remote, tmp_path):
    _advance_local(repo)
    plan, _ = P.plan_publish(repo, remote="origin", branch="main")
    _advance_remote(remote, tmp_path)
    _, failure = P.apply_publish(repo, plan, approved=True)

    actions = P.next_actions_for(failure)
    assert actions == ("git.branches",)
    for forbidden in ("force", "push", "update"):
        assert not any(forbidden in a for a in actions)


def test_response_loss_does_not_infer_outcome(repo, remote):
    """応答が返らないとき「たぶん成功」も「たぶん失敗」も言わない。"""
    _advance_local(repo)
    plan, _ = P.plan_publish(repo, remote="origin", branch="main")

    outcome, failure = P.apply_publish(repo, plan, approved=True, response_lost=True)
    assert failure is None
    assert outcome.code == P.CODE_INDETERMINATE
    assert outcome.after_sha is None
    assert P.next_actions_for(outcome) == ()
    assert P.required_human_input(outcome)


# --- delete --------------------------------------------------------------------


def test_delete_removes_only_the_exact_ref(repo, remote):
    _git(repo, "push", "-q", "origin", "HEAD:refs/heads/feature")
    main_before = _remote_sha(remote)

    plan, _ = P.plan_delete_remote_branch(repo, remote="origin", branch="feature")
    outcome, failure = P.apply_delete_remote_branch(repo, plan, approved=True)

    assert failure is None and outcome.code == P.CODE_DONE
    assert _remote_sha(remote, "refs/heads/feature") is None
    assert _remote_sha(remote) == main_before, "他の ref を消してはならない"


def test_delete_stops_when_remote_sha_changed(repo, remote, tmp_path):
    _git(repo, "push", "-q", "origin", "HEAD:refs/heads/feature")
    plan, _ = P.plan_delete_remote_branch(repo, remote="origin", branch="feature")

    work = tmp_path / "other"
    subprocess.run(["git", "clone", "-q", str(remote), str(work)], check=True)
    _git(work, "config", "user.email", "o@example.com")
    _git(work, "config", "user.name", "o")
    _git(work, "checkout", "-q", "-B", "feature", "origin/feature")
    (work / "f.txt").write_text("f\n", encoding="utf-8")
    _git(work, "add", "-A")
    _git(work, "commit", "-qm", "chore: feature moved")
    _git(work, "push", "-q", "origin", "feature")

    outcome, failure = P.apply_delete_remote_branch(repo, plan, approved=True)
    assert outcome is None
    assert failure.code == P.CODE_STALE
    assert _remote_sha(remote, "refs/heads/feature") is not None, "削除しない"


def test_delete_of_missing_ref_is_blocked(repo):
    plan, failure = P.plan_delete_remote_branch(repo, remote="origin", branch="ghost")
    assert plan is None
    assert failure.code == P.CODE_BLOCKED and failure.cause == "invalid-ref"


def test_delete_response_loss_is_indeterminate(repo, remote):
    _git(repo, "push", "-q", "origin", "HEAD:refs/heads/feature")
    plan, _ = P.plan_delete_remote_branch(repo, remote="origin", branch="feature")
    outcome, failure = P.apply_delete_remote_branch(
        repo, plan, approved=True, response_lost=True
    )
    assert failure is None and outcome.code == P.CODE_INDETERMINATE
    assert _remote_sha(remote, "refs/heads/feature") is not None


# --- 禁止操作を提示しない -------------------------------------------------------


def test_module_offers_no_force_entry_point():
    public = [name for name in dir(P) if not name.startswith("_")]
    for name in public:
        lowered = name.lower()
        assert "force" not in lowered
        assert "reset" not in lowered
        assert "rebase" not in lowered


def test_forbidden_operations_are_declared():
    assert "force-push" in P.FORBIDDEN_OPERATIONS
    assert "reset --hard" in P.FORBIDDEN_OPERATIONS


def test_no_next_action_mentions_forbidden_operations(repo, remote, tmp_path):
    _advance_local(repo)
    plan, _ = P.plan_publish(repo, remote="origin", branch="main")
    _advance_remote(remote, tmp_path)
    _, failure = P.apply_publish(repo, plan, approved=True)
    for action in P.next_actions_for(failure):
        for forbidden in P.FORBIDDEN_OPERATIONS:
            assert forbidden not in action


# --- guard target ---------------------------------------------------------------


def test_publish_target_excludes_local_identity():
    targets = P.guard_targets_for_publish("github.com", "R_kg1", "main")
    assert len(targets) == 1
    key = targets[0].canonical_key
    assert "github.com" in key and "R_kg1" in key
    assert "/tmp" not in key and ".git" not in key


def test_same_remote_ref_from_different_hosts_differ():
    a = P.guard_targets_for_publish("github.com", "R_1", "main")[0]
    b = P.guard_targets_for_publish("gitlab.com", "R_1", "main")[0]
    assert a.canonical_key != b.canonical_key
