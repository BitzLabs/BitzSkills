"""終了コード4（argv不正）を表す例外。

Core操作を開始する前のargv検査で違反を検出した場合はこの例外を送出する。
標準出力へは何も書かず、標準エラーへ ``bitz: <context>: <reason>`` を1行だけ書く。
"""

from __future__ import annotations


class CliArgError(Exception):
    """argv解析またはCLI側の事前検査で検出した終了コード4相当のエラー。"""

    def __init__(self, context: str, reason: str) -> None:
        super().__init__(reason)
        self.context = context
        self.reason = reason
