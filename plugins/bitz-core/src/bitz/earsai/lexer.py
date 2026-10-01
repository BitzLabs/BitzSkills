"""行内の字句規則（EARS-AI言語・意味中間表現仕様 §3・§4）の低水準の基本部品。

1つの候補行を左から右へ1回走査し、タグの角括弧・コードスパン・エスケープを読み取る。位置は
すべてUnicodeのコードポイント単位で0始まりのオフセットとし、呼び出し側（parser.py）が
診断向けに1始まりの列へ変換する。TAB・結合文字・全角文字もPythonの`str`の
コードポイントのインデックスがそのまま1列として扱えるため、特別な補正を要しない。
"""

from __future__ import annotations

import re

from . import ir as ir_mod

#: `text-atom`のエスケープが許す5文字（§3 `escaped`）。
ESCAPABLE = "[]\\`\""

ACTIVATION_TEXT_KEYWORDS = ("WHEN", "WHILE", "WHERE", "IF_ERROR")
ACTIVATION_KEYWORDS = ("ALWAYS",) + ACTIVATION_TEXT_KEYWORDS
MODALITY_KEYWORDS = ("MUST", "SHOULD", "MAY")
OPERATION_KEYWORDS = ("THEN", "GENERATE", "CONSTRAINT")
CORE_TAG_KEYWORDS = ("ACTOR",) + ACTIVATION_KEYWORDS + MODALITY_KEYWORDS + ("REASON",) + OPERATION_KEYWORDS

#: local-id = upper, { upper | digit | "-" }, "-", digit, digit, { digit } （ADR-054、EARS-AI言語・意味中間表現仕様 §2.1）。
STATEMENT_ID_RE = re.compile(r"^(REQ|TECH|ADR|TASK)-[0-9]{3,}:[A-Z][A-Z0-9-]*-[0-9]{2,}$")
ACTOR_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")
EXTENSION_RE = re.compile(r"^(?P<ns>[a-z][a-z0-9]*):(?P<term>[A-Z][A-Z0-9_]*)(?:=(?P<value>.*))?$")
#: bare-value = bare-char, { bare-char } ; bare-char = alnum | "-" | "_" | "." （§3）。
BARE_VALUE_RE = re.compile(r"^[A-Za-z0-9_.-]+$")

_SP_TAB_RUN_RE = re.compile(r"[ \t]+")


class LexError(Exception):
    """字句規則の違反。`condition` は`ir.py`の`CONDITION_*`、`offset`は0始まりのコードポイントのオフセット。

    `detail`は`CONDITION_TAG_UNCLOSED`の原因の種類（"escape"／"quote"／"unclosed"）を
    呼び出し側（parser.py）が診断の文面の選択に使うための、保証せず可能な範囲で与える補助情報。
    他の条件では常に`None`。
    """

    def __init__(self, condition: str, offset: int, detail: str | None = None) -> None:
        super().__init__(condition)
        self.condition = condition
        self.offset = offset
        self.detail = detail


def normalize_text(value: str) -> str:
    """§4.6 SP／TABの正規化。前後を除去し、内部の連続するSP／TABを1個のSPへ畳む。"""

    stripped = value.strip(" \t")
    return _SP_TAB_RUN_RE.sub(" ", stripped)


def decode_escapes(value: str) -> str:
    """既知のエスケープだけを解除する（`read_bracket`が既に妥当性を検証済みの文字列に使う）。"""

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
    """`pos`の`[`から対応する`]`まで読み取り、(内容, `]`の直後のオフセット)を返す。

    DQUOTE区間は`]`を`qchar`として無視し（拡張タグの`quoted-value`）、5種類の既知のエスケープは
    2文字をまとめて消費する。§4.3「コードスパンの外にある未エスケープの`[`で、直前の`text`を終了する」はタグの
    角括弧の内容にも及ぶため、引用符の外で未エスケープの`[`に出会った時点でも即座に破綻とする
    （その内側を次のタグの開始とみなし、これ以上`pos`の角括弧を探索しない）。
    閉じられない場合、不正なエスケープの場合、`quoted-value`が閉じない場合、内側に未エスケープの`[`が
    現れた場合は、いずれも`EAI-CORE-SYNTAX-004`に当たるものとして、最初に開いた`[`（`pos`）の位置で
    `CONDITION_TAG_UNCLOSED`の`LexError`を送出する（診断レジストリ §4: 不正なエスケープ・
    未閉鎖の`quoted-value`・不正または未閉鎖のタグは同一の`conditionId`）。
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
    """`start`のバッククォートの連続列から、同じ長さで閉じる最初の連続列までを読む(§3 `code-span`)。

    (コードスパンの内容, 終了の連続列の直後のオフセット)を返す。閉じられなければ`CONDITION_CODE_UNCLOSED`を送出する。
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
    """`activation`／`reason`の`text`。次の未エスケープでコードスパンの外の`[`まで読み、(元のテキスト, `[`のオフセット)を返す。

    §4.6の正規化は呼び出し側が連結した後に適用する。行末まで`[`が現れない場合は、期待した
    次のタグが存在しないことを表す`CONDITION_TAG_REQUIRED`を送出する。
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
    """`operation`の`text`と`period`（§3の特例）。

    §4.3「コードスパンの外にある未エスケープの`[`で、直前の`text`を終了する」は`operation`の`text`にも適用する。
    未エスケープかつコードスパンの外の`[`に出会ったら、そこで`text`の走査を終了し`(None, None, その`[`のオフセット)`
    を返す。呼び出し側は、`operation`の後には次のタグが存在しないことを踏まえてその角括弧を
    分類する（閉じなければ不正なタグ、閉じてCoreのタグのキーワードならタグの順序の不正、それ以外は不正なタグ。
    2026-09作業依頼#1）。

    `[`に出会わずに行末へ達した場合は、コードスパンの外にある行末直前の最後の`.`または`。`だけを
    `period`とみなし、それ以前を`text`（正規化後）とする。該当する終端の`period`がなければ
    `(None, None, None)`を返し、呼び出し側が句点の欠落として扱う。
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
