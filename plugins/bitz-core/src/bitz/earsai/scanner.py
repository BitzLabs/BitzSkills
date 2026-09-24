"""規範文候補Scanner（EARS-AI仕様 §5）。

候補抽出と完全構文検証を分離する。ScannerはLFへ改行を正規化した後、文書先頭から
行単位で状態機械を実行し、角括弧の閉鎖・statement ID・tagの妥当性を判定せずに
候補行だけをbyte変更せず返す。判定はASCIIかつcase-sensitiveで、tokenの妥当性を
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
    """1件の規範文候補行。

    ``line`` は1始まりの行番号、``column`` は候補行内で最初に現れる ``[`` の
    1始まりcolumn（Unicode code point単位）、``raw`` は改行を含まない候補行全体。
    """

    line: int
    column: int
    raw: str


def normalize_newlines(text: str) -> str:
    """CRLF・CRをLFへ正規化する（§5冒頭）。"""

    return text.replace("\r\n", "\n").replace("\r", "\n")


def _is_candidate_token(token: str) -> bool:
    """§5 `IsCandidateToken`。ASCII・case-sensitiveで、tokenの妥当性は問わない。"""

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
    """`start`位置から始まる3個以上の連続backtickまたはtildeのrunを返す。"""

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


def scan_candidates(text: str) -> list[Candidate]:
    """文書全体（Frontmatterを含む）から規範文候補を抽出する。

    行番号は元file基準の1始まりとする。fence・blockquote・4 SP indentの内側、
    GFM checkboxは候補にしない（SINGLE-099-*、SINGLE-010-01）。
    """

    normalized = normalize_newlines(text)
    lines = normalized.split("\n")
    candidates: list[Candidate] = []

    state_fence: tuple[str, int] | None = None  # (opening文字, run長) またはNormal時None

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
            continue

        if indent <= 3:
            run = _fence_run(line, indent)
            if run is not None:
                state_fence = (run[0], run[1])
                continue

        if indent >= 4:
            continue

        cursor = indent
        if cursor < len(line) and line[cursor] == ">":
            continue
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
