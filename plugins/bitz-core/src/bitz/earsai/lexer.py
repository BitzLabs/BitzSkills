"""行内字句規則（EARS-AI仕様 §3・§4）の低水準primitive。

1候補行を左から右へ1回走査し、tag bracket・code span・escapeを読み取る。位置は
すべてUnicode code point単位0始まりのoffsetとし、呼び出し側（parser.py）が
Diagnostic向けに1始まりcolumnへ変換する。TAB・結合文字・全角文字もPython `str`の
code point index がそのまま1 columnとして扱えるため、特別な補正を要しない。
"""

from __future__ import annotations

import re

from . import ir as ir_mod

#: text-atomのescapeが許す5文字（§3 escaped）。
ESCAPABLE = "[]\\`\""

ACTIVATION_TEXT_KEYWORDS = ("WHEN", "WHILE", "WHERE", "IF_ERROR")
ACTIVATION_KEYWORDS = ("ALWAYS",) + ACTIVATION_TEXT_KEYWORDS
MODALITY_KEYWORDS = ("MUST", "SHOULD", "MAY")
OPERATION_KEYWORDS = ("THEN", "GENERATE", "CONSTRAINT")
CORE_TAG_KEYWORDS = ("ACTOR",) + ACTIVATION_KEYWORDS + MODALITY_KEYWORDS + ("REASON",) + OPERATION_KEYWORDS

STATEMENT_ID_RE = re.compile(r"^(REQ|TECH|ADR|TASK)-[0-9]{3,}:[A-Za-z0-9][A-Za-z0-9-]*$")
ACTOR_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")
EXTENSION_RE = re.compile(r"^(?P<ns>[a-z][a-z0-9]*):(?P<term>[A-Z][A-Z0-9_]*)(?:=(?P<value>.*))?$")
#: bare-value = bare-char, { bare-char } ; bare-char = alnum | "-" | "_" | "." （§3）。
BARE_VALUE_RE = re.compile(r"^[A-Za-z0-9_.-]+$")

_SP_TAB_RUN_RE = re.compile(r"[ \t]+")


class LexError(Exception):
    """字句規則違反。`condition` はir.pyの`CONDITION_*`、`offset`は0始まりcode point offset。

    `detail`は`CONDITION_TAG_UNCLOSED`の原因種別（"escape"／"quote"／"unclosed"）を
    呼び出し側（parser.py）がDiagnostic文面選択に使うためのbest-effort補助情報。
    他のconditionでは常にNone。
    """

    def __init__(self, condition: str, offset: int, detail: str | None = None) -> None:
        super().__init__(condition)
        self.condition = condition
        self.offset = offset
        self.detail = detail


def normalize_text(value: str) -> str:
    """§4.6 SP／TAB正規化。前後を除去し内部の連続SP／TABを1個のSPへ畳む。"""

    stripped = value.strip(" \t")
    return _SP_TAB_RUN_RE.sub(" ", stripped)


def decode_escapes(value: str) -> str:
    """既知escapeだけを解除する（`read_bracket`が既に妥当性を検証済みの文字列に使う）。"""

    out: list[str] = []
    i = 0
    n = len(value)
    while i < n:
        if value[i] == "\\" and i + 1 < n and value[i + 1] in ESCAPABLE:
            out.append(value[i + 1])
            i += 2
        else:
            out.append(value[i])
            i += 1
    return "".join(out)


def read_bracket(line: str, pos: int) -> tuple[str, int]:
    """`pos`の`[`から対応する`]`まで読み取り、(内容, `]`直後のoffset)を返す。

    DQUOTE区間は`]`をqcharとして無視し（extensionのquoted value）、5種類の既知escapeは
    2文字をまとめて消費する。§4.3「code span外の未escape`[`で直前textを終了する」はtag
    bracket内容にも及ぶため、quote外で未escapeの`[`に出会った時点でも即座に破綻とする
    （その内側を次のtagの開始とみなし、これ以上`pos`のbracketを探索しない）。
    閉じられない場合、不正escapeの場合、quoted valueが閉じない場合、内側に未escapeの`[`が
    現れた場合は、いずれも`EAI-CORE-SYNTAX-004`相当として、最初に開いた`[`（`pos`）の位置で
    `CONDITION_TAG_UNCLOSED`のLexErrorを送出する（Diagnostic registry §4: 不正escape・
    未閉鎖quoted value・不正／未閉鎖tagは同一conditionId）。
    """

    assert line[pos] == "["
    i = pos + 1
    n = len(line)
    in_quote = False
    quote_start = -1
    while i < n:
        ch = line[i]
        if ch == "\\":
            if i + 1 < n and line[i + 1] in ESCAPABLE:
                i += 2
                continue
            raise LexError(ir_mod.CONDITION_TAG_UNCLOSED, i, detail="escape")
        if ch == '"':
            if in_quote:
                in_quote = False
            else:
                in_quote = True
                quote_start = i
            i += 1
            continue
        if not in_quote and ch == "[":
            raise LexError(ir_mod.CONDITION_TAG_UNCLOSED, pos, detail="unclosed")
        if not in_quote and ch == "]":
            return line[pos + 1:i], i + 1
        i += 1
    if in_quote:
        raise LexError(ir_mod.CONDITION_TAG_UNCLOSED, quote_start, detail="quote")
    raise LexError(ir_mod.CONDITION_TAG_UNCLOSED, pos, detail="unclosed")


def _read_code_span(line: str, start: int) -> tuple[str, int]:
    """`start`のbacktick runから、同じrun長で閉じる最初のrunまでを読む(§3 code-span)。

    (span内容, 終了runの直後offset)を返す。閉じられなければ`CONDITION_CODE_UNCLOSED`を送出する。
    """

    n = len(line)
    j = start
    while j < n and line[j] == "`":
        j += 1
    width = j - start
    k = j
    while k < n:
        if line[k] != "`":
            k += 1
            continue
        run_start = k
        while k < n and line[k] == "`":
            k += 1
        if k - run_start == width:
            return line[j:run_start], k
    raise LexError(ir_mod.CONDITION_CODE_UNCLOSED, start)


def scan_text_until_bracket(line: str, pos: int) -> tuple[str, int]:
    """activation／reasonのtext。次の未escape・非code-span`[`まで読み、(生text, `[`のoffset)を返す。

    §4.6の正規化は呼び出し側がconcat後に適用する。行末まで`[`が現れない場合は、期待した
    次tagが存在しないことを表す`CONDITION_TAG_REQUIRED`を送出する。
    """

    out: list[str] = []
    i = pos
    n = len(line)
    while i < n:
        ch = line[i]
        if ch == "\\":
            if i + 1 < n and line[i + 1] in ESCAPABLE:
                out.append(line[i + 1])
                i += 2
                continue
            raise LexError(ir_mod.CONDITION_TAG_UNCLOSED, i, detail="escape")
        if ch == "`":
            content, end = _read_code_span(line, i)
            out.append(content)
            i = end
            continue
        if ch == "[":
            return "".join(out), i
        out.append(ch)
        i += 1
    raise LexError(ir_mod.CONDITION_TAG_REQUIRED, pos)


def scan_operation_text(line: str, pos: int) -> tuple[str | None, str | None, int | None]:
    """operationのtext＋period（§3特例）。

    §4.3「code span外の未escape`[`で直前textを終了する」はoperationのtextにも適用する。
    未escapeかつcode span外の`[`に出会ったら、そこでtext走査を終了し`(None, None, その`[`のoffset)`
    を返す。呼び出し側は、operationの後には次tagが存在しないことを踏まえてそのbracketを
    分類する（閉じなければ不正tag、閉じてCore tag keywordならtag順序不正、それ以外は不正tag。
    2026-09作業依頼#1）。

    `[`に出会わずにEOLへ達した場合は、code span外にある行末直前の最後の`.`または`。`だけを
    periodとみなし、それ以前をtext（正規化後）とする。該当する終端periodがなければ
    `(None, None, None)`を返し、呼び出し側が句点欠落として扱う。
    """

    n = len(line)
    atoms: list[tuple[str, int, int, str]] = []  # (kind, start, end, decoded)
    i = pos
    while i < n:
        ch = line[i]
        if ch == "\\":
            if i + 1 < n and line[i + 1] in ESCAPABLE:
                atoms.append(("char", i, i + 2, line[i + 1]))
                i += 2
                continue
            raise LexError(ir_mod.CONDITION_TAG_UNCLOSED, i, detail="escape")
        if ch == "`":
            start = i
            content, end = _read_code_span(line, i)
            atoms.append(("code", start, end, content))
            i = end
            continue
        if ch == "[":
            return None, None, i
        atoms.append(("char", i, i + 1, ch))
        i += 1

    if not atoms:
        return None, None, None
    last_kind, last_start, last_end, last_decoded = atoms[-1]
    if last_kind == "char" and (last_end - last_start) == 1 and last_decoded in (".", "。"):
        body = atoms[:-1]
        period = last_decoded
    else:
        return None, None, None
    text = normalize_text("".join(atom[3] for atom in body))
    return text, period, None
