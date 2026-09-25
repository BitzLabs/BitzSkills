"""``.spec/bitz.yaml`` の読込みとSchema検査。

`workspace・設定仕様` §4〜§8 と `Diagnostic registry` §3 を実装する。1回読み込んだbyte列を
呼び出し側の同じ操作内で再利用できるよう、読み込み結果を :class:`ConfigOutcome` へまとめて返す。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import lex
from . import messages
from .yamlsafe import YamlForbiddenError, YamlSyntaxError, parse_yaml_subset

CONFIG_PATH = ".spec/bitz.yaml"
CONFIG_LIMIT_BYTES = 64 * 1024
DEFAULT_WORKSPACE_ID = "root"

_TYPE_NAMES = {
    str: "string",
    bool: "boolean",
    int: "integer",
    float: "number",
    dict: "map",
    list: "array",
}

_KNOWN_TOP_KEYS = {
    "schemaVersion",
    "language",
    "earsAi",
    "context",
    "verify",
    "safety",
    "workspace",
    "multiWorkspace",
}

_COMMAND_NAME_RE = lex.re.compile(r"^[a-z][a-z0-9-]{0,31}$")


def _type_name(value: object) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "map"
    if value is None:
        return "null"
    return type(value).__name__


@dataclass
class Diagnostic:
    code: str
    severity: str
    resultStatus: str
    summary: str
    source: dict
    specRefs: list[str] | None = None
    suggestedAction: str | None = None

    def to_dict(self) -> dict:
        d = {
            "code": self.code,
            "severity": self.severity,
            "resultStatus": self.resultStatus,
            "summary": self.summary,
            "source": self.source,
        }
        if self.specRefs:
            d["specRefs"] = self.specRefs
        if self.suggestedAction:
            d["suggestedAction"] = self.suggestedAction
        return d


def _file_source(workspace_id: str | None, key: str | None = None) -> dict:
    src = {"kind": "file", "workspaceId": workspace_id, "path": CONFIG_PATH}
    if key:
        src["key"] = key
    return src


@dataclass
class ConfigOutcome:
    """設定読込みの結果。

    ``stop`` が真のとき、呼び出し側は当該Diagnosticをそのまま返して操作を停止する
    （`stop-operation` 継続単位）。``warnings``（BOM、未知key、`profiles`）は`continue`継続単位の
    Diagnosticであり、stop有無にかかわらず結果へ含める。``workspace_id`` は結果とDiagnosticの
    sourceへ使う実効ID。``stop_stage`` はdoctorが検査項目（config／schema／ears）を割り当てるための
    停止段階で、``"config"``（YAML構文・禁止構文・型・必須field不正、I/O、上限超過）、
    ``"schema-major"``（`schemaVersion` major非互換）、``"ears-major"``（`earsAi` major非互換）、
    またはNone（停止なし）のいずれかを取る。
    """

    diagnostics: list[Diagnostic] = field(default_factory=list)
    warnings: list[Diagnostic] = field(default_factory=list)
    stop: bool = False
    stop_stage: str | None = None
    workspace_id: str | None = None
    config: dict | None = None


def _add_type_error(diags: list[Diagnostic], key: str, expected_type: str) -> None:
    diags.append(
        Diagnostic(
            code="SPEC-CONFIG-SCHEMA-001",
            severity="error",
            resultStatus="error",
            summary=f"{key}は{expected_type}で指定してください",
            source=_file_source(None, key),
        )
    )


def _dedupe_diagnostics(diags: list[Diagnostic]) -> list[Diagnostic]:
    """同一fieldに対する重複Diagnosticを除く（`code`と`source.key`の組で判定）。"""
    seen: set[tuple[str, str | None]] = set()
    result: list[Diagnostic] = []
    for d in diags:
        key = (d.code, d.source.get("key"))
        if key in seen:
            continue
        seen.add(key)
        result.append(d)
    return result


def _add_required_error(diags: list[Diagnostic], key: str) -> None:
    diags.append(
        Diagnostic(
            code="SPEC-CONFIG-SCHEMA-001",
            severity="error",
            resultStatus="error",
            summary=f"必須設定{key}がありません",
            source=_file_source(None, key),
        )
    )


def _argv_diag(key: str, summary: str) -> Diagnostic:
    return Diagnostic(
        code="SPEC-CONFIG-SCHEMA-001",
        severity="error",
        resultStatus="error",
        summary=summary,
        source=_file_source(None, key),
    )


def _validate_command(name: str, raw: object, diags: list[Diagnostic]) -> dict | None:
    """command定義を検査する（`workspace・設定仕様 §6`）。

    argv要素ごとの違反はfixture（`SINGLE-126-01`〜`05`）が要求する文言・
    ``argv[<index>]``形式のsource keyで個別に返す。
    """

    prefix = f"verify.commands.{name}"
    if isinstance(raw, list):
        raw = {"argv": raw}
    if not isinstance(raw, dict):
        _add_type_error(diags, prefix, "mapまたはargv配列")
        return None
    argv = raw.get("argv")
    cwd = raw.get("cwd", ".")
    if not isinstance(argv, list) or not (1 <= len(argv) <= 256):
        diags.append(_argv_diag(f"{prefix}.argv", messages.CONFIG_ARGV_LENGTH_INVALID))
        return None
    ok = True
    for index, value in enumerate(argv):
        key = f"{prefix}.argv[{index}]"
        if not isinstance(value, str):
            diags.append(_argv_diag(key, messages.CONFIG_ARGV_ELEMENT_NOT_STRING))
            ok = False
            continue
        if index == 0 and value == "":
            diags.append(_argv_diag(key, messages.CONFIG_ARGV_FIRST_EMPTY))
            ok = False
        if "\x00" in value:
            diags.append(_argv_diag(key, messages.CONFIG_ARGV_ELEMENT_NUL))
            ok = False
        if len(value.encode("utf-8")) > 32 * 1024:
            diags.append(_argv_diag(key, messages.CONFIG_ARGV_ELEMENT_TOO_LONG))
            ok = False
    if not ok:
        return None
    if not isinstance(cwd, str):
        _add_type_error(diags, f"{prefix}.cwd", "string")
        return None
    return {"argv": argv, "cwd": cwd}


def _validate_schema_version(config: dict, diags: list[Diagnostic]) -> None:
    """`schemaVersion` 自身の型・必須だけを検査する。

    major検査（`Diagnostic registry` priority 144）は他fieldの型・必須検査（142/143）より
    後に位置するが、`schemaVersion`自身の型・必須はmajor判定の前提であるため独立して先に検査する。
    """
    if "schemaVersion" not in config:
        _add_required_error(diags, "schemaVersion")
    elif not isinstance(config["schemaVersion"], str):
        _add_type_error(diags, "schemaVersion", "string")


def _peek_workspace_id(config: dict) -> str:
    """`workspace.id`の型・値域が妥当な場合だけそれを使う。それ以外は既定`root`。

    Schema major不適合時点ではworkspaceの型検査をまだ実施していないため、
    `SPEC-CONFIG-SCHEMA-001`／blockedのsource.workspaceIdをこのbest-effort値で補う。
    """
    workspace_cfg = config.get("workspace")
    if isinstance(workspace_cfg, dict):
        wid = workspace_cfg.get("id")
        if isinstance(wid, str) and lex.WORKSPACE_ID_RE.match(wid):
            return wid
    return DEFAULT_WORKSPACE_ID


def _validate_other_fields(config: dict, diags: list[Diagnostic]) -> None:
    """`schemaVersion`以外の全fieldの型・必須・未知keyを検査する。"""
    for key in config:
        if key == "profiles":
            diags.append(
                Diagnostic(
                    code="SPEC-CONFIG-UNKNOWN-001",
                    severity="warning",
                    resultStatus="passed_with_warnings",
                    summary="profilesはCore 1.0では使用しません",
                    source=_file_source(None, "profiles"),
                )
            )
        elif key not in _KNOWN_TOP_KEYS:
            diags.append(
                Diagnostic(
                    code="SPEC-CONFIG-UNKNOWN-001",
                    severity="warning",
                    resultStatus="passed_with_warnings",
                    summary="未知の設定keyです",
                    source=_file_source(None, key),
                )
            )

    if "language" in config and not isinstance(config["language"], str):
        _add_type_error(diags, "language", "string")

    if "earsAi" not in config:
        _add_required_error(diags, "earsAi")
    elif not isinstance(config["earsAi"], str):
        _add_type_error(diags, "earsAi", "string")

    context_cfg = config.get("context")
    if context_cfg is not None:
        if not isinstance(context_cfg, dict):
            _add_type_error(diags, "context", "map")
        else:
            if "maxDocuments" in context_cfg:
                v = context_cfg["maxDocuments"]
                if not isinstance(v, int) or isinstance(v, bool) or not (1 <= v <= 100):
                    _add_type_error(diags, "context.maxDocuments", "1〜100のinteger")
            if "maxBytes" in context_cfg:
                v = context_cfg["maxBytes"]
                if not isinstance(v, int) or isinstance(v, bool) or not (4096 <= v <= 1048576):
                    _add_type_error(diags, "context.maxBytes", "4096〜1048576のinteger")

    verify_cfg = config.get("verify")
    commands: dict[str, dict] = {}
    if verify_cfg is not None:
        if not isinstance(verify_cfg, dict):
            _add_type_error(diags, "verify", "map")
        else:
            if "timeoutSeconds" in verify_cfg:
                v = verify_cfg["timeoutSeconds"]
                if not isinstance(v, int) or isinstance(v, bool) or not (1 <= v <= 3600):
                    _add_type_error(diags, "verify.timeoutSeconds", "1〜3600のinteger")
            cmds = verify_cfg.get("commands")
            if cmds is not None:
                if not isinstance(cmds, dict):
                    _add_type_error(diags, "verify.commands", "map")
                else:
                    for name, raw in cmds.items():
                        if not _COMMAND_NAME_RE.match(name):
                            _add_type_error(diags, f"verify.commands.{name}", "[a-z][a-z0-9-]{0,31}")
                            continue
                        validated = _validate_command(name, raw, diags)
                        if validated is not None:
                            commands[name] = validated

    safety_cfg = config.get("safety")
    if safety_cfg is not None:
        if not isinstance(safety_cfg, dict):
            _add_type_error(diags, "safety", "map")
        elif "protectApprovedRequirements" in safety_cfg:
            if not isinstance(safety_cfg["protectApprovedRequirements"], bool):
                _add_type_error(diags, "safety.protectApprovedRequirements", "boolean")

    workspace_cfg = config.get("workspace")
    if workspace_cfg is not None:
        if not isinstance(workspace_cfg, dict):
            _add_type_error(diags, "workspace", "map")
        elif "id" in workspace_cfg:
            wid = workspace_cfg["id"]
            if not isinstance(wid, str) or not lex.WORKSPACE_ID_RE.match(wid):
                _add_type_error(diags, "workspace.id", "[a-z][a-z0-9-]{0,31}")

    # multiWorkspace.membersの詳細検証はStep 1の範囲外（複合workspace仕様側で扱う）。
    # TODO(Step5以降): multiWorkspace.membersのcatalog検証を実装する。

    config["_resolvedCommands"] = commands


def load_config(read_bytes, *, ears_version_code: str = "SPEC-EARS-VERSION-001") -> ConfigOutcome:
    """`.spec/bitz.yaml` を読み込みSchema検査する。

    ``read_bytes`` は呼び出し側が用意した生byte列（1回読み込んだものを渡す）。
    ``ears_version_code`` はEARS-AI major非互換時に使うcodeで、doctorだけ
    ``SPEC-DOCTOR-EARS-001`` を渡す（`Diagnostic registry` §6）。
    """

    outcome = ConfigOutcome()

    if len(read_bytes) > CONFIG_LIMIT_BYTES:
        outcome.diagnostics.append(
            Diagnostic(
                code="SPEC-INPUT-LIMIT-001",
                severity="error",
                resultStatus="failed",
                summary="設定fileが64 KiB上限を超過しました",
                source={"kind": "file", "workspaceId": DEFAULT_WORKSPACE_ID, "path": CONFIG_PATH},
            )
        )
        outcome.stop = True
        outcome.stop_stage = "config"
        outcome.workspace_id = DEFAULT_WORKSPACE_ID
        return outcome

    # BOMのwarningは`continue`継続単位のため即座にoutcome.diagnosticsへ入れず、最終的な
    # workspace同一性が確定してからsource.workspaceIdを補い、stop有無にかかわらず
    # outcome.warningsへ入れる（結果契約 §5、Diagnostic registry priority 120）。
    bom_warning: Diagnostic | None = None
    data = read_bytes
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
        bom_warning = Diagnostic(
            code="SPEC-INPUT-BOM-001",
            severity="warning",
            resultStatus="passed_with_warnings",
            summary="設定file先頭のBOMを除いて解析を続行します",
            source={"kind": "file", "workspaceId": None, "path": CONFIG_PATH},
        )

    def _finish_stop(
        stage: str,
        diagnostics: list[Diagnostic],
        workspace_id: str | None,
        extra_warnings: list[Diagnostic] | None = None,
    ) -> ConfigOutcome:
        outcome.diagnostics.extend(diagnostics)
        outcome.stop = True
        outcome.stop_stage = stage
        outcome.workspace_id = workspace_id
        pending = ([bom_warning] if bom_warning is not None else []) + list(extra_warnings or [])
        for w in pending:
            w.source["workspaceId"] = workspace_id
        outcome.warnings.extend(pending)
        return outcome

    def _finish_success(workspace_id: str, value: dict, soft_warnings: list[Diagnostic]) -> ConfigOutcome:
        pending = ([bom_warning] if bom_warning is not None else []) + soft_warnings
        for w in pending:
            w.source["workspaceId"] = workspace_id
        outcome.warnings.extend(pending)
        outcome.workspace_id = workspace_id
        outcome.config = value
        outcome.stop = False
        outcome.stop_stage = None
        return outcome

    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return _finish_stop(
            "config",
            [
                Diagnostic(
                    code="SPEC-INPUT-READ-001",
                    severity="error",
                    resultStatus="failed",
                    summary="設定fileをUTF-8として復号できません",
                    source={"kind": "file", "workspaceId": None, "path": CONFIG_PATH},
                )
            ],
            None,
        )

    try:
        value = parse_yaml_subset(text)
    except YamlSyntaxError:
        return _finish_stop(
            "config",
            [
                Diagnostic(
                    code="SPEC-CONFIG-SCHEMA-001",
                    severity="error",
                    resultStatus="error",
                    summary="設定YAMLの構文が不正です",
                    source={"kind": "file", "workspaceId": None, "path": CONFIG_PATH},
                )
            ],
            None,
        )
    except YamlForbiddenError as exc:
        return _finish_stop(
            "config",
            [
                Diagnostic(
                    code="SPEC-CONFIG-SCHEMA-001",
                    severity="error",
                    resultStatus="error",
                    summary=exc.summary,
                    source=_file_source(None, exc.key),
                )
            ],
            None,
        )

    if value is None:
        value = {}
    if not isinstance(value, dict):
        return _finish_stop(
            "config",
            [
                Diagnostic(
                    code="SPEC-CONFIG-SCHEMA-001",
                    severity="error",
                    resultStatus="error",
                    summary="設定YAMLはmapで記述してください",
                    source={"kind": "file", "workspaceId": None, "path": CONFIG_PATH},
                )
            ],
            None,
        )

    # `schemaVersion`自身の型・必須をmajor判定より先に検査する。他fieldより優先することで、
    # 未対応majorの設定を旧Schemaの型規則で誤ってerror判定しない（Diagnostic registry priority
    # 142/143 対 144。同major内での型・必須検査を優先しつつ、schemaVersion自体は例外的に先読みする）。
    schema_version_errors: list[Diagnostic] = []
    _validate_schema_version(value, schema_version_errors)
    if schema_version_errors:
        return _finish_stop("config", schema_version_errors, None)

    major = str(value["schemaVersion"]).split(".", 1)[0]
    if major != "1":
        tentative_workspace_id = _peek_workspace_id(value)
        return _finish_stop(
            "schema-major",
            [
                Diagnostic(
                    code="SPEC-CONFIG-SCHEMA-001",
                    severity="error",
                    resultStatus="blocked",
                    summary="未対応のSchema majorです",
                    source=_file_source(tentative_workspace_id, "schemaVersion"),
                )
            ],
            tentative_workspace_id,
        )

    # ここまででmajorは対応済み。他の全fieldの型・必須・未知keyを検査する。
    field_errors: list[Diagnostic] = []
    _validate_other_fields(value, field_errors)

    hard_errors = _dedupe_diagnostics([d for d in field_errors if d.resultStatus == "error"])
    soft_warnings = [d for d in field_errors if d.resultStatus == "passed_with_warnings"]

    if hard_errors:
        # 独立した型・必須errorは全件返す（結果契約 §6.1「独立原因は別々に返す」）。
        # ここで識別できないworkspace同一性はDiagnostic・warning双方でnullにする。
        return _finish_stop("config", hard_errors, None, extra_warnings=soft_warnings)

    # 型・必須検査を全field通過。workspace同一性を確定し、earsAiのmajor互換性を検査する。
    workspace_id = _peek_workspace_id(value)

    ears_ai = value.get("earsAi", "1.0")
    ears_major = str(ears_ai).split(".", 1)[0]
    if ears_major != "1":
        return _finish_stop(
            "ears-major",
            [
                Diagnostic(
                    code=ears_version_code,
                    severity="error",
                    resultStatus="blocked",
                    summary="未対応のEARS-AI majorです",
                    source=_file_source(workspace_id, "earsAi"),
                )
            ],
            workspace_id,
            extra_warnings=soft_warnings,
        )

    return _finish_success(workspace_id, value, soft_warnings)


def read_config(path, *, ears_version_code: str = "SPEC-EARS-VERSION-001") -> ConfigOutcome:
    """設定fileを上限+1 byteまでだけ読み、`load_config`へ渡す。

    上限を超えた時点で読取りを続けない（`INPUT-LIMIT-CONFIG`）。権限、I/O、読取り中の消失は
    `INPUT-IO-CONFIG`（`SPEC-INPUT-READ-001`／error）として操作を止める。
    """
    try:
        with open(path, "rb") as f:
            raw = f.read(CONFIG_LIMIT_BYTES + 1)
    except OSError:
        outcome = ConfigOutcome()
        outcome.diagnostics.append(
            Diagnostic(
                code="SPEC-INPUT-READ-001",
                severity="error",
                resultStatus="error",
                summary="設定fileを読み取れません",
                source={"kind": "file", "workspaceId": DEFAULT_WORKSPACE_ID, "path": CONFIG_PATH},
            )
        )
        outcome.stop = True
        outcome.stop_stage = "config"
        outcome.workspace_id = DEFAULT_WORKSPACE_ID
        return outcome
    return load_config(raw, ears_version_code=ears_version_code)
