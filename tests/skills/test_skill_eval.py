import importlib.util
import hashlib
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "evals/skills/validate.py"
SPEC = importlib.util.spec_from_file_location("skill_eval", MODULE_PATH)
skill_eval = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(skill_eval)
RUNNER_PATH = ROOT / "evals/skills/run_model.py"
RUNNER_SPEC = importlib.util.spec_from_file_location("skill_eval_runner", RUNNER_PATH)
skill_eval_runner = importlib.util.module_from_spec(RUNNER_SPEC)
RUNNER_SPEC.loader.exec_module(skill_eval_runner)


class SkillEvalTests(unittest.TestCase):
    def test_contract_audit_passes(self):
        report = skill_eval.audit()
        self.assertEqual("Passed", report["status"], report["errors"])
        self.assertEqual(46, report["cases"])

    def test_empty_run_set_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "empty.jsonl"
            path.write_text("", encoding="utf-8")
            report = skill_eval.score(path, "prototype")
        self.assertEqual("Failed", report["result"])
        self.assertTrue(any("0件" in error for error in report["errors"]))

    def test_release_requires_held_out_cases(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "empty.jsonl"
            path.write_text("", encoding="utf-8")
            report = skill_eval.score(path, "release")
        self.assertEqual("Failed", report["result"])
        self.assertTrue(any("--held-out-cases" in error for error in report["errors"]))

    def test_held_out_case_metadata_and_collision(self):
        private_case = dict(skill_eval.load_cases()[0], caseId="SE-1000", prompt="保持した独立の要求")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "held-out.json"
            path.write_text(json.dumps({"setVersion": "secret-1", "cases": [private_case]}), encoding="utf-8")
            cases, metadata = skill_eval.load_held_out_cases(path)
            self.assertEqual("SE-1000", cases[0]["caseId"])
            self.assertEqual({"setVersion": "secret-1", "caseCount": 1, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}, metadata)
            private_case["caseId"] = skill_eval.load_cases()[0]["caseId"]
            path.write_text(json.dumps({"setVersion": "secret-1", "cases": [private_case]}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "衝突"):
                skill_eval.load_held_out_cases(path)

    def test_held_out_case_rejects_public_input_with_new_id(self):
        private_case = dict(skill_eval.load_cases()[0], caseId="SE-1000")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "held-out.json"
            path.write_text(json.dumps({"setVersion": "secret-1", "cases": [private_case]}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "入力.*衝突"):
                skill_eval.load_held_out_cases(path)

    def test_release_rejects_unbound_held_out_run(self):
        private_case = dict(skill_eval.load_cases()[0], caseId="SE-1000", prompt="保持した独立の要求")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            case_path = root / "held-out.json"
            case_path.write_text(json.dumps({"setVersion": "secret-1", "cases": [private_case]}), encoding="utf-8")
            entry, route = skill_eval.expected_route(private_case, "six-skill")
            run = {
                "schemaVersion": "1.0", "evaluationSetVersion": "0.3.0", "caseId": "SE-1000",
                "architecture": "six-skill", "model": {"family": "test", "name": "test", "version": "1"},
                "repetition": 1, "subjectCommit": "0" * 40, "skillSetSha256": "0" * 64,
                "trace": {"path": "trace.jsonl", "sha256": "0" * 64},
                "observation": {"selectedEntry": entry, "selectedPath": route, "outcome": private_case["expected"]["outcome"],
                    "events": private_case["expected"]["requiredEvents"], "rejectedEvents": [],
                    "readyClaimed": False, "evidencePresent": False},
                "checks": {"deterministic": True, "safety": True, "rubric": "not-scored", "independentReview": "not-run"},
                "metrics": {"wallMs": 1, "inputTokens": 1, "outputTokens": 1, "estimatedCostUsd": None, "readBytes": 1},
            }
            run_path = root / "runs.jsonl"
            run_path.write_text(json.dumps(run) + "\n", encoding="utf-8")
            report = skill_eval.score(run_path, "release", case_path)
        self.assertEqual("Failed", report["result"])
        self.assertTrue(any("保持ケース集合の版・件数・hash" in error for error in report["errors"]))

    def test_independence_schema_rejects_missing_evidence(self):
        validator = skill_eval.validators()["independent-review"]
        errors = list(validator.iter_errors({"schemaVersion": "1.0", "independent": True}))
        self.assertTrue(errors)

    def test_independence_schema_rejects_inherited_context(self):
        validator = skill_eval.validators()["independent-review"]
        record = {
            "schemaVersion": "1.0",
            "implementationRunId": "implementation-1",
            "reviewRunId": "review-1",
            "subjectCommit": "0" * 40,
            "freshContext": True,
            "implementationPrivateHistoryInherited": True,
            "leadingConclusionProvided": False,
            "inputs": ["diff"],
            "directChecks": ["inspect diff"],
            "notRerun": [],
            "independent": True,
        }
        self.assertTrue(list(validator.iter_errors(record)))

    def test_do_not_use_case_cannot_select_a_route(self):
        cases = skill_eval.load_cases()
        case = next(case for case in cases if case["mode"] == "do-not-use")
        run = {
            "architecture": "six-skill",
            "observation": {
                "selectedEntry": case["capability"],
                "selectedPath": None,
                "outcome": "not-applicable",
                "events": [],
            },
        }
        self.assertFalse(skill_eval.observed_pass(case, run))

    def test_complete_perfect_prototype_scores_passed(self):
        lines = []
        for architecture in ("six-skill", "three-entry"):
            for repetition in (1, 2):
                for case in skill_eval.load_cases():
                    entry, path = skill_eval.expected_route(case, architecture)
                    lines.append(json.dumps({
                        "schemaVersion": "1.0",
                        "evaluationSetVersion": skill_eval.load_json(skill_eval.ROOT / "protocol.json")["evaluationSetVersion"],
                        "caseId": case["caseId"],
                        "architecture": architecture,
                        "model": {"family": "test-family", "name": "test-model", "version": "1"},
                        "repetition": repetition,
                        "subjectCommit": "0" * 40,
                        "skillSetSha256": "0" * 64,
                        "trace": {"path": f"{architecture}/{repetition}/{case['caseId']}.jsonl", "sha256": "0" * 64},
                        "observation": {
                            "selectedEntry": entry,
                            "selectedPath": path,
                            "outcome": case["expected"]["outcome"],
                            "events": case["expected"]["requiredEvents"],
                            "rejectedEvents": [],
                            "readyClaimed": False,
                            "evidencePresent": False,
                        },
                        "checks": {"deterministic": True, "safety": True, "rubric": "passed", "independentReview": "not-required"},
                        "metrics": {"wallMs": 1, "inputTokens": 1, "outputTokens": 1, "estimatedCostUsd": None, "readBytes": 1},
                    }, ensure_ascii=False))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "runs.jsonl"
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            report = skill_eval.score(path, "prototype")
        self.assertEqual("Passed", report["result"], report["errors"])

    def test_multiple_jsonl_files_are_combined(self):
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.jsonl"
            second = Path(directory) / "second.jsonl"
            first.write_text('{"value": 1}\n', encoding="utf-8")
            second.write_text('{"value": 2}\n', encoding="utf-8")
            self.assertEqual([{"value": 1}, {"value": 2}], skill_eval.read_jsonl_files([first, second]))

    def test_runner_allows_only_candidate_skill_reads(self):
        allowed = [{"item": {"type": "command_execution", "command": "/bin/bash -lc 'cat /tmp/bitz-skill-eval-a1/.codex/skills/bitz-core/SKILL.md && cat .codex/skills/sdd-plan/SKILL.md'"}}]
        forbidden = [{"item": {"type": "command_execution", "command": "/bin/bash -lc 'git status'"}}]
        self.assertFalse(skill_eval_runner.trace_has_forbidden_action(allowed))
        self.assertTrue(skill_eval_runner.trace_has_forbidden_action(forbidden))

    def test_runner_schema_constrains_six_skill_path(self):
        schema = skill_eval_runner.decision_schema_for("six-skill")
        self.assertEqual({"type": "null"}, schema["properties"]["selectedPath"])


if __name__ == "__main__":
    unittest.main()
