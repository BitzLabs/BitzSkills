"""公開CLIと公開形式でSDDから品質へ証拠を渡す合成試験。

モデル行動や独立レビューの成功を模擬しない。実際には未実施の
人手レビュー・独立検分を残し、Core通過だけではreadyにならないことを調べる。
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from jsonschema import Draft202012Validator
import test_sdd_implement_connection as implementation
import test_sdd_plan_examples as planning


ROOT = planning.ROOT
QUALITY = ROOT / "plugins/bitz-quality"


class SddQualityIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = implementation.SddImplementConnectionTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.workspace = self.fixture.workspace
        self.fixture.prepare()
        # 証拠は合成例の一時領域だけに保存し、Coreの対象差分へ入れない。
        self.artifacts = tempfile.TemporaryDirectory(prefix="bitz-integration-evidence-")
        self.addCleanup(self.artifacts.cleanup)
        self.evidence = Path(self.artifacts.name)

    def invoke(self, operation, *arguments):
        before = planning.snapshot(self.workspace)
        argv = [sys.executable, "-B", "-m", "bitz.cli", operation, *arguments, "--format", "json"]
        process = subprocess.run(argv, cwd=self.workspace, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
                                 capture_output=True, timeout=20)
        raw = json.loads(process.stdout)
        self.assertEqual({"passed": 0, "passed_with_warnings": 0, "failed": 1,
                          "blocked": 2, "error": 3}[raw["status"]], process.returncode, process.stderr)
        self.assertEqual(before, planning.snapshot(self.workspace))
        path = self.evidence / f"{operation}-{len(list(self.evidence.iterdir()))}.json"
        path.write_bytes(process.stdout)
        return {"operation": operation, "status": raw["status"], "exitCode": process.returncode,
                "source": str(path), "sha256": hashlib.sha256(process.stdout).hexdigest(),
                "subjectCommit": raw["revision"]["commit"], "role": "current_gate",
                "roleReason": "確定した合成対象を公開CLIで直接検査", "argv": argv,
                "cwd": str(self.workspace), "rawResult": raw, "stderr": process.stderr.decode()}

    def validate(self, kind, document, valid=True):
        path = self.evidence / f"{kind}.json"
        path.write_text(json.dumps(document, ensure_ascii=False))
        process = subprocess.run([sys.executable, "-B", str(QUALITY / "scripts/validate_quality.py"), kind, str(path)],
                                 capture_output=True, text=True, timeout=20)
        result = json.loads(process.stdout)
        self.assertEqual(0 if valid else 1, process.returncode, result)
        self.assertFalse(result["certifiesQuality"])
        return result

    def plan(self):
        plan = json.loads((QUALITY / "examples/local-change-plan.json").read_text())
        plan.update(subjectCommit=self.fixture.fixture.git("rev-parse", "HEAD").stdout.strip(),
                    planningStatus="proposed", flow="full", openQuestions=[], notRun=[])
        plan["goal"] = "合成公開契約の空入力エラー件数を実テストで検査する。型・内容は未検査。"
        plan["risk"]["band"] = "Q2"
        plan["risk"]["rationale"] = "この試験では公開契約を扱うQ2条件を固定する"
        for area in plan["risk"]["areas"].values():
            area["openQuestions"] = []
        plan["evidencePlan"] = [
            {"evidenceId": name, "priority": "required", "reason": reason,
             "checksCondition": reason, "method": "一次結果の直接検査", "command": None,
             "cwd": str(self.workspace), "safetyPrerequisites": ["合成対象と検査本文を確認"], "owner": "試験担当"}
            for name, reason in (("context", "承認済み要求とTASKの実装解決"),
                                 ("check", "TASK変更境界"), ("verify", "空入力のエラー件数が1"),
                                 ("human-review", "人手による受入れは未実施"))]
        plan["coreResults"] = [self.invoke("context", "TASK-001", "--purpose", "implement"),
                               self.invoke("check", "TASK-001")]
        self.validate("plan", plan)
        return plan

    def results(self, repair=False):
        if repair:
            (self.workspace / "src/input.py").write_text(implementation.FIXED_SOURCE)
            self.fixture.fixture.commit_fixture()
        return [self.invoke("context", "TASK-001", "--purpose", "implement"),
                self.invoke("check", "TASK-001"), self.invoke("verify", "TASK-001")]

    def handoff(self, observations):
        evidence = [{"evidenceId": item["operation"], "kind": "core-result",
                     "source": item["source"], "sha256": item["sha256"]} for item in observations]
        record = {"schemaVersion": "1.0", "subjectCommit": observations[0]["subjectCommit"],
                  "originIds": ["TASK-001"], "changedPaths": ["src/input.py"],
                  "risk": {"band": "Q2", "dimensions": ["compatibility"],
                           "rationale": "公開契約のQ2合成条件"},
                  "requiredEvidence": evidence, "collectedEvidence": copy.deepcopy(evidence),
                  "missingEvidence": [{"evidenceId": "human-review", "reason": "人手受入れは未実施"}],
                  "checks": [{"name": item["operation"], "command": item["argv"],
                              "result": "passed" if item["exitCode"] == 0 else "failed"}
                             for item in observations] + [{"name": "human-review", "command": None, "result": "not-run"}]}
        schema = json.loads((ROOT / "evals/skills/schemas/handoff.schema.json").read_text())
        self.assertEqual([], list(Draft202012Validator(schema).iter_errors(record)))
        for item in record["collectedEvidence"]:
            self.assertEqual(item["sha256"], hashlib.sha256(Path(item["source"]).read_bytes()).hexdigest())
        return record

    def review(self, handoff, observations, plan=None):
        review = json.loads((QUALITY / "examples/missing-evidence-review.json").read_text())
        review.update(subjectCommit=handoff["subjectCommit"], riskBand="Q2",
                      riskAssessment={"minimumBand": "Q2", "rationale": handoff["risk"]["rationale"]},
                      qualityPlanPresent=plan is not None, coreResults=observations,
                      requiredEvidenceIds=[e["evidenceId"] for e in handoff["requiredEvidence"]]
                                          + [e["evidenceId"] for e in handoff["missingEvidence"]] + ["quality-plan"],
                      collectedEvidence=[{k: v for k, v in e.items() if k != "kind"}
                                         | {"subjectCommit": handoff["subjectCommit"]}
                                         for e in handoff["collectedEvidence"]],
                      missingEvidenceIds=[e["evidenceId"] for e in handoff["missingEvidence"]],
                      notRerun=[{"check": "人手受入れ", "reason": "試験は人手レビューを代行しない",
                                 "evidenceIds": ["human-review"], "evidenceAvailable": False}])
        if plan is not None:
            # 計画は実装前のrefで作る。取得済みの計画を新対象へ適用する
            # という合成入力であり、独立検分済みとの宣言はしない。
            path = self.evidence / "plan.json"
            review["collectedEvidence"].append({"evidenceId": "quality-plan", "source": str(path),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "subjectCommit": handoff["subjectCommit"]})
            self.assertEqual([e["evidenceId"] for e in plan["evidencePlan"]], review["requiredEvidenceIds"][:-1])
        else:
            review["missingEvidenceIds"].append("quality-plan")
            review["notRerun"].append({"check": "品質計画", "reason": "未提供",
                                       "evidenceIds": ["quality-plan"], "evidenceAvailable": False})
        review["decision"] = "not_ready" if any(e["status"] == "failed" for e in observations) else "unknown"
        return review

    def test_plan_before_implementation_and_real_repair_keep_review_pending(self):
        original = (self.workspace / "src/input.py").read_bytes()
        plan = self.plan()
        self.assertEqual(original, (self.workspace / "src/input.py").read_bytes())
        failed = self.results()
        self.assertEqual("failed", failed[-1]["status"])
        passed = self.results(repair=True)
        self.assertEqual("passed", passed[-1]["status"])
        self.assertFalse(passed[-1]["rawResult"]["revision"]["dirty"])
        review = self.review(self.handoff(passed), passed, plan)
        self.validate("review", review)
        self.assertEqual("unknown", review["decision"])
        self.assertFalse(review["independence"]["independent"])
        self.assertIn("status: open", (self.workspace / ".spec/tasks/TASK-001.md").read_text())
        review["decision"] = "ready"
        self.validate("review", review, valid=False)

    def test_q2_without_plan_preserves_required_missing_evidence(self):
        passed = self.results(repair=True)
        review = self.review(self.handoff(passed), passed)
        self.validate("review", review)
        self.assertIn("quality-plan", review["missingEvidenceIds"])
        review["missingEvidenceIds"].remove("quality-plan")
        self.validate("review", review, valid=False)

    def test_actual_failed_verify_remains_not_ready_despite_missing_review(self):
        failed = self.results()
        review = self.review(self.handoff(failed), failed)
        self.validate("review", review)
        self.assertEqual("not_ready", review["decision"])
        self.assertEqual(1, review["coreResults"][-1]["exitCode"])
        review["decision"] = "unknown"
        self.validate("review", review, valid=False)

    def test_previous_ref_evidence_cannot_support_repaired_subject(self):
        old = self.results()
        current = self.results(repair=True)
        self.assertNotEqual(old[0]["subjectCommit"], current[0]["subjectCommit"])
        review = self.review(self.handoff(current), current)
        review["coreResults"][-1] = old[-1]
        self.validate("review", review, valid=False)


if __name__ == "__main__":
    unittest.main()
