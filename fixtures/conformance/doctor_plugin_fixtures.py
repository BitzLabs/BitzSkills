"""`doctor`のプラグインの要求（Core APIの範囲と対応機能）の判定を固定する（Coreの公開操作は実行しない）。

根拠は[ADR-061](../../docs/02.設計書/10_決定記録/ADR-061_doctorのプラグイン要求の字句と判定を確定する.md)、`doctor`仕様 §3・§4・§4.1・§7・§8、
診断レジストリ、結果・診断・終了コード §3・§7、Core実行環境・CLI基盤契約 §5である（実装の確認事項C6）。

- `SINGLE-160`: 要求が完全で互換。検査項目`core`の直後に`plugin`と`capability`が`passed`で並ぶ。
- `SINGLE-161`: Core APIが範囲を満たさない。`SPEC-DOCTOR-API-001`（`blocked`）。対応機能は満たすので`capability`は`passed`。
- `SINGLE-162`: 対応機能が不足する。`SPEC-DOCTOR-CAPABILITY-001`（`blocked`）。Core APIは満たすので`plugin`は`passed`。
- `SINGLE-163`: `--plugin-version`と`--require-core-api`が欠ける。`SPEC-DOCTOR-PLUGIN-001`（`failed`）。`capability`は置かない。
- `SINGLE-164-01`〜`08`: 字句の不一致。終了コード4で結果を作らず、標準エラー出力に理由を1行だけ書く。1件につき不一致は1つのオプションだけである。
- `MULTI-032`: `doctor --all-workspaces`。`core`、`plugin`、`capability`は最上位に1回だけ置き、診断も最上位に1回だけ置く。メンバーへは複製しない。

期待値は、規範文から導いたリテラルと、このモジュールが引数列だけから導く参照計算（`reference_lexical_errors`、`reference_plugin_outcome`）の
両方で求め、一致を要求する。Coreの出力は期待値の根拠にしない。ただし`summary`の文字列は規範文が定めないため、Coreの`messages.py`の文言を
既存の慣行どおりに使う。規範文から導いた値ではない。
`suggestedAction`の文字列は、管理者が2026-10-12に承認した文言である（ADR-062 Decision 2、`Coreの出力文言のレビュー記録.md` PR-4の節）。
これも規範文から導いた値ではなく、Coreの出力を写したものでもない。
"""
import json
from pathlib import Path
import re
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from .schemas import schema_path
from . import multi_doctor_fixtures
from .git_environment_fixtures import check_cli_error_output
from .harness import git, setup
from .initial_fixtures import CONFIGS, observe, compare_state
from .registry_closure_fixtures import CORE, EXIT, doctor_checks

HERE = Path(__file__).resolve().parent
# ADR-061 Decision 3：Core 1.0のAPIのバージョンと公開する対応機能（`doctor`仕様 §4）。
CORE_API = (1, 0)
CAPABILITIES = ("context.v1", "check.v1", "verify.v1", "doctor.v1", "multiWorkspace.v1")
PLUGIN = "bitz-sdd"
VERSION = "1.2.0"
# 規範文が文言を定めないため、Coreの`messages.py`の文言を使う（規範文から導いた値ではない）。
SUMMARIES = {
    "SPEC-DOCTOR-PLUGIN-001": "プラグインの要求が不完全です",
    "SPEC-DOCTOR-API-001": "CoreのAPIのバージョンがプラグインの要求する範囲を満たしません",
    "SPEC-DOCTOR-CAPABILITY-001": "プラグインの要求する対応機能をCoreが公開していません",
}
# 管理者が承認した`suggestedAction`の文型（`{…}`は差し込む値）。参照計算が使う。リテラルの期待値は文字列全体を別に書く。
ACTION_TEMPLATES = {
    "SPEC-DOCTOR-PLUGIN-001": "--plugin、--plugin-version、--require-core-apiを同時に指定してください",
    "SPEC-DOCTOR-API-001": "範囲{required}を満たすCoreへ更新するか、Core APIのバージョン{core_api}に対応するプラグインを使ってください",
    "SPEC-DOCTOR-CAPABILITY-001": "対応機能{missing}を公開するCoreへ更新するか、プラグインの要求を見直してください",
}
REQUEST_OPTIONS = ("--plugin", "--plugin-version", "--require-core-api", "--require-capability")


def request(plugin=PLUGIN, version=VERSION, api="^1.0", capabilities=("context.v1", "check.v1")):
    """`doctor`のプラグインの要求の引数列。値を`None`にしたオプションは渡さない。"""
    argv = []
    for name, value in (("--plugin", plugin), ("--plugin-version", version), ("--require-core-api", api)):
        if value is not None:
            argv += [name, value]
    for capability in capabilities:
        argv += ["--require-capability", capability]
    return argv


# 単一ワークスペース：id: (`doctor`の後ろの引数列, 説明)。`--format json`は末尾に付ける。
SINGLE = {
    "SINGLE-160": (request(), "プラグインの要求が完全で、Core APIと対応機能の両方を満たす"),
    "SINGLE-161": (request(api=">=1.1"), "Core APIのバージョンが要求する範囲を満たさない"),
    "SINGLE-162": (request(capabilities=("context.v2", "check.v1")), "要求した対応機能をCoreが公開していない"),
    "SINGLE-163": (request(version=None, api=None, capabilities=("context.v1",)),
                   "プラグインの要求の組合せが不完全で、--plugin-versionと--require-core-apiが欠ける"),
}
# 字句の不一致：id: (不一致のオプション, 引数列, 説明)。ほかのオプションは字句が正しい。
LEXICAL = {
    "SINGLE-164-01": ("--require-core-api", request(api="~1.0"), "範囲の~はnpm形式として受け付けず、終了コード4で拒否する"),
    "SINGLE-164-02": ("--plugin", request(plugin="Bitz-SDD"), "プラグインIDの大文字を拒否する"),
    "SINGLE-164-03": ("--require-capability", request(capabilities=("context.v0",)),
                      "対応機能名のバージョンが0を拒否する"),
    "SINGLE-164-04": ("--plugin-version", request(version="1.0"), "プラグインのバージョンのパッチ部の欠落を拒否する"),
    "SINGLE-164-05": ("--require-core-api", request(api="^1.0.0"), "範囲のパッチバージョンを拒否する"),
    "SINGLE-164-06": ("--require-core-api", request(api=">=1.0  <2.0"), "範囲の比較子を区切る空白が2文字なら拒否する"),
    "SINGLE-164-07": ("--plugin-version", request(version="v1.2.0"), "プラグインのバージョンの接頭辞vを拒否する"),
    "SINGLE-164-08": ("--plugin", request(plugin="a" * 65), "65文字のプラグインIDを拒否する"),
}
MULTI = {
    "MULTI-032": (["--all-workspaces"] + request(api="^2.0"),
                  "doctor --all-workspacesでCore APIの非互換を最上位へ1回だけ置き、メンバーへ複製しない"),
}


# --- 参照計算（ADR-061 Decision 1〜3を、Coreとは別に書く） ----------------------------------------

_PLUGIN_ID = re.compile(r"[a-z][a-z0-9]*(-[a-z0-9]+)*", re.ASCII)
_IDENT = r"(?:0|[1-9][0-9]*|[0-9]*[a-zA-Z-][0-9a-zA-Z-]*)"
_SEMVER = re.compile(
    r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    rf"(?:-{_IDENT}(?:\.{_IDENT})*)?(?:\+[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*)?", re.ASCII)
_COMPARATOR = re.compile(r"(\^|>=|>|<=|<|=)?(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", re.ASCII)
_CAPABILITY = re.compile(r"[a-zA-Z][a-zA-Z0-9]*\.v[1-9][0-9]*", re.ASCII)


def parse_range(text):
    """`--require-core-api`の範囲を比較子の列へ読む。字句が合わなければ`None`。"""
    comparators = []
    for token in text.split(" "):
        match = _COMPARATOR.fullmatch(token)
        if match is None:
            return None
        comparators.append((match.group(1) or "=", match.group(2), match.group(3)))
    return comparators


def _number_key(value):
    """先頭に`0`を含まない十進の非負整数の大小を、`int`への変換なしに比べるキー（4300桁を超える値も扱う）。"""
    digits = str(value)
    return (len(digits), digits)


def satisfies(api, comparators):
    api = (_number_key(api[0]), _number_key(api[1]))
    for operator, major, minor in comparators:
        bound = (_number_key(major), _number_key(minor))
        if operator == "^":
            # `api < (major + 1).0`は、MAJORが整数なので`api`のMAJOR <= `major`と同じ。
            ok = bound <= api and api[0] <= _number_key(major)
        else:
            ok = {">=": api >= bound, ">": api > bound, "<=": api <= bound, "<": api < bound, "=": api == bound}[operator]
        if not ok:
            return False
    return True


def parse_request(argv):
    """`doctor`の後ろの引数列から、プラグインの要求の4種のオプションを読む。"""
    single, capabilities, index = {}, [], 0
    while index < len(argv):
        name = argv[index]
        if name == "--format":
            index += 2
        elif name == "--all-workspaces":
            index += 1
        elif name in REQUEST_OPTIONS:
            if name == "--require-capability":
                capabilities.append(argv[index + 1])
            elif name in single:
                raise ValueError(f"{name}が重複しています")
            else:
                single[name] = argv[index + 1]
            index += 2
        else:
            raise ValueError(f"想定外の引数です: {name}")
    return single, capabilities


def reference_lexical_errors(argv):
    """字句に一致しないオプションの名前の一覧（ADR-061 Decision 1）。"""
    single, capabilities = parse_request(argv)
    errors = []
    plugin = single.get("--plugin")
    if plugin is not None and not (len(plugin) <= 64 and _PLUGIN_ID.fullmatch(plugin)):
        errors.append("--plugin")
    version = single.get("--plugin-version")
    if version is not None and _SEMVER.fullmatch(version) is None:
        errors.append("--plugin-version")
    api = single.get("--require-core-api")
    if api is not None and parse_range(api) is None:
        errors.append("--require-core-api")
    if any(_CAPABILITY.fullmatch(capability) is None for capability in capabilities):
        errors.append("--require-capability")
    return errors


def reference_plugin_outcome(argv):
    """字句が正しい引数列から、検査項目`plugin`／`capability`と診断を導く（ADR-061 Decision 2〜4）。

    返す値は`(checks, diagnostics)`。4種のオプションのどれも指定しなければ、どちらも空である。
    """
    single, capabilities = parse_request(argv)
    if not single and not capabilities:
        return [], []
    plugin = single.get("--plugin")
    source = {"kind": "environment", "component": "plugin"}
    if plugin is not None:
        source["identifier"] = plugin
    missing = sorted(name for name in ("--plugin", "--plugin-version", "--require-core-api") if name not in single)
    if missing:
        return [{"name": "plugin", "status": "failed"}], [_diagnostic("SPEC-DOCTOR-PLUGIN-001", "failed", source, {"missing": missing})]
    checks, diagnostics = [], []
    api_range = single["--require-core-api"]
    if satisfies(CORE_API, parse_range(api_range)):
        checks.append({"name": "plugin", "status": "passed"})
    else:
        checks.append({"name": "plugin", "status": "blocked"})
        diagnostics.append(_diagnostic("SPEC-DOCTOR-API-001", "blocked", source,
                                       {"coreApi": ".".join(map(str, CORE_API)), "required": api_range}))
    unsupported = sorted(set(capabilities) - set(CAPABILITIES))
    if unsupported:
        checks.append({"name": "capability", "status": "blocked"})
        diagnostics.append(_diagnostic("SPEC-DOCTOR-CAPABILITY-001", "blocked", source, {"missing": unsupported}))
    else:
        checks.append({"name": "capability", "status": "passed"})
    return checks, diagnostics


def _diagnostic(code, status, source, evidence):
    action = ACTION_TEMPLATES[code].format(
        required=evidence.get("required"), core_api=evidence.get("coreApi"), missing="、".join(evidence.get("missing", [])))
    return {"code": code, "severity": "error", "resultStatus": status, "summary": SUMMARIES[code],
            "source": dict(source), "evidence": evidence, "suggestedAction": action}


def sort_diagnostics(diagnostics):
    """共通の並べ替えの規則。ここでは発生元がすべて`environment`なので`code`の辞書順になる。"""
    return sorted(diagnostics, key=lambda item: item["code"])


def worst(statuses):
    order = ["passed", "passed_with_warnings", "blocked", "failed", "error"]
    # 結果・診断・終了コード §3：error > failed > blocked > passed_with_warnings > passed
    return max(statuses, key=order.index)


# --- レビュー済みの期待値（リテラル） ----------------------------------------------------------

def diagnostic_literals(identifier):
    """リテラルで書いた診断。参照計算とは独立に、規範文から導いた値を書く。"""
    source = {"kind": "environment", "component": "plugin", "identifier": PLUGIN}
    api = {"SINGLE-161": ">=1.1", "MULTI-032": "^2.0"}
    if identifier in api:
        return [{"code": "SPEC-DOCTOR-API-001", "severity": "error", "resultStatus": "blocked",
                 "summary": SUMMARIES["SPEC-DOCTOR-API-001"], "source": source,
                 "evidence": {"coreApi": "1.0", "required": api[identifier]},
                 "suggestedAction": f"範囲{api[identifier]}を満たすCoreへ更新するか、Core APIのバージョン1.0に対応するプラグインを使ってください"}]
    if identifier == "SINGLE-162":
        return [{"code": "SPEC-DOCTOR-CAPABILITY-001", "severity": "error", "resultStatus": "blocked",
                 "summary": SUMMARIES["SPEC-DOCTOR-CAPABILITY-001"], "source": source,
                 "evidence": {"missing": ["context.v2"]},
                 "suggestedAction": "対応機能context.v2を公開するCoreへ更新するか、プラグインの要求を見直してください"}]
    if identifier == "SINGLE-163":
        return [{"code": "SPEC-DOCTOR-PLUGIN-001", "severity": "error", "resultStatus": "failed",
                 "summary": SUMMARIES["SPEC-DOCTOR-PLUGIN-001"], "source": source,
                 "evidence": {"missing": ["--plugin-version", "--require-core-api"]},
                 "suggestedAction": "--plugin、--plugin-version、--require-core-apiを同時に指定してください"}]
    return []


def plugin_check_literals(identifier):
    return {
        "SINGLE-160": [{"name": "plugin", "status": "passed"}, {"name": "capability", "status": "passed"}],
        "SINGLE-161": [{"name": "plugin", "status": "blocked"}, {"name": "capability", "status": "passed"}],
        "SINGLE-162": [{"name": "plugin", "status": "passed"}, {"name": "capability", "status": "blocked"}],
        "SINGLE-163": [{"name": "plugin", "status": "failed"}],
        "MULTI-032": [{"name": "plugin", "status": "blocked"}, {"name": "capability", "status": "passed"}],
    }[identifier]


def operation_status(identifier):
    return {"SINGLE-160": "passed", "SINGLE-161": "blocked", "SINGLE-162": "blocked",
            "SINGLE-163": "failed", "MULTI-032": "blocked"}[identifier]


def reviewed_single_result(identifier):
    """検査項目`core`の直後に`plugin`、`capability`を置く。ほかの検査項目と状態は`SINGLE-001`と同じ（プラグインの要求と無関係）。"""
    base = doctor_checks()
    return {"schemaVersion": "1.0", "operation": "doctor", "status": operation_status(identifier),
            "workspace": {"id": "root", "path": "."}, "durationMs": 0,
            "diagnostics": diagnostic_literals(identifier),
            "core": dict(CORE), "checks": base[:1] + plugin_check_literals(identifier) + base[1:]}


def reviewed_multi_result(identifier):
    """最上位の`checks[]`は`core`、`plugin`、`capability`、`git`、`catalog`の順。メンバーの結果は`MULTI-026-01`と同じで、診断を複製しない。"""
    return {
        "schemaVersion": "1.0", "operation": "doctor", "status": operation_status(identifier),
        "multiWorkspace": {"id": "platform", "path": "."}, "core": dict(CORE),
        "checks": [{"name": "core", "status": "passed"}, *plugin_check_literals(identifier),
                   {"name": "git", "status": "passed"}, {"name": "catalog", "status": "passed"}],
        "workspaces": [multi_doctor_fixtures.workspace("platform", "."),
                       multi_doctor_fixtures.workspace("api", "services/api"),
                       multi_doctor_fixtures.workspace("web", "apps/web")],
        "durationMs": 0, "diagnostics": diagnostic_literals(identifier),
    }


def reviewed_inputs(identifier):
    if identifier in MULTI:
        return multi_doctor_fixtures.reviewed_inputs("MULTI-026-01")
    return {".spec/bitz.yaml": CONFIGS["SINGLE-001"].encode()}


def description(identifier):
    for table in (SINGLE, MULTI):
        if identifier in table:
            return table[identifier][1]
    return LEXICAL[identifier][2]


def reviewed_argv(identifier):
    if identifier in LEXICAL:
        return ["doctor", *LEXICAL[identifier][1], "--format", "json"]
    if identifier in MULTI:
        return ["doctor", *MULTI[identifier][0], "--format", "json"]
    return ["doctor", *SINGLE[identifier][0], "--format", "json"]


def reviewed_manifest(identifier):
    if identifier in LEXICAL:
        expect = {"exitCode": 4, "stdout": "none", "reportFileCount": 0}
    else:
        expect = {"status": operation_status(identifier), "exitCode": EXIT[operation_status(identifier)], "stdout": "json",
                  "resultFile": "expected/doctor.json", "reportFileCount": 0}
    if identifier in MULTI:
        setup_value = {"git": True, "baseCommit": {"message": "base", "paths": ["."]}, "operations": []}
        cwd = "apps/web"
    else:
        setup_value, cwd = {"git": True, "operations": []}, "."
    return {"fixtureId": identifier, "description": description(identifier), "setup": setup_value,
            "invocation": {"runner": "bitz", "cwd": cwd, "argv": reviewed_argv(identifier), "env": {}},
            "expect": expect}


def cli_output():
    return {"exitCode": 4, "stdout": "", "stderrPrefix": "bitz: doctor: ", "stderrLineCount": 1,
            "stderrReasonRequired": True, "stderrTerminalControls": False}


def reviewed_result(identifier):
    return reviewed_multi_result(identifier) if identifier in MULTI else reviewed_single_result(identifier)


def all_identifiers():
    return [*SINGLE, *LEXICAL, *MULTI]


# --- 参照計算との照合 ------------------------------------------------------------------------

VALID_VALUES = {"--plugin": PLUGIN, "--plugin-version": VERSION, "--require-core-api": "^1.0",
                "--require-capability": "context.v1"}


def repaired(tail, option):
    """不一致のオプションの値だけを字句の正しい値へ置き換えた引数列。"""
    fixed = list(tail)
    for index, token in enumerate(fixed[:-1]):
        if token == option:
            fixed[index + 1] = VALID_VALUES[option]
    return fixed


def check_reference(identifier, manifest, result):
    """リテラルの期待値が、引数列だけから導く参照計算と一致すること。"""
    argv = manifest["invocation"]["argv"]
    if argv[0] != "doctor":
        raise ValueError("操作は`doctor`である必要があります")
    tail = argv[1:]
    errors = reference_lexical_errors(tail)
    if identifier in LEXICAL:
        option = LEXICAL[identifier][0]
        if errors != [option]:
            raise ValueError("字句の不一致は、想定した1つのオプションだけである必要があります")
        # 陰性対照：不一致のオプションの値だけを直せば、字句の不一致はなくなる。
        if reference_lexical_errors(repaired(tail, option)):
            raise ValueError("不一致のオプションだけが原因である必要があります")
        return
    if errors:
        raise ValueError("字句が正しい引数列である必要があります")
    checks, diagnostics = reference_plugin_outcome(tail)
    if checks != plugin_check_literals(identifier) or sort_diagnostics(diagnostics) != diagnostic_literals(identifier):
        raise ValueError("検査項目または診断が引数列からの参照計算と異なります")
    names = [item["name"] for item in result["checks"]]
    if names[0] != "core" or names[1:1 + len(checks)] != [item["name"] for item in checks]:
        raise ValueError("`plugin`と`capability`は`core`の直後に置く必要があります")
    if identifier in MULTI:
        members = [item["name"] for member in result["workspaces"] for item in member["checks"]]
        if names.count("core") != 1 or names.count("plugin") != 1 or names.count("capability") != 1 or any(
                name in ("core", "plugin", "capability") for name in members):
            raise ValueError("`core`、`plugin`、`capability`は最上位に1回だけ置く必要があります")
        if any(member["diagnostics"] for member in result["workspaces"]):
            raise ValueError("プラグインの要求の診断をメンバーへ複製してはいけません")
    # 操作の状態は診断の`resultStatus`の最悪値である。診断がなければ`passed`である。
    effects = [item["resultStatus"] for item in diagnostics] or ["passed"]
    if result["status"] != worst(effects) or manifest["expect"]["exitCode"] != EXIT[result["status"]]:
        raise ValueError("操作の状態または終了コードが診断の最悪値と異なります")


def check_contract(identifier, manifest):
    if identifier in LEXICAL:
        if "status" in manifest["expect"] or "resultFile" in manifest["expect"]:
            raise ValueError("引数不正は結果を作りません")
        check_cli_error_output(4, b"", b"bitz: doctor: reason\n", "doctor")


# --- 生成と監査 --------------------------------------------------------------------------------

def _dump(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def generate(root=HERE):
    """レビュー済みの入力と期待値からfixtureを書き出す。副作用の期待値は、隔離した準備手順の観測で作る（Coreは実行しない）。"""
    for identifier in all_identifiers():
        fixture = root / ("multi" if identifier in MULTI else "single") / identifier
        for name, content in reviewed_inputs(identifier).items():
            path = fixture / "repo" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        manifest = reviewed_manifest(identifier)
        (fixture / "manifest.json").write_text(_dump(manifest))
        if identifier in LEXICAL:
            (fixture / "cli-output.json").write_text(_dump(cli_output()))
        else:
            (fixture / "expected").mkdir(parents=True, exist_ok=True)
            (fixture / "expected/doctor.json").write_text(_dump(reviewed_result(identifier)))
        with tempfile.TemporaryDirectory(prefix="bitz-doctor-plugin-") as temporary:
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
    for identifier in all_identifiers():
        if identifiers is not None and identifier not in identifiers:
            continue
        fixture = root / ("multi" if identifier in MULTI else "single") / identifier
        try:
            manifest = json.loads((fixture / "manifest.json").read_text())
            effects = json.loads((fixture / "side-effects.json").read_text())
            validators["manifest"].validate(manifest)
            validators["side-effects"].validate(effects)
            if manifest != reviewed_manifest(identifier):
                raise ValueError("起動条件がレビュー済みの期待値と異なります")
            if identifier in LEXICAL:
                if json.loads((fixture / "cli-output.json").read_text()) != cli_output():
                    raise ValueError("CLI出力の期待値がレビュー済みの契約と異なります")
                if (fixture / "expected").exists():
                    raise ValueError("引数不正のfixtureは期待結果のファイルを持ちません")
                result = None
            else:
                if (fixture / "cli-output.json").exists():
                    raise ValueError("結果を返すfixtureは`cli-output.json`を持ちません")
                result = json.loads((fixture / "expected/doctor.json").read_text())
                validators["result"].validate(result)
                if result != reviewed_result(identifier):
                    raise ValueError("完全結果がレビュー済みの期待値と異なります")
            check_reference(identifier, manifest, result)
            check_contract(identifier, manifest)
            expected_inputs = reviewed_inputs(identifier)
            files = {p.relative_to(fixture / "repo").as_posix(): p
                     for p in (fixture / "repo").rglob("*") if p.is_file() or p.is_symlink()}
            if set(files) != set(expected_inputs) or any(
                    p.is_symlink() or p.read_bytes() != expected_inputs[name] for name, p in files.items()):
                raise ValueError("入力がレビュー済みのcorpusと異なります")
            if effects["policy"] != "read-only" or effects["before"] != effects["after"]:
                raise ValueError("読取り専用の期待値が書込みを許しています")
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-doctor-plugin-") as temporary:
                for run in range(2):
                    sandbox = Path(temporary) / str(run)
                    sandbox.mkdir()
                    repository = setup(fixture, manifest, sandbox / "repo")
                    if identifier not in MULTI and (git(repository, "ls-files", "-z") or git(repository, "for-each-ref")):
                        raise ValueError("単一ワークスペースのfixtureはコミットのないリポジトリで、インデックスが空である必要があります")
                    external = {key: sandbox / key for key in ("home", "cache", "temporary")}
                    for path in external.values():
                        path.mkdir()
                    actual = observe(repository, external)
                    if compare_state(effects["before"], actual) or (previous is not None and previous != actual):
                        raise ValueError("隔離した準備手順が固定したスナップショットと異なります")
                    previous = actual
                    if identifier in MULTI:
                        multi_doctor_fixtures.check_precondition("MULTI-026-01", repository)
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, IndexError, ValidationError,
                subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "status": "Passed" if not errors else "Failed", "errors": errors}
