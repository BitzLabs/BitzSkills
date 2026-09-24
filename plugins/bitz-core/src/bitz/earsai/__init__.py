"""EARS-AI言語のCandidate Scanner／Lexer／Parser／Semantic IR（Phase A）。

`docs/03.詳細設計/01_EARS-AI/01_言語・Semantic-IR仕様.md` を実装する。文書モデル
（Frontmatter・状態・関係）や ``check`` への統合はPhase B／Cで扱うため、本packageは
1文書のtextを受け取ってSemantic IRの配列と構文条件（condition）の配列を返すだけに留める。

公開APIは :func:`bitz.earsai.parser.parse_document` を主入口とする。
"""

from __future__ import annotations

from .parser import ParseResult, parse_document
from .scanner import Candidate, scan_candidates

__all__ = ["Candidate", "scan_candidates", "ParseResult", "parse_document"]
