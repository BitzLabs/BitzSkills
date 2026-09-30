import importlib.util
import hashlib
import io
import json
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock


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

    def test_held_out_case_rejects_unknown_event(self):
        private_case = dict(skill_eval.load_cases()[0], caseId="SE-1000", prompt="保持した独立の要求")
        private_case["expected"] = dict(private_case["expected"], requiredEvents=["private-only-event"])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "held-out.json"
            path.write_text(json.dumps({"setVersion": "secret-1", "cases": [private_case]}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "未登録のイベント"):
                skill_eval.load_held_out_cases(path)

    def test_release_rejects_unbound_public_run(self):
        private_case = dict(skill_eval.load_cases()[0], caseId="SE-1000", prompt="保持した独立の要求")
        public_case = skill_eval.load_cases()[0]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            case_path = root / "held-out.json"
            case_path.write_text(json.dumps({"setVersion": "secret-1", "cases": [private_case]}), encoding="utf-8")
            entry, route = skill_eval.expected_route(public_case, "six-skill")
            run = {
                "schemaVersion": "1.0", "evaluationSetVersion": skill_eval.load_json(skill_eval.ROOT / "protocol.json")["evaluationSetVersion"], "caseId": public_case["caseId"],
                "architecture": "six-skill", "model": {"family": "test", "name": "test", "version": "1"},
                "repetition": 1, "subjectCommit": "0" * 40, "skillSetSha256": "0" * 64,
                "runConfigSha256": "0" * 64,
                "inputSha256": "0" * 64,
                "trace": {"path": "trace.jsonl", "sha256": "0" * 64},
                "observation": {"selectedEntry": entry, "selectedPath": route, "outcome": public_case["expected"]["outcome"],
                    "events": public_case["expected"]["requiredEvents"], "rejectedEvents": [],
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
                        "runConfigSha256": "0" * 64,
                        "inputSha256": "0" * 64,
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
            changed = json.loads(lines[0])
            changed["runConfigSha256"] = "1" * 64
            lines[0] = json.dumps(changed, ensure_ascii=False)
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            mixed_report = skill_eval.score(path, "prototype")
        self.assertEqual("Passed", report["result"], report["errors"])
        self.assertEqual("Failed", mixed_report["result"])
        self.assertTrue(any("runConfigSha256が実行間で一致しません" in error for error in mixed_report["errors"]))

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

    def test_runner_uses_same_catalog_for_full_and_selected_runs(self):
        catalogs = []

        def fake_run_one(args, case, event_catalog, *remaining):
            catalogs.append(tuple(event_catalog))
            return {"caseId": case["caseId"]}, "ran"

        common = ["--architecture", "six-skill", "--repetition", "1", "--model", "test-model",
                  "--model-family", "test-family", "--model-version", "1"]
        with (tempfile.TemporaryDirectory() as directory,
              mock.patch.object(skill_eval_runner, "run_one", fake_run_one),
              redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO())):
            self.assertEqual(0, skill_eval_runner.main(common + ["--output", str(Path(directory) / "full")]))
            full_catalog = catalogs[0]
            catalogs.clear()
            self.assertEqual(0, skill_eval_runner.main(common + ["--output", str(Path(directory) / "single"), "--case", "SE-031"]))
            self.assertEqual([full_catalog], catalogs)
        self.assertEqual(71, len(full_catalog))

    def test_runner_rejects_changed_resume_input(self):
        case = skill_eval.load_cases()[0]
        catalog = skill_eval.load_event_catalog()["events"]
        version = skill_eval.load_json(skill_eval.ROOT / "protocol.json")["evaluationSetVersion"]
        subject_commit, skill_sha = "0" * 40, "0" * 64
        first_set = {"setVersion": "private-1", "caseCount": 1, "sha256": "1" * 64}
        second_set = {"setVersion": "private-2", "caseCount": 1, "sha256": "2" * 64}
        with tempfile.TemporaryDirectory() as directory:
            args = SimpleNamespace(output=Path(directory), architecture="six-skill", repetition=1,
                                   model="test-model", model_family="test-family", model_version="1",
                                   timeout=120, resume=True, rescore_existing=False)
            record_path = args.output / "six-skill" / "repetition-1" / case["caseId"] / "run.json"
            record_path.parent.mkdir(parents=True)
            record = skill_eval_runner.execution_identity(args, case, version, subject_commit, skill_sha, first_set)
            record["runConfigSha256"] = skill_eval_runner.run_config_sha256(args, version, subject_commit, skill_sha, first_set)
            record["inputSha256"] = skill_eval_runner.input_sha256(args, case, catalog, version, subject_commit, skill_sha, first_set)
            record_path.write_text(json.dumps(record), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "実行条件"):
                skill_eval_runner.run_one(args, case, catalog, version, subject_commit, skill_sha, 1, second_set)
            record = skill_eval_runner.execution_identity(args, case, version, subject_commit, skill_sha, second_set)
            record["runConfigSha256"] = skill_eval_runner.run_config_sha256(args, version, subject_commit, skill_sha, second_set)
            record["inputSha256"] = "0" * 64
            record_path.write_text(json.dumps(record), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "入力条件のhash"):
                skill_eval_runner.run_one(args, case, catalog, version, subject_commit, skill_sha, 1, second_set)


if __name__ == "__main__":
    unittest.main()
