"""CORE-FR-011 scripts/spec ラッパーの回帰テスト（テスト先行）。

bitz-sdd を「インストール済みプラグイン」として消費する本リポ（ドッグフーディング）で、
SDD ツール（inspect/scaffold/status/update）をバージョン非依存に解決して委譲する
ラッパー `scripts/spec` を検証する。

環境変数 BITZSKILLS_PLUGINS_DIR でプラグイン格納先を差し替え、
以下を example-test で確認する:
  - installed_plugins.json の固定版（projectPath 一致）を優先解決すること
  - 該当エントリが無ければキャッシュの semver 最大版へフォールバックすること
  - フォールバック時、当該ツールを欠く版はスキップすること
  - 引数と終了コードを透過すること
  - 未知のツール名 / 解決不能 / 解決先スクリプト不在で非ゼロ失敗すること
  - ソースにバージョン番号を直書きしないこと
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

SPEC_WRAPPER = Path(__file__).resolve().parent.parent / "scripts" / "spec"

# ツール名 → 実スクリプト名（ラッパーと同じ対応。テスト側で独立に定義して二重化検証する）
SPEC_TOOLS = {
    "inspect": "spec_inspect.py",
    "scaffold": "spec_scaffold.py",
    "status": "spec_status.py",
    "update": "spec_update.py",
}
REL = ("skills", "sdd-core", "scripts")

# 委譲先のダミースクリプト。marker で「どの版のどのツール」が呼ばれたかを、
# args で引数透過を、FAKE_RC で終了コード透過を検証できるようにする。
FAKE_TEMPLATE = (
    "import sys, os, json\n"
    'print(json.dumps({{"marker": "{marker}", "args": sys.argv[1:]}}))\n'
    'sys.exit(int(os.environ.get("FAKE_RC", "0")))\n'
)


def make_version(cache_root: Path, marketplace: str, version: str, tools) -> Path:
    """cache/<marketplace>/bitz-sdd/<version>/skills/sdd-core/scripts/ に
    指定ツールのダミースクリプトを作り、その版ディレクトリ（installPath 相当）を返す。"""
    ver_root = cache_root / marketplace / "bitz-sdd" / version
    scripts_dir = ver_root.joinpath(*REL)
    scripts_dir.mkdir(parents=True, exist_ok=True)
    for t in tools:
        (scripts_dir / SPEC_TOOLS[t]).write_text(
            FAKE_TEMPLATE.format(marker=f"{version}:{t}"), encoding="utf-8"
        )
    return ver_root


def write_installed(plugins_dir: Path, project_path: Path, install_path: Path):
    """installed_plugins.json に bitz-sdd の1エントリを書く。"""
    plugins_dir.mkdir(parents=True, exist_ok=True)
    (plugins_dir / "installed_plugins.json").write_text(
        json.dumps({
            "version": 2,
            "plugins": {
                "bitz-sdd@bitzskills": [{
                    "scope": "project",
                    "projectPath": str(project_path),
                    "installPath": str(install_path),
                    "version": "x",
                }]
            },
        }),
        encoding="utf-8",
    )


def make_repo(tmp_path: Path) -> Path:
    """ラッパーを scripts/spec に持つ最小リポジトリを作る（repo_root = spec の親の親）。"""
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    (repo / "scripts" / "spec").write_bytes(SPEC_WRAPPER.read_bytes())
    return repo


def run_spec(repo: Path, plugins_dir: Path, *args, rc=None):
    env = dict(os.environ)
    env["BITZSKILLS_PLUGINS_DIR"] = str(plugins_dir)
    if rc is not None:
        env["FAKE_RC"] = str(rc)
    return subprocess.run(
        [sys.executable, str(repo / "scripts" / "spec"), *args],
        capture_output=True, text=True, env=env,
    )


def test_wrapper_exists():
    assert SPEC_WRAPPER.exists(), "scripts/spec ラッパーが存在すること"


def test_fixed_version_priority(tmp_path):
    """installed_plugins.json の固定版を、semver 最大版より優先して解決する。"""
    repo = make_repo(tmp_path)
    plugins = tmp_path / "plugins"
    cache = plugins / "cache"
    pinned = make_version(cache, "bitzskills", "1.0.0", SPEC_TOOLS)
    make_version(cache, "bitzskills", "2.0.0", SPEC_TOOLS)  # より新しいがピン留めではない
    write_installed(plugins, repo, pinned)

    r = run_spec(repo, plugins, "inspect")
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["marker"] == "1.0.0:inspect"


def test_cache_fallback_semver_max(tmp_path):
    """installed に該当が無ければキャッシュの semver 最大版へフォールバックする。"""
    repo = make_repo(tmp_path)
    plugins = tmp_path / "plugins"
    cache = plugins / "cache"
    make_version(cache, "bitzskills", "1.0.0", SPEC_TOOLS)
    make_version(cache, "bitzskills", "1.10.0", SPEC_TOOLS)  # 文字列比較では 1.2.0 未満に見える罠
    make_version(cache, "bitzskills", "1.2.0", SPEC_TOOLS)
    # installed_plugins.json は書かない

    r = run_spec(repo, plugins, "status")
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["marker"] == "1.10.0:status"


def test_projectpath_mismatch_falls_back_to_cache(tmp_path):
    """projectPath が一致しない installed エントリは無視してキャッシュへフォールバックする。"""
    repo = make_repo(tmp_path)
    plugins = tmp_path / "plugins"
    cache = plugins / "cache"
    other = make_version(cache, "bitzskills", "1.0.0", SPEC_TOOLS)
    make_version(cache, "bitzskills", "2.0.0", SPEC_TOOLS)
    write_installed(plugins, tmp_path / "somewhere-else", other)

    r = run_spec(repo, plugins, "inspect")
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["marker"] == "2.0.0:inspect"


def test_fallback_skips_versions_missing_tool(tmp_path):
    """フォールバック時、当該ツールを欠く版はスキップし、備える最大版を選ぶ。"""
    repo = make_repo(tmp_path)
    plugins = tmp_path / "plugins"
    cache = plugins / "cache"
    make_version(cache, "bitzskills", "1.0.0", SPEC_TOOLS)  # 全ツールあり
    make_version(cache, "bitzskills", "2.0.0", ["inspect", "status", "update"])  # scaffold 欠落

    # scaffold は 2.0.0 に無いので 1.0.0 が選ばれる
    r_sc = run_spec(repo, plugins, "scaffold")
    assert r_sc.returncode == 0, r_sc.stderr
    assert json.loads(r_sc.stdout)["marker"] == "1.0.0:scaffold"

    # inspect は両方にあるので 2.0.0
    r_in = run_spec(repo, plugins, "inspect")
    assert r_in.returncode == 0, r_in.stderr
    assert json.loads(r_in.stdout)["marker"] == "2.0.0:inspect"


def test_arg_and_exit_passthrough(tmp_path):
    """引数と終了コードを委譲先へ/から透過する。"""
    repo = make_repo(tmp_path)
    plugins = tmp_path / "plugins"
    cache = plugins / "cache"
    pinned = make_version(cache, "bitzskills", "1.0.0", SPEC_TOOLS)
    write_installed(plugins, repo, pinned)

    r = run_spec(repo, plugins, "inspect", "--workspace", ".", "plugins/foo", rc=7)
    assert r.returncode == 7, r.stderr
    payload = json.loads(r.stdout)
    assert payload["args"] == ["--workspace", ".", "plugins/foo"]


def test_unknown_tool_fails_nonzero_and_lists_valid(tmp_path):
    """未知のツール名は非ゼロで失敗し、有効なツール名を提示する。"""
    repo = make_repo(tmp_path)
    plugins = tmp_path / "plugins"
    make_version(plugins / "cache", "bitzskills", "1.0.0", SPEC_TOOLS)

    r = run_spec(repo, plugins, "frobnicate")
    assert r.returncode != 0
    for name in SPEC_TOOLS:
        assert name in r.stderr


def test_no_tool_fails_nonzero(tmp_path):
    """ツール名なしは非ゼロで失敗する。"""
    repo = make_repo(tmp_path)
    plugins = tmp_path / "plugins"
    make_version(plugins / "cache", "bitzskills", "1.0.0", SPEC_TOOLS)

    r = run_spec(repo, plugins)
    assert r.returncode != 0


def test_unresolvable_fails_nonzero(tmp_path):
    """当該ツールを備える bitz-sdd がどこにも無ければ非ゼロで失敗する。"""
    repo = make_repo(tmp_path)
    plugins = tmp_path / "plugins"
    (plugins / "cache").mkdir(parents=True)  # 空のキャッシュ

    r = run_spec(repo, plugins, "inspect")
    assert r.returncode != 0


def test_pinned_but_script_missing_fails_nonzero(tmp_path):
    """固定版が解決先スクリプトを欠く場合は（黙ってフォールバックせず）非ゼロで失敗する。"""
    repo = make_repo(tmp_path)
    plugins = tmp_path / "plugins"
    cache = plugins / "cache"
    # ピン留めした版には scaffold が無い
    pinned = make_version(cache, "bitzskills", "1.0.0", ["inspect", "status", "update"])
    # キャッシュには scaffold を備える別版もあるが、ピン留めが壊れているので使わない
    make_version(cache, "bitzskills", "2.0.0", SPEC_TOOLS)
    write_installed(plugins, repo, pinned)

    r = run_spec(repo, plugins, "scaffold")
    assert r.returncode != 0
    assert "scaffold" in (r.stderr + r.stdout).lower() or "spec_scaffold" in r.stderr


def test_source_has_no_hardcoded_version():
    """ラッパーのソースに semver 形式のバージョン番号を直書きしない。"""
    src = SPEC_WRAPPER.read_text(encoding="utf-8")
    hits = re.findall(r"\b\d+\.\d+\.\d+\b", src)
    assert not hits, f"バージョン番号が直書きされている: {hits}"
