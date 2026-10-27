"""複合ワークスペース全体の`doctor`の診断とメンバーの継続を固定するレビュー済みの入力と期待値。

- `MULTI-026-01`、`MULTI-026-02`: 全体事前検査を通過した後の、ルートワークスペースと全メンバーの診断。
- `MULTI-033`: ルートの設定のEARS-AIのメジャーバージョンが非互換で、全体事前検査が非成功になる（実装の確認事項C31）。
  診断は`doctor`の`SPEC-DOCTOR-EARS-001`（診断レジストリの`DOCTOR-EARS-VERSION`）で、`check`などの`SPEC-EARS-VERSION-001`ではない。
  メンバーの診断は開始しない。期待値の根拠は規範文と承認済みの文言で、Coreの出力ではない。
"""
import json
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from .schemas import schema_path
from . import multi_crosscheck, multi_reference
from .harness import setup
from .initial_fixtures import observe, compare_state

HERE = Path(__file__).resolve().parent
CAPABILITIES = ["context.v1", "check.v1", "verify.v1", "doctor.v1", "multiWorkspace.v1"]
CORE = {"version": "1.0.0", "apiVersion": "1.0", "capabilities": CAPABILITIES}
CASES = {
    "MULTI-026-01": "rootと全memberを順序どおりdoctor診断する",
    "MULTI-026-02": "memberのcommand失敗後も後続memberを診断して全体へ集約する",
    "MULTI-033": "ルートのEARS-AIのメジャーバージョンの非互換で全体事前検査が止まり、doctorの診断コードを返す",
}
# 全体事前検査が止まるfixture。メンバーの診断を開始せず、`workspaces`は空配列である。
PRECHECK_STOPPED = ("MULTI-033",)
# 承認済みの文言（`Coreの出力文言のレビュー記録.md`。ADR-062 Decision 2）。規範文から導いた値ではなく、Coreの出力を写した値でもない。
EARS_SUMMARY = "未対応のEARS-AIのメジャーバージョンです"
EARS_ACTION = "設定キーearsAiをCoreが対応するメジャーバージョン1に合わせてください"
# Core 1.0が対応するEARS-AIのメジャーバージョン（`doctor`仕様 §3の検査8、診断レジストリ）。
SUPPORTED_EARS_MAJOR = 1
INCOMPATIBLE_EARS_AI = "2.0"


def api_config(identifier):
    value = multi_reference.plain_config("api")
    if identifier == "MULTI-026-02":
        value += (
            "verify:\n"
            "  commands:\n"
            "    backend:\n"
            "      argv: [./missing-command]\n"
            "      cwd: .\n"
        )
    return value


def stopped_root_config():
    """ルートの設定は、`earsAi`だけが非互換である。ほかはカタログとして正しく、メンバーはwebの1つである。"""
    return multi_reference.root_config([("web", "apps/web")]).replace(
        'earsAi: "1.0"', f'earsAi: "{INCOMPATIBLE_EARS_AI}"')


def reviewed_inputs(identifier):
    if identifier in PRECHECK_STOPPED:
        return {
            multi_reference.ROOT_CONFIG_PATH: stopped_root_config().encode(),
            multi_reference.WEB_CONFIG_PATH: multi_reference.plain_config("web").encode(),
        }
    return {
        multi_reference.ROOT_CONFIG_PATH: multi_reference.root_config(
            [("web", "apps/web"), ("api", "services/api")]).encode(),
        multi_reference.API_CONFIG_PATH: api_config(identifier).encode(),
        multi_reference.WEB_CONFIG_PATH: multi_reference.plain_config("web").encode(),
    }


def reviewed_manifest(identifier):
    text = identifier == "MULTI-026-02"
    blocked = text or identifier in PRECHECK_STOPPED
    expect = {
        "status": "blocked" if blocked else "passed",
        "exitCode": 2 if blocked else 0,
        "stdout": "text" if text else "json",
        "resultFile": "expected/doctor.json",
        "reportFileCount": 0,
    }
    if text:
        expect["textFile"] = "expected/doctor.txt"
    return {
        "fixtureId": identifier,
        "description": CASES[identifier],
        "setup": {"git": True, "baseCommit": {"message": "base", "paths": ["."]},
                  "operations": []},
        # `MULTI-033`はリポジトリのルートで実行する。ほかはメンバーの配下から実行する。
        "invocation": {"runner": "bitz", "cwd": "." if identifier in PRECHECK_STOPPED else "apps/web",
                       "argv": ["doctor", "--all-workspaces"] + ([] if text else ["--format", "json"]),
                       "env": {}},
        "expect": expect,
    }


def checks(command="passed"):
    return [
        {"name": "workspace", "status": "passed"},
        {"name": "config", "status": "passed"},
        {"name": "schema", "status": "passed"},
        {"name": "ears", "status": "passed"},
        {"name": "command", "status": command},
        {"name": "impact", "status": "info"},
    ]


def command_diagnostic():
    return {
        "code": "SPEC-DOCTOR-COMMAND-001",
        "severity": "error",
        "resultStatus": "blocked",
        "summary": "コマンドの実行可能ファイルを解決できません",
        "source": {"kind": "file", "workspaceId": "api", "path": ".spec/bitz.yaml",
                   "key": "verify.commands.backend.argv"},
        "suggestedAction": "設定キーverify.commands.backend.argvの先頭の実行可能ファイルを"
                           "インストールするか、正しいパスを指定してください",
    }


def workspace(workspace_id, path, status="passed", command="passed", diagnostics=()):
    return {
        "id": workspace_id,
        "path": path,
        "status": status,
        "checks": checks(command),
        "durationMs": 0,
        "diagnostics": [dict(entry) for entry in diagnostics],
    }


def ears_diagnostic():
    """ルートの設定のEARS-AIのメジャーバージョンの非互換。発生元はルートの設定の`earsAi`である（単一ワークスペースの`SINGLE-095`と同じ形）。"""
    return {
        "code": "SPEC-DOCTOR-EARS-001",
        "severity": "error",
        "resultStatus": "blocked",
        "summary": EARS_SUMMARY,
        "source": {"kind": "file", "workspaceId": "platform", "path": ".spec/bitz.yaml", "key": "earsAi"},
        "suggestedAction": EARS_ACTION,
    }


def reviewed_stopped_result(identifier):
    """全体事前検査が止まる結果。ルートの設定のメジャーバージョンが非対応なので、最上位の`catalog`は`blocked`（`doctor`仕様 §3）で、
    `workspaces`は空である。"""
    return {
        "schemaVersion": "1.0",
        "operation": "doctor",
        "status": "blocked",
        "multiWorkspace": {"id": "platform", "path": "."},
        "core": dict(CORE),
        "checks": [
            {"name": "core", "status": "passed"},
            {"name": "git", "status": "passed"},
            {"name": "catalog", "status": "blocked"},
        ],
        "workspaces": [],
        "durationMs": 0,
        "diagnostics": [ears_diagnostic()],
    }


def reference_ears_precheck(root_config_text):
    """ルートの設定の`earsAi`だけから、全体事前検査の結果を導く参照計算（Coreは使わない）。

    メジャーバージョンがCoreの対応と異なれば`doctor`の診断（`SPEC-DOCTOR-EARS-001`）を1件返し、等しければ空を返す。
    """
    config = multi_crosscheck.read_yaml(root_config_text)
    major = int(str(config["earsAi"]).split(".")[0])
    return [] if major == SUPPORTED_EARS_MAJOR else [ears_diagnostic()]


def reviewed_result(identifier):
    if identifier in PRECHECK_STOPPED:
        return reviewed_stopped_result(identifier)
    failed = identifier == "MULTI-026-02"
    return {
        "schemaVersion": "1.0",
        "operation": "doctor",
        "status": "blocked" if failed else "passed",
        "multiWorkspace": {"id": "platform", "path": "."},
        "core": dict(CORE),
        "checks": [
            {"name": "core", "status": "passed"},
            {"name": "git", "status": "passed"},
            {"name": "catalog", "status": "passed"},
        ],
        "workspaces": [
            workspace("platform", "."),
            workspace("api", "services/api", "blocked", "blocked", [command_diagnostic()])
            if failed else workspace("api", "services/api"),
            workspace("web", "apps/web"),
        ],
        "durationMs": 0,
        "diagnostics": [],
    }


def reviewed_text(identifier):
    if identifier != "MULTI-026-02":
        raise ValueError("テキストの期待値を持たないfixtureです")
    return (
        "doctor blocked targets=21 diagnostics=1 (0ms)\n"
        "api:.spec/bitz.yaml::: error: SPEC-DOCTOR-COMMAND-001: "
        "コマンドの実行可能ファイルを解決できません\n"
        "  -> 設定キーverify.commands.backend.argvの先頭の実行可能ファイルを"
        "インストールするか、正しいパスを指定してください\n"
    )


def check_precondition(identifier, repository):
    if identifier in PRECHECK_STOPPED:
        text = (repository / multi_reference.ROOT_CONFIG_PATH).read_text(encoding="utf-8")
        root = multi_crosscheck.read_yaml(text)
        web = multi_crosscheck.read_yaml((repository / multi_reference.WEB_CONFIG_PATH).read_text(encoding="utf-8"))
        # 原因は`earsAi`のメジャーバージョンだけである。カタログ、メンバー、Gitは正しい。
        if root["workspace"]["id"] != "platform" or root["multiWorkspace"]["members"] != [{"id": "web", "path": "apps/web"}]:
            raise ValueError("ルートワークスペースのカタログが想定と異なります")
        if root["earsAi"] != INCOMPATIBLE_EARS_AI or web["earsAi"] != "1.0":
            raise ValueError("ルートだけがEARS-AIのメジャーバージョンの非互換である必要があります")
        if text.replace(f'earsAi: "{INCOMPATIBLE_EARS_AI}"', 'earsAi: "1.0"') != multi_reference.root_config([("web", "apps/web")]):
            raise ValueError("ルートの設定は`earsAi`以外が最小のカタログと同じである必要があります")
        if reference_ears_precheck(text) != [ears_diagnostic()]:
            raise ValueError("参照計算がEARS-AIのメジャーバージョンの非互換を導きません")
        return
    root_id, members = multi_crosscheck.catalog(repository)
    catalog_order = [("web", "apps/web"), ("api", "services/api")]
    result_order = [("api", "services/api"), ("web", "apps/web")]
    if root_id != "platform" or members != catalog_order or sorted(members) != result_order:
        raise ValueError("全体操作の`doctor`のワークスペースの集合または順序が不正です")
    if identifier == "MULTI-026-02":
        config = multi_crosscheck.read_yaml(
            (repository / multi_reference.API_CONFIG_PATH).read_text(encoding="utf-8"))
        argv = config["verify"]["commands"]["backend"]["argv"]
        if argv != ["./missing-command"] or (repository / "services/api/missing-command").exists():
            raise ValueError("メンバーのコマンド不在条件が成立していません")


def _dump(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def generate(root=HERE, identifiers=PRECHECK_STOPPED):
    """レビュー済みの入力と期待値からfixtureを書き出す。副作用の期待値は、隔離した準備手順の観測で作る（Coreは実行しない）。

    既定は`MULTI-033`だけである。`MULTI-026-01`〜`02`は整形の異なる既存のファイルを持つので、引数で指定したときだけ書き直す。
    """
    for identifier in CASES:
        if identifiers is not None and identifier not in identifiers:
            continue
        fixture = root / "multi" / identifier
        for name, content in reviewed_inputs(identifier).items():
            path = fixture / "repo" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        manifest = reviewed_manifest(identifier)
        (fixture / "manifest.json").write_text(_dump(manifest))
        (fixture / "expected").mkdir(parents=True, exist_ok=True)
        (fixture / "expected/doctor.json").write_text(_dump(reviewed_result(identifier)))
        if identifier == "MULTI-026-02":
            (fixture / "expected/doctor.txt").write_text(reviewed_text(identifier))
        with tempfile.TemporaryDirectory(prefix="bitz-multi-doctor-") as temporary:
            sandbox = Path(temporary)
            repository = setup(fixture, manifest, sandbox / "repo")
            external = {name: sandbox / name for name in ("home", "cache", "temporary")}
            for path in external.values():
                path.mkdir()
            state = observe(repository, external)
        (fixture / "side-effects.json").write_text(
            _dump({"schemaVersion": "1.0", "policy": "read-only", "before": state, "after": state}))


def check_stopped_contract(manifest, result):
    """全体事前検査が止まる結果の構造。リテラルの期待値とは別に、規範文から導く条件を要求する。"""
    codes = [item["code"] for item in result["diagnostics"]]
    # 診断は`doctor`のコード1件だけで、`check`などのコードを混ぜない（診断レジストリ `DOCTOR-EARS-VERSION`／`EARS-SCHEMA-MAJOR`）。
    if codes != ["SPEC-DOCTOR-EARS-001"] or "suggestedAction" not in result["diagnostics"][0]:
        raise ValueError("診断は修復手順を持つ`SPEC-DOCTOR-EARS-001`の1件だけである必要があります")
    # 全体事前検査が非成功なら、メンバーの診断を開始しない（`doctor`仕様 §3）。
    if result["workspaces"]:
        raise ValueError("全体事前検査が非成功の結果は、メンバーの診断を開始してはいけません")
    # ルートの設定のメジャーバージョンが非対応なら、カタログの検査項目を`blocked`で置く（`doctor`仕様 §3）。
    if result["checks"] != [{"name": "core", "status": "passed"}, {"name": "git", "status": "passed"},
                            {"name": "catalog", "status": "blocked"}]:
        raise ValueError("最上位の検査項目は`core`、`git`と、`blocked`の`catalog`である必要があります")
    if result["status"] != "blocked" or manifest["expect"]["exitCode"] != 2:
        raise ValueError("診断の効果`blocked`は終了コード2である必要があります")


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
            result = json.loads((fixture / "expected/doctor.json").read_text())
            effects = json.loads((fixture / "side-effects.json").read_text())
            for name, value in (("manifest", manifest), ("result", result), ("side-effects", effects)):
                validators[name].validate(value)
            if manifest != reviewed_manifest(identifier):
                raise ValueError("起動条件がレビュー済みの期待値と異なります")
            if result != reviewed_result(identifier):
                raise ValueError("完全結果がレビュー済みの期待値と異なります")
            if identifier in PRECHECK_STOPPED:
                check_stopped_contract(manifest, result)
            if identifier == "MULTI-026-02" and (
                    fixture / "expected/doctor.txt").read_text() != reviewed_text(identifier):
                raise ValueError("テキストの期待値がレビュー済みの期待値と異なります")
            entries = {path.relative_to(fixture / "repo").as_posix(): path.read_bytes()
                       for path in (fixture / "repo").rglob("*") if path.is_file()}
            if entries != reviewed_inputs(identifier):
                raise ValueError("入力がレビュー済みのcorpusと異なります")
            if effects["before"] != effects["after"]:
                raise ValueError("読取り専用の期待値が書込みを許しています")
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-multi-doctor-") as temporary:
                for run in range(2):
                    sandbox = Path(temporary) / str(run)
                    sandbox.mkdir()
                    repository = setup(fixture, manifest, sandbox / "repo")
                    external = {name: sandbox / name for name in ("home", "cache", "temporary")}
                    for path in external.values():
                        path.mkdir()
                    actual = observe(repository, external)
                    if compare_state(effects["before"], actual) or (previous is not None and previous != actual):
                        raise ValueError("隔離した準備手順が固定したスナップショットと異なります")
                    previous = actual
                    check_precondition(identifier, repository)
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, IndexError, ValidationError,
                subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "status": "Passed" if not errors else "Failed", "errors": errors}
