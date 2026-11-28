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

[ADR-086](../../docs/02.設計書/10_決定記録/ADR-086_複合ワークスペースでUTF-8でないパスの名前の診断の置き場と、設定の候補の扱いを定める.md)の決定1〜3
（安全な入出力・互換性 §6、複合ワークスペース仕様 §5、§8）による追加:

| fixture | 入力 | 操作 | 期待 |
|---|---|---|---|
| `MULTI-075-01` | メンバー`web`の配下の未追跡の`apps/web/notes/\\xff.txt` | `check --all-workspaces --base HEAD` | `failed`／1。`web`の`diagnostics`に`SPEC-PATH-INVALID-001`（`source.path`は`web`のルートからの`notes/\\xff.txt`） |
| `MULTI-075-02` | ルートワークスペースの未追跡の`notes/\\xff.txt`（メンバーの外） | 同上 | `failed`／1。`platform`の`diagnostics`に1件 |
| `MULTI-075-03` | メンバーのパスの親の直下の未追跡の`apps/\\xff/x.txt`（どのメンバーのパスとも一致しないセグメント） | 同上 | `failed`／1。`platform`の`diagnostics`に1件（`source.path`は`apps/\\xff/x.txt`） |
| `MULTI-075-04` | 未追跡の設定の候補`tools/\\xff/.spec/bitz.yaml` | 同上 | `blocked`／2。`SPEC-MULTI-UNREGISTERED-001`の1件（`workspaceId: null`）、`workspaces: []`。`CHECK-PATH-NOT-UTF8`は返さない |
| `MULTI-075-05` | 同じ入力 | `doctor --all-workspaces` | `blocked`／2。同じ1件、検査項目`catalog`は`blocked` |
| `SINGLE-192-02` | 基準版にコミットした入れ子の設定`sandbox/\\xff/.spec/bitz.yaml`。TASKの`changes`の中のコードを変える | `check TASK-001 --base HEAD` | `failed`／1。入れ子の判定に使う設定のパスの一覧のUTF-8でないパスを、`SPEC-PATH-INVALID-001`の1件として返して続ける（ADR-074、ADR-086の決定2） |

submoduleとworktreeのUTF-8でないパス（決定3）は、準備の処理`submodule`と`worktree`の`path`がJSONの文字列で、`setup.materialize`はGitの準備の前に行うので、作れない（報告の対象）。
"""
import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from .approved_history_fixtures import API, CONFIG, CONFIG_PATH, MULTI_REPO, ROOT_CONFIG, WEB, req
from .nested_workspace_fixtures import BASE_TASK, TASK_PATH
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


def path_diagnostic(workspace, text):
    return {"code": "SPEC-PATH-INVALID-001", "severity": "error", "resultStatus": "failed", "summary": PATH_SUMMARY.format(path=text),
            "source": {"kind": "file", "workspaceId": workspace, "path": text}}


UNREGISTERED_SUMMARY = "Gitが認識する設定ファイルがカタログに登録されていません"
# 基準版のコミットに含めるパス（UTF-8でない名前の入力を未追跡のまま残す）。
MULTI_TRACKED = [CONFIG_PATH, f"{WEB}/.spec", f"{API}/.spec"]


def untracked_multi(placeholder, raw, argv="check"):
    """`MULTI-071-01`のcorpusに、UTF-8でない名前の未追跡のファイルを1つ置く。"""
    return dict(repo={**MULTI_REPO, placeholder: CONFIG + b"workspace:\n  id: x\n" if raw.endswith(b"bitz.yaml") else b"# not UTF-8 name\n"},
                changes={}, raw=raw, placeholder=placeholder,
                setup={"git": True, "materialize": [{"from": placeholder, "toBytes": raw.hex()}],
                       "baseCommit": {"message": "base", "paths": list(MULTI_TRACKED)}, "operations": []},
                argv=(["check", "--all-workspaces", "--base", "HEAD", "--format", "json"] if argv == "check"
                      else ["doctor", "--all-workspaces", "--format", "json"]))


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

CASES.update({
    "MULTI-075-01": dict(untracked_multi("tmp/web-note.txt", b"apps/web/notes/\xff.txt"), owner="web", text="notes/\\xff.txt",
                         description="--all-workspacesでは、メンバーの配下のUTF-8でないパスの診断を、所有するワークスペースにそのルートからのパスで置く"),
    "MULTI-075-02": dict(untracked_multi("tmp/root-note.txt", b"notes/\xff.txt"), owner="platform", text="notes/\\xff.txt",
                         description="--all-workspacesでは、メンバーの外のUTF-8でないパスの診断を、ルートワークスペースに置く"),
    "MULTI-075-03": dict(untracked_multi("tmp/apps-note.txt", b"apps/\xff/x.txt"), owner="platform", text="apps/\\xff/x.txt",
                         description="UTF-8でないセグメントはどのメンバーのパスとも一致しないので、メンバーの親の直下のパスはルートワークスペースが所有する"),
    "MULTI-075-04": dict(untracked_multi("tmp/bitz.yaml", b"tools/\xff/.spec/bitz.yaml"), text="tools/\\xff/.spec/bitz.yaml",
                         description="Gitが認識する設定の候補の名前がUTF-8でなければ、未登録の設定として全体事前検査を止める"),
    "MULTI-075-05": dict(untracked_multi("tmp/bitz.yaml", b"tools/\xff/.spec/bitz.yaml", argv="doctor"), text="tools/\\xff/.spec/bitz.yaml",
                         description="doctorも、Gitが認識する設定の候補の名前がUTF-8でなければ、未登録の設定として全体事前検査を止める"),
    "SINGLE-192-02": dict(
        repo={**BASE_TASK, "tmp/bitz.yaml": CONFIG}, changes={"inside.py": b"# changed allowed path\n"},
        raw=b"sandbox/\xff/.spec/bitz.yaml", placeholder="tmp/bitz.yaml", text="sandbox/\\xff/.spec/bitz.yaml",
        setup={"git": True, "materialize": [{"from": "tmp/bitz.yaml", "toBytes": b"sandbox/\xff/.spec/bitz.yaml".hex()}],
               "baseCommit": {"message": "base", "paths": ["."]},
               "operations": [{"op": "update", "path": "src/inside.py", "source": "changes/inside.py"}]},
        argv=["check", "TASK-001", "--base", "HEAD", "--format", "json"],
        description="入れ子のワークスペースの判定に使う設定のパスの名前がUTF-8でなければ、そのパスを診断して続ける"),
})
# 各ワークスペースの完全検査の件数（`MULTI-071-01`のcorpus。ルートの`platform`は仕様文書を持たない）。
MULTI_WORKSPACES = (("platform", ".", 0, 0), ("api", API, 1, 1), ("web", WEB, 1, 1))


def fixture_dir(root, identifier):
    return root / ("multi" if identifier.startswith("MULTI-") else "single") / identifier


def operation(identifier):
    return CASES[identifier]["argv"][0]


def reviewed_manifest(identifier):
    case_ = CASES[identifier]
    status = "blocked" if identifier in {"MULTI-075-04", "MULTI-075-05"} else "failed"
    return {"fixtureId": identifier, "description": case_["description"], "setup": copy.deepcopy(case_["setup"]),
            "invocation": {"runner": "bitz", "cwd": ".", "argv": list(case_["argv"]), "env": {}},
            "expect": {"status": status, "exitCode": 2 if status == "blocked" else 1, "stdout": "json",
                       "resultFile": f"expected/{operation(identifier)}.json", "reportFileCount": 0}}


def reviewed_result(identifier):
    case_ = CASES[identifier]
    if identifier in {"MULTI-075-01", "MULTI-075-02", "MULTI-075-03"}:
        workspaces = []
        for workspace_id, path, documents, statements in MULTI_WORKSPACES:
            own = [path_diagnostic(workspace_id, case_["text"])] if workspace_id == case_["owner"] else []
            workspaces.append({"id": workspace_id, "path": path, "status": "failed" if own else "passed",
                               "checkedDocumentCount": documents, "checkedStatementCount": statements, "durationMs": 0, "diagnostics": own})
        return {"schemaVersion": "1.0", "operation": "check", "scope": "all-workspaces", "status": "failed",
                "multiWorkspace": {"id": "platform", "path": "."}, "workspaces": workspaces,
                "revision": {"base": COMMIT, "commit": COMMIT, "dirty": True}, "durationMs": 0, "diagnostics": []}
    if identifier in {"MULTI-075-04", "MULTI-075-05"}:
        unregistered = {"code": "SPEC-MULTI-UNREGISTERED-001", "severity": "error", "resultStatus": "blocked", "summary": UNREGISTERED_SUMMARY,
                        "source": {"kind": "file", "workspaceId": None, "path": case_["text"]}}
        if identifier == "MULTI-075-04":
            # 未登録の設定で止まる`check --all-workspaces`の形（`MULTI-030-02`）。
            return {"schemaVersion": "1.0", "operation": "check", "scope": "all-workspaces", "status": "blocked",
                    "multiWorkspace": {"id": "platform", "path": "."}, "workspaces": [],
                    "revision": {"base": COMMIT, "commit": COMMIT, "dirty": True}, "durationMs": 0, "diagnostics": [unregistered]}
        # 全体事前検査で止まる`doctor --all-workspaces`の形（`MULTI-048-02`）で、未登録の設定は検査項目`catalog`を`blocked`にする（`MULTI-036-10`）。
        result = json.loads((HERE / "multi/MULTI-048-02/expected/doctor.json").read_text())
        if [item["name"] for item in result["checks"]] != ["core", "git", "catalog"] or result["workspaces"]:
            raise ValueError("基のfixture（MULTI-048-02）の形がレビュー済みの形と異なります")
        result.update(status="blocked", diagnostics=[unregistered])
        result["checks"][-1]["status"] = "blocked"
        return result
    if identifier == "SINGLE-192-02":
        # 明示したTASKの`check`の形（`SINGLE-184-*`）。完全検査の対象はTASK-001だけで、TASKの`changes`の中の変更は境界の外でない。
        return {"schemaVersion": "1.0", "operation": "check", "status": "failed", "scope": "selected",
                "workspace": {"id": "root", "path": "."}, "revision": {"base": COMMIT, "commit": COMMIT, "dirty": True},
                "checkedDocumentCount": 1, "checkedStatementCount": 0, "durationMs": 0,
                "diagnostics": [path_diagnostic("root", case_["text"])]}
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
    case_ = CASES[identifier]
    if "raw" in case_ and identifier != "SINGLE-192-01":
        raw = case_["raw"]
        if not os.path.lexists(os.path.join(os.fsencode(repository), raw)) or (repository / case_["placeholder"]).exists():
            raise ValueError("UTF-8でない名前の入力がレビュー済みの位置にありません")
        tracked = raw in git(repository, "ls-files", "-z").split(b"\0")
        if tracked != (identifier == "SINGLE-192-02"):
            raise ValueError("UTF-8でない名前の入力の追跡の状態がレビュー済みの形と異なります")
        if identifier == "SINGLE-192-02":
            if status != " M src/inside.py\n":
                raise ValueError("変更がTASKのchangesの中のコードだけではありません")
        elif status.count("\n") != 1 or not status.startswith('?? "'):
            raise ValueError("変更がUTF-8でない名前の未追跡のファイルだけではありません")
        return
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
