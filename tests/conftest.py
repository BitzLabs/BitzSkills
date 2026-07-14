import shutil
from pathlib import Path

import pytest

@pytest.fixture
def make_repo(tmp_path: Path):
    """bump_version.py / release_check.py 用の最小構成リポジトリを tmp_path に構築する"""
    def _make_repo():
        # tmp_repo/scripts
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        
        # .claude-plugin/marketplace.json
        cc_dir = tmp_path / ".claude-plugin"
        cc_dir.mkdir()
        marketplace = cc_dir / "marketplace.json"
        marketplace.write_text(
            '{"name":"test","plugins":[{"name":"demo","source":"./plugins/demo"}]}', 
            encoding="utf-8"
        )
        
        # plugins/demo の Claude Code / Antigravity / Codex 向けマニフェスト
        demo_dir = tmp_path / "plugins" / "demo"
        demo_cc_dir = demo_dir / ".claude-plugin"
        demo_cc_dir.mkdir(parents=True)
        demo_codex_dir = demo_dir / ".codex-plugin"
        demo_codex_dir.mkdir()
        (demo_cc_dir / "plugin.json").write_text('{"name":"demo","version":"0.1.0"}', encoding="utf-8")
        (demo_dir / "plugin.json").write_text('{"name":"demo","version":"0.1.0"}', encoding="utf-8")
        (demo_codex_dir / "plugin.json").write_text(
            '{"name":"demo","version":"0.1.0","skills":"./skills/"}',
            encoding="utf-8"
        )
        
        # plugins/demo/skills/demo-skill/SKILL.md
        skill_dir = demo_dir / "skills" / "demo-skill"
        skill_dir.mkdir(parents=True)
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text(
            "---\n"
            "name: demo-skill\n"
            "description: A demo skill\n"
            "metadata:\n"
            "  version: 1.0.0\n"
            "  author: test\n"
            "  created: 2026-01-01\n"
            "  updated: 2026-01-01\n"
            "---\n"
            "# Demo Skill\n",
            encoding="utf-8"
        )
        return tmp_path
    return _make_repo

@pytest.fixture
def copy_script():
    """実体スクリプトをテスト用リポジトリ内の scripts/ へコピーする"""
    def _copy_script(repo_root: Path, original_script_path: Path) -> Path:
        dest = repo_root / "scripts" / original_script_path.name
        shutil.copy2(original_script_path, dest)
        return dest
    return _copy_script
