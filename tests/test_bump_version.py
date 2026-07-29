import json
import subprocess
import sys
from pathlib import Path

# プロジェクトルートにある元のスクリプト
BUMP_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "bump_version.py"


def test_bump_versions(make_repo, copy_script):
    """patch/minor/major と、種別省略時（デフォルト patch）の正常系挙動を検証"""
    repo = make_repo()
    script = copy_script(repo, BUMP_SCRIPT)
    cc_json_path = repo / "plugins/demo/.claude-plugin/plugin.json"
    agy_json_path = repo / "plugins/demo/plugin.json"
    codex_json_path = repo / "plugins/demo/.codex-plugin/plugin.json"
    
    # default (patch): 0.1.0 -> 0.1.1
    res = subprocess.run([sys.executable, str(script), "demo"], capture_output=True, text=True)
    assert res.returncode == 0
    
    assert json.loads(cc_json_path.read_text(encoding="utf-8"))["version"] == "0.1.1"
    assert json.loads(agy_json_path.read_text(encoding="utf-8"))["version"] == "0.1.1"
    assert json.loads(codex_json_path.read_text(encoding="utf-8"))["version"] == "0.1.1"

    # minor: 0.1.1 -> 0.2.0
    res = subprocess.run([sys.executable, str(script), "demo", "minor"], capture_output=True, text=True)
    assert res.returncode == 0
    assert json.loads(cc_json_path.read_text(encoding="utf-8"))["version"] == "0.2.0"
    assert json.loads(codex_json_path.read_text(encoding="utf-8"))["version"] == "0.2.0"
    
    # major: 0.2.0 -> 1.0.0
    res = subprocess.run([sys.executable, str(script), "demo", "major"], capture_output=True, text=True)
    assert res.returncode == 0
    assert json.loads(cc_json_path.read_text(encoding="utf-8"))["version"] == "1.0.0"
    assert json.loads(codex_json_path.read_text(encoding="utf-8"))["version"] == "1.0.0"


def test_bump_mismatched_versions(make_repo, copy_script):
    """3マニフェストが不一致の場合、大きい方を基準にして bump されることを検証"""
    repo = make_repo()
    script = copy_script(repo, BUMP_SCRIPT)
    
    cc_file = repo / "plugins/demo/.claude-plugin/plugin.json"
    agy_file = repo / "plugins/demo/plugin.json"
    codex_file = repo / "plugins/demo/.codex-plugin/plugin.json"
    
    cc_file.write_text('{"name":"demo","version":"0.1.0"}', encoding="utf-8")
    agy_file.write_text('{"name":"demo","version":"0.2.0"}', encoding="utf-8")
    codex_file.write_text('{"name":"demo","version":"0.1.5"}', encoding="utf-8")
    
    res = subprocess.run([sys.executable, str(script), "demo", "patch"], capture_output=True, text=True)
    assert res.returncode == 0
    assert "警告" in res.stdout
    
    cc_json = json.loads(cc_file.read_text(encoding="utf-8"))
    agy_json = json.loads(agy_file.read_text(encoding="utf-8"))
    codex_json = json.loads(codex_file.read_text(encoding="utf-8"))
    
    # 大きい方 0.2.0 が基準になり、3つが 0.2.1 に揃う
    assert cc_json["version"] == "0.2.1"
    assert agy_json["version"] == "0.2.1"
    assert codex_json["version"] == "0.2.1"


def test_bump_missing_manifest(make_repo, copy_script):
    """マニフェストが1つ欠落していると失敗し、残ったファイルが無変更であることを検証"""
    repo = make_repo()
    script = copy_script(repo, BUMP_SCRIPT)
    
    agy_file = repo / "plugins/demo/plugin.json"
    content_before = agy_file.read_text(encoding="utf-8")
    
    # Codex マニフェストを削除
    (repo / "plugins/demo/.codex-plugin/plugin.json").unlink()
    
    res = subprocess.run([sys.executable, str(script), "demo"], capture_output=True, text=True)
    assert res.returncode != 0
    
    # 残った方は無変更
    assert agy_file.read_text(encoding="utf-8") == content_before


def test_bump_invalid_part(make_repo, copy_script):
    """不正な bump 種別を指定すると失敗すること"""
    repo = make_repo()
    script = copy_script(repo, BUMP_SCRIPT)
    
    res = subprocess.run([sys.executable, str(script), "demo", "huge"], capture_output=True, text=True)
    assert res.returncode != 0


def test_bump_invalid_semver(make_repo, copy_script):
    """不正な semver が記載されていると失敗し、ファイルが無変更であることを検証"""
    repo = make_repo()
    script = copy_script(repo, BUMP_SCRIPT)
    
    cc_file = repo / "plugins/demo/.claude-plugin/plugin.json"
    agy_file = repo / "plugins/demo/plugin.json"
    codex_file = repo / "plugins/demo/.codex-plugin/plugin.json"
    
    content = '{"name":"demo","version":"abc"}'
    cc_file.write_text(content, encoding="utf-8")
    agy_file.write_text(content, encoding="utf-8")
    codex_file.write_text(content, encoding="utf-8")
    
    res = subprocess.run([sys.executable, str(script), "demo"], capture_output=True, text=True)
    assert res.returncode != 0
    
    # 3つとも無変更
    assert cc_file.read_text(encoding="utf-8") == content
    assert agy_file.read_text(encoding="utf-8") == content
    assert codex_file.read_text(encoding="utf-8") == content


# ---- CORE-FR-018: 副作用を持つ運用スクリプトの引数契約 ----------------------


def _versions(repo: Path) -> set[str]:
    return {
        json.loads((repo / "plugins/demo" / rel).read_text(encoding="utf-8"))["version"]
        for rel in (".claude-plugin/plugin.json", "plugin.json", ".codex-plugin/plugin.json")
    }


def test_bump_unknown_argument_is_rejected_without_mutating(make_repo, copy_script):
    """未知引数は拒否し、マニフェストを一切書き換えない"""
    repo = make_repo()
    script = copy_script(repo, BUMP_SCRIPT)

    res = subprocess.run(
        [sys.executable, str(script), "demo", "minor", "--bogus-flag"],
        capture_output=True, text=True,
    )

    assert res.returncode != 0
    assert "unrecognized arguments" in res.stderr
    assert _versions(repo) == {"0.1.0"}


def test_bump_help_after_positional_args_does_not_bump(make_repo, copy_script):
    """--help は引数位置に関わらず効き、bump を実行しない（SI-CORE-036 の事故形状）"""
    repo = make_repo()
    script = copy_script(repo, BUMP_SCRIPT)

    res = subprocess.run(
        [sys.executable, str(script), "demo", "minor", "--help"],
        capture_output=True, text=True,
    )

    assert res.returncode == 0
    assert "usage:" in res.stdout
    assert _versions(repo) == {"0.1.0"}


def test_bump_short_help_does_not_bump(make_repo, copy_script):
    repo = make_repo()
    script = copy_script(repo, BUMP_SCRIPT)

    res = subprocess.run(
        [sys.executable, str(script), "demo", "-h"], capture_output=True, text=True
    )

    assert res.returncode == 0
    assert _versions(repo) == {"0.1.0"}


def test_bump_dry_run_reports_without_writing(make_repo, copy_script):
    """--dry-run は新旧 version を出すだけで3マニフェストを書き換えない"""
    repo = make_repo()
    script = copy_script(repo, BUMP_SCRIPT)

    res = subprocess.run(
        [sys.executable, str(script), "demo", "minor", "--dry-run"],
        capture_output=True, text=True,
    )

    assert res.returncode == 0, res.stderr
    assert "0.1.0 -> 0.2.0" in res.stdout
    assert "書き換えは行っていません" in res.stdout
    assert _versions(repo) == {"0.1.0"}
