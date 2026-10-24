"""複合ワークスペースのルートとメンバーの`workspace.id`の省略を、既定値`root`で通さないことを固定する（Coreの公開操作は実行しない）。

実装の確認事項C42とADR-051の追加に対応する。複合ワークスペース仕様 §2は、ルートワークスペースと全メンバーで`workspace.id`を必須とし、
カタログの`id`とメンバー設定の`workspace.id`を一致させると定める。§4.1は、既定値`root`を`multiWorkspace`のない基準版の写像だけに限る。
修正前のCoreは、ルートの`.spec/bitz.yaml`が`workspace.id`を省略しても既定値`root`をルートのIDとして成功し、
メンバーが省略してカタログの`id`が`root`のときも一致とみなした。この群は、その停止と、停止しない境界を12件で固定する。

| fixture | 操作と実行ディレクトリ | 原因と期待 |
|---|---|---|
| `MULTI-043-01` | `check --all-workspaces --base HEAD`、`.` | ルートが`workspace.id`を省略。`SPEC-MULTI-CONFIG-001`の1件、`multiWorkspace`は`{null, .}`、`workspaces`は空。`failed`／1 |
| `MULTI-043-02` | `verify --all-workspaces`、`.` | 同じ入力。`verify`の全体の停止結果 |
| `MULTI-043-03` | `doctor --all-workspaces`、`.` | 同じ入力。`catalog`が`failed`、`suggestedAction`なし |
| `MULTI-043-04` | `check --base HEAD`、`.` | 同じ入力の単独の`check`。`workspace`は`{null, .}` |
| `MULTI-043-05` | `check --base HEAD`、`apps/web` | 同じ入力のメンバーからの単独の`check`。メンバーは明示したIDがカタログと一致するので`workspace`は`{web, apps/web}` |
| `MULTI-043-06` | `verify`、`.` | 同じ入力の単独の`verify` |
| `MULTI-043-07` | `doctor`、`.` | 同じ入力の単独の`doctor` |
| `MULTI-043-08` | `check --all-workspaces --base HEAD`、`.` | ルートの省略に、メンバー`api`の設定の不在と未登録の設定が重なる。`SPEC-MULTI-CONFIG-001`の1件だけ |
| `MULTI-043-09` | `check --all-workspaces --base HEAD`、`.` | ルートの省略に、メンバー`web`のIDの不一致が重なる。`SPEC-MULTI-CONFIG-001`の1件だけ |
| `MULTI-043-10` | `check --all-workspaces --base HEAD`、`.` | メンバーが省略し、カタログの`id`が`root`。ルートは明示。`SPEC-MULTI-MEMBER-001`の1件、`multiWorkspace`は`{platform, .}` |
| `MULTI-043-11` | `check --base HEAD`、`apps/web` | 同じ入力のメンバーからの単独の`check`。省略したIDはカタログのIDと一致しないので`workspace`は`{null, apps/web}` |
| `MULTI-043-12` | `check --all-workspaces --base HEAD`、`.` | 対照: ルートが`workspace.id: root`を明示すれば成功する |

基本のリポジトリは、ルート（`.`）、メンバー`web`（`apps/web`）と`api`（`services/api`）である。入力の種類は次のとおりである。

| 種類 | 内容 |
|---|---|
| `root-omitted` | ルートの設定が`workspace`を持たない。メンバーは`id: web`、`id: api`を明示し、カタログのIDと一致する |
| `root-omitted-member-absent` | `root-omitted`から`services/api/.spec/bitz.yaml`を除き（ディレクトリは残す）、カタログ未登録の`tools/x/.spec/bitz.yaml`を足す |
| `root-omitted-id-mismatch` | `root-omitted`で、`web`の設定の`id`をカタログと異なる`frontend`にする |
| `member-omitted` | ルートは`id: platform`を明示。カタログの`id`が`root`のメンバー（`apps/web`）の設定が`workspace`を持たない |
| `explicit-root` | ルートが`id: root`を明示する対照。メンバー`web`、`api`は`MULTI-001`と同じ入力 |

期待値の根拠は規範文と、このモジュールの参照計算だけである（Coreの出力は根拠にしない）。

- 複合ワークスペース仕様 §2: ルートワークスペースと全メンバーで`workspace.id`を必須とする。カタログの`id`とメンバー設定の`workspace.id`は一致させる。
  §4.1: 既定値`root`は`multiWorkspace`のない基準版の写像だけ。
- 診断レジストリ: `MULTI-CONFIG`（`SPEC-MULTI-CONFIG-001`、`error`／`failed`、`stop-multi-workspace`、900、「ルートの条件」）、
  `MULTI-MEMBER`（`SPEC-MULTI-MEMBER-001`、910、「カタログのIDと不一致」）。
- 結果・診断・終了コード §2: 有効なルートワークスペースのIDを構成できない全体結果は`multiWorkspace`を`{"id": null, "path": "."}`、`workspaces`を空配列にする。
  停止した単独結果の`workspace.id`は、ルートでは明示した有効なIDを持つときだけ、メンバーではカタログのIDと一致するときだけそのID、それ以外は`null`。
  §5: ルートのIDの不正で同一性を構成できない診断の`source.workspaceId`は`null`。
- ユーザーの決定（2026-10-20、2026-10-25）: ルートの省略は全体事前検査で`SPEC-MULTI-CONFIG-001`の1件だけで単独に止める（ほかのカタログの不備より優先）。
  `summary`は管理者が承認した文言（`Coreの出力文言のレビュー記録.md`）。`source`は`{"kind": "file", "workspaceId": null, "path": ".spec/bitz.yaml", "key": "workspace.id"}`。
  メンバーの省略は、既存の承認済みの文言の`SPEC-MULTI-MEMBER-001`。
- `doctor` §3の`catalog`は`failed`。`suggestedAction`は付けない（`doctor`仕様 §8の表の診断ではない）。終了コードは`failed`なので1。
"""
import json
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from .digest_crosscheck import read_yaml
from .harness import git, setup
from .initial_fixtures import compare_state
from .multi_catalog_fixtures import observe_state
from .schemas import schema_path
from . import multi_identity_fixtures, multi_reference

HERE = Path(__file__).resolve().parent
COMMIT = "0" * 40
CAPABILITIES = ["context.v1", "check.v1", "verify.v1", "doctor.v1", "multiWorkspace.v1"]
CORE = {"version": "1.0.0", "apiVersion": "1.0", "capabilities": CAPABILITIES}
ROOT_CONFIG_PATH = multi_reference.ROOT_CONFIG_PATH
WEB_CONFIG_PATH = multi_reference.WEB_CONFIG_PATH
API_CONFIG_PATH = multi_reference.API_CONFIG_PATH
API_SOURCE_PATH = "services/api/src/session.py"
TOOLS_CONFIG_PATH = "tools/x/.spec/bitz.yaml"
MEMBERS = (("web", "apps/web"), ("api", "services/api"))

# 承認済みの診断の文言。`Coreの出力文言のレビュー記録.md`（2026-10-25の1件と、2026-10-12の既存の文言）。
ROOT_ID_REQUIRED = "ルートワークスペースの設定キーworkspace.idがありません"
MEMBER_ID_MISMATCH = "メンバーの設定キーworkspace.idがカタログのIDと一致しません"

# id: dict(op, scope, cwd, argv〈`--format json`の前〉, inputs, cause, status, exit, description)
# scope: `all`は`--all-workspaces`、`single`は単独の操作。cause: `root-id`、`member-id`、`None`（成功）。
CASES = {
    "MULTI-043-01": dict(op="check", scope="all", cwd=".", argv=["check", "--all-workspaces", "--base", "HEAD"], inputs="root-omitted",
                         cause="root-id", status="failed", exit=1,
                         description="ルートがworkspace.idを省略した複合ワークスペースのcheck --all-workspacesを既定値rootで通さない"),
    "MULTI-043-02": dict(op="verify", scope="all", cwd=".", argv=["verify", "--all-workspaces"], inputs="root-omitted",
                         cause="root-id", status="failed", exit=1,
                         description="ルートがworkspace.idを省略した複合ワークスペースのverify --all-workspacesを既定値rootで通さない"),
    "MULTI-043-03": dict(op="doctor", scope="all", cwd=".", argv=["doctor", "--all-workspaces"], inputs="root-omitted",
                         cause="root-id", status="failed", exit=1,
                         description="ルートがworkspace.idを省略した複合ワークスペースのdoctor --all-workspacesを既定値rootで通さない"),
    "MULTI-043-04": dict(op="check", scope="single", cwd=".", argv=["check", "--base", "HEAD"], inputs="root-omitted",
                         cause="root-id", status="failed", exit=1,
                         description="ルートがworkspace.idを省略した複合ワークスペースのルートからの単独のcheckを、同一性を構成せずに止める"),
    "MULTI-043-05": dict(op="check", scope="single", cwd="apps/web", argv=["check", "--base", "HEAD"], inputs="root-omitted",
                         cause="root-id", status="failed", exit=1,
                         description="ルートがworkspace.idを省略した複合ワークスペースのメンバーからの単独のcheckを、メンバーの同一性を保って止める"),
    "MULTI-043-06": dict(op="verify", scope="single", cwd=".", argv=["verify"], inputs="root-omitted",
                         cause="root-id", status="failed", exit=1,
                         description="ルートがworkspace.idを省略した複合ワークスペースのルートからの単独のverifyを、同一性を構成せずに止める"),
    "MULTI-043-07": dict(op="doctor", scope="single", cwd=".", argv=["doctor"], inputs="root-omitted",
                         cause="root-id", status="failed", exit=1,
                         description="ルートがworkspace.idを省略した複合ワークスペースのルートからの単独のdoctorを、同一性を構成せずに止める"),
    "MULTI-043-08": dict(op="check", scope="all", cwd=".", argv=["check", "--all-workspaces", "--base", "HEAD"],
                         inputs="root-omitted-member-absent", cause="root-id", status="failed", exit=1,
                         description="ルートの省略に、メンバーの設定の不在と未登録の設定が重なっても、ルートの省略の1件だけで止める"),
    "MULTI-043-09": dict(op="check", scope="all", cwd=".", argv=["check", "--all-workspaces", "--base", "HEAD"],
                         inputs="root-omitted-id-mismatch", cause="root-id", status="failed", exit=1,
                         description="ルートの省略に、メンバーのIDの不一致が重なっても、ルートの省略の1件だけで止める"),
    "MULTI-043-10": dict(op="check", scope="all", cwd=".", argv=["check", "--all-workspaces", "--base", "HEAD"],
                         inputs="member-omitted", cause="member-id", status="failed", exit=1,
                         description="メンバーがworkspace.idを省略したとき、カタログのIDがrootでも一致とみなさない"),
    "MULTI-043-11": dict(op="check", scope="single", cwd="apps/web", argv=["check", "--base", "HEAD"], inputs="member-omitted",
                         cause="member-id", status="failed", exit=1,
                         description="IDを省略したメンバーからの単独のcheckを、カタログのIDと一致しないので同一性を構成せずに止める"),
    "MULTI-043-12": dict(op="check", scope="all", cwd=".", argv=["check", "--all-workspaces", "--base", "HEAD"], inputs="explicit-root",
                         cause=None, status="passed", exit=0,
                         description="ルートがworkspace.id: rootを明示すれば複合ワークスペースとして成功する"),
}
RESULT_FILES = {"check": "expected/check.json", "verify": "expected/verify.json", "doctor": "expected/doctor.json"}
ROOT_OMITTED = ("root-omitted", "root-omitted-member-absent", "root-omitted-id-mismatch")


# --- 入力 -------------------------------------------------------------------------------

def root_config(inputs):
    """カタログのルートの設定。`root-omitted`系は`workspace`を持たない。"""
    members = MEMBERS
    if inputs == "member-omitted":
        members = (("root", "apps/web"), ("api", "services/api"))
    text = multi_reference.root_config(members, root_id="platform")
    if inputs in ROOT_OMITTED:
        text = text.replace("workspace:\n  id: platform\n", "", 1)
    if inputs == "explicit-root":
        text = text.replace("id: platform\n", "id: root\n", 1)
    return text


def root_requirement():
    return multi_reference.REQ_HEAD + "\n" + multi_reference.REQ_BODY


def reviewed_inputs(identifier):
    """`repo/`の全入力。パス→バイト列。"""
    inputs = CASES[identifier]["inputs"]
    if inputs == "explicit-root":
        # `MULTI-001`の入力のルートのIDだけを`root`にする（修飾した参照も`root::`へ）。
        files = {path: data.decode().replace("platform", "root").encode() for path, data in multi_reference.reviewed_inputs().items()}
        return files
    files = {
        ROOT_CONFIG_PATH: root_config(inputs),
        multi_reference.ROOT_REQ_PATH: root_requirement(),
        WEB_CONFIG_PATH: multi_reference.plain_config("frontend" if inputs == "root-omitted-id-mismatch" else "web"),
        API_CONFIG_PATH: multi_reference.plain_config("api"),
    }
    if inputs == "member-omitted":
        # メンバー`apps/web`の設定は`workspace`を持たない。
        files[WEB_CONFIG_PATH] = 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\n'
    if inputs == "root-omitted-member-absent":
        # メンバー`api`のディレクトリは実在し、設定は存在しない。カタログにないGit追跡の設定を足す。
        del files[API_CONFIG_PATH]
        files[API_SOURCE_PATH] = multi_reference.CODE_FILES[API_SOURCE_PATH]
        files[TOOLS_CONFIG_PATH] = multi_reference.plain_config("x")
    return {name: data.encode() if isinstance(data, str) else data for name, data in files.items()}


def reviewed_manifest(identifier):
    case = CASES[identifier]
    return {
        "fixtureId": identifier,
        "description": case["description"],
        "setup": {"git": True, "baseCommit": {"message": "base", "paths": ["."]}, "operations": []},
        "invocation": {"runner": "bitz", "cwd": case["cwd"], "argv": [*case["argv"], "--format", "json"], "env": {}},
        "expect": {"status": case["status"], "exitCode": case["exit"], "stdout": "json",
                   "resultFile": RESULT_FILES[case["op"]], "reportFileCount": 0},
    }


# --- レビュー済みの期待結果 -----------------------------------------------------------------

def diagnostic(identifier):
    cause = CASES[identifier]["cause"]
    if cause == "root-id":
        return {"code": "SPEC-MULTI-CONFIG-001", "severity": "error", "resultStatus": "failed", "summary": ROOT_ID_REQUIRED,
                "source": {"kind": "file", "workspaceId": None, "path": ".spec/bitz.yaml", "key": "workspace.id"}}
    # 発生元は、メンバーの設定そのものではなく、カタログの宣言（ルートの`multiWorkspace.members`）である
    # （`MULTI-036-03`のメンバーの不在の診断と同じ。ルートのIDは明示されているので`workspaceId`は`platform`）。
    return {"code": "SPEC-MULTI-MEMBER-001", "severity": "error", "resultStatus": "failed", "summary": MEMBER_ID_MISMATCH,
            "source": {"kind": "file", "workspaceId": "platform", "path": ".spec/bitz.yaml", "key": "multiWorkspace.members"}}


def multi_workspace(identifier):
    return {"id": None if CASES[identifier]["cause"] == "root-id" else "platform", "path": "."}


# 単独の操作の`workspace`。ルートでは明示した有効なIDを持つときだけそのID、メンバーではカタログのIDと一致するときだけそのID、それ以外は`null`。
SINGLE_WORKSPACES = {
    "MULTI-043-04": {"id": None, "path": "."}, "MULTI-043-05": {"id": "web", "path": "apps/web"},
    "MULTI-043-06": {"id": None, "path": "."}, "MULTI-043-07": {"id": None, "path": "."},
    "MULTI-043-11": {"id": None, "path": "apps/web"},
}


def stopped_checks(status):
    return [{"name": "core", "status": "passed"}, {"name": "git", "status": "passed"}, {"name": "catalog", "status": status}]


def reviewed_check_result(identifier):
    case = CASES[identifier]
    revision = {"base": COMMIT, "commit": COMMIT, "dirty": False}
    if case["cause"] is None:
        result = multi_identity_fixtures.all_workspaces_result("MULTI-001")
        return json.loads(json.dumps(result).replace("platform", "root"))
    if case["scope"] == "all":
        return {"schemaVersion": "1.0", "operation": "check", "scope": "all-workspaces", "status": "failed",
                "multiWorkspace": multi_workspace(identifier), "workspaces": [], "revision": revision, "durationMs": 0,
                "diagnostics": [diagnostic(identifier)]}
    # 引数なしの単独の`check`は`scope: changed`。処理を始める前の停止なので件数は0。
    return {"schemaVersion": "1.0", "operation": "check", "scope": "changed", "status": "failed",
            "workspace": dict(SINGLE_WORKSPACES[identifier]), "revision": revision, "durationMs": 0,
            "selection": {"changedPathCount": 0, "targetDocumentCount": 0, "excludedCodeTestPathCount": 0},
            "diagnostics": [diagnostic(identifier)]}


def reviewed_verify_result(identifier):
    revision = {"commit": COMMIT, "dirty": False}
    if CASES[identifier]["scope"] == "all":
        return {"schemaVersion": "1.0", "operation": "verify", "scope": "all-workspaces", "status": "failed",
                "multiWorkspace": multi_workspace(identifier), "workspaces": [], "revision": revision, "durationMs": 0,
                "diagnostics": [diagnostic(identifier)]}
    return {"schemaVersion": "1.0", "operation": "verify", "scope": "all", "status": "failed",
            "workspace": dict(SINGLE_WORKSPACES[identifier]), "targetResults": [], "revision": revision, "commands": [],
            "durationMs": 0, "diagnostics": [diagnostic(identifier)]}


def reviewed_doctor_result(identifier):
    result = {"schemaVersion": "1.0", "operation": "doctor", "status": "failed", "core": json.loads(json.dumps(CORE)),
              "checks": stopped_checks("failed"), "durationMs": 0, "diagnostics": [diagnostic(identifier)]}
    if CASES[identifier]["scope"] == "all":
        return {**result, "multiWorkspace": multi_workspace(identifier), "workspaces": []}
    return {**result, "workspace": dict(SINGLE_WORKSPACES[identifier])}


def reviewed_result(identifier):
    return {"check": reviewed_check_result, "verify": reviewed_verify_result,
            "doctor": reviewed_doctor_result}[CASES[identifier]["op"]](identifier)


# --- 参照計算 --------------------------------------------------------------------------------

def load_config(repository, directory):
    path = repository / directory / ".spec/bitz.yaml"
    return read_yaml(path.read_text(encoding="utf-8")) if path.is_file() else None


def explicit_id(config):
    """設定が明示した`workspace.id`。省略は`None`（既定値`root`は明示のIDではない）。"""
    workspace = config.get("workspace") if config is not None else None
    value = workspace.get("id") if isinstance(workspace, dict) else None
    return value if isinstance(value, str) else None


def nearest_directory(repository, cwd):
    """複合ワークスペース仕様 §3の手順2: 現在のディレクトリからリポジトリのルートへ探索して、最も近い設定のディレクトリを返す。"""
    current = Path(cwd)
    while True:
        if (repository / current / ".spec/bitz.yaml").is_file():
            return current.as_posix()
        if current.as_posix() == ".":
            raise ValueError("最も近い設定がありません")
        current = current.parent


def reference_decision(repository, cwd):
    """参照計算: 入力の木構造から、全体事前検査の停止の原因、ルートのID、停止結果の`workspace`を導く（複合ワークスペース仕様 §2・§4.1・§7、結果・診断・終了コード §2）。

    原因は`root-id`（ルートが`workspace.id`を省略）、`member-id`（メンバーの設定が`workspace.id`を省略、またはカタログのIDと不一致）、`None`。
    ルートの省略は、ほかのカタログの不備より先に判定する（ユーザーの決定）。
    """
    root = load_config(repository, ".")
    if root is None or "multiWorkspace" not in root:
        raise ValueError("複合ワークスペースのルートの設定が必要です")
    members = [(item["id"], item["path"]) for item in root["multiWorkspace"]["members"]]
    root_id = explicit_id(root)
    cause = None
    if root_id is None:
        cause = "root-id"
    else:
        for member_id, path in members:
            config = load_config(repository, path)
            # メンバーの設定の不在は`SPEC-MULTI-MEMBER-001`の別の原因である。この群は扱わない。
            if config is not None and explicit_id(config) != member_id:
                cause = "member-id"
                break
    nearest = nearest_directory(repository, cwd)
    registered = dict((path, member_id) for member_id, path in members)
    if nearest == ".":
        workspace_id = root_id
    elif nearest in registered and explicit_id(load_config(repository, nearest)) == registered[nearest]:
        workspace_id = registered[nearest]
    else:
        workspace_id = None
    return {"cause": cause, "multiWorkspaceId": root_id, "workspace": {"id": workspace_id, "path": nearest}}


def check_against_reference(identifier, result, reference):
    """リテラルの期待値が、参照計算と一致することを要求する。"""
    case = CASES[identifier]
    if reference["cause"] != case["cause"]:
        raise ValueError("停止の原因が入力からの参照計算と異なります")
    if case["cause"] is None:
        if result["status"] != "passed" or result["diagnostics"]:
            raise ValueError("対照は診断を持たず通ります")
        if result["multiWorkspace"] != {"id": reference["multiWorkspaceId"], "path": "."}:
            raise ValueError("`multiWorkspace`が入力からの参照計算と異なります")
        return
    code = "SPEC-MULTI-CONFIG-001" if case["cause"] == "root-id" else "SPEC-MULTI-MEMBER-001"
    if [(item["code"], item["resultStatus"]) for item in result["diagnostics"]] != [(code, "failed")] or result["status"] != "failed":
        raise ValueError("診断または状態が停止の原因と異なります")
    summary = ROOT_ID_REQUIRED if case["cause"] == "root-id" else MEMBER_ID_MISMATCH
    source = result["diagnostics"][0]["source"]
    expected_workspace_id = None if case["cause"] == "root-id" else reference["multiWorkspaceId"]
    if result["diagnostics"][0]["summary"] != summary or source["workspaceId"] != expected_workspace_id:
        raise ValueError("診断の文言、発生元が入力からの参照計算と異なります")
    if case["scope"] == "all":
        # 有効なルートのIDを構成できないときだけ`multiWorkspace.id`は`null`。`workspaces`は空配列。
        if result["multiWorkspace"] != {"id": reference["multiWorkspaceId"], "path": "."} or result["workspaces"] != []:
            raise ValueError("`multiWorkspace`または`workspaces`が入力からの参照計算と異なります")
        if "workspace" in result:
            raise ValueError("`--all-workspaces`の結果は`workspace`を持ちません")
    else:
        if result["workspace"] != reference["workspace"] or "multiWorkspace" in result or "workspaces" in result:
            raise ValueError("`workspace`が入力からの参照計算と異なります")
    if case["op"] == "doctor" and ([item["name"] for item in result["checks"]] != ["core", "git", "catalog"]
                                   or result["checks"][2]["status"] != "failed" or "suggestedAction" in result["diagnostics"][0]):
        raise ValueError("`doctor`の検査項目が全体事前検査の停止結果と異なります")
    if case["op"] == "verify" and case["scope"] == "single" and (result["targetResults"] or result["commands"]):
        raise ValueError("停止した`verify`は検証対象もコマンドも持ちません")


def git_dirty(repository):
    return bool(git(repository, "status", "--porcelain=v1", "--untracked-files=all").strip())


def check_conditions(identifier, repository):
    """原因の構成を、散文ではなく準備手順の後の入力とGitの状態から確かめる。原因以外のカタログの不備を持たないことも要求する。"""
    case = CASES[identifier]
    inputs = case["inputs"]
    if not (repository / ".git").exists():
        raise ValueError("Gitのリポジトリが必要です")
    if git_dirty(repository):
        raise ValueError("このfixtureの作業ツリーはコミット済みと同じである必要があります")
    reference = reference_decision(repository, case["cwd"])
    root = load_config(repository, ".")
    members = [(item["id"], item["path"]) for item in root["multiWorkspace"]["members"]]
    web = load_config(repository, "apps/web")
    api = load_config(repository, "services/api")
    if inputs in ROOT_OMITTED:
        # ルートの省略。`workspace`キーそのものを持たない（`workspace: {}`などの別の形ではない）。
        if "workspace" in root:
            raise ValueError("ルートの設定が`workspace`を持ってはいけません")
        if {path for _, path in members} != {"apps/web", "services/api"}:
            raise ValueError("カタログはメンバー`web`、`api`を宣言する必要があります")
    if inputs == "root-omitted":
        # 修正前のCoreが成功する構成: 原因はルートの省略だけで、メンバーは明示したIDがカタログと一致する。
        if explicit_id(web) != "web" or explicit_id(api) != "api" or dict(members) != {"web": "apps/web", "api": "services/api"}:
            raise ValueError("メンバーは明示したIDがカタログのIDと一致する必要があります")
        if git(repository, "ls-files", "--", TOOLS_CONFIG_PATH).strip():
            raise ValueError("未登録の設定を持ってはいけません")
    if inputs == "root-omitted-member-absent":
        if api is not None or not (repository / "services/api").is_dir() or explicit_id(web) != "web":
            raise ValueError("メンバー`api`のディレクトリは実在し、設定は存在しない必要があります")
        if not git(repository, "ls-files", "--", TOOLS_CONFIG_PATH).strip() or TOOLS_CONFIG_PATH.removesuffix("/.spec/bitz.yaml") in {path for _, path in members}:
            raise ValueError("カタログにない設定がGitで追跡されている必要があります")
    if inputs == "root-omitted-id-mismatch":
        if explicit_id(web) != "frontend" or dict(members)["web"] != "apps/web" or explicit_id(api) != "api":
            raise ValueError("メンバー`web`の明示したIDだけがカタログのIDと異なる必要があります")
    if inputs == "member-omitted":
        if explicit_id(root) != "platform" or ("root", "apps/web") not in members or explicit_id(api) != "api":
            raise ValueError("ルートは明示し、カタログのIDが`root`のメンバーだけが省略する必要があります")
        if web is None or "workspace" in web:
            raise ValueError("メンバー`apps/web`の設定が`workspace`を持ってはいけません")
    if inputs == "explicit-root":
        if explicit_id(root) != "root" or explicit_id(web) != "web" or explicit_id(api) != "api":
            raise ValueError("対照は、ルートが`workspace.id: root`を明示し、メンバーも明示する必要があります")
    if case["scope"] == "single" and case["cwd"] != nearest_directory(repository, case["cwd"]):
        raise ValueError("単独の操作は、実行ディレクトリ自身の設定を最も近い設定にします")
    return reference


# --- 生成と監査 ---------------------------------------------------------------------------------

def _dump(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def generate(root=HERE):
    """レビュー済みの入力と期待値からfixtureを書き出す。副作用の期待値は、隔離した準備手順の観測で作る（Coreは実行しない）。"""
    for identifier in CASES:
        fixture = root / "multi" / identifier
        for name, content in reviewed_inputs(identifier).items():
            path = fixture / "repo" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        manifest = reviewed_manifest(identifier)
        (fixture / "manifest.json").write_text(_dump(manifest))
        (fixture / "expected").mkdir(parents=True, exist_ok=True)
        (fixture / RESULT_FILES[CASES[identifier]["op"]]).write_text(_dump(reviewed_result(identifier)))
        with tempfile.TemporaryDirectory(prefix="bitz-multi-workspace-id-") as temporary:
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
            result = json.loads((fixture / RESULT_FILES[CASES[identifier]["op"]]).read_text())
            effects = json.loads((fixture / "side-effects.json").read_text())
            for key, value in (("manifest", manifest), ("result", result), ("side-effects", effects)):
                validators[key].validate(value)
            if manifest != reviewed_manifest(identifier):
                raise ValueError("起動条件がレビュー済みの期待値と異なります")
            if result != reviewed_result(identifier):
                raise ValueError("完全結果がレビュー済みの期待値と異なります")
            inputs = reviewed_inputs(identifier)
            files = {p.relative_to(fixture / "repo").as_posix(): p
                     for p in (fixture / "repo").rglob("*") if p.is_file() or p.is_symlink()}
            if set(files) != set(inputs) or any(p.is_symlink() or p.read_bytes() != inputs[key] for key, p in files.items()):
                raise ValueError("入力がレビュー済みのcorpusと異なります")
            if (fixture / "changes").exists() or (fixture / "cli-output.json").exists():
                raise ValueError("このfixtureは`changes/`と`cli-output.json`を持ちません")
            if effects["policy"] != "read-only" or effects["before"] != effects["after"]:
                raise ValueError("読取り専用の期待値が書込みを許しています")
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-multi-workspace-id-") as temporary:
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
                    check_against_reference(identifier, result, reference)
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, IndexError, ValidationError,
                subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "references": 1, "status": "Passed" if not errors else "Failed", "errors": errors}
