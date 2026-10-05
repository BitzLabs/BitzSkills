"""品質評価器の起動中断で原出力と条件を失わないことをモデルなしで検証する。"""
import base64
import errno
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
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


if __name__ == "__main__":
    unittest.main()
