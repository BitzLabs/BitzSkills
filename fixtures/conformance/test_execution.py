"""計時と進捗が適合判定を変えず、不正な部分実行を成功にしないことを確認する。"""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import run_conformance as entry


class ExecutionTests(unittest.TestCase):
    def run_harness(self, extra):
        stdout, stderr = io.StringIO(), io.StringIO()
        def fixture(root, identifier, core, validators, temporary, *, timings=None):
            if timings is not None:
                timings["process"] = 12.3
            return {"id": identifier, "result": "passed", "differences": []}
        with patch.object(entry, "CoreEnvironment"), patch.object(entry, "run_fixture", side_effect=fixture), \
             patch.object(entry, "host_tool_versions", return_value={"python": "3.12.3"}), \
             contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = entry.main(["--core", ".", *extra])
        return code, stdout.getvalue(), stderr.getvalue()

    def test_timings_and_progress_do_not_change_result(self):
        plain = self.run_harness(["--fixture", "SINGLE-001"])
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "timings.json"
            measured = self.run_harness(["--fixture", "SINGLE-001", "--timings", str(path), "--progress"])
            timings = json.loads(path.read_text())
        self.assertEqual(plain[:2], measured[:2])
        self.assertEqual(plain[2], "")
        self.assertIn("[1/1] SINGLE-001: passed", measured[2])
        self.assertEqual(timings["fixtures"][0]["phasesMs"], {"process": 12.3})
        self.assertGreaterEqual(timings["durationMs"], 0)
        self.assertNotIn("durationMs", json.loads(measured[1])["fixtures"][0])

    def test_missing_fixture_returns_failed_report(self):
        code, output, _ = self.run_harness(["--fixture", "MULTI-020-999"])
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(output)["counts"]["error"], 1)

    def test_invalid_selection_returns_invocation_error(self):
        for args in (["--step", "0"], ["--step", "1", "--suite", "scale"],
                     ["--step", "5", "--shard", "0"]):
            with self.subTest(args=args):
                code, output, error = self.run_harness(args)
                self.assertEqual(code, 2)
                self.assertFalse(output)
                self.assertTrue(error)

    def test_result_and_timing_paths_cannot_overwrite_each_other(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            entry.parse_args(["--core", ".", "--step", "5", "--output", "result.json", "--timings", "./result.json"])
        self.assertEqual(error.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
