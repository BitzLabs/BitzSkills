"""仕様文書の一覧の構築と、`check --full`の文書の検査（Step 2のフェーズB）。

`02_仕様文書モデル/02_文書・フロントマター・状態仕様.md`、`03_文書種別・本文テンプレート.md`、
`03_操作仕様/02_check.md` §3・§4 と `00_共通契約/05_診断レジストリ.md` §3・§4 を実装する。
関係の解決（参照先の存在・型・循環・旧フィールド`refs`）、`implements`/`tests`のパスの存在、
`covers`の解決、TASKを明示した`check`の境界の検査はフェーズC（次段）で実装するため、本モジュールは行わない。

フェーズCが使う索引として、:func:`build_catalog` は文書ごとの検証済みのフロントマター
（``DocEntry.frontmatter``）と本文の規範文の一覧（``DocEntry.statements``）を保持したまま返す。
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

from . import frontmatter as fm_mod
from . import limits as limits_mod
from . import messages
from .config import Diagnostic
from .earsai import ir as ir_mod
from .earsai.parser import parse_document
from .earsai.scanner import normal_line_numbers, normalize_newlines, scan_candidates
from .yamlsafe import YamlForbiddenError, YamlSyntaxError, parse_yaml_subset

# ファイル単位の上限（仕様文書の大きさ、フロントマターの大きさ、1文書の規範文の数、1文書の配列の項目の数）と仕様文書のファイル数は、
# 呼び出し側が渡す:class:`bitz.limits.Limits`で決める（安全な入出力・互換性 §4・§4.1、ADR-076）。省略したときは絶対上限を使う。

DOC_KIND_DIR = {"REQ": "requirements", "TECH": "technical", "ADR": "decisions", "TASK": "tasks"}
DIR_TO_KIND = {v: k for k, v in DOC_KIND_DIR.items()}
#: `.spec/`直下の、エントリの種別にかかわらず既知とし、探索せず、中身を読まないエントリ（ワークスペース・設定仕様 §3）。
#: `reports`は結果の保存先、`journal`と`plans`は経過の記録と計画の置き場として予約したもの（ADR-074）。
RESERVED_TOP_ENTRIES = frozenset({"reports", "journal", "plans"})
KNOWN_TOP_ENTRIES = {"bitz.yaml", "requirements", "technical", "decisions", "tasks"} | RESERVED_TOP_ENTRIES

REQUIRED_REQ_SECTIONS = ("Intent", "Acceptance Criteria", "Verification")
ALLOWED_STATEMENT_SECTIONS = {
    "REQ": {"Acceptance Criteria"},
    "TECH": {"Contract", "Constraints"},
    "ADR": set(),
    "TASK": set(),
}

_FILE_ID_RE = re.compile(r"^((?:REQ|TECH|ADR|TASK)-[0-9]{3,})(?:-.+)?$")
_H1_RE = re.compile(r"^# (.*)$")
_H2_RE = re.compile(r"^## (.*)$")

#: `kind` -> (`code`, `category`) 。`category`は"hard-draft"（`draft`なら`continue`の警告、それ以外は`skip-document`
#: の`error`）、"hard-always"（`draft`に依存せず常に`skip-document`の`error`）、"soft"（常に`continue`の警告）。
_EARS_TABLE = {
    ir_mod.CONDITION_CODE_UNCLOSED: ("EAI-CORE-SYNTAX-005", "hard-draft"),
    ir_mod.CONDITION_TAG_UNCLOSED: ("EAI-CORE-SYNTAX-004", "hard-draft"),
    ir_mod.CONDITION_ID_FORMAT: ("EAI-CORE-ID-001", "hard-always"),
    ir_mod.CONDITION_ID_DUPLICATE: ("EAI-CORE-ID-002", "hard-always"),
    ir_mod.CONDITION_TAG_ORDER: ("EAI-CORE-SYNTAX-001", "hard-draft"),
    ir_mod.CONDITION_TAG_REQUIRED: ("EAI-CORE-SYNTAX-002", "hard-draft"),
    ir_mod.CONDITION_TRIGGER_MULTIPLE: ("EAI-CORE-SYNTAX-003", "hard-draft"),
    ir_mod.CONDITION_PERIOD_MISSING: ("EAI-CORE-SYNTAX-006", "hard-draft"),
    ir_mod.CONDITION_OPERAND_MISSING: ("EAI-CORE-SEM-001", "hard-draft"),
    ir_mod.CONDITION_SHOULD_REASON_MISSING: ("EAI-CORE-SHOULD-001", "soft"),
    ir_mod.CONDITION_EXTENSION_UNKNOWN: ("EAI-EXT-UNKNOWN-001", "soft"),
}


def _mk(code, severity, status, summary, path, workspace_id, *, line=None, column=None, key=None) -> Diagnostic:
    src: dict = {"kind": "file", "workspaceId": workspace_id, "path": path}
    if line is not None:
        src["line"] = line
        src["column"] = column
    if key is not None:
        src["key"] = key
    return Diagnostic(code=code, severity=severity, resultStatus=status, summary=summary, source=src)


_TAG_UNCLOSED_DETAIL_TEXT = {
    "escape": messages.EAI_UNKNOWN_ESCAPE,
    "quote": messages.EAI_QUOTE_UNCLOSED,
    "unclosed": messages.EAI_TAG_UNCLOSED,
    "invalid": messages.EAI_TAG_INVALID,
}


def _tag_unclosed_summary(detail: str | None) -> str:
    return _TAG_UNCLOSED_DETAIL_TEXT.get(detail, messages.EAI_TAG_UNCLOSED)


_EARS_SUMMARY = {
    ir_mod.CONDITION_CODE_UNCLOSED: lambda detail: messages.EAI_CODE_UNCLOSED,
    ir_mod.CONDITION_TAG_UNCLOSED: _tag_unclosed_summary,
    ir_mod.CONDITION_ID_FORMAT: lambda detail: messages.EAI_ID_FORMAT,
    ir_mod.CONDITION_ID_DUPLICATE: lambda detail: messages.EAI_ID_DUPLICATE,
    ir_mod.CONDITION_TAG_ORDER: lambda detail: messages.EAI_TAG_ORDER,
    ir_mod.CONDITION_TAG_REQUIRED: lambda detail: messages.EAI_TAG_REQUIRED,
    ir_mod.CONDITION_TRIGGER_MULTIPLE: lambda detail: messages.EAI_TRIGGER_MULTIPLE,
    ir_mod.CONDITION_PERIOD_MISSING: lambda detail: messages.EAI_PERIOD_MISSING,
    ir_mod.CONDITION_OPERAND_MISSING: lambda detail: messages.EAI_OPERAND_MISSING,
    ir_mod.CONDITION_SHOULD_REASON_MISSING: lambda detail: messages.EAI_SHOULD_REASON_MISSING,
    ir_mod.CONDITION_EXTENSION_UNKNOWN: lambda detail: messages.EAI_EXTENSION_UNKNOWN,
}


@dataclass
class DocEntry:
    path: str
    kind: str
    doc_id: str | None = None
    title: str | None = None
    status: str | None = None
    frontmatter: dict | None = None
    body: str | None = None  # フロントマターの終端の直後から文書の末尾までの元の本文（正規化前、改行の統一だけ済み）。
    statements: list[dict] = field(default_factory=list)
    counted: bool = False
    statement_count: int = 0
    warnings: list[Diagnostic] = field(default_factory=list)
    hard: list[Diagnostic] | None = None  # `None`でない＝この文書は`skip-document`
    duplicate: bool = False  # `True`＝IDの重複により`skip-document`（フェーズCの関係・パスの解決の索引から除く）
    #: 複合ワークスペースの他のメンバーの文書を作業ワークスペースの視点で修飾したビュー（`multirelate._qualified_relations_view`）が、
    #: 修飾する前の`relations.requires`の宣言どおりの綴りを保持する（診断の`evidence`は宣言どおりに返す）。ビューでなければ``None``。
    declared_requires: list[str] | None = None


@dataclass
class CatalogResult:
    entries: list[DocEntry] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)
    checked_document_count: int = 0
    checked_statement_count: int = 0
    #: 仕様文書のファイル数の上限を超えて操作を止めたか（`INPUT-LIMIT-SPEC-COUNT`、`stop-operation`）。
    stopped: bool = False


def _discover_top_level(spec_dir: str) -> list[str]:
    """`.spec/`直下の未知のエントリ名を返す（予約した`reports`・`journal`・`plans`は種別を問わず既知、探索しない）。

    シンボリックリンク（ファイル・ディレクトリとも）は予約したエントリ以外なら、名前が既知の種別と一致していても
    常に未知のエントリとする（ワークスペース・設定仕様 §1-5「シンボリックリンクをたどって、ワークスペースの外の
    仕様文書を読み込まない」）。たどらない・読まない。
    """

    unknown: list[str] = []
    try:
        entries = sorted(os.listdir(spec_dir))
    except OSError:
        return []
    for name in entries:
        if name in RESERVED_TOP_ENTRIES:
            continue
        full = os.path.join(spec_dir, name)
        if os.path.islink(full):
            unknown.append(name)
            continue
        if name not in KNOWN_TOP_ENTRIES:
            unknown.append(name)
    return unknown


def _discover_files(spec_dir: str, kind: str) -> tuple[list[str], list[str]]:
    """種別ディレクトリの配下を自前でたどり、``(md_paths, unknown_paths)``を返す。

    `os.walk`の既定の分類（`entry.is_dir()`はシンボリックリンクを追跡する）に頼らず、
    エントリごとに`os.path.islink`を判定してシンボリックリンクをたどらない（ワークスペース・設定仕様 §1-5）。
    `.md`以外のファイル（隠しファイル・一時ファイルを含む）とシンボリックリンクはすべて未知のエントリとして返す
    （ワークスペース・設定仕様 §3）。
    """

    sub_name = DOC_KIND_DIR[kind]
    sub = os.path.join(spec_dir, sub_name)
    md_rel: list[str] = []
    unknown_rel: list[str] = []
    if os.path.islink(sub) or not os.path.isdir(sub):
        return [], []

    def _walk(dir_abs: str, dir_rel: str) -> None:
        try:
            names = sorted(os.listdir(dir_abs))
        except OSError:
            return
        for name in names:
            full = os.path.join(dir_abs, name)
            rel = f"{dir_rel}/{name}" if dir_rel else name
            if os.path.islink(full):
                unknown_rel.append(rel)
                continue
            if os.path.isdir(full):
                _walk(full, rel)
            elif os.path.isfile(full):
                if name.endswith(".md"):
                    md_rel.append(rel)
                else:
                    unknown_rel.append(rel)

    _walk(sub, "")
    md_paths = sorted(f".spec/{sub_name}/{rel}" for rel in md_rel)
    unknown_paths = sorted(f".spec/{sub_name}/{rel}" for rel in unknown_rel)
    return md_paths, unknown_paths


def _read_bytes(abs_path: str) -> tuple[bytes | None, bool]:
    try:
        with open(abs_path, "rb") as f:
            return f.read(), True
    except OSError:
        return None, False


def _extract_frontmatter(text: str) -> tuple[str | None, str | None, int | None]:
    """``(frontmatter_raw, body, closing_line_index0)``を返す。フロントマターが見つからなければすべて``None``。"""

    if not text.startswith("---\n"):
        return None, None, None
    closing = text.find("\n---\n", 4)
    marker_length = 5
    if closing < 0 and text.endswith("\n---"):
        closing = len(text) - 4
        marker_length = 4
    if closing < 0:
        return None, None, None
    raw = text[4:closing]
    body = text[closing + marker_length :]
    closing_line = text.count("\n", 0, closing + 1)
    return raw, body, closing_line


def _frontmatter_bytes(fm_raw: str, closing_line: int | None) -> int:
    """フロントマターの大きさ（文書・フロントマター・状態仕様 §11）。

    改行を正規化した後の本文で、開始の区切りの行と終了の区切りの行の間にある各行を、その行の改行（1バイト）を含めて数えた
    UTF-8のバイト数の合計とする。区切りの行自身は含めない。間に行がなければ0バイトとする。``fm_raw``と``closing_line``は
    :func:`_extract_frontmatter`の戻り値で、``fm_raw``は間の行を改行でつないだもの（最後の行の改行を含まない）、
    ``closing_line``は終了の区切りの行の0始まりの行番号（開始の区切りの行は0行目なので、間の行の数は``closing_line - 1``）。
    """

    if closing_line is None or closing_line <= 1:
        return 0
    return len(fm_raw.encode("utf-8")) + 1


_TOP_KEY_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*):")


def _enclosing_key(fm_raw: str, line0: int | None) -> str | None:
    """構文が壊れた位置（0始まりの行番号）から、直前の直下のキーを、保証せず可能な範囲で推定する。"""

    if line0 is None:
        return None
    lines = fm_raw.split("\n")
    start = min(line0, len(lines) - 1)
    for i in range(start, -1, -1):
        m = _TOP_KEY_RE.match(lines[i])
        if m:
            return m.group(1)
    return None


def _issue_to_diag(issue: fm_mod.FieldIssue, path: str, workspace_id: str) -> Diagnostic:
    return _mk(issue.code, issue.severity, issue.status, issue.summary, path, workspace_id, key=issue.key)


def _build_h2_index(lines: list[str], body_start: int, normal_lines: set[int]) -> list[tuple[int, str]]:
    """(1始まりの行番号, 節の名前)のリストを行番号の昇順で返す。

    フェンス内・4つのSPの字下げの内側・引用ブロックの直後にある``## ``様の行は、走査器（§5）と同じ規則で
    除外し、見出しとして数えない（走査器と同じ文脈の除外規則を共有する）。
    """

    result = []
    for i in range(body_start, len(lines)):
        line_no = i + 1
        if line_no not in normal_lines:
            continue
        m = _H2_RE.match(lines[i])
        if m:
            result.append((line_no, m.group(1).strip()))
    return result


def _section_for_line(h2_index: list[tuple[int, str]], line_no: int) -> str | None:
    current = None
    for h2_line, name in h2_index:
        if h2_line <= line_no:
            current = name
        else:
            break
    return current


def _check_h1(
    lines: list[str],
    body_start: int,
    doc_id: str,
    title: str,
    path: str,
    workspace_id: str,
    normal_lines: set[int],
) -> Diagnostic | None:
    candidates = [
        (i + 1, m.group(1))
        for i in range(body_start, len(lines))
        if (i + 1) in normal_lines and (m := _H1_RE.match(lines[i]))
    ]
    first_nonblank = None
    for i in range(body_start, len(lines)):
        if lines[i].strip() != "":
            first_nonblank = i + 1
            break
    if not candidates:
        line = first_nonblank or (body_start + 1)
        return _mk("SPEC-STYLE-H1-001", "error", "failed", messages.H1_MISSING, path, workspace_id, line=line, column=1)
    if len(candidates) > 1:
        line, _content = candidates[0]
        return _mk("SPEC-STYLE-H1-001", "error", "failed", messages.H1_MULTIPLE, path, workspace_id, line=line, column=1)
    line, content = candidates[0]
    expected = f"{doc_id} {title}"
    if line != first_nonblank or content != expected:
        return _mk("SPEC-STYLE-H1-001", "error", "failed", messages.H1_MISMATCH, path, workspace_id, line=line, column=1)
    return None


def _check_sections(h2_index: list[tuple[int, str]], lines: list[str], path: str, workspace_id: str) -> list[Diagnostic]:
    diags: list[Diagnostic] = []
    by_name = {name: h2_line for h2_line, name in h2_index}
    ordered_lines = sorted(h2_line for h2_line, _ in h2_index)
    for name in REQUIRED_REQ_SECTIONS:
        if name not in by_name:
            diags.append(
                _mk("SPEC-STYLE-SECTION-001", "error", "failed", messages.section_missing(name), path, workspace_id)
            )
            continue
        start = by_name[name]
        later = [l for l in ordered_lines if l > start]
        end = later[0] if later else len(lines) + 1
        body_lines = lines[start:end - 1]
        if all(line.strip() == "" for line in body_lines):
            diags.append(
                _mk("SPEC-STYLE-SECTION-001", "error", "failed", messages.section_empty(name), path, workspace_id)
            )
    return diags


def _process_document(
    spec_dir: str, path: str, kind: str, workspace_id: str, limits: limits_mod.Limits = limits_mod.ABSOLUTE
) -> DocEntry:
    abs_path = os.path.join(spec_dir, path[len(".spec/") :])

    raw, ok = _read_bytes(abs_path)
    if not ok:
        entry = DocEntry(path=path, kind=kind)
        entry.hard = [_mk("SPEC-INPUT-READ-001", "error", "error", messages.SPEC_IO_UNREADABLE, path, workspace_id)]
        return entry
    return _process_document_content(raw, path, kind, workspace_id, limits)


def _process_document_content(
    raw: bytes,
    path: str,
    kind: str,
    workspace_id: str,
    limits: limits_mod.Limits = limits_mod.ABSOLUTE,
    *,
    identity_only: bool = False,
) -> DocEntry:
    """バイト列から:class:`DocEntry`を組み立てる（`_process_document`のファイルの読取り以降を共有する）。

    Gitの基準版の文書の解析（:func:`build_base_catalog`）でも同じ関数を使う（`02_check.md`の
    「基準版の文書の解析は現在版と同じフロントマター／構文解析器を使う」）。ファイルの読取り自体のI/Oエラー
    （`SPEC-INPUT-READ-001`）だけは呼び出し側（`_process_document`）の責務であり、ここには含めない。
    ``limits``はファイル単位の上限（`specBytes`、`frontmatterBytes`、`documentStatementCount`、`documentArrayItemCount`）を決める。
    ``identity_only``が真なら、IDと状態を確定した時点で返す（ファイル名とIDの一致、EARS-AIの構文、本文の検査をしない）。
    IDを読めるか（``doc_id``が``None``でないか）は、偽のときと同じに決まる。承認済み要求の保護の途中のコミットの版の読取りが使う。
    """

    entry = DocEntry(path=path, kind=kind)
    if len(raw) > limits.specBytes:
        entry.hard = [
            _mk(
                "SPEC-INPUT-LIMIT-001", "error", "failed",
                messages.spec_size_limit(limits_mod.format_bytes(limits, "specBytes", "1 MiB")), path, workspace_id,
            )
        ]
        return entry

    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
        entry.warnings.append(_mk("SPEC-INPUT-BOM-001", "warning", "passed_with_warnings", messages.SPEC_BOM, path, workspace_id))

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        entry.hard = [_mk("SPEC-INPUT-READ-001", "error", "failed", messages.SPEC_UTF8_INVALID, path, workspace_id)]
        return entry

    text = normalize_newlines(text)
    fm_raw, body, closing_idx = _extract_frontmatter(text)
    if fm_raw is None:
        entry.hard = [
            _mk("SPEC-FM-SCHEMA-001", "error", "failed", messages.frontmatter_yaml_syntax_invalid(), path, workspace_id)
        ]
        return entry

    if _frontmatter_bytes(fm_raw, closing_idx) > limits.frontmatterBytes:
        entry.hard = [
            _mk(
                "SPEC-INPUT-LIMIT-001", "error", "failed",
                messages.frontmatter_size_limit(limits_mod.format_bytes(limits, "frontmatterBytes", "32 KiB")),
                path, workspace_id,
            )
        ]
        return entry

    try:
        value = parse_yaml_subset(fm_raw, label=messages.FRONTMATTER_LABEL)
    except YamlSyntaxError as exc:
        key = _enclosing_key(fm_raw, exc.line)
        entry.hard = [
            _mk(
                "SPEC-FM-SCHEMA-001",
                "error",
                "failed",
                messages.frontmatter_yaml_syntax_invalid(),
                path,
                workspace_id,
                key=key,
            )
        ]
        return entry
    except YamlForbiddenError as exc:
        entry.hard = [_mk("SPEC-FM-SCHEMA-001", "error", "failed", exc.summary, path, workspace_id, key=exc.key)]
        return entry

    outcome = fm_mod.validate(value, kind, array_item_limit=limits.documentArrayItemCount)
    if outcome.hard:
        entry.hard = [_issue_to_diag(i, path, workspace_id) for i in outcome.hard]
        return entry

    entry.warnings.extend(_issue_to_diag(i, path, workspace_id) for i in outcome.soft)
    fm = outcome.value
    entry.frontmatter = fm
    entry.body = body
    entry.doc_id = fm["id"]
    entry.title = fm["title"]
    entry.status = fm["status"]
    if identity_only:
        return entry

    # --- ファイル名とフロントマターのIDの一致 -----------------------------------
    basename = os.path.basename(path)
    stem = basename[:-3] if basename.endswith(".md") else basename
    m = _FILE_ID_RE.match(stem)
    file_id = m.group(1) if m else None
    if file_id != entry.doc_id:
        entry.hard = [_mk("SPEC-FILE-NAME-001", "error", "failed", messages.FILE_NAME_MISMATCH, path, workspace_id, key="id")]
        return entry

    # --- EARS-AI構文 ------------------------------------------------------
    candidates = scan_candidates(text)
    if len(candidates) > limits.documentStatementCount:
        entry.hard = [
            _mk(
                "SPEC-INPUT-LIMIT-001", "error", "failed",
                messages.statement_count_limit(limits.documentStatementCount), path, workspace_id,
            )
        ]
        return entry

    is_draft = entry.status == "draft"
    parse_result = parse_document(text, path)
    lines = text.split("\n")
    normal_lines = normal_line_numbers(text)

    hard_ears: list[Diagnostic] = []
    for cond in parse_result.conditions:
        kind_c = cond["kind"]
        code, category = _EARS_TABLE[kind_c]
        summary = _EARS_SUMMARY[kind_c](cond.get("detail"))
        if category == "soft":
            entry.warnings.append(
                _mk(code, "warning", "passed_with_warnings", summary, path, workspace_id, line=cond["line"], column=cond["column"])
            )
        elif category == "hard-draft" and is_draft:
            entry.warnings.append(
                _mk(code, "warning", "passed_with_warnings", summary, path, workspace_id, line=cond["line"], column=cond["column"])
            )
        else:
            hard_ears.append(
                _mk(code, "error", "failed", summary, path, workspace_id, line=cond["line"], column=cond["column"])
            )

    # --- 規範文IDの文書ID整合（check.md §4「3」、レジストリの条件行`EAI-ID-DOCUMENT-MISMATCH`）。
    # 診断コードはID形式の不正と同じ`EAI-CORE-ID-001`だが、`summary`は専用の文言とする（`draft`でも`error`、
    # `skip-document`）。
    for stmt in parse_result.statements:
        if stmt["documentId"] != entry.doc_id:
            hard_ears.append(
                _mk(
                    "EAI-CORE-ID-001",
                    "error",
                    "failed",
                    messages.EAI_ID_DOCUMENT_MISMATCH,
                    path,
                    workspace_id,
                    line=stmt["source"]["line"],
                    column=stmt["source"]["column"],
                )
            )

    if hard_ears:
        entry.hard = hard_ears
        return entry

    # --- 配置の検査（`continue`、`skip-document`にしない） -------------------------
    body_start = closing_idx + 1
    h2_index = _build_h2_index(lines, body_start, normal_lines)
    allowed = ALLOWED_STATEMENT_SECTIONS[kind]
    valid_statements = []
    placement_diags: list[Diagnostic] = []
    for stmt in parse_result.statements:
        section = _section_for_line(h2_index, stmt["source"]["line"])
        if section in allowed:
            valid_statements.append(stmt)
        else:
            placement_diags.append(
                _mk(
                    "SPEC-STYLE-PLACEMENT-001",
                    "error",
                    "failed",
                    messages.placement_invalid(kind),
                    path,
                    workspace_id,
                    line=stmt["source"]["line"],
                    column=stmt["source"]["column"],
                )
            )

    if kind == "REQ" and entry.status == "approved" and not valid_statements:
        entry.hard = [_mk("SPEC-REQ-STATEMENT-001", "error", "failed", messages.REQ_STATEMENT_EMPTY, path, workspace_id)]
        return entry

    entry.statements = valid_statements
    entry.statement_count = len(valid_statements)
    entry.counted = True
    entry.warnings.extend(placement_diags)

    h1_diag = _check_h1(lines, body_start, entry.doc_id, entry.title, path, workspace_id, normal_lines)
    if h1_diag is not None:
        entry.warnings.append(h1_diag)
    if kind == "REQ":
        entry.warnings.extend(_check_sections(h2_index, lines, path, workspace_id))

    return entry


def duplicate_diagnostic(doc_id: str, first_path: str, workspace_id: str, *, qualify_summary_ids: bool = False) -> Diagnostic:
    """文書IDの重複の診断`SPEC-ID-DUPLICATE-001`を作る。発生元は重複した写しのうちパスの辞書順で最初のファイル（`key: id`）。

    複合ワークスペース内では、`summary`に差し込む文書IDを所有ワークスペースのIDで修飾する（複合ワークスペース仕様 §4、確認事項C69）。
    `check`の完全検査（:func:`build_catalog`）と、`context`・`verify`・`check`が閉包を作るときに辿るIDの重複を返す経路
    （:mod:`bitz.dupclosure`。関係・トレースモデル §5.1、確認事項C96）が同じ診断を返すための唯一の組み立て。
    """

    return _mk(
        "SPEC-ID-DUPLICATE-001", "error", "failed",
        messages.doc_id_duplicate(f"{workspace_id}::{doc_id}" if qualify_summary_ids else doc_id),
        first_path, workspace_id, key="id",
    )


def build_catalog(
    workspace_root: str,
    workspace_id: str,
    *,
    limits: limits_mod.Limits = limits_mod.ABSOLUTE,
    qualify_summary_ids: bool = False,
) -> CatalogResult:
    """ワークスペースの仕様文書の一覧を作り、各文書を検査する。

    ``limits``は、仕様文書のファイル数（`specFileCount`）とファイル単位の上限を決める（安全な入出力・互換性 §4.1）。
    単一ワークスペースは作業ワークスペースの設定、複合ワークスペースはルートワークスペースの設定から決めた値を渡す。
    """

    spec_file_count_limit = limits.specFileCount
    result = CatalogResult()
    spec_dir = os.path.join(workspace_root, ".spec")
    if not os.path.isdir(spec_dir):
        return result

    unknown_top = _discover_top_level(spec_dir)

    kind_files: dict[str, list[str]] = {}
    unknown_in_kinds: list[str] = []
    for kind in ("REQ", "TECH", "ADR", "TASK"):
        md_paths, unknown_paths = _discover_files(spec_dir, kind)
        kind_files[kind] = md_paths
        unknown_in_kinds.extend(unknown_paths)

    # --- 仕様文書のファイル数の上限（安全な入出力 §4、`INPUT-LIMIT-SPEC-COUNT`）。`stop-operation`のため
    # 文書を1件も読まず、他の診断（未知のエントリを含む）も返さず操作を止める。
    total_md = sum(len(paths) for paths in kind_files.values())
    if total_md > spec_file_count_limit:
        result.diagnostics = [
            _mk(
                "SPEC-INPUT-LIMIT-001",
                "error",
                "failed",
                messages.spec_file_count_limit(spec_file_count_limit),
                ".spec",
                workspace_id,
            )
        ]
        result.stopped = True
        return result

    for name in sorted(unknown_top):
        result.diagnostics.append(
            _mk(
                "SPEC-WORKSPACE-UNKNOWN-001",
                "warning",
                "passed_with_warnings",
                messages.WORKSPACE_UNKNOWN_ENTRY,
                ".spec/" + name,
                workspace_id,
            )
        )
    for rel_path in sorted(unknown_in_kinds):
        result.diagnostics.append(
            _mk(
                "SPEC-WORKSPACE-UNKNOWN-001",
                "warning",
                "passed_with_warnings",
                messages.WORKSPACE_UNKNOWN_ENTRY,
                rel_path,
                workspace_id,
            )
        )

    entries: list[DocEntry] = []
    for kind in ("REQ", "TECH", "ADR", "TASK"):
        for path in kind_files[kind]:
            entries.append(_process_document(spec_dir, path, kind, workspace_id, limits))

    # --- IDの一意性（ファイル名／フロントマターの段階を通過した文書だけを対象にする） --------
    by_id: dict[str, list[DocEntry]] = {}
    for e in entries:
        if e.hard is None and e.doc_id is not None:
            by_id.setdefault(e.doc_id, []).append(e)

    duplicate_entries: set[int] = set()
    for doc_id, group in by_id.items():
        if len(group) > 1:
            group_sorted = sorted(group, key=lambda e: e.path)
            for e in group_sorted:
                duplicate_entries.add(id(e))
                e.duplicate = True
            result.diagnostics.append(
                duplicate_diagnostic(doc_id, group_sorted[0].path, workspace_id, qualify_summary_ids=qualify_summary_ids)
            )

    for e in entries:
        if id(e) in duplicate_entries:
            # 重複した文書は件数に数えない（`skip-document`）が、それ以前に確定した警告
            # （BOM／`FM-UNKNOWN`／`UNAVAILABLE`／`EXT-UNKNOWN`など、`continue`継続単位）は残す。
            result.diagnostics.extend(e.warnings)
            continue
        if e.hard is not None:
            result.diagnostics.extend(e.warnings)
            result.diagnostics.extend(e.hard)
            continue
        result.diagnostics.extend(e.warnings)
        if e.counted:
            result.checked_document_count += 1
            result.checked_statement_count += e.statement_count

    result.entries = entries
    return result


def _kind_for_base_path(path: str) -> str | None:
    """ワークスペースのルートからの相対パス（``.spec/<dir>/...``）から仕様文書の種別を推定する。"""

    parts = path.split("/")
    if len(parts) < 2 or parts[0] != ".spec":
        return None
    return DIR_TO_KIND.get(parts[1])


def build_base_catalog(
    git_executable: str,
    cwd: str,
    env: dict[str, str],
    base_rev: str,
    workspace_root: str,
    workspace_id: str,
    limits: limits_mod.Limits = limits_mod.ABSOLUTE,
) -> dict[str, DocEntry]:
    """Gitの基準版``base_rev``の時点の文書の一覧を``doc_id -> DocEntry``で返す（`02_check.md §5・§9`）。

    ``limits``は現在版の設定から決めた上限で、基準版の文書にも同じファイル単位の上限を適用する（安全な入出力・互換性 §4.1）。

    現在版と同じ:func:`_process_document_content`を使う（`基準版の文書の解析は現在版と同じ
    フロントマター／構文解析器を使う`）。フロントマターが壊れている、ファイル名のIDと不一致、EARS-AI構文が壊れている
    など`skip-document`相当（``entry.hard is not None``）の基準版の文書は、推測で診断を作らず
    比較対象から静かに除く（状態遷移・承認済み要求の保護のいずれも、既に壊れていた基準版の文書との
    差分を機械的に断定できないため）。IDが重複しているときは、最初に見つかった（パス昇順の）文書だけを使う。

    仕様文書の一覧または内容をGitから読めない場合（部分クローンで欠けたオブジェクトなど。Gitは遅延取得をしない）は、
    :class:`bitz.gitutil.GitReadError`を送出する（`check` §5、ADR-082の決定2）。
    """

    from . import gitutil  # 遅延インポート（循環インポートを避ける）。

    blobs = gitutil.list_base_spec_blobs(git_executable, cwd, env, base_rev, workspace_root)
    if blobs is None:
        raise gitutil.GitReadError("基準版の仕様文書の一覧を読めません")
    result: dict[str, DocEntry] = {}
    spec_blobs = sorted(
        (path, oid) for path, oid in blobs if path.endswith(".md") and _kind_for_base_path(path) is not None
    )
    if not spec_blobs:
        return result
    with gitutil.BlobReader(git_executable, cwd, env) as reader:
        for path, oid in spec_blobs:
            kind = _kind_for_base_path(path)
            assert kind is not None
            # 読めない内容（欠けたオブジェクトなど）は、黙って除かず:class:`gitutil.GitReadError`にする（`check` §5、ADR-082の決定2）。
            # `specBytes`を超える内容は保持せずに読み捨てる（上限を超えた版は`skip-document`相当で、比較から除く）。
            obj_type, raw = reader.read_object(oid, max_bytes=limits.specBytes)
            if obj_type != "blob":
                raise gitutil.GitReadError("基準版の仕様文書の内容を読めません")
            if raw is None:
                continue
            entry = _process_document_content(raw, path, kind, workspace_id, limits)
            if entry.hard is not None or entry.duplicate:
                continue
            if entry.doc_id is None or entry.doc_id in result:
                continue
            result[entry.doc_id] = entry
    return result
