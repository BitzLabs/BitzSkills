"""Public CLI connection and rejection of contradictory quality advice.

Synthetic references below are test inputs, not evidence of a real review.
The format checker cannot prove the truth of a supplied finding or hash.
"""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "plugins/bitz-quality"
SPEC = importlib.util.spec_from_file_location("quality_format", PACKAGE / "scripts/validate_quality.py")
quality = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(quality)


def example(name):
    return json.loads((PACKAGE / "examples" / name).read_text(encoding="utf-8"))


def complete_review():
    value = example("missing-evidence-review.json")
    value["subjectCommit"] = "a" * 40
    value["independence"].update(independent=True, freshContext=True, directChecks=["合成試験の宣言"])
    value["collectedEvidence"] = [
        {"evidenceId": name, "source": "synthetic test input", "sha256": hashlib.sha256(name.encode()).hexdigest(), "subjectCommit": "a" * 40}
        for name in value["requiredEvidenceIds"]
    ]
    value["missingEvidenceIds"] = []
    value["notRerun"] = []
    value["coreResults"] = [core_observation(operation=operation) for operation in ("context", "check")]
    value["decision"] = "ready"
    return value


def core_observation(status="passed", operation="check", role="current_gate"):
    raw = {"operation": operation, "status": status, "revision": {"commit": "a" * 40, "dirty": False}, "diagnostics": []}
    if operation == "context":
        raw.update(resolution={"complete": True}, contextDigest="b" * 64)
    return {"operation": operation, "status": status, "exitCode": quality.EXIT_CODES[status],
            "source": "synthetic test input, not a real Core result", "sha256": hashlib.sha256(json.dumps(raw).encode()).hexdigest(),
            "subjectCommit": "a" * 40, "role": role, "roleReason": "合成入力の判定整合性試験", "argv": ["bitz", operation],
            "cwd": "synthetic", "rawResult": raw, "stderr": ""}


class QualityContractTests(unittest.TestCase):
    def assert_invalid(self, kind, value, text=None):
        errors = quality.validate(kind, value)
        self.assertTrue(errors)
        if text:
            self.assertTrue(any(text in e for e in errors), errors)

    def test_schemas_and_unproven_examples(self):
        for path in (PACKAGE / "schemas").glob("*.schema.json"):
            Draft202012Validator.check_schema(json.loads(path.read_text()))
        self.assertEqual([], quality.validate("plan", example("local-change-plan.json")))
        self.assertEqual([], quality.validate("review", example("missing-evidence-review.json")))

    def test_packaged_local_links_resolve(self):
        for file in PACKAGE.rglob("*.md"):
            for link in re.findall(r"\]\(([^)]+)\)", file.read_text(encoding="utf-8")):
                if "://" not in link:
                    target = (file.parent / link.split("#", 1)[0]).resolve()
                    self.assertTrue(target.is_relative_to(PACKAGE.resolve()), (file, link))
                    self.assertTrue(target.is_file(), (file, link))

    def test_risk_cannot_omit_security(self):
        value = example("local-change-plan.json")
        del value["risk"]["areas"]["security"]
        self.assert_invalid("plan", value)

    def test_unknown_risk_cannot_be_presented_as_resolved_plan(self):
        value = example("local-change-plan.json")
        value["risk"]["areas"]["security"]["minimumBand"] = None
        value["planningStatus"] = "proposed"
        self.assert_invalid("plan", value, "unknown risk")

    def test_major_risk_cannot_be_averaged_away(self):
        value = example("local-change-plan.json")
        value["risk"]["areas"]["security"]["minimumBand"] = "Q3"
        self.assert_invalid("plan", value, "downgrade")

    def test_q2_requires_independent_review_and_full_flow(self):
        value = example("local-change-plan.json")
        value["risk"]["band"] = "Q2"
        value["independentReviewPlanned"] = False
        self.assert_invalid("plan", value, "independent")
        value["independentReviewPlanned"] = True
        self.assert_invalid("plan", value, "full flow")
        value["flow"] = "full"
        self.assertEqual([], quality.validate("plan", value))

    def test_all_evidence_cannot_be_demoted_to_recommended(self):
        value = example("local-change-plan.json")
        for item in value["evidencePlan"]:
            item["priority"] = "recommended"
        self.assert_invalid("plan", value, "required evidence")

    def test_duplicate_planned_evidence_is_ambiguous(self):
        value = example("local-change-plan.json")
        value["evidencePlan"].append(copy.deepcopy(value["evidencePlan"][0]))
        self.assert_invalid("plan", value, "duplicate")

    def test_missing_evidence_cannot_be_moved_to_conditions(self):
        value = example("missing-evidence-review.json")
        value["decision"] = "ready_with_conditions"
        value["conditions"] = [{"action": "不足試験を後日行う", "owner": "作業者", "dueOrDecisionPoint": "後日"}]
        self.assert_invalid("review", value, "expected unknown")

    def test_critical_defect_wins_over_missing_evidence_and_independence(self):
        value = example("missing-evidence-review.json")
        value["findings"] = [{"severity": "critical", "location": "synthetic auth boundary", "impact": "認可回避", "evidence": "合成入力で確認された欠陥という宣言", "resolved": False}]
        self.assert_invalid("review", value, "expected not_ready")
        value["decision"] = "not_ready"
        self.assertEqual([], quality.validate("review", value))
        self.assertFalse(value["independence"]["independent"])
        self.assertTrue(value["missingEvidenceIds"])

    def test_missing_ids_cannot_be_removed_without_evidence(self):
        value = example("missing-evidence-review.json")
        value["missingEvidenceIds"] = []
        self.assert_invalid("review", value, "missing evidence ids")

    def test_evidence_from_old_ref_cannot_support_new_ready(self):
        value = complete_review()
        value["collectedEvidence"][0]["subjectCommit"] = "b" * 40
        self.assert_invalid("review", value, "another subject")

    def test_same_id_different_hash_is_not_two_evidence_items(self):
        value = complete_review()
        extra = copy.deepcopy(value["collectedEvidence"][0])
        extra["sha256"] = hashlib.sha256(b"another result").hexdigest()
        value["collectedEvidence"].append(extra)
        self.assert_invalid("review", value, "duplicate")

    def test_same_run_cannot_self_certify_independence(self):
        value = complete_review()
        value["independence"]["reviewRunId"] = value["independence"]["implementationRunId"]
        self.assert_invalid("review", value, "another run")

    def test_inherited_history_cannot_claim_independent(self):
        value = complete_review()
        value["independence"]["implementationPrivateHistoryInherited"] = True
        self.assert_invalid("review", value)

    def test_q2_without_quality_plan_cannot_be_ready(self):
        value = complete_review()
        value["riskBand"] = "Q2"
        self.assert_invalid("review", value, "expected unknown")
        value["decision"] = "unknown"
        self.assertEqual([], quality.validate("review", value))

    def test_explicit_noncritical_condition_and_ready_are_separate(self):
        value = complete_review()
        self.assertEqual([], quality.validate("review", value))
        value["conditions"] = [{"action": "運用窓口を確定", "owner": "利用者", "dueOrDecisionPoint": "受入れ判断前"}]
        self.assert_invalid("review", value, "ready_with_conditions")
        value["decision"] = "ready_with_conditions"
        self.assertEqual([], quality.validate("review", value))

    def test_minor_unresolved_finding_cannot_be_hidden_in_ready(self):
        value = complete_review()
        value["findings"] = [{"severity": "minor", "location": "synthetic docs", "impact": "説明不足", "evidence": "合成所見", "resolved": False}]
        self.assert_invalid("review", value, "noncritical condition")

    def test_cli_format_valid_does_not_certify_quality(self):
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "PYTHONDONTWRITEBYTECODE": "1"}
        result = subprocess.run([sys.executable, "-B", str(PACKAGE / "scripts/validate_quality.py"), "review", str(PACKAGE / "examples/missing-evidence-review.json")], env=env, capture_output=True, text=True, timeout=15)
        self.assertEqual(0, result.returncode, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual("valid", data["status"])
        self.assertFalse(data["certifiesQuality"])
        self.assertEqual("format-and-declared-consistency", data["scope"])

    def test_current_core_failure_overrides_missing_evidence(self):
        value = example("missing-evidence-review.json")
        value["subjectCommit"] = "a" * 40
        value["coreResults"] = [core_observation("failed")]
        self.assert_invalid("review", value, "expected not_ready")
        value["decision"] = "not_ready"
        self.assertEqual([], quality.validate("review", value))

    def test_current_core_blocked_error_and_invalid_invocation_are_unknown(self):
        for status in ("blocked", "error", None):
            with self.subTest(status=status):
                value = complete_review()
                item = core_observation(status)
                if status is None:
                    item.update(rawResult=None, stderr="bitz: check: invalid argument")
                value["coreResults"][1] = item
                self.assert_invalid("review", value, "expected unknown")
                value["decision"] = "unknown"
                self.assertEqual([], quality.validate("review", value))

    def test_historical_and_expected_negative_do_not_replace_current_gates(self):
        for role in ("historical", "expected_negative"):
            value = complete_review()
            value["coreResults"].append(core_observation("failed", role=role))
            self.assertEqual([], quality.validate("review", value))
            value["coreResults"] = value["coreResults"][-1:]
            self.assert_invalid("review", value, "expected unknown")

    def test_core_original_status_exit_and_revision_cannot_be_rewritten(self):
        for field, replacement in (("exitCode", 1), ("status", "failed"), ("subjectCommit", "b" * 40)):
            value = complete_review()
            value["coreResults"][0][field] = replacement
            self.assert_invalid("review", value)

    def test_dirty_or_incomplete_context_cannot_support_ready(self):
        for mutation in ("dirty", "resolution", "digest"):
            value = complete_review()
            raw = value["coreResults"][0]["rawResult"]
            if mutation == "dirty":
                raw["revision"]["dirty"] = True
            elif mutation == "resolution":
                raw["resolution"]["complete"] = False
            else:
                raw["contextDigest"] = None
            self.assert_invalid("review", value, "expected unknown")

    def test_invalid_invocation_cannot_invent_a_core_result(self):
        value = complete_review()
        value["coreResults"][1]["status"] = None
        value["coreResults"][1]["exitCode"] = 4
        self.assert_invalid("review", value, "no Core result")

    def test_malformed_retained_metadata_is_rejected_without_crashing(self):
        for field in ("revision", "resolution"):
            value = complete_review()
            value["coreResults"][0]["rawResult"][field] = []
            self.assert_invalid("review", value, "schema:")

    def test_missing_reexecution_is_linked_to_evidence_availability(self):
        value = complete_review()
        value["notRerun"] = [{"check": "回帰試験", "reason": "独立に一次結果を直接検分した合成宣言", "evidenceIds": ["regression"], "evidenceAvailable": True}]
        self.assertEqual([], quality.validate("review", value))
        value["notRerun"][0]["evidenceAvailable"] = False
        self.assert_invalid("review", value, "unavailable evidence")
        value["collectedEvidence"] = [e for e in value["collectedEvidence"] if e["evidenceId"] != "regression"]
        value["missingEvidenceIds"] = ["regression"]
        value["decision"] = "unknown"
        self.assertEqual([], quality.validate("review", value))

    def test_plan_preserves_original_core_warnings_and_unexecuted_checks(self):
        value = example("local-change-plan.json")
        value["subjectCommit"] = "a" * 40
        item = core_observation("passed_with_warnings", operation="context")
        item["rawResult"]["diagnostics"] = [{"severity": "warning", "message": "合成警告"}]
        value["coreResults"] = [item]
        self.assertEqual([], quality.validate("plan", value))
        self.assertEqual("合成警告", value["coreResults"][0]["rawResult"]["diagnostics"][0]["message"])
        self.assertFalse(value["notRun"][0]["evidenceAvailable"])
        value["coreResults"] = [core_observation("blocked")]
        value["planningStatus"] = "proposed"
        self.assert_invalid("plan", value, "non-success")

    def test_real_core_pass_does_not_supply_missing_test_evidence(self):
        scratch = ROOT / ".venv"
        scratch.mkdir(exist_ok=True)
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "PYTHONPATH": os.environ["PYTHONPATH"], "PYTHONDONTWRITEBYTECODE": "1", "LC_ALL": "C.UTF-8"}
        with tempfile.TemporaryDirectory(prefix="quality-contract-", dir=scratch) as name:
            workspace = Path(name)
            (workspace / ".spec/requirements").mkdir(parents=True)
            (workspace / ".spec/bitz.yaml").write_text('schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\n', encoding="utf-8")
            (workspace / ".spec/requirements/REQ-001.md").write_text('---\nid: REQ-001\ntitle: 空の入力を拒否する\nstatus: approved\n---\n\n# REQ-001 空の入力を拒否する\n\n## Intent\n\n空入力の理由を示す。\n\n## Acceptance Criteria\n\n- [REQ-001:AC-01] [ACTOR:TargetSystem] [WHEN] 空の入力を受け取った場合 [MUST] [THEN] 入力エラーを1件返す。\n\n## Verification\n\n実テストは未実装・未実証。\n', encoding="utf-8")
            for args in (["init", "-b", "quality-synthetic"], ["add", "--", ".spec/bitz.yaml", ".spec/requirements/REQ-001.md"], ["-c", "user.name=Quality synthetic test", "-c", "user.email=quality@invalid", "commit", "-m", "synthetic base"]):
                subprocess.run(["git", *args], cwd=workspace, env=env, check=True, capture_output=True, timeout=15)
            ref = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=workspace, env=env, text=True).strip()
            value = example("missing-evidence-review.json")
            value["subjectCommit"] = ref
            before = {p.relative_to(workspace).as_posix(): p.read_bytes() for p in (workspace / ".spec").rglob("*") if p.is_file()}
            for operation, args in [("context", ["context", "REQ-001", "--purpose", "interpret", "--format", "json"]), ("check", ["check", "REQ-001", "--format", "json"])]:
                result = subprocess.run([sys.executable, "-B", "-m", "bitz.cli", *args], cwd=workspace, env=env, capture_output=True, timeout=20)
                self.assertEqual(0, result.returncode, result.stderr)
                core = json.loads(result.stdout)
                self.assertIn(core["status"], {"passed", "passed_with_warnings"})
                self.assertEqual(operation, core["operation"])
                value["coreResults"].append({"operation": operation, "status": core["status"], "exitCode": result.returncode,
                    "source": "actual synthetic public CLI stdout", "sha256": hashlib.sha256(result.stdout).hexdigest(),
                    "subjectCommit": ref, "role": "current_gate", "roleReason": "同一合成workspaceの読取り検査",
                    "argv": [sys.executable, "-B", "-m", "bitz.cli", *args], "cwd": str(workspace), "rawResult": core, "stderr": result.stderr.decode()})
            self.assertEqual([], quality.validate("review", value))
            self.assertEqual("unknown", value["decision"])
            self.assertEqual([], value["collectedEvidence"])
            value["decision"] = "ready"
            self.assert_invalid("review", value, "expected unknown")
            self.assertEqual(before, {p.relative_to(workspace).as_posix(): p.read_bytes() for p in (workspace / ".spec").rglob("*") if p.is_file()})


if __name__ == "__main__":
    unittest.main()
