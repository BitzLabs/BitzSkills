"""Step 1で引数列の解析だけを提供し、本体の処理を未実装とする操作に共通の例外。

引数列が公開構文として妥当な場合だけここへ到達する（構文不正は :class:`~bitz.errors.CliArgError` で
すでに終了コード4になっている）。標準エラー出力へ理由を1行出し、終了コード3（`error`相当）で終える。
"""

from __future__ import annotations


class NotImplementedOperation(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason
