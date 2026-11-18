"""`bitz` CLIのエントリポイント。

`--help`と`--version`（終了コード0）、引数の解析（終了コード4）、操作の実行、`--format`に応じた出力を仲介する。
"""

from __future__ import annotations

import json
import os
import sys

from . import check as check_op
from . import context as context_op
from . import doctor as doctor_op
from . import messages
from . import verify as verify_op
from .cliargs import InfoRequest, detect_info_request, parse_argv
from .contextrender import render_context_markdown
from .errors import CliArgError
from .textrender import render_check_text, render_doctor_text, render_verify_text
from .textutil import sanitize_control_chars


def _write_stderr_line(context: str, reason: str) -> None:
    message = sanitize_control_chars(f"bitz: {context}: {reason}")
    sys.stderr.write(message + "\n")


def _write_stdout_utf8(text: str) -> None:
    """標準出力へUTF-8で書く（`--help`の出力はUTF-8であることが契約。Core実行環境・CLI基盤契約 §5.1）。

    ロケールの文字コードによらずUTF-8のバイト列を書くため、テキストの層を通さずバイナリの層へ書く。
    バイナリの層を持たない置き換えられた標準出力（試験の``io.StringIO``など）には、そのまま書く。
    """
    buffer = getattr(sys.stdout, "buffer", None)
    if buffer is None:
        sys.stdout.write(text)
        return
    sys.stdout.flush()
    buffer.write(text.encode("utf-8"))
    buffer.flush()


def _run_info_request(request: InfoRequest) -> int:
    """`--help`と`--version`を処理する（ADR-075）。

    ワークスペースの探索、設定とファイルの読取り、Gitの呼出し、結果とレポートの作成を行わず、標準エラー出力へ何も書かない。
    """
    if request.kind == "version":
        # `doctor`の結果の`core.version`と同じ値を、同じ定義から取る（§5.1）。
        _write_stdout_utf8(messages.version_line(doctor_op.CORE_VERSION))
        return 0
    if request.operation is None:
        _write_stdout_utf8(messages.HELP_TOP)
    else:
        _write_stdout_utf8(messages.HELP_BY_OPERATION[request.operation])
    return 0


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    info_request = detect_info_request(argv)
    if info_request is not None:
        return _run_info_request(info_request)

    try:
        parsed = parse_argv(argv)
    except CliArgError as exc:
        _write_stderr_line(exc.context, exc.reason)
        return 4

    cwd = os.getcwd()
    env = dict(os.environ)

    try:
        if parsed.operation == "doctor":
            result, exit_code = doctor_op.run(parsed, cwd, env)
            fmt = parsed.single.get("--format", "text")
            _emit(result, fmt, render_doctor_text)
            return exit_code
        if parsed.operation == "check":
            result, exit_code = check_op.run(parsed, cwd, env)
            fmt = parsed.single.get("--format", "text")
            _emit(result, fmt, render_check_text)
            return exit_code
        if parsed.operation == "context":
            result, exit_code = context_op.run(parsed, cwd, env)
            fmt = parsed.single.get("--format", "markdown")
            _emit(result, fmt, render_context_markdown)
            return exit_code
        # `parse_argv`は公開の4つの操作のどれかだけを返す（`cliargs.OPERATIONS`）。
        result, exit_code = verify_op.run(parsed, cwd, env)
        fmt = parsed.single.get("--format", "text")
        _emit(result, fmt, render_verify_text)
        return exit_code
    except CliArgError as exc:
        _write_stderr_line(exc.context, exc.reason)
        return 4


def _emit(result: dict, fmt: str, text_renderer) -> None:
    if fmt == "json":
        sys.stdout.write(json.dumps(result, ensure_ascii=False) + "\n")
    else:
        sys.stdout.write(text_renderer(result))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
