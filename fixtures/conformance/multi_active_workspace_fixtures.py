"""複合ワークスペースの中で、`verify`と`doctor`が作業ワークスペースを`--workspace`と最寄りの設定で決めることを固定する（Coreの公開操作は実行しない）。

複合ワークスペース仕様 §3は、作業ワークスペースを次の順で決めると定める。修飾IDの起点はその所有ワークスペース、`--workspace <id>`（カタログ内のルートまたはメンバーのID）、
現在のディレクトリの最寄りの設定のワークスペースである。`MULTI-029-01`〜`03`と`MULTI-031-01`〜`02`は`check`と`context`でこれを固定した。この群は、同じ規則が
`verify`と`doctor`にも適用されることを固定する（実装の確認事項C24、C38）。

`verify`（`MULTI-034-01`〜`05`）は、ルート`platform`のREQ-001（`MUST`の規範文1件）、メンバー`web`のTECH-010（`platform::REQ-001:AC-01`を`refines`し、
テスト対応を持つ）、メンバー`api`のTECH-010（`web`と同じローカルID。文書単位のテスト対応を持つ）を置く。3つのワークスペースは、どれも引数なしの`verify`の対象を1件ずつ持つ
（複合ワークスペース仕様 §3、`verify` §7）。

| fixture | 実行ディレクトリ | 引数 | 作業ワークスペース |
|---|---|---|---|
| `MULTI-034-01` | `apps/web` | `verify TECH-010` | 最寄りの設定の`web`。非修飾の`TECH-010`は`web::TECH-010`に解決する（`api::TECH-010`ではない） |
| `MULTI-034-02` | `.` | `verify TECH-010 --workspace web` | `--workspace`の`web`。最寄りの設定の`platform`を置き換える |
| `MULTI-034-03` | `.` | `verify --workspace web` | `web`。既定の対象は`web`の文書だけ（`scope: all`） |
| `MULTI-034-04` | `.` | `verify` | 最寄りの設定の`platform`。既定の対象は`platform`の文書だけ |
| `MULTI-034-05` | `apps/web` | `verify` | 最寄りの設定の`web`。既定の対象は`web`の文書だけ |

結果の`workspace`は作業ワークスペースの実際のIDとリポジトリのルートからの相対パス、検証対象・規範文・`covers`は修飾IDで返す（`verify` §8、複合ワークスペース仕様 §4）。
引数なしの既定の対象は、作業ワークスペースの`approved`のREQ、規範文を持つ`approved`のTECH、規範文を持たず`tests`を宣言する`approved`のTECHである（`verify` §7）。
他のワークスペースの文書は対象に加えない。統合索引の文書を列挙すると、3つのワークスペースの対象が混ざる（陰性対照）。

`doctor`（`MULTI-035-01`〜`03`）は、ルート`platform`とメンバー`web`、`api`（仕様文書なし）を置く。

| fixture | 実行ディレクトリ | 引数 | `workspace` |
|---|---|---|---|
| `MULTI-035-01` | `apps/web` | `doctor --workspace platform` | `platform`、パスは`.`。メンバーの中から`--workspace`でルートへ切り替える |
| `MULTI-035-02` | `.` | `doctor --workspace web` | `web`、パスは`apps/web`（リポジトリのルートからの相対パス） |
| `MULTI-035-03` | `apps/web` | `doctor` | `web`、パスは`apps/web`。`--workspace`なしは最寄りの設定のメンバーで、パスはカタログのパス |

`workspace.path`は、複合ワークスペース内のワークスペース単独操作でリポジトリのルートからの相対パスである（結果・診断・終了コード §2、`doctor` §7）。
検査項目は、`doctor` §3の検査順序の表の順に`core`、`workspace`、`config`、`catalog`（検査6。複合ワークスペースのカタログ、メンバー、パスの所有）、`schema`、`ears`、`git`、`command`、`impact`である。
複合ワークスペースの中の単独の`doctor`は、全体事前検査が成功したときに`catalog`の検査項目を置く（ユーザーの決定D4。単一ワークスペースは置かない）。

期待値の根拠は規範文と、このモジュールの参照計算だけである。`verify`は、作業ワークスペース、既定の対象、検証対象ごとの規範文・テスト割当て・コマンド・`covers`・
コンテキストのハッシュ値を、入力の木構造から導く`reference_verify`で、`doctor`は、作業ワークスペースと検査項目を入力の木構造から導く`reference_doctor`で、
リテラルの期待値と照合する。ハッシュ値は、独立に書いた2系統の参照計算（`multi_verify_fixtures`のリテラルA、`multi_crosscheck`の木構造からの導出B）の一致を要求する。
Coreの出力は期待値の根拠にしない。
"""
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from .digest_crosscheck import read_statements
from .harness import setup
from .initial_fixtures import observe, compare_state
from .multi_check_fixtures import MEMBERS, select_workspace
from .schemas import schema_path
from . import multi_crosscheck, multi_reference, multi_verify_fixtures
from .multi_verify_fixtures import command_result, requirement, target as target_entry, technical

HERE = Path(__file__).resolve().parent
COMMIT = "0" * 40
CAPABILITIES = ["context.v1", "check.v1", "verify.v1", "doctor.v1", "multiWorkspace.v1"]
CORE = {"version": "1.0.0", "apiVersion": "1.0", "capabilities": CAPABILITIES}
# 参照計算の材料に使う、`multi_verify_fixtures`のレビュー済みのハッシュ値の材料の識別子。ハッシュ値の材料は識別子に依存しない（`MULTI-014`だけがコマンドを変える）。
DIGEST_SOURCE = "MULTI-013"
SUPPORTED_MAJOR = 1

# id: (操作, 実行ディレクトリ, 引数列の残り, `--workspace`の値, 位置引数, 状態, 終了コード, 説明)
CASES = {
    "MULTI-034-01": ("verify", "apps/web", ["verify", "TECH-010"], None, ["TECH-010"], "passed", 0,
                     "メンバーの中の`verify TECH-010`が、非修飾のIDを最寄りの設定のメンバーで解決する"),
    "MULTI-034-02": ("verify", ".", ["verify", "TECH-010", "--workspace", "web"], "web", ["TECH-010"], "passed", 0,
                     "ルートの`verify TECH-010 --workspace web`が、メンバーを作業ワークスペースにして非修飾のIDを解決する"),
    "MULTI-034-03": ("verify", ".", ["verify", "--workspace", "web"], "web", [], "passed", 0,
                     "ルートの`verify --workspace web`が、メンバーの文書だけを既定の対象にする"),
    "MULTI-034-04": ("verify", ".", ["verify"], None, [], "passed", 0,
                     "ルートの引数なしの`verify`が、ルートの文書だけを既定の対象にして遮断されない"),
    "MULTI-034-05": ("verify", "apps/web", ["verify"], None, [], "passed", 0,
                     "メンバーの中の引数なしの`verify`が、メンバーの文書だけを既定の対象にする"),
    "MULTI-035-01": ("doctor", "apps/web", ["doctor", "--workspace", "platform"], "platform", [], "passed", 0,
                     "メンバーの中の`doctor --workspace platform`が、ルートを診断して`workspace.path`を`.`にする"),
    "MULTI-035-02": ("doctor", ".", ["doctor", "--workspace", "web"], "web", [], "passed", 0,
                     "ルートの`doctor --workspace web`が、メンバーを診断して`workspace.path`を`apps/web`にする"),
    "MULTI-035-03": ("doctor", "apps/web", ["doctor"], None, [], "passed", 0,
                     "メンバーの中の`--workspace`なしの`doctor`が、メンバーを診断して`workspace.path`を`apps/web`にする"),
}
OPERATION, CWD, ARGV, OPTION, POSITIONALS, STATUS, EXIT = range(7)
# 作業ワークスペースの期待。ここは参照計算の結果と一致することを要求する。
ACTIVE = {
    "MULTI-034-01": "web", "MULTI-034-02": "web", "MULTI-034-03": "web", "MULTI-034-04": "platform",
    "MULTI-034-05": "web", "MULTI-035-01": "platform", "MULTI-035-02": "web", "MULTI-035-03": "web",
}
SCOPE = {"MULTI-034-01": "selected", "MULTI-034-02": "selected", "MULTI-034-03": "all",
         "MULTI-034-04": "all", "MULTI-034-05": "all"}
RESULT_FILES = {"verify": "expected/verify.json", "doctor": "expected/doctor.json"}
WEB_TEST = "apps/web/tests/auth/test_login.py"
API_TEST = "services/api/tests/test_audit.py"
API_TECH_PATH = "services/api/.spec/technical/TECH-010.md"


def operation(identifier):
    return CASES[identifier][OPERATION]


def reviewed_inputs(identifier):
    """`repo/`の全入力。`verify`の5件は同じ入力、`doctor`の3件は同じ入力を共有する。"""
    if operation(identifier) == "doctor":
        # 仕様文書もコマンドも持たない。作業ワークスペースの同一性（IDとパス）が結果を決める。
        return {
            multi_reference.ROOT_CONFIG_PATH: multi_reference.root_config(MEMBERS).encode(),
            multi_reference.WEB_CONFIG_PATH: multi_reference.plain_config("web").encode(),
            multi_reference.API_CONFIG_PATH: multi_reference.plain_config("api").encode(),
        }
    return {
        multi_reference.ROOT_CONFIG_PATH: multi_reference.root_config(MEMBERS).encode(),
        multi_reference.WEB_CONFIG_PATH: multi_reference.member_config("web", "frontend").encode(),
        multi_reference.API_CONFIG_PATH: multi_reference.member_config("api", "backend").encode(),
        multi_reference.ROOT_REQ_PATH: requirement("REQ-001", "認証の基準", "REQ-001:AC-01").encode(),
        multi_reference.WEB_TECH_PATH: technical(
            "TECH-010", "Web側の実装方針", "webでREQ-001を実装する。",
            refines="platform::REQ-001:AC-01",
            tests=[("tests/auth/test_login.py", "platform::REQ-001:AC-01", "frontend")]).encode(),
        WEB_TEST: b"def test_login():\n    assert True\n",
        # `web`と同じローカルID `TECH-010`。規範文を持たず、文書単位のテスト対応だけを持つ。
        API_TECH_PATH: technical(
            "TECH-010", "API側の文書単位の監査方針", "規範文を持たず、文書単位のテストだけを宣言する。",
            tests=[("tests/test_audit.py", "TECH-010", "backend")]).encode(),
        API_TEST: b"def test_audit():\n    assert True\n",
    }


def reviewed_manifest(identifier):
    kind, cwd, argv, _, _, status, exit_code, description = CASES[identifier]
    return {
        "fixtureId": identifier,
        "description": description,
        "setup": {"git": True, "baseCommit": {"message": "base", "paths": ["."]}, "operations": []},
        "invocation": {"runner": "bitz", "cwd": cwd, "argv": [*argv, "--format", "json"], "env": {}},
        "expect": {"status": status, "exitCode": exit_code, "stdout": "json",
                   "resultFile": RESULT_FILES[kind], "reportFileCount": 0},
    }


# --- verify のレビュー済みの期待結果 ------------------------------------------------------

def web_target_result():
    """`web::TECH-010`。規範文を持たないTECHは`statements: []`で、文書単位のテスト割当て`web::frontend`を使う（`verify` §3）。"""
    return target_entry("web::TECH-010", "passed", multi_verify_fixtures.digest(DIGEST_SOURCE, "web::TECH-010"),
                        bindings=["web::frontend"])


def root_target_result():
    """`platform::REQ-001`。`MUST`の規範文1件を、`web`のTECH-010のテスト対応が直接カバーする。"""
    return target_entry("platform::REQ-001", "passed", multi_verify_fixtures.digest(DIGEST_SOURCE, "platform::REQ-001"),
                        ["platform::REQ-001:AC-01"], ["web::frontend"])


def web_command():
    return command_result("web", "frontend", "/bin/true", ["tests/auth/test_login.py"], ["platform::REQ-001:AC-01"])


def reviewed_verify_result(identifier):
    if ACTIVE[identifier] == "platform":
        workspace, target = {"id": "platform", "path": "."}, root_target_result()
    else:
        workspace, target = {"id": "web", "path": "apps/web"}, web_target_result()
    return {
        "schemaVersion": "1.0", "operation": "verify", "status": "passed", "scope": SCOPE[identifier],
        "workspace": workspace,
        "targetResults": [target],
        "revision": {"commit": COMMIT, "dirty": False},
        # 検証対象が`platform::REQ-001`でも`web::TECH-010`でも、テスト割当ては`web::frontend`で、コマンドの実体は`web`が所有する。
        "commands": [web_command()],
        "durationMs": 0,
        "diagnostics": [],
    }


# --- doctor のレビュー済みの期待結果 ------------------------------------------------------

def reviewed_doctor_result(identifier):
    workspace = {"id": "platform", "path": "."} if ACTIVE[identifier] == "platform" else {"id": "web", "path": "apps/web"}
    return {
        "schemaVersion": "1.0", "operation": "doctor", "status": "passed",
        "workspace": workspace,
        "core": dict(CORE),
        "checks": [
            {"name": "core", "status": "passed"},
            {"name": "workspace", "status": "passed"},
            {"name": "config", "status": "passed"},
            {"name": "catalog", "status": "passed"},
            {"name": "schema", "status": "passed"},
            {"name": "ears", "status": "passed"},
            {"name": "git", "status": "passed"},
            {"name": "command", "status": "passed"},
            {"name": "impact", "status": "info"},
        ],
        "durationMs": 0,
        "diagnostics": [],
    }


def reviewed_result(identifier):
    return reviewed_verify_result(identifier) if operation(identifier) == "verify" else reviewed_doctor_result(identifier)


# --- 参照計算 --------------------------------------------------------------------------------

def default_targets(documents, workspace_id):
    """引数なしの`verify`の対象。作業ワークスペースの`approved`のREQ、規範文を持つTECH、規範文を持たず`tests`を宣言するTECH（`verify` §7）。"""
    found = []
    for identifier, document in sorted(documents.items()):
        if document["workspaceId"] != workspace_id or document["frontmatter"]["status"] != "approved":
            continue
        statements = read_statements(document["body"])
        if document["kind"] == "requirement" or (
                document["kind"] == "technical" and (statements or document["frontmatter"].get("tests"))):
            found.append(identifier)
    return found


def reference_verify(repository, cwd, option, positionals):
    """参照計算: 入力の木構造から、作業ワークスペース、検証対象、規範文、テスト割当て、コマンド、ハッシュ値を導く（`verify` §3・§4・§5・§7・§8、複合ワークスペース仕様 §3・§4）。"""
    _, workspaces, documents = multi_crosscheck.load_workspaces(repository)
    active = select_workspace(workspaces, cwd, option)
    if positionals:
        # 非修飾のIDは、作業ワークスペースで解決する。他のワークスペースから探索しない（複合ワークスペース仕様 §4）。
        names = sorted({multi_crosscheck.qualify(active, name) for name in positionals})
        scope = "selected"
    else:
        names = default_targets(documents, active)
        scope = "all"
    targets, plan = [], {}
    for name in names:
        if name not in documents:
            raise ValueError(f"検証対象{name}が作業ワークスペースの仕様文書にありません")
        document = documents[name]
        statements = [f"{document['workspaceId']}::{item['id']}" for item in read_statements(document["body"])]
        selected, _ = multi_crosscheck.closure(documents, name)
        # 規範文を持つ文書は、閉包の文書のテスト対応のうち対象の規範文をカバーするもの、規範文を持たないTECHは自身のテスト対応を使う（`verify` §3）。
        pool = [documents[item] for item in selected] if statements else [document]
        used = []
        for owner in pool:
            for entry in multi_crosscheck.tests(owner):
                covered = [value for value in entry["covers"] if (value in statements if statements else True)]
                if covered:
                    used.append((owner["workspaceId"], entry["command"], entry["path"], covered))
        musts = {f"{document['workspaceId']}::{item['id']}" for item in read_statements(document["body"])
                 if item["modality"] == "MUST"}
        tested = {value for _, _, _, covered in used for value in covered}
        digest = multi_crosscheck.digest(multi_crosscheck.canonical_bytes(multi_crosscheck.build(repository, name)))
        targets.append({"target": name, "statements": sorted(statements),
                        "bindingRefs": sorted({f"{ws}::{command}" for ws, command, _, _ in used}),
                        "contextDigest": digest, "untestedMust": sorted(musts - tested)})
        for ws, command, path, covered in used:
            entry = plan.setdefault((ws, command), {"tests": set(), "covers": set()})
            entry["tests"].add(path)
            entry["covers"].update(covered)
    commands = []
    for (ws, command), entry in sorted(plan.items()):
        definition = workspaces[ws]["config"]["verify"]["commands"][command]
        tests = sorted(entry["tests"])
        argv = []
        for item in definition["argv"]:
            argv += tests if item == "{tests}" else [item]
        commands.append({"bindingId": f"{ws}::{command}", "workspaceId": ws, "name": command, "tests": tests,
                         "covers": sorted(entry["covers"]), "argv": argv, "cwd": definition.get("cwd", ".")})
    return {"workspace": {"id": active, "path": workspaces[active]["path"]}, "scope": scope,
            "targets": targets, "commands": commands, "defaults": names,
            "status": "passed" if all(not item["untestedMust"] for item in targets) and targets else "blocked"}


def check_verify_against_reference(result, reference):
    """リテラルの期待値が、参照計算と一致することを要求する。"""
    if result["workspace"] != reference["workspace"] or result["scope"] != reference["scope"]:
        raise ValueError("`workspace`または`scope`が入力からの参照計算と異なります")
    actual = [{"target": item["target"], "statements": item["statements"], "bindingRefs": item["bindingRefs"],
               "contextDigest": item["contextDigest"]} for item in result["targetResults"]]
    expected = [{key: item[key] for key in ("target", "statements", "bindingRefs", "contextDigest")}
                for item in reference["targets"]]
    if actual != expected:
        raise ValueError("検証対象が入力からの参照計算と異なります")
    commands = [{"bindingId": item["bindingId"], "workspaceId": item["workspaceId"], "name": item["name"],
                 "tests": item["tests"], "covers": item["covers"], "argv": item["argv"], "cwd": item["cwd"]}
                for item in result["commands"]]
    if commands != reference["commands"]:
        raise ValueError("コマンドが入力からの参照計算と異なります")
    if result["status"] != reference["status"] or any(item["status"] != result["status"] for item in result["targetResults"]):
        raise ValueError("状態が入力からの参照計算と異なります")


def resolves(workspace_root, argv0):
    """実行ファイルの解決（`verify` §5.1）。この群が使うのは`/`を含む実行ファイルだけである。"""
    if "/" not in argv0:
        raise ValueError("この参照計算は、`/`を含まない実行ファイルを扱いません")
    path = Path(argv0) if argv0.startswith("/") else workspace_root / argv0
    return path.is_file() and (path.stat().st_mode & 0o111) != 0


def reference_doctor(repository, cwd, option):
    """参照計算: 入力の木構造から、作業ワークスペースと検査項目の状態を導く（`doctor` §3・§7、複合ワークスペース仕様 §3）。"""
    _, workspaces, _ = multi_crosscheck.load_workspaces(repository)
    active = select_workspace(workspaces, cwd, option)
    entry = workspaces[active]
    root = repository if entry["path"] == "." else repository / entry["path"]
    config = entry["config"]
    commands = config.get("verify", {}).get("commands", {})
    unresolved = [name for name, definition in sorted(commands.items())
                  if not resolves(root / definition.get("cwd", "."), definition["argv"][0])]
    checks = [
        {"name": "core", "status": "passed" if sys.version_info[:2] >= (3, 12) else "blocked"},
        {"name": "workspace", "status": "passed" if (root / ".spec/bitz.yaml").is_file() else "blocked"},
        {"name": "config", "status": "passed"},
        # 検査6: 複合ワークスペースのカタログ、メンバー、パスの所有。`load_workspaces`がカタログのIDと設定のIDの一致、メンバーのディレクトリの実在を要求する。
        {"name": "catalog", "status": "passed"},
        {"name": "schema", "status": "passed" if int(str(config["schemaVersion"]).split(".")[0]) == SUPPORTED_MAJOR else "blocked"},
        {"name": "ears", "status": "passed" if int(str(config["earsAi"]).split(".")[0]) == SUPPORTED_MAJOR else "blocked"},
        {"name": "git", "status": "passed" if (repository / ".git").exists() else "warning"},
        {"name": "command", "status": "blocked" if unresolved else "passed"},
        {"name": "impact", "status": "info"},
    ]
    return {"workspace": {"id": active, "path": entry["path"]}, "checks": checks,
            "status": "passed" if all(item["status"] in {"passed", "info"} for item in checks) else "blocked"}


def check_doctor_against_reference(result, reference):
    if result["workspace"] != reference["workspace"]:
        raise ValueError("`workspace`が入力からの参照計算と異なります")
    if result["checks"] != reference["checks"] or result["status"] != reference["status"]:
        raise ValueError("検査項目または状態が入力からの参照計算と異なります")


def check_digests(repository, result):
    """検証対象のハッシュ値を、独立に書いた2系統の参照計算（リテラルAと木構造からの導出B）で照合する。"""
    for entry in result["targetResults"]:
        derived = multi_crosscheck.canonical_bytes(multi_crosscheck.build(repository, entry["target"]))
        literal = multi_reference.canonical_bytes(multi_verify_fixtures.reviewed_digest_input(DIGEST_SOURCE, entry["target"]))
        if literal != derived:
            raise ValueError(f"{entry['target']}の参照計算AとBの正規JSONが一致しません")
        if multi_crosscheck.digest(derived) != entry["contextDigest"]:
            raise ValueError(f"{entry['target']}のハッシュ値が参照計算と一致しません")


def check_conditions(identifier, repository):
    """原因の構成を、散文ではなく入力の木構造から確かめる。"""
    _, workspaces, documents = multi_crosscheck.load_workspaces(repository)
    cwd, option = CASES[identifier][CWD], CASES[identifier][OPTION]
    active = select_workspace(workspaces, cwd, option)
    if active != ACTIVE[identifier]:
        raise ValueError("作業ワークスペースが期待と異なります")
    if sorted(workspaces) != ["api", "platform", "web"] or workspaces["web"]["path"] != "apps/web":
        raise ValueError("ワークスペースは、ルート`platform`とメンバー`web`（`apps/web`）、`api`である必要があります")
    if option is not None:
        # `--workspace`が最寄りの設定と異なる場合は置き換えを、同じ場合は一致を、入力から確かめる。
        nearest = select_workspace(workspaces, cwd, None)
        if option != active or (identifier in {"MULTI-034-02", "MULTI-034-03", "MULTI-035-01", "MULTI-035-02"} and nearest == active):
            raise ValueError("`--workspace`が最寄りの設定のワークスペースを置き換える必要があります")
    if operation(identifier) == "doctor":
        if documents:
            raise ValueError("`doctor`のfixtureは仕様文書を持ってはいけません")
        if multi_crosscheck.catalog(repository)[1] != MEMBERS:
            raise ValueError("カタログのメンバーの列挙順が想定と異なります")
        # `workspace.path`はカタログのパスで、実行ディレクトリの相対パスではない。
        if select_workspace(workspaces, cwd, option) != ACTIVE[identifier]:
            raise ValueError("作業ワークスペースが期待と異なります")
        return
    if any(document["frontmatter"]["status"] != "approved" for document in documents.values()):
        raise ValueError("すべての文書は状態`approved`である必要があります")
    if sorted(documents) != ["api::TECH-010", "platform::REQ-001", "web::TECH-010"]:
        raise ValueError("文書は、ルートのREQ-001、`web`と`api`のTECH-010だけである必要があります")
    # 3つのワークスペースが、引数なしの既定の対象を1件ずつ持つ。統合索引を列挙すると、作業ワークスペース以外の対象が混ざる。
    per_workspace = {name: default_targets(documents, name) for name in workspaces}
    if per_workspace != {"platform": ["platform::REQ-001"], "web": ["web::TECH-010"], "api": ["api::TECH-010"]}:
        raise ValueError("既定の対象は、ワークスペースごとに1件ずつである必要があります")
    # 非修飾の`TECH-010`は`web`と`api`の両方に実在し、作業ワークスペースで決まる（陰性対照）。
    if documents["web::TECH-010"]["frontmatter"]["id"] != documents["api::TECH-010"]["frontmatter"]["id"]:
        raise ValueError("`web`と`api`は同じローカルID `TECH-010`を持つ必要があります")
    if any(documents[name]["frontmatter"].get("relations") for name in ("api::TECH-010", "platform::REQ-001")):
        raise ValueError("`api`のTECH-010とルートのREQ-001は関係を宣言してはいけません")
    reference = reference_verify(repository, cwd, option, CASES[identifier][POSITIONALS])
    if reference["status"] != "passed":
        raise ValueError("検証対象は通過する構成である必要があります")
    all_defaults = [name for names in per_workspace.values() for name in names]
    if not CASES[identifier][POSITIONALS]:
        if reference["defaults"] != per_workspace[active] or len(reference["defaults"]) >= len(all_defaults):
            raise ValueError("既定の対象は作業ワークスペースの文書だけである必要があります")
    # 陰性対照: 作業ワークスペースを取り違えると、検証対象が変わる。
    for other in sorted(set(workspaces) - {active}):
        try:
            same = reference_verify(repository, cwd, other, CASES[identifier][POSITIONALS])["targets"] == reference["targets"]
        except ValueError:
            # 別の作業ワークスペースでは、非修飾のIDが仕様文書に存在しない。
            same = False
        if same:
            raise ValueError("別の作業ワークスペースの結果と区別できる必要があります")
    # 陰性対照: `api`の`TECH-010`は、別のコマンドの別のテスト割当てを使う。
    if any(item["workspaceId"] == "api" for item in reference["commands"]):
        raise ValueError("`api`のテスト割当てが実行されてはいけません")


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
        (fixture / "expected").mkdir(parents=True, exist_ok=True)
        manifest = reviewed_manifest(identifier)
        (fixture / "manifest.json").write_text(_dump(manifest))
        (fixture / RESULT_FILES[operation(identifier)]).write_text(_dump(reviewed_result(identifier)))
        with tempfile.TemporaryDirectory(prefix="bitz-multi-active-") as temporary:
            sandbox = Path(temporary)
            repository = setup(fixture, manifest, sandbox / "repo")
            external = {name: sandbox / name for name in ("home", "cache", "temporary")}
            for path in external.values():
                path.mkdir()
            state = observe(repository, external)
        (fixture / "side-effects.json").write_text(
            _dump({"schemaVersion": "1.0", "policy": "read-only", "before": state, "after": state}))


def validate(root=HERE, identifiers=None):
    errors, prepared = [], []
    validators = {name: Draft202012Validator(json.loads(schema_path(root, name).read_text()))
                  for name in ("manifest", "result", "side-effects")}
    frontmatter = json.loads(schema_path(root, "frontmatter").read_text())
    for identifier in CASES:
        if identifiers is not None and identifier not in identifiers:
            continue
        fixture = root / "multi" / identifier
        kind = operation(identifier)
        try:
            manifest = json.loads((fixture / "manifest.json").read_text())
            result = json.loads((fixture / RESULT_FILES[kind]).read_text())
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
            if entries != {("repo", name): data for name, data in reviewed.items()}:
                raise ValueError("入力がレビュー済みのcorpusと異なります")
            if effects["policy"] != "read-only" or effects["before"] != effects["after"]:
                raise ValueError("読取り専用の期待値が書込みを許しています")
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-multi-active-") as temporary:
                for run in range(2):
                    sandbox = Path(temporary) / str(run)
                    sandbox.mkdir()
                    repository = setup(fixture, manifest, sandbox / "repo")
                    external = {key: sandbox / key for key in ("home", "cache", "temporary")}
                    for path in external.values():
                        path.mkdir()
                    actual = observe(repository, external)
                    if compare_state(effects["before"], actual) or (previous is not None and previous != actual):
                        raise ValueError("隔離した準備手順が固定したスナップショットと異なります")
                    previous = actual
                    check_conditions(identifier, repository)
                    cwd, option = CASES[identifier][CWD], CASES[identifier][OPTION]
                    if kind == "verify":
                        check_verify_against_reference(
                            result, reference_verify(repository, cwd, option, CASES[identifier][POSITIONALS]))
                        check_digests(repository, result)
                    else:
                        check_doctor_against_reference(result, reference_doctor(repository, cwd, option))
                    _, _, documents = multi_crosscheck.load_workspaces(repository)
                    for document in documents.values():
                        Draft202012Validator({"$ref": "#/$defs/" + {
                            "requirement": "reqFrontmatter", "technical": "techFrontmatter",
                            "decision": "adrFrontmatter", "task": "taskFrontmatter"}[document["kind"]],
                            "$defs": frontmatter["$defs"]}).validate(document["frontmatter"])
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, IndexError, ValidationError,
                subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "references": 2, "status": "Passed" if not errors else "Failed", "errors": errors}
