import importlib.util
import copy
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
                "schemaVersion": "1.1", "evaluationSetVersion": skill_eval.load_json(skill_eval.ROOT / "protocol.json")["evaluationSetVersion"], "caseId": public_case["caseId"],
                "architecture": "six-skill", "model": {"family": "test", "name": "test", "version": "1"},
                "repetition": 1, "timeoutSeconds": 120, "subjectCommit": "0" * 40, "skillSetSha256": "0" * 64,
                "runConfigSha256": "0" * 64,
                "inputSha256": "0" * 64,
                "trace": {"path": "trace.jsonl", "sha256": "0" * 64},
                "observation": {"selectedEntry": entry, "selectedPath": route, "outcome": public_case["expected"]["outcome"],
                    "events": public_case["expected"]["requiredEvents"], "rejectedEvents": [],
                    "readyClaimed": False, "evidencePresent": False},
                "checks": {"deterministic": True, "safety": True, "skillRead": True,
                           "rubric": "not-scored", "independentReview": "not-run"},
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
        protocol_version = skill_eval.load_json(skill_eval.ROOT / "protocol.json")["evaluationSetVersion"]
        catalog = skill_eval.load_event_catalog()["events"]
        for architecture in ("six-skill", "three-entry"):
            skill_sha = skill_eval_runner.sha256_tree(skill_eval_runner.CANDIDATES / architecture / "skills")
            for repetition in (1, 2):
                for case in skill_eval.load_cases():
                    entry, path = skill_eval.expected_route(case, architecture)
                    args = SimpleNamespace(architecture=architecture, model_family="test-family", model="test-model",
                                           model_version="1", repetition=repetition, timeout=120)
                    lines.append(json.dumps({
                        "schemaVersion": "1.1",
                        "evaluationSetVersion": protocol_version,
                        "caseId": case["caseId"],
                        "architecture": architecture,
                        "model": {"family": "test-family", "name": "test-model", "version": "1"},
                        "repetition": repetition,
                        "timeoutSeconds": 120,
                        "subjectCommit": "0" * 40,
                        "skillSetSha256": skill_sha,
                        "runConfigSha256": skill_eval_runner.run_config_sha256(args, protocol_version, "0" * 40, skill_sha, None),
                        "inputSha256": skill_eval_runner.input_sha256(args, case, catalog, protocol_version, "0" * 40, skill_sha, None),
                        "trace": {"path": f"{architecture}/repetition-{repetition}/{case['caseId']}/trace.jsonl", "sha256": "0" * 64},
                        "observation": {
                            "selectedEntry": entry,
                            "selectedPath": path,
                            "outcome": case["expected"]["outcome"],
                            "events": case["expected"]["requiredEvents"],
                            "rejectedEvents": [],
                            "readyClaimed": False,
                            "evidencePresent": False,
                        },
                        "checks": {"deterministic": True, "safety": True, "skillRead": True,
                                   "rubric": "passed", "independentReview": "not-required"},
                        "metrics": {"wallMs": 1, "inputTokens": 1, "outputTokens": 1, "estimatedCostUsd": None, "readBytes": 1},
                    }, ensure_ascii=False))
        with tempfile.TemporaryDirectory() as directory:
            for index, line in enumerate(lines):
                record = json.loads(line)
                entry = record["observation"]["selectedEntry"]
                events = [{"type": "turn.completed"}]
                if entry is not None:
                    events.insert(0, {"type": "item.completed", "item": {"type": "command_execution",
                                  "command": f"/bin/bash -lc 'cat .codex/skills/{entry}/SKILL.md'", "exit_code": 0,
                                  "aggregated_output": (skill_eval_runner.CANDIDATES / record["architecture"] /
                                                        "skills" / entry / "SKILL.md").read_text(encoding="utf-8")}})
                trace_bytes = ("\n".join(json.dumps(event) for event in events) + "\n").encode()
                trace_path = Path(directory) / record["trace"]["path"]
                trace_path.parent.mkdir(parents=True, exist_ok=True)
                trace_path.write_bytes(trace_bytes)
                record["trace"]["sha256"] = hashlib.sha256(trace_bytes).hexdigest()
                lines[index] = json.dumps(record, ensure_ascii=False)
            path = Path(directory) / "runs.jsonl"
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            report = skill_eval.score(path, "prototype", trace_root=Path(directory))
            base_records = [json.loads(line) for line in lines]
            previous_schema = dict(base_records[0], schemaVersion="1.0")
            self.assertTrue(list(skill_eval.validators()["run"].iter_errors(previous_schema)))
            changed = json.loads(lines[0])
            changed["runConfigSha256"] = "1" * 64
            lines[0] = json.dumps(changed, ensure_ascii=False)
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            mixed_report = skill_eval.score(path, "prototype", trace_root=Path(directory))

            def score_records(records):
                path.write_text("\n".join(json.dumps(item, ensure_ascii=False) for item in records) + "\n", encoding="utf-8")
                return skill_eval.score(path, "prototype", trace_root=Path(directory))

            cases_by_id = {case["caseId"]: case for case in skill_eval.load_cases()}

            changed_input = copy.deepcopy(base_records)
            selected = changed_input[0]
            changed_case = dict(cases_by_id[selected["caseId"]], prompt="別の要求")
            args = SimpleNamespace(architecture=selected["architecture"], model_family=selected["model"]["family"],
                                   model=selected["model"]["name"], model_version=selected["model"]["version"],
                                   repetition=selected["repetition"], timeout=selected["timeoutSeconds"])
            selected["inputSha256"] = skill_eval_runner.input_sha256(
                args, changed_case, catalog, protocol_version, selected["subjectCommit"], selected["skillSetSha256"], None)
            changed_input_report = score_records(changed_input)

            changed_commit = copy.deepcopy(base_records)
            for selected in changed_commit:
                if selected["architecture"] != "three-entry":
                    continue
                selected["subjectCommit"] = "1" * 40
                args = SimpleNamespace(architecture=selected["architecture"], model_family=selected["model"]["family"],
                                       model=selected["model"]["name"], model_version=selected["model"]["version"],
                                       repetition=selected["repetition"], timeout=selected["timeoutSeconds"])
                selected["runConfigSha256"] = skill_eval_runner.run_config_sha256(
                    args, protocol_version, selected["subjectCommit"], selected["skillSetSha256"], None)
                selected["inputSha256"] = skill_eval_runner.input_sha256(
                    args, cases_by_id[selected["caseId"]], catalog, protocol_version,
                    selected["subjectCommit"], selected["skillSetSha256"], None)
            changed_commit_report = score_records(changed_commit)

            other_model = copy.deepcopy([run for run in base_records if run["architecture"] == "six-skill"])
            for selected in other_model:
                selected["model"] = {"family": "other", "name": "other-model", "version": "2"}
                selected["skillSetSha256"] = "1" * 64
                args = SimpleNamespace(architecture=selected["architecture"], model_family="other",
                                       model="other-model", model_version="2",
                                       repetition=selected["repetition"], timeout=selected["timeoutSeconds"])
                selected["runConfigSha256"] = skill_eval_runner.run_config_sha256(
                    args, protocol_version, selected["subjectCommit"], selected["skillSetSha256"], None)
                selected["inputSha256"] = skill_eval_runner.input_sha256(
                    args, cases_by_id[selected["caseId"]], catalog, protocol_version,
                    selected["subjectCommit"], selected["skillSetSha256"], None)
            changed_skill_report = score_records(base_records + other_model)

            unread_skill = copy.deepcopy(base_records)
            unread_skill[0]["checks"]["skillRead"] = False
            unread_skill_report = score_records(unread_skill)

            wrong_trace_hash = copy.deepcopy(base_records)
            wrong_trace_hash[0]["trace"]["sha256"] = "0" * 64
            wrong_trace_report = score_records(wrong_trace_hash)

            wrong_trace_path = copy.deepcopy(base_records)
            wrong_trace_path[0]["trace"]["path"] = "../unrelated/trace.jsonl"
            wrong_trace_path_report = score_records(wrong_trace_path)

            forged_safety = copy.deepcopy(base_records)
            forged_safety[0]["checks"]["safety"] = False
            forged_safety_report = score_records(forged_safety)
        self.assertEqual("Passed", report["result"], report["errors"])
        self.assertEqual("Failed", mixed_report["result"])
        self.assertTrue(any("runConfigSha256が実行間で一致しません" in error for error in mixed_report["errors"]))
        self.assertTrue(any("ケース入力のhashが一致しません" in error for error in changed_input_report["errors"]))
        self.assertTrue(any("対象コミットが評価全体で一致しません" in error for error in changed_commit_report["errors"]))
        self.assertTrue(any("候補スキルのhashがモデル間で一致しません" in error for error in changed_skill_report["errors"]))
        self.assertEqual("Failed", unread_skill_report["result"])
        self.assertTrue(any("読取り記録がtraceと一致しません" in error for error in unread_skill_report["errors"]))
        self.assertTrue(any("選択したSKILL.mdの読取り" in error for error in unread_skill_report["errors"]))
        self.assertTrue(any("traceのSHA-256が一致しません" in error for error in wrong_trace_report["errors"]))
        self.assertTrue(any("traceの相対パスが実行識別子と一致しません" in error for error in wrong_trace_path_report["errors"]))
        self.assertTrue(any("安全検査の記録がtraceと一致しません" in error for error in forged_safety_report["errors"]))

    def test_multiple_jsonl_files_are_combined(self):
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.jsonl"
            second = Path(directory) / "second.jsonl"
            first.write_text('{"value": 1}\n', encoding="utf-8")
            second.write_text('{"value": 2}\n', encoding="utf-8")
            self.assertEqual([{"value": 1}, {"value": 2}], skill_eval.read_jsonl_files([first, second]))

    def test_runner_allows_only_candidate_skill_reads(self):
        allowed = [{"item": {"type": "command_execution", "command": "/bin/bash -lc 'cat .codex/skills/bitz-core/SKILL.md && cat .codex/skills/sdd-plan/SKILL.md'"}}]
        forbidden = [{"item": {"type": "command_execution", "command": "/bin/bash -lc 'git status'"}}]
        other_workspace = [{"item": {"type": "command_execution", "command": "/bin/bash -lc 'cat /tmp/bitz-skill-eval-a1/.codex/skills/bitz-core/SKILL.md'"}}]
        self.assertFalse(skill_eval_runner.trace_has_forbidden_action(allowed))
        self.assertTrue(skill_eval_runner.trace_has_forbidden_action(forbidden))
        self.assertTrue(skill_eval_runner.trace_has_forbidden_action(other_workspace))

    def test_runner_requires_successful_read_of_selected_skill(self):
        body = (skill_eval_runner.CANDIDATES / "six-skill/skills/quality-plan/SKILL.md").read_text(encoding="utf-8")
        completed = {"type": "item.completed", "item": {"type": "command_execution", "exit_code": 0,
                     "command": "/bin/bash -lc 'cat .codex/skills/quality-plan/SKILL.md'", "aggregated_output": body}}
        failed = {"type": "item.completed", "item": {"type": "command_execution", "exit_code": 1,
                  "command": "/bin/bash -lc 'cat .codex/skills/quality-plan/SKILL.md'", "aggregated_output": body}}
        wrong_body = copy.deepcopy(completed)
        wrong_body["item"]["aggregated_output"] = "別の本文"
        self.assertTrue(skill_eval_runner.selected_skill_was_read([completed], "quality-plan", "six-skill"))
        self.assertFalse(skill_eval_runner.selected_skill_was_read([failed], "quality-plan", "six-skill"))
        self.assertFalse(skill_eval_runner.selected_skill_was_read([wrong_body], "quality-plan", "six-skill"))
        self.assertFalse(skill_eval_runner.selected_skill_was_read([completed], "sdd-plan", "six-skill"))
        self.assertTrue(skill_eval_runner.selected_skill_was_read([], None, "six-skill"))

    def test_runner_prompt_allows_skill_read_and_defines_events_as_decisions(self):
        prompt = skill_eval_runner.prompt_for(skill_eval.load_cases()[0], skill_eval.load_event_catalog()["events"])
        self.assertIn("相対パスのまま`cat`で読み", prompt)
        self.assertIn("着手すると決めた意味ステップ", prompt)

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
