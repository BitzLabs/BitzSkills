"""基準版のルートの設定が値の空の`multiWorkspace:`を持つときの、Gitの比較の扱いを固定する（Coreの公開操作は実行しない）。

実装の確認事項C58の続き（独立レビューのM1）とADR-051の追加に対応する。複合ワークスペース仕様 §2.1は、設定が`multiWorkspace`を宣言するかをキーの有無で判定すると定める。
§8は、全体操作がスナップショットごとに、そのスナップショット自身のルートの設定が`multiWorkspace`を宣言する場合だけ、そのスナップショット自身のカタログとの差分を検査すると定め、
§4.1は、既定値`root`から明示のIDへの写像を、基準版に`multiWorkspace`がない場合だけに使うと定める。
基準版のルートが値の空の宣言を持つとき、修正前のCoreは基準版を「宣言なし」とみなした。カタログ未登録の設定を検査せず、`workspace.id`を省略した基準版のIDを写像した。
ユーザーの決定（2026-10-26）は、基準版でも値の空の宣言を`members: []`と同じ「ルートだけのカタログ」として扱うことである。
この群は、その扱いを、`members: []`の基準版との対照を含めて4件で固定する。

| fixture | 操作と実行ディレクトリ | 原因と期待 |
|---|---|---|
| `MULTI-048-06` | `check --all-workspaces --base HEAD`、`.` | 基準版のルートが`workspace.id: platform`と値の空の`multiWorkspace:`を持ち、カタログ未登録の`apps/web`の設定をコミットしている。現在版は`web`を登録する。`SPEC-MULTI-UNREGISTERED-001`の1件。`blocked`／2 |
| `MULTI-048-07` | `check --all-workspaces --base HEAD`、`.` | 基準版のルートが`workspace.id`を省略し、値の空の`multiWorkspace:`と`approved`のREQ-001を持つ。現在版は`platform`を明示し、`web`を登録する。IDを写像せず、`SPEC-STATE-TRANSITION-001`（`workspaceId`は`root`）の1件。`failed`／1 |
| `MULTI-048-08` | 同上 | 対照: `06`の基準版の`multiWorkspace`が`members: []`。`06`と同じ結果。修正前のCoreも通る |
| `MULTI-048-09` | 同上 | 対照: `07`の基準版の`multiWorkspace`が`members: []`。`07`と同じ結果。修正前のCoreも通る |

基準版はコミット（`baseCommit`）、現在版は作業ツリーの変更（`setup.operations`）で作り、`--base HEAD`で比べる。現在版との差は`revision.dirty: true`に現れる。
共通のREQ-001は、`approved`で規範文`AC-01`、`AC-02`を持つ。

| 種類 | 基準版（コミット） | 現在版（作業ツリー） |
|---|---|---|
| `base-null-unregistered` | ルート`workspace.id: platform`と`multiWorkspace:`（空）。REQ-001。`apps/web`の設定（`id: web`） | ルートが`members`に`web`（`apps/web`）を登録する |
| `base-null-no-id` | ルートが`workspace`なしと`multiWorkspace:`（空）。REQ-001。`apps/web`の設定なし | ルートが`workspace.id: platform`と`members: [web]`、`apps/web`の設定（`id: web`）を足す |
| `base-empty-unregistered`、`base-empty-no-id` | 上の2種で`multiWorkspace`が`members: []` | 上の2種と同じ |

期待値の根拠は規範文と、このモジュールの参照計算だけである（Coreの出力は根拠にしない）。

- 複合ワークスペース仕様 §2.1: 宣言はキー`multiWorkspace`の有無で判定する。§8: 各スナップショット自身のルートの設定が宣言する場合だけ、そのスナップショットのカタログとの差分
  （Gitが認識する`.spec/bitz.yaml`の候補の集合の差）を検査し、差があれば`SPEC-MULTI-UNREGISTERED-001`（`blocked`）とする。全体事前検査の非成功は`workspaces: []`。
- 同 §4.1: ID変更は、旧ワークスペースの削除と新しいワークスペースの追加。既定値`root`から明示のIDへの写像は、基準版に`multiWorkspace`がない場合だけ。
  基準版の値の空の宣言は宣言ありなので、基準版のルートのIDは既定値`root`のまま、現在版の`platform`へ写像しない。旧ワークスペース`root`の管理済みの仕様文書の削除は、
  `SPEC-STATE-TRANSITION-001`（`MULTI-018-01`と同じ形。`workspaceId`は旧ワークスペースのID、`path`はそのワークスペースからの相対）。
- 診断レジストリ: `MULTI-UNREGISTERED`（`SPEC-MULTI-UNREGISTERED-001`、`blocked`）、`STATE-TRANSITION`（`SPEC-STATE-TRANSITION-001`、`failed`）。
- ユーザーの決定（2026-10-26）: 値の空の宣言は`members: []`と同じ。基準版でも、メンバー0件のルートだけのカタログとして扱う（基準版の設定不適合は検査しない。検査するのは現在版だけ）。
- 診断の`summary`は、既存の承認済みの文言（`Gitが認識する設定ファイルがカタログに登録されていません`〈`MULTI-030-02`、`MULTI-006`〉、`管理済みの仕様文書が削除されています`〈`MULTI-018-01`〉）である。
"""
import json
from pathlib import Path
import re
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from .digest_crosscheck import read_yaml
from .harness import git, setup
from .initial_fixtures import compare_state
from .multi_catalog_fixtures import observe_state
from .multi_null_declaration_fixtures import CONFIG_HEAD, load_config, explicit_id
from .schemas import schema_path
from . import multi_reference

HERE = Path(__file__).resolve().parent
COMMIT = "0" * 40
ROOT_CONFIG_PATH = multi_reference.ROOT_CONFIG_PATH
REQ_PATH = multi_reference.ROOT_REQ_PATH
WEB_CONFIG_PATH = multi_reference.WEB_CONFIG_PATH
UNREGISTERED_SUMMARY = "Gitが認識する設定ファイルがカタログに登録されていません"
TRANSITION_SUMMARY = "管理済みの仕様文書が削除されています"
ARGV = ["check", "--all-workspaces", "--base", "HEAD"]

# id: dict(inputs, cause, status, exit, description)。cause: `unregistered`（基準版のカタログ未登録の設定）、`transition`（旧ワークスペースの管理済みの仕様文書の削除）。
CASES = {
    "MULTI-048-06": dict(inputs="base-null-unregistered", cause="unregistered", status="blocked", exit=2,
                         description="基準版のルートの値が空のmultiWorkspaceの宣言を、ルートだけのカタログとして、基準版のカタログ未登録の設定を検出する"),
    "MULTI-048-07": dict(inputs="base-null-no-id", cause="transition", status="failed", exit=1,
                         description="基準版のルートの値が空のmultiWorkspaceの宣言は宣言ありなので、省略したIDをrootから写像せず、旧ワークスペースの削除として検査する"),
    "MULTI-048-08": dict(inputs="base-empty-unregistered", cause="unregistered", status="blocked", exit=2,
                         description="対照: 基準版のルートがmembers: []でも、値が空の宣言と同じく基準版のカタログ未登録の設定を検出する"),
    "MULTI-048-09": dict(inputs="base-empty-no-id", cause="transition", status="failed", exit=1,
                         description="対照: 基準版のルートがmembers: []でも、値が空の宣言と同じく省略したIDを写像せず、旧ワークスペースの削除として検査する"),
}
UNREGISTERED = ("base-null-unregistered", "base-empty-unregistered")
NO_ID = ("base-null-no-id", "base-empty-no-id")
NULL_BASE = ("base-null-unregistered", "base-null-no-id")
CURRENT_ROOT = multi_reference.root_config((("web", "apps/web"),), root_id="platform")


# --- 入力 -------------------------------------------------------------------------------

def base_root_config(inputs):
    head = CONFIG_HEAD if inputs in UNREGISTERED else CONFIG_HEAD.replace("workspace:\n  id: platform\n", "")
    return head + ("multiWorkspace:\n" if inputs in NULL_BASE else "multiWorkspace:\n  members: []\n")


def reviewed_inputs(identifier):
    """`repo/`（基準版）と`changes/`（現在版の差分）の全入力。パス→バイト列。"""
    inputs = CASES[identifier]["inputs"]
    files = {ROOT_CONFIG_PATH: base_root_config(inputs), REQ_PATH: multi_reference.REQ_HEAD + "\n" + multi_reference.REQ_BODY}
    changes = {"bitz.yaml": CURRENT_ROOT}
    if inputs in UNREGISTERED:
        files[WEB_CONFIG_PATH] = multi_reference.plain_config("web")
    else:
        changes["web.yaml"] = multi_reference.plain_config("web")
    return {"files": {name: data.encode() for name, data in files.items()},
            "changes": {name: data.encode() for name, data in changes.items()}}


def reviewed_manifest(identifier):
    case = CASES[identifier]
    operations = [{"op": "update", "path": ROOT_CONFIG_PATH, "source": "changes/bitz.yaml"}]
    if case["inputs"] in NO_ID:
        operations.append({"op": "create", "path": WEB_CONFIG_PATH, "source": "changes/web.yaml"})
    return {
        "fixtureId": identifier,
        "description": case["description"],
        "setup": {"git": True, "baseCommit": {"message": "base", "paths": ["."]}, "operations": operations},
        "invocation": {"runner": "bitz", "cwd": ".", "argv": [*ARGV, "--format", "json"], "env": {}},
        "expect": {"status": case["status"], "exitCode": case["exit"], "stdout": "json",
                   "resultFile": "expected/check.json", "reportFileCount": 0},
    }


# --- レビュー済みの期待結果 -----------------------------------------------------------------

def reviewed_result(identifier):
    case = CASES[identifier]
    result = {"schemaVersion": "1.0", "operation": "check", "scope": "all-workspaces", "status": case["status"],
              "multiWorkspace": {"id": "platform", "path": "."}, "workspaces": [],
              "revision": {"base": COMMIT, "commit": COMMIT, "dirty": True}, "durationMs": 0}
    if case["cause"] == "unregistered":
        # 全体事前検査の停止。基準版でGitが認識する、カタログ未登録の設定。`workspaceId`は`null`。
        result["diagnostics"] = [{"code": "SPEC-MULTI-UNREGISTERED-001", "severity": "error", "resultStatus": "blocked",
                                  "summary": UNREGISTERED_SUMMARY,
                                  "source": {"kind": "file", "workspaceId": None, "path": "apps/web/.spec/bitz.yaml"}}]
        return result
    # 全体事前検査を通過する。現在版のワークスペースは、ルートが先頭、その後はIDの辞書順。件数は現在版の全文書。
    result["workspaces"] = [
        {"id": "platform", "path": ".", "status": "passed", "checkedDocumentCount": 1, "checkedStatementCount": 2, "durationMs": 0, "diagnostics": []},
        {"id": "web", "path": "apps/web", "status": "passed", "checkedDocumentCount": 0, "checkedStatementCount": 0, "durationMs": 0, "diagnostics": []},
    ]
    result["diagnostics"] = [{"code": "SPEC-STATE-TRANSITION-001", "severity": "error", "resultStatus": "failed",
                              "summary": TRANSITION_SUMMARY,
                              "source": {"kind": "file", "workspaceId": "root", "path": ".spec/requirements/REQ-001.md"}}]
    return result


# --- 参照計算 --------------------------------------------------------------------------------

CONFIG_SUFFIX = ".spec/bitz.yaml"
STATEMENT = re.compile(r"^- \[[A-Z]+-[0-9]+:[A-Za-z0-9-]+\]", re.MULTILINE)
MANAGED_DIRECTORIES = ("requirements", "technical", "decisions", "tasks")


def head_text(repository, path):
    return git(repository, "show", f"HEAD:{path}").decode("utf-8")


def head_files(repository):
    output = git(repository, "-c", "core.quotePath=false", "ls-tree", "-r", "--name-only", "HEAD").decode("utf-8")
    return sorted(line for line in output.split("\n") if line)


def workspace_directory(config_path):
    return "." if config_path == CONFIG_SUFFIX else config_path[:-len("/" + CONFIG_SUFFIX)]


def catalog_of(config):
    """スナップショットのルートの設定から、(パス→ID)のカタログを導く。宣言はキーの有無で判定し、値の空の宣言は`members`を持たない（ルートだけ）。

    ルートのIDは、明示した`workspace.id`、なければ既定値`root`（宣言ありの基準版は、現在版のIDへ写像しない。複合ワークスペース仕様 §4.1）。
    """
    declaration = config["multiWorkspace"]
    members = [(item["id"], item["path"]) for item in declaration.get("members", [])] if isinstance(declaration, dict) else []
    return {".": explicit_id(config) or "root", **{path: member_id for member_id, path in members}}


def reference_decision(repository, null_is_undeclared=False):
    """参照計算: コミットした基準版と作業ツリーの現在版から、全体事前検査の停止と、旧ワークスペースの削除を導く（複合ワークスペース仕様 §2.1・§4.1・§8）。

    `null_is_undeclared`は修正前のCoreの読み方の再現: 値の空の宣言を宣言なしとみなし、カタログとの差分を検査せず、省略したIDを写像する。
    """
    base_root = read_yaml(head_text(repository, ROOT_CONFIG_PATH))
    if "multiWorkspace" not in base_root:
        raise ValueError("基準版のルートの設定が`multiWorkspace`を宣言する必要があります")
    current_root = load_config(repository, ".")
    if "multiWorkspace" not in current_root or explicit_id(current_root) is None:
        raise ValueError("現在版は`workspace.id`を明示した複合ワークスペースのルートである必要があります")
    current = catalog_of(current_root)
    if null_is_undeclared and base_root["multiWorkspace"] == {}:
        # 宣言なしの基準版: 候補の不存在保証をさかのぼって適用せず、既定値`root`を現在版のルートのIDへ写像する。
        return {"cause": None, "unregistered": [], "removed": {}, "current": current}
    base = catalog_of(base_root)
    unregistered = [path for path in (workspace_directory(name) for name in head_files(repository) if name.endswith(CONFIG_SUFFIX))
                    if path not in base]
    if unregistered:
        return {"cause": "unregistered", "unregistered": sorted(f"{path}/{CONFIG_SUFFIX}" for path in unregistered), "removed": {}, "current": current}
    # 基準版にあって現在版にないワークスペースID。そのワークスペースの管理済み（状態が`draft`でない）の仕様文書の削除。
    removed = {}
    for path, workspace_id in base.items():
        if workspace_id in current.values():
            continue
        prefix = "" if path == "." else path + "/"
        for name in head_files(repository):
            if any(name.startswith(f"{prefix}.spec/{directory}/") for directory in MANAGED_DIRECTORIES) and name.endswith(".md"):
                status = re.search(r"^status: (\S+)$", head_text(repository, name), re.MULTILINE)
                if status and status.group(1) != "draft":
                    removed.setdefault(workspace_id, []).append(name[len(prefix):])
    return {"cause": "transition" if removed else None, "unregistered": [], "removed": removed, "current": current}


def current_counts(repository, directory):
    """現在版のワークスペースの全文書の数と規範文の数（作業ツリー）。"""
    root = repository / directory / ".spec"
    documents = [path for kind in MANAGED_DIRECTORIES if (root / kind).is_dir() for path in sorted((root / kind).glob("*.md"))]
    return len(documents), sum(len(STATEMENT.findall(path.read_text(encoding="utf-8"))) for path in documents)


def check_against_reference(identifier, result, reference, repository):
    """リテラルの期待値が、参照計算と一致することを要求する。"""
    case = CASES[identifier]
    if reference["cause"] != case["cause"]:
        raise ValueError("停止の原因が入力からの参照計算と異なります")
    diagnostics = result["diagnostics"]
    if case["cause"] == "unregistered":
        expected = [("SPEC-MULTI-UNREGISTERED-001", "blocked", None, path) for path in reference["unregistered"]]
        if result["workspaces"] != [] or result["status"] != "blocked":
            raise ValueError("全体事前検査の停止は`blocked`で`workspaces`を空にします")
    else:
        expected = [("SPEC-STATE-TRANSITION-001", "failed", workspace_id, path)
                    for workspace_id in sorted(reference["removed"]) for path in sorted(reference["removed"][workspace_id])]
        if result["status"] != "failed":
            raise ValueError("旧ワークスペースの削除は`failed`です")
        # 全体事前検査を通過するので、現在版のワークスペースをルート、IDの辞書順に並べ、文書数と規範文の数は作業ツリーの全文書から導く。
        current = reference["current"]
        order = [(".", current["."])] + sorted(((path, workspace_id) for path, workspace_id in current.items() if path != "."), key=lambda item: item[1])
        wanted = [{"id": workspace_id, "path": path, "status": "passed", "checkedDocumentCount": current_counts(repository, path)[0],
                   "checkedStatementCount": current_counts(repository, path)[1], "durationMs": 0, "diagnostics": []} for path, workspace_id in order]
        if result["workspaces"] != wanted:
            raise ValueError("`workspaces`が入力からの参照計算と異なります")
    if [(item["code"], item["resultStatus"], item["source"]["workspaceId"], item["source"]["path"]) for item in diagnostics] != expected:
        raise ValueError("診断が入力からの参照計算と異なります")
    summary = UNREGISTERED_SUMMARY if case["cause"] == "unregistered" else TRANSITION_SUMMARY
    if any(item["summary"] != summary or "key" in item["source"] or item["source"]["kind"] != "file" for item in diagnostics):
        raise ValueError("診断の文言、発生元が入力からの参照計算と異なります")
    if result["multiWorkspace"] != {"id": reference["current"]["."], "path": "."} or "workspace" in result:
        raise ValueError("`multiWorkspace`が入力からの参照計算と異なります")


def git_dirty(repository):
    return bool(git(repository, "status", "--porcelain=v1", "--untracked-files=all").strip())


def check_conditions(identifier, repository):
    """原因の構成を、散文ではなく準備手順の後のコミットと作業ツリーから確かめる。"""
    inputs = CASES[identifier]["inputs"]
    if not (repository / ".git").exists():
        raise ValueError("Gitのリポジトリが必要です")
    if not git_dirty(repository) or len(git(repository, "rev-list", "HEAD").split()) != 1:
        raise ValueError("基準版の1コミットと、変更した作業ツリー（現在版）が必要です")
    reference = reference_decision(repository)
    base_text = head_text(repository, ROOT_CONFIG_PATH)
    base_root = read_yaml(base_text)
    # 基準版: `multiWorkspace`が、キーだけの1行（値なし）、または`members: []`。どちらも`workspace`の有無以外は同じ。
    if inputs in NULL_BASE and (base_root["multiWorkspace"] != {} or not base_text.endswith("multiWorkspace:\n")):
        raise ValueError("基準版の`multiWorkspace`は、キーだけで値のない宣言である必要があります")
    if inputs not in NULL_BASE and base_root["multiWorkspace"] != {"members": []}:
        raise ValueError("対照の基準版の`multiWorkspace`は`members: []`である必要があります")
    base_files = head_files(repository)
    if inputs in UNREGISTERED:
        if explicit_id(base_root) != "platform" or "apps/web/.spec/bitz.yaml" not in base_files:
            raise ValueError("基準版は`workspace.id: platform`を明示し、カタログ未登録の`apps/web`の設定をコミットする必要があります")
    else:
        if "workspace" in base_root or "apps/web/.spec/bitz.yaml" in base_files:
            raise ValueError("基準版は`workspace`を持たず、`apps/web`の設定を持ってはいけません")
        if ".spec/requirements/REQ-001.md" not in base_files or "status: approved" not in head_text(repository, ".spec/requirements/REQ-001.md"):
            raise ValueError("基準版は`approved`のREQ-001を持つ必要があります")
    # 現在版: ルートが`workspace.id: platform`を明示して`web`（`apps/web`）を登録し、`web`の設定が実在する。
    current_root = load_config(repository, ".")
    web = load_config(repository, "apps/web")
    if explicit_id(current_root) != "platform" or current_root["multiWorkspace"] != {"members": [{"id": "web", "path": "apps/web"}]}:
        raise ValueError("現在版のルートは`workspace.id: platform`を明示し、メンバー`web`だけを登録する必要があります")
    if explicit_id(web) != "web" or "multiWorkspace" in web:
        raise ValueError("現在版の`apps/web`の設定は`workspace.id: web`を持ち、`multiWorkspace`を宣言してはいけません")
    return reference


# --- 生成と監査 ---------------------------------------------------------------------------------

def _dump(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def generate(root=HERE):
    """レビュー済みの入力と期待値からfixtureを書き出す。副作用の期待値は、隔離した準備手順の観測で作る（Coreは実行しない）。"""
    for identifier in CASES:
        fixture = root / "multi" / identifier
        inputs = reviewed_inputs(identifier)
        for directory, files in (("repo", inputs["files"]), ("changes", inputs["changes"])):
            for name, content in files.items():
                path = fixture / directory / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
        manifest = reviewed_manifest(identifier)
        (fixture / "manifest.json").write_text(_dump(manifest))
        (fixture / "expected").mkdir(parents=True, exist_ok=True)
        (fixture / "expected/check.json").write_text(_dump(reviewed_result(identifier)))
        with tempfile.TemporaryDirectory(prefix="bitz-multi-null-base-") as temporary:
            sandbox = Path(temporary)
            repository = setup(fixture, manifest, sandbox / "repo")
            external = {name: sandbox / name for name in ("home", "cache", "temporary")}
            for path in external.values():
                path.mkdir()
            state = observe_state(manifest, repository, external)
        (fixture / "side-effects.json").write_text(
            _dump({"schemaVersion": "1.0", "policy": "read-only", "before": state, "after": state}))


def validate(root=HERE, identifiers=None):
    errors, prepared = [], []
    validators = {name: Draft202012Validator(json.loads(schema_path(root, name).read_text()))
                  for name in ("manifest", "result", "side-effects")}
    for identifier in CASES:
        if identifiers is not None and identifier not in identifiers:
            continue
        fixture = root / "multi" / identifier
        try:
            manifest = json.loads((fixture / "manifest.json").read_text())
            result = json.loads((fixture / "expected/check.json").read_text())
            effects = json.loads((fixture / "side-effects.json").read_text())
            for key, value in (("manifest", manifest), ("result", result), ("side-effects", effects)):
                validators[key].validate(value)
            if manifest != reviewed_manifest(identifier):
                raise ValueError("起動条件がレビュー済みの期待値と異なります")
            if result != reviewed_result(identifier):
                raise ValueError("完全結果がレビュー済みの期待値と異なります")
            reviewed = reviewed_inputs(identifier)
            entries = {}
            for directory in ("repo", "changes"):
                for path in (fixture / directory).rglob("*"):
                    if path.is_symlink() or path.is_file():
                        entries[(directory, path.relative_to(fixture / directory).as_posix())] = (
                            None if path.is_symlink() else path.read_bytes())
            expected = {**{("repo", name): data for name, data in reviewed["files"].items()},
                        **{("changes", name): data for name, data in reviewed["changes"].items()}}
            if entries != expected:
                raise ValueError("入力がレビュー済みのcorpusと異なります")
            if (fixture / "cli-output.json").exists():
                raise ValueError("このfixtureは`cli-output.json`を持ちません")
            if effects["policy"] != "read-only" or effects["before"] != effects["after"]:
                raise ValueError("読取り専用の期待値が書込みを許しています")
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-multi-null-base-") as temporary:
                for run in range(2):
                    sandbox = Path(temporary) / str(run)
                    sandbox.mkdir()
                    repository = setup(fixture, manifest, sandbox / "repo")
                    external = {key: sandbox / key for key in ("home", "cache", "temporary")}
                    for path in external.values():
                        path.mkdir()
                    actual = observe_state(manifest, repository, external)
                    if compare_state(effects["before"], actual) or (previous is not None and previous != actual):
                        raise ValueError("隔離した準備手順が固定したスナップショットと異なります")
                    previous = actual
                    reference = check_conditions(identifier, repository)
                    check_against_reference(identifier, result, reference, repository)
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, IndexError, ValidationError,
                subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "references": 1, "status": "Passed" if not errors else "Failed", "errors": errors}
