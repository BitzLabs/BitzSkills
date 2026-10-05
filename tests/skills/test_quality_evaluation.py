"""Read-only host, exact evidence binding and continuation gates; no model calls."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / "evals/skills/quality"
sys.path.insert(0, str(HERE))
import evaluate
from host import Host, sha
import preflight


class QualityEvaluationTests(unittest.TestCase):
    def setUp(self):
        scratch = ROOT / ".venv"
        scratch.mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix="quality-host-test-", dir=scratch)
        self.directory = Path(self.temporary.name)
        self.cases = evaluate.load(HERE / "protocol.json")["cases"]

    def tearDown(self):
        self.temporary.cleanup()

    def prepared(self, case_index=0, variant="baseline", parent=None):
        parent = parent or self.directory
        workspace, control = evaluate.setup(parent, self.cases[case_index], variant, "synthetic-quality-review")
        log = parent / "host.jsonl"
        log.write_text("")
        return Host(workspace, control, log), workspace, control

    def test_read_returns_actual_hash_and_rejects_unlisted_paths(self):
        host, workspace, _ = self.prepared()
        result = host.call("read_file", {"path": "target.py"})
        self.assertFalse(result["isError"])
        data = json.loads(result["content"][0]["text"])
        self.assertEqual(sha((workspace / "target.py").read_bytes()), data["sha256"])
        for path in ("../control.json", ".git/config", "resources/../target.py", "/etc/passwd"):
            self.assertTrue(host.call("read_file", {"path": path})["isError"])

    def test_changed_fixed_file_and_symlink_are_rejected(self):
        host, workspace, _ = self.prepared()
        target = workspace / "target.py"
        target.write_text("changed synthetic input")
        self.assertTrue(host.call("read_file", {"path": "target.py"})["isError"])
        target.unlink()
        target.symlink_to(workspace / "test_fixture.py")
        self.assertTrue(host.call("read_file", {"path": "target.py"})["isError"])

    def test_arbitrary_execution_and_extra_arguments_are_not_available(self):
        host, _, _ = self.prepared()
        with patch("host.subprocess.run", side_effect=AssertionError("must not spawn")):
            for name, args in [("shell", {"command": "echo synthetic"}), ("run_bitz", {"operation": "verify"}),
                               ("run_bitz", {"operation": "check", "argv": ["--report", "outside"]}),
                               ("write_file", {"path": "target.py", "content": "replacement"})]:
                self.assertTrue(host.call(name, args)["isError"])

    def test_plan_has_no_test_execution_surface(self):
        host, _, _ = self.prepared()
        self.assertNotIn("run_fixture_test", {x["name"] for x in host.tools})
        self.assertTrue(host.call("run_fixture_test", {})["isError"])

    def test_review_runs_only_fixed_test_after_actual_reads(self):
        host, _, _ = self.prepared(1)
        self.assertTrue(host.call("run_fixture_test", {})["isError"])
        for name in ("target.py", "test_fixture.py"):
            self.assertFalse(host.call("read_file", {"path": name})["isError"])
        result = host.call("run_fixture_test", {})
        self.assertFalse(result["isError"])
        data = json.loads(result["content"][0]["text"])
        self.assertEqual(0, data["exitCode"])
        self.assertIn("Ran 1 test", data["stderr"])
        self.assertIn("OK", data["stderr"])

    def test_real_public_core_observation_keeps_original_bytes(self):
        host, _, control = self.prepared()
        result = host.call("run_bitz", {"operation": "context"})
        self.assertFalse(result["isError"])
        public = json.loads(result["content"][0]["text"])
        self.assertNotIn("execution", public)
        actual = evaluate.jsonl(host.log)[-1]["result"]
        self.assertEqual(public["observation"], actual["observation"])
        self.assertEqual(sha(actual["execution"]["stdout"].encode()), public["observation"]["sha256"])
        self.assertEqual(json.loads(actual["execution"]["stdout"]), public["observation"]["rawResult"])
        self.assertEqual(control["subjectCommit"], public["observation"]["rawResult"]["revision"]["commit"])
        self.assertFalse(public["observation"]["rawResult"]["revision"]["dirty"])

    def test_native_stdio_host_initializes_and_serves_exact_fixed_file(self):
        _, workspace, control = self.prepared()
        evaluate.write(self.directory / "control.json", control)
        requests = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05"}},
                    {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                    {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "read_file", "arguments": {"path": "target.py"}}}]
        result = subprocess.run([sys.executable, "-B", str(HERE / "host.py"), "--workspace", str(workspace),
                                 "--control", str(self.directory / "control.json"), "--log", str(self.directory / "rpc.jsonl")],
                                input="\n".join(json.dumps(r) for r in requests) + "\n", env=preflight.environment(),
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(0, result.returncode, result.stderr)
        responses = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual([1, 2, 3], [r["id"] for r in responses])
        self.assertEqual("2024-11-05", responses[0]["result"]["protocolVersion"])
        self.assertNotIn("run_fixture_test", {t["name"] for t in responses[1]["result"]["tools"]})
        returned = json.loads(responses[2]["result"]["content"][0]["text"])
        self.assertEqual(sha((workspace / "target.py").read_bytes()), returned["sha256"])

    def test_shared_inputs_match_and_expected_values_stay_outside_workspace(self):
        left = self.directory / "skill"
        right = self.directory / "baseline"
        left.mkdir()
        right.mkdir()
        _, workspace, skill = self.prepared(variant="skill", parent=left)
        _, _, baseline = self.prepared(parent=right)
        self.assertEqual(skill["subjectCommit"], baseline["subjectCommit"])
        self.assertEqual(skill["fixtureFiles"], baseline["fixtureFiles"])
        for name, digest in baseline["readableFiles"].items():
            self.assertEqual(digest, skill["readableFiles"][name])
        self.assertEqual(sha((HERE / "advice-format.md").read_bytes()), baseline["readableFiles"]["resources/advice-format.md"])
        self.assertFalse(any("SKILL.md" in name for name in baseline["readableFiles"]))
        extra = set(skill["readableFiles"]) - set(baseline["readableFiles"])
        self.assertTrue(extra)
        self.assertTrue(all(name.startswith("resources/bitz-quality/skills/quality-plan/") for name in extra))
        for forbidden in ("protocol.json", "preflight.py", "review-base.py", "approval.json"):
            self.assertFalse(any(Path(name).name == forbidden for name in skill["readableFiles"]))

    def test_approval_preserves_case_hash_and_eight_call_cap(self):
        approval = evaluate.load(HERE / "approval.json")
        protocol = evaluate.load(HERE / "protocol.json")
        self.assertEqual("approved", approval["approvalStatus"])
        self.assertEqual(sha((HERE / "protocol.json").read_bytes()), approval["protocolSha256"])
        self.assertEqual(8, approval["maximumNewTrajectories"])
        self.assertEqual(8, len(protocol["cases"]) * len(protocol["variants"]) * protocol["repetitions"])
        self.assertEqual("gpt-6.1-sol", approval["model"])
        self.assertFalse(approval["reuseSddBudget"])
        self.assertFalse(approval["baselineSemanticFailureContinuation"])

    def test_missing_or_failed_independent_receipt_cannot_spawn_next_model(self):
        run = self.directory / "prior-attempt"
        run.mkdir()
        evaluate.write(self.directory / "attempts.json", [{"directory": run.name}])
        evaluate.write(self.directory / "quality-pilot-authorization.json", {"output": str(self.directory), "approvalSha256": sha((HERE / "approval.json").read_bytes()), "attemptCount": 1})
        with patch("evaluate.authorization_directory", return_value=self.directory), patch("preflight.git", return_value=b""), patch("evaluate.subprocess.run", side_effect=AssertionError("must not invoke model")):
            with self.assertRaisesRegex(ValueError, "needs independent review"):
                evaluate.measure(SimpleNamespace(output=self.directory, timeout=10))
            evaluate.write(run / "independent-receipt.json", {"schemaVersion": "1.0", "independent": True, "implementationPrivateHistoryInherited": False,
                "status": "failed", "runSha256": "a" * 64, "reviewRunId": "independent-synthetic", "comparisonRunId": "synthetic",
                "sourceCommit": "a" * 40, "subjectCommit": "a" * 40,
                "checks": {"mechanical": "passed", "safety": "passed", "evidence": "passed", "semantic": "failed"},
                "directChecks": ["合成試験"], "reason": "意味不適合の停止試験"})
            evaluate.write(run / "run.json", {"identity": {"runId": "synthetic", "sourceCommit": "a" * 40}})
            evaluate.write(run / "control.json", {"subjectCommit": "a" * 40})
            with self.assertRaisesRegex(ValueError, "review failed"):
                evaluate.measure(SimpleNamespace(output=self.directory, timeout=10))

    def test_remediation_keeps_exact_case_and_pending_approval_cannot_execute(self):
        protocol = evaluate.load(HERE / "remediation-protocol.json")
        approval = evaluate.load(HERE / "remediation-approval.json")
        self.assertEqual([self.cases[1]], protocol["cases"])
        self.assertEqual(sha((HERE / "protocol.json").read_bytes()), protocol["origin"]["protocolSha256"])
        self.assertEqual(sha((HERE / "remediation-protocol.json").read_bytes()), approval["protocolSha256"])
        self.assertEqual("approved", approval["approvalStatus"])
        self.assertEqual("SOLでの評価は、すべて許可します。", approval["userInstruction"])
        self.assertEqual("0.1.2", protocol["pluginVersion"])
        self.assertEqual(4, len(protocol["cases"]) * len(protocol["variants"]) * protocol["repetitions"])
        self.assertEqual(4, approval["maximumNewTrajectories"])
        self.assertFalse(approval["reuseOriginalBudget"])
        self.assertFalse(approval["reuseSddBudget"])
        self.assertEqual(evaluate.load(HERE / "protocol.json")["stopOn"], protocol["stopOn"])
        original_load = evaluate.load
        pending = {**approval, "approvalStatus": "pending"}
        with patch("evaluate.load", side_effect=lambda path: pending if path == HERE / "remediation-approval.json" else original_load(path)), patch("evaluate.authorization_lock", side_effect=AssertionError("must not open ledger")), patch("evaluate.subprocess.run", side_effect=AssertionError("must not invoke model")):
            with self.assertRaisesRegex(ValueError, "authorization"):
                evaluate.measure(SimpleNamespace(output=self.directory, timeout=10,
                    protocol=HERE / "remediation-protocol.json", approval=HERE / "remediation-approval.json"))

    def test_arbitrary_contract_paths_are_rejected_before_execution(self):
        with patch("evaluate.subprocess.run", side_effect=AssertionError("must not invoke model")):
            for field in ("approval", "protocol"):
                args = dict(output=self.directory, timeout=10)
                args[field] = self.directory / "replacement.json"
                with self.assertRaisesRegex(ValueError, "only fixed"):
                    evaluate.measure(SimpleNamespace(**args))

    def test_old_approval_cannot_measure_a_changed_candidate(self):
        with patch("evaluate.authorization_directory", return_value=self.directory), patch("preflight.git", return_value=b""), patch("evaluate.subprocess.run", side_effect=AssertionError("must not invoke model")):
            with self.assertRaisesRegex(ValueError, "candidate version"):
                evaluate.measure(SimpleNamespace(output=self.directory, timeout=10))
        self.assertFalse((self.directory / "attempts.json").exists())

    def test_separate_proposed_ledger_preserves_original_budget_and_output_binding(self):
        original = self.directory / "quality-pilot-authorization.json"
        evaluate.write(original, {"output": "original-output", "attemptCount": 2, "approvalSha256": sha((HERE / "approval.json").read_bytes())})
        before = original.read_bytes()
        approval_path = HERE / "remediation-approval.json"
        approval = evaluate.load(approval_path)
        with patch("evaluate.authorization_directory", return_value=self.directory):
            # Exercise bookkeeping only; no model invocation is part of this test.
            with evaluate.authorization_lock(self.directory / "new", approval, approval_path) as (path, ledger):
                self.assertNotEqual(original, path)
                self.assertEqual(0, ledger["attemptCount"])
                ledger["attemptCount"] = 1
                evaluate.write(path, ledger)
            with self.assertRaisesRegex(ValueError, "another output"):
                with evaluate.authorization_lock(self.directory / "replacement", approval, approval_path):
                    self.fail("must not create another allowance")
        self.assertEqual(before, original.read_bytes())

    def test_exhausted_budget_cannot_spawn_model(self):
        evaluate.write(self.directory / "attempts.json", [{"directory": f"prior-{i}"} for i in range(8)])
        evaluate.write(self.directory / "quality-pilot-authorization.json", {"output": str(self.directory), "approvalSha256": sha((HERE / "approval.json").read_bytes()), "attemptCount": 8})
        with patch("evaluate.authorization_directory", return_value=self.directory), patch("preflight.git", return_value=b""), patch("evaluate.subprocess.run", side_effect=AssertionError("must not invoke model")):
            with self.assertRaisesRegex(ValueError, "budget exhausted"):
                evaluate.measure(SimpleNamespace(output=self.directory, timeout=10))

    def test_new_output_cannot_bypass_the_global_authorized_budget(self):
        approval = evaluate.load(HERE / "approval.json")
        evaluate.write(self.directory / "quality-pilot-authorization.json", {"output": str(self.directory / "original"), "approvalSha256": sha((HERE / "approval.json").read_bytes()), "attemptCount": 1})
        with patch("evaluate.authorization_directory", return_value=self.directory):
            with self.assertRaisesRegex(ValueError, "another output"):
                with evaluate.authorization_lock(self.directory / "replacement", approval):
                    self.fail("must not permit another budget")

    def test_native_codex_disables_extra_tool_surfaces_without_a_model_call(self):
        configs = evaluate.model_configs(self.directory, self.directory)
        command = ["codex", "features", "list"]
        for key, value in configs.items():
            command.extend(["-c", key + "=" + json.dumps(value)])
        process = subprocess.run(command, capture_output=True, text=True, timeout=20)
        self.assertEqual(0, process.returncode, process.stderr)
        states = {parts[0]: parts[-1] for line in process.stdout.splitlines() if len(parts := line.split()) >= 3}
        self.assertEqual("false", states.get("shell_tool"))
        for key, value in configs.items():
            feature = key.removeprefix("features.")
            if key.startswith("features.") and feature in states and feature != "unified_exec":
                self.assertEqual(str(value).lower(), states[feature], key)
        self.assertEqual("disabled", configs["web_search"])
        self.assertFalse(configs["apps._default.enabled"])

    def record_from_actual_host(self, read_contract=True):
        host, _, control = self.prepared()
        for name in ("target.py", "test_fixture.py", ".spec/requirements/REQ-001.md"):
            host.call("read_file", {"path": name})
        if read_contract:
            host.call("read_file", {"path": "resources/advice-format.md"})
        host.call("read_diff", {})
        for operation in ("context", "check"):
            host.call("run_bitz", {"operation": operation})
        calls = evaluate.jsonl(host.log)
        document = evaluate.load(ROOT / "plugins/bitz-quality/examples/local-change-plan.json")
        document["subjectCommit"] = control["subjectCommit"]
        response = {"documentJson": json.dumps(document, ensure_ascii=False),
                    "coreObservationIds": [c["result"]["observationId"] for c in calls if c["tool"] == "run_bitz"],
                    "reason": "合成試験。モデル測定の成功ではない"}
        trace = [{"type": "item.completed", "item": {"type": "mcp_tool_call", "server": "quality_eval", "tool": c["tool"], "arguments": c["arguments"],
                  "status": "completed", "error": None,
                  "result": {"content": [{"type": "text", "text": json.dumps({k: v for k, v in c["result"].items() if k != "execution"}, ensure_ascii=False)}], "structured_content": None}}} for c in calls]
        trace.append({"type": "item.completed", "item": {"type": "agent_message", "text": json.dumps(response)}})
        evaluate.write(self.directory / "control.json", control)
        evaluate.write(self.directory / "response.json", response)
        (self.directory / "trace.jsonl").write_text("\n".join(json.dumps(e) for e in trace) + "\n")
        record = {"identity": {"variant": "baseline", "executionVersion": "quality-execution-0.1.1"}, "artifacts": {name: sha((self.directory / name).read_bytes()) for name in ("host.jsonl", "control.json", "response.json", "trace.jsonl")}}
        return record, calls

    def test_shared_contract_requires_actual_read_without_changing_legacy_records(self):
        record, _ = self.record_from_actual_host(read_contract=False)
        errors, _ = evaluate.inspect_record(self.directory, self.cases[0], record)
        self.assertIn("shared declared format contract was not read", errors["mechanical"])
        record["identity"]["executionVersion"] = "quality-execution-0.1.2"
        errors, _ = evaluate.inspect_record(self.directory, self.cases[0], record)
        self.assertIn("shared declared format contract was not read", errors["mechanical"])
        record["identity"]["executionVersion"] = "quality-execution-0.1.3"
        errors, _ = evaluate.inspect_record(self.directory, self.cases[0], record)
        self.assertIn("shared declared format contract was not read", errors["mechanical"])
        record["identity"]["executionVersion"] = "quality-execution-0.1.4"
        errors, _ = evaluate.inspect_record(self.directory, self.cases[0], record)
        self.assertIn("shared declared format contract was not read", errors["mechanical"])
        record["identity"]["executionVersion"] = "quality-execution-0.1.0"
        errors, _ = evaluate.inspect_record(self.directory, self.cases[0], record)
        self.assertFalse(any(errors.values()), errors)

    def test_shared_format_batch_preserves_case_stop_policy_and_approval_binding(self):
        protocol = evaluate.load(HERE / "shared-format-protocol.json")
        approval = evaluate.load(HERE / "shared-format-approval.json")
        prior = evaluate.load(HERE / "remediation-protocol.json")
        self.assertEqual(prior["cases"], protocol["cases"])
        self.assertEqual(prior["stopOn"], protocol["stopOn"])
        self.assertEqual("approved", approval["approvalStatus"])
        self.assertEqual(sha((HERE / "shared-format-protocol.json").read_bytes()), approval["protocolSha256"])
        self.assertEqual(4, approval["maximumNewTrajectories"])
        self.assertEqual(protocol["model"], approval["model"])
        # Mixing two approved contract files must not create another budget.
        with patch("evaluate.authorization_lock", side_effect=AssertionError("must not open ledger")), patch("evaluate.subprocess.run", side_effect=AssertionError("must not invoke model")):
            with self.assertRaisesRegex(ValueError, "only fixed"):
                evaluate.measure(SimpleNamespace(output=self.directory, timeout=10,
                    protocol=HERE / "shared-format-protocol.json", approval=HERE / "remediation-approval.json"))

    def test_model_version_and_sol_scope_mismatch_stop_before_any_output_or_ledger(self):
        approval_path = HERE / "shared-format-approval.json"
        protocol_path = HERE / "shared-format-protocol.json"
        scope_path = HERE.parent / "sol-authorization.json"
        original_load = evaluate.load
        for name, replacement_path, field, value in [
            ("non-sol", approval_path, "model", "gpt-6-astra"),
            ("protocol model", protocol_path, "model", "gpt-6-sol"),
            ("evaluation version", approval_path, "evaluationSetVersion", "wrong-version"),
            ("scope pending", scope_path, "approvalStatus", "pending"),
            ("scope absent model", scope_path, "models", []),
            ("scope non-user", scope_path, "approvedBy", "not-user"),
            ("scope other project", scope_path, "scope", "別プロジェクトの評価"),
            ("scope models mapping", scope_path, "models", {"gpt-6.1-sol": True}),
            ("scope extra model", scope_path, "models", ["gpt-6.1-sol", "gpt-6-astra"]),
            ("other authorization", approval_path, "authorization", "replacement.json")
        ]:
            replacement = {**original_load(replacement_path), field: value}
            with self.subTest(name=name), patch("evaluate.load", side_effect=lambda path: replacement if path == replacement_path else original_load(path)), patch("evaluate.authorization_lock", side_effect=AssertionError("must not open ledger")), patch("preflight.git", side_effect=AssertionError("must stop before workspace access")), patch("evaluate.subprocess.run", side_effect=AssertionError("must not invoke model")):
                with self.assertRaisesRegex(ValueError, "sol authorization"):
                    evaluate.measure(SimpleNamespace(output=self.directory / "must-not-exist", timeout=10,
                        protocol=protocol_path, approval=approval_path))
                self.assertFalse((self.directory / "must-not-exist").exists())

    def test_original_core_insertion_preserves_exact_actual_observations(self):
        record, calls = self.record_from_actual_host()
        errors, document = evaluate.inspect_record(self.directory, self.cases[0], record)
        self.assertFalse(any(errors.values()), errors)
        actual = [c["result"]["observation"] for c in calls if c["tool"] == "run_bitz"]
        self.assertEqual(actual, document["coreResults"])
        self.assertEqual([], json.loads(evaluate.load(self.directory / "response.json")["documentJson"])["coreResults"])

    def test_rewritten_hash_trace_and_invented_core_cannot_pass_inspection(self):
        record, _ = self.record_from_actual_host()
        response = evaluate.load(self.directory / "response.json")
        response["coreObservationIds"] = ["invented-core"]
        evaluate.write(self.directory / "response.json", response)
        errors, _ = evaluate.inspect_record(self.directory, self.cases[0], record)
        self.assertTrue(any("artifact hash" in e for e in errors["evidence"]))
        self.assertTrue(any("actual trace" in e for e in errors["evidence"]))
        self.assertTrue(any("Core observation IDs" in e for e in errors["evidence"]))

    def test_native_or_extra_server_use_cannot_pass_safety(self):
        record, _ = self.record_from_actual_host()
        trace = evaluate.jsonl(self.directory / "trace.jsonl")
        trace.insert(0, {"type": "item.completed", "item": {"type": "command_execution", "command": "synthetic disallowed command"}})
        (self.directory / "trace.jsonl").write_text("\n".join(json.dumps(e) for e in trace) + "\n")
        errors, _ = evaluate.inspect_record(self.directory, self.cases[0], record)
        self.assertIn("native tool use outside fixed host", errors["safety"])

    def test_missing_or_substituted_tool_return_is_rejected_even_with_new_artifact_hash(self):
        record, _ = self.record_from_actual_host()
        original_trace = evaluate.jsonl(self.directory / "trace.jsonl")
        for mutation in ("missing", "replacement", "structured", "status"):
            with self.subTest(mutation=mutation):
                trace = copy.deepcopy(original_trace)
                item = trace[0]["item"]
                if mutation == "missing":
                    del item["result"]
                elif mutation == "replacement":
                    item["result"]["content"][0]["text"] = json.dumps({"substituted": True})
                elif mutation == "structured":
                    item["result"]["structured_content"] = {"substituted": True}
                else:
                    item["status"] = "failed"
                (self.directory / "trace.jsonl").write_text("\n".join(json.dumps(e) for e in trace) + "\n")
                record["artifacts"]["trace.jsonl"] = sha((self.directory / "trace.jsonl").read_bytes())
                errors, _ = evaluate.inspect_record(self.directory, self.cases[0], record)
                self.assertIn("trace MCP return differs from original host public result", errors["evidence"])


if __name__ == "__main__":
    unittest.main()
