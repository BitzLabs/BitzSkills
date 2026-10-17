"""複合ワークスペースの単独操作が、全体事前検査で停止することを固定する（Coreの公開操作は実行しない）。

複合ワークスペース仕様 §7とADR-063は、複合ワークスペースの単独の`context`、`check`、`verify`、`doctor`が、作業ワークスペースの処理の前に
全体事前検査を行い、非成功なら処理を始めずに、全体事前検査の診断を最上位の`diagnostics`に置いた単独結果を返すと定める（実装の確認事項C27）。
この群は、その停止と、停止しない境界を、13件で固定する。基本のリポジトリは`MULTI-019`と同じ形（ルート`platform`、メンバー`web`〈`apps/web`〉と
`api`〈`services/api`〉）である。

| fixture | 操作と実行ディレクトリ | 原因と期待 |
|---|---|---|
| `MULTI-036-01` | `check`（引数なし）、`tools/x` | 最も近い設定`tools/x/.spec/bitz.yaml`がカタログにない。`blocked`／2。`workspace`は`{null, tools/x}` |
| `MULTI-036-02` | `context web::REQ-010 --workspace web`、`tools/x` | `--workspace`があっても同じ未登録で止まる。`context`の停止結果は複合固有のフィールドを持たない |
| `MULTI-036-03` | `verify`（引数なし）、`apps/web` | メンバー`api`の設定がない（`SPEC-MULTI-MEMBER-001`）。`failed`／1。`targetResults`と`commands`は空 |
| `MULTI-036-04` | `check`、ルート。Git不在 | `SPEC-MULTI-GIT-001`。`revision: null`。Git不在なので`scope: full` |
| `MULTI-036-05` | `check`、ルート直下の`.spec`のない`docs`。Git不在 | 最も近い設定がルートの設定なので`036-04`と同じく止まる |
| `MULTI-036-06` | `check`、`apps/web`。Git不在 | 最も近い設定が`multiWorkspace`を宣言しないので、単一ワークスペースの縮退（`SINGLE-037`の形）。止まらない |
| `MULTI-036-07` | `context platform::REQ-001`、ルート | ルートの`earsAi`が非対応のメジャーバージョン。`multiWorkspace`の宣言があるので複合と判定して止まる（`SPEC-EARS-VERSION-001`） |
| `MULTI-036-08` | `check --full`、ルート | ルートの設定を読めない（禁止されたYAMLのアンカー）。複合と判定せず、単一ワークスペースの設定の停止（`SINGLE-091`の形） |
| `MULTI-036-09` | `check --full --workspace nope`、`apps/web` | カタログにない`--workspace`でも、全体事前検査が非成功なら終了コード4にせず`SPEC-MULTI-MEMBER-001`を返す |
| `MULTI-036-10` | `doctor`、ルート | `HEAD`のコミットにだけ未登録の設定がある。Gitが認識する設定の比較で止まる。`checks`は`core`、`git`、`catalog` |
| `MULTI-036-11` | `doctor`、ルート。Git不在 | `checks`は`core`、`git`（`blocked`）。`MULTI-019`の単独版 |
| `MULTI-036-12` | `verify`（引数なし）、`apps/web` | 無関係な場所にカタログにない設定がある。単独の`verify`はリポジトリ全体を列挙しないので止まらず、`MULTI-034-05`と同じ結果 |
| `MULTI-036-13` | `doctor`、`tools/x` | `.gitignore`で無視された未登録の設定を、最も近い設定として照合して止まる。Gitが認識する設定の比較には現れない |

期待値の根拠は規範文（複合ワークスペース仕様 §2・§3・§7・§8・§10、結果・診断・終了コード §2、`doctor` §3、ADR-063）と、このモジュールの参照計算だけである。
参照計算`reference_decision`は、入力の木構造と、準備手順の後のGitの状態から、複合かどうか、停止の原因、停止結果の`workspace`、未登録の設定の一覧を導く。
Coreの出力は期待値の根拠にしない。診断の文言は、`Coreの出力文言のレビュー記録.md`の承認済みの文字列と、ADR-063の決定7の「選択した設定ファイルがカタログに登録されていません」である。
"""
import json
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from .digest_crosscheck import KIND_BY_DIRECTORY, read_yaml, split_document
from .harness import git, setup
from .initial_fixtures import compare_state
from .multi_catalog_fixtures import observe_state
from .multi_check_fixtures import MEMBERS
from .schemas import schema_path
from . import multi_active_workspace_fixtures as active, multi_reference
from .multi_verify_fixtures import requirement

HERE = Path(__file__).resolve().parent
COMMIT = "0" * 40
CAPABILITIES = ["context.v1", "check.v1", "verify.v1", "doctor.v1", "multiWorkspace.v1"]
CORE = {"version": "1.0.0", "apiVersion": "1.0", "capabilities": CAPABILITIES}
SUPPORTED_MAJOR = 1
TOOLS_CONFIG_PATH = "tools/x/.spec/bitz.yaml"
WEB_REQ_PATH = "apps/web/.spec/requirements/REQ-010.md"
ROOT_REQ_PATH = multi_reference.ROOT_REQ_PATH

# 承認済みの診断の文言。`Coreの出力文言のレビュー記録.md`と、ADR-063の決定7。
UNREGISTERED_SELECTED = "選択した設定ファイルがカタログに登録されていません"
UNREGISTERED_GIT = "Gitが認識する設定ファイルがカタログに登録されていません"
NO_GIT = "Gitのリポジトリの境界を確定できません"
MEMBER_MISSING = "メンバーの.spec/bitz.yamlがありません"
EARS_VERSION = "未対応のEARS-AIのメジャーバージョンです"
ANCHOR = "設定YAMLのアンカーは禁止です"
GIT_DEGRADED = ("Git不在のため全体検査へ縮退します。承認済み要求の保護、状態遷移、"
                "管理済みの仕様文書の削除の差分検査は実施できません")

GIT_ABSENT_ENV = {"PATH": "/dev/null"}
# 原因: 全体事前検査が止まる原因。`None`は止まらない（単一ワークスペース、または全体事前検査が成功）。
# id: dict(操作, 実行ディレクトリ, 引数列〈`--format json`の前〉, Gitの有無, 入力の種類, 準備手順, 状態, 終了コード, 原因, 説明)
CASES = {
    "MULTI-036-01": dict(op="check", cwd="tools/x", argv=["check", "--base", "HEAD"], git=True, inputs="tools", operations=[],
                         status="blocked", exit=2, cause="unregistered-selected",
                         description="カタログにない設定の中の引数なしの`check`が、選択した設定の未登録で停止する"),
    "MULTI-036-02": dict(op="context", cwd="tools/x", argv=["context", "web::REQ-010", "--workspace", "web"], git=True,
                         inputs="tools-context", operations=[], status="blocked", exit=2, cause="unregistered-selected",
                         description="`--workspace`を指定した`context`も、選択した設定の未登録で停止する"),
    "MULTI-036-03": dict(op="verify", cwd="apps/web", argv=["verify"], git=True, inputs="no-api-config", operations=[],
                         status="failed", exit=1, cause="member",
                         description="メンバー`api`の設定がないとき、メンバーの中の引数なしの`verify`が停止する"),
    "MULTI-036-04": dict(op="check", cwd=".", argv=["check"], git=False, inputs="root", operations=[],
                         status="blocked", exit=2, cause="git",
                         description="Git不在のルートの引数なしの`check`が、Gitの境界を確定できずに停止する"),
    "MULTI-036-05": dict(op="check", cwd="docs", argv=["check"], git=False, inputs="docs", operations=[],
                         status="blocked", exit=2, cause="git",
                         description="Git不在で、設定のないサブディレクトリの`check`も、最も近いルートの設定が複合なので停止する"),
    "MULTI-036-06": dict(op="check", cwd="apps/web", argv=["check"], git=False, inputs="git-absent-member", operations=[],
                         status="passed_with_warnings", exit=0, cause=None,
                         description="Git不在のメンバーの中の`check`は、単一ワークスペースの縮退として動く"),
    "MULTI-036-07": dict(op="context", cwd=".", argv=["context", "platform::REQ-001"], git=True, inputs="ears-major", operations=[],
                         status="blocked", exit=2, cause="version",
                         description="ルートのEARS-AIのメジャーバージョンが非対応でも、`multiWorkspace`の宣言があれば複合と判定して停止する"),
    "MULTI-036-08": dict(op="check", cwd=".", argv=["check", "--full", "--base", "HEAD"], git=True, inputs="anchor", operations=[],
                         status="error", exit=3, cause=None,
                         description="ルートの設定を読めないときは複合と判定せず、単一ワークスペースの設定の停止にする"),
    "MULTI-036-09": dict(op="check", cwd="apps/web", argv=["check", "--full", "--workspace", "nope", "--base", "HEAD"], git=True,
                         inputs="no-api-config", operations=[], status="failed", exit=1, cause="member",
                         description="カタログにない`--workspace`でも、全体事前検査が非成功なら終了コード4にせず結果を返す"),
    "MULTI-036-10": dict(op="doctor", cwd=".", argv=["doctor"], git=True, inputs="tools", operations=[
                             {"op": "delete", "path": TOOLS_CONFIG_PATH}],
                         status="blocked", exit=2, cause="unregistered-git",
                         description="`HEAD`にだけ未登録の設定がある単独の`doctor`が、Gitが認識する設定の比較で停止する"),
    "MULTI-036-11": dict(op="doctor", cwd=".", argv=["doctor"], git=False, inputs="root", operations=[],
                         status="blocked", exit=2, cause="git",
                         description="Git不在のルートの単独の`doctor`が、Gitの境界を確定できずに停止する"),
    "MULTI-036-12": dict(op="verify", cwd="apps/web", argv=["verify"], git=True, inputs="unrelated-tools", operations=[],
                         status="passed", exit=0, cause=None,
                         description="無関係な場所の未登録の設定では、単独の`verify`は停止しない"),
    "MULTI-036-13": dict(op="doctor", cwd="tools/x", argv=["doctor"], git=True, inputs="ignored", operations=[
                             {"op": "create", "path": TOOLS_CONFIG_PATH, "source": "changes/x-bitz.yaml"}],
                         status="blocked", exit=2, cause="unregistered-selected",
                         description="Gitが無視する未登録の設定も、選択した設定として照合して`doctor`が停止する"),
}
RESULT_FILES = {"check": "expected/check.json", "context": "expected/context.json",
                "verify": "expected/verify.json", "doctor": "expected/doctor.json"}
# 停止の原因ごとの診断コードと結果への効果。`doctor`のEARS-AIの非対応だけ、診断のコードが異なる（この群にはない）。
CAUSE_DIAGNOSTIC = {
    "git": ("SPEC-MULTI-GIT-001", "blocked"),
    "version": ("SPEC-EARS-VERSION-001", "blocked"),
    "member": ("SPEC-MULTI-MEMBER-001", "failed"),
    "unregistered-selected": ("SPEC-MULTI-UNREGISTERED-001", "blocked"),
    "unregistered-git": ("SPEC-MULTI-UNREGISTERED-001", "blocked"),
}


def operation(identifier):
    return CASES[identifier]["op"]


# --- 入力 -------------------------------------------------------------------------------

def tools_config():
    return multi_reference.plain_config("x")


def web_requirement():
    return requirement("REQ-010", "認証の基準", "REQ-010:AC-01")


def root_requirement():
    return requirement("REQ-001", "認証の基準", "REQ-001:AC-01")


def base_files():
    return {
        multi_reference.ROOT_CONFIG_PATH: multi_reference.root_config(MEMBERS),
        multi_reference.WEB_CONFIG_PATH: multi_reference.plain_config("web"),
        multi_reference.API_CONFIG_PATH: multi_reference.plain_config("api"),
    }


def reviewed_inputs(identifier):
    """`repo/`の全入力と`changes/`の全入力。(repo, changes)のパス→バイト列の辞書を返す。"""
    kind = CASES[identifier]["inputs"]
    repo, changes = base_files(), {}
    if kind == "tools":
        repo[TOOLS_CONFIG_PATH] = tools_config()
    elif kind == "tools-context":
        repo[TOOLS_CONFIG_PATH] = tools_config()
        repo[WEB_REQ_PATH] = web_requirement()
    elif kind in {"no-api-config", "unrelated-tools"}:
        # `MULTI-034-05`と同じ入力。`web`のTECH-010が通るテスト対応を持ち、メンバー`api`の仕様文書もある。
        repo = {name: data.decode() for name, data in active.reviewed_inputs("MULTI-034-05").items()}
        if kind == "no-api-config":
            # メンバー`api`のディレクトリ（`services/api`）は実在するが、設定と仕様文書を持たない。
            del repo[multi_reference.API_CONFIG_PATH]
            del repo[active.API_TECH_PATH]
        else:
            repo[TOOLS_CONFIG_PATH] = tools_config()
    elif kind == "docs":
        repo["docs/notes.md"] = "# 覚え書き\n\n仕様文書ではない。\n"
    elif kind == "git-absent-member":
        repo[ROOT_REQ_PATH] = root_requirement()
        repo[WEB_REQ_PATH] = web_requirement()
    elif kind == "ears-major":
        repo[multi_reference.ROOT_CONFIG_PATH] = repo[multi_reference.ROOT_CONFIG_PATH].replace('earsAi: "1.0"', 'earsAi: "2.0"')
        repo[ROOT_REQ_PATH] = root_requirement()
    elif kind == "anchor":
        repo[multi_reference.ROOT_CONFIG_PATH] = repo[multi_reference.ROOT_CONFIG_PATH].replace("language: ja\n", "language: &label ja\n")
    elif kind == "ignored":
        repo[".gitignore"] = "tools/x/.spec/\n"
        changes["changes/x-bitz.yaml"] = tools_config()
    elif kind != "root":
        raise ValueError(f"未知の入力の種類です: {kind}")
    return ({name: (data if isinstance(data, bytes) else data.encode()) for name, data in repo.items()},
            {name: data.encode() for name, data in changes.items()})


def reviewed_manifest(identifier):
    case = CASES[identifier]
    setup_plan = {"git": case["git"], "operations": case["operations"]}
    if case["git"]:
        setup_plan["baseCommit"] = {"message": "base", "paths": ["."]}
    return {
        "fixtureId": identifier,
        "description": case["description"],
        "setup": setup_plan,
        "invocation": {"runner": "bitz", "cwd": case["cwd"], "argv": [*case["argv"], "--format", "json"],
                       "env": dict(GIT_ABSENT_ENV) if not case["git"] else {}},
        "expect": {"status": case["status"], "exitCode": case["exit"], "stdout": "json",
                   "resultFile": RESULT_FILES[case["op"]], "reportFileCount": 0},
    }


# --- レビュー済みの期待結果 -----------------------------------------------------------------

def file_source(path, workspace_id=None, key=None):
    source = {"kind": "file", "workspaceId": workspace_id, "path": path}
    if key is not None:
        source["key"] = key
    return source


def diagnostic(code, status, summary, source):
    return {"code": code, "severity": "error", "resultStatus": status, "summary": summary, "source": source}


def unregistered(summary, path):
    return diagnostic("SPEC-MULTI-UNREGISTERED-001", "blocked", summary, file_source(path))


def no_git():
    return diagnostic("SPEC-MULTI-GIT-001", "blocked", NO_GIT, {"kind": "environment", "component": "git"})


def diagnostics_of(identifier):
    return {
        "MULTI-036-01": [unregistered(UNREGISTERED_SELECTED, TOOLS_CONFIG_PATH)],
        "MULTI-036-02": [unregistered(UNREGISTERED_SELECTED, TOOLS_CONFIG_PATH)],
        "MULTI-036-03": [diagnostic("SPEC-MULTI-MEMBER-001", "failed", MEMBER_MISSING,
                                    file_source(".spec/bitz.yaml", "platform", "multiWorkspace.members"))],
        "MULTI-036-04": [no_git()],
        "MULTI-036-05": [no_git()],
        "MULTI-036-06": [{"code": "SPEC-GIT-DEGRADED-001", "severity": "warning", "resultStatus": "passed_with_warnings",
                          "summary": GIT_DEGRADED, "source": {"kind": "environment", "component": "git", "identifier": "git"}}],
        "MULTI-036-07": [diagnostic("SPEC-EARS-VERSION-001", "blocked", EARS_VERSION,
                                    file_source(".spec/bitz.yaml", "platform", "earsAi"))],
        "MULTI-036-08": [diagnostic("SPEC-CONFIG-SCHEMA-001", "error", ANCHOR, file_source(".spec/bitz.yaml", None, "language"))],
        "MULTI-036-09": [diagnostic("SPEC-MULTI-MEMBER-001", "failed", MEMBER_MISSING,
                                    file_source(".spec/bitz.yaml", "platform", "multiWorkspace.members"))],
        "MULTI-036-10": [unregistered(UNREGISTERED_GIT, TOOLS_CONFIG_PATH)],
        "MULTI-036-11": [no_git()],
        "MULTI-036-13": [unregistered(UNREGISTERED_SELECTED, TOOLS_CONFIG_PATH)],
    }[identifier]


WORKSPACES = {
    "MULTI-036-01": {"id": None, "path": "tools/x"}, "MULTI-036-02": {"id": None, "path": "tools/x"},
    "MULTI-036-03": {"id": "web", "path": "apps/web"}, "MULTI-036-04": {"id": "platform", "path": "."},
    "MULTI-036-05": {"id": "platform", "path": "."}, "MULTI-036-06": {"id": "web", "path": "."},
    "MULTI-036-07": {"id": "platform", "path": "."}, "MULTI-036-08": {"id": None, "path": "."},
    "MULTI-036-09": {"id": "web", "path": "apps/web"}, "MULTI-036-10": {"id": "platform", "path": "."},
    "MULTI-036-11": {"id": "platform", "path": "."}, "MULTI-036-12": {"id": "web", "path": "apps/web"},
    "MULTI-036-13": {"id": None, "path": "tools/x"},
}


def empty_coverage():
    empty = {"total": [], "addressed": [], "tested": [], "unaddressed": [], "untested": []}
    return {"must": dict(empty), "should": dict(empty), "may": dict(empty), "adjacent": []}


def reviewed_check_result(identifier):
    """`check`。Git不在とコミットのないリポジトリは`scope: full`、`revision: null`。引数なしでGitがあれば`scope: changed`で、処理を始める前の停止なので件数は0。"""
    case = CASES[identifier]
    revision = {"base": COMMIT, "commit": COMMIT, "dirty": False} if case["git"] else None
    result = {
        "schemaVersion": "1.0", "operation": "check", "status": case["status"],
        "scope": "full" if "--full" in case["argv"] or not case["git"] else "changed",
        "workspace": dict(WORKSPACES[identifier]), "revision": revision, "durationMs": 0,
        "diagnostics": diagnostics_of(identifier),
    }
    if result["scope"] == "changed":
        result["selection"] = {"changedPathCount": 0, "targetDocumentCount": 0, "excludedCodeTestPathCount": 0}
    else:
        result["checkedDocumentCount"] = 1 if identifier == "MULTI-036-06" else 0
        result["checkedStatementCount"] = 1 if identifier == "MULTI-036-06" else 0
    return result


def reviewed_context_result(identifier):
    """`context`の停止結果。到達ワークスペースを確定しないので、複合固有のフィールド（`resolution.workspaces`、`crossWorkspaceEdges`）を持たない。"""
    return {
        "schemaVersion": "1.0", "operation": "context", "status": CASES[identifier]["status"], "purpose": "interpret",
        "workspace": dict(WORKSPACES[identifier]),
        "roots": [CASES[identifier]["argv"][1]],
        "contextDigest": None, "revision": {"commit": COMMIT, "dirty": False},
        "resolution": {"complete": False, "documentCount": 0, "unresolvedStrongRelations": 0},
        "projection": {"detail": "standard", "expanded": []},
        "documents": [], "constraintLedger": {"statements": []}, "coverage": empty_coverage(),
        "durationMs": 0, "diagnostics": diagnostics_of(identifier),
    }


def reviewed_verify_result(identifier):
    if identifier == "MULTI-036-12":
        # 止まらないので、`MULTI-034-05`と同じ通常の結果。
        return active.reviewed_verify_result("MULTI-034-05")
    return {
        "schemaVersion": "1.0", "operation": "verify", "status": CASES[identifier]["status"], "scope": "all",
        "workspace": dict(WORKSPACES[identifier]), "targetResults": [],
        "revision": {"commit": COMMIT, "dirty": False}, "commands": [], "durationMs": 0,
        "diagnostics": diagnostics_of(identifier),
    }


def reviewed_doctor_result(identifier):
    """`doctor`の停止結果。ワークスペース固有の検査項目を置かず、`--all-workspaces`の停止結果と同じ最上位の検査項目を置く。"""
    cause = CASES[identifier]["cause"]
    checks = ([{"name": "core", "status": "passed"}, {"name": "git", "status": "blocked"}] if cause == "git"
              else [{"name": "core", "status": "passed"}, {"name": "git", "status": "passed"}, {"name": "catalog", "status": "blocked"}])
    return {
        "schemaVersion": "1.0", "operation": "doctor", "status": CASES[identifier]["status"],
        "workspace": dict(WORKSPACES[identifier]), "core": dict(CORE), "checks": checks, "durationMs": 0,
        "diagnostics": diagnostics_of(identifier),
    }


def reviewed_result(identifier):
    return {"check": reviewed_check_result, "context": reviewed_context_result, "verify": reviewed_verify_result,
            "doctor": reviewed_doctor_result}[operation(identifier)](identifier)


# --- 参照計算 --------------------------------------------------------------------------------

def forbidden_yaml(text):
    """禁止されたYAML（アンカー、エイリアス、タグ）。この参照計算は、fixtureの入力が使う限られた形だけを扱う。"""
    for line in text.splitlines():
        code = line.split("#", 1)[0]
        if any(token[:1] in {"&", "*", "!"} for token in code.split()):
            return True
    return False


def load_config(repository, directory):
    path = repository / directory / ".spec/bitz.yaml"
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    return None if forbidden_yaml(text) else read_yaml(text)


def nearest_directory(repository, cwd):
    """複合ワークスペース仕様 §3の手順2: 現在のディレクトリからリポジトリのルートへ親の方向に探索して、最も近い設定のディレクトリを返す。"""
    current = Path(cwd)
    while True:
        if (repository / current / ".spec/bitz.yaml").is_file():
            return current.as_posix()
        if current.as_posix() == ".":
            return None
        current = current.parent


def major(value):
    return int(str(value).split(".")[0])


def recognized_configs(repository):
    """Gitが認識する`.spec/bitz.yaml`。`HEAD`のスナップショットと、現在のスナップショット（作業ツリーに存在する追跡対象とステージ済みのパスと、無視されない未追跡のパス）。"""
    def configs(names):
        return {name for name in names if name == ".spec/bitz.yaml" or name.endswith("/.spec/bitz.yaml")}

    head = configs(git(repository, "-c", "core.quotePath=false", "ls-tree", "-r", "-z", "--name-only", "HEAD").decode().split("\0"))
    listed = git(repository, "-c", "core.quotePath=false", "ls-files", "-z", "--cached", "--others", "--exclude-standard").decode().split("\0")
    current = configs(name for name in listed if name and (repository / name).exists())
    return head, current


def snapshot_catalog_paths(text):
    """スナップショット自身のルートの設定が`multiWorkspace`を宣言する場合のカタログの設定の集合。宣言しなければ`None`（比較しない）。"""
    if text is None or forbidden_yaml(text):
        return None
    config = read_yaml(text)
    if "multiWorkspace" not in config:
        return None
    return {".spec/bitz.yaml"} | {f"{member['path']}/.spec/bitz.yaml" for member in config["multiWorkspace"]["members"]}


def git_unregistered(repository):
    head, current = recognized_configs(repository)
    head_text = git(repository, "show", "HEAD:.spec/bitz.yaml").decode() if ".spec/bitz.yaml" in head else None
    current_text = (repository / ".spec/bitz.yaml").read_text(encoding="utf-8") if (repository / ".spec/bitz.yaml").is_file() else None
    found = set()
    for names, text in ((head, head_text), (current, current_text)):
        catalog = snapshot_catalog_paths(text)
        if catalog is not None:
            found |= names - catalog
    return sorted(found)


def reference_decision(repository, op, cwd, git_present):
    """参照計算: 入力の木構造とGitの状態から、複合かどうか、全体事前検査の停止の原因、停止結果の`workspace`を導く（複合ワークスペース仕様 §3・§7・§8・§10、ADR-063）。

    返す辞書は`mode`（`single`または`multi`）、`cause`（`CAUSE_DIAGNOSTIC`のキー、止まらなければ`None`）、`workspace`、`unregistered`（未登録の設定のパスの一覧）、
    `config`（単一ワークスペースの設定を読めるか）を持つ。
    """
    nearest = nearest_directory(repository, cwd)
    if nearest is None:
        raise ValueError("最も近い設定がありません")
    near_config = load_config(repository, nearest)
    if not git_present:
        # リポジトリのルートを確定できない。最も近い設定が`multiWorkspace`を宣言していれば複合で、そうでなければ単一ワークスペースの縮退。
        # 複合を宣言する設定はルートワークスペースなので、パスは`.`である。
        if near_config is not None and "multiWorkspace" in near_config:
            return {"mode": "multi", "cause": "git", "workspace": {"id": near_config["workspace"]["id"], "path": "."},
                    "unregistered": [], "config": True}
        return single_decision(near_config)
    root_config = load_config(repository, ".")
    if root_config is None or "multiWorkspace" not in root_config:
        return single_decision(root_config if nearest == "." else near_config)
    members = {member["path"]: member["id"] for member in root_config["multiWorkspace"]["members"]}
    registered = {".": root_config["workspace"]["id"], **members}
    if nearest in registered and near_config is not None and near_config["workspace"]["id"] == registered[nearest]:
        workspace = {"id": registered[nearest], "path": nearest}
    else:
        workspace = {"id": None, "path": nearest}
    selected = [] if nearest in registered else [f"{nearest}/.spec/bitz.yaml"]
    # 原因の優先は、未対応のメジャーバージョン、メンバーの設定、未登録（診断レジストリの優先順位と同じ並び）である。
    if major(root_config["schemaVersion"]) != SUPPORTED_MAJOR or major(root_config["earsAi"]) != SUPPORTED_MAJOR:
        cause, listed = "version", []
    elif any(not (repository / path / ".spec/bitz.yaml").is_file() for path in members):
        cause, listed = "member", []
    elif op == "doctor" and git_unregistered(repository):
        # 単独の`doctor`は、Gitが認識する設定の比較を行う。選択した設定の照合と同じ設定が重なる場合は、この群の範囲外とする。
        listed = git_unregistered(repository)
        if selected:
            raise ValueError("Gitが認識する設定の比較と選択した設定の照合が重なる場合は、この群の範囲外です")
        cause = "unregistered-git"
    elif selected:
        cause, listed = "unregistered-selected", selected
    else:
        cause, listed = None, []
    return {"mode": "multi", "cause": cause, "workspace": workspace, "unregistered": listed or selected, "config": True}


def single_decision(config):
    """単一ワークスペース。設定を読めなければ`workspace.id`は`null`、読めれば設定した`workspace.id`、なければ`root`。"""
    if config is None:
        return {"mode": "single", "cause": None, "workspace": {"id": None, "path": "."}, "unregistered": [], "config": False}
    return {"mode": "single", "cause": None, "workspace": {"id": config.get("workspace", {}).get("id", "root"), "path": "."},
            "unregistered": [], "config": True}


def check_against_reference(identifier, result, reference):
    """リテラルの期待値が、参照計算と一致することを要求する。"""
    case = CASES[identifier]
    if reference["cause"] != case["cause"]:
        raise ValueError("停止の原因が入力からの参照計算と異なります")
    if result["workspace"] != reference["workspace"]:
        raise ValueError("`workspace`が入力からの参照計算と異なります")
    codes = [(item["code"], item["resultStatus"]) for item in result["diagnostics"]]
    if reference["cause"] is not None:
        if codes != [CAUSE_DIAGNOSTIC[reference["cause"]]] or result["status"] != CAUSE_DIAGNOSTIC[reference["cause"]][1]:
            raise ValueError("診断または状態が停止の原因と異なります")
        if reference["cause"].startswith("unregistered"):
            summary = UNREGISTERED_GIT if reference["cause"] == "unregistered-git" else UNREGISTERED_SELECTED
            source = result["diagnostics"][0]["source"]
            if (result["diagnostics"][0]["summary"] != summary or source["workspaceId"] is not None
                    or [source["path"]] != reference["unregistered"]):
                raise ValueError("未登録の診断の文言、発生元が入力からの参照計算と異なります")
        # 停止した結果の`revision`は、Gitの境界を確定できずに停止した場合（`SPEC-MULTI-GIT-001`）だけ`null`である。`doctor`は`revision`を持たない。
        if case["op"] != "doctor" and (result["revision"] is None) != (reference["cause"] == "git"):
            raise ValueError("`revision`の有無が停止の原因と異なります")
        if case["op"] == "doctor":
            expected = ["core", "git"] if reference["cause"] == "git" else ["core", "git", "catalog"]
            if [item["name"] for item in result["checks"]] != expected or "revision" in result or "workspaces" in result:
                raise ValueError("`doctor`の検査項目が全体事前検査の停止結果と異なります")
        if case["op"] == "context" and (result["contextDigest"] is not None or result["resolution"]["complete"]
                                        or "workspaces" in result["resolution"] or "crossWorkspaceEdges" in result["resolution"]):
            raise ValueError("`context`の停止結果が複合固有のフィールドを持っています")
        if case["op"] == "verify" and (result["targetResults"] or result["commands"]):
            raise ValueError("停止した`verify`は検証対象もコマンドも持ちません")
    elif reference["mode"] == "single":
        # 単一ワークスペース: 複合として停止しない。
        if any(item["code"].startswith("SPEC-MULTI-") for item in result["diagnostics"]):
            raise ValueError("単一ワークスペースが複合ワークスペースの診断を返しています")
    else:
        if result["diagnostics"] or result["status"] != "passed":
            raise ValueError("止まらない単独の`verify`は診断を持たず通ります")


def git_dirty(repository):
    return bool(git(repository, "status", "--porcelain=v1", "--untracked-files=all").strip())


def check_conditions(identifier, repository):
    """原因の構成を、散文ではなく準備手順の後の入力とGitの状態から確かめる。"""
    case = CASES[identifier]
    has_git = (repository / ".git").exists()
    if has_git != case["git"]:
        raise ValueError("Gitの有無が期待と異なります")
    reference = reference_decision(repository, case["op"], case["cwd"], case["git"])
    # 各fixtureの原因を、入力から1つずつ確かめる。
    if case["cause"] == "unregistered-selected":
        if TOOLS_CONFIG_PATH.removesuffix("/.spec/bitz.yaml") in {path for _, path in MEMBERS}:
            raise ValueError("未登録の設定がカタログに入っています")
        if reference["workspace"] != {"id": None, "path": "tools/x"}:
            raise ValueError("最も近い設定が未登録の`tools/x`である必要があります")
        tracked = bool(git(repository, "ls-files", "--", TOOLS_CONFIG_PATH).strip())
        if identifier == "MULTI-036-13":
            # 無視された未追跡の設定: Gitが認識する設定の比較には現れず、選択した設定の照合だけが拾う。
            try:
                git(repository, "check-ignore", "-q", "--", TOOLS_CONFIG_PATH)
            except subprocess.CalledProcessError:
                raise ValueError("`MULTI-036-13`の設定は、`.gitignore`で無視されている必要があります") from None
            if tracked or git_unregistered(repository):
                raise ValueError("`MULTI-036-13`の設定は、Gitが認識しない未追跡のファイルである必要があります")
        elif not tracked:
            raise ValueError("未登録の設定はGitで追跡されている必要があります")
    if case["cause"] == "unregistered-git":
        head, current = recognized_configs(repository)
        if TOOLS_CONFIG_PATH not in head or TOOLS_CONFIG_PATH in current or (repository / TOOLS_CONFIG_PATH).exists():
            raise ValueError("`HEAD`にだけ未登録の設定がある必要があります")
        if reference["workspace"] != {"id": "platform", "path": "."}:
            raise ValueError("ルートで実行する必要があります")
    if case["cause"] == "member":
        if (repository / multi_reference.API_CONFIG_PATH).exists() or not (repository / "services/api").is_dir():
            raise ValueError("メンバー`api`のディレクトリは実在し、設定は存在しない必要があります")
        if not (repository / multi_reference.WEB_CONFIG_PATH).is_file():
            raise ValueError("実行ディレクトリのメンバー`web`は正しい設定を持つ必要があります")
    if case["cause"] == "version":
        root_config = load_config(repository, ".")
        if major(root_config["earsAi"]) == SUPPORTED_MAJOR or "multiWorkspace" not in root_config:
            raise ValueError("ルートの`earsAi`が非対応で、`multiWorkspace`を宣言している必要があります")
    if case["cause"] == "git" and has_git:
        raise ValueError("Git不在のケースにGitのメタデータがあります")
    if identifier == "MULTI-036-05" and (repository / "docs/.spec").exists():
        raise ValueError("`docs`は設定を持ってはいけません")
    if identifier == "MULTI-036-06":
        near = load_config(repository, "apps/web")
        if "multiWorkspace" in near or reference["mode"] != "single":
            raise ValueError("最も近い設定が`multiWorkspace`を宣言してはいけません")
        if "multiWorkspace" not in load_config(repository, "."):
            raise ValueError("ルートの設定は複合を宣言する必要があります（最も近い設定だけで判定することの対照）")
    if identifier == "MULTI-036-08":
        text = (repository / multi_reference.ROOT_CONFIG_PATH).read_text()
        if not forbidden_yaml(text) or "multiWorkspace:" not in text or reference["mode"] != "single":
            raise ValueError("ルートの設定は、`multiWorkspace`を含むが読めない設定である必要があります")
        if forbidden_yaml(multi_reference.root_config(MEMBERS)):
            raise ValueError("正しいルートの設定は禁止されたYAMLを含んではいけません")
    if identifier == "MULTI-036-09":
        option = case["argv"][case["argv"].index("--workspace") + 1]
        if option in {"platform", "web", "api"}:
            raise ValueError("`--workspace`はカタログにないIDを渡す必要があります")
    if identifier == "MULTI-036-12":
        if git_unregistered(repository) != [TOOLS_CONFIG_PATH] or reference["cause"] is not None:
            raise ValueError("`tools/x`の未登録は、Gitが認識する設定の比較では拾われるが、単独の`verify`は止まらない構成である必要があります")
        if reference["workspace"] != {"id": "web", "path": "apps/web"}:
            raise ValueError("`apps/web`で実行する必要があります")
    if has_git and identifier in {"MULTI-036-01", "MULTI-036-02", "MULTI-036-03", "MULTI-036-07", "MULTI-036-08", "MULTI-036-09"}:
        if git_dirty(repository):
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
                path = fixture / prefix / (name.removeprefix("changes/") if prefix == "changes" else name)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
        (fixture / "expected").mkdir(parents=True, exist_ok=True)
        manifest = reviewed_manifest(identifier)
        (fixture / "manifest.json").write_text(_dump(manifest))
        (fixture / RESULT_FILES[operation(identifier)]).write_text(_dump(reviewed_result(identifier)))
        with tempfile.TemporaryDirectory(prefix="bitz-multi-single-precheck-") as temporary:
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
            repo, changes = reviewed_inputs(identifier)
            entries = {}
            for directory in ("repo", "changes"):
                for path in (fixture / directory).rglob("*"):
                    if path.is_symlink() or path.is_file():
                        entries[(directory, path.relative_to(fixture / directory).as_posix())] = (
                            None if path.is_symlink() else path.read_bytes())
            expected_entries = {("repo", name): data for name, data in repo.items()}
            expected_entries.update({("changes", name.removeprefix("changes/")): data for name, data in changes.items()})
            if entries != expected_entries:
                raise ValueError("入力がレビュー済みのcorpusと異なります")
            if effects["policy"] != "read-only" or effects["before"] != effects["after"]:
                raise ValueError("読取り専用の期待値が書込みを許しています")
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-multi-single-precheck-") as temporary:
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
                    if identifier == "MULTI-036-12":
                        # 通常の結果: 作業ワークスペースの`verify`の参照計算とハッシュ値の照合は、`MULTI-034-05`の群の参照計算を使う。
                        verify_reference = active.reference_verify(repository, "apps/web", None, [])
                        active.check_verify_against_reference(result, verify_reference)
                        active.check_digests(repository, result)
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
