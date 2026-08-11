"""git.stage の index CAS（FLW-FR-005）を実 Git リポジトリで検証する。

負の対照: `git add .` 相当の一括指定、plan の副作用、index が動いた状態での apply、
`index.lock` を他 writer が保持している状態、native lock を無視した writer。
"""

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / "plugins" / "bitz-flow" / "skills" / "flow-core"
sys.path.insert(0, str(SKILL / "scripts"))

from flowlib import git_write as W  # noqa: E402


def _git(repo: Path, *args: str):
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    )


@pytest.fixture
def repo(tmp_path):
    path = tmp_path / "repo"
    path.mkdir()
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    _git(path, "config", "user.email", "t@example.com")
    _git(path, "config", "user.name", "t")
    (path / "tracked.txt").write_text("base\n", encoding="utf-8")
    _git(path, "add", "tracked.txt")
    _git(path, "commit", "-qm", "init")
    (path / "new.txt").write_text("hello\n", encoding="utf-8")
    (path / "other.txt").write_text("other\n", encoding="utf-8")
    return path


@pytest.fixture
def common(repo):
    return repo / ".git"


def _staged(repo: Path) -> set[str]:
    out = subprocess.run(
        ["git", "-C", str(repo), "diff", "--cached", "--name-only"],
        capture_output=True, text=True, check=True,
    )
    return {line for line in out.stdout.splitlines() if line}


# --- plan は副作用を持たない ---------------------------------------------------


def test_plan_has_no_side_effect(repo, common):
    before = W.index_digest(common)
    plan, failure = W.plan_stage(repo, common, ["new.txt"])
    assert failure is None
    assert W.index_digest(common) == before, "plan で index を変えてはならない"
    assert _staged(repo) == set()


def test_plan_enumerates_effects(repo, common):
    plan, _ = W.plan_stage(repo, common, ["new.txt", "other.txt"])
    assert plan.effects == ("stage new.txt", "stage other.txt")
    assert plan.paths == ("new.txt", "other.txt")


def test_plan_records_current_index_digest(repo, common):
    plan, _ = W.plan_stage(repo, common, ["new.txt"])
    assert plan.index_digest == W.index_digest(common)


@pytest.mark.parametrize("path", [".", "-A", "--all", "*"])
def test_bulk_specifiers_are_rejected(repo, common, path):
    plan, failure = W.plan_stage(repo, common, [path])
    assert plan is None
    assert failure.code == W.CODE_INVALID_INPUT


def test_empty_paths_rejected(repo, common):
    plan, failure = W.plan_stage(repo, common, [])
    assert plan is None and failure.code == W.CODE_INVALID_INPUT


def test_invalid_path_is_classified(repo, common):
    plan, failure = W.plan_stage(repo, common, ["does-not-exist.txt"])
    assert plan is None
    assert failure.code == W.CODE_BLOCKED
    assert failure.cause in ("invalid-path", "invalid-ref", "not-repository", None)


def test_plan_removes_its_temporary_index(repo, common):
    W.plan_stage(repo, common, ["new.txt"])
    leftovers = list(common.glob(".bitz-flow-plan-index-*"))
    assert leftovers == []


# --- apply -------------------------------------------------------------------


def test_apply_publishes_planned_index(repo, common):
    plan, _ = W.plan_stage(repo, common, ["new.txt"])
    digest, failure = W.apply_stage(common, plan)
    assert failure is None
    assert _staged(repo) == {"new.txt"}
    assert W.verify_postcondition(common, digest) is None


def test_apply_leaves_no_lock_behind(repo, common):
    plan, _ = W.plan_stage(repo, common, ["new.txt"])
    W.apply_stage(common, plan)
    assert not (common / W.INDEX_LOCK_NAME).exists()


def test_git_still_understands_the_index(repo, common):
    """自前で書いた index を Git 自身が読めること。"""
    plan, _ = W.plan_stage(repo, common, ["new.txt"])
    W.apply_stage(common, plan)
    out = subprocess.run(
        ["git", "-C", str(repo), "status", "--porcelain"], capture_output=True, text=True, check=True
    )
    assert "A  new.txt" in out.stdout


def test_stale_index_is_rejected_without_side_effect(repo, common):
    """plan 後に index が動いていたら副作用 0 で STALE。"""
    plan, _ = W.plan_stage(repo, common, ["new.txt"])
    _git(repo, "add", "other.txt")
    before = W.index_digest(common)

    digest, failure = W.apply_stage(common, plan)
    assert digest is None
    assert failure.code == W.CODE_STALE
    assert failure.cause == "snapshot-mismatch"
    assert W.index_digest(common) == before, "STALE 時に index を変えてはならない"
    assert _staged(repo) == {"other.txt"}


def test_existing_lock_blocks_apply(repo, common):
    plan, _ = W.plan_stage(repo, common, ["new.txt"])
    lock = common / W.INDEX_LOCK_NAME
    lock.write_bytes(b"")
    try:
        digest, failure = W.apply_stage(common, plan)
        assert digest is None
        assert failure.code == W.CODE_BLOCKED
        assert "他の writer" in failure.reason
        assert _staged(repo) == set()
    finally:
        lock.unlink()


def test_native_lock_excludes_concurrent_git_add(repo, common):
    """M1-FLT-029 前半: 外部 `git add` は native `index.lock` により排他される。"""
    outcome = {}

    def intruder(_common):
        outcome["proc"] = subprocess.run(
            ["git", "-C", str(repo), "add", "other.txt"], capture_output=True, text=True
        )

    plan, _ = W.plan_stage(repo, common, ["new.txt"])
    digest, failure = W.apply_stage(common, plan, on_locked=intruder)

    assert outcome["proc"].returncode != 0, "lock 保持中の git add が通ってはならない"
    assert "index.lock" in outcome["proc"].stderr
    assert failure is None and digest is not None
    assert _staged(repo) == {"new.txt"}, "割り込みの内容が混ざってはならない"


def test_writer_ignoring_native_lock_is_detected(repo, common):
    """M1-FLT-029 後半: lock を無視して index を直接書く writer は検出して quarantine 対象にする。"""

    def intruder(_common):
        # Git を経由せず index ファイルを直接置き換える（lock を尊重しない writer）
        W.index_path(common).write_bytes(b"DIRTY-INDEX")

    plan, _ = W.plan_stage(repo, common, ["new.txt"])
    digest, failure = W.apply_stage(common, plan, on_locked=intruder)
    assert digest is None
    assert failure.code == W.CODE_BLOCKED
    assert "lock を無視した writer" in failure.reason


def test_postcondition_mismatch_is_reported(repo, common):
    plan, _ = W.plan_stage(repo, common, ["new.txt"])
    digest, _ = W.apply_stage(common, plan)
    _git(repo, "add", "other.txt")
    failure = W.verify_postcondition(common, digest)
    assert failure is not None
    assert failure.stage == "post-check"
    assert "quarantine" in failure.reason


# --- capability ---------------------------------------------------------------


def test_capability_is_satisfied_on_this_platform(common):
    assert W.capability(common) == []


def test_missing_common_dir_is_unsupported(repo, tmp_path):
    plan, failure = W.plan_stage(repo, tmp_path / "nowhere", ["new.txt"])
    assert plan is None
    assert failure.code == W.CODE_UNSUPPORTED
    assert failure.stage == "validate"


# --- read/write の分離 ---------------------------------------------------------


def test_write_module_reuses_read_conventions():
    """pager / color / external diff の無効化と環境変数は read adapter と共有する。"""
    from flowlib import git_read

    assert W.git_read.GIT_COMMON_FLAGS is git_read.GIT_COMMON_FLAGS
    assert W.git_read.GIT_ENV is git_read.GIT_ENV


def test_read_module_has_no_write_entry_points():
    from flowlib import git_read

    for name in ("apply_stage", "plan_stage", "stage"):
        assert not hasattr(git_read, name), f"read adapter に write が混ざっている: {name}"
