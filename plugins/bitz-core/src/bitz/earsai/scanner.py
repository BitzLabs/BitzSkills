"""規範文の候補の走査器（EARS-AI言語・意味中間表現仕様 §5）。

候補抽出と完全な構文検証を分離する。走査器はLFへ改行を正規化した後、文書の先頭から
行単位で状態機械を実行し、角括弧の閉鎖・規範文ID・タグの妥当性を判定せずに
候補行だけを、バイト列を変えずに返す。判定はASCIIかつ大文字と小文字を区別して行い、トークンの妥当性を
要求しない（`IsCandidateToken`）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_KNOWN_PREFIXES = ("REQ", "TECH", "ADR", "TASK")
_CORE_TAG_KEYWORDS = (
    "ACTOR",
    "ALWAYS",
    "WHEN",
    "WHILE",
    "WHERE",
    "IF_ERROR",
    "MUST",
    "SHOULD",
    "MAY",
    "REASON",
    "THEN",
    "GENERATE",
    "CONSTRAINT",
)
_RULE2_RE = re.compile(r"^[A-Z][A-Za-z0-9]*[:\-]")
_RULE4_RE = re.compile(r"^[a-z][a-z0-9]*:")


@dataclass(frozen=True)
class Candidate:
    """1件の規範文の候補行。

    ``line`` は1始まりの行番号、``column`` は候補行内で最初に現れる ``[`` の
    1始まりの列（Unicodeのコードポイント単位）、``raw`` は改行を含まない候補行全体。
    """

    line: int
    column: int
    raw: str


def normalize_newlines(text: str) -> str:
    """CRLF・CRをLFへ正規化する（§5冒頭）。"""

    return text.replace("\r\n", "\n").replace("\r", "\n")


def _is_candidate_token(token: str) -> bool:
    """§5 `IsCandidateToken`。ASCIIで、大文字と小文字を区別し、トークンの妥当性は問わない。"""

    if any(token.startswith(prefix) for prefix in _KNOWN_PREFIXES):
        return True
    if _RULE2_RE.match(token):
        return True
    if any(token.startswith(keyword) for keyword in _CORE_TAG_KEYWORDS):
        return True
    if _RULE4_RE.match(token):
        return True
    return False


def _leading_sp_count(line: str) -> int:
    count = 0
    for ch in line:
        if ch != " ":
            break
        count += 1
    return count


def _fence_run(line: str, start: int) -> tuple[str, int] | None:
    """`start`の位置から始まる、3個以上の連続するバッククォートまたはチルダの連続列を返す。"""

    if start >= len(line):
        return None
    ch = line[start]
    if ch not in ("`", "~"):
        return None
    end = start
    while end < len(line) and line[end] == ch:
        end += 1
    run_len = end - start
    if run_len < 3:
        return None
    return ch, run_len


def _iter_line_contexts(lines: list[str]):
    """行ごとに``(1始まりの行番号, line, indent, excluded)``を`yield`する（§5 フェンスの状態機械）。

    ``excluded``が``True``の行は、フェンス内・4つのSPの字下げの内側・引用ブロックの直後のいずれかであり、
    候補行の判定（`scan_candidates`）と見出しの判定（`document.py`のH1／H2の検出）が
    同じ文脈の除外規則を共有するための唯一の実装箇所。
    """

    state_fence: tuple[str, int] | None = None  # (開始の文字, 連続列の長さ) または通常の状態のときは`None`

    for index, line in enumerate(lines):
        line_number = index + 1
        indent = _leading_sp_count(line)

        if state_fence is not None:
            open_char, open_len = state_fence
            if indent <= 3:
                run = _fence_run(line, indent)
                if run is not None and run[0] == open_char and run[1] >= open_len:
                    rest = line[indent + run[1]:]
                    if rest == "" or set(rest) == {" "}:
                        state_fence = None
            yield line_number, line, indent, True
            continue

        if indent <= 3:
            run = _fence_run(line, indent)
            if run is not None:
                state_fence = (run[0], run[1])
                yield line_number, line, indent, True
                continue

        if indent >= 4:
            yield line_number, line, indent, True
            continue

        cursor = indent
        if cursor < len(line) and line[cursor] == ">":
            yield line_number, line, indent, True
            continue

        yield line_number, line, indent, False


def normal_line_numbers(text: str) -> set[int]:
    """フェンス・4つのSPの字下げ・引用ブロックの直後を除いた行番号（1始まり）を返す。

    見出し（H1／H2）の検出が候補行の検出と同じ文脈の除外規則を共有するために使う
    （`document.py`）。
    """

    normalized = normalize_newlines(text)
    lines = normalized.split("\n")
    return {ln for ln, _line, _indent, excluded in _iter_line_contexts(lines) if not excluded}


def scan_candidates(text: str) -> list[Candidate]:
    """文書全体（フロントマターを含む）から規範文の候補を抽出する。

    行番号は元のファイルを基準にした1始まりとする。フェンス・引用ブロック・4つのSPの字下げの内側、
    GFMのチェックボックスは候補にしない（SINGLE-099-*、SINGLE-010-01）。
    """

    normalized = normalize_newlines(text)
    lines = normalized.split("\n")
    candidates: list[Candidate] = []

    for line_number, line, indent, excluded in _iter_line_contexts(lines):
        if excluded:
            continue

        cursor = indent
        if line[cursor:cursor + 3] != "- [":
            continue

        bracket_start = cursor + 2
        close = line.find("]", bracket_start + 1)
        token = line[bracket_start + 1:close] if close != -1 else line[bracket_start + 1:]
        if token in (" ", "x", "X"):
            continue
        if _is_candidate_token(token):
            candidates.append(Candidate(line=line_number, column=cursor + 3, raw=line))

    return candidates
