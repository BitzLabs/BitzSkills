"""commit_lint.py（flow-core 同梱スクリプト）の単体テスト。

Conventional Commits タイトル・作業 ID・Implements フッターの検査、
入力経路（--message / --file / stdin / --range）、終了コードを検証する。
"""
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = (
    REPO_ROOT / "plugins" / "bitz-flow" / "skills" / "flow-core" / "scripts" / "commit_lint.py"
)


def run(*args: str, stdin: str | None = None, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        input=stdin,
        cwd=str(cwd) if cwd else None,
    )


def git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)


def test_help_standalone():
    """--help がスキル読み込みなしで単体動作すること。"""
    res = run("--help")
    assert res.returncode == 0
    assert "Conventional" in res.stdout


@pytest.mark.parametrize(
    "title",
    [
        "feat: 説明",
        "fix(auth): 説明",
        "refactor!: 破壊的変更",
        "chore(scope)!: 破壊的",
        "feat(auth): [#123] 説明",
    ],
)
def test_conforming_titles_rc0(title: str):
    """適合タイトル（scope あり/なし・破壊的 !）は rc0 で OK を返すこと。"""
    res = run("--message", title)
    assert res.returncode == 0, res.stdout
    assert res.stdout.startswith("OK ")


@pytest.mark.parametrize(
    "title",
    [
        "wip: 語彙外の type",
        "feat 説明でコロン欠落",
        "説明だけ",
    ],
)
def test_nonconforming_titles_rc1(title: str):
    """type 語彙外・コロン欠落は rc1 で NG を返すこと。"""
    res = run("--message", title)
    assert res.returncode == 1
    assert "NG" in res.stdout


def test_require_task_id():
    """--require-task-id: 作業 ID の有無で結果が分かれること。"""
    without = run("--message", "feat: 説明", "--require-task-id")
    assert without.returncode == 1
    with_id = run("--message", "feat: [#123] 説明", "--require-task-id")
    assert with_id.returncode == 0


def test_require_implements():
    """--require-implements: Implements フッターの有無で結果が分かれること。"""
    without = run("--message", "feat: 説明", "--require-implements")
    assert without.returncode == 1
    with_footer = run(
        "--message", "feat: 説明\n\n本文\n\nImplements: CORE-FR-015", "--require-implements"
    )
    assert with_footer.returncode == 0


def test_file_stdin():
    """--file - で標準入力からメッセージを読めること。"""
    res = run("--file", "-", stdin="feat(core): stdin 経由の適合メッセージ")
    assert res.returncode == 0
    assert res.stdout.startswith("OK ")


def test_no_input_rc2():
    """入力指定が無ければ rc2（使用法エラー）。"""
    res = run()
    assert res.returncode == 2


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "proj"
    r.mkdir()
    subprocess.run(["git", "init", "-b", "main", str(r)], capture_output=True, text=True)
    git(r, "config", "user.name", "Tester")
    git(r, "config", "user.email", "tester@example.com")
    return r


def test_range_multiple_commits_mixed(repo: Path):
    """--range で複数コミットを検査し、違反混在で rc1・NG 行に sha が出ること。"""
    # 基点となる初期コミット（検査対象外）
    (repo / "base.txt").write_text("base\n", encoding="utf-8")
    git(repo, "add", "base.txt")
    git(repo, "commit", "-m", "chore: init")
    # 1件目: 適合
    (repo / "a.txt").write_text("a\n", encoding="utf-8")
    git(repo, "add", "a.txt")
    git(repo, "commit", "-m", "feat: 適合コミット")
    # 2件目: 違反（語彙外 type）
    (repo / "b.txt").write_text("b\n", encoding="utf-8")
    git(repo, "add", "b.txt")
    git(repo, "commit", "-m", "wip: 違反コミット")
    bad_sha = git(repo, "rev-parse", "HEAD").stdout.strip()[:7]

    res = run("--range", "HEAD~2..HEAD", cwd=repo)
    assert res.returncode == 1
    assert "NG" in res.stdout
    assert bad_sha in res.stdout


def test_range_zero_commits_rc0(repo: Path):
    """--range で対象コミットが0件なら OK 0 で rc0。"""
    (repo / "a.txt").write_text("a\n", encoding="utf-8")
    git(repo, "add", "a.txt")
    git(repo, "commit", "-m", "feat: 唯一のコミット")
    res = run("--range", "HEAD..HEAD", cwd=repo)
    assert res.returncode == 0
    assert res.stdout.strip() == "OK 0"


def test_read_only_no_history_rewrite():
    """ソースが履歴書き換え系 git（reset --hard / push --force）を呼ばないこと。"""
    src = SCRIPT.read_text(encoding="utf-8")
    for forbidden in ["reset --hard", "--force", "push origin"]:
        assert forbidden not in src, forbidden
