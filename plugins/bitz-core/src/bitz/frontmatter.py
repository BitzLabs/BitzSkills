"""SPEC MarkdownのFrontmatter検証（`02_SPECモデル/02_文書・Frontmatter・状態仕様.md`）。

YAML構文層は`yamlsafe.parse_yaml_subset`を再利用し、本moduleはSchema（型・必須・値域・
未知key・利用不能field）だけを扱う。文面は`messages.py`に委譲する。呼び出し側
（`document.py`）が`source.path`／`workspaceId`を組み立てるため、ここでは`key`だけを
返す軽量な :class:`FieldIssue` を使う。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import messages

ARRAY_ITEM_LIMIT = 1000

ID_PATTERN = {
    "REQ": re.compile(r"^REQ-[0-9]{3,}$"),
    "TECH": re.compile(r"^TECH-[0-9]{3,}$"),
    "ADR": re.compile(r"^ADR-[0-9]{3,}$"),
    "TASK": re.compile(r"^TASK-[0-9]{3,}$"),
}
STATUS_ENUM = {
    "REQ": {"draft", "approved", "outdated", "rejected"},
    "TECH": {"draft", "approved", "outdated", "rejected"},
    "ADR": {"proposed", "accepted", "rejected", "superseded"},
    "TASK": {"open", "done", "cancelled"},
}
KIND_LABEL = {"REQ": "REQ", "TECH": "TECH", "ADR": "ADR", "TASK": "TASK"}
#: `frontmatter.schema.json`のproperties記述順（relations, implements, tests, verify, changes）に
#: 固定する。setの反復順（PYTHONHASHSEED依存）でDiagnosticの生成順が揺れないようにするため。
ALL_OPTIONAL_FIELDS = ("relations", "implements", "tests", "verify", "changes")
AVAILABLE_OPTIONAL_FIELDS = {
    "REQ": {"relations", "implements", "tests", "verify"},
    "TECH": {"relations", "implements", "tests", "verify"},
    "ADR": {"relations"},
    "TASK": {"relations", "changes"},
}
COMMON_REQUIRED = ("id", "title", "status")
RELATION_KEYS = ("requires", "refines", "addresses", "supersedes", "related")

#: Schema `idString`と同じpattern（複合workspace修飾子・statement suffixを含む）。
_ID_REF_RE = re.compile(
    r"^(?:(?:[a-z][a-z0-9-]{0,31})::)?(?:REQ|TECH|ADR|TASK)-[0-9]{3,}"
    r"(?::[A-Z][A-Z0-9-]*-[0-9]{2,})?$"
)
_COMMAND_NAME_RE = re.compile(r"^[a-z][a-z0-9-]{0,31}$")
_TEST_KEYS = ("path", "covers", "command")
#: `id`・`title`・`status`・`relations`・`implements`・`tests`・`verify`・`changes`・`refs`は
#: Schemaの名前付きproperty。これ以外がextensionValue検査対象の未知／`x-`fieldになる。
_NAMED_FIELDS = set(COMMON_REQUIRED) | set(ALL_OPTIONAL_FIELDS) | {"refs"}


@dataclass
class FieldIssue:
    code: str
    severity: str
    status: str
    summary: str
    key: str | None = None


@dataclass
class FrontmatterOutcome:
    hard: list[FieldIssue] = field(default_factory=list)
    soft: list[FieldIssue] = field(default_factory=list)
    value: dict | None = None
    """検証済みの生Frontmatter辞書（hardが空のときだけ非None）。"""


def _is_scalar(v: object) -> bool:
    return v is None or isinstance(v, (str, int, float, bool))


def _dup_key(v: object):
    return (type(v).__name__, v)


def _has_duplicates(items: list) -> bool:
    seen = set()
    for it in items:
        k = _dup_key(it)
        if k in seen:
            return True
        seen.add(k)
    return False


def _is_bad_path(p: object) -> bool:
    if not isinstance(p, str) or p == "":
        return True
    if p.startswith("/"):
        return True
    if "\x00" in p:
        return True
    if any(ch in p for ch in "*?["):
        return True
    if any(seg in (".", "..") for seg in p.split("/")):
        return True
    return False


def _is_valid_extension_value(v: object, depth: int = 0) -> bool:
    """Schema `extensionValue`（scalar｜scalarArray｜extensionMap、再帰的）を判定する。

    `scalarArray`は重複を許さない。`extensionMap`は文字列keyのmapで、値は同じ規則を
    再帰的に満たす。object配列（listの要素がscalarでないもの）は許可しない（文書仕様 §3.2）。
    """

    if depth > 32:
        return False
    if _is_scalar(v):
        return True
    if isinstance(v, list):
        if any(not _is_scalar(x) for x in v):
            return False
        return not _has_duplicates(v)
    if isinstance(v, dict):
        return all(isinstance(k, str) for k in v) and all(
            _is_valid_extension_value(x, depth + 1) for x in v.values()
        )
    return False


def _is_bad_id_ref(x: object) -> bool:
    return not isinstance(x, str) or x == "" or not _ID_REF_RE.match(x)


def _schema_error(key: str, summary: str) -> FieldIssue:
    return FieldIssue(code="SPEC-FM-SCHEMA-001", severity="error", status="failed", summary=summary, key=key)


def _limit_error(key: str, summary: str) -> FieldIssue:
    return FieldIssue(code="SPEC-INPUT-LIMIT-001", severity="error", status="failed", summary=summary, key=key)


def _required_error(key: str) -> FieldIssue:
    return FieldIssue(
        code="SPEC-FM-REQUIRED-001",
        severity="error",
        status="failed",
        summary=messages.fm_required_missing(key),
        key=key,
    )


def _unavailable_warning(kind: str, key: str) -> FieldIssue:
    return FieldIssue(
        code="SPEC-FM-UNAVAILABLE-001",
        severity="warning",
        status="passed_with_warnings",
        summary=messages.fm_unavailable(KIND_LABEL[kind], key),
        key=key,
    )


def _unknown_warning(key: str) -> FieldIssue:
    return FieldIssue(
        code="SPEC-FM-UNKNOWN-001",
        severity="warning",
        status="passed_with_warnings",
        summary=messages.fm_unknown_field(key),
        key=key,
    )


def _check_path_array(value: object, key: str, limits: list[FieldIssue], hard: list[FieldIssue], label: str) -> bool:
    """``key``がpath配列として妥当か検査する。型不正ならTrueを返し呼び出し側で打ち切る。"""

    if not isinstance(value, list) or any(_is_bad_path(p) for p in value):
        hard.append(_schema_error(key, messages.fm_type_error(key, "stringの配列")))
        return True
    if len(value) > ARRAY_ITEM_LIMIT:
        limits.append(_limit_error(key, messages.array_count_limit(key)))
        return True
    if _has_duplicates(value):
        hard.append(_schema_error(key, messages.fm_array_duplicate(key)))
        return True
    return False


def validate(value: object, kind: str) -> FrontmatterOutcome:
    """1文書のFrontmatter（YAML部分集合としてdecode済み）を検証する。"""

    outcome = FrontmatterOutcome()
    if not isinstance(value, dict):
        outcome.hard.append(_schema_error(None, "Frontmatterはmapで記述してください"))
        return outcome

    limits: list[FieldIssue] = []
    hard: list[FieldIssue] = []

    # --- 必須field ---------------------------------------------------
    for key in COMMON_REQUIRED:
        if key not in value:
            hard.append(_required_error(key))

    # --- id -------------------------------------------------------------
    if "id" in value:
        v = value["id"]
        if v is None:
            hard.append(_schema_error("id", messages.fm_null_forbidden("id")))
        elif not isinstance(v, str):
            hard.append(_schema_error("id", messages.fm_type_error("id", "string")))
        elif v == "":
            hard.append(_schema_error("id", messages.fm_empty_forbidden("id")))
        elif not ID_PATTERN[kind].match(v):
            hard.append(_schema_error("id", messages.fm_id_format_invalid(kind)))

    # --- title ------------------------------------------------------------
    if "title" in value:
        v = value["title"]
        if v is None:
            hard.append(_schema_error("title", messages.fm_null_forbidden("title")))
        elif not isinstance(v, str):
            hard.append(_schema_error("title", messages.fm_type_error("title", "string")))
        elif "\n" in v or "\r" in v or not (1 <= len(v) <= 120) or v.strip() == "":
            hard.append(_schema_error("title", messages.TITLE_LENGTH_RULE))

    # --- status -------------------------------------------------------
    if "status" in value:
        v = value["status"]
        if v is None:
            hard.append(_schema_error("status", messages.fm_null_forbidden("status")))
        elif not isinstance(v, str):
            hard.append(_schema_error("status", messages.fm_type_error("status", "string")))
        elif v == "":
            hard.append(_schema_error("status", messages.fm_empty_forbidden("status")))
        elif v not in STATUS_ENUM[kind]:
            hard.append(_schema_error("status", messages.fm_status_invalid(kind)))

    # --- relations ----------------------------------------------------
    if "relations" in value:
        v = value["relations"]
        if v is None:
            hard.append(_schema_error("relations", messages.fm_null_forbidden("relations")))
        elif not isinstance(v, dict):
            hard.append(_schema_error("relations", messages.fm_type_error("relations", "map")))
        else:
            for rk, rv in v.items():
                if rk not in RELATION_KEYS:
                    hard.append(_schema_error(f"relations.{rk}", messages.fm_relations_unknown_key(rk)))
                    continue
                if not isinstance(rv, list) or any(_is_bad_id_ref(x) for x in rv):
                    hard.append(
                        _schema_error(f"relations.{rk}", messages.fm_type_error(f"relations.{rk}", "ID文字列の配列"))
                    )
                    continue
                if len(rv) > ARRAY_ITEM_LIMIT:
                    limits.append(_limit_error(f"relations.{rk}", messages.array_count_limit(f"relations.{rk}")))
                    continue
                if _has_duplicates(rv):
                    hard.append(_schema_error(f"relations.{rk}", messages.fm_relations_duplicate(rk)))

    # --- implements ------------------------------------------------------
    if "implements" in value:
        v = value["implements"]
        if v is None:
            hard.append(_schema_error("implements", messages.fm_null_forbidden("implements")))
        else:
            _check_path_array(v, "implements", limits, hard, "implements")

    # --- tests --------------------------------------------------------
    if "tests" in value:
        v = value["tests"]
        if v is None:
            hard.append(_schema_error("tests", messages.fm_null_forbidden("tests")))
        elif not isinstance(v, list):
            hard.append(_schema_error("tests", messages.fm_type_error("tests", "objectの配列")))
        elif len(v) > ARRAY_ITEM_LIMIT:
            limits.append(_limit_error("tests", messages.array_count_limit("tests")))
        else:
            dup_keys: list[tuple] = []
            tests_hard = False
            for idx, item in enumerate(v):
                prefix = f"tests[{idx}]"
                if not isinstance(item, dict):
                    hard.append(_schema_error(prefix, messages.fm_type_error(prefix, "object")))
                    tests_hard = True
                    continue
                unknown = [k for k in item if k not in _TEST_KEYS]
                if unknown:
                    hard.append(_schema_error(f"{prefix}.{unknown[0]}", messages.fm_tests_unknown_key(idx, unknown[0])))
                    tests_hard = True
                    continue
                if "path" not in item or "covers" not in item:
                    hard.append(_schema_error(prefix, messages.fm_type_error(prefix, "path・coversを持つobject")))
                    tests_hard = True
                    continue
                path_v = item.get("path")
                if _is_bad_path(path_v):
                    hard.append(_schema_error(f"{prefix}.path", messages.fm_type_error(f"{prefix}.path", "string")))
                    tests_hard = True
                    continue
                covers_v = item.get("covers")
                if not isinstance(covers_v, list) or any(_is_bad_id_ref(x) for x in covers_v):
                    hard.append(
                        _schema_error(f"{prefix}.covers", messages.fm_type_error(f"{prefix}.covers", "ID文字列の配列"))
                    )
                    tests_hard = True
                    continue
                if len(covers_v) > ARRAY_ITEM_LIMIT:
                    limits.append(_limit_error(f"{prefix}.covers", messages.array_count_limit(f"{prefix}.covers")))
                    continue
                if len(covers_v) == 0:
                    hard.append(_schema_error(f"{prefix}.covers", messages.TESTS_COVERS_EMPTY))
                    tests_hard = True
                    continue
                if _has_duplicates(covers_v):
                    hard.append(_schema_error(f"{prefix}.covers", messages.fm_array_duplicate(f"{prefix}.covers")))
                    tests_hard = True
                    continue
                command_v = item.get("command")
                if command_v is not None:
                    if not isinstance(command_v, str) or command_v == "" or not _COMMAND_NAME_RE.match(command_v):
                        hard.append(
                            _schema_error(f"{prefix}.command", messages.fm_type_error(f"{prefix}.command", "command名"))
                        )
                        tests_hard = True
                        continue
                dup_keys.append((path_v, command_v, tuple(sorted(covers_v))))
            if not tests_hard and not limits and _has_duplicates(dup_keys):
                hard.append(_schema_error("tests", messages.TESTS_DUPLICATE))

    # --- verify -------------------------------------------------------
    if "verify" in value:
        v = value["verify"]
        if v is None:
            hard.append(_schema_error("verify", messages.fm_null_forbidden("verify")))
        elif not isinstance(v, str):
            hard.append(_schema_error("verify", messages.fm_type_error("verify", "string")))
        elif v == "":
            hard.append(_schema_error("verify", messages.fm_empty_forbidden("verify")))
        elif not _COMMAND_NAME_RE.match(v):
            hard.append(_schema_error("verify", messages.fm_type_error("verify", "command名")))

    # --- changes --------------------------------------------------------
    if "changes" in value:
        v = value["changes"]
        if v is None:
            hard.append(_schema_error("changes", messages.fm_null_forbidden("changes")))
        else:
            _check_path_array(v, "changes", limits, hard, "changes")

    # --- refs（旧field。型だけ検証し、legacy検出（SPEC-RELATION-LEGACY-001）はPhase Cが行う） ---
    if "refs" in value:
        v = value["refs"]
        if v is None:
            hard.append(_schema_error("refs", messages.fm_null_forbidden("refs")))
        elif not isinstance(v, list) or any(not _is_scalar(x) for x in v):
            hard.append(_schema_error("refs", messages.fm_type_error("refs", "scalarの配列")))
        elif len(v) > ARRAY_ITEM_LIMIT:
            limits.append(_limit_error("refs", messages.array_count_limit("refs")))
        elif _has_duplicates(v):
            hard.append(_schema_error("refs", messages.fm_array_duplicate("refs")))

    # --- 拡張field・未知field（文書仕様 §3.2、Schema additionalProperties=extensionValue） -----
    pending_unknown: list[FieldIssue] = []
    for key, v in value.items():
        if key in _NAMED_FIELDS:
            continue
        if not _is_valid_extension_value(v):
            hard.append(_schema_error(key, messages.fm_extension_invalid(key)))
            continue
        if not key.startswith("x-"):
            pending_unknown.append(_unknown_warning(key))

    if limits:
        outcome.hard = limits
        return outcome
    if hard:
        outcome.hard = hard
        return outcome

    # --- soft warnings（hardが皆無のときだけ評価する。fieldは固定順で反復し、
    # setの反復順（PYTHONHASHSEED依存）でDiagnostic生成順が揺れないようにする） -----------
    soft: list[FieldIssue] = []
    available = AVAILABLE_OPTIONAL_FIELDS[kind]
    for key in ALL_OPTIONAL_FIELDS:
        if key in value and key not in available:
            soft.append(_unavailable_warning(kind, key))

    soft.extend(pending_unknown)

    outcome.soft = soft
    outcome.value = value
    return outcome
