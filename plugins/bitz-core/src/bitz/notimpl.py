"""Step 1でargv解析だけを提供し本体処理を未実装とする操作の共通例外。

argvが公開構文として妥当な場合だけここへ到達する（構文不正は :class:`~bitz.errors.CliArgError` で
既に終了コード4になっている）。標準エラーへ理由を1行出し、終了コード3（`error`相当）で終える。
"""

from __future__ import annotations


class NotImplementedOperation(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason
