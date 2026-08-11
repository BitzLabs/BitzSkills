"""M1 で追加する Git read（FLW-FR-004）を実 Git リポジトリで検証する。

確認したいこと: 非 ASCII / 改行を含む path・binary・rename・conflict・detached HEAD・
空リポジトリで壊れないこと、`diff-detail` の上限超過を黙って切らないこと、副作用が 0 であること。
"""

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / "plugins" / "bitz-flow" / "skills" / "flow-core"
sys.path.insert(0, str(SKILL / "scripts"))

from flowlib import git_read_ext as X  # noqa: E402


def _git(repo: Path, *args: str, check=True):
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=check
    )


@pytest.fixture
def repo(tmp_path):
    path = tmp_path / "repo"
    path.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(path)], check=True)
    _git(path, "config", "user.email", "t@example.com")
    _git(path, "config", "user.name", "t")
    (path / "a.txt").write_text("line1\nline2\nline3\n", encoding="utf-8")
    (path / "日本語 ファイル.txt").write_text("あ\n", encoding="utf-8")
    (path / "bin.dat").write_bytes(bytes(range(256)))
    _git(path, "add", "-A")
    _git(path, "commit", "-qm", "chore: init")
    (path / "a.txt").write_text("line1\nCHANGED\nline3\n", encoding="utf-8")
    return path


@pytest.fixture
def empty_repo(tmp_path):
    path = tmp_path / "empty"
    path.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(path)], check=True)
    _git(path, "config", "user.email", "t@example.com")
    _git(path, "config", "user.name", "t")
    return path


def _head(repo: Path) -> str:
    return _git(repo, "rev-parse", "HEAD", check=False).stdout.strip()


# --- diff-detail --------------------------------------------------------------


def test_diff_detail_returns_changed_lines(repo):
    detail, failure = X.diff_detail(repo, ["a.txt"])
    assert failure is None
    body = "\n".join(l for h in detail.hunks for l in h["lines"])
    assert "+CHANGED" in body
    assert detail.total_hunks >= 1


def test_diff_detail_requires_explicit_paths(repo):
    detail, failure = X.diff_detail(repo, [])
    assert detail is None and failure.cause == "invalid-path"


def test_diff_detail_discloses_truncation(repo):
    """上限超過を黙って切らない。"""
    big = "\n".join(f"line{i}" for i in range(500))
    (repo / "big.txt").write_text(big, encoding="utf-8")
    _git(repo, "add", "big.txt")
    _git(repo, "commit", "-qm", "chore: big")
    (repo / "big.txt").write_text(big.replace("line10", "CHANGED10").replace("line400", "CHANGED400"), encoding="utf-8")

    detail, failure = X.diff_detail(repo, ["big.txt"], max_bytes=80, max_hunks=1)
    assert failure is None
    assert detail.truncated is True
    assert detail.shown_hunks <= 1
    assert detail.total_hunks >= detail.shown_hunks
    assert detail.total_bytes > 0


def test_diff_detail_within_limits_is_not_truncated(repo):
    detail, _ = X.diff_detail(repo, ["a.txt"], max_bytes=1_000_000, max_hunks=1000)
    assert detail.truncated is False
    assert detail.shown_hunks == detail.total_hunks


def test_diff_detail_snapshot_changes_with_content(repo):
    first, _ = X.diff_detail(repo, ["a.txt"])
    (repo / "a.txt").write_text("line1\nCHANGED\nMORE\n", encoding="utf-8")
    second, _ = X.diff_detail(repo, ["a.txt"])
    assert first.snapshot != second.snapshot


def test_diff_detail_handles_non_ascii_path(repo):
    (repo / "日本語 ファイル.txt").write_text("い\n", encoding="utf-8")
    detail, failure = X.diff_detail(repo, ["日本語 ファイル.txt"])
    assert failure is None and detail.total_hunks >= 1


def test_diff_detail_handles_binary(repo):
    (repo / "bin.dat").write_bytes(bytes(range(255, -1, -1)))
    detail, failure = X.diff_detail(repo, ["bin.dat"])
    assert failure is None, "binary でも失敗しない"


def test_diff_detail_has_no_side_effect(repo):
    before = _head(repo)
    X.diff_detail(repo, ["a.txt"])
    assert _head(repo) == before


# --- log ----------------------------------------------------------------------


def test_log_returns_entries(repo):
    entries, failure = X.log(repo)
    assert failure is None and entries
    first = entries[0]
    assert set(first) == {"sha", "short_sha", "subject", "author_date", "parents"}
    assert first["subject"] == "chore: init"
    assert first["sha"].startswith(first["short_sha"])


def test_log_respects_limit(repo):
    for i in range(3):
        (repo / f"f{i}.txt").write_text(f"{i}\n", encoding="utf-8")
        _git(repo, "add", f"f{i}.txt")
        _git(repo, "commit", "-qm", f"chore: c{i}")
    entries, _ = X.log(repo, limit=2)
    assert len(entries) == 2


def test_log_records_parents(repo):
    (repo / "n.txt").write_text("n\n", encoding="utf-8")
    _git(repo, "add", "n.txt")
    _git(repo, "commit", "-qm", "chore: second")
    entries, _ = X.log(repo)
    assert entries[0]["parents"], "親を持つ commit で parents が空になってはならない"


def test_log_on_empty_repo_fails_with_vocabulary_cause(empty_repo):
    entries, failure = X.log(empty_repo)
    assert entries is None
    assert failure.cause in ("invalid-ref", "not-repository")


def test_log_subject_with_non_ascii(repo):
    (repo / "x.txt").write_text("x\n", encoding="utf-8")
    _git(repo, "add", "x.txt")
    _git(repo, "commit", "-qm", "feat: 日本語の件名")
    entries, _ = X.log(repo)
    assert entries[0]["subject"] == "feat: 日本語の件名"


# --- branches -----------------------------------------------------------------


def test_branches_lists_local(repo):
    entries, failure = X.branches(repo)
    assert failure is None
    local = [e for e in entries if e["scope"] == "local"]
    assert any(e["ref"] == "refs/heads/main" for e in local)
    assert all(set(e) == {"ref", "scope", "sha", "upstream", "ahead", "behind"} for e in entries)


def test_branches_reports_upstream_and_track(tmp_path, repo):
    bare = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True)
    _git(repo, "remote", "add", "origin", str(bare))
    _git(repo, "push", "-q", "-u", "origin", "main")
    (repo / "ahead.txt").write_text("a\n", encoding="utf-8")
    _git(repo, "add", "ahead.txt")
    _git(repo, "commit", "-qm", "chore: ahead")

    entries, _ = X.branches(repo)
    main = next(e for e in entries if e["ref"] == "refs/heads/main")
    assert main["upstream"] == "origin/main"
    assert main["ahead"] == 1 and main["behind"] == 0


def test_branches_on_detached_head(repo):
    _git(repo, "checkout", "-q", "--detach")
    entries, failure = X.branches(repo)
    assert failure is None and entries


# --- conflicts ----------------------------------------------------------------


def test_conflicts_empty_when_clean(repo):
    paths, failure = X.conflicts(repo)
    assert failure is None and paths == []


def test_conflicts_lists_unmerged_paths(repo):
    _git(repo, "checkout", "-q", "-b", "side")
    (repo / "a.txt").write_text("SIDE\n", encoding="utf-8")
    _git(repo, "commit", "-qam", "chore: side")
    _git(repo, "checkout", "-q", "main")
    (repo / "a.txt").write_text("MAIN\n", encoding="utf-8")
    _git(repo, "commit", "-qam", "chore: main")
    _git(repo, "merge", "side", check=False)

    paths, failure = X.conflicts(repo)
    assert failure is None
    assert "a.txt" in paths


# --- worktree list ------------------------------------------------------------


def test_worktree_list_returns_main(repo):
    entries, failure = X.worktree_list(repo)
    assert failure is None and entries
    assert Path(entries[0]["path"]).name == repo.name
    assert entries[0]["branch"] == "refs/heads/main"


def test_worktree_list_includes_linked(repo, tmp_path):
    linked = tmp_path / "wt-linked"
    _git(repo, "worktree", "add", "-q", "-b", "wt", str(linked))
    entries, _ = X.worktree_list(repo)
    assert len(entries) == 2
    assert any(e["branch"] == "refs/heads/wt" for e in entries)


def test_worktree_list_marks_detached(repo, tmp_path):
    linked = tmp_path / "wt-detached"
    _git(repo, "worktree", "add", "-q", "--detach", str(linked))
    entries, _ = X.worktree_list(repo)
    detached = [e for e in entries if e["branch"] is None]
    assert detached and detached[0]["head"]


# --- 共通規律 ------------------------------------------------------------------


def test_all_readers_have_no_side_effect(repo):
    before = _head(repo)
    X.log(repo)
    X.branches(repo)
    X.conflicts(repo)
    X.worktree_list(repo)
    assert _head(repo) == before


def test_failures_use_allowed_vocabulary(tmp_path):
    not_a_repo = tmp_path / "plain"
    not_a_repo.mkdir()
    for call in (
        lambda: X.log(not_a_repo),
        lambda: X.branches(not_a_repo),
        lambda: X.conflicts(not_a_repo),
        lambda: X.worktree_list(not_a_repo),
    ):
        value, failure = call()
        assert value is None
        assert failure.cause in (
            "not-repository", "invalid-ref", "invalid-path", "permission-denied",
            "command-unavailable", "timeout",
        )


def test_module_shares_read_conventions():
    assert X.git_read.GIT_COMMON_FLAGS is not None
    assert "--no-pager" in X.git_read.GIT_COMMON_FLAGS
    assert X.git_read.GIT_ENV["GIT_TERMINAL_PROMPT"] == "0"
