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


@pytest.fixture
def allowlisted_root(tmp_path_factory, request):
    """allowlist 済み filesystem 上の owner-only ディレクトリを返す。

    pytest の `tmp_path` は `/tmp`（多くの環境で tmpfs）に作られるが、tmpfs は
    再起動で消えるため durability 保証が成立せず allowlist から外した
    （`FLW-REV-028:GP-007`）。probe が `SUPPORTED` を返す前提の test は、
    実運用と同じ**永続 filesystem** 上で走らせる必要がある。

    worktree root の既定は `<repo-parent>/.worktrees/...`（`FLW-DSN-006`）なので、
    repository の兄弟位置を借りる。allowlist 済み fs が見つからなければ skip する。
    """
    import os
    import shutil
    import sys
    import tempfile
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[1]
    skill = repo_root / "plugins" / "bitz-flow" / "skills" / "flow-core"
    sys.path.insert(0, str(skill / "scripts"))
    from flowlib import worktree_platform as platform_probe

    profiles = platform_probe.load_support_profiles(platform_probe.SUPPORT_REGISTRY_PATH)
    allowed = profiles[platform_probe.current_platform()].filesystem_types

    for parent in (repo_root.parent, Path.home()):
        kind = platform_probe._linux_filesystem_type(parent)
        if kind in allowed:
            created = Path(tempfile.mkdtemp(prefix=".bitz-flow-test-", dir=str(parent)))
            os.chmod(created, 0o700)
            request.addfinalizer(lambda: shutil.rmtree(created, ignore_errors=True))
            return created
    pytest.skip(f"allowlist 済み filesystem({sorted(allowed)})上の作業場所が無い")
