"""pr_helper.py（flow-pr 同梱スクリプト）の単体テスト。

3節（目的 / 変更点 / 検証結果）の生成、箇条書き、Closes / Implements 行、
未指定節の TODO、--output 書き出し、外部コマンド非使用を検証する。
"""
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = (
    REPO_ROOT / "plugins" / "bitz-flow" / "skills" / "flow-pr" / "scripts" / "pr_helper.py"
)


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], capture_output=True, text=True
    )


def test_help_standalone():
    """--help がスキル読み込みなしで単体動作すること。"""
    res = run("--help")
    assert res.returncode == 0
    assert "PR" in res.stdout


def test_three_sections_present():
    """目的 / 変更点 / 検証結果 の3節が必ず出ること。"""
    res = run("--purpose", "認証を実装する")
    assert res.returncode == 0
    assert "## 目的" in res.stdout
    assert "## 変更点" in res.stdout
    assert "## 検証結果" in res.stdout
    assert "認証を実装する" in res.stdout


def test_multiple_changes_and_verifications_as_bullets():
    """--change / --verification の複数指定が箇条書きになること。"""
    res = run(
        "--change", "トークン更新を追加",
        "--change", "失効処理を追加",
        "--verification", "pytest green",
        "--verification", "release_check PASS",
    )
    assert res.returncode == 0
    assert "- トークン更新を追加" in res.stdout
    assert "- 失効処理を追加" in res.stdout
    assert "- pytest green" in res.stdout
    assert "- release_check PASS" in res.stdout


def test_closes_and_implements_lines():
    """Closes / Implements 行が指定時のみ出ること。"""
    res = run("--closes", "123", "--implements", "CORE-FR-015", "--implements", "CORE-FR-016")
    assert res.returncode == 0
    assert "Closes #123" in res.stdout
    assert "Implements: CORE-FR-015, CORE-FR-016" in res.stdout


def test_no_footer_when_unspecified():
    """Closes / Implements を指定しなければフッター行が出ないこと。"""
    res = run("--purpose", "x")
    assert "Closes" not in res.stdout
    assert "Implements:" not in res.stdout


def test_todo_placeholder_for_unspecified_sections():
    """未指定の節には TODO プレースホルダが出ること。"""
    res = run()
    assert res.returncode == 0
    # 3節すべて未指定なので TODO が複数現れる
    assert res.stdout.count("TODO") >= 3


def test_title_comment():
    """--title 指定時に suggested title がコメントとして冒頭に出ること。"""
    res = run("--title", "feat(auth): 実装")
    assert res.returncode == 0
    assert "suggested title: feat(auth): 実装" in res.stdout


def test_output_to_file(tmp_path: Path):
    """--output でファイルに書き出せること。"""
    out = tmp_path / "PR.md"
    res = run("--purpose", "目的テキスト", "--output", str(out))
    assert res.returncode == 0
    content = out.read_text(encoding="utf-8")
    assert "## 目的" in content
    assert "目的テキスト" in content


def test_source_has_no_external_command_execution():
    """ソースが外部コマンド実行モジュールを含まないこと（生成専用の担保）。"""
    src = SCRIPT.read_text(encoding="utf-8")
    assert "subprocess" not in src
    assert "os.system" not in src
