"""CORE-FR-011 scripts/spec ラッパーのClaude/Codex横断回帰テスト。"""
import importlib.machinery
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

SPEC_WRAPPER = Path(__file__).resolve().parent.parent / "scripts" / "spec"
SPEC_TOOLS = {
    "inspect": "spec_inspect.py",
    "scaffold": "spec_scaffold.py",
    "status": "spec_status.py",
    "update": "spec_update.py",
}
V3_SUPPORT_SCRIPTS = ("spec_labels.py", "spec_trace.py", "spec_transaction.py")
REL = ("skills", "sdd-core", "scripts")
FAKE_TEMPLATE = (
    "import sys, os, json\n"
    'print(json.dumps({{"marker": "{marker}", "args": sys.argv[1:]}}))\n'
    'sys.exit(int(os.environ.get("FAKE_RC", "0")))\n'
)


def load_wrapper():
    """拡張子なしのscripts/specをテスト用モジュールとして読む。"""
    name = "bitzskills_spec_wrapper_under_test"
    loader = importlib.machinery.SourceFileLoader(name, str(SPEC_WRAPPER))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    loader.exec_module(module)
    return module


WRAPPER = load_wrapper()


def make_version(
    cache_root: Path,
    marketplace: str,
    version: str,
    tools=SPEC_TOOLS,
    *,
    manifest_version=None,
    content_tag=None,
    v3_support=False,
) -> Path:
    """完全または意図的に破損したbitz-sdd cache版を作る。"""
    ver_root = cache_root / marketplace / "bitz-sdd" / version
    scripts_dir = ver_root.joinpath(*REL)
    scripts_dir.mkdir(parents=True, exist_ok=True)
    tag = content_tag if content_tag is not None else version
    (ver_root / "plugin.json").write_text(
        json.dumps({
            "name": "bitz-sdd",
            "version": manifest_version if manifest_version is not None else version,
        }),
        encoding="utf-8",
    )
    for tool in tools:
        (scripts_dir / SPEC_TOOLS[tool]).write_text(
            FAKE_TEMPLATE.format(marker=f"{tag}:{tool}"), encoding="utf-8"
        )
    if v3_support:
        for script_name in V3_SUPPORT_SCRIPTS:
            (scripts_dir / script_name).write_text(
                f"# support {tag}:{script_name}\n", encoding="utf-8"
            )
    return ver_root


def write_installed(
    plugins_dir: Path,
    project_path: Path,
    install_path: Path,
    *,
    version=None,
):
    """Claude installed_plugins.jsonへbitz-sddの固定版を書く。"""
    plugins_dir.mkdir(parents=True, exist_ok=True)
    pinned_version = version if version is not None else install_path.name
    (plugins_dir / "installed_plugins.json").write_text(
        json.dumps({
            "version": 2,
            "plugins": {
                "bitz-sdd@bitzskills": [{
                    "scope": "project",
                    "projectPath": str(project_path),
                    "installPath": str(install_path),
                    "version": pinned_version,
                }]
            },
        }),
        encoding="utf-8",
    )


def make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    (repo / "scripts" / "spec").write_bytes(SPEC_WRAPPER.read_bytes())
    return repo


def run_spec(repo: Path, plugins_dir: Path, *args, rc=None, extra_env=None):
    env = dict(os.environ)
    env["BITZSKILLS_PLUGINS_DIR"] = str(plugins_dir)
    if rc is not None:
        env["FAKE_RC"] = str(rc)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, str(repo / "scripts" / "spec"), *args],
        capture_output=True,
        text=True,
        env=env,
    )


def discovery(state, reason, entry=None):
    return WRAPPER.CodexDiscovery(state=state, reason=reason, entry=entry)


def codex_entry(version: str, *, installed=True, enabled=True):
    return {
        "pluginId": "bitz-sdd@bitzskills",
        "name": "bitz-sdd",
        "marketplaceName": "bitzskills",
        "version": version,
        "installed": installed,
        "enabled": enabled,
    }


def test_CORE_FR_011_wrapper_exists():
    assert SPEC_WRAPPER.exists()


def test_CORE_FR_011_override_fixed_version_priority(tmp_path):
    repo = make_repo(tmp_path)
    plugins = tmp_path / "plugins"
    pinned = make_version(plugins / "cache", "bitzskills", "1.0.0")
    make_version(plugins / "cache", "bitzskills", "2.0.0")
    write_installed(plugins, repo, pinned)

    result = run_spec(repo, plugins, "inspect")
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["marker"] == "1.0.0:inspect"


def test_CORE_FR_011_override_does_not_invoke_codex(tmp_path):
    repo = make_repo(tmp_path)
    plugins = tmp_path / "plugins"
    make_version(plugins / "cache", "bitzskills", "1.0.0")
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    marker = tmp_path / "codex-called"
    fake_codex = fake_bin / "codex"
    fake_codex.write_text(
        f"#!{sys.executable}\nfrom pathlib import Path\nPath({str(marker)!r}).write_text('called')\n",
        encoding="utf-8",
    )
    fake_codex.chmod(0o755)

    result = run_spec(
        repo,
        plugins,
        "status",
        extra_env={"PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}"},
    )
    assert result.returncode == 0, result.stderr
    assert not marker.exists()


def test_CORE_FR_011_cache_selects_one_complete_plugin_version(tmp_path):
    """全ツールが揃わない新版をツールごとに混用しない。"""
    repo = make_repo(tmp_path)
    plugins = tmp_path / "plugins"
    make_version(plugins / "cache", "bitzskills", "1.0.0")
    make_version(
        plugins / "cache",
        "bitzskills",
        "2.0.0",
        ["inspect", "status", "update"],
    )

    for tool in SPEC_TOOLS:
        result = run_spec(repo, plugins, tool)
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout)["marker"] == f"1.0.0:{tool}"


def test_CORE_FR_011_cache_uses_strict_semver_and_prefers_release(tmp_path):
    repo = make_repo(tmp_path)
    plugins = tmp_path / "plugins"
    make_version(plugins / "cache", "bitzskills", "1.0.0-rc.2")
    make_version(plugins / "cache", "bitzskills", "1.0.0")
    make_version(plugins / "cache", "bitzskills", "9.latest")

    result = run_spec(repo, plugins, "status")
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["marker"] == "1.0.0:status"


def test_CORE_FR_011_projectpath_mismatch_falls_back(tmp_path):
    repo = make_repo(tmp_path)
    plugins = tmp_path / "plugins"
    other = make_version(plugins / "cache", "bitzskills", "1.0.0")
    make_version(plugins / "cache", "bitzskills", "2.0.0")
    write_installed(plugins, tmp_path / "other-repo", other)

    result = run_spec(repo, plugins, "inspect")
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["marker"] == "2.0.0:inspect"


def test_CORE_FR_011_pinned_incomplete_fails_without_fallback(tmp_path):
    repo = make_repo(tmp_path)
    plugins = tmp_path / "plugins"
    pinned = make_version(
        plugins / "cache",
        "bitzskills",
        "1.0.0",
        ["inspect", "status", "update"],
    )
    make_version(plugins / "cache", "bitzskills", "2.0.0")
    write_installed(plugins, repo, pinned)

    result = run_spec(repo, plugins, "scaffold")
    assert result.returncode == WRAPPER.EXIT_UNRESOLVED
    assert "固定版" in result.stderr


def test_CORE_FR_011_pinned_manifest_version_mismatch_fails(tmp_path):
    repo = make_repo(tmp_path)
    plugins = tmp_path / "plugins"
    pinned = make_version(
        plugins / "cache",
        "bitzskills",
        "1.0.0",
        manifest_version="1.0.1",
    )
    write_installed(plugins, repo, pinned)

    result = run_spec(repo, plugins, "inspect")
    assert result.returncode == WRAPPER.EXIT_UNRESOLVED
    assert "version" in result.stderr


def test_CORE_FR_011_codex_valid_resolves_exact_custom_home(tmp_path):
    codex_plugins = tmp_path / "custom-codex" / "plugins"
    claude_plugins = tmp_path / "claude" / "plugins"
    make_version(codex_plugins / "cache", "bitzskills", "2.8.0")
    candidate = WRAPPER.resolve_default(
        SPEC_TOOLS["status"],
        codex_plugins,
        claude_plugins,
        discovery("valid", "installed-enabled", codex_entry("2.8.0")),
        tmp_path / "repo",
    )
    assert candidate.platform == "codex"
    assert candidate.version == "2.8.0"
    assert candidate.plugin_root == (
        codex_plugins / "cache" / "bitzskills" / "bitz-sdd" / "2.8.0"
    )


@pytest.mark.parametrize("reason", ["disabled", "uninstalled", "no-entry"])
def test_CORE_FR_011_authoritative_negative_excludes_codex_cache(tmp_path, reason):
    codex_plugins = tmp_path / "codex" / "plugins"
    claude_plugins = tmp_path / "claude" / "plugins"
    make_version(codex_plugins / "cache", "bitzskills", "9.0.0")
    make_version(claude_plugins / "cache", "bitzskills", "1.0.0")

    candidate = WRAPPER.resolve_default(
        SPEC_TOOLS["inspect"],
        codex_plugins,
        claude_plugins,
        discovery("authoritative-negative", reason),
        tmp_path / "repo",
    )
    assert candidate.platform == "claude"
    assert candidate.version == "1.0.0"


def test_CORE_FR_011_unavailable_allows_codex_cache_fallback(tmp_path):
    codex_plugins = tmp_path / "codex" / "plugins"
    claude_plugins = tmp_path / "claude" / "plugins"
    make_version(codex_plugins / "cache", "bitzskills", "2.0.0")
    make_version(claude_plugins / "cache", "bitzskills", "1.0.0")

    candidate = WRAPPER.resolve_default(
        SPEC_TOOLS["update"],
        codex_plugins,
        claude_plugins,
        discovery("unavailable", "cli-not-found"),
        tmp_path / "repo",
    )
    assert candidate.platform == "codex"
    assert candidate.version == "2.0.0"


def test_CORE_FR_011_corrupt_excludes_codex_cache(tmp_path):
    codex_plugins = tmp_path / "codex" / "plugins"
    claude_plugins = tmp_path / "claude" / "plugins"
    make_version(codex_plugins / "cache", "bitzskills", "9.0.0")
    make_version(claude_plugins / "cache", "bitzskills", "1.0.0")

    candidate = WRAPPER.resolve_default(
        SPEC_TOOLS["update"],
        codex_plugins,
        claude_plugins,
        discovery("corrupt", "invalid-json"),
        tmp_path / "repo",
    )
    assert candidate.platform == "claude"
    assert candidate.version == "1.0.0"


def test_CORE_FR_011_pinned_version_conflict_fails(tmp_path):
    codex_plugins = tmp_path / "codex" / "plugins"
    claude_plugins = tmp_path / "claude" / "plugins"
    make_version(codex_plugins / "cache", "bitzskills", "2.0.0")
    claude_pinned = make_version(
        claude_plugins / "cache", "bitzskills", "1.0.0"
    )
    repo = tmp_path / "repo"
    write_installed(claude_plugins, repo, claude_pinned)

    with pytest.raises(WRAPPER.ResolutionError, match="競合"):
        WRAPPER.resolve_default(
            SPEC_TOOLS["inspect"],
            codex_plugins,
            claude_plugins,
            discovery("valid", "installed-enabled", codex_entry("2.0.0")),
            repo,
        )


def test_CORE_FR_011_same_version_different_fingerprint_fails(tmp_path):
    codex_plugins = tmp_path / "codex" / "plugins"
    claude_plugins = tmp_path / "claude" / "plugins"
    make_version(
        codex_plugins / "cache",
        "bitzskills",
        "2.0.0",
        content_tag="codex-build",
    )
    make_version(
        claude_plugins / "cache",
        "bitzskills",
        "2.0.0",
        content_tag="claude-build",
    )

    with pytest.raises(WRAPPER.ResolutionError, match="fingerprint"):
        WRAPPER.resolve_default(
            SPEC_TOOLS["inspect"],
            codex_plugins,
            claude_plugins,
            discovery("unavailable", "cli-not-found"),
            tmp_path / "repo",
        )


def test_CORE_FR_011_same_version_same_fingerprint_prefers_codex(tmp_path):
    codex_plugins = tmp_path / "codex" / "plugins"
    claude_plugins = tmp_path / "claude" / "plugins"
    make_version(codex_plugins / "cache", "bitzskills", "2.0.0")
    make_version(claude_plugins / "cache", "bitzskills", "2.0.0")

    candidate = WRAPPER.resolve_default(
        SPEC_TOOLS["inspect"],
        codex_plugins,
        claude_plugins,
        discovery("unavailable", "cli-not-found"),
        tmp_path / "repo",
    )
    assert candidate.platform == "codex"


def test_CORE_FR_011_discover_codex_classifies_timeout(monkeypatch, tmp_path):
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], WRAPPER.CODEX_TIMEOUT_SECONDS)

    monkeypatch.setattr(WRAPPER.shutil, "which", lambda _: "/fake/codex")
    monkeypatch.setattr(WRAPPER.subprocess, "run", timeout)
    result = WRAPPER.discover_codex(tmp_path)
    assert result.state == "unavailable"
    assert result.reason == "timeout"


def test_CORE_FR_011_discover_codex_classifies_invalid_json(monkeypatch, tmp_path):
    completed = subprocess.CompletedProcess(
        args=["codex"], returncode=0, stdout="{invalid", stderr="secret"
    )
    monkeypatch.setattr(WRAPPER.shutil, "which", lambda _: "/fake/codex")
    monkeypatch.setattr(WRAPPER.subprocess, "run", lambda *a, **k: completed)
    result = WRAPPER.discover_codex(tmp_path)
    assert result.state == "corrupt"
    assert result.reason == "invalid-json"
    assert "secret" not in result.reason


def test_CORE_FR_011_discover_codex_rejects_oversized_output(monkeypatch, tmp_path):
    completed = subprocess.CompletedProcess(
        args=["codex"],
        returncode=0,
        stdout="x" * (WRAPPER.CODEX_STDOUT_LIMIT + 1),
        stderr="",
    )
    monkeypatch.setattr(WRAPPER.shutil, "which", lambda _: "/fake/codex")
    monkeypatch.setattr(WRAPPER.subprocess, "run", lambda *a, **k: completed)
    result = WRAPPER.discover_codex(tmp_path)
    assert result.state == "corrupt"
    assert result.reason == "stdout-too-large"


def test_CORE_FR_011_arg_and_exit_passthrough(tmp_path):
    repo = make_repo(tmp_path)
    plugins = tmp_path / "plugins"
    pinned = make_version(plugins / "cache", "bitzskills", "1.0.0")
    write_installed(plugins, repo, pinned)

    result = run_spec(
        repo,
        plugins,
        "inspect",
        "--workspace",
        ".",
        "plugins/foo",
        rc=7,
    )
    assert result.returncode == 7, result.stderr
    assert json.loads(result.stdout)["args"] == [
        "--workspace",
        ".",
        "plugins/foo",
    ]


@pytest.mark.parametrize("args", [(), ("frobnicate",)])
def test_CORE_FR_011_usage_errors_list_valid_tools(tmp_path, args):
    repo = make_repo(tmp_path)
    plugins = tmp_path / "plugins"
    make_version(plugins / "cache", "bitzskills", "1.0.0")

    result = run_spec(repo, plugins, *args)
    assert result.returncode == WRAPPER.EXIT_USAGE
    for name in SPEC_TOOLS:
        assert name in result.stderr


def test_CORE_FR_011_unresolved_diagnostic_is_safe_and_actionable(tmp_path):
    repo = make_repo(tmp_path)
    plugins = tmp_path / "plugins"
    (plugins / "cache").mkdir(parents=True)

    result = run_spec(repo, plugins, "inspect")
    assert result.returncode == WRAPPER.EXIT_UNRESOLVED
    assert "BITZSKILLS_PLUGINS_DIR" in result.stderr
    assert str(plugins / "cache") in result.stderr
    assert "再試行" in result.stderr


def test_CORE_FR_011_source_has_no_hardcoded_plugin_version():
    src = SPEC_WRAPPER.read_text(encoding="utf-8")
    hits = re.findall(r"\b\d+\.\d+\.\d+\b", src)
    assert not hits, f"プラグインversionが直書きされている: {hits}"


def test_SDD_FR_143_v3_candidate_requires_transaction_support_scripts(tmp_path):
    repo = make_repo(tmp_path)
    plugins = tmp_path / "plugins"
    make_version(plugins / "cache", "bitzskills", "2.9.0")
    make_version(plugins / "cache", "bitzskills", "3.0.0")

    result = run_spec(repo, plugins, "update")

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["marker"] == "2.9.0:update"


def test_SDD_FR_143_complete_v3_candidate_is_selectable(tmp_path):
    repo = make_repo(tmp_path)
    plugins = tmp_path / "plugins"
    make_version(plugins / "cache", "bitzskills", "2.9.0")
    make_version(
        plugins / "cache",
        "bitzskills",
        "3.0.0",
        v3_support=True,
    )

    result = run_spec(repo, plugins, "update")

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["marker"] == "3.0.0:update"
