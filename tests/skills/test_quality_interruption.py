"""品質評価器の起動中断で原出力と条件を失わないことをモデルなしで検証する。"""
import base64
import errno
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / "evals/skills/quality"
sys.path.insert(0, str(HERE))
import evaluate


class QualityInterruptionTests(unittest.TestCase):
    def setUp(self):
        scratch = ROOT / ".venv"
        scratch.mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix="quality-interruption-test-", dir=scratch)
        self.directory = Path(self.temporary.name)
        self.workspace = self.directory / "workspace"
        self.workspace.mkdir()
        (self.workspace / "unchanged.txt").write_text("before", encoding="utf-8")
        evaluate.write(self.directory / "workspace-before.json", evaluate.preflight.files(self.workspace))
        for name in ("control.json", "model-config.json", "prompt.txt", "host.jsonl"):
            (self.directory / name).write_text("synthetic", encoding="utf-8")

    def tearDown(self):
        self.temporary.cleanup()

    def test_save_native_outputs_keeps_non_utf8_when_trace_write_fails(self):
        original = Path.write_bytes

        def write(path, content):
            if path.name == "trace.jsonl":
                raise OSError(errno.ENOSPC, "synthetic full")
            return original(path, content)

        with patch.object(Path, "write_bytes", autospec=True, side_effect=write):
            first, errors, unsaved = evaluate.save_native_outputs(self.directory, b"\xffpartial", b"stderr")
        self.assertIsInstance(first, OSError)
        self.assertEqual([{"path": "trace.jsonl", "errorType": "OSError", "errno": errno.ENOSPC}], errors)
        self.assertEqual(b"\xffpartial", base64.b64decode(unsaved["trace.jsonl"]["data"]))
        self.assertEqual(b"stderr", (self.directory / "stderr.log").read_bytes())

    def test_preserve_invocation_failure_records_context_diff_and_unsaved_bytes(self):
        before = evaluate.load(self.directory / "workspace-before.json")
        (self.workspace / "unexpected.txt").write_text("changed", encoding="utf-8")
        identity = {"runId": "synthetic-interruption", "sourceCommit": "a" * 40}
        command = ["codex", "exec", "--model", "gpt-6.1-sol", "-"]
        evaluate.preserve_invocation_failure(
            self.directory, identity, self.workspace, command, 600, time.monotonic() - 0.01,
            error_type="TimeoutExpired", reason="synthetic timeout", errno=None,
            output_save_errors=[{"path": "trace.jsonl", "errorType": "OSError", "errno": errno.ENOSPC}],
            unsaved_outputs={"trace.jsonl": {"encoding": "base64", "data": base64.b64encode(b"\xff").decode("ascii")}},
        )
        record = evaluate.load(self.directory / "interruption.json")
        self.assertEqual("interrupted", record["status"])
        self.assertEqual(identity, record["identity"])
        self.assertEqual(command, record["invocation"]["argv"])
        self.assertEqual(["unexpected.txt"], record["changes"]["changedPaths"])
        self.assertEqual(before, record["changes"]["before"])
        self.assertEqual(b"\xff", base64.b64decode(record["unsavedOutputs"]["trace.jsonl"]["data"]))
        self.assertFalse(record["automaticRetry"])

    def replay(self, outcome, *, failing_outputs=(), change=False):
        """実measure/台帳/保存を接続し、CodexだけをSpyへ置換する。"""
        replay_dir = Path(tempfile.mkdtemp(prefix="replay-", dir=self.directory))
        output = replay_dir / "synthetic-measurement"
        scope_dir = replay_dir / "synthetic-authorization"
        scope_dir.mkdir()
        raw_trace = b'{"type":"turn.completed","usage":{"synthetic":true}}\n'
        raw_stderr = b"synthetic native stderr\n"
        native_calls = []

        def setup(directory, case, variant, run_id):
            workspace = directory / case["caseId"]
            workspace.mkdir()
            (workspace / "target.py").write_text("synthetic unchanged\n")
            return workspace, {"subjectCommit": "b" * 40, "baseCommit": "c" * 40}

        def backend(command, **kwargs):
            self.assertEqual("codex", command[0])
            if command[1:] == ["--version"]:
                return subprocess.CompletedProcess(command, 0, "synthetic Codex version", "")
            self.assertEqual("exec", command[1])
            native_calls.append({"command": command, "kwargs": kwargs})
            directory = output / "quality-pilot-skill-r1-QR-004"
            if change:
                (directory / "QR-004/target.py").write_text("synthetic changed\n")
            if outcome == "spawn-error":
                raise OSError(errno.ENOENT, "synthetic executable absent")
            if outcome.startswith("timeout"):
                trace = b"\xffpartial trace\n" if outcome == "timeout-bytes" else "partial trace\n"
                stderr = b"\xfepartial stderr\n" if outcome == "timeout-bytes" else "partial stderr\n"
                raise subprocess.TimeoutExpired(command, 600, output=trace, stderr=stderr)
            if outcome == "keyboard":
                raise KeyboardInterrupt()
            if outcome != "missing-response":
                (directory / "response.json").write_text("{}")
            stdout = b"\xffnon-UTF8 trace\n" if outcome == "non-utf8" else raw_trace
            return subprocess.CompletedProcess(command, 2 if outcome == "nonzero" else 0, stdout, raw_stderr)

        original_write = Path.write_bytes

        def write_bytes(path, content):
            if path.name in failing_outputs:
                raise OSError(errno.ENOSPC, "synthetic output full")
            return original_write(path, content)

        args = SimpleNamespace(output=output, timeout=600, protocol=HERE / "normal-protocol.json",
                               approval=HERE / "normal-approval.json")
        with patch("evaluate.authorization_directory", return_value=scope_dir), \
             patch("preflight.git", side_effect=lambda args, *rest: b"" if args[0] == "status" else b"a" * 40), \
             patch("evaluate.setup", side_effect=setup), \
             patch("evaluate.subprocess.run", side_effect=backend), \
             patch("evaluate.inspect_record", return_value=({"mechanical": [], "safety": [], "evidence": []}, None)), \
             patch.object(Path, "write_bytes", autospec=True, side_effect=write_bytes), redirect_stdout(io.StringIO()):
            raised = None
            try:
                result = evaluate.measure(args)
            except (OSError, ValueError, subprocess.SubprocessError, KeyboardInterrupt) as error:
                raised = error
                result = None
            directory = output / "quality-pilot-skill-r1-QR-004"
            if outcome != "success":
                before = {str(p): p.read_bytes() for p in [output / "attempts.json", *scope_dir.glob("*.json")]}
                with self.assertRaises((OSError, ValueError)):
                    evaluate.measure(args)
                self.assertEqual(before, {name: Path(name).read_bytes() for name in before})
                self.assertEqual(1, len(native_calls), "interrupted attempt must block another backend")
        self.assertEqual(1, len(evaluate.load(output / "attempts.json")))
        ledgers = list(scope_dir.glob("*-authorization.json"))
        self.assertEqual(1, len(ledgers))
        self.assertEqual(1, evaluate.load(ledgers[0])["attemptCount"])
        return directory, native_calls[0], raised, result, raw_trace, raw_stderr

    def test_postprocessing_oserror_preserves_completed_native_outputs(self):
        directory, _, error, _, trace, stderr = self.replay("missing-response")
        self.assertIsInstance(error, FileNotFoundError)
        self.assertEqual(trace, (directory / "trace.jsonl").read_bytes())
        self.assertEqual(stderr, (directory / "stderr.log").read_bytes())
        record = evaluate.load(directory / "interruption.json")
        self.assertEqual(0, record["exitCode"])
        self.assertFalse(record["automaticRetry"])

    def test_native_capture_is_binary_and_non_utf8_is_retained(self):
        directory, call, error, _, _, stderr = self.replay("non-utf8")
        self.assertIsInstance(error, UnicodeDecodeError)
        self.assertFalse(call["kwargs"].get("text", False))
        self.assertIsInstance(call["kwargs"]["input"], bytes)
        self.assertEqual(b"\xffnon-UTF8 trace\n", (directory / "trace.jsonl").read_bytes())
        self.assertEqual(stderr, (directory / "stderr.log").read_bytes())
        self.assertEqual(0, evaluate.load(directory / "interruption.json")["exitCode"])

    def test_keyboard_interrupt_is_recorded_without_inventing_output(self):
        directory, _, error, _, _, _ = self.replay("keyboard")
        self.assertIsInstance(error, KeyboardInterrupt)
        record = evaluate.load(directory / "interruption.json")
        self.assertEqual("KeyboardInterrupt", record["errorType"])
        self.assertFalse(record["nativeOutputAvailable"])
        self.assertIsNone(record["providerUsage"])
        self.assertFalse((directory / "run.json").exists())

    def test_nonzero_exit_keeps_raw_logs_and_actual_workspace_change(self):
        directory, _, error, _, trace, stderr = self.replay("nonzero", change=True)
        self.assertIsInstance(error, ValueError)
        self.assertEqual(trace, (directory / "trace.jsonl").read_bytes())
        self.assertEqual(stderr, (directory / "stderr.log").read_bytes())
        record = evaluate.load(directory / "interruption.json")
        self.assertEqual("NonzeroExit", record["errorType"])
        self.assertEqual(2, record["exitCode"])
        self.assertEqual(["target.py"], record["changes"]["changedPaths"])

    def test_timeout_bytes_and_text_outputs_are_preserved(self):
        for outcome, trace, stderr in (("timeout-bytes", b"\xffpartial trace\n", b"\xfepartial stderr\n"),
                                       ("timeout-text", b"partial trace\n", b"partial stderr\n")):
            with self.subTest(outcome=outcome):
                directory, _, error, _, _, _ = self.replay(outcome)
                self.assertIsInstance(error, subprocess.TimeoutExpired)
                self.assertEqual(trace, (directory / "trace.jsonl").read_bytes())
                self.assertEqual(stderr, (directory / "stderr.log").read_bytes())
                self.assertEqual("TimeoutExpired", evaluate.load(directory / "interruption.json")["errorType"])

    def test_each_output_write_failure_preserves_both_original_streams(self):
        for failing in (("trace.jsonl",), ("stderr.log",), ("trace.jsonl", "stderr.log")):
            with self.subTest(failing=failing):
                directory, _, error, _, trace, stderr = self.replay("nonzero", failing_outputs=failing)
                self.assertIsInstance(error, OSError)
                record = evaluate.load(directory / "interruption.json")
                self.assertEqual(len(failing), len(record["outputSaveErrors"]))
                self.assertEqual(2, record["exitCode"])
                for name, raw in (("trace.jsonl", trace), ("stderr.log", stderr)):
                    saved = base64.b64decode(record["unsavedOutputs"][name]["data"]) if name in failing else (directory / name).read_bytes()
                    self.assertEqual(raw, saved)
                self.assertFalse((directory / "run.json").exists())

    def test_spawn_failure_records_unknown_output_without_synthetic_stderr(self):
        directory, _, error, _, _, _ = self.replay("spawn-error")
        self.assertIsInstance(error, OSError)
        record = evaluate.load(directory / "interruption.json")
        self.assertEqual(errno.ENOENT, record["errno"])
        self.assertFalse(record["nativeOutputAvailable"])
        self.assertIsNone(record["providerUsage"])
        self.assertFalse((directory / "trace.jsonl").exists())
        self.assertFalse((directory / "stderr.log").exists())

    def test_interrupted_attempt_cannot_be_reopened_with_a_receipt(self):
        directory, _, _, _, _, _ = self.replay("nonzero")
        evaluate.write(directory / "independent-receipt.json", {"status": "passed"})
        with self.assertRaisesRegex(ValueError, "was interrupted"):
            evaluate.verify_receipt(directory)

    def test_success_still_records_one_trajectory_without_interruption(self):
        directory, _, error, result, _, _ = self.replay("success")
        self.assertIsNone(error)
        self.assertEqual(0, result)
        self.assertTrue((directory / "run.json").exists())
        self.assertFalse((directory / "interruption.json").exists())


if __name__ == "__main__":
    unittest.main()
