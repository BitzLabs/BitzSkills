"""CORE-CON-011: CLI スクリプトの未知引数拒否。

リポジトリ内の CLI スクリプトを実行時に収集し、解釈できない引数を渡したときに
処理を続行せず非ゼロ終了することを検証する。新しいスクリプトを追加すると、
明示的な除外宣言がない限り自動的に本テストの対象へ入る。
"""
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent

# 収集対象（リポジトリが提供する CLI スクリプトの置き場）
GLOBS = (
    "scripts/*.py",
    "plugins/*/scripts/*.py",
    "plugins/*/skills/*/scripts/*.py",
)

# 本規約の対象外（除外理由は CORE-CON-011 の説明を参照）
EXCLUDED = {
    # stdin JSON 駆動の hook。CLI 引数契約を持たず、起動形はプラットフォームが決める。
    # 厳格化するとプラットフォーム側の仕様変更でガードレールフックが機能停止する
    "scripts/agy_guard.py",
    "plugins/bitz-env/scripts/env_guard.py",
}

UNKNOWN_ARG = "--bitzskills-unknown-flag"


def is_cli_script(path: Path) -> bool:
    """`__main__` を持たないライブラリは CLI ではないため対象外"""
    return "__main__" in path.read_text(encoding="utf-8")


def collect_cli_scripts() -> list[Path]:
    found = []
    for pattern in GLOBS:
        for path in sorted(REPO.glob(pattern)):
            rel = path.relative_to(REPO).as_posix()
            if rel in EXCLUDED or not is_cli_script(path):
                continue
            found.append(path)
    return found


CLI_SCRIPTS = collect_cli_scripts()
CLI_IDS = [p.relative_to(REPO).as_posix() for p in CLI_SCRIPTS]


def run_script(script: Path, *args: str, cwd: Path):
    """一時ディレクトリを作業ディレクトリにして起動する。

    契約違反のスクリプトが処理を続行してしまっても、副作用を一時ディレクトリ内へ閉じ込める。
    """
    return subprocess.run(
        [sys.executable, str(script), *args],
        capture_output=True,
        text=True,
        cwd=str(cwd),
        timeout=60,
    )


def test_cli_scripts_are_collected():
    """収集漏れで対象ゼロになり、素通りで green になることを防ぐ"""
    assert len(CLI_SCRIPTS) >= 10, CLI_IDS


@pytest.mark.parametrize("script", CLI_SCRIPTS, ids=CLI_IDS)
def test_unknown_argument_is_rejected(script: Path, tmp_path: Path):
    """解釈できない引数を渡したら処理を続行せず非ゼロ終了する"""
    result = run_script(script, UNKNOWN_ARG, cwd=tmp_path)
    assert result.returncode != 0, (
        f"{script.relative_to(REPO)} が未知引数を黙認した:\n{result.stdout}\n{result.stderr}"
    )


@pytest.mark.parametrize("script", CLI_SCRIPTS, ids=CLI_IDS)
def test_help_flag_is_honored(script: Path, tmp_path: Path):
    """--help は引数位置に関わらず効き、使用方法を出力して正常終了する"""
    result = run_script(script, "--help", cwd=tmp_path)
    assert result.returncode == 0, (
        f"{script.relative_to(REPO)} の --help が失敗した:\n{result.stdout}\n{result.stderr}"
    )
    assert "usage" in (result.stdout + result.stderr).lower()


def test_excluded_scripts_still_exist():
    """除外宣言が実体から乖離していないこと（削除・移動の検出）"""
    for rel in EXCLUDED:
        assert (REPO / rel).exists(), f"除外リストの {rel} が存在しない"
