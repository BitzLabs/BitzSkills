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
    
    # default (patch): 0.1.0 -> 0.1.1
    res = subprocess.run([sys.executable, str(script), "demo"], capture_output=True, text=True)
    assert res.returncode == 0
    
    assert json.loads(cc_json_path.read_text(encoding="utf-8"))["version"] == "0.1.1"
    assert json.loads(agy_json_path.read_text(encoding="utf-8"))["version"] == "0.1.1"

    # minor: 0.1.1 -> 0.2.0
    res = subprocess.run([sys.executable, str(script), "demo", "minor"], capture_output=True, text=True)
    assert res.returncode == 0
    assert json.loads(cc_json_path.read_text(encoding="utf-8"))["version"] == "0.2.0"
    
    # major: 0.2.0 -> 1.0.0
    res = subprocess.run([sys.executable, str(script), "demo", "major"], capture_output=True, text=True)
    assert res.returncode == 0
    assert json.loads(cc_json_path.read_text(encoding="utf-8"))["version"] == "1.0.0"


def test_bump_mismatched_versions(make_repo, copy_script):
    """2マニフェストが不一致の場合、大きい方を基準にして bump されることを検証"""
    repo = make_repo()
    script = copy_script(repo, BUMP_SCRIPT)
    
    cc_file = repo / "plugins/demo/.claude-plugin/plugin.json"
    agy_file = repo / "plugins/demo/plugin.json"
    
    cc_file.write_text('{"name":"demo","version":"0.1.0"}', encoding="utf-8")
    agy_file.write_text('{"name":"demo","version":"0.2.0"}', encoding="utf-8")
    
    res = subprocess.run([sys.executable, str(script), "demo", "patch"], capture_output=True, text=True)
    assert res.returncode == 0
    assert "警告" in res.stdout
    
    cc_json = json.loads(cc_file.read_text(encoding="utf-8"))
    agy_json = json.loads(agy_file.read_text(encoding="utf-8"))
    
    # 大きい方 0.2.0 が基準になり、両方が 0.2.1 に揃う
    assert cc_json["version"] == "0.2.1"
    assert agy_json["version"] == "0.2.1"


def test_bump_missing_manifest(make_repo, copy_script):
    """マニフェストが片方欠落していると失敗し、残ったファイルが無変更であることを検証"""
    repo = make_repo()
    script = copy_script(repo, BUMP_SCRIPT)
    
    agy_file = repo / "plugins/demo/plugin.json"
    content_before = agy_file.read_text(encoding="utf-8")
    
    # 片方を削除
    (repo / "plugins/demo/.claude-plugin/plugin.json").unlink()
    
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
    
    content = '{"name":"demo","version":"abc"}'
    cc_file.write_text(content, encoding="utf-8")
    agy_file.write_text(content, encoding="utf-8")
    
    res = subprocess.run([sys.executable, str(script), "demo"], capture_output=True, text=True)
    assert res.returncode != 0
    
    # どちらも無変更
    assert cc_file.read_text(encoding="utf-8") == content
    assert agy_file.read_text(encoding="utf-8") == content
