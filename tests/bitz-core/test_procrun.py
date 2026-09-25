"""`bitz.procrun`の単体試験（`03_操作仕様/03_verify.md` §5・§5.2）。

時間のかかる試験はtimeout値を小さくし、数秒で終わるようにする。
"""

import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from bitz import procrun


def _write_script(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)


class ExitTests(unittest.TestCase):
    def test_exit_zero_is_passed_like_termination(self):
        result = procrun.run([sys.executable, "-c", "print('ok')"], os.getcwd(), dict(os.environ), 5)
        self.assertEqual(result["termination"], "exit")
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(result["stdout_excerpt"], "ok\n")

    def test_exit_nonzero(self):
        result = procrun.run([sys.executable, "-c", "raise SystemExit(3)"], os.getcwd(), dict(os.environ), 5)
        self.assertEqual(result["termination"], "exit")
        self.assertEqual(result["exit_code"], 3)

    def test_spawn_error_for_missing_executable(self):
        result = procrun.run(["/nonexistent/bin/nope"], os.getcwd(), dict(os.environ), 5)
        self.assertEqual(result["termination"], "spawn_error")
        self.assertIsNone(result["exit_code"])
        self.assertEqual(result["stdout_excerpt"], "")
        self.assertEqual(result["stderr_excerpt"], "")


class SignalTests(unittest.TestCase):
    def test_self_signal_is_reported_as_signal_with_null_exit_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "signal.sh"
            _write_script(script, "#!/bin/sh\nkill -TERM $$\n")
            result = procrun.run([str(script)], tmp, dict(os.environ), 5)
        self.assertEqual(result["termination"], "signal")
        self.assertIsNone(result["exit_code"])


class TimeoutTests(unittest.TestCase):
    def test_timeout_confirms_within_five_seconds_even_with_pipe_holding_descendant(self):
        """graceful terminationを無視し、TERMを無視する子孫がpipeを保持し続けても、
        timeout到達から5秒以内にbinding結果を確定する（§5.2）。"""

        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "hang.sh"
            _write_script(
                script,
                "#!/bin/sh\n"
                "trap '' TERM\n"
                "sh -c \"trap '' TERM; sleep 60\" &\n"
                "echo hang-ready\n"
                "i=0\n"
                "while [ \"$i\" -lt 60 ]; do\n"
                "    sleep 1\n"
                "    i=$((i + 1))\n"
                "done\n",
            )
            started = time.monotonic()
            result = procrun.run([str(script)], tmp, dict(os.environ), 1)
            elapsed = time.monotonic() - started

        self.assertEqual(result["termination"], "timeout")
        self.assertIsNone(result["exit_code"])
        self.assertEqual(result["stdout_excerpt"], "hang-ready\n")
        # timeoutSeconds=1 + 状態機械の上限5秒 + 若干の余裕。
        self.assertLess(elapsed, 8.0)

    def test_group_sigkill_even_when_direct_process_already_exited_from_sigterm(self):
        """検収是正6: 直接processがSIGTERMで終了しても、process groupへSIGKILLを送り、
        TERMを無視する子孫（同じgroupに残る）を確実に止める。"""

        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "leave_orphan.sh"
            _write_script(
                script,
                "#!/bin/sh\n"
                # 子孫はTERMを無視してsleepし続ける。親はTERMを普通に受けて即終了する
                # （trapを設定しないので、SIGTERMで直接processは速やかに死ぬ）。
                "sh -c \"trap '' TERM; sleep 60\" &\n"
                "echo ready\n"
                "sleep 60\n",
            )
            result = procrun.run([str(script)], tmp, dict(os.environ), 1)
        self.assertEqual(result["termination"], "timeout")
        time.sleep(0.3)
        check = subprocess.run(["pgrep", "-f", "trap '' TERM; sleep 60"], capture_output=True, text=True)
        self.assertEqual(check.stdout.strip(), "", "TERMを無視する子孫が生き残っています")

    def test_no_leftover_process_after_timeout(self):
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "hang.sh"
            _write_script(
                script,
                "#!/bin/sh\n"
                "trap '' TERM\n"
                "echo ready\n"
                "sleep 60\n",
            )
            result = procrun.run([str(script)], tmp, dict(os.environ), 1)
        self.assertEqual(result["termination"], "timeout")
        # process groupへのSIGKILLで直接processは確実に停止しているはず。
        time.sleep(0.2)
        check = subprocess.run(["pgrep", "-f", str(script)], capture_output=True, text=True)
        self.assertEqual(check.stdout.strip(), "", "timeout後にprocessが残っています")


class StreamTests(unittest.TestCase):
    def test_stdout_and_stderr_drain_concurrently_without_deadlock(self):
        # 片方のstreamだけへ大量出力しても、もう片方が詰まって全体がdeadlockしないことを確認する。
        code = (
            "import sys\n"
            "for _ in range(20000):\n"
            "    sys.stdout.write('x')\n"
            "sys.stderr.write('done')\n"
        )
        started = time.monotonic()
        result = procrun.run([sys.executable, "-c", code], os.getcwd(), dict(os.environ), 10)
        elapsed = time.monotonic() - started
        self.assertEqual(result["termination"], "exit")
        self.assertEqual(len(result["stdout_excerpt"]), 20000)
        self.assertEqual(result["stderr_excerpt"], "done")
        self.assertLess(elapsed, 5.0)


if __name__ == "__main__":
    unittest.main()
