"""targetの字句規則。

文書ID、statement ID、複合workspace修飾ID、SPEC pathの構文検査だけを行う。
catalogへの存在確認（`CTX-ROOT-MISSING-001`）はCore操作開始後の責務であり、ここでは扱わない。
"""

from __future__ import annotations

import re

DOC_KIND_DIR = {
    "REQ": "requirements",
    "TECH": "technical",
    "ADR": "decisions",
    "TASK": "tasks",
}

_DOC_ID_RE = re.compile(r"^(REQ|TECH|ADR|TASK)-[0-9]{3,}$")
_LOCAL_ID_RE = r"[A-Za-z0-9][A-Za-z0-9-]*"
_STATEMENT_ID_RE = re.compile(r"^(REQ|TECH|ADR|TASK)-[0-9]{3,}:" + _LOCAL_ID_RE + r"$")
WORKSPACE_ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,31}$")
_QUALIFIER_RE = re.compile(r"^([a-z][a-z0-9-]{0,31})::(.+)$")


def _doc_kind(s: str) -> str | None:
    m = _DOC_ID_RE.match(s)
    return m.group(1) if m else None


def _statement_kind(s: str) -> str | None:
    m = _STATEMENT_ID_RE.match(s)
    return m.group(1) if m else None


def _strip_qualifier(s: str) -> str:
    """複合workspace修飾子``<workspace-id>::``を構文チェックのうえ剥がす。

    修飾子がなければそのまま返す。修飾子の構文が不正なら空文字列を返し、
    呼び出し側で「一致なし」として扱わせる。
    """
    if "::" not in s:
        return s
    m = _QUALIFIER_RE.match(s)
    if not m:
        return ""
    return m.group(2)


def is_document_id(s: str, kinds: frozenset[str]) -> bool:
    if not s:
        return False
    inner = _strip_qualifier(s)
    if not inner:
        return False
    kind = _doc_kind(inner)
    return kind is not None and kind in kinds


def is_statement_id(s: str, kinds: frozenset[str]) -> bool:
    if not s:
        return False
    inner = _strip_qualifier(s)
    if not inner:
        return False
    kind = _statement_kind(inner)
    return kind is not None and kind in kinds


def is_spec_path(s: str, kinds: frozenset[str]) -> bool:
    if not s or not s.endswith(".md"):
        return False
    if s.startswith("/") or ".." in s.split("/"):
        return False
    parts = s.split("/")
    if len(parts) < 3 or parts[0] != ".spec":
        return False
    dir_to_kind = {v: k for k, v in DOC_KIND_DIR.items()}
    kind = dir_to_kind.get(parts[1])
    if kind is None or kind not in kinds:
        return False
    # ファイル名部分（最後の要素）が空でないこと。
    return bool(parts[-1]) and parts[-1] != ".md"


def is_valid_target(s: str, kinds: frozenset[str], allow_path: bool) -> bool:
    if s == "":
        return False
    if is_document_id(s, kinds) or is_statement_id(s, kinds):
        return True
    if allow_path and is_spec_path(s, kinds):
        return True
    return False


DOCUMENT_ID_ALL = frozenset({"REQ", "TECH", "ADR", "TASK"})
