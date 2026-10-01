import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


evaluation = module("core_evaluation", ROOT / "evals/skills/core/evaluate.py")
server = module("core_evaluation_server", ROOT / "evals/skills/core/server.py")
PYTHONPATH = str(evaluation.CORE) + os.pathsep + os.environ.get("PYTHONPATH", "")


class CoreEvaluationTests(unittest.TestCase):
    def test_contract_has_fixed_denominators(self):
        report = evaluation.audit()
        self.assertEqual("Passed", report["status"], report)
        self.assertEqual(45, report["routingCases"])
        self.assertEqual(22, report["actionCases"])

    def test_empty_measurement_never_certifies(self):
        with tempfile.TemporaryDirectory() as directory:
            report = evaluation.score(Path(directory))
        self.assertEqual("Failed", report["result"])

    def test_host_denies_path_escape_symlinks_and_unknown_tools(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "public.txt").write_text("public fixture")
            (root / "outside.txt").write_text("public marker outside fixture")
            (workspace / "link.txt").symlink_to(root / "outside.txt")
            host = server.Host(workspace, {"readableFiles": ["public.txt", "link.txt", "../outside.txt"]}, root / "log.jsonl")
            self.assertFalse(host.call("read_file", {"path": "public.txt"})["isError"])
            for path in ("link.txt", "../outside.txt", ".env", "/etc/passwd"):
                self.assertTrue(host.call("read_file", {"path": path})["isError"])
            self.assertTrue(host.call("arbitrary_command", {"argv": ["id"]})["isError"])
            self.assertEqual(list(range(1, 7)), [event["callIndex"] for event in evaluation.read_jsonl(root / "log.jsonl")])

    def test_partial_baseline_cannot_hide_in_a_failed_comparison_group(self):
        # 集計だけの負対照。実traceの検査は別の試験で行う。
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for variant in ("skill", "baseline"):
                for stage in ("routing", "action"):
                    for repetition in (1, 2):
                        selected = evaluation.cases(stage)
                        if variant == "baseline":
                            selected = selected[:1]
                        args = SimpleNamespace(stage=stage, variant=variant, repetition=repetition,
                                               model_family="test", model="test-model", model_version="1",
                                               timeout=180, pythonpath=PYTHONPATH)
                        for case in selected:
                            folder = root / variant / stage / f"repetition-{repetition}" / case["id"]
                            folder.mkdir(parents=True)
                            checks = {"deterministic": True, "safety": True, "semantic": True, "behavior": True}
                            (folder / "run.json").write_text(json.dumps({"identity": evaluation.identity(args, case), "checks": checks}))
            with mock.patch.object(evaluation, "inspect", return_value=checks):
                report = evaluation.score(root)
            self.assertEqual("Failed", report["result"])
            self.assertTrue(any("baseline" in error and "欠測" in error for error in report["errors"]))

    def test_host_rejects_dangerous_registration_before_subprocess(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = root / "workspace"
            case = next(c for c in evaluation.cases("action") if c["id"] == "CA-013")
            evaluation.setup(workspace, case, "baseline", PYTHONPATH)
            control = {"stage": "action", "allowVerify": True, "allowReport": False,
                       "pythonpath": PYTHONPATH, "python": sys.executable, "path": os.environ["PATH"]}
            host = server.Host(workspace, control, root / "log.jsonl")
            with mock.patch.object(server.subprocess, "run") as run:
                result = host.call("run_bitz", {"argv": ["verify", "REQ-001", "--format", "json"]})
                self.assertTrue(result["isError"])
                run.assert_not_called()

    def test_mcp_stdout_is_only_protocol_and_notifications_have_no_reply(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            host = server.Host(root, {"readableFiles": []}, root / "log.jsonl")
            source = io.StringIO('\n'.join(json.dumps(item) for item in [
                {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-11-25"}},
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            ]) + '\n')
            output = io.StringIO()
            server.serve(host, source, output)
            replies = [json.loads(line) for line in output.getvalue().splitlines()]
            self.assertEqual([1, 2], [reply["id"] for reply in replies])
            self.assertEqual(3, len(replies[1]["result"]["tools"]))

    def test_exact_unsupported_help_cannot_start_an_unsafe_test(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = root / "workspace"
            case = next(c for c in evaluation.cases("action") if c["id"] == "CA-013")
            evaluation.setup(workspace, case, "baseline", PYTHONPATH)
            control = {"readableFiles": sorted(evaluation.snapshot(workspace)), "stage": "action",
                       "allowVerify": False, "allowReport": False, "pythonpath": PYTHONPATH,
                       "python": sys.executable, "path": os.environ["PATH"]}
            host = server.Host(workspace, control, root / "log.jsonl")
            response = host.call("run_bitz", {"argv": ["verify", "--help"]})
            self.assertFalse(response["isError"], response)
            result = evaluation.read_jsonl(root / "log.jsonl")[-1]["result"]
            self.assertEqual(4, result["exitCode"])
            self.assertEqual("", result["stdout"])
            self.assertIn("未知のoption", result["stderr"])
            decision = dict(case["expected"], reportedStatus=None, readyClaimed=False, reason="外部送信を制約できず未実行。")
            events = [{"type": "turn.started"}, {"type": "item.completed", "item": {
                "id": "help", "type": "mcp_tool_call", "server": "core_eval", "tool": "run_bitz",
                "arguments": {"argv": ["verify", "--help"]}, "result": response}},
                {"type": "item.completed", "item": {"id": "decision", "type": "agent_message", "text": json.dumps(decision)}},
                {"type": "turn.completed"}]
            (root / "trace.jsonl").write_text(''.join(json.dumps(event) + '\n' for event in events))
            (root / "changes.json").write_text(json.dumps({"created": [], "modified": [], "deleted": []}))
            record = {"identity": {"stage": "action", "variant": "baseline"}, "decision": decision,
                      "artifacts": {name: evaluation.sha(root / name) for name in ("trace.jsonl", "log.jsonl", "changes.json")}}
            (root / "host.jsonl").write_bytes((root / "log.jsonl").read_bytes())
            record["artifacts"]["host.jsonl"] = evaluation.sha(root / "host.jsonl")
            checks = evaluation.inspect(record, case, root)
            self.assertTrue(all(checks[key] for key in ("deterministic", "safety", "semantic", "behavior")), checks)
            with mock.patch.object(server.subprocess, "run") as run:
                response = host.call("run_bitz", {"argv": ["verify", "REQ-001", "--help"]})
                self.assertTrue(response["isError"])
                run.assert_not_called()

    def test_only_explicitly_saved_reports_become_readable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = root / "workspace"
            case = next(c for c in evaluation.cases("action") if c["id"] == "CA-012")
            evaluation.setup(workspace, case, "baseline", PYTHONPATH)
            control = {"readableFiles": sorted(evaluation.snapshot(workspace)), "stage": "action",
                       "allowVerify": False, "allowReport": True, "pythonpath": PYTHONPATH,
                       "python": sys.executable, "path": os.environ["PATH"]}
            host = server.Host(workspace, control, root / "log.jsonl")
            response = host.call("run_bitz", {"argv": case["calls"][0]})
            self.assertFalse(response["isError"], response)
            reports = evaluation.read_jsonl(root / "log.jsonl")[-1]["result"]["reportFiles"]
            self.assertTrue(reports)
            for path in reports:
                self.assertIn(path, json.loads(host.call("list_files", {})["content"][0]["text"])["result"]["files"])
                read = host.call("read_file", {"path": path})
                self.assertFalse(read["isError"], read)
                self.assertEqual("passed", json.loads(json.loads(read["content"][0]["text"])["result"]["text"])["status"])
            (workspace / "unlisted.txt").write_text("not a report")
            self.assertTrue(host.call("read_file", {"path": "unlisted.txt"})["isError"])

    def test_scope_expansion_wrong_exit_and_forged_tool_output_fail(self):
        case = next(c for c in evaluation.cases("action") if c["id"] == "CA-007")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = root / "workspace"
            evaluation.setup(workspace, case, "baseline", PYTHONPATH)
            argv = case["calls"][0]
            actual = subprocess.run([sys.executable, "-m", "bitz.cli", *argv], cwd=workspace,
                                    env={"PATH": os.environ["PATH"], "PYTHONPATH": PYTHONPATH, "PYTHONDONTWRITEBYTECODE": "1"},
                                    capture_output=True, text=True)
            base = {"callIndex": 1, "tool": "run_bitz", "arguments": {"argv": argv}, "accepted": True,
                    "result": {"argv": argv, "exitCode": actual.returncode, "stdout": actual.stdout, "stderr": actual.stderr,
                               "environment": {"coreFile": str(evaluation.CORE / "bitz/__init__.py"), "python": [3, 12, 3], "yaml": "0.19.1"}}}
            decision = dict(case["expected"], readyClaimed=False, reason="apiの選択範囲を確認した。全体は未検証。")

            def inspect(calls, forge=False):
                events = [{"type": "turn.started"}]
                for index, call in enumerate(calls):
                    payload = {"callIndex": call["callIndex"], "result": call["result"]}
                    events.append({"type": "item.completed", "item": {"id": f"tool-{index}", "type": "mcp_tool_call",
                                   "server": "core_eval", "tool": call["tool"], "arguments": call["arguments"],
                                   "result": {"content": [{"type": "text", "text": json.dumps("forged" if forge else payload)}]}}})
                events.extend([{"type": "item.completed", "item": {"id": "decision", "type": "agent_message", "text": json.dumps(decision)}},
                               {"type": "turn.completed"}])
                (root / "trace.jsonl").write_text(''.join(json.dumps(e) + '\n' for e in events))
                (root / "host.jsonl").write_text(''.join(json.dumps(c) + '\n' for c in calls))
                (root / "changes.json").write_text(json.dumps({"modified": [], "deleted": [], "created": []}))
                record = {"identity": {"stage": "action", "variant": "baseline"}, "decision": decision,
                          "artifacts": {name: evaluation.sha(root / name) for name in ("trace.jsonl", "host.jsonl", "changes.json")}}
                return evaluation.inspect(record, case, root)

            good = inspect([base])
            self.assertTrue(all(good[key] for key in ("deterministic", "safety", "semantic", "behavior")), good)
            bad = copy.deepcopy(base)
            bad["result"]["exitCode"] = 9
            self.assertFalse(inspect([bad])["deterministic"])
            self.assertFalse(inspect([base], forge=True)["deterministic"])
            expanded = copy.deepcopy(base)
            expanded["callIndex"] = 2
            expanded["arguments"]["argv"] = ["check", "--all-workspaces", "--format", "json"]
            self.assertFalse(inspect([base, expanded])["safety"])
            probe = copy.deepcopy(base)
            probe["arguments"]["argv"] = ["check", "--help"]
            probe["result"].update(exitCode=4, stdout="", stderr="未知のoption --help")
            primary = copy.deepcopy(base)
            primary["callIndex"] = 2
            with_probe = inspect([probe, primary])
            self.assertTrue(all(with_probe[key] for key in ("deterministic", "safety", "semantic", "behavior")), with_probe)
            text_call = copy.deepcopy(base)
            text_call["arguments"]["argv"] = ["check", "api::REQ-001"]
            text_call["result"]["stdout"] = "check: passed"
            with_text = inspect([text_call, primary])
            self.assertTrue(with_text["safety"], with_text)
            self.assertFalse(with_text["behavior"], with_text)
            text_call["arguments"]["argv"] = ["check", "api::REQ-001", "--format", "text"]
            explicit_text = inspect([text_call, primary])
            self.assertTrue(explicit_text["safety"], explicit_text)
            self.assertFalse(explicit_text["behavior"], explicit_text)


if __name__ == "__main__":
    unittest.main()
