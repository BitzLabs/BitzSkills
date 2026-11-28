"""UTF-8でないパスの名前と、比べるリビジョンの壊れたルートの設定を固定する（Coreの公開操作は実行しない）。

[ADR-084](../../docs/02.設計書/10_決定記録/ADR-084_Gitの読取りの既知の問題を解消し、SHA-256のリポジトリに対応する.md)の決定1・2と、
[ADR-085](../../docs/02.設計書/10_決定記録/ADR-085_適合harnessでUTF-8でない名前とSHA-256のコミットIDを扱い、壊れたリビジョンの設定の診断の形を定める.md)の決定1・3、
[安全な入出力・互換性 §6](../../docs/03.詳細設計/00_共通契約/02_安全な入出力・互換性.md#6-正規パス)、[`check` §5、§9](../../docs/03.詳細設計/03_操作仕様/02_check.md#5-git基準版と変更集合)、
[複合ワークスペース仕様 §2、§8](../../docs/03.詳細設計/02_仕様文書モデル/05_複合ワークスペース仕様.md)、[`doctor` §3](../../docs/03.詳細設計/03_操作仕様/04_doctor.md)を根拠とする。

| fixture | 入力 | 操作 | 期待 |
|---|---|---|---|
| `SINGLE-192-01` | 基準版は`.spec/`だけ。未追跡の`notes/\\xff.txt`（UTF-8でない名前。`setup.materialize`の`toBytes`） | 引数なしの`check --base HEAD` | `failed`／1。`SPEC-PATH-INVALID-001`の1件。`selection`は`changed 1`、`target 0`、`excluded 1` |
| `MULTI-074-01` | 基準版のルートの設定のYAMLの構文が不正。作業ツリーで直す | `check --all-workspaces --base HEAD` | `failed`／1。`SPEC-MULTI-CONFIG-001`の1件、`workspaces: []` |
| `MULTI-074-02` | 同じ入力（`HEAD`のルートの設定が不正） | `doctor --all-workspaces` | `failed`／1。`MULTI-048-02`と同じ形で、診断だけが異なる |
| `MULTI-074-03` | 基準版のルートの設定がシンボリックリンク。作業ツリーで通常のファイルにする | `check --all-workspaces --base HEAD` | `MULTI-074-01`と同じ結果 |

`--all-workspaces`でUTF-8でないパスの名前を置くfixtureは、診断の置き場所（最上位かワークスペースか）、`source`の`workspaceId`とパスの基準、
全体事前検査を止めるかを仕様が定めないので、置いていない（報告の対象）。
"""
import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from .approved_history_fixtures import CONFIG, CONFIG_PATH, MULTI_REPO, ROOT_CONFIG, req
from .document_fixtures import REQ_PATH
from .harness import git, setup
from .initial_fixtures import compare_state, observe
from .schemas import schema_path

HERE = Path(__file__).resolve().parent
COMMIT = "0" * 40
NON_UTF8 = b"notes/\xff.txt"
NON_UTF8_TEXT = "notes/\\xff.txt"
PLACEHOLDER = "notes/placeholder.txt"
PATH_SUMMARY = "パス{path}の名前をUTF-8として読めません"
REVISION_SUMMARY = "比べるリビジョンのルートワークスペースの設定が不正です"
BROKEN_ROOT_CONFIG = CONFIG + b"workspace: [platform\n"
LINK_TARGET = "../config/root.yaml"


class Link(str):
    """シンボリックリンクのリンク先。"""


def revision_diagnostic():
    return {"code": "SPEC-MULTI-CONFIG-001", "severity": "error", "resultStatus": "failed", "summary": REVISION_SUMMARY,
            "source": {"kind": "file", "workspaceId": "platform", "path": CONFIG_PATH}}


CASES = {
    "SINGLE-192-01": dict(
        repo={CONFIG_PATH: CONFIG, REQ_PATH: req(), PLACEHOLDER: b"# not UTF-8 name\n"}, changes={},
        setup={"git": True, "materialize": [{"from": PLACEHOLDER, "toBytes": NON_UTF8.hex()}],
               "baseCommit": {"message": "base", "paths": [".spec"]}, "operations": []},
        argv=["check", "--base", "HEAD", "--format", "json"],
        description="未追跡のパスの名前がUTF-8でなければ、そのパスを\\xNNで表して診断し、所有されないパスとして数えて続ける"),
    "MULTI-074-01": dict(
        repo={**MULTI_REPO, CONFIG_PATH: BROKEN_ROOT_CONFIG}, changes={"root.yaml": ROOT_CONFIG},
        setup={"git": True, "baseCommit": {"message": "base", "paths": ["."]},
               "operations": [{"op": "update", "path": CONFIG_PATH, "source": "changes/root.yaml"}]},
        argv=["check", "--all-workspaces", "--base", "HEAD", "--format", "json"],
        description="比べるリビジョンのルートの設定がYAMLのマッピングとして読めなければ、全体事前検査の不適合にする"),
    "MULTI-074-02": dict(
        repo={**MULTI_REPO, CONFIG_PATH: BROKEN_ROOT_CONFIG}, changes={"root.yaml": ROOT_CONFIG},
        setup={"git": True, "baseCommit": {"message": "base", "paths": ["."]},
               "operations": [{"op": "update", "path": CONFIG_PATH, "source": "changes/root.yaml"}]},
        argv=["doctor", "--all-workspaces", "--format", "json"],
        description="doctorはHEADのルートの設定がYAMLのマッピングとして読めなければ、全体事前検査の不適合にする"),
    "MULTI-074-03": dict(
        repo={**MULTI_REPO, CONFIG_PATH: Link(LINK_TARGET), "config/root.yaml": ROOT_CONFIG}, changes={"root.yaml": ROOT_CONFIG},
        setup={"git": True, "baseCommit": {"message": "base", "paths": ["."]},
               "operations": [{"op": "delete", "path": CONFIG_PATH},
                              {"op": "create", "path": CONFIG_PATH, "source": "changes/root.yaml"}]},
        argv=["check", "--all-workspaces", "--base", "HEAD", "--format", "json"],
        description="比べるリビジョンのルートの設定が通常のファイルでなければ（シンボリックリンク）、全体事前検査の不適合にする"),
}


def fixture_dir(root, identifier):
    return root / ("multi" if identifier.startswith("MULTI-") else "single") / identifier


def operation(identifier):
    return CASES[identifier]["argv"][0]


def reviewed_manifest(identifier):
    case_ = CASES[identifier]
    return {"fixtureId": identifier, "description": case_["description"], "setup": copy.deepcopy(case_["setup"]),
            "invocation": {"runner": "bitz", "cwd": ".", "argv": list(case_["argv"]), "env": {}},
            "expect": {"status": "failed", "exitCode": 1, "stdout": "json",
                       "resultFile": f"expected/{operation(identifier)}.json", "reportFileCount": 0}}


def reviewed_result(identifier):
    if identifier == "SINGLE-192-01":
        return {"schemaVersion": "1.0", "operation": "check", "status": "failed", "scope": "changed",
                "workspace": {"id": "root", "path": "."}, "revision": {"base": COMMIT, "commit": COMMIT, "dirty": True},
                "selection": {"changedPathCount": 1, "targetDocumentCount": 0, "excludedCodeTestPathCount": 1},
                "durationMs": 0,
                "diagnostics": [{"code": "SPEC-PATH-INVALID-001", "severity": "error", "resultStatus": "failed",
                                 "summary": PATH_SUMMARY.format(path=NON_UTF8_TEXT),
                                 "source": {"kind": "file", "workspaceId": "root", "path": NON_UTF8_TEXT}}]}
    if operation(identifier) == "doctor":
        # 全体事前検査の不適合で止まる`doctor --all-workspaces`の形（`MULTI-048-02`。検査項目`catalog`が`failed`）。
        result = json.loads((HERE / "multi/MULTI-048-02/expected/doctor.json").read_text())
        if [item["code"] for item in result["diagnostics"]] != ["SPEC-MULTI-CONFIG-001"] or result["workspaces"]:
            raise ValueError("基のfixture（MULTI-048-02）の形がレビュー済みの形と異なります")
        result["diagnostics"] = [revision_diagnostic()]
        return result
    return {"schemaVersion": "1.0", "operation": "check", "status": "failed", "scope": "all-workspaces",
            "multiWorkspace": {"id": "platform", "path": "."}, "workspaces": [],
            "revision": {"base": COMMIT, "commit": COMMIT, "dirty": True}, "durationMs": 0, "diagnostics": [revision_diagnostic()]}


# --- 入力 -------------------------------------------------------------------------------------

def read_tree(directory):
    tree = {}
    if not directory.is_dir():
        return tree
    for current, directories, files in os.walk(directory, followlinks=False):
        for name in sorted(directories + files):
            path = Path(current) / name
            relative = path.relative_to(directory).as_posix()
            if path.is_symlink():
                tree[relative] = Link(os.readlink(path))
            elif path.is_file():
                if path.stat().st_mode & 0o111:
                    raise ValueError("入力に実行ビットがあります")
                tree[relative] = path.read_bytes()
    return tree


def write_tree(directory, tree):
    for relative, value in sorted(tree.items()):
        path = directory / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(value, Link):
            path.symlink_to(str(value))
        else:
            path.write_bytes(value)
            path.chmod(0o644)


def dump(value):
    # UTF-8でない名前は、ファイルシステムの符号化（surrogateescape）の文字としてスナップショットに現れるので、ASCIIのエスケープで書く。
    return json.dumps(value, ensure_ascii=True, indent=2) + "\n"


# --- 準備した後の状態の検査 -------------------------------------------------------------------

def inspect(repository, identifier):
    status = git(repository, "status", "--porcelain=v1", "--untracked-files=all").decode()
    if identifier == "SINGLE-192-01":
        names = os.listdir(os.fsencode(repository / "notes"))
        if names != [b"\xff.txt"] or status != '?? "notes/\\377.txt"\n':
            raise ValueError("UTF-8でない名前の未追跡のファイルがレビュー済みの形と異なります")
        try:
            NON_UTF8.decode("utf-8")
        except UnicodeDecodeError:
            pass
        else:
            raise ValueError("名前がUTF-8として読めます")
        return
    listing = git(repository, "ls-tree", "HEAD", CONFIG_PATH).decode().split()
    mode = listing[0] if listing else None
    if identifier == "MULTI-074-03":
        if mode != "120000" or git(repository, "show", f"HEAD:{CONFIG_PATH}").decode() != LINK_TARGET:
            raise ValueError("比べるリビジョンのルートの設定がシンボリックリンクではありません")
    elif mode != "100644" or git(repository, "show", f"HEAD:{CONFIG_PATH}") != BROKEN_ROOT_CONFIG:
        raise ValueError("比べるリビジョンのルートの設定がレビュー済みの不正な設定ではありません")
    current = repository / CONFIG_PATH
    if current.is_symlink() or current.read_bytes() != ROOT_CONFIG:
        raise ValueError("現在版のルートの設定が適合する通常のファイルではありません")


def prepared_states(fixture, manifest, identifier):
    states = []
    with tempfile.TemporaryDirectory(prefix="bitz-git-read-") as temporary:
        for run in range(2):
            sandbox = Path(temporary) / str(run)
            sandbox.mkdir()
            repository = setup(fixture, manifest, sandbox / "repo")
            inspect(repository, identifier)
            external = {name: sandbox / name for name in ("home", "cache", "temporary")}
            for path in external.values():
                path.mkdir()
            states.append(observe(repository, external))
    if states[0] != states[1]:
        raise ValueError("隔離した2回の準備手順が一致しません")
    return states[0]


def generate(root=HERE, identifiers=None):
    for identifier in CASES:
        if identifiers is not None and identifier not in identifiers:
            continue
        fixture = fixture_dir(root, identifier)
        fixture.mkdir(parents=True, exist_ok=False)
        write_tree(fixture / "repo", CASES[identifier]["repo"])
        if CASES[identifier]["changes"]:
            write_tree(fixture / "changes", CASES[identifier]["changes"])
        manifest = reviewed_manifest(identifier)
        (fixture / "manifest.json").write_text(dump(manifest))
        (fixture / "expected").mkdir()
        (fixture / reviewed_manifest(identifier)["expect"]["resultFile"]).write_text(
            json.dumps(reviewed_result(identifier), ensure_ascii=False, indent=2) + "\n")
        state = prepared_states(fixture, manifest, identifier)
        (fixture / "side-effects.json").write_text(dump({"schemaVersion": "1.0", "policy": "read-only", "before": state, "after": state}))


def validate(root=HERE, identifiers=None):
    errors, prepared = [], []
    validators = {name: Draft202012Validator(json.loads(schema_path(root, name).read_text()))
                  for name in ("manifest", "result", "side-effects")}
    for identifier in CASES:
        if identifiers is not None and identifier not in identifiers:
            continue
        fixture = fixture_dir(root, identifier)
        try:
            manifest = json.loads((fixture / "manifest.json").read_text())
            expected_file = reviewed_manifest(identifier)["expect"]["resultFile"]
            result = json.loads((fixture / expected_file).read_text())
            effects = json.loads((fixture / "side-effects.json").read_text())
            for name, value in (("manifest", manifest), ("result", result), ("side-effects", effects)):
                validators[name].validate(value)
            if manifest != reviewed_manifest(identifier) or result != reviewed_result(identifier):
                raise ValueError("マニフェストまたは期待結果がレビュー済みの期待値と異なります")
            if {path.name for path in (fixture / "expected").iterdir()} != {Path(expected_file).name}:
                raise ValueError("期待値のファイルがレビュー済みの1件と異なります")
            if read_tree(fixture / "repo") != CASES[identifier]["repo"] or read_tree(fixture / "changes") != CASES[identifier]["changes"]:
                raise ValueError("入力がレビュー済みの入力と異なります")
            if {path.name for path in fixture.iterdir()} - {"repo", "changes", "expected", "manifest.json", "side-effects.json"}:
                raise ValueError("fixtureにレビューしていないファイルがあります")
            if effects["policy"] != "read-only" or effects["before"] != effects["after"]:
                raise ValueError("読取り専用の期待値が書込みを許しています")
            if compare_state(effects["before"], prepared_states(fixture, manifest, identifier)):
                raise ValueError("隔離した準備手順が固定したスナップショットと異なります")
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, IndexError, UnicodeError, ValidationError, subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).splitlines()[0] if str(error) else type(error).__name__}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "status": "Passed" if not errors else "Failed", "errors": errors}
