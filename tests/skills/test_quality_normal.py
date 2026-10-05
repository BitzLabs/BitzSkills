"""Q0/Q1の実差分・試験許可・有限比較をモデルなしで実接続する。"""
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


class QualityNormalTests(unittest.TestCase):
    def setUp(self):
        scratch = ROOT / ".venv"
        scratch.mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix="quality-normal-test-", dir=scratch)
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.cases = {c["caseId"]: c for c in evaluate.load(HERE / "normal-cases.json")["cases"]}

    def prepared(self, case_id, variant="baseline", suffix=""):
        parent = self.directory / (case_id + "-" + variant + suffix)
        parent.mkdir()
        workspace, control = evaluate.setup(parent, self.cases[case_id], variant, "synthetic-normal-review")
        log = parent / "host.jsonl"
        log.write_text("")
        return Host(workspace, control, log), workspace, control

    def changed(self, workspace, control):
        env = preflight.environment()
        names = preflight.git(["diff", "--name-only", control["baseCommit"], control["subjectCommit"]], workspace, env).decode().splitlines()
        self.assertEqual(b"", preflight.git(["status", "--porcelain"], workspace, env))
        return names

    def test_document_diff_has_static_heading_evidence_without_test_execution(self):
        with patch.object(preflight, "run", wraps=preflight.run) as invoked:
            host, workspace, control = self.prepared("QR-004")
        self.assertEqual(["README.md"], self.changed(workspace, control))
        original = preflight.git(["show", control["baseCommit"] + ":README.md"], workspace, preflight.environment())
        self.assertEqual((HERE / "fixtures/bases/review-document-readme.md").read_bytes(), original)
        self.assertIn("-# Local inspection", control["diff"])
        self.assertIn("+# ローカルの検査手順", control["diff"])
        self.assertFalse(control["allowTests"])
        self.assertFalse(any(c.args[0][0] == sys.executable and c.args[0][-1] == "test_fixture.py" for c in invoked.call_args_list))
        for name in self.cases["QR-004"]["additionalReadFiles"]:
            self.assertFalse(host.call("read_file", {"path": name})["isError"])
        self.assertNotIn("run_fixture_test", {t["name"] for t in host.tools})
        with patch("host.subprocess.run", side_effect=AssertionError("must not run tests")):
            self.assertTrue(host.call("run_fixture_test", {})["isError"])

    def test_local_fix_runs_three_assertions_and_preserves_the_actual_base(self):
        host, workspace, control = self.prepared("QR-005")
        self.assertEqual(["target.py"], self.changed(workspace, control))
        original = preflight.git(["show", control["baseCommit"] + ":target.py"], workspace, preflight.environment())
        self.assertEqual((HERE / "fixtures/bases/review-local-fix-target.py").read_bytes(), original)
        self.assertIn('-    return ["empty"]', control["diff"])
        self.assertIn('+    return ["empty"] if value == "" else []', control["diff"])
        before = preflight.files(workspace)
        for name in ("target.py", "test_fixture.py"):
            self.assertFalse(host.call("read_file", {"path": name})["isError"])
        result = json.loads(host.call("run_fixture_test", {})["content"][0]["text"])
        self.assertEqual(0, result["exitCode"])
        self.assertIn("Ran 3 tests", result["stderr"])
        self.assertEqual(before, preflight.files(workspace))
        self.changed(workspace, control)

    def test_common_inputs_match_across_variants_and_repetitions_without_answer_leak(self):
        for case_id in self.cases:
            with self.subTest(case=case_id):
                controls = [self.prepared(case_id, variant, "-r" + str(r))[2] for r in (1, 2) for variant in ("skill", "baseline")]
                baseline = controls[1]
                for control in controls:
                    for key in ("baseCommit", "subjectCommit", "fixtureFiles", "diff", "allowTests"):
                        self.assertEqual(baseline[key], control[key], key)
                    for name, value in baseline["readableFiles"].items():
                        self.assertEqual(value, control["readableFiles"][name])
                    extra = set(control["readableFiles"]) - set(baseline["readableFiles"])
                    self.assertTrue(all(n.startswith("resources/bitz-quality/skills/quality-review/") for n in extra))
                    for forbidden in ("normal-cases.json", "normal-protocol.json", "normal-approval.json", "review-document-readme.md", "review-local-fix-target.py"):
                        self.assertFalse(any(Path(n).name == forbidden for n in control["readableFiles"]))

    def test_exhausted_normal_budget_preserves_old_ledgers_without_backend(self):
        approval_path = HERE / "normal-approval.json"
        approval = evaluate.load(approval_path)
        old = self.directory / "quality-pilot-old-authorization.json"
        old.write_text('{"attemptCount": 8, "interruptionPreserved": true}\n')
        original = old.read_bytes()
        with patch("evaluate.authorization_directory", return_value=self.directory):
            with evaluate.authorization_lock(self.directory / "normal", approval, approval_path) as (path, ledger):
                self.assertNotEqual(path, old)
                self.assertEqual(0, ledger["attemptCount"])
                ledger["attemptCount"] = 8
                evaluate.write(path, ledger)
            capped = path.read_bytes()
            with patch("preflight.git", return_value=b""), patch("evaluate.subprocess.run", side_effect=AssertionError("must not invoke backend")):
                with self.assertRaisesRegex(ValueError, "budget exhausted"):
                    evaluate.measure(SimpleNamespace(protocol=HERE / "normal-protocol.json", approval=approval_path,
                        output=self.directory / "normal", timeout=600))
            self.assertEqual(capped, path.read_bytes())
        self.assertEqual(original, old.read_bytes())

    def test_preparation_and_mixed_contracts_stop_before_ledger_or_backend(self):
        catalog = evaluate.load(HERE / "normal-cases.json")
        self.assertEqual("preparation_only", catalog["status"])
        self.assertEqual(0, catalog["newModelTrajectories"])
        protocol = evaluate.load(HERE / "normal-protocol.json")
        approval = evaluate.load(HERE / "normal-approval.json")
        self.assertEqual(list(self.cases.values()), protocol["cases"])
        self.assertEqual(sha((HERE / "normal-protocol.json").read_bytes()), approval["protocolSha256"])
        self.assertEqual(8, len(protocol["cases"]) * len(protocol["variants"]) * protocol["repetitions"])
        self.assertEqual(8, protocol["maximumNewTrajectories"])
        self.assertEqual(8, approval["maximumNewTrajectories"])
        self.assertEqual(0, protocol["automaticRetries"])
        self.assertEqual(600, protocol["timeoutSeconds"])
        self.assertFalse(approval["reuseExpansionBudget"])
        self.assertTrue(approval["stopOnAnyFailure"])
        with patch("evaluate.authorization_lock", side_effect=AssertionError("must not open ledger")), patch("evaluate.subprocess.run", side_effect=AssertionError("must not invoke model")):
            pairs = [("normal-cases.json", "normal-approval.json"), ("normal-protocol.json", "expansion-approval.json"), ("expansion-protocol.json", "normal-approval.json")]
            for protocol_name, approval_name in pairs:
                with self.subTest(protocol=protocol_name, approval=approval_name):
                    with self.assertRaisesRegex(ValueError, "only fixed"):
                        evaluate.measure(SimpleNamespace(protocol=HERE / protocol_name, approval=HERE / approval_name, output=self.directory / "never-created", timeout=600))
        self.assertFalse((self.directory / "never-created").exists())


if __name__ == "__main__":
    unittest.main()
