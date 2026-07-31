"""外部プロセス実行ランナー（FLW-DSN-013 process runner 節）。

Git / GitHub の知識を持たない汎用ランナー。依存方向は adapters → process runner の
一方向であり、本 module は result object にも renderer にも依存しない。

呼び出し側への契約:

- 戻り値の ``stdout`` / ``stderr`` は **parse のための一時データ**である。
  result へ転記してはならない（result envelope は additionalProperties: false で
  機械的に禁止している。references/output-contract.md）。
- 失敗理由は ``cause``（許可語彙）と ``stage`` で表す。exception・traceback・
  下位コマンドの終了コードをそのまま公開しない。
"""

from __future__ import annotations

import os
import platform
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from typing import Mapping, Sequence

# references/output-contract.md の許可語彙のうち、本 module が返し得るもの。
CAUSE_TIMEOUT = "timeout"
CAUSE_COMMAND_UNAVAILABLE = "command-unavailable"
CAUSE_PERMISSION_DENIED = "permission-denied"
# byte 上限超過に対応する専用 cause は許可語彙に無い。全量を観測できていない事実を
# 表す `result-indeterminate` を割り当て、区別は exit_category="output-limit" で行う
# （語彙の追加は公開契約の変更にあたるため、必要なら spec-issue で裁定する）。
CAUSE_RESULT_INDETERMINATE = "result-indeterminate"

STAGE_INSPECT = "inspect"
STAGE_VALIDATE = "validate"

# read operation の timeout 範囲（FLW-DSN-003）。write は M1 以降で 10〜300 秒。
READ_TIMEOUT_MIN_SECONDS = 1
READ_TIMEOUT_MAX_SECONDS = 300
DEFAULT_TIMEOUT_SECONDS = 30

# operation 別 byte 上限の既定。超過したプロセスは終了させ UNAVAILABLE を返す。
DEFAULT_OUTPUT_LIMIT_BYTES = 8 * 1024 * 1024

_TERMINATE_GRACE_SECONDS = 2.0
_POLL_INTERVAL_SECONDS = 0.02


class TimeoutBudget:
    """action 全体の deadline を段階へ配分する（FLW-DSN-013）。

    write operation は execution 最大 60%、termination grace 最大 10%（1〜5 秒）、
    reconciliation reserve 最低 30%（3 秒以上）へ分割し、execution が reserve を
    消費しないようにする。M0 は read-only のため reserve を使わないが、
    配分規則は M1 以降と同じ実装を共有する。
    """

    def __init__(self, total_seconds: float, *, mutating: bool = False) -> None:
        self.total_seconds = float(total_seconds)
        self.mutating = mutating
        self._started_at = time.monotonic()
        if mutating:
            self.execution_seconds = self.total_seconds * 0.6
            self.grace_seconds = min(5.0, max(1.0, self.total_seconds * 0.1))
            self.reconciliation_seconds = max(3.0, self.total_seconds * 0.3)
        else:
            self.execution_seconds = self.total_seconds
            self.grace_seconds = _TERMINATE_GRACE_SECONDS
            self.reconciliation_seconds = 0.0

    @property
    def elapsed_seconds(self) -> float:
        return time.monotonic() - self._started_at

    @property
    def execution_expired(self) -> bool:
        return self.elapsed_seconds >= self.execution_seconds


def normalize_timeout(value: float | None, *, mutating: bool = False) -> float:
    """timeout を許容範囲へ丸める。範囲外は境界値へ寄せる（拒否はしない）。"""
    minimum = 10 if mutating else READ_TIMEOUT_MIN_SECONDS
    if value is None:
        return float(DEFAULT_TIMEOUT_SECONDS)
    return float(min(READ_TIMEOUT_MAX_SECONDS, max(minimum, value)))


@dataclass(frozen=True)
class ProcessOutcome:
    """1 プロセス実行の結果。

    ``ok`` は「プロセスが上限内に正常終了した」ことだけを表す。operation として
    成功したかは呼び出し側が exit_status と parse 結果から判定する。
    """

    ok: bool
    command_name: str
    exit_status: int | None
    stdout: bytes
    stderr: bytes
    output_truncated: bool
    duration_ms: int
    cause: str | None = None
    stage: str = STAGE_INSPECT
    exit_category: str = "ok"


@dataclass
class _Drain:
    """パイプを byte 上限まで読む。上限超過を検出したら打ち切る。"""

    limit: int
    chunks: list[bytes] = field(default_factory=list)
    total: int = 0
    over_limit: bool = False

    def run(self, stream) -> None:
        try:
            while True:
                chunk = stream.read(65536)
                if not chunk:
                    return
                if self.total < self.limit:
                    self.chunks.append(chunk[: self.limit - self.total])
                self.total += len(chunk)
                if self.total > self.limit:
                    self.over_limit = True
                    return
        except (OSError, ValueError):
            # 強制終了でパイプが閉じた場合。読めた分だけを使う。
            return
        finally:
            try:
                stream.close()
            except OSError:
                pass

    @property
    def data(self) -> bytes:
        return b"".join(self.chunks)


class _ProcessTree:
    """子孫プロセスまで確実に終了させるための platform 依存部。

    POSIX は新規 session（= 新規 process group）へ入れて group signal を送る。
    Windows は ctypes の Job Object でプロセスツリーを所有し、close 時に kill する。
    どちらも提供できない platform では ``supported`` を False とし、呼び出し側が
    write operation を UNSUPPORTED へ縮退できるようにする。
    """

    def __init__(self) -> None:
        self.supported = False
        self._job = None
        self._kernel32 = None
        if os.name == "posix":
            self.supported = True
        elif os.name == "nt":
            self._kernel32 = self._open_job()
            self.supported = self._job is not None

    def _open_job(self):
        import ctypes
        from ctypes import wintypes

        try:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        except OSError:
            return None

        class _JobObjectBasicLimitInformation(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", wintypes.LARGE_INTEGER),
                ("PerJobUserTimeLimit", wintypes.LARGE_INTEGER),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.POINTER(wintypes.ULONG)),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]

        class _IoCounters(ctypes.Structure):
            _fields_ = [
                ("ReadOperationCount", ctypes.c_ulonglong),
                ("WriteOperationCount", ctypes.c_ulonglong),
                ("OtherOperationCount", ctypes.c_ulonglong),
                ("ReadTransferCount", ctypes.c_ulonglong),
                ("WriteTransferCount", ctypes.c_ulonglong),
                ("OtherTransferCount", ctypes.c_ulonglong),
            ]

        class _JobObjectExtendedLimitInformation(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", _JobObjectBasicLimitInformation),
                ("IoInfo", _IoCounters),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        job = kernel32.CreateJobObjectW(None, None)
        if not job:
            return None
        info = _JobObjectExtendedLimitInformation()
        info.BasicLimitInformation.LimitFlags = 0x2000  # KILL_ON_JOB_CLOSE
        ok = kernel32.SetInformationJobObject(
            job, 9, ctypes.byref(info), ctypes.sizeof(info)  # ExtendedLimitInformation
        )
        if not ok:
            kernel32.CloseHandle(job)
            return None
        self._job = job
        return kernel32

    def popen_kwargs(self) -> dict:
        if os.name == "posix":
            return {"start_new_session": True}
        if os.name == "nt":
            return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
        return {}

    def attach(self, proc: subprocess.Popen) -> None:
        if os.name != "nt" or self._job is None or self._kernel32 is None:
            return
        import ctypes

        handle = ctypes.windll.kernel32.OpenProcess(0x1F0FFF, False, proc.pid)
        if handle:
            self._kernel32.AssignProcessToJobObject(self._job, handle)
            ctypes.windll.kernel32.CloseHandle(handle)

    def terminate(self, proc: subprocess.Popen) -> None:
        if os.name == "posix":
            try:
                os.killpg(os.getpgid(proc.pid), 15)  # SIGTERM
            except (ProcessLookupError, PermissionError, OSError):
                proc.terminate()
            return
        proc.terminate()

    def kill(self, proc: subprocess.Popen) -> None:
        if os.name == "posix":
            try:
                os.killpg(os.getpgid(proc.pid), 9)  # SIGKILL
            except (ProcessLookupError, PermissionError, OSError):
                proc.kill()
            return
        self.close()
        proc.kill()

    def close(self) -> None:
        if os.name == "nt" and self._job is not None and self._kernel32 is not None:
            self._kernel32.CloseHandle(self._job)
            self._job = None


def process_tree_capability() -> str:
    """プロセスツリーを安全に収束できるかを返す（``supported`` / ``unsupported``）。

    write operation は unsupported な platform で UNSUPPORTED へ縮退する
    （M1 以降。M0 は read-only のため read を継続する）。
    """
    tree = _ProcessTree()
    try:
        return "supported" if tree.supported else "unsupported"
    finally:
        tree.close()


def run(
    argv: Sequence[str],
    *,
    cwd: str | None = None,
    timeout_seconds: float | None = None,
    output_limit_bytes: int = DEFAULT_OUTPUT_LIMIT_BYTES,
    env_overrides: Mapping[str, str] | None = None,
    mutating: bool = False,
    stage: str = STAGE_INSPECT,
) -> ProcessOutcome:
    """1 コマンドを実行する。

    ``argv`` は argument array であり、shell を経由しない（``shell=False``）。
    任意の shell 文字列を構築しないため、引用符・メタ文字の解釈は起きない。
    """
    if not argv:
        raise ValueError("argv が空です")

    command_name = os.path.basename(argv[0])
    budget = TimeoutBudget(normalize_timeout(timeout_seconds, mutating=mutating), mutating=mutating)
    started = time.monotonic()

    env = dict(os.environ)
    if env_overrides:
        env.update(env_overrides)

    tree = _ProcessTree()
    try:
        try:
            proc = subprocess.Popen(  # noqa: S603 - argument array・shell=False で実行する
                list(argv),
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                env=env,
                shell=False,
                **tree.popen_kwargs(),
            )
        except FileNotFoundError:
            return _failure(command_name, CAUSE_COMMAND_UNAVAILABLE, stage, started, "not-found")
        except PermissionError:
            return _failure(command_name, CAUSE_PERMISSION_DENIED, stage, started, "permission")
        except OSError:
            return _failure(command_name, CAUSE_COMMAND_UNAVAILABLE, stage, started, "spawn-failed")

        tree.attach(proc)
        out_drain = _Drain(output_limit_bytes)
        err_drain = _Drain(output_limit_bytes)
        threads = [
            threading.Thread(target=out_drain.run, args=(proc.stdout,), daemon=True),
            threading.Thread(target=err_drain.run, args=(proc.stderr,), daemon=True),
        ]
        for thread in threads:
            thread.start()

        timed_out = False
        over_limit = False
        while proc.poll() is None:
            if out_drain.over_limit or err_drain.over_limit:
                over_limit = True
                break
            if budget.execution_expired:
                timed_out = True
                break
            time.sleep(_POLL_INTERVAL_SECONDS)

        if timed_out or over_limit:
            _converge(tree, proc, budget.grace_seconds)
        else:
            proc.wait()

        for thread in threads:
            thread.join(timeout=budget.grace_seconds)

        # プロセスが上限超過の検出より先に終了した場合（パイプが閉じて EPIPE で
        # 落ちた場合を含む）を拾うため、drain の合流後にもう一度判定する。
        if not timed_out and not over_limit and (out_drain.over_limit or err_drain.over_limit):
            over_limit = True

        duration_ms = int((time.monotonic() - started) * 1000)
        if timed_out:
            return ProcessOutcome(
                ok=False,
                command_name=command_name,
                exit_status=proc.returncode,
                stdout=b"",
                stderr=b"",
                output_truncated=False,
                duration_ms=duration_ms,
                cause=CAUSE_TIMEOUT,
                stage=stage,
                exit_category="timeout",
            )
        if over_limit:
            return ProcessOutcome(
                ok=False,
                command_name=command_name,
                exit_status=proc.returncode,
                stdout=b"",
                stderr=b"",
                output_truncated=True,
                duration_ms=duration_ms,
                cause=CAUSE_RESULT_INDETERMINATE,
                stage=stage,
                exit_category="output-limit",
            )

        exit_status = proc.returncode
        return ProcessOutcome(
            ok=exit_status == 0,
            command_name=command_name,
            exit_status=exit_status,
            stdout=out_drain.data,
            stderr=err_drain.data,
            output_truncated=False,
            duration_ms=duration_ms,
            cause=None,
            stage=stage,
            exit_category="ok" if exit_status == 0 else "non-zero",
        )
    finally:
        tree.close()


def _converge(tree: _ProcessTree, proc: subprocess.Popen, grace_seconds: float) -> None:
    """terminate → 短い猶予 → kill → 必ず wait する。"""
    tree.terminate(proc)
    deadline = time.monotonic() + grace_seconds
    while proc.poll() is None and time.monotonic() < deadline:
        time.sleep(_POLL_INTERVAL_SECONDS)
    if proc.poll() is None:
        tree.kill(proc)
    proc.wait()


def _failure(
    command_name: str, cause: str, stage: str, started: float, exit_category: str
) -> ProcessOutcome:
    return ProcessOutcome(
        ok=False,
        command_name=command_name,
        exit_status=None,
        stdout=b"",
        stderr=b"",
        output_truncated=False,
        duration_ms=int((time.monotonic() - started) * 1000),
        cause=cause,
        stage=stage,
        exit_category=exit_category,
    )


def runtime_report() -> dict:
    """実行環境の要約（doctor と capability 判定が使う。秘密値を含めない）。"""
    return {
        "python": f"{sys.version_info.major}.{sys.version_info.minor}",
        "platform": platform.system().lower(),
        "process_tree": process_tree_capability(),
    }
