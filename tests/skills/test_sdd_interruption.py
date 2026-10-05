"""実モデルを起動せずSDD native出力捕捉の退行を再現する。"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("sdd_interruption_subject", ROOT / "evals/skills/sdd/evaluate.py")
evaluation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluation)


class SddInterruptionRegression(unittest.TestCase):
    def exercise(self, kind):
        temporary = tempfile.TemporaryDirectory(prefix="sdd-native-regression-", dir=ROOT / ".venv")
        self.addCleanup(temporary.cleanup)
        output = Path(temporary.name) / "output"
        target = output / "skill/repetition-1/SI-010"
        args = argparse.Namespace(output=output, variant="skill", repetition=1, resume=False,
            model="gpt-6.1-sol", model_version="synthetic-only", timeout=10, pythonpath=os.environ["PYTHONPATH"])
        case = next(c for c in evaluation.load(evaluation.HERE / "cases.json") if c["id"] == "SI-010")
        original_run = evaluation.subprocess.run
        original_snapshot = evaluation.snapshot
        native_started, post_interrupted = False, False
        def snapshot(workspace):
            nonlocal post_interrupted
            if kind == "post-interrupt" and native_started and not post_interrupted:
                post_interrupted = True
                raise KeyboardInterrupt()
            return original_snapshot(workspace)
        self.native_calls = 0
        def dispatch(command, **kwargs):
            nonlocal native_started
            if command[0] != "codex":
                return original_run(command, **kwargs)
            self.native_calls += 1
            native_started = True
            evaluation.write(target / "workspace", "src/input.py", evaluation.FIXED)
            if kind == "interrupt":
                raise KeyboardInterrupt()
            if kind == "spawn-error":
                raise PermissionError(30, "synthetic read-only startup")
            if kind == "timeout-partial":
                raise subprocess.TimeoutExpired(command, 10, output=None, stderr=b"native stderr\n")
            child = [sys.executable, "-B", "-c",
                "import sys; sys.stdout.buffer.write(b'partial\\xff trace\\n'); sys.stderr.buffer.write(b'partial\\xfe stderr\\n')"]
            if kind == "post-interrupt":
                child[-1] = "import sys; sys.stdout.buffer.write(b'native trace\\n'); sys.stderr.buffer.write(b'native stderr\\n')"
            return original_run(child, **kwargs)
        with patch.object(evaluation, "identity", return_value={"sourceCommit": "synthetic-fixed-ref"}), \
                patch.object(evaluation.subprocess, "run", side_effect=dispatch), \
                patch.object(evaluation, "snapshot", side_effect=snapshot):
            expected = KeyboardInterrupt if kind in ("interrupt", "post-interrupt") else PermissionError if kind == "spawn-error" else subprocess.TimeoutExpired if kind == "timeout-partial" else FileNotFoundError
            with self.assertRaises(expected):
                evaluation.run_one(args, case)
            self.assertEqual(1, self.native_calls)
            with self.assertRaisesRegex(ValueError, "既存出力"):
                evaluation.run_one(args, case)
            self.assertEqual(1, self.native_calls)
        self.assertFalse((target / "run.json").exists())
        record = evaluation.load(target / "failure.json")
        self.assertEqual("not-measured", record["semantic"])
        self.assertEqual("not-certified", record["gateDecision"])
        self.assertEqual(["src/input.py"], record["changes"]["changedPaths"])
        return target, record

    def test_normal_return_keeps_non_utf8_raw_bytes_before_postprocessing(self):
        target, record = self.exercise("non-utf8")
        self.assertEqual(b"partial\xff trace\n", (target / "trace.jsonl").read_bytes())
        self.assertEqual(b"partial\xfe stderr\n", (target / "stderr.log").read_bytes())
        self.assertEqual(0, record["exitCode"])
        self.assertTrue(record["nativeOutputsObtained"])

    def test_keyboard_interrupt_records_unavailable_output_without_claiming_empty_capture(self):
        target, record = self.exercise("interrupt")
        self.assertEqual("KeyboardInterrupt", record["errorType"])
        self.assertFalse(record["nativeOutputsObtained"])
        self.assertIsNone(record["exitCode"])
        self.assertIsNone(record["providerUsage"])

    def test_spawn_error_does_not_fabricate_provider_stderr(self):
        target, record = self.exercise("spawn-error")
        self.assertEqual(b"", (target / "stderr.log").read_bytes())
        self.assertEqual(30, record["errno"])
        self.assertFalse(record["nativeOutputsObtained"])

    def test_postprocessing_interrupt_keeps_completed_capture_and_exit_code(self):
        target, record = self.exercise("post-interrupt")
        self.assertEqual("KeyboardInterrupt", record["errorType"])
        self.assertTrue(record["nativeOutputsObtained"])
        self.assertEqual(0, record["exitCode"])
        self.assertEqual(b"native trace\n", (target / "trace.jsonl").read_bytes())
        self.assertEqual(b"native stderr\n", (target / "stderr.log").read_bytes())

    def test_partial_timeout_distinguishes_missing_stdout_from_captured_stderr(self):
        target, record = self.exercise("timeout-partial")
        self.assertTrue(record["nativeOutputsObtained"])
        self.assertEqual({"stdout": False, "stderr": True}, record["nativeOutputAvailability"])
        self.assertEqual(b"", (target / "trace.jsonl").read_bytes())
        self.assertEqual(b"native stderr\n", (target / "stderr.log").read_bytes())
        self.assertIsNone(record["exitCode"])


if __name__ == "__main__":
    unittest.main()
