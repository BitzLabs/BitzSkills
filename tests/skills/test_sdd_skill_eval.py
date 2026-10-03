"""SDD評価ホストと採点の試験。ここで作るモデルtraceは合成の単体試験用。"""

import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

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


if __name__ == "__main__":
    unittest.main()
