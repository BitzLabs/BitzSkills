"""単一ワークスペースの`--workspace`と、`multiWorkspace`を宣言しない設定の`--all-workspaces`を固定する（Coreの公開操作は実行しない）。

実装の確認事項C73・C64とADR-051の追加に対応する。修正前のCoreは、次の2つの欠陥を持っていた。

- C73: 単一ワークスペースの`--workspace`が、設定がないとき、または設定を読めずに同一性を構成できないときも、値によらず終了コード4
  （「指定したワークスペースが見つかりません」）になり、`--workspace`を付けない場合の停止の結果を返さなかった。
- C64: `multiWorkspace`を宣言しない単一ワークスペースでも、`--all-workspaces`が成功した（入れ子の`.spec`があれば、未登録の診断で`blocked`）。

ユーザーの決定により、規範は次のとおりに明記された。

- Core実行環境・CLI基盤契約 §6: 単一ワークスペースの`--workspace`は、設定から構成したワークスペースの同一性と比べる。設定がない場合と、設定を読めずに同一性を構成できない場合
  （結果・診断・終了コード §2。上限の超過、読取りの失敗、文字コードの不正、設定の構文、型、必須の不正）は、値によらず比べず、`--workspace`を付けない場合と同じ停止の結果を返す
  （複合ワークスペース仕様 §3の5の、全体事前検査が非成功の場合と同じ扱い）。同一性を構成できる場合（既定値`root`、明示のID、スキーマまたはEARS-AIの版の非対応）は、
  一致しない値を引数不正（終了コード4）とする。
- 複合ワークスペース仕様 §8: 設定の読込みを通過したルートの設定（スキーマまたはEARS-AIのメジャーバージョンが非対応の設定を含む）が`multiWorkspace`を宣言しなければ、
  `--all-workspaces`は複合ワークスペースを発見できない引数不正（終了コード4）とする。ルートの設定を読めない場合は、候補を発見した後の不適合として、全体事前検査の停止の結果を返す。

この群は、次の8件で固定する。`SINGLE-170-01`〜`02`、`04`、`05`〜`07`が欠陥を検出し、`03`と`08`は修正前のCoreも通る対照である。

| fixture | 操作と入力 | 期待 |
|---|---|---|
| `SINGLE-170-01` | `check --workspace app --full --base HEAD`。設定のYAMLの構文が不正（閉じられていないフロー配列） | `error`／3。`--workspace`なしと同じ停止の結果。`workspace.id`は`null` |
| `SINGLE-170-02` | `doctor --workspace app`。設定の`language`が整数（型の不正。`SINGLE-092`と同じ入力） | `error`／3。`SINGLE-092`と同じ結果 |
| `SINGLE-170-03` | `context REQ-001 --workspace app`。既定値`root`の設定（対照） | 終了コード4 |
| `SINGLE-170-04` | `verify --workspace app REQ-001`。設定がない | `blocked`／2。`SPEC-WORKSPACE-MISSING-001`だけ |
| `SINGLE-170-05` | `check --all-workspaces --base HEAD`。`multiWorkspace`を宣言しない設定 | 終了コード4 |
| `SINGLE-170-06` | `doctor --all-workspaces`。`multiWorkspace`を宣言しない設定と、入れ子の`.spec` | 終了コード4 |
| `SINGLE-170-07` | `verify --all-workspaces`。`multiWorkspace`を宣言しない、スキーマの版が非対応の設定 | 終了コード4 |
| `SINGLE-170-08` | `check --all-workspaces --base HEAD`。設定のYAMLの構文が不正（対照） | `error`／3。全体事前検査の停止の結果。`multiWorkspace.id`は`null` |

期待値の根拠は、規範文と、このモジュールの参照計算だけである（Coreの出力は根拠にしない）。診断のコード、状態、終了コードは診断レジストリ（`CONFIG-YAML-SYNTAX`は
`SPEC-CONFIG-SCHEMA-001`の`error`／`error`、`WORKSPACE-CONFIG-MISSING`は`SPEC-WORKSPACE-MISSING-001`の`error`／`blocked`）と、結果・診断・終了コード §3による。

診断の文言は、既存の承認済みのものだけを使う。

- 設定のYAMLの構文の不正: 「設定YAMLの構文が不正です」（`MULTI-057-02`。`Coreの出力文言のレビュー記録.md`の承認による）。
- 設定の型の不正: 「設定キーlanguageは文字列で指定してください」（`SINGLE-004-01`、`SINGLE-092`）。
- 設定がない: 「.spec/bitz.yamlがありません」（`SINGLE-094`、`SINGLE-152`）。

終了コード4の`SINGLE-170-03`と`05`〜`07`は、既存の引数不正のfixture（`cli_error_fixtures.py`）の形にならう。結果もレポートも作らず、標準出力は空、標準エラー出力は1行
（`bitz: <操作>: <理由>`）である。理由の文字列は固定しない。
"""
import json
from pathlib import Path
import re
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from . import registry_closure_fixtures
from .document_fixtures import DOCUMENT, REQ_PATH
from .git_environment_fixtures import check_cli_error_output
from .harness import git, setup
from .initial_fixtures import CONFIGS, compare_state, observe
from .multi_member_config_source_fixtures import config_defects, explicit_workspace_id
from .schemas import schema_path

HERE = Path(__file__).resolve().parent
COMMIT = "0" * 40
CONFIG_PATH = ".spec/bitz.yaml"
NESTED_CONFIG_PATH = "services/api/.spec/bitz.yaml"
EXIT_BY_STATUS = {"passed": 0, "passed_with_warnings": 0, "failed": 1, "blocked": 2, "error": 3}

# 承認済みの診断の文言（モジュールの説明を参照）。
SYNTAX_SUMMARY = "設定YAMLの構文が不正です"
MISSING_SUMMARY = ".spec/bitz.yamlがありません"

# 既定値`root`の最小の設定、スキーマの版が非対応の設定、型の不正の設定（`SINGLE-004-01`と同じ値）、YAMLの構文が不正な設定。
DEFAULT_CONFIG = CONFIGS["SINGLE-001"]
SCHEMA_MAJOR_CONFIG = CONFIGS["SINGLE-003"]
TYPE_CONFIG = CONFIGS["SINGLE-004-01"]
# 閉じられていないフロー配列。YAMLの構文として不正で、禁止された構文（アンカーなど）ではない（`MULTI-057-02`と同じ）。
SYNTAX_CONFIG = DEFAULT_CONFIG + "workspace: [\n"
NESTED_CONFIG = DEFAULT_CONFIG + "workspace:\n  id: api\n"

# 設定の不備のうち、ワークスペースの同一性を構成する前に止まるもの（結果・診断・終了コード §2）。版の非対応は同一性を構成できる。
UNCONSTRUCTED = {"limit", "utf8", "syntax", "forbidden", "type"}

# id: dict(op, argv〈`--format json`の前〉, inputs〈入力の種類〉, outcome, defective〈修正前のCoreが欠陥を持つか〉, description)
# outcome: `stop`（停止の結果）または`argument-error`（終了コード4）。
CASES = {
    "SINGLE-170-01": dict(op="check", argv=["check", "--workspace", "app", "--full", "--base", "HEAD"], inputs="syntax", outcome="stop", defective=True,
                          description="設定のYAMLの構文が不正なcheckは、--workspaceの値を比べず、--workspaceなしと同じ停止の結果を返す"),
    "SINGLE-170-02": dict(op="doctor", argv=["doctor", "--workspace", "app"], inputs="type", outcome="stop", defective=True,
                          description="設定の型が不正なdoctorは、--workspaceの値を比べず、--workspaceなしと同じ停止の結果を返す"),
    "SINGLE-170-03": dict(op="context", argv=["context", "REQ-001", "--workspace", "app"], inputs="default", outcome="argument-error",
                          defective=False,
                          description="対照: 同一性を構成できる既定値rootの設定では、一致しない--workspaceを終了コード4で拒否する"),
    "SINGLE-170-04": dict(op="verify", argv=["verify", "--workspace", "app", "REQ-001"], inputs="missing", outcome="stop", defective=True,
                          description="設定がないverifyは、--workspaceの値を比べず、設定の不在の停止の結果を返す"),
    "SINGLE-170-05": dict(op="check", argv=["check", "--all-workspaces", "--base", "HEAD"], inputs="default", outcome="argument-error",
                          defective=True,
                          description="multiWorkspaceを宣言しない設定のcheck --all-workspacesは、複合ワークスペースを発見できず終了コード4にする"),
    "SINGLE-170-06": dict(op="doctor", argv=["doctor", "--all-workspaces"], inputs="nested", outcome="argument-error", defective=True,
                          description="入れ子の.specがあっても、multiWorkspaceを宣言しない設定のdoctor --all-workspacesは終了コード4にする"),
    "SINGLE-170-07": dict(op="verify", argv=["verify", "--all-workspaces"], inputs="schema-major", outcome="argument-error", defective=True,
                          description="スキーマの版が非対応でもmultiWorkspaceを宣言しない設定のverify --all-workspacesは終了コード4にする"),
    "SINGLE-170-08": dict(op="check", argv=["check", "--all-workspaces", "--base", "HEAD"], inputs="syntax", outcome="stop", defective=False,
                          description="対照: 設定のYAMLの構文が不正なcheck --all-workspacesは、引数不正にせず全体事前検査の停止の結果を返す"),
}
RESULT_FILES = {"check": "expected/check.json", "context": "expected/context.json", "doctor": "expected/doctor.json",
                "verify": "expected/verify.json"}


# --- 入力 -------------------------------------------------------------------------------

def reviewed_inputs(identifier):
    """`repo/`の全入力。パス→バイト列。"""
    kind = CASES[identifier]["inputs"]
    if kind == "type":
        # `SINGLE-092`の入力をそのまま使う。
        return dict(registry_closure_fixtures.reviewed_inputs("SINGLE-092"))
    requirement = {REQ_PATH: DOCUMENT.encode()}
    if kind == "missing":
        return requirement
    config = {"default": DEFAULT_CONFIG, "nested": DEFAULT_CONFIG, "schema-major": SCHEMA_MAJOR_CONFIG, "syntax": SYNTAX_CONFIG}[kind]
    inputs = {CONFIG_PATH: config.encode(), **requirement}
    if kind == "nested":
        inputs[NESTED_CONFIG_PATH] = NESTED_CONFIG.encode()
    return inputs


def reviewed_manifest(identifier):
    case = CASES[identifier]
    if case["inputs"] == "type":
        # `SINGLE-092`と同じ準備手順（基準版のコミットを置かない）。
        setup_plan = {"git": True, "operations": []}
    else:
        setup_plan = {"git": True, "baseCommit": {"message": "base", "paths": ["."]}, "operations": []}
    manifest = {
        "fixtureId": identifier,
        "description": case["description"],
        "setup": setup_plan,
        "invocation": {"runner": "bitz", "cwd": ".", "argv": [*case["argv"], "--format", "json"], "env": {}},
    }
    if case["outcome"] == "argument-error":
        # 結果の状態を持たない: 結果ができる前に引数を拒否する。
        manifest["expect"] = {"exitCode": 4, "stdout": "none", "reportFileCount": 0}
    else:
        status = STOPS[case["inputs"]]["status"]
        manifest["expect"] = {"status": status, "exitCode": EXIT_BY_STATUS[status], "stdout": "json",
                              "resultFile": RESULT_FILES[case["op"]], "reportFileCount": 0}
    return manifest


def reviewed_cli_output(identifier):
    return {"exitCode": 4, "stdout": "", "stderrPrefix": f"bitz: {CASES[identifier]['op']}: ", "stderrLineCount": 1,
            "stderrReasonRequired": True, "stderrTerminalControls": False}


# --- レビュー済みの期待結果 -----------------------------------------------------------------

# 入力の種類ごとの、設定の停止の診断。診断レジストリ: `CONFIG-YAML-SYNTAX`は`SPEC-CONFIG-SCHEMA-001`（`error`／`error`）、
# `CONFIG-FIELD-TYPE`は同じ、`WORKSPACE-CONFIG-MISSING`は`SPEC-WORKSPACE-MISSING-001`（`error`／`blocked`、発生元は環境）。
STOPS = {
    "syntax": dict(code="SPEC-CONFIG-SCHEMA-001", status="error", summary=SYNTAX_SUMMARY,
                   source={"kind": "file", "workspaceId": None, "path": CONFIG_PATH}),
    "type": dict(code="SPEC-CONFIG-SCHEMA-001", status="error", summary="設定キーlanguageは文字列で指定してください",
                 source={"kind": "file", "workspaceId": None, "path": CONFIG_PATH, "key": "language"}),
    "missing": dict(code="SPEC-WORKSPACE-MISSING-001", status="blocked", summary=MISSING_SUMMARY,
                    source={"kind": "environment", "component": "workspace", "identifier": "."}),
}


def reviewed_diagnostic(kind):
    stop = STOPS[kind]
    return {"code": stop["code"], "severity": "error", "resultStatus": stop["status"], "summary": stop["summary"],
            "source": dict(stop["source"])}


def is_all_workspaces(identifier):
    return "--all-workspaces" in CASES[identifier]["argv"]


def reviewed_result(identifier):
    """停止の結果の期待値（終了コード4の場合は結果を作らないので呼ばない）。"""
    case = CASES[identifier]
    stop = STOPS[case["inputs"]]
    diagnostics = [reviewed_diagnostic(case["inputs"])]
    revision = {"base": COMMIT, "commit": COMMIT, "dirty": False}
    if case["op"] == "doctor":
        # `SINGLE-092`と同じ結果。`--workspace`の値は結果に現れない。
        return registry_closure_fixtures.reviewed_result("SINGLE-092")
    if case["op"] == "check" and is_all_workspaces(identifier):
        # 全体事前検査の停止。ルートの設定を読めないので、`multiWorkspace.id`は`null`（`MULTI-049-01`と同じ形）。
        return {"schemaVersion": "1.0", "operation": "check", "scope": "all-workspaces", "status": stop["status"],
                "multiWorkspace": {"id": None, "path": "."}, "workspaces": [], "revision": revision, "durationMs": 0,
                "diagnostics": diagnostics}
    if case["op"] == "check":
        return {"schemaVersion": "1.0", "operation": "check", "status": stop["status"], "workspace": {"id": None, "path": "."},
                "durationMs": 0, "diagnostics": diagnostics, "scope": "full", "revision": revision,
                "checkedDocumentCount": 0, "checkedStatementCount": 0}
    # `verify`。早期に返す結果は検証対象もコマンドも持たない。`revision`は、コミットのあるリポジトリなので`commit`と`dirty`（`SINGLE-165`と同じ形）。
    return {"schemaVersion": "1.0", "operation": "verify", "status": stop["status"], "scope": "selected",
            "workspace": {"id": None, "path": "."}, "targetResults": [], "revision": {"commit": COMMIT, "dirty": False},
            "commands": [], "durationMs": 0, "diagnostics": diagnostics}


# --- 参照計算 --------------------------------------------------------------------------------

def read_config(repository):
    path = repository / CONFIG_PATH
    return path.read_bytes() if path.is_file() else None


def identity(data):
    """設定から構成するワークスペースの同一性（結果・診断・終了コード §2、ワークスペース・設定仕様）。構成できなければ`None`。

    設定がない、または同一性を構成する前に止まる不備（上限、文字コード、構文、禁止された構文、型）があれば`None`。版の非対応は同一性を構成できる。
    明示した`workspace.id`がなければ既定値`root`。
    """
    if data is None or any(defect in UNCONSTRUCTED for defect in config_defects(data)):
        return None
    return explicit_workspace_id(data.decode("utf-8")) or "root"


def stop_kind(data):
    """設定の停止の種類（診断レジストリの条件の順に最初の不備）。この群が扱わない不備は拒否する。"""
    if data is None:
        return "missing"
    defects = config_defects(data)
    if defects[:1] == ["syntax"]:
        return "syntax"
    if defects[:1] == ["type"]:
        return "type"
    raise ValueError(f"この群が扱わない設定の不備です: {defects}")


def declares_multi_workspace(data):
    """`multiWorkspace`の宣言は、トップレベルのキーの有無で判定する（複合ワークスペース仕様 §3、`MULTI-043-17`）。"""
    return re.search(r"^multiWorkspace:", data.decode("utf-8"), re.MULTILINE) is not None


def reference_outcome(argv, repository):
    """参照計算: 引数列と設定の本文から、操作が終了コード4にするか、停止の結果を返すかを導く（Core実行環境・CLI基盤契約 §6、複合ワークスペース仕様 §8）。

    - `--workspace`: 同一性を構成できなければ値を比べず、`--workspace`なしと同じ停止の結果。構成できれば、一致しない値は終了コード4。
    - `--all-workspaces`: 設定を読めないなら全体事前検査の停止の結果。YAMLとして読めた設定が`multiWorkspace`を宣言しなければ、発見できず終了コード4。
    """
    data = read_config(repository)
    if "--workspace" in argv:
        value = argv[argv.index("--workspace") + 1]
        constructed = identity(data)
        if constructed is None:
            return {"kind": "stop", "stop": stop_kind(data)}
        if constructed != value:
            return {"kind": "argument-error"}
        raise ValueError("この群は、一致する--workspaceを扱いません")
    if "--all-workspaces" in argv:
        if data is None:
            return {"kind": "argument-error"}
        if identity(data) is None:
            return {"kind": "stop", "stop": stop_kind(data)}
        if not declares_multi_workspace(data):
            return {"kind": "argument-error"}
        raise ValueError("この群は、multiWorkspaceを宣言した設定を扱いません")
    raise ValueError("この群は、--workspaceか--all-workspacesを指定します")


def defective_outcome(argv, repository):
    """修正前のCoreの読み方の再現（確認事項C73・C64の欠陥）。

    - `--workspace`: 設定の有無と同一性の構成の可否にかかわらず、構成した同一性（なければ`null`）と値を比べ、一致しなければ終了コード4にした。
    - `--all-workspaces`: 設定を読めるかぎり`multiWorkspace`の宣言を見ず、複合ワークスペースの処理へ進んだ。設定を読めない場合の停止の結果は変わらない。
    """
    data = read_config(repository)
    if "--workspace" in argv:
        value = argv[argv.index("--workspace") + 1]
        return {"kind": "argument-error"} if identity(data) != value else {"kind": "proceeds"}
    if "--all-workspaces" in argv:
        if data is not None and identity(data) is None:
            return {"kind": "stop", "stop": stop_kind(data)}
        return {"kind": "proceeds"} if data is not None else {"kind": "argument-error"}
    raise ValueError("この群は、--workspaceか--all-workspacesを指定します")


def check_against_reference(identifier, manifest, result, reference):
    """リテラルの期待値が、参照計算と一致することを要求する。"""
    case = CASES[identifier]
    if reference["kind"] != case["outcome"]:
        raise ValueError("結果の種類が入力からの参照計算と異なります")
    if reference["kind"] == "argument-error":
        if result is not None or manifest["expect"] != {"exitCode": 4, "stdout": "none", "reportFileCount": 0}:
            raise ValueError("引数不正は結果もレポートも作らず、終了コードは4である必要があります")
        return
    kind = reference["stop"]
    if kind != case["inputs"]:
        raise ValueError("停止の種類が入力からの参照計算と異なります")
    stop = STOPS[kind]
    if len(result["diagnostics"]) != 1:
        raise ValueError("停止の結果の診断は1件である必要があります")
    diagnostic = result["diagnostics"][0]
    if (diagnostic["code"], diagnostic["resultStatus"], diagnostic["summary"], diagnostic["source"]) != (
            stop["code"], stop["status"], stop["summary"], stop["source"]):
        raise ValueError("診断が入力からの参照計算と異なります")
    if result["status"] != stop["status"] or manifest["expect"]["exitCode"] != EXIT_BY_STATUS[stop["status"]]:
        raise ValueError("結果の状態または終了コードが参照計算と異なります")
    if is_all_workspaces(identifier):
        # 全体事前検査が非成功なので、ワークスペースの処理を始めず`workspaces`は空。ルートの設定を読めないので`multiWorkspace.id`は`null`。
        if result["multiWorkspace"] != {"id": None, "path": "."} or result["workspaces"] != [] or "workspace" in result:
            raise ValueError("全体事前検査の停止の結果の形が参照計算と異なります")
    elif result["workspace"] != {"id": None, "path": "."} or "multiWorkspace" in result:
        # 同一性を構成できないので`workspace.id`は`null`。`--workspace`の値は結果に現れない。
        raise ValueError("`workspace`が参照計算と異なります")
    if '"app"' in json.dumps(result, ensure_ascii=False):
        raise ValueError("`--workspace`の値は結果に現れてはいけません")


def git_dirty(repository):
    return bool(git(repository, "status", "--porcelain=v1", "--untracked-files=all").decode().strip())


def check_conditions(identifier, repository, manifest):
    """入力の構成を、散文ではなく準備手順の後の入力とGitの状態から確かめる。意図した原因以外を持たないことも要求する。"""
    case = CASES[identifier]
    kind = case["inputs"]
    config = read_config(repository)
    if (config is None) != (kind == "missing"):
        raise ValueError("設定の有無がレビュー済みのケースと矛盾します")
    expected_defects = {"syntax": ["syntax"], "type": ["type"], "schema-major": ["schema-major"], "default": [], "nested": []}.get(kind)
    if config is not None and config_defects(config) != expected_defects:
        raise ValueError(f"設定の不備が意図した1か所ではありません: {config_defects(config)}")
    if config is not None:
        text = config.decode("utf-8")
        if kind in {"default", "nested", "schema-major"} and ("workspace" in text or "multiWorkspace" in text):
            raise ValueError("このケースの設定は`workspace.id`も`multiWorkspace`も持ってはいけません（同一性は既定値`root`）")
        if kind != "type" and "multiWorkspace" in text:
            raise ValueError("このfixtureの設定は`multiWorkspace`を宣言してはいけません")
        if "--workspace" in case["argv"] and identity(config) == "app":
            raise ValueError("`--workspace`の値が構成した同一性と一致してはいけません")
    nested = repository / NESTED_CONFIG_PATH
    if nested.exists() != (kind == "nested"):
        raise ValueError("入れ子の`.spec`の有無がレビュー済みのケースと矛盾します")
    if nested.exists() and (config_defects(nested.read_bytes()) != [] or explicit_workspace_id(nested.read_text(encoding="utf-8")) != "api"):
        raise ValueError("入れ子の`.spec`は、有効な設定（`workspace.id: api`）である必要があります")
    if "baseCommit" in manifest["setup"]:
        if git_dirty(repository):
            raise ValueError("このfixtureの作業ツリーはコミット済みと同じである必要があります")
    return reference_outcome(case["argv"], repository), defective_outcome(case["argv"], repository)


# --- 生成と監査 ---------------------------------------------------------------------------------

def _dump(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def generate(root=HERE):
    """レビュー済みの入力と期待値からfixtureを書き出す。副作用の期待値は、隔離した準備手順の観測で作る（Coreは実行しない）。"""
    for identifier, case in CASES.items():
        fixture = root / "single" / identifier
        for name, content in reviewed_inputs(identifier).items():
            path = fixture / "repo" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        manifest = reviewed_manifest(identifier)
        (fixture / "manifest.json").write_text(_dump(manifest))
        if case["outcome"] == "argument-error":
            (fixture / "cli-output.json").write_text(_dump(reviewed_cli_output(identifier)))
        else:
            (fixture / "expected").mkdir(parents=True, exist_ok=True)
            (fixture / RESULT_FILES[case["op"]]).write_text(_dump(reviewed_result(identifier)))
        with tempfile.TemporaryDirectory(prefix="bitz-workspace-selection-") as temporary:
            sandbox = Path(temporary)
            repository = setup(fixture, manifest, sandbox / "repo")
            external = {name: sandbox / name for name in ("home", "cache", "temporary")}
            for path in external.values():
                path.mkdir()
            state = observe(repository, external)
        (fixture / "side-effects.json").write_text(
            _dump({"schemaVersion": "1.0", "policy": "read-only", "before": state, "after": state}))


def check_cli_error_contract(identifier):
    """標準エラー出力の契約は共通のヘルパーが持つ。この操作で動かし、接頭辞や理由が一致しなくなったことを見逃さないようにする。"""
    operation = CASES[identifier]["op"]
    check_cli_error_output(4, b"", f"bitz: {operation}: reason\n".encode(), operation)
    for bad in (f"bitz: {operation}: \n", "bitz: other: reason\n", f"bitz: {operation}: reason\nextra\n"):
        try:
            check_cli_error_output(4, b"", bad.encode(), operation)
        except ValueError:
            continue
        raise ValueError("標準エラー出力の契約が拒否すべき出力を受理しています")


def validate(root=HERE, identifiers=None):
    errors, prepared = [], []
    validators = {name: Draft202012Validator(json.loads(schema_path(root, name).read_text()))
                  for name in ("manifest", "result", "side-effects")}
    for identifier, case in CASES.items():
        if identifiers is not None and identifier not in identifiers:
            continue
        fixture = root / "single" / identifier
        try:
            manifest = json.loads((fixture / "manifest.json").read_text())
            effects = json.loads((fixture / "side-effects.json").read_text())
            validators["manifest"].validate(manifest)
            validators["side-effects"].validate(effects)
            if manifest != reviewed_manifest(identifier):
                raise ValueError("起動条件がレビュー済みの期待値と異なります")
            result = None
            present = {name for name in ("expected", "cli-output.json", "changes") if (fixture / name).exists()}
            if case["outcome"] == "argument-error":
                if present != {"cli-output.json"}:
                    raise ValueError("引数不正のfixtureは`cli-output.json`だけを持ち、期待結果のファイルを持ちません")
                if json.loads((fixture / "cli-output.json").read_text()) != reviewed_cli_output(identifier):
                    raise ValueError("CLI出力の期待値がレビュー済みの契約と異なります")
                check_cli_error_contract(identifier)
            else:
                if present != {"expected"} or {path.relative_to(fixture).as_posix() for path in (fixture / "expected").glob("*")} != {
                        RESULT_FILES[case["op"]]}:
                    raise ValueError("期待結果のファイルが操作と異なります")
                result = json.loads((fixture / RESULT_FILES[case["op"]]).read_text())
                validators["result"].validate(result)
                if result != reviewed_result(identifier):
                    raise ValueError("完全結果がレビュー済みの期待値と異なります")
            inputs = reviewed_inputs(identifier)
            files = {p.relative_to(fixture / "repo").as_posix(): p
                     for p in (fixture / "repo").rglob("*") if p.is_file() or p.is_symlink()}
            if set(files) != set(inputs) or any(p.is_symlink() or p.read_bytes() != inputs[key] for key, p in files.items()):
                raise ValueError("入力がレビュー済みのcorpusと異なります")
            if effects["policy"] != "read-only" or effects["before"] != effects["after"]:
                raise ValueError("読取り専用の期待値が書込みを許しています")
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-workspace-selection-") as temporary:
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
                    reference, broken = check_conditions(identifier, repository, manifest)
                    check_against_reference(identifier, manifest, result, reference)
                    # 欠陥を検出できる入力であること。修正前の読み方は、欠陥のあるケースでは参照計算と異なり、対照では同じである。
                    if (broken != reference) != case["defective"]:
                        raise ValueError("修正前のCoreの欠陥を検出できる入力、または対照の入力ではありません")
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, IndexError, ValidationError,
                subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "references": 1, "status": "Passed" if not errors else "Failed", "errors": errors}
