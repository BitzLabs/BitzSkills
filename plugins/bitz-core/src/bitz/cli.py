"""`bitz` CLIのentrypoint。

argv解析（終了コード4）、operationの実行、`--format`に応じた出力を仲介する。
"""

from __future__ import annotations

import json
import os
import sys

from . import check as check_op
from . import doctor as doctor_op
from .cliargs import parse_argv
from .errors import CliArgError
from .notimpl import NotImplementedOperation
from .textrender import render_check_text, render_doctor_text
from .textutil import sanitize_control_chars


def _write_stderr_line(context: str, reason: str) -> None:
    message = sanitize_control_chars(f"bitz: {context}: {reason}")
    sys.stderr.write(message + "\n")


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

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
        # context／verifyの本体処理はStep 3／4で実装する。
        raise NotImplementedOperation(
            f"{parsed.operation}: 本体処理はStep 2以降で実装する"
        )
    except CliArgError as exc:
        _write_stderr_line(exc.context, exc.reason)
        return 4
    except NotImplementedOperation as exc:
        sys.stderr.write(sanitize_control_chars(exc.reason) + "\n")
        return 3


def _emit(result: dict, fmt: str, text_renderer) -> None:
    if fmt == "json":
        sys.stdout.write(json.dumps(result, ensure_ascii=False) + "\n")
    else:
        sys.stdout.write(text_renderer(result))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
