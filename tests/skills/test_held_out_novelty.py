"""非公開本文を漏らさず、新旧集合の束縛と除外根拠を検査する。"""
from __future__ import annotations

import copy
from contextlib import ExitStack, redirect_stdout, redirect_stderr
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("held_out_novelty_audit", ROOT / "evals/skills/routing/audit_held_out.py")
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


def save(path, value):
    raw = json.dumps(value, ensure_ascii=False, indent=2).encode()
    path.write_bytes(raw)
    path.chmod(0o600)
    return hashlib.sha256(raw).hexdigest()


class HeldOutNoveltyTests(unittest.TestCase):
    def setUp(self):
        (ROOT / ".venv").mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="novelty-audit-", dir=ROOT / ".venv")
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.public = base / "public"
        skills = self.public / "evals/skills"
        skills.mkdir(parents=True)
        for directory in ["cases", "schemas"]:
            shutil.copytree(ROOT / "evals/skills" / directory, skills / directory)
        shutil.copy2(ROOT / "evals/skills/event-catalog.json", skills / "event-catalog.json")
        routing = skills / "routing"
        routing.mkdir()
        shutil.copy2(ROOT / "evals/skills/routing/novelty.schema.json", routing / "novelty.schema.json")
        self.private = base / "private"
        self.private.mkdir(mode=0o700)
        self.previous_path = self.private / "cases.json"
        new_root = self.private / "collection-02"
        new_root.mkdir(mode=0o700)
        self.case_path = new_root / "cases.json"
        self.novelty_path = new_root / "novelty.json"
        self.contract_path = routing / "held-out-collection-v0.2.json"
        self.cases = []
        capabilities = list(audit.validate.CAPABILITIES)
        for index in range(12):
            cap = capabilities[index % 6]
            entry, route = audit.validate.CAPABILITIES[cap]
            positive = index < 6
            negative = 6 <= index < 9
            self.cases.append({"schemaVersion": "1.0", "caseId": f"SE-{900+index}",
                "category": ["explicit", "explicit", "implicit", "implicit", "contextual", "contextual", "negative", "negative", "negative", "safety", "safety", "safety"][index],
                "capability": cap, "mode": "use" if positive else "do-not-use" if negative else "stop",
                "prompt": f"合成新規監査入力 {index}", "context": [f"合成前提 {index}"], "mandatory": True,
                "expected": {"sixSkill": None if negative else cap, "threeEntry": None if negative else {"entry": entry, "path": route},
                             "outcome": "proceed" if positive else "not-applicable" if negative else "stop", "requiredEvents": [], "forbiddenEvents": []}})
        previous = copy.deepcopy(self.cases)
        for index, case in enumerate(previous):
            case.update(caseId=f"SE-{800+index}", prompt=f"合成旧監査入力 {index}")
        self.previous_sha = save(self.previous_path, {"setVersion": "synthetic-previous", "cases": previous})
        snapshot = self.public / ".venv/snapshot"
        body = snapshot / "resources/bitz-core/README.md"
        body.parent.mkdir(parents=True)
        body.write_text("合成の固定資源")
        self.body = body
        manifest = {"sourceCommit": "a"*40, "candidateVersion": "synthetic", "skills": [{}]*6,
                    "resources": {"resources/bitz-core/README.md": hashlib.sha256(body.read_bytes()).hexdigest()}}
        manifest_sha = save(snapshot / "manifest.json", manifest)
        self.contract = {"collectionVersion": "production-routing-held-out-collection-0.2.0",
            "storageAuthorization": {"root": str(new_root)}, "setVersion": "production-routing-held-out-0.2.0",
            "denominator": {"maxCases": 12},
            "inputSha256": {str(p.relative_to(self.public)): hashlib.sha256(p.read_bytes()).hexdigest() for p in (skills / "cases").glob("*.json")},
            "noveltyConditions": {"publicCases": 46},
            "candidate": {"snapshotRelativePath": ".venv/snapshot", "sourceCommit": "a"*40, "candidateVersion": "synthetic",
                          "manifestSha256": manifest_sha, "skillCount": 6, "resourceCount": 1},
            "excludedSet": {"path": str(self.previous_path), "sha256": self.previous_sha, "setVersion": "synthetic-previous", "caseCount": 12}}
        save(self.contract_path, self.contract)
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(audit, "ROOT", self.public))
        self.stack.enter_context(patch.multiple(audit.validate, ROOT=skills, CASES=skills / "cases", SCHEMAS=skills / "schemas", EVENT_CATALOG=skills / "event-catalog.json"))
        public_ids = [c["caseId"] for c in audit.validate.load_cases()]
        self.novelty = {"schemaVersion": "1.0", "setVersion": self.contract["setVersion"], "casesSha256": "",
            "publicCasesConsidered": public_ids, "excludedCasesConsidered": [c["caseId"] for c in previous],
            "comparisons": [{"caseId": c["caseId"], "primaryDecision": "PRIVATE_SENTINEL", "causalPreconditions": ["合成前提"],
                            "requestedAction": "合成動作", "stoppingReason": "合成理由", "nearestPublicCaseIds": [public_ids[0]],
                            "nearestExcludedCaseIds": [previous[0]["caseId"]], "decisionRelevantDifferences": ["合成の決定差"],
                            "sameDecisionUnderSamePremises": False, "differenceChangesDecisionOrScope": True} for c in self.cases]}
        self.persist()

    def persist(self):
        digest = save(self.case_path, {"setVersion": self.contract["setVersion"], "cases": self.cases})
        self.novelty["casesSha256"] = digest
        save(self.novelty_path, self.novelty)

    def run_audit(self):
        return audit.audit(self.contract_path, self.case_path)

    def test_complete_exclusion_evidence_is_not_semantic_certification(self):
        result = self.run_audit()
        self.assertEqual(result["novelty"]["comparisonCount"], 12)
        self.assertEqual(result["novelty"]["publicExclusionCount"], 46)
        self.assertEqual(result["novelty"]["previousExclusionCount"], 12)
        self.assertEqual(result["novelty"]["semanticNovelty"], "requires_independent_review")
        self.assertFalse(result["certifiesSkillGate"])
        self.assertNotIn("PRIVATE_SENTINEL", json.dumps(result))

    def test_public_input_normalization_detects_whitespace_equivalent_case(self):
        public_case = audit.validate.load_cases()[0]
        self.cases[0].update(prompt="  " + public_case["prompt"] + "  ", context=public_case["context"])
        self.persist()
        with self.assertRaisesRegex(ValueError, "normalized input collision"):
            self.run_audit()

    def test_previous_input_collision_and_previous_drift_are_rejected(self):
        self.cases[0]["prompt"] = "合成旧監査入力 0"
        self.persist()
        with self.assertRaisesRegex(ValueError, "normalized input collision"):
            self.run_audit()
        self.cases[0]["prompt"] = "合成新規監査入力 0"
        self.persist()
        self.previous_path.write_bytes(self.previous_path.read_bytes() + b"\n")
        with self.assertRaisesRegex(ValueError, "excluded set drift"):
            self.run_audit()

    def test_bindings_coverage_and_unknown_references_are_rejected(self):
        original = copy.deepcopy(self.novelty)
        mutations = [lambda n: n.update(casesSha256="0"*64),
                     lambda n: n["publicCasesConsidered"].pop(),
                     lambda n: n["excludedCasesConsidered"].pop(),
                     lambda n: n["comparisons"][0].update(caseId=n["comparisons"][1]["caseId"]),
                     lambda n: n["comparisons"][0].update(nearestPublicCaseIds=["SE-9999"]),
                     lambda n: n["comparisons"][0].update(nearestExcludedCaseIds=["SE-9999"])]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                value = copy.deepcopy(original)
                mutate(value)
                save(self.novelty_path, value)
                with self.assertRaises(ValueError):
                    self.run_audit()

    def test_cli_does_not_export_private_schema_diagnostic(self):
        self.novelty["comparisons"][0]["primaryDecision"] = {"secret": "PRIVATE_SENTINEL"}
        save(self.novelty_path, self.novelty)
        actual_audit = audit.audit
        with self.assertRaises(Exception) as error:
            self.run_audit()
        self.assertIn("PRIVATE_SENTINEL", str(error.exception))
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(sys, "argv", ["audit", "--collection", "novelty", "--cases", str(self.case_path)]), \
             patch.object(audit, "audit", lambda _, path: actual_audit(self.contract_path, path)), \
             redirect_stdout(stdout), redirect_stderr(stderr):
            code = audit.main()
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(stdout.getvalue()), {"status": "blocked", "errorType": "ValidationError"})
        self.assertEqual(stderr.getvalue(), "")
        self.assertNotIn("PRIVATE_SENTINEL", stdout.getvalue())

    def test_private_permissions_symlink_and_candidate_drift_are_rejected(self):
        self.novelty_path.chmod(0o644)
        with self.assertRaisesRegex(ValueError, "private file permissions"):
            self.run_audit()
        self.novelty_path.chmod(0o600)
        relocated = self.novelty_path.with_name("elsewhere.json")
        self.novelty_path.rename(relocated)
        self.novelty_path.symlink_to(relocated)
        with self.assertRaisesRegex(ValueError, "symlink storage"):
            self.run_audit()
        self.novelty_path.unlink()
        relocated.rename(self.novelty_path)
        self.body.write_text("changed")
        with self.assertRaisesRegex(ValueError, "candidate resource drift"):
            self.run_audit()

    def test_normalization_preserves_distinct_content_but_ignores_context_order(self):
        self.assertEqual(audit.normalized_input({"prompt": "ＡBC  x", "context": ["Ｂ", "a"]}),
                         audit.normalized_input({"prompt": "abc x", "context": ["a", "b"]}))
        self.assertNotEqual(audit.normalized_input({"prompt": "return []", "context": []}),
                            audit.normalized_input({"prompt": "return {}", "context": []}))

    def test_legacy_collection_can_be_reaudited_without_novelty_claim(self):
        legacy = copy.deepcopy(self.contract)
        legacy.update(collectionVersion="production-routing-held-out-collection-0.1.0", setVersion="synthetic-previous",
                      storageAuthorization={"root": str(self.private)})
        legacy_path = self.contract_path.with_name("legacy.json")
        save(legacy_path, legacy)
        result = audit.audit(legacy_path, self.previous_path)
        self.assertNotIn("novelty", result)
        self.assertEqual(result["heldOut"]["sha256"], self.previous_sha)

    def test_additional_public_json_is_rejected_before_case_loading(self):
        extra = copy.deepcopy(audit.validate.load_cases()[0])
        extra.update(caseId="SE-9999", prompt="合成追加の公開入力")
        save(self.public / "evals/skills/cases/extra.json", [extra])
        self.novelty["publicCasesConsidered"].append(extra["caseId"])
        save(self.novelty_path, self.novelty)
        # 固定2ファイルのhashが同じでも、第3のJSONをケース読取り前に拒否する。
        with patch.object(audit.validate, "load_held_out_cases", side_effect=AssertionError("unfixed input read")):
            with self.assertRaisesRegex(ValueError, "public input files drift"):
                self.run_audit()

    def test_declared_public_denominator_is_enforced(self):
        self.contract["noveltyConditions"]["publicCases"] = 47
        save(self.contract_path, self.contract)
        with self.assertRaisesRegex(ValueError, "public case denominator"):
            self.run_audit()

    def test_fixed_ref_collection_uses_new_version_and_four_digit_ids(self):
        self.contract.update(collectionVersion="production-routing-held-out-collection-0.3.0",
                             setVersion="production-routing-held-out-0.3.0")
        for index, case in enumerate(self.cases):
            case["caseId"] = f"SE-{1000+index}"
            self.novelty["comparisons"][index]["caseId"] = case["caseId"]
        self.novelty["setVersion"] = self.contract["setVersion"]
        save(self.contract_path, self.contract)
        self.persist()
        result = self.run_audit()
        self.assertEqual(result["heldOut"]["setVersion"], self.contract["setVersion"])
        self.assertEqual(result["heldOut"]["caseCount"], 12)
        self.assertEqual(result["novelty"]["semanticNovelty"], "requires_independent_review")


if __name__ == "__main__":
    unittest.main()
