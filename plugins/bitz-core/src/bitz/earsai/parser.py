"""EARS-AI構文解析器（EARS-AI言語・意味中間表現仕様 §3・§4・§7）。

走査器（scanner.py）が返した各候補行へ、字句解析器の基本部品（lexer.py）を適用して
規範文の文法（§3 EBNF）を検証し、意味中間表現（ir.py）または構文の条件を返す。

- 同一の元の原因からは1件の条件だけを返す。各規範文の構文検証は最初に破綻した
  条件で即座に`return`するため（早期に`return`する方式）、複数の破綻の候補が同じ位置に重なる場合
  （例: 未閉鎖のコードスパンの結果として未閉鎖のタグにもなる）でも、自然に先に検出した方だけを
  返す。検出順は§4末尾の`priority`の順（未閉鎖のコードスパン→未閉鎖／不正なタグ→ID形式→タグの順序→
  必須のタグの不足→発動条件が複数→句点の欠落→オペランドの不足）と一致させてある。
- `SHOULD`の理由がない場合と、未知の名前空間の拡張タグは、意味中間表現を返したうえで条件も返す（統語的には
  妥当なため）。
- `draft`の差分による重大度の決定はフェーズBへ委ねる。本モジュールは`ir.CONDITION_*`の種類（`kind`）だけを返す。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import ir as ir_mod
from . import lexer
from .lexer import LexError
from .scanner import scan_candidates


@dataclass
class ParseResult:
    """1文書の解析結果。`statements`は§6の意味中間表現の辞書の配列、文書順（行、列、ID順）。"""

    statements: list[dict] = field(default_factory=list)
    conditions: list[dict] = field(default_factory=list)


def _looks_like_core_tag(content: str) -> bool:
    """角括弧の内容がCoreのタグのキーワード（ACTORの`ACTOR:`の接頭辞の形も含む）に見えるか。"""

    if content in lexer.CORE_TAG_KEYWORDS:
        return True
    head = content.split(":", 1)[0]
    return head in lexer.CORE_TAG_KEYWORDS


def _is_valid_quoted_value(value: str) -> bool:
    """`"`で始まり`"`で終わり、内部が`qchar`または既知のエスケープだけの`quoted-value`か。"""

    if len(value) < 2 or value[0] != '"' or value[-1] != '"':
        return False
    inner = value[1:-1]
    i = 0
    n = len(inner)
    while i < n:
        ch = inner[i]
        if ch == "\\":
            if i + 1 < n and inner[i + 1] in lexer.ESCAPABLE:
                i += 2
                continue
            return False
        if ch == '"':
            # 未エスケープのDQUOTEは値の終端を意味するため、`inner`に現れてはならない。
            return False
        i += 1
    return True


def _is_valid_extension_value(value: str) -> bool:
    """拡張タグの値が`bare-value`または`quoted-value`として妥当か（§3）。"""

    if value.startswith('"'):
        return _is_valid_quoted_value(value)
    return bool(lexer.BARE_VALUE_RE.fullmatch(value))


def _is_valid_extension(content: str) -> bool:
    match = lexer.EXTENSION_RE.match(content)
    if not match:
        return False
    value = match.group("value")
    return value is None or _is_valid_extension_value(value)


def _scan_top_level_brackets(line: str, start: int) -> list[tuple[str, int]]:
    """`start`から行末まで、コードスパンの外の妥当なタグの角括弧を出現順に列挙する（保証せず、可能な範囲で行う）。

    不正なエスケープや未閉鎖のコードスパン／タグに出会った時点で、それ以降は判定できないため打ち切る
    （後方に期待するタグが「存在する」ことの検出だけが目的であり、網羅的な妥当性検証ではない）。
    """

    results: list[tuple[str, int]] = []
    i = start
    n = len(line)
    while i < n:
        ch = line[i]
        if ch == "\\":
            if i + 1 < n and line[i + 1] in lexer.ESCAPABLE:
                i += 2
                continue
            break
        if ch == "`":
            try:
                _content, end = lexer._read_code_span(line, i)  # noqa: SLF001 (同一package内)
            except LexError:
                break
            i = end
            continue
        if ch == "[":
            try:
                content, end = lexer.read_bracket(line, i)
            except LexError:
                break
            results.append((content, i))
            i = end
            continue
        i += 1
    return results


def _search_later(line: str, start: int, predicate) -> bool:
    return any(predicate(content) for content, _ in _scan_top_level_brackets(line, start))


def _classify_wrong_slot(content: str, line: str, search_from: int, predicate) -> str:
    """期待する位置に現れなかった角括弧を分類する（作業依頼2026-09 #4）。

    - Coreのタグでも妥当な拡張タグでもない → 不正なタグ（EAI-CORE-SYNTAX-004）。
    - Coreのタグまたは拡張タグだが期待する位置と違う → 同じ行の後方（コードスパンの外）に期待する位置の
      タグが実在すれば順序違い（タグの順序の不正）、実在しなければ必須のタグの不足。
    """

    if not _looks_like_core_tag(content) and not _is_valid_extension(content):
        return ir_mod.CONDITION_TAG_UNCLOSED
    if _search_later(line, search_from, predicate):
        return ir_mod.CONDITION_TAG_ORDER
    return ir_mod.CONDITION_TAG_REQUIRED


def _actor_predicate(content: str) -> bool:
    return content == "ACTOR" or content.startswith("ACTOR:")


def _activation_predicate(content: str) -> bool:
    return content in lexer.ACTIVATION_KEYWORDS


def _modality_predicate(content: str) -> bool:
    return content in lexer.MODALITY_KEYWORDS


def _operation_predicate(content: str) -> bool:
    return content in lexer.OPERATION_KEYWORDS


class _StatementBreak(Exception):
    """1つの候補行の構文解析を打ち切り、単一の条件を返すための内部例外。

    `detail`は`CONDITION_TAG_UNCLOSED`の原因の種類（"escape"／"quote"／"unclosed"／"invalid"）を
    呼び出し側（document.py）が文面の選択に使うための、保証せず可能な範囲で与える補助情報。他の種類（`kind`）では常に`None`。
    """

    def __init__(self, kind: str, column: int, *, detail: str | None = None) -> None:
        super().__init__(kind)
        self.kind = kind
        self.column = column
        self.detail = detail


def _bracket(line: str, pos: int) -> tuple[str, int]:
    try:
        return lexer.read_bracket(line, pos)
    except LexError as error:
        raise _StatementBreak(error.condition, error.offset + 1, detail=error.detail) from error


def _wrong_slot_break(content: str, line: str, search_from: int, predicate, column: int) -> "_StatementBreak":
    """`_classify_wrong_slot`の結果を、種類（`kind`）に応じた`detail`付きの`_StatementBreak`へ包む。"""

    kind = _classify_wrong_slot(content, line, search_from, predicate)
    detail = "invalid" if kind == ir_mod.CONDITION_TAG_UNCLOSED else None
    return _StatementBreak(kind, column, detail=detail)


def _require_tag(line: str, pos: int, predicate) -> tuple[str, int]:
    """`pos`の位置に、期待する位置のタグがあることを要求する。

    `pos`に角括弧があっても`predicate`を満たさない場合、または`pos`に角括弧が無い場合は、
    行の後方の探索の結果に応じて、タグの順序の不正／必須のタグの不足を送出する。位置は常に`pos`
    （期待する位置のまま）とする。
    """

    if pos < len(line) and line[pos] == "[":
        content, next_pos = _bracket(line, pos)
        if predicate(content):
            return content, next_pos
        raise _wrong_slot_break(content, line, next_pos, predicate, pos + 1)
    if _search_later(line, pos, predicate):
        raise _StatementBreak(ir_mod.CONDITION_TAG_ORDER, pos + 1)
    raise _StatementBreak(ir_mod.CONDITION_TAG_REQUIRED, pos + 1)


def _parse_statement_pieces(line: str, id_column: int) -> tuple[dict, list[dict], list[int]]:
    """1つの候補行を解析する。破綻時は`_StatementBreak`を送出する。

    戻り値は(意味中間表現の構成要素の辞書, 警告を伴う条件の(`kind`, `column`)のリスト用の元のデータ, 未使用)。
    実際には警告を伴う条件の`kind`と`column`の組をタプルで返すため、下で組み立て直す。
    """

    pos0 = id_column - 1

    id_content, pos = _bracket(line, pos0)
    if not lexer.STATEMENT_ID_RE.match(id_content):
        raise _StatementBreak(ir_mod.CONDITION_ID_FORMAT, pos0 + 1)
    document_id, local_id = id_content.split(":", 1)
    statement_id = id_content

    if pos >= len(line) or line[pos] != " ":
        raise _StatementBreak(ir_mod.CONDITION_TAG_REQUIRED, pos0 + 1)
    pos += 1

    extensions: list[dict] = []
    extension_positions: list[int] = []
    while pos < len(line) and line[pos] == "[":
        tag_pos = pos
        content, next_pos = _bracket(line, pos)
        if _actor_predicate(content):
            break
        match = lexer.EXTENSION_RE.match(content)
        if not match:
            raise _wrong_slot_break(content, line, next_pos, _actor_predicate, tag_pos + 1)
        value = match.group("value")
        if value is not None and not _is_valid_extension_value(value):
            raise _StatementBreak(ir_mod.CONDITION_TAG_UNCLOSED, tag_pos + 1, detail="invalid")
        if value is not None and value.startswith('"'):
            value = lexer.decode_escapes(value[1:-1])
        extensions.append({"namespace": match.group("ns"), "term": match.group("term"), "value": value})
        extension_positions.append(tag_pos + 1)
        if next_pos >= len(line) or line[next_pos] != " ":
            raise _StatementBreak(ir_mod.CONDITION_TAG_REQUIRED, tag_pos + 1)
        pos = next_pos + 1

    actor_tag_pos = pos
    content, next_pos = _require_tag(line, pos, _actor_predicate)
    if content in ("ACTOR", "ACTOR:"):
        raise _StatementBreak(ir_mod.CONDITION_OPERAND_MISSING, actor_tag_pos + 1)
    actor = content[len("ACTOR:"):]
    if not lexer.ACTOR_ID_RE.match(actor):
        raise _StatementBreak(ir_mod.CONDITION_TAG_UNCLOSED, actor_tag_pos + 1, detail="invalid")
    if next_pos >= len(line) or line[next_pos] != " ":
        raise _StatementBreak(ir_mod.CONDITION_TAG_REQUIRED, actor_tag_pos + 1)
    pos = next_pos + 1

    activation_tag_pos = pos
    content, next_pos = _require_tag(line, pos, _activation_predicate)
    if content == "ALWAYS":
        activation: dict = {"kind": "ALWAYS"}
        if next_pos >= len(line) or line[next_pos] != " ":
            raise _StatementBreak(ir_mod.CONDITION_TAG_REQUIRED, activation_tag_pos + 1)
        pos = next_pos + 1
    else:  # WHEN/WHILE/WHERE/IF_ERROR
        if next_pos >= len(line) or line[next_pos] != " ":
            raise _StatementBreak(ir_mod.CONDITION_OPERAND_MISSING, activation_tag_pos + 1)
        try:
            raw_text, text_end = lexer.scan_text_until_bracket(line, next_pos + 1)
        except LexError as error:
            raise _StatementBreak(error.condition, error.offset + 1, detail=error.detail) from error
        text = lexer.normalize_text(raw_text)
        if not text:
            raise _StatementBreak(ir_mod.CONDITION_OPERAND_MISSING, activation_tag_pos + 1)
        activation = {"kind": content, "text": text}
        pos = text_end

    modality_tag_pos = pos
    if pos < len(line) and line[pos] == "[":
        peek_content, _peek_next = _bracket(line, pos)
        if peek_content in lexer.ACTIVATION_KEYWORDS:
            # 発動条件が2個目出現した（1文は1つの発動条件を持つ、§2.3）。
            raise _StatementBreak(ir_mod.CONDITION_TRIGGER_MULTIPLE, modality_tag_pos + 1)
    content, next_pos = _require_tag(line, pos, _modality_predicate)
    modality = content
    if next_pos >= len(line) or line[next_pos] != " ":
        raise _StatementBreak(ir_mod.CONDITION_TAG_REQUIRED, modality_tag_pos + 1)
    pos = next_pos + 1

    reason: str | None = None
    should_reason_missing = False
    if pos < len(line) and line[pos] == "[":
        peek_pos = pos
        peek_content, peek_next = _bracket(line, peek_pos)
        if peek_content == "REASON":
            if modality != "SHOULD":
                # §7: `MUST`または`MAY`の直後の`[REASON]`はタグの順序の不正とする。
                raise _StatementBreak(ir_mod.CONDITION_TAG_ORDER, peek_pos + 1)
            if peek_next >= len(line) or line[peek_next] != " ":
                raise _StatementBreak(ir_mod.CONDITION_OPERAND_MISSING, peek_pos + 1)
            try:
                raw_reason, reason_end = lexer.scan_text_until_bracket(line, peek_next + 1)
            except LexError as error:
                raise _StatementBreak(error.condition, error.offset + 1, detail=error.detail) from error
            reason_text = lexer.normalize_text(raw_reason)
            if not reason_text:
                raise _StatementBreak(ir_mod.CONDITION_OPERAND_MISSING, peek_pos + 1)
            reason = reason_text
            pos = reason_end
    if modality == "SHOULD" and reason is None:
        should_reason_missing = True

    operation_tag_pos = pos
    content, next_pos = _require_tag(line, pos, _operation_predicate)
    operation_kind = content
    if next_pos >= len(line) or line[next_pos] != " ":
        raise _StatementBreak(ir_mod.CONDITION_OPERAND_MISSING, operation_tag_pos + 1)
    try:
        op_text, period, trailing_bracket_pos = lexer.scan_operation_text(line, next_pos + 1)
    except LexError as error:
        raise _StatementBreak(error.condition, error.offset + 1, detail=error.detail) from error
    if trailing_bracket_pos is not None:
        # `operation`の後にタグは許されない（§3の特例、§4.3の未エスケープの`[`による終端の規則）。
        # 閉じなければ不正なタグ、閉じてCoreのタグのキーワードなら順序の不正、それ以外は不正なタグ。
        try:
            trailing_content, _end = lexer.read_bracket(line, trailing_bracket_pos)
        except LexError as error:
            raise _StatementBreak(ir_mod.CONDITION_TAG_UNCLOSED, trailing_bracket_pos + 1, detail=error.detail) from None
        if _looks_like_core_tag(trailing_content):
            raise _StatementBreak(ir_mod.CONDITION_TAG_ORDER, trailing_bracket_pos + 1)
        raise _StatementBreak(ir_mod.CONDITION_TAG_UNCLOSED, trailing_bracket_pos + 1, detail="invalid")
    if period is None:
        raise _StatementBreak(ir_mod.CONDITION_PERIOD_MISSING, len(line) + 1)
    if not op_text:
        raise _StatementBreak(ir_mod.CONDITION_OPERAND_MISSING, operation_tag_pos + 1)
    operation = {"kind": operation_kind, "text": op_text}

    soft_conditions: list[dict] = []
    if should_reason_missing:
        soft_conditions.append(ir_mod.condition(ir_mod.CONDITION_SHOULD_REASON_MISSING, 0, modality_tag_pos + 1))
    for ext_pos in extension_positions:
        soft_conditions.append(ir_mod.condition(ir_mod.CONDITION_EXTENSION_UNKNOWN, 0, ext_pos))

    pieces = {
        "statement_id": statement_id,
        "document_id": document_id,
        "local_id": local_id,
        "actor": actor,
        "activation": activation,
        "modality": modality,
        "reason": reason,
        "operation": operation,
        "extensions": extensions,
    }
    return pieces, soft_conditions, []


def parse_statement(line: str, line_number: int, id_column: int) -> tuple[dict | None, list[dict]]:
    """1つの候補行を解析する。

    成功時は`(意味中間表現の構成要素の辞書, 警告を伴う条件のリスト)`。この辞書は
    `ir.build_semantic_ir`が要求するキーのうち`path`・`line`・`column`・`raw`を除いたものを持つ。
    構文が破綻した場合は`(None, [condition])`（条件は1件だけ）を返す。
    """

    try:
        pieces, soft_conditions, _ = _parse_statement_pieces(line, id_column)
    except _StatementBreak as brk:
        return None, [ir_mod.condition(brk.kind, line_number, brk.column, detail=brk.detail)]
    for cond in soft_conditions:
        cond["line"] = line_number
    return pieces, soft_conditions


def parse_document(text: str, path: str) -> ParseResult:
    """1文書のテキスト（フロントマターを含む元のファイル全体）を解析する。

    行番号・列は、元のファイルを基準にした、Unicodeのコードポイント単位で1始まりとする。改行はLFへ正規化する。
    規範文IDの文書内の重複は`ir.CONDITION_ID_DUPLICATE`として、2回目以降の出現ごとに返す
    （ワークスペースをまたぐIDの一意性検査はフェーズBの責務）。
    """

    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.split("\n")
    candidates = scan_candidates(normalized)

    result = ParseResult()
    seen_ids: set[str] = set()

    for candidate in candidates:
        line_text = lines[candidate.line - 1]
        pieces, conditions = parse_statement(line_text, candidate.line, candidate.column)
        if pieces is None:
            result.conditions.extend(conditions)
            continue

        statement_id = pieces["statement_id"]
        ir = ir_mod.build_semantic_ir(
            statement_id=statement_id,
            document_id=pieces["document_id"],
            local_id=pieces["local_id"],
            path=path,
            line=candidate.line,
            column=candidate.column,
            actor=pieces["actor"],
            activation=pieces["activation"],
            modality=pieces["modality"],
            reason=pieces["reason"],
            operation=pieces["operation"],
            extensions=pieces["extensions"],
            raw=candidate.raw,
        )
        result.statements.append(ir)
        result.conditions.extend(conditions)

        if statement_id in seen_ids:
            result.conditions.append(
                ir_mod.condition(ir_mod.CONDITION_ID_DUPLICATE, candidate.line, candidate.column)
            )
        else:
            seen_ids.add(statement_id)

    return result
