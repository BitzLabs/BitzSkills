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
    """3マニフェストの version 不一致の場合、exit 1 になり該当 FAIL 行が出ること"""
    repo = make_repo()
    script = copy_script(repo, CHECK_SCRIPT)
    
    agy_file = repo / "plugins/demo/plugin.json"
    agy_file.write_text('{"name":"demo","version":"0.2.0"}', encoding="utf-8")
    
    res = run_check(script)
    assert res.returncode == 1
    assert "FAIL" in res.stdout
    assert "version 一致" in res.stdout


def test_release_check_missing_codex_manifest(make_repo, copy_script):
    """Codex マニフェストが欠落している場合、exit 1 になること"""
    repo = make_repo()
    script = copy_script(repo, CHECK_SCRIPT)
    (repo / "plugins/demo/.codex-plugin/plugin.json").unlink()

    res = run_check(script)
    assert res.returncode == 1
    assert "マニフェスト3つの存在" in res.stdout


def test_release_check_invalid_codex_skills_path(make_repo, copy_script):
    """Codex マニフェストが skills/ を公開しない場合、exit 1 になること"""
    repo = make_repo()
    script = copy_script(repo, CHECK_SCRIPT)
    codex_file = repo / "plugins/demo/.codex-plugin/plugin.json"
    codex_file.write_text(
        '{"name":"demo","version":"0.1.0","skills":"skills"}',
        encoding="utf-8",
    )

    res = run_check(script)
    assert res.returncode == 1
    assert "Codex skills パス" in res.stdout


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


def add_plugin(repo: Path, name: str, version: str = "0.1.0", dependencies=None,
               dependencies_by_runtime=None):
    """fixture リポジトリへプラグインを追加し marketplace に登録する。

    dependencies は3マニフェスト共通の metadata.dependencies。
    dependencies_by_runtime={"claude": [...], "agy": [...], "codex": [...]} を渡すと
    ランタイムごとに異なる宣言を書ける（不一致テスト用）。
    """
    plugin_dir = repo / "plugins" / name
    (plugin_dir / "skills").mkdir(parents=True)
    manifests = {
        "claude": plugin_dir / ".claude-plugin" / "plugin.json",
        "agy": plugin_dir / "plugin.json",
        "codex": plugin_dir / ".codex-plugin" / "plugin.json",
    }
    for runtime, path in manifests.items():
        data = {"name": name, "version": version}
        if runtime == "codex":
            data["skills"] = "./skills/"
        deps = dependencies
        if dependencies_by_runtime is not None:
            deps = dependencies_by_runtime.get(runtime)
        if deps is not None:
            data["metadata"] = {"dependencies": deps}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")
    marketplace = repo / ".claude-plugin/marketplace.json"
    mp_data = json.loads(marketplace.read_text(encoding="utf-8"))
    mp_data["plugins"].append({"name": name, "source": f"./plugins/{name}"})
    marketplace.write_text(json.dumps(mp_data), encoding="utf-8")


def set_demo_dependencies(repo: Path, dependencies):
    """既存 demo プラグインの3マニフェストへ metadata.dependencies を書き込む"""
    for path in (
        repo / "plugins/demo/.claude-plugin/plugin.json",
        repo / "plugins/demo/plugin.json",
        repo / "plugins/demo/.codex-plugin/plugin.json",
    ):
        data = json.loads(path.read_text(encoding="utf-8"))
        data["metadata"] = {"dependencies": dependencies}
        path.write_text(json.dumps(data), encoding="utf-8")


def test_release_check_dependency_satisfied(make_repo, copy_script):
    """実在する依存先 + 満たされる semver 制約の宣言は PASS になること"""
    repo = make_repo()
    script = copy_script(repo, CHECK_SCRIPT)
    add_plugin(repo, "base", version="1.5.0")
    set_demo_dependencies(repo, ["base>=1.4"])

    res = run_check(script)
    assert res.returncode == 0
    assert "PASS" in res.stdout


def test_release_check_dependency_missing_target(make_repo, copy_script):
    """依存先プラグインが実体に存在しない場合、exit 1 になること"""
    repo = make_repo()
    script = copy_script(repo, CHECK_SCRIPT)
    set_demo_dependencies(repo, ["ghost>=1.0"])

    res = run_check(script)
    assert res.returncode == 1
    assert "依存先" in res.stdout


def test_release_check_dependency_version_unsatisfied(make_repo, copy_script):
    """依存先の現行 version が semver 制約を満たさない場合、exit 1 になること"""
    repo = make_repo()
    script = copy_script(repo, CHECK_SCRIPT)
    add_plugin(repo, "base", version="0.9.0")
    set_demo_dependencies(repo, ["base>=1.4"])

    res = run_check(script)
    assert res.returncode == 1
    assert "制約" in res.stdout


def test_release_check_dependency_cycle(make_repo, copy_script):
    """依存グラフに循環がある場合、exit 1 になること"""
    repo = make_repo()
    script = copy_script(repo, CHECK_SCRIPT)
    add_plugin(repo, "base", dependencies=["demo"])
    set_demo_dependencies(repo, ["base"])

    res = run_check(script)
    assert res.returncode == 1
    assert "循環" in res.stdout


def test_release_check_dependency_manifest_mismatch(make_repo, copy_script):
    """3マニフェストで metadata.dependencies が同値でない場合、exit 1 になること"""
    repo = make_repo()
    script = copy_script(repo, CHECK_SCRIPT)
    add_plugin(
        repo,
        "mixed",
        dependencies_by_runtime={
            "claude": ["demo>=0.1"],
            "agy": ["demo>=0.1"],
            "codex": ["demo>=0.2"],
        },
    )

    res = run_check(script)
    assert res.returncode == 1
    assert "dependencies 一致" in res.stdout


def test_release_check_no_dependency_declaration_stays_silent(make_repo, copy_script):
    """依存宣言を持たないプラグインは依存検証の報告対象にならず PASS のままであること（後方互換）"""
    repo = make_repo()
    script = copy_script(repo, CHECK_SCRIPT)

    res = run_check(script)
    assert res.returncode == 0
    assert "依存" not in res.stdout


def test_release_check_missing_frontmatter(make_repo, copy_script):
    """SKILL.md に frontmatter 自体がない場合、exit 1 になること"""
    repo = make_repo()
    script = copy_script(repo, CHECK_SCRIPT)
    
    skill_md = repo / "plugins/demo/skills/demo-skill/SKILL.md"
    skill_md.write_text("# Demo Skill\nNo frontmatter here.", encoding="utf-8")
    
    res = run_check(script)
    assert res.returncode == 1
    assert "欠落" in res.stdout
