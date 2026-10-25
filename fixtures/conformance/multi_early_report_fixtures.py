"""`--all-workspaces`の早期の結果が`--report`をルートワークスペースへ保存することを固定する（Coreの公開操作は実行しない）。

実装の確認事項C53とADR-051の追加に対応する。結果・診断・終了コード §8は、`check`と`verify`が「状態にかかわらず」、`--report`を指定された場合だけ結果のJSONを
`.spec/reports/`へ保存し、全体レポートはルートワークスペースの`.spec/reports/`へ保存すると定める。保存の失敗は`SPEC-REPORT-WRITE-001`
（重大度`error`、結果への効果`error`）で、元の結果と診断は端末に保持する。
修正前のCoreは、`check --all-workspaces`と`verify --all-workspaces`が全体事前検査で止まった結果（と、`verify`の実行計画の上限超過の結果）を、
`--report`を指定しても保存しなかった。この群は、全体事前検査の停止を、保存の成功・保存の失敗・`--report`なしの対照で10件固定する。

| fixture | 操作と実行ディレクトリ | 原因と期待 |
|---|---|---|
| `MULTI-045-01` | `check --all-workspaces --base HEAD --report`、`.` | メンバー`api`の設定がない（`SPEC-MULTI-MEMBER-001`）。`failed`／1。ルートの`.spec/reports/`に1件 |
| `MULTI-045-02` | `verify --all-workspaces --report`、`.` | 同じ入力。`failed`／1。ルートに1件 |
| `MULTI-045-03` | `check --all-workspaces --base HEAD --report`、`.` | 同じ入力で`.spec/reports`が通常ファイル。`SPEC-REPORT-WRITE-001`が§7の順に入る。`error`／3。レポートは0件 |
| `MULTI-045-04` | `verify --all-workspaces --report`、`.` | `03`の`verify`。`error`／3 |
| `MULTI-045-05` | `check --all-workspaces --base HEAD --report`、`.` | ルートが`workspace.id`を省略（`SPEC-MULTI-CONFIG-001`、`multiWorkspace.id`は`null`）。`failed`／1。ルートに1件 |
| `MULTI-045-06` | `verify --all-workspaces --report`、`.` | `05`の`verify`。ルートに1件 |
| `MULTI-045-07` | `check --all-workspaces --base HEAD --report`、`.` | `05`の入力で`.spec/reports`が通常ファイル。`SPEC-REPORT-WRITE-001`の`source.workspaceId`は`null`。`error`／3 |
| `MULTI-045-08` | `verify --all-workspaces --report`、`.` | `07`の`verify`。`error`／3 |
| `MULTI-045-09` | `check --all-workspaces --base HEAD`、`.` | 対照: `01`と同じ入力で`--report`なし。結果は`01`と同じで、ファイルを作らず既存のレポートを変えない |
| `MULTI-045-10` | `verify --all-workspaces`、`.` | 対照: `02`と同じ入力で`--report`なし |

入力は2種類である。どちらも、ルート（`.`）、メンバー`web`（`apps/web`）と`api`（`services/api`）を宣言し、ルートのREQ-001を置く。

| 種類 | 内容 |
|---|---|
| `member-absent` | ルートは`workspace.id: platform`を明示する。`web`は設定を持つ。`api`は`.spec/bitz.yaml`を持たない（`services/api`のディレクトリは`src/session.py`で残す） |
| `root-omitted` | `MULTI-043-01`と同じ入力。ルートの設定が`workspace`を持たない |

レポートのディレクトリの状態は、書き込める場合はコミット済みの既存のレポート`.spec/reports/existing.json`を持つディレクトリ、書き込めない場合は
`.spec/reports`の位置に置いた通常ファイルである（`SINGLE-072`と同じ。ディレクトリの権限はバージョン管理できない）。

期待値の根拠は規範文と、このモジュールの参照計算だけである（Coreの出力は根拠にしない）。

- 結果・診断・終了コード §8: `check`と`verify`は、状態にかかわらず、`--report`が指定された場合だけ結果のJSONを保存する。`--report`がなければ新しいファイルも作らず、
  既存のレポートを変えない。全体レポートはルートワークスペースの`.spec/reports/`へ保存する（メンバーの`.spec/reports/`へは保存しない）。
  ファイル名は`<YYYYMMDDTHHMMSSZ>-<operation>[-<sequence>].json`。保存の失敗は`SPEC-REPORT-WRITE-001`（`error`、結果への効果`error`）で、元の結果と診断は端末に保持する。
  レポートは結果のJSONそのものである（保存しても結果は変わらない）。
- 同 §3: 状態の最悪値の集約（`error > failed > blocked`）と終了コード。`SPEC-MULTI-MEMBER-001`・`SPEC-MULTI-CONFIG-001`は`failed`なので、保存の失敗が加わると`error`／3になる。
- 同 §5: ルートの`workspace.id`の省略でルートの同一性を構成できない診断の`source.workspaceId`は`null`。保存の失敗の診断の`source`は、ルートワークスペースの
  `{file, <ルートのID>, .spec/reports}`である（同一性を構成できないときは`workspaceId`が`null`）。
- 同 §7: 診断の並びは、発生元のワークスペースID（`null`が先）、`path`、`line`、`column`、`code`、`specRefs`の辞書順。保存の失敗を末尾に足さず、この順に入れる（確認事項C51）。
  この群の入力では、`.spec/bitz.yaml`が`.spec/reports`より辞書順で前なので、停止の診断が先になる。
- 診断レジストリ: `MULTI-MEMBER`（`SPEC-MULTI-MEMBER-001`、`error`／`failed`）、`MULTI-CONFIG`（`SPEC-MULTI-CONFIG-001`、`error`／`failed`）、`REPORT-WRITE`（`SPEC-REPORT-WRITE-001`、`error`／`error`）。
  `summary`は、承認済みの文言（`Coreの出力文言のレビュー記録.md`）。
- 複合ワークスペース仕様 §9: `--report`なしの全体操作は、状態にかかわらずファイルを作らない。全体事前検査でルートの同一性を構成できない場合だけ`multiWorkspace`を`{id: null, path: .}`とする。

`verify`の実行計画の上限超過（`SPEC-MULTI-LIMIT-001`）は、この群の範囲外とする。既存の上限のfixture（`MULTI-021-08`、`MULTI-041`）は、バージョン管理できない大きさの入力を
生成し、`stateDigest`で固定するため、harnessが`--report`との組合せ（`explicit-report`と`stateDigest`）に対応していない。単体試験が固定する。
"""
import json
from pathlib import Path
import re
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from .harness import git, setup
from .initial_fixtures import compare_state
from .multi_catalog_fixtures import observe_state
from .schemas import schema_path
from . import multi_reference, multi_report_fixtures, multi_workspace_id_fixtures as workspace_id, report_write_fixtures

HERE = Path(__file__).resolve().parent
COMMIT = "0" * 40
REPORT_DIRECTORY = multi_report_fixtures.REPORT_DIRECTORY
EXISTING_REPORT = multi_report_fixtures.EXISTING_REPORT
NAME_PATTERN = multi_report_fixtures.NAME_PATTERN
BLOCKING_FILE = report_write_fixtures.BLOCKING_FILE
ROOT_CONFIG_PATH = multi_reference.ROOT_CONFIG_PATH
WEB_CONFIG_PATH = multi_reference.WEB_CONFIG_PATH
API_CONFIG_PATH = multi_reference.API_CONFIG_PATH
API_SOURCE_PATH = workspace_id.API_SOURCE_PATH
MEMBERS = workspace_id.MEMBERS

# 承認済みの診断の文言。`Coreの出力文言のレビュー記録.md`。
MEMBER_MISSING = "メンバーの.spec/bitz.yamlがありません"
ROOT_ID_REQUIRED = workspace_id.ROOT_ID_REQUIRED
REPORT_WRITE = "レポートの保存先へ排他的に作成できません"

# 結果・診断・終了コード §3の最悪値の集約の順（弱い方から強い方）と、状態と終了コードの対応。
SEVERITY_ORDER = ["passed", "passed_with_warnings", "blocked", "failed", "error"]
EXIT_CODES = {"passed": 0, "passed_with_warnings": 0, "failed": 1, "blocked": 2, "error": 3}

# id: dict(op, inputs, report, reports, status, exit, cause, description)
# report: `--report`の有無。reports: `directory`（書き込める）または`file`（`.spec/reports`を通常ファイルにして保存を失敗させる）。
# cause: 全体事前検査の停止の原因（`member-missing`、`root-id`）。
CASES = {
    "MULTI-045-01": dict(op="check", inputs="member-absent", report=True, reports="directory", status="failed", exit=1, cause="member-missing",
                         description="全体事前検査で止まったcheck --all-workspacesも、--reportをルートワークスペースへ保存する"),
    "MULTI-045-02": dict(op="verify", inputs="member-absent", report=True, reports="directory", status="failed", exit=1, cause="member-missing",
                         description="全体事前検査で止まったverify --all-workspacesも、--reportをルートワークスペースへ保存する"),
    "MULTI-045-03": dict(op="check", inputs="member-absent", report=True, reports="file", status="error", exit=3, cause="member-missing",
                         description="全体事前検査で止まったcheck --all-workspacesのレポートの保存の失敗を、診断の並びに入れて返す"),
    "MULTI-045-04": dict(op="verify", inputs="member-absent", report=True, reports="file", status="error", exit=3, cause="member-missing",
                         description="全体事前検査で止まったverify --all-workspacesのレポートの保存の失敗を、診断の並びに入れて返す"),
    "MULTI-045-05": dict(op="check", inputs="root-omitted", report=True, reports="directory", status="failed", exit=1, cause="root-id",
                         description="ルートの同一性を構成できずに止まったcheck --all-workspacesも、--reportをルートへ保存する"),
    "MULTI-045-06": dict(op="verify", inputs="root-omitted", report=True, reports="directory", status="failed", exit=1, cause="root-id",
                         description="ルートの同一性を構成できずに止まったverify --all-workspacesも、--reportをルートへ保存する"),
    "MULTI-045-07": dict(op="check", inputs="root-omitted", report=True, reports="file", status="error", exit=3, cause="root-id",
                         description="ルートの同一性を構成できないときのレポートの保存の失敗の診断は、workspaceIdをnullにする"),
    "MULTI-045-08": dict(op="verify", inputs="root-omitted", report=True, reports="file", status="error", exit=3, cause="root-id",
                         description="ルートの同一性を構成できないverify --all-workspacesのレポートの保存の失敗の診断も、workspaceIdをnullにする"),
    "MULTI-045-09": dict(op="check", inputs="member-absent", report=False, reports="directory", status="failed", exit=1, cause="member-missing",
                         description="対照: --reportなしの全体事前検査で止まったcheck --all-workspacesはファイルを作らない"),
    "MULTI-045-10": dict(op="verify", inputs="member-absent", report=False, reports="directory", status="failed", exit=1, cause="member-missing",
                         description="対照: --reportなしの全体事前検査で止まったverify --all-workspacesはファイルを作らない"),
}
RESULT_FILES = {"check": "expected/check.json", "verify": "expected/verify.json"}


def saved_count(identifier):
    """マニフェストの`reportFileCount`: `--report`があり、保存先が書き込めるときだけ1件。"""
    case = CASES[identifier]
    return 1 if case["report"] and case["reports"] == "directory" else 0


# --- 入力 -------------------------------------------------------------------------------

def member_absent_files():
    """ルート`platform`（`.`）、`web`（`apps/web`）、`api`（`services/api`）。`api`は設定を持たず、ディレクトリだけが実在する。"""
    files = {
        ROOT_CONFIG_PATH: multi_reference.root_config(MEMBERS, root_id="platform"),
        multi_reference.ROOT_REQ_PATH: workspace_id.root_requirement(),
        WEB_CONFIG_PATH: multi_reference.plain_config("web"),
        API_SOURCE_PATH: multi_reference.CODE_FILES[API_SOURCE_PATH],
    }
    return {name: data.encode() if isinstance(data, str) else data for name, data in files.items()}


def reviewed_inputs(identifier):
    """`repo/`の全入力。パス→バイト列。"""
    case = CASES[identifier]
    files = member_absent_files() if case["inputs"] == "member-absent" else dict(workspace_id.reviewed_inputs("MULTI-043-01"))
    if case["reports"] == "directory":
        files[EXISTING_REPORT] = b"{}\n"
    else:
        # 通常ファイルがパスを占めるので、レポートのディレクトリは存在できない（`SINGLE-072`と同じ）。
        files[REPORT_DIRECTORY] = BLOCKING_FILE
    return files


def reviewed_manifest(identifier):
    case = CASES[identifier]
    argv = [case["op"], "--all-workspaces"]
    if case["op"] == "check":
        argv += ["--base", "HEAD"]
    argv += ["--format", "json"]
    if case["report"]:
        argv.append("--report")
    return {
        "fixtureId": identifier,
        "description": case["description"],
        "setup": {"git": True, "baseCommit": {"message": "base", "paths": ["."]}, "operations": []},
        "invocation": {"runner": "bitz", "cwd": ".", "argv": argv, "env": {}},
        "expect": {"status": case["status"], "exitCode": case["exit"], "stdout": "json",
                   "resultFile": RESULT_FILES[case["op"]], "reportFileCount": saved_count(identifier)},
    }


# --- レビュー済みの期待結果 -----------------------------------------------------------------

def root_workspace_id(identifier):
    """ルートワークスペースのID。ルートが`workspace.id`を省略するときは構成できないので`None`。"""
    return None if CASES[identifier]["cause"] == "root-id" else "platform"


def stop_diagnostic(identifier):
    if CASES[identifier]["cause"] == "root-id":
        return {"code": "SPEC-MULTI-CONFIG-001", "severity": "error", "resultStatus": "failed", "summary": ROOT_ID_REQUIRED,
                "source": {"kind": "file", "workspaceId": None, "path": ".spec/bitz.yaml", "key": "workspace.id"}}
    # 発生元はカタログの宣言（ルートの`multiWorkspace.members`）。`MULTI-036-03`と同じ。
    return {"code": "SPEC-MULTI-MEMBER-001", "severity": "error", "resultStatus": "failed", "summary": MEMBER_MISSING,
            "source": {"kind": "file", "workspaceId": "platform", "path": ".spec/bitz.yaml", "key": "multiWorkspace.members"}}


def write_diagnostic(workspace):
    return {"code": "SPEC-REPORT-WRITE-001", "severity": "error", "resultStatus": "error", "summary": REPORT_WRITE,
            "source": {"kind": "file", "workspaceId": workspace, "path": REPORT_DIRECTORY}}


def section7_key(diagnostic):
    """結果・診断・終了コード §7: 発生元のワークスペースID（`null`が先）、`path`、`line`、`column`、`code`の辞書順。

    この群の診断はすべて、`file`の発生元で、`specRefs`を持たない。`line`と`column`は持たない。
    """
    source = diagnostic["source"]
    workspace = source["workspaceId"]
    return (workspace is not None, workspace or "", source["path"], source.get("line", 0), source.get("column", 0), diagnostic["code"])


def worst_status(diagnostics):
    return max((item["resultStatus"] for item in diagnostics), key=SEVERITY_ORDER.index)


def reviewed_diagnostics(identifier):
    case = CASES[identifier]
    diagnostics = [stop_diagnostic(identifier)]
    if case["report"] and case["reports"] == "file":
        diagnostics.append(write_diagnostic(root_workspace_id(identifier)))
    return sorted(diagnostics, key=section7_key)


def reviewed_result(identifier):
    case = CASES[identifier]
    diagnostics = reviewed_diagnostics(identifier)
    common = {"schemaVersion": "1.0", "operation": case["op"], "scope": "all-workspaces", "status": worst_status(diagnostics),
              "multiWorkspace": {"id": root_workspace_id(identifier), "path": "."}, "workspaces": []}
    if case["op"] == "check":
        revision = {"base": COMMIT, "commit": COMMIT, "dirty": False}
    else:
        revision = {"commit": COMMIT, "dirty": False}
    return {**common, "revision": revision, "durationMs": 0, "diagnostics": diagnostics}


def reviewed_effects(identifier, state):
    effects = {"schemaVersion": "1.0", "policy": "read-only", "before": state, "after": state}
    if saved_count(identifier):
        effects["policy"] = "explicit-report"
        effects["report"] = {"directory": REPORT_DIRECTORY, "createdCount": 1, "namePattern": NAME_PATTERN, "temporaryFilesRemaining": 0}
    return effects


# --- 参照計算 --------------------------------------------------------------------------------

def reference_decision(repository):
    """参照計算: 入力の木構造から、全体事前検査の停止の原因、ルートのID、レポートの保存先の状態を導く。

    ルートの`workspace.id`の省略は、ほかのカタログの不備より先に判定する（複合ワークスペース仕様 §2、ユーザーの決定）。
    メンバーの設定の不在は`SPEC-MULTI-MEMBER-001`の原因である（診断レジストリ）。
    """
    root = workspace_id.load_config(repository, ".")
    if root is None or "multiWorkspace" not in root:
        raise ValueError("複合ワークスペースのルートの設定が必要です")
    root_id = workspace_id.explicit_id(root)
    declaration = root["multiWorkspace"]
    members = [(item["id"], item["path"]) for item in declaration.get("members", [])] if isinstance(declaration, dict) else []
    cause = None
    if root_id is None:
        cause = "root-id"
    else:
        for _, path in members:
            if workspace_id.load_config(repository, path) is None:
                cause = "member-missing"
                break
    reports = repository / REPORT_DIRECTORY
    # 保存できるのは、ルートの`.spec/reports`がディレクトリ（シンボリックリンクでない）ときだけ。
    state = "directory" if reports.is_dir() and not reports.is_symlink() else "file" if reports.is_file() else "absent"
    return {"cause": cause, "rootId": root_id, "reports": state, "members": members}


def reference_outcome(case, decision):
    """参照計算: 起動条件と入力から、診断の並び、状態、終了コード、保存されるレポートの件数を導く。"""
    if decision["cause"] is None:
        raise ValueError("このfixtureは全体事前検査が非成功である必要があります")
    root_id = decision["rootId"]
    if decision["cause"] == "root-id":
        stop = ("SPEC-MULTI-CONFIG-001", "failed", None)
    else:
        stop = ("SPEC-MULTI-MEMBER-001", "failed", root_id)
    pairs = [(stop[0], stop[1], stop[2], ".spec/bitz.yaml")]
    saved = 0
    if case["report"]:
        if decision["reports"] == "directory":
            saved = 1
        else:
            pairs.append(("SPEC-REPORT-WRITE-001", "error", root_id, REPORT_DIRECTORY))
    # §7の並び。ワークスペースIDの`null`が先、次に`path`、`code`。
    pairs.sort(key=lambda pair: (pair[2] is not None, pair[2] or "", pair[3], pair[0]))
    status = max((pair[1] for pair in pairs), key=SEVERITY_ORDER.index)
    return {"codes": [pair[0] for pair in pairs], "workspaces": [pair[2] for pair in pairs], "status": status,
            "exit": EXIT_CODES[status], "saved": saved}


def check_against_reference(identifier, manifest, result, decision):
    """リテラルの期待値が、参照計算と一致することを要求する。"""
    case = CASES[identifier]
    if decision["cause"] != case["cause"]:
        raise ValueError("停止の原因が入力からの参照計算と異なります")
    if decision["reports"] != case["reports"]:
        raise ValueError("レポートの保存先の状態が入力からの参照計算と異なります")
    outcome = reference_outcome(case, decision)
    if [item["code"] for item in result["diagnostics"]] != outcome["codes"]:
        raise ValueError("診断の並びが入力からの参照計算と異なります")
    if [item["source"]["workspaceId"] for item in result["diagnostics"]] != outcome["workspaces"]:
        raise ValueError("診断の発生元のワークスペースIDが入力からの参照計算と異なります")
    if result["status"] != outcome["status"] or manifest["expect"]["status"] != outcome["status"] \
            or manifest["expect"]["exitCode"] != outcome["exit"]:
        raise ValueError("状態または終了コードが入力からの参照計算と異なります")
    if manifest["expect"]["reportFileCount"] != outcome["saved"]:
        raise ValueError("レポートの件数が入力からの参照計算と異なります")
    # 有効なルートのIDを構成できないときだけ`multiWorkspace.id`は`null`。`workspaces`は空配列（停止の結果はメンバーの処理を始めない）。
    if result["multiWorkspace"] != {"id": decision["rootId"], "path": "."} or result["workspaces"] != []:
        raise ValueError("`multiWorkspace`または`workspaces`が入力からの参照計算と異なります")
    if result["diagnostics"] != sorted(result["diagnostics"], key=section7_key):
        raise ValueError("診断は結果・診断・終了コード §7の順序で並べる必要があります")


def check_report_contract(identifier, manifest, effects):
    case = CASES[identifier]
    argv = manifest["invocation"]["argv"]
    if ("--report" in argv) != case["report"]:
        raise ValueError("マニフェストの`--report`がレビュー済みのケースと異なります")
    if "--all-workspaces" not in argv or manifest["invocation"]["cwd"] != ".":
        raise ValueError("この群はルートで`--all-workspaces`を渡す必要があります")
    if effects["before"] != effects["after"]:
        raise ValueError("実行前後で既存のパスは不変でなければなりません")
    if not saved_count(identifier):
        # 保存しない（`--report`なし、または保存先が書き込めない）。木構造を変えてはいけない。
        if effects["policy"] != "read-only" or "report" in effects or manifest["expect"]["reportFileCount"] != 0:
            raise ValueError("保存しないケースは木構造を変えてはいけません")
        return
    if effects["policy"] != "explicit-report" or effects["report"]["createdCount"] != 1 or manifest["expect"]["reportFileCount"] != 1:
        raise ValueError("明示したレポートはちょうど1件を作る必要があります")
    if effects["report"]["directory"] != REPORT_DIRECTORY:
        raise ValueError("全体のレポートはルートワークスペースの規定先へ保存する必要があります")
    if effects["report"]["temporaryFilesRemaining"] != 0:
        raise ValueError("原子的な作成は一時ファイルを残してはいけません")
    pattern = effects["report"]["namePattern"]
    operation = case["op"]
    if not re.fullmatch(pattern, f"20000101T000000Z-{operation}.json"):
        raise ValueError("レビュー済みの名前のパターンが妥当なレポート名を拒否しています")
    for bad in (f"{operation}.json", f"20000101T000000Z-{operation}-0.json", "20000101T000000Z-doctor.json", f"20000101T000000Z-{operation}.json.tmp"):
        if re.fullmatch(pattern, bad):
            raise ValueError("レビュー済みの名前のパターンが不正なレポート名を受理しています")
    if EXISTING_REPORT not in effects["before"]["repository"]:
        raise ValueError("既存のレポートがないと排他的な作成を検査できません")


def git_dirty(repository):
    return bool(git(repository, "status", "--porcelain=v1", "--untracked-files=all").strip())


def check_conditions(identifier, repository):
    """原因の構成を、散文ではなく準備手順の後の入力とGitの状態から確かめる。原因以外のカタログの不備を持たないことも要求する。"""
    case = CASES[identifier]
    if not (repository / ".git").exists():
        raise ValueError("Gitのリポジトリが必要です")
    if git_dirty(repository):
        raise ValueError("このfixtureの作業ツリーはコミット済みと同じである必要があります")
    decision = reference_decision(repository)
    root = workspace_id.load_config(repository, ".")
    web = workspace_id.load_config(repository, "apps/web")
    api = workspace_id.load_config(repository, "services/api")
    if dict(decision["members"]) != {"web": "apps/web", "api": "services/api"}:
        raise ValueError("カタログはメンバー`web`、`api`を宣言する必要があります")
    if str(root["earsAi"]) != "1.0" or str(root["schemaVersion"]) != "1.0":
        raise ValueError("ルートの版は対応するメジャーバージョンである必要があります")
    if git(repository, "ls-files", "--", "tools").strip():
        raise ValueError("カタログにない設定を持ってはいけません")
    if case["inputs"] == "member-absent":
        if workspace_id.explicit_id(root) != "platform" or workspace_id.explicit_id(web) != "web":
            raise ValueError("ルートと`web`は明示したIDを持つ必要があります")
        if api is not None or not (repository / "services/api").is_dir():
            raise ValueError("`api`のディレクトリは実在し、設定は存在しない必要があります")
    else:
        if "workspace" in root:
            raise ValueError("ルートの設定が`workspace`を持ってはいけません")
        if workspace_id.explicit_id(web) != "web" or workspace_id.explicit_id(api) != "api":
            raise ValueError("メンバーは明示したIDがカタログのIDと一致する必要があります")
    # レポートはルートの`.spec/reports/`だけに保存する。メンバーの`.spec/reports`は存在しない。
    for member in ("apps/web", "services/api"):
        if (repository / member / REPORT_DIRECTORY).exists():
            raise ValueError("メンバーの`.spec/reports`が存在してはいけません")
    reports = repository / REPORT_DIRECTORY
    if case["reports"] == "directory":
        if not reports.is_dir() or sorted(path.name for path in reports.iterdir()) != ["existing.json"]:
            raise ValueError("レポートのディレクトリは既存のレポート1件だけを持つ必要があります")
        if not git(repository, "ls-files", "--", EXISTING_REPORT).strip():
            raise ValueError("既存のレポートはコミット済みである必要があります")
    elif not reports.is_file() or reports.read_bytes() != BLOCKING_FILE:
        raise ValueError("`.spec/reports`は保存を妨げる通常ファイルである必要があります")
    return decision


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
        with tempfile.TemporaryDirectory(prefix="bitz-multi-early-report-") as temporary:
            sandbox = Path(temporary)
            repository = setup(fixture, manifest, sandbox / "repo")
            external = {name: sandbox / name for name in ("home", "cache", "temporary")}
            for path in external.values():
                path.mkdir()
            state = observe_state(manifest, repository, external)
        (fixture / "side-effects.json").write_text(_dump(reviewed_effects(identifier, state)))


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
            check_report_contract(identifier, manifest, effects)
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-multi-early-report-") as temporary:
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
                    decision = check_conditions(identifier, repository)
                    check_against_reference(identifier, manifest, result, decision)
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, IndexError, ValidationError,
                subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "references": 1, "status": "Passed" if not errors else "Failed", "errors": errors}
