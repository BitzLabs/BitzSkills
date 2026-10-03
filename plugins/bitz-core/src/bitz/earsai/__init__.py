"""EARS-AI言語の候補抽出の走査器・字句解析器・構文解析器・意味中間表現（フェーズA）。

`docs/03.詳細設計/01_EARS-AI/01_EARS-AI言語・意味中間表現仕様.md` を実装する。文書モデル
（フロントマター・状態・関係）や ``check`` への統合はフェーズB／Cで扱うため、本パッケージは
1文書のテキストを受け取って意味中間表現の配列と構文の条件（`condition`）の配列を返すだけに留める。

公開APIは :func:`bitz.earsai.parser.parse_document` を主入口とする。
"""

from __future__ import annotations

from .parser import ParseResult, parse_document
from .scanner import Candidate, scan_candidates

__all__ = ["Candidate", "scan_candidates", "ParseResult", "parse_document"]
