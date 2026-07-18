"""worktree_ops.py（flow-worktree 同梱スクリプト）の単体テスト。

dry-run 既定・確認フラグ（--yes）・禁止操作の不在・終了コード・実行時の実副作用を検証する。
git が要るテストは tmp_path に実リポジトリを作って検証する。
"""
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = (
    REPO_ROOT
    / "plugins"
    / "bitz-flow"
    / "skills"
    / "flow-worktree"
    / "scripts"
    / "worktree_ops.py"
)


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], capture_output=True, text=True
    )


def git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """tmp_path/proj に main ブランチと初期コミットを持つ実リポジトリを作る。"""
    r = tmp_path / "proj"
    r.mkdir()
    subprocess.run(["git", "init", "-b", "main", str(r)], capture_output=True, text=True)
    git(r, "config", "user.name", "Tester")
    git(r, "config", "user.email", "tester@example.com")
    (r / "README.md").write_text("hello\n", encoding="utf-8")
    git(r, "add", "README.md")
    git(r, "commit", "-m", "chore: init")
    return r


def branch_exists(repo: Path, name: str) -> bool:
    res = git(repo, "branch", "--list", name)
    return bool(res.stdout.strip())


def load_module():
    spec = importlib.util.spec_from_file_location("worktree_ops", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class FakeSquashRunner:
    """guarded cleanup の git / gh 応答を決定的に返す。"""

    def __init__(self, repo: Path, *, state="initial", pr_state="MERGED", remote_oid="headsha"):
        self.repo = repo
        self.state = state
        self.pr_state = pr_state
        self.remote_oid = remote_oid
        self.commands = []

    def __call__(self, command, *, timeout):
        self.commands.append(tuple(command))
        joined = " ".join(command)
        wt = self.repo.parent / f"{self.repo.name}-wt" / "500"
        if "worktree list --porcelain" in joined:
            if self.state == "initial":
                text = f"worktree {wt}\nHEAD headsha\nbranch refs/heads/feat/500-x\n\n"
            else:
                text = f"worktree {self.repo}\nHEAD defaultsha\nbranch refs/heads/main\n\n"
            return subprocess.CompletedProcess(command, 0, text, "")
        if "rev-parse --verify refs/heads/feat/500-x" in joined:
            if self.state == "local-cleaned":
                return subprocess.CompletedProcess(command, 128, "", "missing")
            return subprocess.CompletedProcess(command, 0, "headsha\n", "")
        if "branch --show-current" in joined:
            return subprocess.CompletedProcess(command, 0, "main\n", "")
        if "status --porcelain" in joined:
            return subprocess.CompletedProcess(command, 0, "", "")
        if command[:3] == ["gh", "pr", "view"]:
            payload = {
                "state": self.pr_state,
                "headRefName": "feat/500-x",
                "headRefOid": "headsha",
                "mergeCommit": {"oid": "mergesha"},
            }
            return subprocess.CompletedProcess(command, 0, json.dumps(payload), "")
        if "ls-remote --heads" in joined:
            text = f"{self.remote_oid}\trefs/heads/feat/500-x\n" if self.remote_oid else ""
            return subprocess.CompletedProcess(command, 0, text, "")
        return subprocess.CompletedProcess(command, 0, "", "")


def test_help_standalone():
    """--help がスキル読み込みなしで単体動作すること。"""
    res = run("--help")
    assert res.returncode == 0
    assert "worktree" in res.stdout


def test_add_dry_run_default_no_side_effects(repo: Path, tmp_path: Path):
    """add は既定 dry-run で worktree を作らず DRY-RUN 行だけ出すこと。"""
    res = run("add", "123", "--branch", "feat/123-x", "--base", "main", "--repo", str(repo))
    assert res.returncode == 0
    assert "DRY-RUN: git" in res.stdout
    assert not (tmp_path / "proj-wt" / "123").exists()
    assert not branch_exists(repo, "feat/123-x")


def test_cleanup_execute_without_yes_rc2_no_side_effects(repo: Path, tmp_path: Path):
    """cleanup を --execute で起動し --yes が無ければ rc2 で副作用ゼロ。"""
    # 事前に worktree を作っておき、消えていないことを確認する
    wt = tmp_path / "proj-wt" / "123"
    git(repo, "worktree", "add", str(wt), "-b", "feat/123-x", "main")
    res = run("cleanup", "123", "--branch", "feat/123-x", "--repo", str(repo), "--execute")
    assert res.returncode == 2
    assert wt.exists()
    assert branch_exists(repo, "feat/123-x")


def test_discard_execute_without_yes_rc2_no_side_effects(repo: Path, tmp_path: Path):
    """discard を --execute で起動し --yes が無ければ rc2 で副作用ゼロ。"""
    wt = tmp_path / "proj-wt" / "124"
    git(repo, "worktree", "add", str(wt), "-b", "feat/124-x", "main")
    res = run("discard", "124", "--branch", "feat/124-x", "--repo", str(repo), "--execute")
    assert res.returncode == 2
    assert wt.exists()
    assert branch_exists(repo, "feat/124-x")


def test_add_execute_creates_worktree_and_branch(repo: Path, tmp_path: Path):
    """add --execute（ローカル base main）で worktree とブランチが実際に作られること。"""
    res = run(
        "add", "200", "--branch", "feat/200-x", "--base", "main", "--repo", str(repo), "--execute"
    )
    assert res.returncode == 0, res.stderr
    assert (tmp_path / "proj-wt" / "200").is_dir()
    assert branch_exists(repo, "feat/200-x")


def test_discard_execute_yes_removes_unmerged(repo: Path, tmp_path: Path):
    """discard --execute --yes で未マージのブランチごと破棄できること。"""
    wt = tmp_path / "proj-wt" / "300"
    git(repo, "worktree", "add", str(wt), "-b", "feat/300-x", "main")
    # worktree 内で未マージのコミットを作る
    (wt / "work.txt").write_text("wip\n", encoding="utf-8")
    git(wt, "add", "work.txt")
    git(wt, "commit", "-m", "chore: wip")
    res = run(
        "discard", "300", "--branch", "feat/300-x", "--repo", str(repo), "--execute", "--yes"
    )
    assert res.returncode == 0, res.stderr
    assert not wt.exists()
    assert not branch_exists(repo, "feat/300-x")


def test_cleanup_execute_yes_removes_merged(repo: Path, tmp_path: Path):
    """cleanup --execute --yes（マージ済みブランチ）で worktree とブランチが消えること。"""
    wt = tmp_path / "proj-wt" / "400"
    git(repo, "worktree", "add", str(wt), "-b", "feat/400-x", "main")
    (wt / "f.txt").write_text("done\n", encoding="utf-8")
    git(wt, "add", "f.txt")
    git(wt, "commit", "-m", "feat: done")
    # main へマージ（-d が成功する状態にする）
    git(repo, "merge", "feat/400-x")
    res = run(
        "cleanup", "400", "--branch", "feat/400-x", "--repo", str(repo), "--execute", "--yes"
    )
    assert res.returncode == 0, res.stderr
    assert not wt.exists()
    assert not branch_exists(repo, "feat/400-x")


def test_flw_fr_001_squash_cleanup_requires_merged_evidence(repo: Path):
    module = load_module()
    runner = FakeSquashRunner(repo, pr_state="OPEN")
    code, report = module.guarded_squash_cleanup(
        repo=repo,
        work_id="500",
        branch="feat/500-x",
        pr_number=56,
        default_branch="main",
        timeout_seconds=30,
        actor="test",
        runner=runner,
    )
    assert code == module.EXIT_INDETERMINATE
    assert report["decision"] == "INDETERMINATE"
    assert not any("worktree remove" in " ".join(cmd) for cmd in runner.commands)
    assert not any("branch -D" in " ".join(cmd) for cmd in runner.commands)


def test_flw_fr_001_squash_cleanup_initial_and_remote_candidate(repo: Path):
    module = load_module()
    runner = FakeSquashRunner(repo)
    code, report = module.guarded_squash_cleanup(
        repo=repo,
        work_id="500",
        branch="feat/500-x",
        pr_number=56,
        default_branch="main",
        timeout_seconds=30,
        actor="test",
        runner=runner,
    )
    joined = [" ".join(cmd) for cmd in runner.commands]
    assert code == 0
    assert report["cleanup_state"] == "initial"
    assert report["remote_candidate"]["expected_sha"] == "headsha"
    assert any("worktree remove" in cmd for cmd in joined)
    assert any("branch -D" in cmd for cmd in joined)
    assert not any(" push " in f" {cmd} " for cmd in joined)
    assert "再照会" in report["remote_candidate"]["warning"]


@pytest.mark.parametrize(
    ("state", "expected_skips"),
    [
        ("cleanup-partial", ["worktree-remove", "remote-candidate"]),
        ("local-cleaned", ["worktree-remove", "local-branch-delete", "remote-candidate"]),
    ],
)
def test_flw_fr_001_squash_cleanup_idempotent_resume(repo: Path, state: str, expected_skips: list[str]):
    module = load_module()
    runner = FakeSquashRunner(repo, state=state, remote_oid="")
    code, report = module.guarded_squash_cleanup(
        repo=repo,
        work_id="500",
        branch="feat/500-x",
        pr_number=56,
        default_branch="main",
        timeout_seconds=30,
        actor=None,
        runner=runner,
    )
    assert code == 0
    assert report["cleanup_state"] == state
    assert report["skipped"] == expected_skips
    assert report["remote_status"] == "absent"


def test_flw_fr_001_squash_cleanup_preserves_advanced_remote(repo: Path):
    module = load_module()
    runner = FakeSquashRunner(repo, remote_oid="newsha")
    code, report = module.guarded_squash_cleanup(
        repo=repo,
        work_id="500",
        branch="feat/500-x",
        pr_number=56,
        default_branch="main",
        timeout_seconds=30,
        actor=None,
        runner=runner,
    )
    assert code == module.EXIT_INDETERMINATE
    assert report["failed_check"] == "remote-head-sha"
    assert not any("worktree remove" in " ".join(cmd) for cmd in runner.commands)


def test_flw_fr_001_squash_cleanup_rejects_path_escape(repo: Path):
    module = load_module()
    runner = FakeSquashRunner(repo)
    code, report = module.guarded_squash_cleanup(
        repo=repo,
        work_id="../escape",
        branch="feat/500-x",
        pr_number=56,
        default_branch="main",
        timeout_seconds=30,
        actor=None,
        runner=runner,
    )
    assert code == module.EXIT_INDETERMINATE
    assert report["failed_check"] == "work-id"
    assert runner.commands == []


def test_no_forbidden_operations_in_source():
    """ソースにガードレール禁止操作が含まれず、push と force が結合しないこと。"""
    src = SCRIPT.read_text(encoding="utf-8")
    for forbidden in ["reset --hard", "git clean", "rm -rf", "sudo"]:
        assert forbidden not in src, forbidden
    # push と強制フラグが同一行に同居しないこと
    assert not re.search(r"push[^\n]*--force", src)
    assert not re.search(r"push[^\n]*(?<!\w)-f(?!\w)", src)
    assert not re.search(r"--force[^\n]*push", src)
