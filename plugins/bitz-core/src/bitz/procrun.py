"""test process実行（`03_操作仕様/03_verify.md` §5・§5.2）。

shellを介さずargvで起動し、標準入力はnull device、標準出力・標準エラー出力は別pipeで
spawn時から並行drainする。読み取ったchunkはbufferへ溜め込まず、その場で``redact.StreamRedactor``へ
渡して公開抜粋（末尾64 KiB）だけを保持する（memoryを出力総量へ依存させないため）。

timeout到達時はdirect processとprocess groupへgraceful terminationを送り、2秒後に
（直接processの生死にかかわらず）process groupへforce kill、さらに2秒drainし、EOFがなくても
read handleを閉じてtimeout到達から5秒以内に確定する。子孫がpipeを保持してもEOFを無期限に待たない。
"""

from __future__ import annotations

import os
import selectors
import signal
import subprocess
import threading
import time

from . import redact


class _Deadline:
    __slots__ = ("_value", "_lock")

    def __init__(self) -> None:
        self._value: float | None = None
        self._lock = threading.Lock()

    def set(self, at: float) -> None:
        with self._lock:
            self._value = at

    def remaining(self) -> float | None:
        with self._lock:
            value = self._value
        if value is None:
            return None
        return value - time.monotonic()


def _reader(fileobj, redactor: "redact.StreamRedactor", deadline: _Deadline) -> None:
    fd = fileobj.fileno()
    os.set_blocking(fd, False)
    sel = selectors.DefaultSelector()
    sel.register(fd, selectors.EVENT_READ)
    try:
        while True:
            remaining = deadline.remaining()
            if remaining is not None and remaining <= 0:
                break
            events = sel.select(timeout=remaining)
            if not events:
                if remaining is not None:
                    break
                continue
            try:
                chunk = os.read(fd, 65536)
            except BlockingIOError:
                continue
            except OSError:
                break
            if not chunk:
                break
            redactor.feed(chunk)
    finally:
        sel.close()
        try:
            fileobj.close()
        except OSError:
            pass


def _terminate(proc: subprocess.Popen, sig: int) -> None:
    try:
        os.killpg(proc.pid, sig)
    except (ProcessLookupError, PermissionError, OSError):
        try:
            proc.send_signal(sig)
        except OSError:
            pass


def run(argv: list[str], cwd: str, env: dict[str, str], timeout_seconds: int) -> dict:
    """``argv``をspawnし、terminationと公開抜粋を返す。

    戻り値は``termination``（``exit``/``spawn_error``/``signal``/``timeout``）、``exit_code``、
    ``stdout_excerpt``/``stderr_excerpt``（redaction済み文字列）、
    ``stdout_truncated``/``stderr_truncated``、``duration_ms``を持つ``dict``。
    """

    start = time.monotonic()
    stdout_redactor = redact.StreamRedactor(env)
    stderr_redactor = redact.StreamRedactor(env)

    try:
        proc = subprocess.Popen(
            argv,
            cwd=cwd,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
    except OSError:
        duration_ms = int((time.monotonic() - start) * 1000)
        return {
            "termination": "spawn_error",
            "exit_code": None,
            "stdout_excerpt": "",
            "stderr_excerpt": "",
            "stdout_truncated": False,
            "stderr_truncated": False,
            "duration_ms": duration_ms,
        }

    deadline_out = _Deadline()
    deadline_err = _Deadline()
    # 保険としての外側上限。子孫がpipeを保持し続けても無期限に待たない。
    outer_deadline = start + timeout_seconds + 5.0
    deadline_out.set(outer_deadline)
    deadline_err.set(outer_deadline)

    t_out = threading.Thread(target=_reader, args=(proc.stdout, stdout_redactor, deadline_out), daemon=True)
    t_err = threading.Thread(target=_reader, args=(proc.stderr, stderr_redactor, deadline_err), daemon=True)
    t_out.start()
    t_err.start()

    exit_code: int | None = None
    try:
        raw_code = proc.wait(timeout=timeout_seconds)
        if raw_code < 0:
            termination = "signal"
            exit_code = None
        else:
            termination = "exit"
            exit_code = raw_code
    except subprocess.TimeoutExpired:
        termination = "timeout"
        timeout_at = time.monotonic()
        _terminate(proc, signal.SIGTERM)
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            pass
        # 2秒の猶予後は、直接processが既に終了していてもprocess groupへSIGKILLを送る
        # （TERMを無視する子孫がpipeを保持し続けるのを断つため。best effort、失敗は無視）。
        _terminate(proc, signal.SIGKILL)
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            pass
        bound = timeout_at + 5.0
        deadline_out.set(min(outer_deadline, bound))
        deadline_err.set(min(outer_deadline, bound))
        exit_code = None

    t_out.join(timeout=10)
    t_err.join(timeout=10)

    stdout_excerpt, stdout_truncated = stdout_redactor.close()
    stderr_excerpt, stderr_truncated = stderr_redactor.close()
    if termination == "spawn_error":  # pragma: no cover - Popen成功後は到達しない防御的分岐
        stdout_excerpt, stderr_excerpt = "", ""
        stdout_truncated = stderr_truncated = False

    duration_ms = int((time.monotonic() - start) * 1000)
    return {
        "termination": termination,
        "exit_code": exit_code,
        "stdout_excerpt": stdout_excerpt,
        "stderr_excerpt": stderr_excerpt,
        "stdout_truncated": stdout_truncated,
        "stderr_truncated": stderr_truncated,
        "duration_ms": duration_ms,
    }
