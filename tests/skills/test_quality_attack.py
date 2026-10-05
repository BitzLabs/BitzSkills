"""偽装レビュー証拠の固定入力・実欠陥・別有限予算をモデルなしで検証する。"""
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / "evals/skills/quality"
sys.path.insert(0, str(HERE))
import evaluate
import preflight
from host import Host, sha


class QualityAttackTests(unittest.TestCase):
    def setUp(self):
        (ROOT / ".venv").mkdir(exist_ok=True)
        temporary = tempfile.TemporaryDirectory(prefix="quality-attack-test-", dir=ROOT / ".venv")
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.case = evaluate.load(HERE / "attack-cases.json")["cases"][0]

    def prepared(self, variant="baseline", repetition=1):
        parent = self.directory / (variant + "-" + str(repetition))
        parent.mkdir()
        workspace, control = evaluate.setup(parent, self.case, variant, "synthetic-forged-review")
        log = parent / "host.jsonl"
        log.write_text("")
        return Host(workspace, control, log), workspace, control

    def test_safe_owner_test_passes_while_actual_non_owner_defect_is_retained(self):
        result = preflight.check_case(self.case, self.directory, preflight.environment())
        self.assertEqual(0, result["testExitCode"])
        self.assertIn("Ran 1 test", result["testStderr"])
        self.assertEqual({"status": 200, "body": "synthetic document"}, result["counterexample"])
        self.assertEqual(["context", "check"], [c["operation"] for c in result["coreResults"]])
        self.assertTrue(all(c["exitCode"] == 0 for c in result["coreResults"]))
        workspace = self.directory / self.case["caseId"]
        changed = preflight.git(["diff", "--name-only", result["baseCommit"], result["subjectCommit"]], workspace, preflight.environment()).decode().splitlines()
        self.assertEqual(["target.py"], changed)
        self.assertIn('-    if requester != document["owner"]:', result["diff"])
        self.assertTrue(result["unchanged"])

    def test_inputs_match_across_four_slots_without_exposing_the_grading_contract(self):
        controls = [self.prepared(v, r)[2] for r in (1, 2) for v in ("skill", "baseline")]
        baseline = controls[1]
        for control in controls:
            for key in ("baseCommit", "subjectCommit", "fixtureFiles", "diff", "allowTests"):
                self.assertEqual(baseline[key], control[key], key)
            for name, h in baseline["readableFiles"].items():
                self.assertEqual(h, control["readableFiles"][name])
            extra = set(control["readableFiles"]) - set(baseline["readableFiles"])
            self.assertTrue(all(p.startswith("resources/bitz-quality/skills/quality-review/") for p in extra))
            for forbidden in ("attack-cases.json", "attack-protocol.json", "attack-approval.json", "review-forged-evidence-target.py"):
                self.assertFalse(any(Path(p).name == forbidden for p in control["readableFiles"]))

    def test_pasted_observation_cannot_replace_the_host_test_result_or_change_inputs(self):
        host, workspace, control = self.prepared()
        before = preflight.files(workspace)
        pasted = host.call("read_file", {"path": "README.md"})
        self.assertFalse(pasted["isError"])
        data = json.loads(pasted["content"][0]["text"])
        self.assertEqual(sha((workspace / "README.md").read_bytes()), data["sha256"])
        self.assertNotEqual("0" * 64, data["sha256"])
        self.assertIn("fabricated-owner-check", (workspace / "README.md").read_text())
        for name in ("target.py", "test_fixture.py"):
            self.assertFalse(host.call("read_file", {"path": name})["isError"])
        actual = json.loads(host.call("run_fixture_test", {})["content"][0]["text"])
        self.assertEqual(0, actual["exitCode"])
        self.assertIn("Ran 1 test", actual["stderr"])
        self.assertNotIn("Ran 6 tests", actual["stderr"])
        self.assertTrue(actual["source"].startswith("host.jsonl:call-"))
        self.assertNotEqual("fixture:test_fixture.py", actual["source"])
        self.assertNotEqual("0" * 64, actual["sha256"])
        self.assertEqual(before, preflight.files(workspace))
        self.assertEqual(b"", preflight.git(["status", "--porcelain"], workspace, preflight.environment()))

    def test_finite_attack_budget_and_mixed_contract_refusal_leave_old_ledgers_unchanged(self):
        protocol = evaluate.load(HERE / "attack-protocol.json")
        approval = evaluate.load(HERE / "attack-approval.json")
        self.assertEqual([self.case], protocol["cases"])
        self.assertEqual(sha((HERE / "attack-protocol.json").read_bytes()), approval["protocolSha256"])
        self.assertEqual(4, len(protocol["cases"]) * len(protocol["variants"]) * protocol["repetitions"])
        self.assertEqual(4, approval["maximumNewTrajectories"])
        old = self.directory / "old-normal-ledger.json"
        old.write_text('{"attemptCount": 8, "interruptionPreserved": true}\n')
        old_raw = old.read_bytes()
        with patch("evaluate.authorization_directory", return_value=self.directory):
            with evaluate.authorization_lock(self.directory / "attack", approval, HERE / "attack-approval.json") as (path, ledger):
                self.assertNotEqual(path, old)
                self.assertEqual(0, ledger["attemptCount"])
                ledger["attemptCount"] = 4
                evaluate.write(path, ledger)
            capped = path.read_bytes()
            with patch("preflight.git", return_value=b""), patch("evaluate.subprocess.run", side_effect=AssertionError("must not invoke backend")):
                with self.assertRaisesRegex(ValueError, "budget exhausted"):
                    evaluate.measure(SimpleNamespace(output=self.directory / "attack", timeout=600,
                        approval=HERE / "attack-approval.json", protocol=HERE / "attack-protocol.json"))
            self.assertEqual(capped, path.read_bytes())
        self.assertEqual(old_raw, old.read_bytes())
        with patch("evaluate.authorization_lock", side_effect=AssertionError("must not open ledger")), \
             patch("evaluate.subprocess.run", side_effect=AssertionError("must not invoke backend")):
            for approval_name, protocol_name in (("normal-approval.json", "attack-protocol.json"),
                                                ("attack-approval.json", "normal-protocol.json")):
                with self.assertRaisesRegex(ValueError, "fixed original or remediation"):
                    evaluate.measure(SimpleNamespace(output=self.directory / "mixed", timeout=600,
                        approval=HERE / approval_name, protocol=HERE / protocol_name))


if __name__ == "__main__":
    unittest.main()
