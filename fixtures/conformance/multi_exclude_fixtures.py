"""複合ワークスペースの除外の指定と入れ子の複合ワークスペースを固定する（Coreの公開操作は実行しない）。

ADR-064は、ルートワークスペースの設定の`multiWorkspace.exclude`に書いたディレクトリとその配下を、その複合ワークスペースの外とみなす。
効果は、Gitが認識する設定の比較（複合ワークスペース仕様 §8）、単独操作の選択した設定の照合（§3の手順4）、作業ワークスペースの決定（§2.1）だけに及ぶ。
除外した範囲の中で探索を始めると、除外のディレクトリから開始位置までの経路の上の設定で、入れ子の複合ワークスペース、単一ワークスペース、
除外の外の規則のどれかを決める（§2.1）。この群は、その決定、除外の不正、除外を信用できない条件、入れ子の複合ワークスペースの範囲を、27件で固定する（ADR-051の追加）。

基本のリポジトリは、ルート`platform`（`.`）、メンバー`web`（`apps/web`）と`api`（`services/api`）、`exclude: [cases, apps/web/tests/data]`である。
`cases/single`は単一の設定、`cases/nested`は`multiWorkspace`を宣言する入れ子のルート（メンバー`m`は`cases/nested/apps/m`）、
`apps/web/tests/data/x`はメンバーの配下の除外にある単一の設定である。どれもGitで追跡する。

| fixture | 操作と実行ディレクトリ | 原因と期待 |
|---|---|---|
| `MULTI-037-01` | `check --all-workspaces`、`.` | 除外した範囲の中の設定は未登録にならず、通る。ルート、`api`、`web`の3件だけを検査する |
| `MULTI-037-02` | `doctor`、`.` | 単独の`doctor`も、除外した範囲の中の設定を比較せず、`catalog`が`passed` |
| `MULTI-037-03` | `check --full`、`cases/single` | 経路の上に`multiWorkspace`を宣言した設定がない。単一ワークスペースとして通る。`workspace.path`は`.` |
| `MULTI-037-04` | `check --all-workspaces`、`cases/single` | 単一ワークスペースの`--all-workspaces`は、複合ワークスペースを発見できない引数不正（終了コード4） |
| `MULTI-037-05` | `check --full`、`cases/nested` | 入れ子の複合ワークスペースのルートワークスペースとして通る。`workspace`は`{nested, .}` |
| `MULTI-037-06` | `check --all-workspaces`、`cases/nested/apps/m` | 最寄りの設定はメンバー`m`だが、除外のディレクトリに最も近い宣言は`cases/nested`。入れ子の全体操作で、ルートと`m`を検査する |
| `MULTI-037-07` | `doctor --all-workspaces`、`cases/nested` | 入れ子の`doctor`の全体 |
| `MULTI-037-08` | `verify REQ-001`、`apps/web/tests/data/x` | メンバーの配下の除外の中の単一ワークスペースとして動く |
| `MULTI-037-09`〜`15` | `check --all-workspaces`、`.` | `exclude`の不正（字句、末尾の`/`、重複、入れ子、`.spec`、文字列の配列でない、101件）は`SPEC-MULTI-CONFIG-001`（`failed`） |
| `MULTI-037-16`、`17` | `check --all-workspaces`、`.` | メンバーのパスが除外のパスの配下／同じなら`SPEC-MULTI-PATH-001`（`failed`） |
| `MULTI-037-18` | `check`、`cases/single` | `exclude`が不正なら除外を決めず、外側の全体事前検査で停止する |
| `MULTI-037-19` | `check --full`、`cases/single` | `exclude`が妥当なら、外側のほかの不備（`api`の設定の不在）で止まらない |
| `MULTI-037-20` | `check --all-workspaces`、`.` | 存在しない除外は通る |
| `MULTI-037-21` | `check --full`、`cases/nested` | 外側のルートの設定が読めないなら、除外も入れ子も決めず、最も近い設定を単一ワークスペースとして使う |
| `MULTI-037-22` | `doctor --all-workspaces`、`cases/nested` | 入れ子の中の未登録の設定は、入れ子のルート相対のパスで`blocked` |
| `MULTI-037-23` | `check --base HEAD`、`cases/nested` | 入れ子のルートの外の変更は、変更集合に入らない |
| `MULTI-037-24`〜`27` | `check`、`cases/single` | ルートの`multiWorkspace`が設定不適合（`members`の不在・非配列・0件、`maxMembers`の範囲外）なら、妥当な`exclude`も信用せず、外側の全体事前検査で停止する |

期待値の根拠は規範文（複合ワークスペース仕様 §2・§2.1・§3・§7・§8、ADR-064、ADR-063、結果・診断・終了コード §2、`check` §6・§9、`doctor` §3・§7）と、
このモジュールの参照計算だけである。参照計算`reference_scope`は、入力の木構造とGitの状態から、除外した範囲、探索の開始位置の場所（外側／入れ子／単一）、
複合ワークスペースのルート、除外の不正、停止の原因、結果のパス、文書と規範文の件数、変更集合の件数を導く。Coreの出力は期待値の根拠にしない。
診断の文言は、`Coreの出力文言のレビュー記録.md`の承認済みの文字列（ADR-064 決定8）と、既存の「Gitが認識する設定ファイルがカタログに登録されていません」である。
"""
import copy
import json
from pathlib import Path, PurePosixPath
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from . import digest_crosscheck, multi_reference, verify_fixtures
from .digest_crosscheck import KIND_BY_DIRECTORY, read_statements, split_document
from .harness import git, setup
from .initial_fixtures import compare_state
from .multi_catalog_fixtures import observe_state
from .multi_check_fixtures import MEMBERS
from .multi_verify_fixtures import requirement, technical
from .schemas import schema_path

HERE = Path(__file__).resolve().parent
COMMIT = "0" * 40
CAPABILITIES = ["context.v1", "check.v1", "verify.v1", "doctor.v1", "multiWorkspace.v1"]
CORE = {"version": "1.0.0", "apiVersion": "1.0", "capabilities": CAPABILITIES}
SUPPORTED_MAJOR = 1
MAX_EXCLUDE = 100
GLOB_CHARACTERS = set("*?[]{}")
ROOT_ID = "platform"
EXCLUDE = ["cases", "apps/web/tests/data"]
X_DIRECTORY = "apps/web/tests/data/x"
SINGLE_DIRECTORY = "cases/single"
NESTED_DIRECTORY = "cases/nested"
NESTED_MEMBER_DIRECTORY = "cases/nested/apps/m"
NESTED_UNREGISTERED_DIRECTORY = "cases/nested/tools/z"
NESTED_CHANGED_TECH = "cases/nested/.spec/technical/TECH-021.md"
ROOT_REQ_PATH = ".spec/requirements/REQ-001.md"
OUTSIDE_CODE_PATH = "services/api/src/session.py"
NESTED_CODE_PATH = "cases/nested/src/extra.py"
OUTSIDE_NEW_PATH = "tools/outside.py"

# 承認済みの診断の文言（ADR-064 決定8。`Coreの出力文言のレビュー記録.md`）と、既存の文言。
MEMBERS_REQUIRED = "設定キーmultiWorkspace.membersは1件以上指定してください"
MEMBERS_TYPE = "設定キーmultiWorkspace.membersは配列で指定してください"
MAX_MEMBERS_RANGE = "設定キーmultiWorkspace.maxMembersは1〜100の整数で指定してください"
EXCLUDE_TYPE = "設定キーmultiWorkspace.excludeは文字列の配列で指定してください"
EXCLUDE_COUNT = "設定キーmultiWorkspace.excludeは100件以下で指定してください"
EXCLUDE_FORMAT = "除外のパスの形式が不正です"
EXCLUDE_DUPLICATE = "除外のパスが重複しています"
EXCLUDE_NESTED = "除外のパスが別の除外のパスの配下にあります"
EXCLUDE_SPEC = "除外のパスに.specが含まれています"
MEMBER_EXCLUDED = "メンバーのパスが除外した範囲にあります"
UNREGISTERED_GIT = "Gitが認識する設定ファイルがカタログに登録されていません"
UNREGISTERED_SELECTED = "選択した設定ファイルがカタログに登録されていません"
MEMBER_MISSING = "メンバーの.spec/bitz.yamlがありません"

# 停止の原因: (診断コード, 結果への効果, summary, 発生元のキー)
CAUSES = {
    "exclude-type": ("SPEC-MULTI-CONFIG-001", "failed", EXCLUDE_TYPE, "multiWorkspace.exclude"),
    "exclude-count": ("SPEC-MULTI-CONFIG-001", "failed", EXCLUDE_COUNT, "multiWorkspace.exclude"),
    "members-required": ("SPEC-MULTI-CONFIG-001", "failed", MEMBERS_REQUIRED, "multiWorkspace.members"),
    "members-type": ("SPEC-MULTI-CONFIG-001", "failed", MEMBERS_TYPE, "multiWorkspace.members"),
    "max-members": ("SPEC-MULTI-CONFIG-001", "failed", MAX_MEMBERS_RANGE, "multiWorkspace.maxMembers"),
    "exclude-format": ("SPEC-MULTI-CONFIG-001", "failed", EXCLUDE_FORMAT, "multiWorkspace.exclude"),
    "exclude-duplicate": ("SPEC-MULTI-CONFIG-001", "failed", EXCLUDE_DUPLICATE, "multiWorkspace.exclude"),
    "exclude-nested": ("SPEC-MULTI-CONFIG-001", "failed", EXCLUDE_NESTED, "multiWorkspace.exclude"),
    "exclude-spec": ("SPEC-MULTI-CONFIG-001", "failed", EXCLUDE_SPEC, "multiWorkspace.exclude"),
    "member-excluded": ("SPEC-MULTI-PATH-001", "failed", MEMBER_EXCLUDED, "multiWorkspace.members"),
    "unregistered-git": ("SPEC-MULTI-UNREGISTERED-001", "blocked", UNREGISTERED_GIT, None),
    "unregistered-selected": ("SPEC-MULTI-UNREGISTERED-001", "blocked", UNREGISTERED_SELECTED, None),
    "member-missing": ("SPEC-MULTI-MEMBER-001", "failed", MEMBER_MISSING, "multiWorkspace.members"),
}



def case(op, cwd, argv, tree, exclude=EXCLUDE, operations=(), status="passed", exit_code=0, cause=None, description="", **expected):
    return dict(op=op, cwd=cwd, argv=list(argv), tree=tree, exclude=exclude, operations=list(operations),
                status=status, exit=exit_code, cause=cause, description=description, expected=expected)


def _untrusted(tree, cause, description):
    """ルートの`multiWorkspace`が設定不適合（`exclude: [cases]`は妥当）。`cases/single`の単独の`check`が、除外を決めず外側の全体事前検査で停止する。"""
    return case("check", SINGLE_DIRECTORY, ["check", "--base", "HEAD"], tree, exclude=["cases"], status="failed", exit_code=1, cause=cause,
                description=f"{description}。除外した範囲の中の単独の`check`も外側の全体事前検査で停止する",
                workspace={"id": None, "path": SINGLE_DIRECTORY}, dirty=False)


def _invalid(identifier_exclude, cause, description):
    return case("check", ".", ["check", "--all-workspaces", "--base", "HEAD"], "base", exclude=identifier_exclude,
                status="failed", exit_code=1, cause=cause, description=description,
                root=ROOT_ID, workspaces=[], dirty=False)


PLATFORM_WORKSPACES = [("platform", ".", 1, 1), ("api", "services/api", 0, 0), ("web", "apps/web", 0, 0)]
SINGLE_WORKSPACE = {"id": "single", "path": "."}
NESTED_WORKSPACE = {"id": "nested", "path": "."}
NESTED_WORKSPACES = [("nested", ".", 1, 1), ("m", "apps/m", 1, 1)]
FULL_CHECK = ["check", "--full", "--base", "HEAD"]

CASES = {
    "MULTI-037-01": case("check", ".", ["check", "--all-workspaces", "--base", "HEAD"], "full",
                         description="除外した範囲の中の設定は未登録にならず、`check --all-workspaces`が通る",
                         root=ROOT_ID, workspaces=PLATFORM_WORKSPACES, dirty=False),
    "MULTI-037-02": case("doctor", ".", ["doctor"], "full",
                         description="単独の`doctor`も、除外した範囲の中の設定を比較せず、検査項目`catalog`が通る",
                         workspace={"id": ROOT_ID, "path": "."}),
    "MULTI-037-03": case("check", SINGLE_DIRECTORY, FULL_CHECK, "full",
                         description="除外した範囲の中の単一の設定で単独の`check`を実行すると、単一ワークスペースとして通る",
                         workspace=SINGLE_WORKSPACE, counts=(1, 1), dirty=False),
    "MULTI-037-04": case("check", SINGLE_DIRECTORY, ["check", "--all-workspaces", "--base", "HEAD"], "full",
                         status=None, exit_code=4,
                         description="除外した範囲の中の単一ワークスペースでは、`--all-workspaces`が複合ワークスペースを発見できず引数不正になる"),
    "MULTI-037-05": case("check", NESTED_DIRECTORY, FULL_CHECK, "full",
                         description="除外した範囲の中の入れ子の複合ワークスペースのルートで、単独の`check`がルートワークスペースとして通る",
                         workspace=NESTED_WORKSPACE, counts=(1, 1), dirty=False),
    "MULTI-037-06": case("check", NESTED_MEMBER_DIRECTORY, ["check", "--all-workspaces", "--base", "HEAD"], "full",
                         description="入れ子のメンバーの中の`check --all-workspaces`が、入れ子の複合ワークスペース全体を検査する",
                         root="nested", workspaces=NESTED_WORKSPACES, dirty=False),
    "MULTI-037-07": case("doctor", NESTED_DIRECTORY, ["doctor", "--all-workspaces"], "full",
                         description="入れ子の複合ワークスペースのルートで、`doctor --all-workspaces`が入れ子の全体を診断する",
                         root="nested", workspaces=NESTED_WORKSPACES),
    "MULTI-037-08": case("verify", X_DIRECTORY, ["verify", "REQ-001"], "full",
                         description="メンバーの配下の除外の中の単一ワークスペースで、単独の`verify`が単一ワークスペースとして動く",
                         workspace={"id": "root", "path": "."}, dirty=False),
    "MULTI-037-09": _invalid(["../x"], "exclude-format", "`..`を含む除外のパスを設定不適合にする"),
    "MULTI-037-10": _invalid(["cases/"], "exclude-format", "末尾が`/`の除外のパスを設定不適合にする"),
    "MULTI-037-11": _invalid(["cases", "cases"], "exclude-duplicate", "重複した除外のパスを設定不適合にする"),
    "MULTI-037-12": _invalid(["cases", "cases/a"], "exclude-nested", "別の除外のパスの配下にある除外のパスを設定不適合にする"),
    "MULTI-037-13": _invalid(["cases/x/.spec"], "exclude-spec", "`.spec`のセグメントを含む除外のパスを設定不適合にする"),
    "MULTI-037-14": _invalid("cases", "exclude-type", "文字列の配列でない`exclude`を設定不適合にする"),
    "MULTI-037-15": _invalid([f"ex{number:03d}" for number in range(1, 102)], "exclude-count", "101件の`exclude`を設定不適合にする"),
    "MULTI-037-16": case("check", ".", ["check", "--all-workspaces", "--base", "HEAD"], "base", exclude=["apps"],
                         status="failed", exit_code=1, cause="member-excluded",
                         description="メンバーのパスが除外のパスの配下にあるとき、パスの不適合にする",
                         root=ROOT_ID, workspaces=[], dirty=False),
    "MULTI-037-17": case("check", ".", ["check", "--all-workspaces", "--base", "HEAD"], "base", exclude=["apps/web"],
                         status="failed", exit_code=1, cause="member-excluded",
                         description="メンバーのパスが除外のパスと同じとき、パスの不適合にする",
                         root=ROOT_ID, workspaces=[], dirty=False),
    "MULTI-037-18": case("check", SINGLE_DIRECTORY, ["check", "--base", "HEAD"], "full", exclude=["cases", "cases"],
                         status="failed", exit_code=1, cause="exclude-duplicate",
                         description="`exclude`が不正なとき、除外を決めず、除外した範囲の中の単独の`check`も外側の全体事前検査で停止する",
                         workspace={"id": None, "path": SINGLE_DIRECTORY}, dirty=False),
    "MULTI-037-19": case("check", SINGLE_DIRECTORY, FULL_CHECK, "api-missing",
                         description="`exclude`が妥当なら、外側のほかの不備（メンバーの設定の不在）では、除外した範囲の中の単独の`check`が止まらない",
                         workspace=SINGLE_WORKSPACE, counts=(1, 1), dirty=False),
    "MULTI-037-20": case("check", ".", ["check", "--all-workspaces", "--base", "HEAD"], "base", exclude=["generated"],
                         description="存在しない除外のパスは、診断にせず通る",
                         root=ROOT_ID, workspaces=[("platform", ".", 1, 1), ("api", "services/api", 0, 0), ("web", "apps/web", 0, 0)],
                         dirty=False),
    "MULTI-037-21": case("check", NESTED_DIRECTORY, FULL_CHECK, "anchor",
                         description="外側のルートの設定が読めないとき、除外も入れ子も決めず、最も近い設定を単一ワークスペースとして使う",
                         workspace=NESTED_WORKSPACE, counts=(1, 1), dirty=False),
    "MULTI-037-22": case("doctor", NESTED_DIRECTORY, ["doctor", "--all-workspaces"], "nested-unregistered",
                         status="blocked", exit_code=2, cause="unregistered-git",
                         description="入れ子の複合ワークスペースの中の未登録の設定を、入れ子のルート相対のパスで`blocked`にする",
                         root="nested", workspaces=[], unregistered=["tools/z/.spec/bitz.yaml"]),
    "MULTI-037-23": case("check", NESTED_DIRECTORY, ["check", "--base", "HEAD"], "nested-changes",
                         operations=[
                             {"op": "update", "path": NESTED_CHANGED_TECH, "source": "changes/TECH-021.md"},
                             {"op": "create", "path": NESTED_CODE_PATH, "source": "changes/extra.py"},
                             {"op": "update", "path": ROOT_REQ_PATH, "source": "changes/REQ-001.md"},
                             {"op": "update", "path": OUTSIDE_CODE_PATH, "source": "changes/session.py"},
                             {"op": "create", "path": OUTSIDE_NEW_PATH, "source": "changes/outside.py"}],
                         description="入れ子の複合ワークスペースの単独の`check`が、入れ子のルートの外の変更を変更集合に入れない",
                         workspace=NESTED_WORKSPACE, selection=(2, 1, 1), dirty=True),
    "MULTI-037-24": _untrusted("members-absent", "members-required", "`members`のない`multiWorkspace`は設定不適合で、除外を決めない"),
    "MULTI-037-25": _untrusted("members-scalar", "members-type", "配列でない`members`は設定不適合で、除外を決めない"),
    "MULTI-037-26": _untrusted("members-empty", "members-required", "0件の`members`は設定不適合で、除外を決めない"),
    "MULTI-037-27": _untrusted("max-members", "max-members", "範囲外の`maxMembers`は設定不適合で、除外を決めない"),
}
ROOT_HEADER = 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\nworkspace:\n  id: platform\n'
_EXCLUDE_CASES = "  exclude:\n    - cases\n"
_MEMBERS = "  members:\n    - id: web\n      path: apps/web\n    - id: api\n      path: services/api\n"
# ルートの`multiWorkspace`の設定不適合（`exclude: [cases]`は妥当）。
UNTRUSTED_ROOT = {
    "members-absent": _EXCLUDE_CASES,
    "members-scalar": "  members: web\n" + _EXCLUDE_CASES,
    "members-empty": "  members: []\n" + _EXCLUDE_CASES,
    "max-members": "  maxMembers: 0\n" + _MEMBERS + _EXCLUDE_CASES,
}
RESULT_FILES = {"check": "expected/check.json", "verify": "expected/verify.json", "doctor": "expected/doctor.json"}


def operation(identifier):
    return CASES[identifier]["op"]


def has_result(identifier):
    return CASES[identifier]["exit"] != 4


def cli_output(identifier):
    """引数不正（終了コード4）は、標準出力を空にし、標準エラー出力に`bitz: <操作>: `で始まる理由1行だけを出す（結果・診断・終了コード §3）。理由の文言は固定しない。"""
    return {"exitCode": 4, "stdout": "", "stderrPrefix": f"bitz: {CASES[identifier]['op']}: ",
            "stderrLineCount": 1, "stderrReasonRequired": True, "stderrTerminalControls": False}


# --- 入力 -------------------------------------------------------------------------------

def root_config(exclude, root_id=ROOT_ID):
    text = multi_reference.root_config(MEMBERS, root_id)
    if isinstance(exclude, list):
        return text + "  exclude:\n" + "".join(f"    - {path}\n" for path in exclude)
    return text + f"  exclude: {exclude}\n"


def single_config():
    return multi_reference.plain_config("single")


def nested_config():
    return multi_reference.root_config([("m", "apps/m")], "nested")


def base_files(exclude):
    return {
        multi_reference.ROOT_CONFIG_PATH: root_config(exclude),
        ROOT_REQ_PATH: requirement("REQ-001", "認証の基準", "REQ-001:AC-01"),
        multi_reference.WEB_CONFIG_PATH: multi_reference.plain_config("web"),
        multi_reference.API_CONFIG_PATH: multi_reference.plain_config("api"),
    }


def cases_files():
    return {
        f"{SINGLE_DIRECTORY}/.spec/bitz.yaml": single_config(),
        f"{SINGLE_DIRECTORY}/.spec/requirements/REQ-010.md": requirement("REQ-010", "単一ワークスペースの基準", "REQ-010:AC-01"),
        f"{NESTED_DIRECTORY}/.spec/bitz.yaml": nested_config(),
        f"{NESTED_DIRECTORY}/.spec/requirements/REQ-020.md": requirement("REQ-020", "入れ子の基準", "REQ-020:AC-01"),
        f"{NESTED_MEMBER_DIRECTORY}/.spec/bitz.yaml": multi_reference.plain_config("m"),
        f"{NESTED_MEMBER_DIRECTORY}/.spec/requirements/REQ-030.md": requirement("REQ-030", "入れ子のメンバーの基準", "REQ-030:AC-01"),
    }


def x_files():
    """`SINGLE-055`と同じ単一ワークスペースを、メンバーの配下の除外へ置く（`verify REQ-001`が通る）。"""
    return {f"{X_DIRECTORY}/{name}": data.decode() for name, data in verify_fixtures.reviewed_inputs("SINGLE-055").items()}


def reviewed_inputs(identifier):
    """`repo/`の全入力と`changes/`の全入力。(repo, changes)のファイル名→バイト列の辞書を返す。"""
    case_ = CASES[identifier]
    tree, changes = case_["tree"], {}
    repo = base_files(case_["exclude"])
    if tree in {"full", "api-missing", "anchor", "nested-unregistered", "nested-changes", *UNTRUSTED_ROOT}:
        repo.update(cases_files())
        repo.update(x_files())
    if tree in UNTRUSTED_ROOT:
        repo[multi_reference.ROOT_CONFIG_PATH] = ROOT_HEADER + "multiWorkspace:\n" + UNTRUSTED_ROOT[tree]
    if tree == "api-missing":
        # メンバー`api`のディレクトリは実在するが、設定を持たない（外側のほかの不備）。
        del repo[multi_reference.API_CONFIG_PATH]
        repo["services/api/tests/test_audit.py"] = "def test_audit():\n    assert True\n"
    elif tree == "anchor":
        repo[multi_reference.ROOT_CONFIG_PATH] = repo[multi_reference.ROOT_CONFIG_PATH].replace("language: ja\n", "language: &label ja\n")
    elif tree == "nested-unregistered":
        repo[f"{NESTED_UNREGISTERED_DIRECTORY}/.spec/bitz.yaml"] = multi_reference.plain_config("z")
    elif tree == "nested-changes":
        repo[NESTED_CHANGED_TECH] = technical("TECH-021", "入れ子の実装方針", "変更前の本文。")
        repo[OUTSIDE_CODE_PATH] = "def open_session():\n    return True\n"
        changes["TECH-021.md"] = technical("TECH-021", "入れ子の実装方針", "変更後の本文。")
        changes["extra.py"] = "def extra():\n    return True\n"
        changes["REQ-001.md"] = requirement("REQ-001", "認証の基準", "REQ-001:AC-01", "秘密情報を出力せず記録もしない")
        changes["session.py"] = "def open_session():\n    return False\n"
        changes["outside.py"] = "def outside():\n    return True\n"
    elif tree not in {"base", "full", *UNTRUSTED_ROOT}:
        raise ValueError(f"未知の入力の種類です: {tree}")
    return ({name: data.encode() for name, data in repo.items()}, {name: data.encode() for name, data in changes.items()})


def reviewed_manifest(identifier):
    case_ = CASES[identifier]
    manifest = {
        "fixtureId": identifier,
        "description": case_["description"],
        "setup": {"git": True, "baseCommit": {"message": "base", "paths": ["."]}, "operations": copy.deepcopy(case_["operations"])},
        "invocation": {"runner": "bitz", "cwd": case_["cwd"], "argv": [*case_["argv"], "--format", "json"], "env": {}},
    }
    if has_result(identifier):
        manifest["expect"] = {"status": case_["status"], "exitCode": case_["exit"], "stdout": "json",
                              "resultFile": RESULT_FILES[case_["op"]], "reportFileCount": 0}
    else:
        manifest["expect"] = {"exitCode": 4, "stdout": "none", "reportFileCount": 0}
    return manifest


# --- レビュー済みの期待結果 -----------------------------------------------------------------

def revision(dirty):
    return {"base": COMMIT, "commit": COMMIT, "dirty": dirty}


def stop_diagnostic(cause, unregistered_paths=()):
    code, status, summary, key = CAUSES[cause]
    if cause == "unregistered-git":
        return [{"code": code, "severity": "error", "resultStatus": status, "summary": summary,
                 "source": {"kind": "file", "workspaceId": None, "path": path}} for path in unregistered_paths]
    return [{"code": code, "severity": "error", "resultStatus": status, "summary": summary,
             "source": {"kind": "file", "workspaceId": ROOT_ID, "path": ".spec/bitz.yaml", "key": key}}]


def workspace_entry(identifier, path, counts):
    return {"id": identifier, "path": path, "status": "passed", "checkedDocumentCount": counts[0],
            "checkedStatementCount": counts[1], "durationMs": 0, "diagnostics": []}


def reviewed_check_result(identifier):
    case_ = CASES[identifier]
    expected, cause = case_["expected"], case_["cause"]
    diagnostics = stop_diagnostic(cause, expected.get("unregistered", ())) if cause else []
    head = {"schemaVersion": "1.0", "operation": "check", "status": case_["status"]}
    tail = {"durationMs": 0, "diagnostics": diagnostics}
    if "--all-workspaces" in case_["argv"]:
        return {**head, "scope": "all-workspaces", "multiWorkspace": {"id": expected["root"], "path": "."},
                "workspaces": [workspace_entry(*entry[:2], entry[2:]) for entry in expected["workspaces"]],
                "revision": revision(expected["dirty"]), **tail}
    scope = "full" if "--full" in case_["argv"] else "changed"
    if scope == "changed":
        selection = expected.get("selection", (0, 0, 0))
        detail = {"selection": {"changedPathCount": selection[0], "targetDocumentCount": selection[1],
                                "excludedCodeTestPathCount": selection[2]}}
    else:
        detail = {"checkedDocumentCount": expected["counts"][0], "checkedStatementCount": expected["counts"][1]}
    return {**head, "scope": scope, "workspace": dict(expected["workspace"]), "revision": revision(expected["dirty"]),
            **detail, **tail}


def workspace_checks(status="passed"):
    return [{"name": "workspace", "status": "passed"}, {"name": "config", "status": "passed"}, {"name": "schema", "status": "passed"},
            {"name": "ears", "status": "passed"}, {"name": "command", "status": status}, {"name": "impact", "status": "info"}]


def reviewed_doctor_result(identifier):
    case_ = CASES[identifier]
    expected, cause = case_["expected"], case_["cause"]
    head = {"schemaVersion": "1.0", "operation": "doctor", "status": case_["status"]}
    tail = {"durationMs": 0}
    if "--all-workspaces" not in case_["argv"]:
        # 単独の`doctor`: 全体事前検査が成功したので、検査6の`catalog`を`config`の後、`schema`の前に置く（`doctor` §3）。
        names = ["core", "workspace", "config", "catalog", "schema", "ears", "git", "command", "impact"]
        return {**head, "workspace": dict(expected["workspace"]), "core": dict(CORE),
                "checks": [{"name": name, "status": "info" if name == "impact" else "passed"} for name in names],
                **tail, "diagnostics": []}
    top = {**head, "multiWorkspace": {"id": expected["root"], "path": "."}, "core": dict(CORE)}
    if cause:
        return {**top, "checks": [{"name": "core", "status": "passed"}, {"name": "git", "status": "passed"},
                                  {"name": "catalog", "status": "blocked"}],
                "workspaces": [], **tail, "diagnostics": stop_diagnostic(cause, expected.get("unregistered", ()))}
    return {**top, "checks": [{"name": name, "status": "passed"} for name in ("core", "git", "catalog")],
            "workspaces": [{"id": entry[0], "path": entry[1], "status": "passed", "checks": workspace_checks(),
                            "durationMs": 0, "diagnostics": []} for entry in expected["workspaces"]],
            **tail, "diagnostics": []}


def reviewed_verify_result(identifier):
    """`SINGLE-055`と同じ入力と結果。コミットがあるので`revision`は`{commit, dirty}`である。"""
    result = copy.deepcopy(verify_fixtures.reviewed_result("SINGLE-055"))
    expected = CASES[identifier]["expected"]
    result["workspace"] = dict(expected["workspace"])
    result["revision"] = {"commit": COMMIT, "dirty": expected["dirty"]}
    return result


def reviewed_result(identifier):
    return {"check": reviewed_check_result, "doctor": reviewed_doctor_result,
            "verify": reviewed_verify_result}[operation(identifier)](identifier)


# --- 参照計算 --------------------------------------------------------------------------------

def forbidden_yaml(text):
    """禁止されたYAML（アンカー、エイリアス、タグ）。この参照計算は、fixtureの入力が使う限られた形だけを扱う。"""
    for line in text.splitlines():
        if any(token[:1] in {"&", "*", "!"} for token in line.split("#", 1)[0].split()):
            return True
    return False


def scalar(text):
    text = text.strip()
    return text[1:-1] if len(text) >= 2 and text[0] == '"' and text[-1] == '"' else text


def parse_config(text):
    """この群の設定が使う限られた形（トップレベルのキー、1段のマッピング、`members`の配列、`exclude`の配列または文字列）だけを読む。"""
    config, top, second = {}, None, None
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent, body = len(raw) - len(raw.lstrip(" ")), raw.strip()
        key, _, value = body.partition(":")
        if indent == 0:
            config[key], top, second = (scalar(value) if value.strip() else {}), key, None
        elif indent == 2 and top is not None:
            config[top][key] = ([] if value.strip() == "[]" else scalar(value)) if value.strip() else []
            second = key
        elif body.startswith("- ") and top == "multiWorkspace" and second is not None:
            item = body[2:]
            if ":" in item:
                name, _, content = item.partition(":")
                config[top][second].append({name.strip(): scalar(content)})
            else:
                config[top][second].append(scalar(item))
        elif indent == 6 and top == "multiWorkspace" and second == "members":
            config[top][second][-1][key] = scalar(value)
    return config


def read_config(repository, directory):
    """(状態, 設定)。状態は`missing`、`unreadable`（禁止されたYAML）、`ok`。"""
    path = repository / directory / ".spec/bitz.yaml"
    if not path.is_file():
        return "missing", None
    text = path.read_text(encoding="utf-8")
    return ("unreadable", None) if forbidden_yaml(text) else ("ok", parse_config(text))


def major(value):
    return int(str(value).split(".")[0])


def versions_supported(config):
    return major(config["schemaVersion"]) == SUPPORTED_MAJOR and major(config["earsAi"]) == SUPPORTED_MAJOR


def lexical_problem(path):
    """メンバーのパスと同じ字句の規則: 絶対パス、空のパス（末尾の`/`を含む）、`.`、`..`、globを禁止する。"""
    if not isinstance(path, str) or not path or path.startswith("/"):
        return True
    parts = path.split("/")
    return any(part in {"", ".", ".."} or set(part) & GLOB_CHARACTERS for part in parts)


def exclude_problem(config):
    """`multiWorkspace`の設定不適合と除外の規則（複合ワークスペース仕様 §2・§2.1、ADR-064 決定1・3）。違反の原因（`CAUSES`のキー）を、検査の順に1件返す。なければ`None`。

    `members`の不在、型、0件、`maxMembers`の範囲は設定不適合で、`exclude`のメンバーのパスとの重なりを判定できないので、除外を信用しない。
    """
    multi = config["multiWorkspace"]
    if "maxMembers" in multi:
        value = multi["maxMembers"]
        if not (isinstance(value, str) and value.isdigit() and 1 <= int(value) <= 100):
            return "max-members"
    members = multi.get("members")
    if members is None or members == []:
        return "members-required"
    if not isinstance(members, list):
        return "members-type"
    raw = multi.get("exclude", [])
    if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
        return "exclude-type"
    if len(raw) > MAX_EXCLUDE:
        return "exclude-count"
    if any(lexical_problem(item) for item in raw):
        return "exclude-format"
    parts = [tuple(item.split("/")) for item in raw]
    if any(".spec" in part for part in parts):
        return "exclude-spec"
    if len(set(parts)) != len(parts):
        return "exclude-duplicate"
    if any(a != b and b[:len(a)] == a for a in parts for b in parts):
        return "exclude-nested"
    member_paths = [tuple(member["path"].split("/")) for member in members]
    if any(member[:len(excluded)] == excluded for member in member_paths for excluded in parts):
        return "member-excluded"
    return None


def within(path, directory):
    """ディレクトリの単位の前方一致。"""
    path, directory = PurePosixPath(path).parts, PurePosixPath(directory).parts
    return path[:len(directory)] == directory


def join(base, relative):
    return PurePosixPath(base, relative).as_posix()


def relative(path, base):
    return PurePosixPath(path).relative_to(PurePosixPath(base)).as_posix()


def nearest_config_directory(repository, start, floor="."):
    """`start`から親の方向へ、`floor`を限りに、最も近い設定のディレクトリを返す。"""
    current = PurePosixPath(start)
    while True:
        if (repository / current / ".spec/bitz.yaml").is_file():
            return current.as_posix()
        if current.as_posix() == floor or current.as_posix() == ".":
            return None
        current = current.parent


def declares(repository, directory):
    """`multiWorkspace`を宣言した設定か。読めない設定は宣言しないものとみなす（複合ワークスペース仕様 §2.1）。"""
    state, config = read_config(repository, directory)
    return state == "ok" and "multiWorkspace" in config


def chain(start, directory):
    """除外のディレクトリ自身を含め、そこから開始位置までの経路のディレクトリ。"""
    relative_parts = PurePosixPath(relative(start, directory)).parts
    result = [directory]
    for index in range(1, len(relative_parts) + 1):
        result.append(join(directory, "/".join(relative_parts[:index])))
    return result if relative(start, directory) != "." else [directory]


def recognized_configs(repository):
    """Gitが認識する`.spec/bitz.yaml`（`HEAD`と現在のスナップショット）。"""
    def configs(names):
        return {name for name in names if name == ".spec/bitz.yaml" or name.endswith("/.spec/bitz.yaml")}

    head = configs(git(repository, "-c", "core.quotePath=false", "ls-tree", "-r", "-z", "--name-only", "HEAD").decode().split("\0"))
    listed = git(repository, "-c", "core.quotePath=false", "ls-files", "-z", "--cached", "--others", "--exclude-standard").decode().split("\0")
    return head, configs(name for name in listed if name and (repository / name).exists())


def outer_scope(repository, base, config, cwd, problem, excluded):
    declared = config["multiWorkspace"].get("members")
    # 型の不正や不在のカタログは作れない。ルートワークスペースだけを置く（停止の原因は`problem`が持つ）。
    members = ({join(base, member["path"]): member["id"] for member in declared} if isinstance(declared, list) else {})
    catalog = {base: config["workspace"]["id"], **members}
    nearest = nearest_config_directory(repository, cwd, base)
    state, near_config = read_config(repository, nearest) if nearest else ("missing", None)
    registered = (nearest in catalog and state == "ok" and near_config.get("workspace", {}).get("id") == catalog[nearest])
    head, current = recognized_configs(repository)
    prefix = "" if base == "." else base + "/"
    listed = sorted(name for name in head | current
                    if name.startswith(prefix) and not any(within(name, item) for item in excluded))
    catalog_configs = {join(path, ".spec/bitz.yaml") for path in catalog}
    return {"kind": "multi", "base": base, "config": config, "problem": problem, "excluded": list(excluded),
            "catalog": catalog, "nearest": nearest,
            "workspace": ({"id": catalog[nearest], "path": relative(nearest, base)} if registered
                          else {"id": None, "path": relative(nearest, base) if nearest else "."}),
            "unregistered_selected": [] if registered or nearest is None else [relative(join(nearest, ".spec/bitz.yaml"), base)],
            "unregistered_git": sorted(relative(name, base) for name in listed if name not in catalog_configs),
            "missing_members": sorted(path for path in members if not (repository / path / ".spec/bitz.yaml").is_file())}


def composite_scope(repository, base, config, cwd):
    """複合ワークスペースのルート`base`の設定`config`で、探索の開始位置`cwd`の場所を決める（複合ワークスペース仕様 §2.1・§3、ADR-064 決定3・4）。"""
    problem, excluded = None, []
    if versions_supported(config):
        problem = exclude_problem(config)
        if problem is None:
            raw = config["multiWorkspace"].get("exclude", [])
            excluded = [join(base, item) for item in raw]
    # 除外を信用できない（読めない、版が非対応、`exclude`が不正）ときは、除外した範囲を決めず、外側の規則で決める。
    hit = next((item for item in excluded if within(cwd, item)), None)
    if hit is not None:
        path = chain(cwd, hit)
        declaring = [directory for directory in path if declares(repository, directory)]
        if declaring:
            _, nested_config_ = read_config(repository, declaring[0])
            nested = composite_scope(repository, declaring[0], nested_config_, cwd)
            nested["via"] = "nested"
            return nested
        if any((repository / directory / ".spec/bitz.yaml").is_file() for directory in path):
            directory = nearest_config_directory(repository, cwd)
            _, near = read_config(repository, directory)
            return {"kind": "single", "directory": directory, "via": "excluded",
                    "workspace": {"id": near.get("workspace", {}).get("id", "root"), "path": "."}}
    scope = outer_scope(repository, base, config, cwd, problem, excluded)
    scope["via"] = "outer"
    return scope


def reference_scope(repository, cwd):
    """参照計算: 入力の木構造とGitの状態から、探索の開始位置の場所を導く。Gitのあるリポジトリだけを扱う。"""
    state, config = read_config(repository, ".")
    if state != "ok" or "multiWorkspace" not in config:
        # 通常の単一ワークスペースの探索（複合ワークスペース仕様 §3の手順1。読めない設定は`multiWorkspace`の有無を判定しない）。
        directory = nearest_config_directory(repository, cwd)
        near_state, near = read_config(repository, directory)
        if near_state != "ok":
            raise ValueError("最も近い設定を読めません")
        return {"kind": "single", "directory": directory, "via": "plain",
                "workspace": {"id": near.get("workspace", {}).get("id", "root"), "path": "."}}
    return composite_scope(repository, ".", config, cwd)


def cause_of(scope, op, all_workspaces):
    """全体事前検査が止まる原因（`CAUSES`のキー）。止まらなければ`None`。"""
    if scope["kind"] == "single":
        return None
    if scope["problem"] is not None:
        return scope["problem"]
    enumerated = all_workspaces or op == "doctor"
    if scope["missing_members"]:
        return "member-missing"
    if enumerated and scope["unregistered_git"]:
        return "unregistered-git"
    if scope["unregistered_selected"]:
        return "unregistered-selected"
    return None


def workspace_documents(repository, directory):
    """ワークスペースの文書数と規範文数（`check`の完全検査の対象）。"""
    documents = digest_crosscheck.load_documents(repository / directory)
    return len(documents), sum(len(read_statements(item["body"])) for item in documents.values())


def expected_workspaces(repository, scope):
    """`--all-workspaces`の`workspaces[]`: ルートワークスペースを先頭に、その後をIDのコードポイント順に並べる。"""
    base = scope["base"]
    root_id = scope["catalog"][base]
    others = sorted((identifier, path) for path, identifier in scope["catalog"].items() if path != base)
    entries = [(root_id, ".", base)] + [(identifier, relative(path, base), path) for identifier, path in others]
    return [(identifier, path, *workspace_documents(repository, directory)) for identifier, path, directory in entries]


def changed_paths(repository):
    output = git(repository, "-c", "core.quotePath=false", "status", "--porcelain=v1", "-z", "--untracked-files=all").decode()
    return [entry[3:] for entry in output.split("\0") if entry]


def selection_counts(repository, base):
    """`check`の引数なしの変更集合の件数（`check` §5・§6）。`base`の外のパスはどのワークスペースにも属さないので数えない。"""
    prefix = "" if base == "." else base + "/"
    inside = [name[len(prefix):] for name in changed_paths(repository) if name.startswith(prefix)]
    documents = digest_crosscheck.load_documents(repository / base)
    by_path = {item["path"]: identifier for identifier, item in documents.items()}
    owned = {path: identifier for identifier, item in documents.items()
             for path in [*item["frontmatter"].get("implements", [])]}
    targets, excluded = set(), 0
    for name in inside:
        owner = by_path.get(name) or owned.get(name)
        if owner is not None:
            targets.add(owner)
        else:
            excluded += 1
    return len(inside), len(targets), excluded


def git_dirty(repository):
    return bool(git(repository, "status", "--porcelain=v1", "--untracked-files=all").strip())


def reference_decision(repository, op, cwd, argv):
    """導いた場所と、操作ごとの停止の原因・結果のパスを返す。"""
    all_workspaces = "--all-workspaces" in argv
    scope = reference_scope(repository, cwd)
    if scope["kind"] == "single":
        return {"scope": scope, "argument_error": all_workspaces, "cause": None, "workspace": scope["workspace"]}
    cause = cause_of(scope, op, all_workspaces)
    return {"scope": scope, "argument_error": False, "cause": cause, "workspace": scope["workspace"]}


def check_against_reference(identifier, result, reference, repository):
    """リテラルの期待値が、入力と参照計算から導いた値と一致することを要求する。"""
    case_ = CASES[identifier]
    scope, cause = reference["scope"], reference["cause"]
    if reference["argument_error"] != (case_["exit"] == 4):
        raise ValueError("引数不正の有無が入力からの参照計算と異なります")
    if result is None:
        return
    if cause != case_["cause"]:
        raise ValueError("停止の原因が入力からの参照計算と異なります")
    all_workspaces = "--all-workspaces" in case_["argv"]
    if cause is not None:
        code, status, summary, key = CAUSES[cause]
        if [(item["code"], item["resultStatus"], item["summary"]) for item in result["diagnostics"]][:1] != [(code, status, summary)]:
            raise ValueError("診断が停止の原因と異なります")
        if result["status"] != status:
            raise ValueError("状態が停止の原因と異なります")
        if cause == "unregistered-git":
            if [item["source"]["path"] for item in result["diagnostics"]] != scope["unregistered_git"] or any(
                    item["source"]["workspaceId"] is not None for item in result["diagnostics"]):
                raise ValueError("未登録の設定のパスが入力からの参照計算と異なります")
        elif result["diagnostics"][0]["source"].get("key") != key or len(result["diagnostics"]) != 1:
            raise ValueError("診断の発生元が入力からの参照計算と異なります")
        if all_workspaces and result["workspaces"] != []:
            raise ValueError("停止した全体操作は`workspaces`を空にします")
    elif result["diagnostics"] or result["status"] != "passed":
        raise ValueError("止まらない操作は診断を持たず通ります")
    if all_workspaces:
        if scope["kind"] != "multi" or result["multiWorkspace"] != {"id": scope["catalog"][scope["base"]], "path": "."}:
            raise ValueError("`multiWorkspace`が入力からの参照計算と異なります")
        if cause is None:
            derived = expected_workspaces(repository, scope)
            if op_of(result) == "check":
                actual = [(item["id"], item["path"], item["checkedDocumentCount"], item["checkedStatementCount"]) for item in result["workspaces"]]
            else:
                actual = [(item["id"], item["path"], *workspace_documents(repository, join(scope["base"], item["path"])))
                          for item in result["workspaces"]]
            if actual != derived:
                raise ValueError("`workspaces`が入力からの参照計算と異なります")
    else:
        if result["workspace"] != reference["workspace"]:
            raise ValueError("`workspace`が入力からの参照計算と異なります")
        if op_of(result) == "check" and cause is None:
            directory = scope["directory"] if scope["kind"] == "single" else join(scope["base"], reference["workspace"]["path"])
            if result["scope"] == "full" and (result["checkedDocumentCount"], result["checkedStatementCount"]) != workspace_documents(repository, directory):
                raise ValueError("文書数または規範文数が入力からの参照計算と異なります")
            if result["scope"] == "changed":
                base = "." if scope["kind"] == "single" else scope["base"]
                derived = selection_counts(repository, base)
                if (result["selection"]["changedPathCount"], result["selection"]["targetDocumentCount"],
                        result["selection"]["excludedCodeTestPathCount"]) != derived:
                    raise ValueError("`selection`が入力からの参照計算と異なります")
    if op_of(result) in {"check", "verify"}:
        expected_dirty = git_dirty(repository)
        if result["revision"]["dirty"] != expected_dirty:
            raise ValueError("`revision.dirty`がGitの状態と異なります")


def op_of(result):
    return result["operation"]


def check_conditions(identifier, repository):
    """原因の構成を、散文ではなく準備手順の後の入力とGitの状態から確かめる。"""
    case_ = CASES[identifier]
    if not (repository / ".git").exists():
        raise ValueError("Gitのあるfixtureです")
    reference = reference_decision(repository, case_["op"], case_["cwd"], case_["argv"])
    scope = reference["scope"]
    head, current = recognized_configs(repository)
    if identifier in {"MULTI-037-01", "MULTI-037-02"}:
        # 除外した範囲の中の設定がGitで追跡され、カタログにない。除外がなければ全体事前検査が止まる（陰性対照）。
        listed = sorted(head | current)
        if not {f"{SINGLE_DIRECTORY}/.spec/bitz.yaml", f"{NESTED_DIRECTORY}/.spec/bitz.yaml",
                f"{NESTED_MEMBER_DIRECTORY}/.spec/bitz.yaml", f"{X_DIRECTORY}/.spec/bitz.yaml"} <= set(listed):
            raise ValueError("除外した範囲の中の設定がGitで追跡されている必要があります")
        no_exclude = outer_scope(repository, ".", scope["config"], ".", None, [])
        if len(no_exclude["unregistered_git"]) != 4 or scope["unregistered_git"]:
            raise ValueError("除外しなければ4件が未登録になり、除外すれば0件である必要があります")
    if identifier in {"MULTI-037-03", "MULTI-037-19"}:
        if scope["kind"] != "single" or scope["directory"] != SINGLE_DIRECTORY or declares(repository, SINGLE_DIRECTORY):
            raise ValueError("`cases/single`は`multiWorkspace`を宣言しない単一の設定である必要があります")
    if identifier == "MULTI-037-04" and (scope["kind"] != "single" or not reference["argument_error"]):
        raise ValueError("単一ワークスペースの`--all-workspaces`は引数不正である必要があります")
    if identifier in {"MULTI-037-05", "MULTI-037-06", "MULTI-037-07", "MULTI-037-22", "MULTI-037-23"}:
        if scope["kind"] != "multi" or scope["via"] != "nested" or scope["base"] != NESTED_DIRECTORY:
            raise ValueError("入れ子の複合ワークスペースのルートは`cases/nested`である必要があります")
    if identifier == "MULTI-037-06":
        # 最寄りの設定はメンバー`m`（入れ子のルートではない）。除外のディレクトリに最も近い宣言を入れ子のルートにする。
        if nearest_config_directory(repository, case_["cwd"]) != NESTED_MEMBER_DIRECTORY or declares(repository, NESTED_MEMBER_DIRECTORY):
            raise ValueError("最寄りの設定は、`multiWorkspace`を宣言しないメンバー`m`である必要があります")
    if identifier == "MULTI-037-08":
        if scope["kind"] != "single" or scope["directory"] != X_DIRECTORY or declares(repository, X_DIRECTORY):
            raise ValueError("`x`は`multiWorkspace`を宣言しない単一の設定である必要があります")
        derived = digest_crosscheck.digest(digest_crosscheck.canonical_bytes(digest_crosscheck.build(repository / X_DIRECTORY)))
        if derived != verify_fixtures.GOLDEN:
            raise ValueError("ハッシュ値の参照計算が`SINGLE-055`のgolden値と異なります")
    if identifier in {f"MULTI-037-{number:02d}" for number in range(9, 18)}:
        if scope["via"] != "outer" or scope["problem"] != case_["cause"]:
            raise ValueError("除外の不正の原因が入力からの参照計算と異なります")
    if identifier in {f"MULTI-037-{number}" for number in range(24, 28)}:
        # `multiWorkspace`が設定不適合なら、妥当な`exclude: [cases]`も信用しない。信用すれば`cases/single`は除外の中の単一ワークスペースになる（陰性対照）。
        if scope["kind"] != "multi":
            raise ValueError("`multiWorkspace`が設定不適合で、除外を決めない必要があります")
        raw = scope["config"]["multiWorkspace"].get("exclude")
        if scope["via"] != "outer" or scope["problem"] != case_["cause"] or raw != ["cases"] or scope["excluded"]:
            raise ValueError("`multiWorkspace`の設定不適合で除外を決めず、外側の規則で`cases/single`を扱う必要があります")
        if reference["workspace"] != {"id": None, "path": SINGLE_DIRECTORY} or exclude_problem({"multiWorkspace": {**scope["config"]["multiWorkspace"],
                "members": [{"id": "web", "path": "apps/web"}], "maxMembers": "20"}}) is not None:
            raise ValueError("`exclude`だけは妥当である必要があります")
    if identifier == "MULTI-037-18":
        # 除外が信用できれば`cases/single`は除外の中の単一ワークスペースになる（陰性対照）。
        if scope["via"] != "outer" or "cases" not in case_["exclude"] or reference["workspace"] != {"id": None, "path": SINGLE_DIRECTORY}:
            raise ValueError("除外を信用できず、外側の規則で`cases/single`が未登録になる必要があります")
    if identifier == "MULTI-037-19":
        # 同じ入力でルートから実行すると、メンバーの設定の不在で止まる（陰性対照）。
        outer = reference_decision(repository, "check", ".", ["check", "--base", "HEAD"])
        if outer["cause"] != "member-missing" or (repository / multi_reference.API_CONFIG_PATH).exists() or not (repository / "services/api").is_dir():
            raise ValueError("メンバー`api`のディレクトリは実在し、設定が不在である必要があります")
    if identifier == "MULTI-037-20" and (repository / "generated").exists():
        raise ValueError("除外のディレクトリは存在してはいけません")
    if identifier == "MULTI-037-21":
        text = (repository / multi_reference.ROOT_CONFIG_PATH).read_text()
        if not forbidden_yaml(text) or "multiWorkspace:" not in text or not declares(repository, NESTED_DIRECTORY):
            raise ValueError("外側のルートの設定は読めず、`cases/nested`は`multiWorkspace`を宣言する必要があります")
        if scope["kind"] != "single" or scope["via"] != "plain" or scope["directory"] != NESTED_DIRECTORY:
            raise ValueError("最も近い設定を単一ワークスペースとして使う必要があります")
        if forbidden_yaml(root_config(EXCLUDE)):
            raise ValueError("正しいルートの設定は禁止されたYAMLを含んではいけません")
    if identifier == "MULTI-037-22":
        # リポジトリ全体を列挙すると、入れ子の外の設定も未登録になる（陰性対照）。入れ子の範囲は`tools/z`だけである。
        whole = sorted(name for name in head | current)
        if f"{NESTED_UNREGISTERED_DIRECTORY}/.spec/bitz.yaml" not in whole or len(whole) <= 5:
            raise ValueError("入れ子の中に未登録の設定があり、入れ子の外にも設定がある必要があります")
        if scope["unregistered_git"] != ["tools/z/.spec/bitz.yaml"]:
            raise ValueError("入れ子のルート相対の未登録の設定は`tools/z`の1件である必要があります")
    if identifier == "MULTI-037-23":
        inside = [name for name in changed_paths(repository) if name.startswith(NESTED_DIRECTORY + "/")]
        outside = [name for name in changed_paths(repository) if not name.startswith(NESTED_DIRECTORY + "/")]
        if len(inside) != 2 or len(outside) != 3 or not git_dirty(repository):
            raise ValueError("入れ子の中の変更は2件、外の変更は3件で、作業ツリーは変更されている必要があります")
    if identifier not in {"MULTI-037-23"} and git_dirty(repository):
        raise ValueError("このfixtureの作業ツリーはコミット済みと同じである必要があります")
    return reference


def _dump(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def generate(root=HERE):
    """レビュー済みの入力と期待値からfixtureを書き出す。副作用の期待値は、隔離した準備手順の観測で作る（Coreは実行しない）。"""
    for identifier in CASES:
        fixture = root / "multi" / identifier
        repo, changes = reviewed_inputs(identifier)
        for prefix, files in (("repo", repo), ("changes", changes)):
            for name, content in files.items():
                path = fixture / prefix / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
        manifest = reviewed_manifest(identifier)
        (fixture / "manifest.json").write_text(_dump(manifest))
        if has_result(identifier):
            (fixture / "expected").mkdir(parents=True, exist_ok=True)
            (fixture / RESULT_FILES[operation(identifier)]).write_text(_dump(reviewed_result(identifier)))
        else:
            (fixture / "cli-output.json").write_text(_dump(cli_output(identifier)))
        with tempfile.TemporaryDirectory(prefix="bitz-multi-exclude-") as temporary:
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
    frontmatter = json.loads(schema_path(root, "frontmatter").read_text())
    kinds = {"requirement": "reqFrontmatter", "technical": "techFrontmatter", "decision": "adrFrontmatter", "task": "taskFrontmatter"}
    for identifier in CASES:
        if identifiers is not None and identifier not in identifiers:
            continue
        fixture = root / "multi" / identifier
        try:
            manifest = json.loads((fixture / "manifest.json").read_text())
            effects = json.loads((fixture / "side-effects.json").read_text())
            checks = [("manifest", manifest), ("side-effects", effects)]
            result = None
            if has_result(identifier):
                result = json.loads((fixture / RESULT_FILES[operation(identifier)]).read_text())
                checks.append(("result", result))
                if result != reviewed_result(identifier):
                    raise ValueError("完全結果がレビュー済みの期待値と異なります")
                if (fixture / "cli-output.json").exists():
                    raise ValueError("結果を返すfixtureは`cli-output.json`を持ちません")
            else:
                if (fixture / "expected").exists():
                    raise ValueError("引数不正のfixtureは期待結果のファイルを持ちません")
                if json.loads((fixture / "cli-output.json").read_text()) != cli_output(identifier):
                    raise ValueError("CLI出力の期待値がレビュー済みの契約と異なります")
            for key, value in checks:
                validators[key].validate(value)
            if manifest != reviewed_manifest(identifier):
                raise ValueError("起動条件がレビュー済みの期待値と異なります")
            repo, changes = reviewed_inputs(identifier)
            entries = {}
            for directory in ("repo", "changes"):
                for path in (fixture / directory).rglob("*"):
                    if path.is_symlink() or path.is_file():
                        entries[(directory, path.relative_to(fixture / directory).as_posix())] = (
                            None if path.is_symlink() else path.read_bytes())
            expected_entries = {("repo", name): data for name, data in repo.items()}
            expected_entries.update({("changes", name): data for name, data in changes.items()})
            if entries != expected_entries:
                raise ValueError("入力がレビュー済みのcorpusと異なります")
            if effects["policy"] != "read-only" or effects["before"] != effects["after"]:
                raise ValueError("読取り専用の期待値が書込みを許しています")
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-multi-exclude-") as temporary:
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
                    for path in sorted(repository.rglob("*.md")):
                        directory = path.parent.name
                        if path.parent.parent.name == ".spec" and directory in KIND_BY_DIRECTORY:
                            frontmatter_value, _ = split_document(path.read_text(encoding="utf-8"))
                            Draft202012Validator({"$ref": "#/$defs/" + kinds[KIND_BY_DIRECTORY[directory]],
                                                  "$defs": frontmatter["$defs"]}).validate(frontmatter_value)
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, IndexError, ValidationError,
                subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "references": 1, "status": "Passed" if not errors else "Failed", "errors": errors}
