"""拡張入力・許可・原差分の実接続試験。モデルやCIは実行しない。"""
import copy
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


class QualityExpansionTests(unittest.TestCase):
    def setUp(self):
        scratch = ROOT / ".venv"
        scratch.mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix="quality-expansion-test-", dir=scratch)
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.cases = {c["caseId"]: c for c in evaluate.load(HERE / "expansion-cases.json")["cases"]}

    def prepared(self, case_id, *, variant="baseline", parent=None):
        parent = parent or self.directory
        parent.mkdir(exist_ok=True)
        workspace, control = evaluate.setup(parent, self.cases[case_id], variant, "synthetic-expanded-review")
        log = parent / "host.jsonl"
        log.write_text("")
        return Host(workspace, control, log), workspace, control

    def test_unknown_input_and_host_keep_tests_unexecuted(self):
        with patch.object(preflight, "run", wraps=preflight.run) as invoked:
            host, workspace, control = self.prepared("QR-002")
        self.assertFalse(any(c.args[0][0] == sys.executable and c.args[0][-1] == "test_fixture.py"
                             for c in invoked.call_args_list))
        self.assertFalse(control["allowTests"])
        self.assertNotIn("run_fixture_test", {t["name"] for t in host.tools})
        with patch("host.subprocess.run", side_effect=AssertionError("must not execute unapproved test")):
            self.assertTrue(host.call("run_fixture_test", {})["isError"])
        self.assertIn('-    return ["empty"]', control["diff"])
        self.assertIn('+    return ["入力エラー"]', control["diff"])
        self.assertEqual(b"", preflight.git(["status", "--porcelain"], workspace, preflight.environment()))

    def test_supply_chain_diff_is_real_and_only_fixed_python_test_runs(self):
        with patch.object(preflight, "run", wraps=preflight.run) as invoked:
            host, workspace, control = self.prepared("QR-003")
        self.assertTrue(control["allowTests"])
        changed = preflight.git(["diff", "--name-only", control["baseCommit"], control["subjectCommit"]], workspace, preflight.environment()).decode().splitlines()
        self.assertEqual([".github/workflows/release.yml"], changed)
        original = preflight.git(["show", control["baseCommit"] + ":.github/workflows/release.yml"], workspace, preflight.environment())
        self.assertEqual((HERE / "fixtures/bases/review-supply-chain-workflow.yml").read_bytes(), original)
        self.assertIn("+  pull_request_target:", control["diff"])
        self.assertIn("+          git fetch origin", control["diff"])
        self.assertIn("+          bash ci/publish.sh", control["diff"])
        self.assertFalse(any(c.args[0][0] in {"bash", "curl", "gh"} for c in invoked.call_args_list))
        for name in ("target.py", "test_fixture.py"):
            self.assertFalse(host.call("read_file", {"path": name})["isError"])
        result = json.loads(host.call("run_fixture_test", {})["content"][0]["text"])
        self.assertEqual(0, result["exitCode"])
        self.assertIn("Ran 1 test", result["stderr"])
        with patch("host.subprocess.run", side_effect=AssertionError("must not run workflow")):
            self.assertTrue(host.call("run_workflow", {"path": ".github/workflows/release.yml"})["isError"])

    def test_expansion_variant_inputs_match_without_expected_answer_leaks(self):
        for case_id in self.cases:
            with self.subTest(case=case_id):
                _, _, skill = self.prepared(case_id, variant="skill", parent=self.directory / (case_id + "-skill"))
                _, _, baseline = self.prepared(case_id, parent=self.directory / (case_id + "-baseline"))
                self.assertEqual(skill["subjectCommit"], baseline["subjectCommit"])
                self.assertEqual(skill["baseCommit"], baseline["baseCommit"])
                self.assertEqual(skill["fixtureFiles"], baseline["fixtureFiles"])
                self.assertEqual(skill["diff"], baseline["diff"])
                for name, value in baseline["readableFiles"].items():
                    self.assertEqual(value, skill["readableFiles"][name])
                extra = set(skill["readableFiles"]) - set(baseline["readableFiles"])
                self.assertTrue(extra)
                self.assertTrue(all(n.startswith("resources/bitz-quality/skills/quality-review/") for n in extra))
                for forbidden in ("expansion-cases.json", "expansion-sources.md", "review-supply-chain-workflow.yml", "review-unknown-target.py"):
                    self.assertFalse(any(Path(n).name == forbidden for n in baseline["readableFiles"]))

    def test_preparation_catalog_cannot_start_a_paid_measurement(self):
        catalog = evaluate.load(HERE / "expansion-cases.json")
        self.assertEqual("preparation_only", catalog["status"])
        self.assertEqual(0, catalog["newModelTrajectories"])
        with patch("evaluate.authorization_lock", side_effect=AssertionError("must not open ledger")), patch("preflight.git", side_effect=AssertionError("must stop before workspace access")), patch("evaluate.subprocess.run", side_effect=AssertionError("must not invoke model")):
            with self.assertRaisesRegex(ValueError, "only fixed"):
                evaluate.measure(SimpleNamespace(protocol=HERE / "expansion-cases.json", output=self.directory / "must-not-exist", timeout=10))
        self.assertFalse((self.directory / "must-not-exist").exists())

    def test_expansion_contract_keeps_inputs_finite_and_mixed_pairs_cannot_start(self):
        protocol = evaluate.load(HERE / "expansion-protocol.json")
        approval = evaluate.load(HERE / "expansion-approval.json")
        self.assertEqual(list(self.cases.values()), protocol["cases"])
        self.assertEqual(sha((HERE / "expansion-protocol.json").read_bytes()), approval["protocolSha256"])
        self.assertEqual("gpt-6.1-sol", protocol["model"])
        self.assertEqual(["skill", "baseline"], protocol["variants"])
        self.assertEqual(2, protocol["repetitions"])
        self.assertEqual(8, len(protocol["cases"]) * len(protocol["variants"]) * protocol["repetitions"])
        self.assertEqual(8, protocol["maximumNewTrajectories"])
        self.assertEqual(8, approval["maximumNewTrajectories"])
        self.assertEqual(1, protocol["independentPreparationReviews"])
        self.assertEqual(8, protocol["independentTrajectoryReviews"])
        self.assertEqual(600, protocol["timeoutSeconds"])
        self.assertEqual(0, protocol["automaticRetries"])
        self.assertFalse(protocol["baselineSemanticFailureContinuation"])
        self.assertTrue(approval["stopOnAnyFailure"])
        self.assertFalse(approval["reuseOriginalBudget"])
        self.assertFalse(approval["reuseSddBudget"])
        with patch("evaluate.authorization_lock", side_effect=AssertionError("must not open ledger")), patch("evaluate.subprocess.run", side_effect=AssertionError("must not invoke model")):
            for field in ("approval", "protocol"):
                args = dict(output=self.directory / "must-not-exist", timeout=600,
                    approval=HERE / "expansion-approval.json", protocol=HERE / "expansion-protocol.json")
                args[field] = HERE / ("shared-format-" + field + ".json")
                with self.assertRaisesRegex(ValueError, "only fixed"):
                    evaluate.measure(SimpleNamespace(**args))
        self.assertFalse((self.directory / "must-not-exist").exists())

    def test_expansion_cap_uses_separate_persistent_ledger_and_no_backend(self):
        approval_path = HERE / "expansion-approval.json"
        approval = evaluate.load(approval_path)
        original = self.directory / "quality-pilot-authorization.json"
        evaluate.write(original, {"output": "original-output", "attemptCount": 2,
                                  "approvalSha256": sha((HERE / "approval.json").read_bytes())})
        before = original.read_bytes()
        with patch("evaluate.authorization_directory", return_value=self.directory):
            with evaluate.authorization_lock(self.directory / "expanded", approval, approval_path) as (path, ledger):
                self.assertNotEqual(path, original)
                self.assertEqual(0, ledger["attemptCount"])
                ledger["attemptCount"] = 8
                evaluate.write(path, ledger)
            capped = path.read_bytes()
            with patch("preflight.git", return_value=b""), patch("evaluate.subprocess.run", side_effect=AssertionError("must not invoke backend")):
                with self.assertRaisesRegex(ValueError, "budget exhausted"):
                    evaluate.measure(SimpleNamespace(output=self.directory / "expanded", timeout=600,
                        approval=approval_path, protocol=HERE / "expansion-protocol.json"))
            self.assertEqual(capped, path.read_bytes())
        self.assertEqual(before, original.read_bytes())

    def test_invalid_case_paths_and_permission_shapes_stop_before_copy(self):
        mutations = [("caseId", "../escape"), ("fixture", "../escape"), ("fixture", "/tmp/escape"),
            ("baseFiles", {"../escape": "fixtures/bases/review-unknown-target.py"}),
            ("baseFiles", {"target.py": "../escape"}), ("baseFiles", {"missing.py": "fixtures/bases/review-unknown-target.py"}),
            ("additionalReadFiles", [".git/config"]), ("additionalReadFiles", ["missing.txt"]),
            ("additionalReadFiles", [{}]), ("testExecution", True), ("testExecution", "allow-all")]
        for field, value in mutations:
            with self.subTest(field=field, value=value), patch.object(preflight.shutil, "copytree", side_effect=AssertionError("must reject before copy")):
                case = {**self.cases["QR-002"], field: value}
                with self.assertRaises(ValueError):
                    preflight.check_case(case, self.directory, preflight.environment())

    def test_fixture_symlinks_and_git_metadata_are_rejected_without_reading_targets(self):
        fixture = self.directory / "fixtures/unsafe"
        fixture.mkdir(parents=True)
        (fixture / "linked").symlink_to(self.directory / "synthetic-unread-target")
        case = {**self.cases["QR-002"], "fixture": "fixtures/unsafe"}
        with patch.object(preflight, "HERE", self.directory), patch.object(preflight.shutil, "copytree", side_effect=AssertionError("must not copy")):
            with self.assertRaisesRegex(ValueError, "symlink"):
                preflight.check_case(case, self.directory, preflight.environment())
            (fixture / "linked").unlink()
            (fixture / ".git").mkdir()
            with self.assertRaisesRegex(ValueError, "relative path"):
                preflight.check_case(case, self.directory, preflight.environment())

    def review_record(self, case_id, *, read_workflow=True, run_test=True):
        case = self.cases[case_id]
        host, _, control = self.prepared(case_id)
        names = ["target.py", "test_fixture.py", f".spec/requirements/{case['originId']}.md", "resources/advice-format.md", *case["additionalReadFiles"]]
        for name in names:
            if read_workflow or name != ".github/workflows/release.yml":
                self.assertFalse(host.call("read_file", {"path": name})["isError"])
        host.call("read_diff", {})
        for operation in ("context", "check"):
            self.assertFalse(host.call("run_bitz", {"operation": operation})["isError"])
        if control["allowTests"] and run_test:
            self.assertFalse(host.call("run_fixture_test", {})["isError"])
        calls = evaluate.jsonl(host.log)
        document = evaluate.load(ROOT / "plugins/bitz-quality/examples/missing-evidence-review.json")
        document.update(subjectCommit=control["subjectCommit"], riskBand="Q2", riskAssessment={"minimumBand": "Q2", "rationale": "採点器だけの合成試験"}, requiredEvidenceIds=["quality-plan", "test-results"], missingEvidenceIds=["quality-plan", "test-results"])
        document["independence"].update(independent=True, freshContext=True, implementationRunId=control["implementationRunId"], reviewRunId=control["reviewRunId"], directChecks=["採点器の合成入力。モデルの意味評価や独立成立の実証ではない"])
        document["notRerun"] = [{"check": "不足証拠", "reason": "合成試験では結果未提供", "evidenceIds": ["quality-plan", "test-results"], "evidenceAvailable": False}]
        response = {"documentJson": json.dumps(document, ensure_ascii=False), "coreObservationIds": [c["result"]["observationId"] for c in calls if c["tool"] == "run_bitz"], "reason": "合成採点器試験。モデル測定ではない"}
        trace = [{"type": "item.completed", "item": {"type": "mcp_tool_call", "server": "quality_eval", "tool": c["tool"], "arguments": c["arguments"], "status": "completed", "error": None, "result": {"content": [{"type": "text", "text": json.dumps({k: v for k, v in c["result"].items() if k != "execution"}, ensure_ascii=False)}], "structured_content": None}}} for c in calls]
        trace.append({"type": "item.completed", "item": {"type": "agent_message", "text": json.dumps(response)}})
        evaluate.write(self.directory / "control.json", control)
        evaluate.write(self.directory / "response.json", response)
        (self.directory / "trace.jsonl").write_text("\n".join(json.dumps(e) for e in trace) + "\n")
        return {"identity": {"variant": "baseline", "executionVersion": "quality-execution-0.1.1"}, "artifacts": {n: sha((self.directory / n).read_bytes()) for n in ("control.json", "response.json", "host.jsonl", "trace.jsonl")}}

    def test_mechanical_inspection_accepts_explicitly_unexecuted_unknown_case(self):
        record = self.review_record("QR-002")
        errors, document = evaluate.inspect_record(self.directory, self.cases["QR-002"], record)
        self.assertFalse(any(errors.values()), errors)
        self.assertEqual("unknown", document["decision"])
        self.assertIn("test-results", document["missingEvidenceIds"])
        self.assertFalse(any(c["tool"] == "run_fixture_test" for c in evaluate.jsonl(self.directory / "host.jsonl")))

    def test_supply_chain_workflow_read_and_allowed_test_are_required(self):
        record = self.review_record("QR-003", read_workflow=False, run_test=False)
        errors, _ = evaluate.inspect_record(self.directory, self.cases["QR-003"], record)
        self.assertIn("actual requirement, implementation and test reads are required", errors["evidence"])
        self.assertIn("actual fixed test execution must succeed", errors["mechanical"])

    def test_missing_independence_and_wrong_run_id_have_distinct_evidence_diagnostics(self):
        record = self.review_record("QR-002")
        response = evaluate.load(self.directory / "response.json")
        document = json.loads(response["documentJson"])

        def inspect():
            response["documentJson"] = json.dumps(document, ensure_ascii=False)
            evaluate.write(self.directory / "response.json", response)
            trace = evaluate.jsonl(self.directory / "trace.jsonl")
            trace[-1]["item"]["text"] = json.dumps(response)
            (self.directory / "trace.jsonl").write_text("\n".join(json.dumps(e) for e in trace) + "\n")
            record["artifacts"] = {n: sha((self.directory / n).read_bytes()) for n in record["artifacts"]}
            return evaluate.inspect_record(self.directory, self.cases["QR-002"], record)[0]

        document["independence"].update(independent=False, leadingConclusionProvided=True)
        errors = inspect()
        self.assertEqual(["independent review was not declared"], errors["evidence"])
        document["independence"]["reviewRunId"] = "synthetic-different-run"
        errors = inspect()
        self.assertEqual(["independent review was not declared", "independent run IDs do not match fixed run identity"], errors["evidence"])
        document["independence"].update(independent=True, leadingConclusionProvided=False)
        errors = inspect()
        self.assertEqual(["independent run IDs do not match fixed run identity"], errors["evidence"])


if __name__ == "__main__":
    unittest.main()
