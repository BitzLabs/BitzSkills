import json
import os
import subprocess
import sys
from pathlib import Path

# プロジェクトルートにある元のスクリプト
CHECK_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "release_check.py"


def run_check(script_path: Path):
    """CLIの検出を避けるため最小限の PATH でスクリプトを実行する"""
    env = os.environ.copy()
    env["PATH"] = str(Path(sys.executable).parent)
    return subprocess.run(
        [sys.executable, str(script_path)],
        capture_output=True,
        text=True,
        env=env
    )


def test_release_check_pass(make_repo, copy_script):
    """正常な fixture の場合、exit 0 になり PASS が出力されること"""
    repo = make_repo()
    script = copy_script(repo, CHECK_SCRIPT)
    
    res = run_check(script)
    assert res.returncode == 0
    assert "PASS" in res.stdout


def test_release_check_mismatched_versions(make_repo, copy_script):
    """2マニフェストの version 不一致の場合、exit 1 になり該当 FAIL 行が出ること"""
    repo = make_repo()
    script = copy_script(repo, CHECK_SCRIPT)
    
    agy_file = repo / "plugins/demo/plugin.json"
    agy_file.write_text('{"name":"demo","version":"0.2.0"}', encoding="utf-8")
    
    res = run_check(script)
    assert res.returncode == 1
    assert "FAIL" in res.stdout
    assert "version 一致" in res.stdout


def test_release_check_ghost_plugin(make_repo, copy_script):
    """marketplace.json に実体のないプラグイン参照がある場合、exit 1 になること"""
    repo = make_repo()
    script = copy_script(repo, CHECK_SCRIPT)
    
    marketplace = repo / ".claude-plugin/marketplace.json"
    mp_data = json.loads(marketplace.read_text(encoding="utf-8"))
    mp_data["plugins"].append({"name": "ghost", "source": "./plugins/ghost"})
    marketplace.write_text(json.dumps(mp_data), encoding="utf-8")
    
    res = run_check(script)
    assert res.returncode == 1
    assert "実体なし" in res.stdout


def test_release_check_unlisted_plugin(make_repo, copy_script):
    """marketplace.json に未列挙のプラグイン実体がある場合、exit 1 になること"""
    repo = make_repo()
    script = copy_script(repo, CHECK_SCRIPT)
    
    # marketplace.json に記載されていない実体ディレクトリを作る
    ghost_dir = repo / "plugins/ghost/.claude-plugin"
    ghost_dir.mkdir(parents=True)
    
    res = run_check(script)
    assert res.returncode == 1
    assert "未列挙" in res.stdout


def test_release_check_missing_metadata(make_repo, copy_script):
    """SKILL.md の metadata 欠落（updated を消す等）で exit 1 になること"""
    repo = make_repo()
    script = copy_script(repo, CHECK_SCRIPT)
    
    skill_md = repo / "plugins/demo/skills/demo-skill/SKILL.md"
    content = skill_md.read_text(encoding="utf-8")
    # updated を消去
    content = content.replace("  updated: 2026-01-01\n", "")
    skill_md.write_text(content, encoding="utf-8")
    
    res = run_check(script)
    assert res.returncode == 1
    assert "updated" in res.stdout


def test_release_check_missing_frontmatter(make_repo, copy_script):
    """SKILL.md に frontmatter 自体がない場合、exit 1 になること"""
    repo = make_repo()
    script = copy_script(repo, CHECK_SCRIPT)
    
    skill_md = repo / "plugins/demo/skills/demo-skill/SKILL.md"
    skill_md.write_text("# Demo Skill\nNo frontmatter here.", encoding="utf-8")
    
    res = run_check(script)
    assert res.returncode == 1
    assert "欠落" in res.stdout
