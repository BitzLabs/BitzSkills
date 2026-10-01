"""終了コード4（引数不正）を表す例外。

Coreの操作を開始する前の引数の検査で違反を検出した場合は、この例外を送出する。
標準出力へは何も書かず、標準エラー出力へ ``bitz: <context>: <reason>`` を1行だけ書く。
"""

from __future__ import annotations


class CliArgError(Exception):
    """引数の解析またはCLI側の事前検査で検出した、終了コード4に当たるエラー。"""

    def __init__(self, context: str, reason: str) -> None:
        super().__init__(reason)
        self.context = context
        self.reason = reason
