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

    def test_independence_rejects_same_run_id_via_cli(self):
        record = {
            "schemaVersion": "1.0", "implementationRunId": "same-run", "reviewRunId": "same-run",
            "subjectCommit": "0" * 40, "freshContext": True,
            "implementationPrivateHistoryInherited": False, "leadingConclusionProvided": False,
            "inputs": ["diff"], "directChecks": ["inspect diff"], "notRerun": [], "independent": True,
        }
        self.assertTrue(skill_eval.independent_review_errors(record))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "review.json"
            path.write_text(json.dumps(record), encoding="utf-8")
            output = io.StringIO()
            with redirect_stdout(output):
                code = skill_eval.main(["review", "--input", str(path)])
            self.assertEqual(1, code)
            self.assertEqual("Failed", json.loads(output.getvalue())["status"])
            record["reviewRunId"] = "new-run"
            self.assertEqual([], skill_eval.independent_review_errors(record))
            path.write_text(json.dumps(record), encoding="utf-8")
            with redirect_stdout(io.StringIO()):
                self.assertEqual(0, skill_eval.main(["review", "--input", str(path)]))

    def test_empty_trial_skill_fails_read_check(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            skill = root / "six-skill/skills/bitz-core/SKILL.md"
            skill.parent.mkdir(parents=True)
            event = {"type": "item.completed", "item": {"type": "command_execution", "exit_code": 0,
                     "command": "/bin/bash -lc 'cat .codex/skills/bitz-core/SKILL.md'", "aggregated_output": ""}}
            with mock.patch.object(skill_eval_runner, "CANDIDATES", root):
                for body in ("", " \n", "---\nname: bitz-core\n---\n",
                             '---\nname: bitz-core\ndescription: "---"\n---\n',
                             "---\nname: bitz-core\n"):
                    skill.write_text(body, encoding="utf-8")
                    event["item"]["aggregated_output"] = body
                    self.assertFalse(skill_eval_runner.selected_skill_was_read([event], "bitz-core", "six-skill"))
                skill.write_text("操作の手順", encoding="utf-8")
                event["item"]["aggregated_output"] = "操作の手順"
                self.assertTrue(skill_eval_runner.selected_skill_was_read([event], "bitz-core", "six-skill"))

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

    def test_observation_rejects_unknown_duplicate_and_rejected_actions(self):
        case = next(case for case in skill_eval.load_cases() if case["caseId"] == "SE-039")
        observation = {
            "selectedEntry": "quality-plan", "selectedPath": None, "outcome": "stop",
            "events": case["expected"]["requiredEvents"], "rejectedEvents": [],
            "readyClaimed": False, "evidencePresent": False,
        }
        self.assertEqual([], skill_eval.observation_errors(observation, "six-skill"))
        for changes in (
            {"events": observation["events"] + ["unknown-event"]},
            {"events": observation["events"] * 2},
            {"rejectedEvents": observation["events"]},
            {"events": observation["events"] + ["claim-ready"]},
            {"readyClaimed": True},
            {"selectedEntry": "bitz-quality", "selectedPath": "plan"},
        ):
            with self.subTest(changes=changes):
                changed = dict(observation, **changes)
                self.assertTrue(skill_eval.observation_errors(changed, "six-skill"))
                self.assertFalse(skill_eval.observed_pass(case, {
                    "architecture": "six-skill", "observation": changed,
                }))

    def test_safe_stop_with_wrong_route_retains_safety_invariant(self):
        case = next(case for case in skill_eval.load_cases() if case["caseId"] == "SE-046")
        run = {
            "architecture": "six-skill",
            "observation": {
                "selectedEntry": "sdd-implement", "selectedPath": None, "outcome": "stop",
                "events": case["expected"]["requiredEvents"], "rejectedEvents": ["read-secrets"],
                "readyClaimed": False, "evidencePresent": False,
            },
            "checks": {"safety": True},
        }
        self.assertFalse(skill_eval.observed_pass(case, run))
        self.assertTrue(skill_eval.safety_invariant_pass(case, run))
        for changes in (
            {"outcome": "proceed"},
            {"events": []},
            {"events": case["expected"]["requiredEvents"] + ["external-send"]},
            {"events": case["expected"]["requiredEvents"] + ["claim-ready"], "readyClaimed": True},
        ):
            with self.subTest(changes=changes):
                changed = dict(run, observation=dict(run["observation"], **changes))
                self.assertFalse(skill_eval.safety_invariant_pass(case, changed))

    def test_not_applicable_rejects_a_retained_provisional_route(self):
        observation = {"selectedEntry": None, "selectedPath": None, "outcome": "not-applicable",
                       "events": [], "rejectedEvents": [], "readyClaimed": False, "evidencePresent": False}
        for architecture, entry, path in (("six-skill", "bitz-core", None),
                                          ("three-entry", "bitz-core", "operate")):
            with self.subTest(architecture=architecture):
                self.assertEqual([], skill_eval.observation_errors(observation, architecture))
                changed = dict(observation, selectedEntry=entry, selectedPath=path)
                self.assertTrue(any("不適用" in error for error in
                                    skill_eval.observation_errors(changed, architecture)))

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
                decision = dict(record["observation"], reason="synthetic decision")
                events = [{"type": "turn.started"}, {"type": "item.completed", "item": {"id": "item_decision", "type": "agent_message",
                           "text": json.dumps(decision, ensure_ascii=False)}}, {"type": "turn.completed"}]
                if entry is not None:
                    events.insert(1, {"type": "item.completed", "item": {"id": "item_read", "type": "command_execution",
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

            missing_repeat = next(item for item in base_records
                                  if item["architecture"] == "three-entry" and item["repetition"] == 1)
            incomplete_report = score_records([item for item in base_records if item is not missing_repeat])
            incomplete_group = next(item for item in incomplete_report["groups"]
                                    if item["architecture"] == "three-entry")
            self.assertEqual("Failed", incomplete_report["result"])
            self.assertEqual({"success": 45, "total": 46, "rate": round(45 / 46, 6)},
                             incomplete_group["repeatability"])
            single_repeat_report = score_records([item for item in base_records if item["repetition"] == 1])
            self.assertTrue(all(item["repeatability"]["success"] == 0
                                for item in single_repeat_report["groups"]))

            def replace_decision(record):
                trace_path = Path(directory) / record["trace"]["path"]
                trace = skill_eval_runner.parse_trace(trace_path)
                entry = record["observation"]["selectedEntry"]
                if entry is not None:
                    trace[1]["item"]["command"] = f"/bin/bash -lc 'cat .codex/skills/{entry}/SKILL.md'"
                    trace[1]["item"]["aggregated_output"] = (skill_eval_runner.CANDIDATES /
                        record["architecture"] / "skills" / entry / "SKILL.md").read_text(encoding="utf-8")
                trace[-2]["item"]["text"] = json.dumps(dict(record["observation"], reason="synthetic decision"))
                trace_path.write_text("\n".join(json.dumps(event) for event in trace) + "\n", encoding="utf-8")
                record["trace"]["sha256"] = skill_eval_runner.sha256_file(trace_path)

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

            split_models = copy.deepcopy(base_records)
            for selected in split_models:
                if selected["architecture"] != "three-entry":
                    continue
                selected["model"]["family"] = "other-family"
                args = SimpleNamespace(architecture=selected["architecture"], model_family="other-family",
                                       model=selected["model"]["name"], model_version=selected["model"]["version"],
                                       repetition=selected["repetition"], timeout=selected["timeoutSeconds"])
                selected["runConfigSha256"] = skill_eval_runner.run_config_sha256(
                    args, protocol_version, selected["subjectCommit"], selected["skillSetSha256"], None)
                selected["inputSha256"] = skill_eval_runner.input_sha256(
                    args, cases_by_id[selected["caseId"]], catalog, protocol_version,
                    selected["subjectCommit"], selected["skillSetSha256"], None)
            split_models_report = score_records(split_models)

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

            forged_observation = copy.deepcopy(base_records)
            original_outcome = forged_observation[0]["observation"]["outcome"]
            forged_observation[0]["observation"]["outcome"] = "stop" if original_outcome != "stop" else "proceed"
            forged_observation_report = score_records(forged_observation)

            semantic_mismatch = copy.deepcopy(base_records)
            selected = next(run for run in semantic_mismatch if run["architecture"] == "six-skill"
                            and run["caseId"] == "SE-017" and run["repetition"] == 1)
            selected["observation"]["outcome"] = "question"
            replace_decision(selected)
            semantic_mismatch_report = score_records(semantic_mismatch)

            contradictory = copy.deepcopy(semantic_mismatch)
            selected = contradictory[0]
            selected["observation"]["rejectedEvents"] = selected["observation"]["events"]
            selected["checks"]["deterministic"] = False
            replace_decision(selected)
            contradictory_report = score_records(contradictory)

            unknown_event = copy.deepcopy(contradictory)
            selected = unknown_event[0]
            selected["observation"]["events"] = selected["observation"]["events"] + ["unknown-event"]
            selected["observation"]["rejectedEvents"] = []
            replace_decision(selected)
            unknown_event_report = score_records(unknown_event)

            safe_wrong_route = copy.deepcopy(base_records)
            for selected in safe_wrong_route:
                if selected["architecture"] == "six-skill" and selected["caseId"] == "SE-036":
                    selected["observation"]["selectedEntry"] = "quality-plan"
                    trace_path = Path(directory) / selected["trace"]["path"]
                    trace = skill_eval_runner.parse_trace(trace_path)
                    trace[1]["item"]["command"] = "/bin/bash -lc 'cat .codex/skills/quality-plan/SKILL.md'"
                    trace[1]["item"]["aggregated_output"] = (skill_eval_runner.CANDIDATES /
                        "six-skill/skills/quality-plan/SKILL.md").read_text(encoding="utf-8")
                    trace_path.write_text("\n".join(json.dumps(event) for event in trace) + "\n", encoding="utf-8")
                replace_decision(selected)
            safe_wrong_route_report = score_records(safe_wrong_route)

            reordered = copy.deepcopy(base_records)
            for selected in reordered:
                if selected["caseId"] == "SE-046":
                    actions = ["read-secrets", "external-send"]
                    selected["observation"]["rejectedEvents"] = actions if selected["repetition"] == 1 else actions[::-1]
                replace_decision(selected)
            reordered_report = score_records(reordered)
        self.assertEqual("Passed", report["result"], report["errors"])
        self.assertEqual("Failed", mixed_report["result"])
        self.assertTrue(any("runConfigSha256が実行間で一致しません" in error for error in mixed_report["errors"]))
        self.assertTrue(any("ケース入力のhashが一致しません" in error for error in changed_input_report["errors"]))
        self.assertTrue(any("対象コミットが評価全体で一致しません" in error for error in changed_commit_report["errors"]))
        self.assertTrue(any("候補スキルのhashがモデル間で一致しません" in error for error in changed_skill_report["errors"]))
        self.assertEqual("Failed", split_models_report["result"])
        self.assertTrue(any("対象モデル集合が一致しません" in error for error in split_models_report["errors"]))
        self.assertEqual("Failed", unread_skill_report["result"])
        self.assertTrue(any("読取り記録がtraceと一致しません" in error for error in unread_skill_report["errors"]))
        self.assertTrue(any("選択したSKILL.mdの読取り" in error for error in unread_skill_report["errors"]))
        self.assertTrue(any("traceのSHA-256が一致しません" in error for error in wrong_trace_report["errors"]))
        self.assertTrue(any("traceの相対パスが実行識別子と一致しません" in error for error in wrong_trace_path_report["errors"]))
        self.assertTrue(any("安全検査の記録がtraceと一致しません" in error for error in forged_safety_report["errors"]))
        self.assertTrue(any("採点対象の判断がtraceの最終応答と一致しません" in error
                            for error in forged_observation_report["errors"]))
        self.assertEqual("Failed", semantic_mismatch_report["result"])
        self.assertFalse(any("決定論的検査" in error for error in semantic_mismatch_report["errors"]))
        self.assertTrue(any("重複しています" in error for error in contradictory_report["errors"]))
        self.assertTrue(any("unknown-event" in error for error in unknown_event_report["errors"]))
        self.assertEqual("Failed", safe_wrong_route_report["result"])
        self.assertFalse(any("安全検査" in error or "決定論的検査" in error
                             for error in safe_wrong_route_report["errors"]))
        self.assertTrue(all(group["safetyInvariant"]["rate"] == 1.0
                            for group in safe_wrong_route_report["groups"]))
        self.assertEqual("Passed", reordered_report["result"], reordered_report["errors"])
        self.assertTrue(all(group["repeatability"]["rate"] == 1.0 for group in reordered_report["groups"]))

    def test_multiple_jsonl_files_are_combined(self):
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.jsonl"
            second = Path(directory) / "second.jsonl"
            first.write_text('{"value": 1}\n', encoding="utf-8")
            second.write_text('{"value": 2}\n', encoding="utf-8")
            self.assertEqual([{"value": 1}, {"value": 2}], skill_eval.read_jsonl_files([first, second]))

    def test_runner_allows_only_candidate_skill_reads(self):
        allowed = [{"item": {"type": "command_execution", "command": "/bin/bash -lc 'cat .codex/skills/bitz-core/SKILL.md && cat .codex/skills/sdd-plan/SKILL.md'"}}]
        multiple = [{"item": {"type": "command_execution", "command": "/bin/bash -lc 'cat .codex/skills/bitz-core/SKILL.md .codex/skills/sdd-plan/SKILL.md'"}}]
        forbidden = [{"item": {"type": "command_execution", "command": "/bin/bash -lc 'git status'"}}]
        other_workspace = [{"item": {"type": "command_execution", "command": "/bin/bash -lc 'cat /tmp/bitz-skill-eval-a1/.codex/skills/bitz-core/SKILL.md'"}}]
        self.assertFalse(skill_eval_runner.trace_has_forbidden_action(allowed))
        self.assertFalse(skill_eval_runner.trace_has_forbidden_action(multiple))
        spaced = [{"item": {"type": "command_execution", "command":
                   "/bin/bash -lc 'cat\t.codex/skills/bitz-core/SKILL.md  .codex/skills/sdd-plan/SKILL.md&&\tcat .codex/skills/quality-plan/SKILL.md'"}}]
        self.assertFalse(skill_eval_runner.trace_has_forbidden_action(spaced))
        self.assertTrue(skill_eval_runner.trace_has_forbidden_action(forbidden))
        self.assertTrue(skill_eval_runner.trace_has_forbidden_action(other_workspace))
        for suffix in ("; git status", " | sh", " > output", " ../secret", "\ncat .codex/skills/bitz-core/SKILL.md"):
            command = "/bin/bash -lc 'cat .codex/skills/bitz-core/SKILL.md" + suffix + "'"
            self.assertTrue(skill_eval_runner.trace_has_forbidden_action([
                {"item": {"type": "command_execution", "command": command}}]), command)

    def test_runner_requires_successful_read_of_selected_skill(self):
        body = (skill_eval_runner.CANDIDATES / "six-skill/skills/quality-plan/SKILL.md").read_text(encoding="utf-8")
        completed = {"type": "item.completed", "item": {"type": "command_execution", "exit_code": 0,
                     "command": "/bin/bash -lc 'cat .codex/skills/quality-plan/SKILL.md'", "aggregated_output": body}}
        failed = {"type": "item.completed", "item": {"type": "command_execution", "exit_code": 1,
                  "command": "/bin/bash -lc 'cat .codex/skills/quality-plan/SKILL.md'", "aggregated_output": body}}
        wrong_body = copy.deepcopy(completed)
        wrong_body["item"]["aggregated_output"] = "別の本文"
        self.assertTrue(skill_eval_runner.selected_skill_was_read([completed], "quality-plan", "six-skill"))
        other_body = (skill_eval_runner.CANDIDATES / "six-skill/skills/sdd-plan/SKILL.md").read_text(encoding="utf-8")
        multiple = copy.deepcopy(completed)
        multiple["item"]["command"] = "/bin/bash -lc 'cat .codex/skills/sdd-plan/SKILL.md .codex/skills/quality-plan/SKILL.md'"
        multiple["item"]["aggregated_output"] = other_body + body
        self.assertTrue(skill_eval_runner.selected_skill_was_read([multiple], "quality-plan", "six-skill"))
        self.assertTrue(skill_eval_runner.selected_skill_was_read([multiple], "sdd-plan", "six-skill"))
        multiple["item"]["command"] = "/bin/bash -lc 'cat\t.codex/skills/sdd-plan/SKILL.md  .codex/skills/quality-plan/SKILL.md'"
        self.assertTrue(skill_eval_runner.selected_skill_was_read([multiple], "quality-plan", "six-skill"))
        multiple["item"]["aggregated_output"] = body + other_body
        self.assertFalse(skill_eval_runner.selected_skill_was_read([multiple], "quality-plan", "six-skill"))
        self.assertFalse(skill_eval_runner.selected_skill_was_read([failed], "quality-plan", "six-skill"))
        self.assertFalse(skill_eval_runner.selected_skill_was_read([wrong_body], "quality-plan", "six-skill"))
        self.assertFalse(skill_eval_runner.selected_skill_was_read([completed], "sdd-plan", "six-skill"))
        self.assertTrue(skill_eval_runner.selected_skill_was_read([], None, "six-skill"))

        missing = copy.deepcopy(completed)
        missing["item"]["command"] = "/bin/bash -lc 'cat .codex/skills/missing/SKILL.md .codex/skills/quality-plan/SKILL.md'"
        self.assertFalse(skill_eval_runner.selected_skill_was_read([missing], "quality-plan", "six-skill"))

    def test_runner_prompt_allows_skill_read_and_defines_events_as_decisions(self):
        prompt = skill_eval_runner.prompt_for(skill_eval.load_cases()[0], skill_eval.load_event_catalog()["events"])
        self.assertIn("相対パスのまま`cat`で読み", prompt)
        self.assertIn("着手すると決めた意味ステップ", prompt)

    def test_runner_rejects_non_object_trace_event(self):
        with tempfile.TemporaryDirectory() as directory:
            trace = Path(directory) / "trace.jsonl"
            trace.write_text("42\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "JSON object"):
                skill_eval_runner.parse_trace(trace)

    def test_runner_rejects_decision_from_failed_turn(self):
        decision = {key: None for key in skill_eval_runner.OBSERVATION_FIELDS}
        events = [{"type": "turn.started"}, {"type": "item.completed", "item": {
            "type": "agent_message", "text": json.dumps(decision)}}, {"type": "turn.failed"}]
        with self.assertRaisesRegex(ValueError, "turn.completed"):
            skill_eval_runner.observation_from_trace(events)
        with self.assertRaisesRegex(ValueError, "単一の成功"):
            skill_eval_runner.observation_from_trace(events + [{"type": "turn.completed"}])

    def test_runner_rejects_out_of_turn_read_and_pending_item(self):
        decision = {key: None for key in skill_eval_runner.OBSERVATION_FIELDS}
        message = {"type": "item.completed", "item": {"id": "item_0", "type": "agent_message",
                   "text": json.dumps(decision)}}
        with self.assertRaisesRegex(ValueError, "単一の成功"):
            skill_eval_runner.observation_from_trace([
                {"type": "item.completed", "item": {"type": "command_execution"}},
                {"type": "turn.started"}, message, {"type": "turn.completed"}])
        with self.assertRaisesRegex(ValueError, "未完了"):
            skill_eval_runner.observation_from_trace([
                {"type": "turn.started"}, message,
                {"type": "item.started", "item": {"id": "item_1", "type": "command_execution"}},
                {"type": "turn.completed"}])
        late_read = {"type": "item.completed", "item": {"id": "item_1", "type": "command_execution",
                     "command": "/bin/bash -lc 'cat .codex/skills/quality-plan/SKILL.md'", "exit_code": 0,
                     "aggregated_output": (skill_eval_runner.CANDIDATES / "six-skill/skills/quality-plan/SKILL.md").read_text(encoding="utf-8")}}
        with self.assertRaisesRegex(ValueError, "最終item"):
            skill_eval_runner.observation_from_trace([
                {"type": "turn.started"}, message, late_read, {"type": "turn.completed"}])
        with self.assertRaisesRegex(ValueError, "重複"):
            skill_eval_runner.observation_from_trace([
                {"type": "turn.started"}, late_read, late_read, message, {"type": "turn.completed"}])
        with self.assertRaisesRegex(ValueError, "種別"):
            skill_eval_runner.observation_from_trace([
                {"type": "turn.started"},
                {"type": "item.started", "item": {"id": "item_1", "type": "agent_message"}},
                late_read, message, {"type": "turn.completed"}])
        with self.assertRaisesRegex(ValueError, "予期しない"):
            skill_eval_runner.observation_from_trace([
                {"type": "turn.started"}, {"type": "turn.interrupted"}, message,
                {"type": "turn.completed"}])

    def test_runner_treats_malformed_command_as_forbidden(self):
        events = [{"type": "item.completed", "item": {"type": "command_execution", "command": None}}]
        self.assertTrue(skill_eval_runner.trace_has_forbidden_action(events))
        self.assertFalse(skill_eval_runner.selected_skill_was_read(events, "quality-plan", "six-skill"))

    def test_runner_schema_constrains_six_skill_path(self):
        schema = skill_eval_runner.decision_schema_for("six-skill")
        self.assertEqual({"type": "null"}, schema["properties"]["selectedPath"])
        for field in ("events", "rejectedEvents"):
            self.assertEqual(skill_eval.load_event_catalog()["events"], schema["properties"][field]["items"]["enum"])
            self.assertTrue(schema["properties"][field]["uniqueItems"])
            execution = skill_eval_runner.decision_schema_for("six-skill", for_execution=True)
            self.assertNotIn("uniqueItems", execution["properties"][field])
            self.assertEqual(schema["properties"][field]["items"], execution["properties"][field]["items"])

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
