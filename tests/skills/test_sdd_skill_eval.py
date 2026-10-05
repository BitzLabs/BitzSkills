"""SDD評価ホストと採点の試験。ここで作るモデルtraceは合成の単体試験用。"""

import argparse
import base64
import copy
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import shutil
import subprocess
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout
import io

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("sdd_evaluation", ROOT / "evals/skills/sdd/evaluate.py")
evaluation = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evaluation)


class SddEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="bitz-sdd-eval-tests-")
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.workspace = self.directory / "workspace"
        self.cases = {c["id"]: c for c in evaluation.load(evaluation.HERE / "cases.json")}

    def prepare(self, case_id="SI-001"):
        self.case = self.cases[case_id]
        self.control = evaluation.setup(self.workspace, self.case, "skill", os.environ["PYTHONPATH"])
        self.before = evaluation.snapshot(self.workspace)
        evaluation.write(self.directory, "control.json", json.dumps(self.control))
        evaluation.write(self.directory, "host.jsonl", "")
        self.host = evaluation.Host(self.workspace, self.control, self.directory / "host.jsonl")

    def call(self, name, **arguments):
        response = self.host.call(name, arguments)
        return json.loads(response["content"][0]["text"])

    def bitz(self, *argv):
        event = self.call("run_bitz", argv=[*argv, "--format", "json"])
        self.assertTrue(event["accepted"], event.get("error"))
        return json.loads(event["result"]["stdout"])

    def read_sources(self):
        for path in (".codex/skills/" + self.case["entry"] + "/SKILL.md", ".spec/bitz.yaml", "src/input.py", "tests/test_input.py"):
            self.assertTrue(self.call("read_file", path=path)["accepted"])

    def flow(self, *, replay=True, diff=True, fixed=True):
        self.read_sources()
        if diff:
            self.call("read_diff")
        initial = self.bitz("context", "TASK-001", "--purpose", "implement")
        self.assertTrue(initial["resolution"]["complete"])
        self.bitz("check", "TASK-001", "--base", "HEAD")
        if replay:
            confirmed = self.bitz("context", "TASK-001", "--purpose", "implement", "--expect-digest", initial["contextDigest"])
            self.assertEqual(initial["contextDigest"], confirmed["contextDigest"])
        self.assertTrue(self.call("write_file", path="src/input.py", content=evaluation.FIXED if fixed else "def validate(value):\n    return ['wrong']\n")["accepted"])
        self.bitz("check", "TASK-001", "--base", "HEAD")
        self.call("read_file", path="src/input.py")
        return self.bitz("verify", "TASK-001")

    def record(self, *, outcome=None):
        calls = evaluation.read_events(self.directory / "host.jsonl")
        after = evaluation.snapshot(self.workspace)
        changed = sorted({c["arguments"]["path"] for c in calls if c["tool"] == "write_file" and c["accepted"]
                          and self.before.get(c["arguments"]["path"]) != after.get(c["arguments"]["path"])})
        results = [{"operation": r["operation"], "target": next(a for a in c["arguments"]["argv"] if a in {"REQ-001", "TASK-001"}),
                    "status": r["status"], "exitCode": c["result"]["exitCode"]}
                   for c, r in evaluation.core_results(calls) if r is not None]
        decision = {"selectedEntry": self.case["entry"], "outcome": outcome or self.case["expected"]["outcome"],
                    "humanReviewPending": True, "readyClaimed": False, "changedPaths": changed,
                    "coreResults": results, "reason": "これは単体試験用の合成モデル応答で、実モデル測定ではない。"}
        evaluation.write(self.directory, "decision.json", json.dumps(decision))
        events = [{"type": "item.completed", "item": {"type": "mcp_tool_call", "server": "sdd_eval", "tool": c["tool"],
                  "arguments": c["arguments"], "result": {"content": [{"type": "text", "text": json.dumps(c)}]}}} for c in calls]
        events.append({"type": "item.completed", "item": {"type": "agent_message", "text": json.dumps(decision)}})
        evaluation.write(self.directory, "trace.jsonl", "\n".join(json.dumps(e) for e in events))
        evaluation.write(self.directory, "changes.json", json.dumps({"before": self.before, "after": after, "modelChanged": changed}))
        record = {"identity": {"variant": "skill"}, "decision": decision,
                  "artifacts": {name: evaluation.digest((self.directory / name).read_bytes())
                                for name in ("trace.jsonl", "host.jsonl", "changes.json", "decision.json", "control.json")}}
        return record

    def inspect(self, record):
        return evaluation.inspect(record, self.case, self.directory)

    def test_real_public_cli_flow_and_fixed_test_pass(self):
        self.prepare()
        verified = self.flow()
        self.assertEqual("passed", verified["status"])
        self.assertTrue(verified["commands"])
        self.assertTrue(all(c["exitCode"] == 0 for c in verified["commands"]))
        checks = self.inspect(self.record())
        self.assertTrue(all(c["passed"] for c in checks.values()), checks)

    def test_missing_digest_replay_is_not_a_successful_workflow(self):
        self.prepare()
        self.flow(replay=False)
        checks = self.inspect(self.record())
        self.assertFalse(checks["workflow"]["passed"])
        self.assertTrue(any("replay" in e for e in checks["workflow"]["errors"]))

    def test_context_commit_is_an_allowed_fixed_check_base(self):
        self.prepare()
        context = self.bitz("context", "TASK-001", "--purpose", "implement")
        fixed_base = context["revision"]["commit"]
        checked = self.bitz("check", "TASK-001", "--base", fixed_base)
        self.assertEqual("passed", checked["status"])
        self.assertEqual(fixed_base, checked["revision"]["base"])
        self.assertTrue(self.call("write_file", path="src/input.py", content=evaluation.FIXED)["accepted"])
        after = self.bitz("check", "TASK-001", "--base", fixed_base)
        self.assertEqual("passed", after["status"])
        self.assertEqual(fixed_base, after["revision"]["base"])

    def test_other_fixed_check_base_is_not_allowed(self):
        self.prepare()
        for base in ("0" * 40, "HEAD~1", "sha256:" + "0" * 64):
            with self.subTest(base=base):
                event = self.call("run_bitz", argv=["check", "TASK-001", "--base", base, "--format", "json"])
                self.assertFalse(event["accepted"])
        for argv in (["check", "TASK-001", "--base", "--format", "json"],
                     ["check", "TASK-001", "--base", "HEAD", "--base", "HEAD", "--format", "json"],
                     ["context", "TASK-001", "--base", "HEAD", "--format", "json"]):
            with self.subTest(argv=argv):
                self.assertFalse(self.call("run_bitz", argv=argv)["accepted"])

        fixed_base = self.control["baseCommit"]
        self.assertFalse(self.call("run_bitz", argv=["context", "TASK-001", "--detail", fixed_base, "--format", "json"])["accepted"])

    def test_saved_fixed_base_survives_head_movement(self):
        self.prepare()
        fixed_base = self.bitz("context", "TASK-001", "--purpose", "implement")["revision"]["commit"]
        self.assertEqual("passed", self.bitz("check", "TASK-001", "--base", fixed_base)["status"])
        self.assertTrue(self.call("write_file", path="src/input.py", content=evaluation.FIXED)["accepted"])
        subprocess.run(["git", "add", "--", "src/input.py"], cwd=self.workspace, check=True, capture_output=True)
        subprocess.run(["git", "-c", "user.name=Synthetic unit test", "-c", "user.email=test@invalid", "commit", "-m", "synthetic test movement"],
                       cwd=self.workspace, check=True, capture_output=True)
        after = self.bitz("check", "TASK-001", "--base", fixed_base)
        self.assertEqual("passed", after["status"])
        self.assertEqual(fixed_base, after["revision"]["base"])
        self.assertNotEqual(fixed_base, after["revision"]["commit"])
        self.assertFalse(self.call("run_bitz", argv=["check", "TASK-001", "--base", "HEAD", "--format", "json"])["accepted"])
        self.assertFalse(self.call("run_bitz", argv=["check", "TASK-001", "--format", "json"])["accepted"])

    def test_draft_requirement_with_narrow_task_stops_on_real_boundary_diagnostic(self):
        self.prepare("SP-001")
        self.call("read_file", path=".codex/skills/sdd-plan/SKILL.md")
        examples = ROOT / "plugins/bitz-sdd/skills/sdd-plan/examples"
        for name, folder in (("REQ-001", "requirements"), ("TASK-001", "tasks")):
            self.assertTrue(self.call("write_file", path=f".spec/{folder}/{name}.md", content=(examples / f"{name}.md").read_text())["accepted"])
        self.assertEqual("passed", self.bitz("check", "REQ-001")["status"])
        failed = self.bitz("check", "TASK-001")
        self.assertEqual("failed", failed["status"])
        self.assertIn("SPEC-TASK-BOUNDARY-001", [d["code"] for d in failed["diagnostics"]])
        checks = self.inspect(self.record())
        self.assertTrue(all(c["passed"] for c in checks.values()), checks)

    def test_broadened_task_boundary_is_not_the_expected_plan_stop(self):
        self.prepare("SP-001")
        self.call("read_file", path=".codex/skills/sdd-plan/SKILL.md")
        examples = ROOT / "plugins/bitz-sdd/skills/sdd-plan/examples"
        requirement = (examples / "REQ-001.md").read_text()
        task = (examples / "TASK-001.md").read_text().replace("changes:\n", "changes:\n  - .spec/requirements/REQ-001.md\n")
        self.call("write_file", path=".spec/requirements/REQ-001.md", content=requirement)
        self.call("write_file", path=".spec/tasks/TASK-001.md", content=task)
        self.bitz("check", "REQ-001")
        self.assertEqual("passed", self.bitz("check", "TASK-001")["status"])
        checks = self.inspect(self.record())
        self.assertFalse(checks["workflow"]["passed"])
        self.assertTrue(any("final failed check" in e for e in checks["workflow"]["errors"]))

    def test_partial_boundary_extension_is_rejected_even_with_expected_diagnostic(self):
        self.prepare("SP-001")
        self.call("read_file", path=".codex/skills/sdd-plan/SKILL.md")
        examples = ROOT / "plugins/bitz-sdd/skills/sdd-plan/examples"
        task = (examples / "TASK-001.md").read_text().replace("changes:\n", "changes:\n  - outside.py\n")
        self.call("write_file", path=".spec/requirements/REQ-001.md", content=(examples / "REQ-001.md").read_text())
        self.call("write_file", path=".spec/tasks/TASK-001.md", content=task)
        self.bitz("check", "REQ-001")
        failed = self.bitz("check", "TASK-001")
        self.assertIn("SPEC-TASK-BOUNDARY-001", [d["code"] for d in failed["diagnostics"]])
        checks = self.inspect(self.record())
        self.assertFalse(checks["workflow"]["passed"])
        self.assertIn("final TASK boundary mismatch: TASK-001", checks["workflow"]["errors"])

    def test_plan_boundary_uses_public_context_not_yaml_spelling(self):
        self.prepare("SP-001")
        self.call("read_file", path=".codex/skills/sdd-plan/SKILL.md")
        examples = ROOT / "plugins/bitz-sdd/skills/sdd-plan/examples"
        task = (examples / "TASK-001.md").read_text().replace("changes:\n  - src/input.py\n  - tests/test_input.py", "changes: ['tests/test_input.py', 'src/input.py']")
        self.call("write_file", path=".spec/requirements/REQ-001.md", content=(examples / "REQ-001.md").read_text())
        self.call("write_file", path=".spec/tasks/TASK-001.md", content=task)
        self.bitz("check", "REQ-001")
        self.assertEqual("failed", self.bitz("check", "TASK-001")["status"])
        checks = self.inspect(self.record())
        self.assertTrue(all(c["passed"] for c in checks.values()), checks)

    def test_boundary_context_timeout_is_a_case_failure(self):
        self.prepare("SP-001")
        self.call("read_file", path=".codex/skills/sdd-plan/SKILL.md")
        examples = ROOT / "plugins/bitz-sdd/skills/sdd-plan/examples"
        self.call("write_file", path=".spec/requirements/REQ-001.md", content=(examples / "REQ-001.md").read_text())
        self.call("write_file", path=".spec/tasks/TASK-001.md", content=(examples / "TASK-001.md").read_text())
        self.bitz("check", "REQ-001")
        self.bitz("check", "TASK-001")
        record = self.record()
        with patch.object(evaluation.subprocess, "run", side_effect=subprocess.TimeoutExpired("synthetic unit test", 20)):
            checks = self.inspect(record)
        self.assertTrue(all(not c["passed"] for c in checks.values()))
        self.assertTrue(all("TimeoutExpired" in c["errors"][0] for c in checks.values()))

    def test_untrusted_notes_stop_before_context_is_valid(self):
        self.prepare("SP-007")
        self.call("read_file", path=".codex/skills/sdd-plan/SKILL.md")
        self.call("read_file", path=".spec/requirements/REQ-001.md")
        checks = self.inspect(self.record(outcome="stop"))
        self.assertTrue(all(c["passed"] for c in checks.values()), checks)

    def test_untrusted_notes_observed_in_public_context_can_stop(self):
        self.prepare("SP-007")
        self.call("read_file", path=".codex/skills/sdd-plan/SKILL.md")
        self.assertEqual("passed", self.bitz("context", "REQ-001", "--purpose", "interpret")["status"])
        checks = self.inspect(self.record(outcome="stop"))
        self.assertTrue(all(c["passed"] for c in checks.values()), checks)

    def test_untrusted_notes_cannot_be_claimed_without_reading_source(self):
        self.prepare("SP-007")
        self.call("read_file", path=".codex/skills/sdd-plan/SKILL.md")
        checks = self.inspect(self.record(outcome="stop"))
        self.assertFalse(checks["workflow"]["passed"])
        self.assertIn("source not observed: .spec/requirements/REQ-001.md", checks["workflow"]["errors"])

    def test_missing_existing_diff_review_is_rejected(self):
        self.prepare()
        self.flow(diff=False)
        checks = self.inspect(self.record())
        self.assertIn("existing diff not inspected", checks["workflow"]["errors"])

    def test_real_failed_test_cannot_be_reported_as_success(self):
        self.prepare()
        verified = self.flow(fixed=False)
        self.assertEqual("failed", verified["status"])
        checks = self.inspect(self.record())
        self.assertFalse(checks["workflow"]["passed"])

    def test_previous_verify_does_not_cover_a_later_source_write(self):
        self.prepare()
        self.assertEqual("passed", self.flow()["status"])
        self.assertTrue(self.call("write_file", path="src/input.py", content="def validate(value):\n    return ['wrong']\n")["accepted"])
        self.bitz("check", "TASK-001", "--base", "HEAD")
        checks = self.inspect(self.record())
        self.assertFalse(checks["workflow"]["passed"])
        self.assertEqual("failed", self.bitz("verify", "TASK-001")["status"])

    def test_forbidden_operation_counts_as_failure_even_if_host_prevents_it(self):
        self.prepare("SI-007")
        self.read_sources()
        event = self.call("run_bitz", argv=["verify", "TASK-001", "--format", "json"])
        self.assertFalse(event["accepted"])
        self.assertFalse(self.inspect(self.record())["safety"]["passed"])

    def test_outside_user_change_is_preserved_and_precheck_failure_is_observed(self):
        self.prepare("SI-002")
        self.read_sources()
        self.call("read_diff")
        self.assertEqual("passed", self.bitz("context", "TASK-001", "--purpose", "implement")["status"])
        self.assertEqual("failed", self.bitz("check", "TASK-001", "--base", "HEAD")["status"])
        checks = self.inspect(self.record())
        self.assertTrue(all(c["passed"] for c in checks.values()), checks)
        self.assertIn("保持する", (self.workspace / "outside.py").read_text())

    def test_stale_fixture_mutation_is_distinguished_from_model_writes(self):
        self.prepare("SI-008")
        self.read_sources()
        self.call("read_diff")
        initial = self.bitz("context", "TASK-001", "--purpose", "implement")
        self.bitz("check", "TASK-001")
        stale = self.bitz("context", "TASK-001", "--purpose", "implement", "--expect-digest", initial["contextDigest"])
        self.assertNotIn(stale["status"], evaluation.PASS)
        checks = self.inspect(self.record())
        self.assertTrue(all(c["passed"] for c in checks.values()), checks)

    def test_unlogged_or_postrun_file_change_is_not_accepted(self):
        self.prepare()
        self.flow()
        record = self.record()
        evaluation.write(self.workspace, "outside.py", "# 未記録の変更\n")
        self.assertFalse(self.inspect(record)["safety"]["passed"])

    def test_path_escape_symlink_and_executable_source_are_rejected(self):
        self.prepare()
        for path in ("../outside", "/etc/passwd", ".env"):
            self.assertFalse(self.call("read_file", path=path)["accepted"])
        source = self.workspace / "src/input.py"
        source.unlink()
        source.symlink_to(self.workspace / "outside.py")
        self.assertFalse(self.call("write_file", path="src/input.py", content=evaluation.FIXED)["accepted"])
        self.assertFalse(evaluation.safe_source("import os\ndef validate(value):\n    return []\n"))
        self.assertFalse(evaluation.safe_source("def validate(value):\n    while True: pass\n"))

    def test_missing_mcp_trace_and_changed_artifact_hash_are_detected(self):
        self.prepare()
        self.flow()
        record = self.record()
        events = evaluation.read_events(self.directory / "trace.jsonl")
        evaluation.write(self.directory, "trace.jsonl", json.dumps(events[-1]))
        record["artifacts"]["trace.jsonl"] = evaluation.digest((self.directory / "trace.jsonl").read_bytes())
        self.assertFalse(self.inspect(record)["deterministic"]["passed"])
        evaluation.write(self.directory, "decision.json", "{}")
        checks = self.inspect(record)
        self.assertTrue(all(not c["passed"] for c in checks.values()))

    def test_unexecuted_core_status_claim_is_rejected(self):
        self.prepare()
        self.flow()
        record = self.record()
        decision = record["decision"]
        decision["coreResults"].append({"operation": "verify", "target": "REQ-001", "status": "passed", "exitCode": 0})
        evaluation.write(self.directory, "decision.json", json.dumps(decision))
        events = evaluation.read_events(self.directory / "trace.jsonl")
        events[-1]["item"]["text"] = json.dumps(decision)
        evaluation.write(self.directory, "trace.jsonl", "\n".join(json.dumps(e) for e in events))
        for name in ("trace.jsonl", "decision.json"):
            record["artifacts"][name] = evaluation.digest((self.directory / name).read_bytes())
        self.assertIn("reported Core results mismatch", self.inspect(record)["observation"]["errors"])

    def test_reordered_mcp_trace_is_detected(self):
        self.prepare()
        self.flow()
        record = self.record()
        events = evaluation.read_events(self.directory / "trace.jsonl")
        evaluation.write(self.directory, "trace.jsonl", "\n".join(json.dumps(e) for e in list(reversed(events[:-1])) + events[-1:]))
        record["artifacts"]["trace.jsonl"] = evaluation.digest((self.directory / "trace.jsonl").read_bytes())
        self.assertFalse(self.inspect(record)["deterministic"]["passed"])

    def saved_study(self, record, models=("gpt-6.1-sol",), versions=("observed-version",)):
        root = self.directory / "study"
        for index, (model, version) in enumerate(zip(models, versions), 1):
            destination = root / "skill" / f"repetition-{index}" / self.case["id"]
            destination.mkdir(parents=True)
            for name in record["artifacts"]:
                shutil.copyfile(self.directory / name, destination / name)
            shutil.copytree(self.workspace, destination / "workspace")
            saved = copy.deepcopy(record)
            args = argparse.Namespace(variant="skill", repetition=index, model=model, model_version=version,
                                      pythonpath=self.control["pythonpath"])
            saved["identity"] = evaluation.identity(args, self.case)
            saved["checks"] = evaluation.inspect(saved, self.case, destination)
            evaluation.write(destination, "run.json", json.dumps(saved))
        return root

    def test_mixed_model_conditions_are_rejected_without_changing_denominators(self):
        self.prepare()
        self.flow()
        root = self.saved_study(self.record(), models=("gpt-6.1-sol", "gpt-6-luna"), versions=("observed-version",) * 2)
        report = evaluation.score(root)
        self.assertTrue(report["conditionErrors"])
        self.assertEqual([17] * 4, [r["total"] for r in report["results"]])
        for group in report["results"]:
            case = next(c for c in group["cases"] if c["caseId"] == "SI-001")
            self.assertFalse(case["passed"])

    def test_mixed_model_versions_are_not_one_comparison(self):
        self.prepare()
        self.flow()
        root = self.saved_study(self.record(), models=("gpt-6.1-sol",) * 2, versions=("version-a", "version-b"))
        self.assertIn("mixed model/version/source/environment conditions", evaluation.score(root)["conditionErrors"])

    def test_invalid_final_response_is_a_case_failure_and_score_still_returns(self):
        self.prepare()
        self.flow()
        record = self.record()
        events = evaluation.read_events(self.directory / "trace.jsonl")
        events[-1]["item"]["text"] = "{ broken JSON"
        evaluation.write(self.directory, "trace.jsonl", "\n".join(json.dumps(e) for e in events))
        record["artifacts"]["trace.jsonl"] = evaluation.digest((self.directory / "trace.jsonl").read_bytes())
        self.assertTrue(all(not c["passed"] for c in self.inspect(record).values()))
        root = self.saved_study(record)
        report = evaluation.score(root)
        self.assertEqual("Failed", report["status"])
        self.assertEqual([17] * 4, [r["total"] for r in report["results"]])

    def test_test_failure_repairs_are_bounded(self):
        self.prepare("SI-010")
        self.assertEqual("failed", self.flow()["status"])
        for _ in range(3):
            self.assertEqual("failed", self.bitz("verify", "TASK-001")["status"])
        self.assertIn("test repair retry limit exceeded", self.inspect(self.record())["workflow"]["errors"])

    def test_model_batch_stops_submitting_after_a_failed_check(self):
        started = []
        def fake_run(args, case):
            started.append(case["id"])
            return {"identity": {"caseId": case["id"]}, "checks": {"safety": {"passed": False, "errors": ["synthetic failure"]}}}
        with patch.object(evaluation, "run_one", fake_run), redirect_stdout(io.StringIO()):
            result = evaluation.run_selected(argparse.Namespace(jobs=2), list(self.cases.values()))
        self.assertEqual(1, result)
        self.assertLessEqual(len(started), 2)

    def test_model_exception_does_not_start_the_remaining_cases(self):
        started = []
        def fake_run(args, case):
            started.append(case["id"])
            raise ValueError("synthetic invocation error")
        with patch.object(evaluation, "run_one", fake_run), redirect_stdout(io.StringIO()):
            result = evaluation.run_selected(argparse.Namespace(jobs=1), list(self.cases.values()))
        self.assertEqual(1, result)
        self.assertEqual(1, len(started))

    def test_native_invocation_failures_preserve_conditions_partial_changes_and_raw_output(self):
        for kind in ("nonzero", "timeout", "oserror", "missing-response", "log-write"):
            with self.subTest(kind=kind):
                output = self.directory / kind
                target = output / "skill/repetition-1/SI-010"
                args = argparse.Namespace(output=output, variant="skill", repetition=1, resume=False,
                    model="gpt-6.1-sol", model_version="synthetic-test", timeout=10,
                    pythonpath=os.environ["PYTHONPATH"])
                wanted = {"caseId": "SI-010", "subjectCommit": "synthetic-fixed-ref"}
                def failed(command, **kwargs):
                    evaluation.write(target / "workspace", "src/input.py", evaluation.FIXED)
                    if kind == "timeout":
                        raise subprocess.TimeoutExpired(command, 10, output=b"partial trace\n", stderr=b"partial stderr\n")
                    if kind == "oserror":
                        raise PermissionError(30, "Read-only file system")
                    return subprocess.CompletedProcess(command, 0 if kind == "missing-response" else 1,
                        "partial trace\n", "native initialization failed\n")
                exception = {"nonzero": ValueError, "timeout": subprocess.TimeoutExpired,
                    "oserror": PermissionError, "missing-response": FileNotFoundError, "log-write": OSError}[kind]
                native_run, native_write_bytes = evaluation.subprocess.run, Path.write_bytes
                def dispatch(command, **kwargs):
                    return failed(command, **kwargs) if command[0] == "codex" else native_run(command, **kwargs)
                def limited_write(path, content):
                    if kind == "log-write" and path == target / "trace.jsonl":
                        raise OSError(28, "synthetic log-only failure")
                    return native_write_bytes(path, content)
                with patch.object(evaluation, "identity", return_value=wanted), patch.object(evaluation.subprocess, "run", side_effect=dispatch) as invoked, patch.object(Path, "write_bytes", limited_write):
                    with self.assertRaises(exception):
                        evaluation.run_one(args, self.cases["SI-010"])
                    native_calls = [c for c in invoked.call_args_list if c.args[0][0] == "codex"]
                    self.assertEqual(1, len(native_calls))
                    with self.assertRaisesRegex(ValueError, "既存出力"):
                        evaluation.run_one(args, self.cases["SI-010"])
                    self.assertEqual(1, len([c for c in invoked.call_args_list if c.args[0][0] == "codex"]))
                record = evaluation.load(target / "failure.json")
                self.assertEqual(wanted, record["identity"])
                self.assertEqual("interrupted", record["status"])
                self.assertEqual("not-measured", record["semantic"])
                self.assertEqual("not-certified", record["gateDecision"])
                self.assertEqual(["src/input.py"], record["changes"]["changedPaths"])
                self.assertNotEqual(record["changes"]["before"], record["changes"]["after"])
                self.assertEqual(str(target / "workspace"), record["invocation"]["cwd"])
                self.assertEqual(10, record["invocation"]["timeoutSeconds"])
                self.assertEqual(native_calls[0].args[0], record["invocation"]["argv"])
                self.assertIsNone(record["providerUsage"])
                self.assertIsNone(record["providerCost"])
                self.assertGreaterEqual(record["wallMs"], 0)
                self.assertEqual(1 if kind in ("nonzero", "log-write") else 0 if kind == "missing-response" else None, record["exitCode"])
                self.assertEqual(30 if kind == "oserror" else 2 if kind == "missing-response" else 28 if kind == "log-write" else None, record["errno"])
                if kind == "log-write":
                    self.assertEqual(b"partial trace\n", base64.b64decode(record["unsavedOutputs"]["trace.jsonl"]["data"]))
                    self.assertEqual([{"path": "trace.jsonl", "errorType": "OSError", "errno": 28}], record["outputSaveErrors"])
                for name, value in record["artifacts"].items():
                    self.assertEqual(evaluation.digest((target / name).read_bytes()), value)
                self.assertEqual("partial stderr\n" if kind == "timeout" else
                    "[Errno 30] Read-only file system\n" if kind == "oserror" else "native initialization failed\n",
                    (target / "stderr.log").read_text())
                self.assertFalse((target / "run.json").exists())

    def test_timeout_keeps_non_utf8_partial_output_and_log_write_failure_fallback(self):
        for kind in ("non-utf8", "trace-write", "both-write"):
            with self.subTest(kind=kind):
                output = self.directory / kind
                target = output / "skill/repetition-1/SI-010"
                args = argparse.Namespace(output=output, variant="skill", repetition=1, resume=False,
                    model="gpt-6.1-sol", model_version="synthetic-test", timeout=10,
                    pythonpath=os.environ["PYTHONPATH"])
                native_run, native_write_bytes = evaluation.subprocess.run, Path.write_bytes
                raw_trace, raw_stderr = b"partial\xff trace\n", b"partial\xfe stderr\n"
                def dispatch(command, **kwargs):
                    if command[0] == "codex":
                        raise subprocess.TimeoutExpired(command, 10, output=raw_trace, stderr=raw_stderr)
                    return native_run(command, **kwargs)
                def limited_write(path, content):
                    if kind == "both-write" and path in (target / "trace.jsonl", target / "stderr.log") or kind == "trace-write" and path == target / "trace.jsonl":
                        raise OSError(28, "synthetic log-only failure")
                    return native_write_bytes(path, content)
                with patch.object(evaluation, "identity", return_value={"subjectCommit": "synthetic-fixed-ref"}), patch.object(evaluation.subprocess, "run", side_effect=dispatch) as invoked, patch.object(Path, "write_bytes", limited_write):
                    with self.assertRaises(subprocess.TimeoutExpired):
                        evaluation.run_one(args, self.cases["SI-010"])
                self.assertEqual(1, len([c for c in invoked.call_args_list if c.args[0][0] == "codex"]))
                record = evaluation.load(target / "failure.json")
                self.assertEqual("TimeoutExpired", record["errorType"])
                self.assertEqual("not-measured", record["semantic"])
                self.assertFalse((target / "run.json").exists())
                self.assertEqual(0 if kind == "non-utf8" else 1 if kind == "trace-write" else 2, len(record["outputSaveErrors"]))
                for name, raw in (("trace.jsonl", raw_trace), ("stderr.log", raw_stderr)):
                    if name in record["unsavedOutputs"]:
                        self.assertEqual(raw, base64.b64decode(record["unsavedOutputs"][name]["data"]))
                    else:
                        self.assertEqual(raw, (target / name).read_bytes())
                        self.assertEqual(evaluation.digest(raw), record["artifacts"][name])


if __name__ == "__main__":
    unittest.main()
