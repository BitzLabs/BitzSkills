"""共通CLI argv解析（`Core実行環境・CLI基盤契約 §5〜§7`、各操作仕様 §2）。

operation固有処理、workspace探索、file読取りより前にargvだけを検査する。ここで検出した
違反はすべて :class:`~bitz.errors.CliArgError`（終了コード4）として送出する。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import lex
from .errors import CliArgError
from .lex import DOCUMENT_ID_ALL

OPERATIONS = ("context", "check", "verify", "doctor")

_TIMEOUT_RE = re.compile(r"^[1-9][0-9]{0,3}$")
_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


@dataclass
class ParsedArgs:
    operation: str
    positionals: list[str] = field(default_factory=list)
    flags: set[str] = field(default_factory=set)
    single: dict[str, str] = field(default_factory=dict)
    repeat: dict[str, list[str]] = field(default_factory=dict)


def _tokenize(op: str, rest: list[str], flags: set[str], single: set[str], repeat: set[str]) -> ParsedArgs:
    positionals: list[str] = []
    seen_flags: set[str] = set()
    single_values: dict[str, str] = {}
    repeat_values: dict[str, list[str]] = {}
    i = 0
    n = len(rest)
    while i < n:
        tok = rest[i]
        if tok.startswith("--"):
            name = tok
            if "=" in name:
                raise CliArgError(op, f"未知のoption形式です: {name}")
            if name in flags:
                if name in seen_flags:
                    raise CliArgError(op, f"{name}が重複しています")
                seen_flags.add(name)
                i += 1
                continue
            if name in single:
                if name in single_values:
                    raise CliArgError(op, f"{name}が重複しています")
                if i + 1 >= n:
                    raise CliArgError(op, f"{name}に値がありません")
                value = rest[i + 1]
                if value == "":
                    raise CliArgError(op, f"{name}の値が空です")
                single_values[name] = value
                i += 2
                continue
            if name in repeat:
                if i + 1 >= n:
                    raise CliArgError(op, f"{name}に値がありません")
                value = rest[i + 1]
                if value == "":
                    raise CliArgError(op, f"{name}の値が空です")
                bucket = repeat_values.setdefault(name, [])
                if value not in bucket:
                    bucket.append(value)
                i += 2
                continue
            raise CliArgError(op, f"未知のoptionです: {name}")
        if tok == "":
            raise CliArgError(op, "空文字列の位置引数は許可されません")
        positionals.append(tok)
        i += 1
    return ParsedArgs(
        operation=op,
        positionals=positionals,
        flags=seen_flags,
        single=single_values,
        repeat=repeat_values,
    )


def _check_format(op: str, parsed: ParsedArgs, allowed: tuple[str, ...], default: str) -> str:
    value = parsed.single.get("--format", default)
    if value not in allowed:
        raise CliArgError(op, f"--formatの値が不正です: {value}")
    return value


def _check_workspace_value(op: str, value: str) -> None:
    if not lex.WORKSPACE_ID_RE.match(value):
        raise CliArgError(op, f"--workspaceの値が不正です: {value}")


def parse_doctor(rest: list[str]) -> ParsedArgs:
    op = "doctor"
    parsed = _tokenize(
        op,
        rest,
        flags={"--all-workspaces"},
        single={"--format", "--workspace", "--plugin", "--plugin-version", "--require-core-api"},
        repeat={"--require-capability"},
    )
    if parsed.positionals:
        raise CliArgError(op, "doctorは位置引数を受け付けません")
    if "--workspace" in parsed.single and "--all-workspaces" in parsed.flags:
        raise CliArgError(op, "--workspaceと--all-workspacesは排他です")
    if "--workspace" in parsed.single:
        _check_workspace_value(op, parsed.single["--workspace"])
    _check_format(op, parsed, ("text", "json"), "text")
    return parsed


def parse_check(rest: list[str]) -> ParsedArgs:
    op = "check"
    parsed = _tokenize(
        op,
        rest,
        flags={"--full", "--report", "--all-workspaces"},
        single={"--base", "--workspace", "--format"},
        repeat=set(),
    )
    explicit_targets = bool(parsed.positionals)
    for t in parsed.positionals:
        if not lex.is_valid_target(t, DOCUMENT_ID_ALL, allow_path=True):
            raise CliArgError(op, f"targetの構文が不正です: {t}")
    if explicit_targets and "--full" in parsed.flags:
        raise CliArgError(op, "明示対象と--fullは排他です")
    if "--all-workspaces" in parsed.flags and (
        explicit_targets or "--full" in parsed.flags or "--workspace" in parsed.single
    ):
        raise CliArgError(op, "--all-workspacesは明示対象・--full・--workspaceと排他です")
    if "--workspace" in parsed.single:
        _check_workspace_value(op, parsed.single["--workspace"])
    _check_format(op, parsed, ("text", "json"), "text")
    return parsed


def parse_verify(rest: list[str]) -> ParsedArgs:
    op = "verify"
    parsed = _tokenize(
        op,
        rest,
        flags={"--report", "--all-workspaces"},
        single={"--workspace", "--timeout", "--format"},
        repeat=set(),
    )
    explicit_targets = bool(parsed.positionals)
    verify_kinds = frozenset({"REQ", "TECH", "TASK"})
    for t in parsed.positionals:
        if not lex.is_valid_target(t, verify_kinds, allow_path=True):
            raise CliArgError(op, f"targetの構文が不正です: {t}")
    if "--all-workspaces" in parsed.flags and (
        explicit_targets or "--workspace" in parsed.single
    ):
        raise CliArgError(op, "--all-workspacesは明示対象・--workspaceと排他です")
    if "--workspace" in parsed.single:
        _check_workspace_value(op, parsed.single["--workspace"])
    if "--timeout" in parsed.single:
        v = parsed.single["--timeout"]
        if not _TIMEOUT_RE.match(v) or not (1 <= int(v) <= 3600):
            raise CliArgError(op, f"--timeoutの値が不正です: {v}")
    _check_format(op, parsed, ("text", "json"), "text")
    return parsed


def parse_context(rest: list[str]) -> ParsedArgs:
    op = "context"
    parsed = _tokenize(
        op,
        rest,
        flags=set(),
        single={"--purpose", "--format", "--detail", "--expect-digest", "--workspace"},
        repeat={"--expand"},
    )
    if not parsed.positionals:
        raise CliArgError(op, "起点を1件以上指定してください")
    for t in parsed.positionals:
        if not lex.is_valid_target(t, DOCUMENT_ID_ALL, allow_path=False):
            raise CliArgError(op, f"起点の構文が不正です: {t}")
    purpose = parsed.single.get("--purpose", "interpret")
    if purpose not in ("interpret", "implement", "verify"):
        raise CliArgError(op, f"--purposeの値が不正です: {purpose}")
    if purpose != "interpret":
        for t in parsed.positionals:
            if lex.is_document_id(t, frozenset({"ADR"})) or lex.is_statement_id(t, frozenset({"ADR"})):
                raise CliArgError(op, f"ADR起点にpurpose={purpose}は指定できません: {t}")
    detail = parsed.single.get("--detail", "standard")
    if detail not in ("compact", "standard", "full"):
        raise CliArgError(op, f"--detailの値が不正です: {detail}")
    _check_format(op, parsed, ("markdown", "json"), "markdown")
    if "--expect-digest" in parsed.single:
        v = parsed.single["--expect-digest"]
        if not _DIGEST_RE.match(v):
            raise CliArgError(op, f"--expect-digestの値が不正です: {v}")
    if "--workspace" in parsed.single:
        _check_workspace_value(op, parsed.single["--workspace"])
    for v in parsed.repeat.get("--expand", []):
        if not lex.is_document_id(v, DOCUMENT_ID_ALL):
            raise CliArgError(op, f"--expandの値が不正です: {v}")
    return parsed


def parse_argv(argv: list[str]) -> ParsedArgs:
    if not argv:
        raise CliArgError("(no-operation)", "operationを指定してください")
    op = argv[0]
    if op not in OPERATIONS:
        raise CliArgError("(no-operation)", f"未知のoperationです: {op}")
    rest = argv[1:]
    if op == "doctor":
        return parse_doctor(rest)
    if op == "check":
        return parse_check(rest)
    if op == "verify":
        return parse_verify(rest)
    return parse_context(rest)
