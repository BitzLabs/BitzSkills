"""実保持入力を使わず、全体経路・来歴例外・比較漏れと非漏えいを統合検査する。"""
from __future__ import annotations

import copy
from contextlib import ExitStack, redirect_stderr, redirect_stdout
import hashlib
import importlib.util
import io
from itertools import combinations
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("remediated_audit", ROOT / "evals/skills/routing/audit_remediated_held_out.py")
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


def save(path, value):
    raw = json.dumps(value, ensure_ascii=False, indent=2).encode()
    path.write_bytes(raw)
    path.chmod(0o600)
    return hashlib.sha256(raw).hexdigest()


class HeldOutRemediationTests(unittest.TestCase):
    def setUp(self):
        (ROOT / ".venv").mkdir(exist_ok=True)
        temp = tempfile.TemporaryDirectory(prefix="routing-remediation-", dir=ROOT / ".venv")
        self.addCleanup(temp.cleanup)
        base = Path(temp.name)
        self.public = base / "public"
        skills = self.public / "evals/skills"
        skills.mkdir(parents=True)
        for name in ["cases", "schemas"]:
            shutil.copytree(ROOT / "evals/skills" / name, skills / name)
        for name in ["event-catalog.json", "protocol.json", "validate.py"]:
            shutil.copy2(ROOT / "evals/skills" / name, skills / name)
        routing = skills / "routing"
        routing.mkdir()
        shutil.copy2(ROOT / audit.EVIDENCE_NAME, self.public / audit.EVIDENCE_NAME)
        self.private = base / "private"
        self.private.mkdir(mode=0o700)
        self.old_root = self.private / "collection-03"
        self.old_root.mkdir(mode=0o700)
        self.new_root = self.private / "collection-04"
        self.new_root.mkdir(mode=0o700)
        self.case_path = self.new_root / "cases.json"
        self.evidence_path = self.new_root / "evidence.json"
        self.old = []
        caps = list(audit.legacy.validate.CAPABILITIES)
        categories = ["explicit", "explicit", "implicit", "implicit", "contextual", "contextual",
                      "negative", "negative", "negative", "safety", "safety", "safety"]
        for i in range(12):
            cap = caps[i % 6]
            entry, route = audit.legacy.validate.CAPABILITIES[cap]
            negative = 6 <= i < 9
            stop = i >= 9
            self.old.append({"schemaVersion": "1.0", "caseId": f"SE-{1000+i}", "category": categories[i],
                "capability": cap, "mode": "do-not-use" if negative else "stop" if stop else "use",
                "prompt": f"合成旧入力 {i}", "context": [f"合成前提 {i}"], "mandatory": True,
                "expected": {"sixSkill": None if negative else cap,
                    "threeEntry": None if negative else {"entry": entry, "path": route},
                    "outcome": "not-applicable" if negative else "stop" if stop else "proceed",
                    "requiredEvents": [], "forbiddenEvents": []}})
        self.cases = copy.deepcopy(self.old)
        for i, case in enumerate(self.cases):
            case["caseId"] = f"SE-{1100+i}"
            if 6 <= i < 9:
                case["prompt"] = f"合成新入力 {i}"
        old_sha = save(self.old_root / "cases.json", {"setVersion": audit.PREVIOUS, "cases": self.old})
        initial = copy.deepcopy(self.old)
        for i, case in enumerate(initial):
            case.update(caseId=f"SE-{800+i}", prompt=f"合成初期入力 {i}")
        initial_sha = save(self.private / "cases.json", {"setVersion": audit.INITIAL, "cases": initial})
        review_sha = save(self.old_root / "independent-receipt.json",
                          {"status": "stopped_on_p1_p2", "affectedCaseCount": 3, "casesSha256": old_sha})
        retained = [c for i, c in enumerate(self.old) if not 6 <= i < 9]
        self.retention = {"schemaVersion": "1.0", "sourceSetVersion": audit.PREVIOUS,
            "sourceCasesSha256": old_sha, "independentReceiptSha256": review_sha,
            "retainedCaseIds": [c["caseId"] for c in retained],
            "replacedCaseIds": [c["caseId"] for c in self.old[6:9]],
            "retainedCaseSha256": {c["caseId"]: audit.case_digest(c) for c in retained}}
        retention_sha = save(self.new_root / "retention.json", self.retention)
        snapshot = self.public / ".venv/snapshot"
        resources, descriptions = {}, []
        for cap in caps:
            entry = audit.legacy.validate.CAPABILITIES[cap][0]
            name = f"resources/{entry}/skills/{cap}/SKILL.md"
            path = snapshot / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("合成の固定本文 " + cap)
            resources[name] = hashlib.sha256(path.read_bytes()).hexdigest()
            descriptions.append({"name": cap, "path": name})
        self.manifest = {"sourceCommit": "a" * 40, "candidateVersion": "synthetic",
                         "skills": descriptions, "resources": resources}
        manifest_sha = save(snapshot / "manifest.json", self.manifest)
        self.contract = {"collectionVersion": "production-routing-held-out-collection-0.4.0", "setVersion": audit.VERSION,
            "storageAuthorization": {"root": str(self.new_root)},
            "inputSha256": {n: hashlib.sha256((self.public / n).read_bytes()).hexdigest() for n in audit.INPUT_NAMES},
            "excludedSets": {audit.INITIAL: {"path": str(self.private / "cases.json"), "sha256": initial_sha},
                             audit.PREVIOUS: {"path": str(self.old_root / "cases.json"), "sha256": old_sha}},
            "retention": {"sha256": retention_sha, "independentReceiptSha256": review_sha},
            "candidate": {"snapshotRelativePath": ".venv/snapshot", "sourceCommit": "a" * 40,
                "candidateVersion": "synthetic", "manifestSha256": manifest_sha, "skillCount": 6, "resourceCount": 6}}
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.multiple(audit, ROOT=self.public, PRIVATE_BASE=self.private))
        self.stack.enter_context(patch.object(audit.legacy, "ROOT", self.public))
        self.stack.enter_context(patch.multiple(audit.legacy.validate, ROOT=skills, CASES=skills / "cases",
                                              SCHEMAS=skills / "schemas", EVENT_CATALOG=skills / "event-catalog.json"))
        public = audit.legacy.validate.load_cases()
        self.evidence = {"schemaVersion": "1.0", "setVersion": audit.VERSION, "casesSha256": "",
            "routing": [], "lineage": [], "publicCasesConsidered": [c["caseId"] for c in public],
            "excludedCasesConsidered": {audit.INITIAL: [c["caseId"] for c in initial],
                                       audit.PREVIOUS: [c["caseId"] for c in self.old]},
            "noveltyComparisons": [], "newCasePairs": []}
        new_ids = []
        for i, case in enumerate(self.cases):
            self.evidence["routing"].append({"caseId": case["caseId"], "primaryRequest": "PRIVATE_SENTINEL",
                "requestedScope": "合成範囲", "causalPreconditions": ["合成条件"], "stoppingReason": "合成判断理由",
                "outcome": case["expected"]["outcome"], "skills": [
                    {"skill": row["name"], "applicability": "applicable" if row["name"] == case["expected"]["sixSkill"] else "not-applicable",
                     "reason": "合成適用根拠", "source": {"path": row["path"], "sha256": resources[row["path"]], "anchor": "合成の固定本文 " + row["name"]}}
                    for row in descriptions]})
            is_new = 6 <= i < 9
            self.evidence["lineage"].append({"caseId": case["caseId"], "origin": "new" if is_new else "retained",
                "previousCaseId": None if is_new else self.old[i]["caseId"],
                "previousCaseSha256": None if is_new else audit.case_digest(self.old[i])})
            if is_new:
                new_ids.append(case["caseId"])
                self.evidence["noveltyComparisons"].append({"caseId": case["caseId"], "expectedSkill": None,
                    "outcome": "not-applicable", "nearestPublicCaseIds": [public[0]["caseId"]],
                    "nearestExcludedCases": [{"setVersion": audit.INITIAL, "caseId": initial[0]["caseId"]},
                                             {"setVersion": audit.PREVIOUS, "caseId": self.old[0]["caseId"]}],
                    "decisiveDifference": "合成の判断差", "counterfactual": {"changedCondition": "合成条件差",
                        "measuredConsequence": "selection", "reason": "合成の変更理由"},
                    "sameDecisionUnderSamePremises": False, "affectsMeasuredDecision": True})
        self.evidence["newCasePairs"] = [{"leftCaseId": a, "rightCaseId": b, "decisiveDifference": "合成差",
                "sameDecisionUnderSamePremises": False, "affectsMeasuredDecision": True} for a, b in combinations(new_ids, 2)]
        self.persist()

    def persist(self):
        self.evidence["casesSha256"] = save(self.case_path, {"setVersion": audit.VERSION, "cases": self.cases})
        save(self.evidence_path, self.evidence)

    def run_audit(self):
        return audit.audit(self.contract, self.case_path)

    def test_new_three_and_retained_nine_are_not_semantic_certification(self):
        result = self.run_audit()
        self.assertEqual((result["newCaseCount"], result["retainedCaseCount"]), (3, 9))
        self.assertEqual(result["routingAssessmentCount"], 12)
        self.assertEqual(result["semanticNovelty"], "requires_independent_review")
        self.assertFalse(result["certifiesSkillGate"])
        self.assertNotIn("PRIVATE_SENTINEL", json.dumps(result))

    def test_individual_negative_with_other_applicable_skill_is_rejected(self):
        self.evidence["routing"][6]["skills"][1]["applicability"] = "applicable"
        self.persist()
        with self.assertRaisesRegex(ValueError, "global routing contradiction"):
            self.run_audit()

    def test_stop_preserves_selection_and_rejects_global_negative(self):
        self.run_audit()
        self.evidence["routing"][9]["skills"][3]["applicability"] = "not-applicable"
        self.persist()
        with self.assertRaisesRegex(ValueError, "global routing contradiction"):
            self.run_audit()

    def test_unresolved_competing_or_missing_skill_assessments_are_rejected(self):
        original = copy.deepcopy(self.evidence)
        mutations = [lambda e: e["routing"][0]["skills"][1].update(applicability="applicable"),
                     lambda e: e["routing"][6]["skills"][1].update(applicability="undetermined"),
                     lambda e: e["routing"][0]["skills"].__setitem__(1, copy.deepcopy(e["routing"][0]["skills"][0])),
                     lambda e: e["routing"][0].update(caseId=e["routing"][1]["caseId"])]
        for change in mutations:
            with self.subTest(change=change):
                self.evidence = copy.deepcopy(original)
                change(self.evidence)
                self.persist()
                with self.assertRaises(ValueError): self.run_audit()

    def test_fixed_source_references_and_case_hash_are_required(self):
        for key, value in [("path", "resources/bitz-core/.credentials.json"), ("sha256", "0" * 64)]:
            with self.subTest(key=key):
                original = copy.deepcopy(self.evidence)
                self.evidence["routing"][0]["skills"][0]["source"][key] = value
                self.persist()
                with self.assertRaisesRegex(ValueError, "routing source binding"): self.run_audit()
                self.evidence = original
        self.persist()
        self.evidence["casesSha256"] = "0" * 64
        save(self.evidence_path, self.evidence)
        with self.assertRaisesRegex(ValueError, "evidence case binding"): self.run_audit()

    def test_retained_input_or_expectation_changes_are_rejected(self):
        self.cases[0]["prompt"] += " 変更"
        self.persist()
        with self.assertRaisesRegex(ValueError, "retained case changed"): self.run_audit()
        old = copy.deepcopy(self.old[0]); old["caseId"] = self.cases[0]["caseId"]
        self.cases[0] = old
        self.cases[0]["expected"]["requiredEvents"] = ["invoke-bitz"]
        self.persist()
        with self.assertRaisesRegex(ValueError, "retained case changed"): self.run_audit()

    def test_source_anchor_must_exist_in_fixed_body(self):
        self.evidence["routing"][0]["skills"][0]["source"]["anchor"] = "存在しない合成見出し"
        self.persist()
        with self.assertRaisesRegex(ValueError, "routing source anchor"): self.run_audit()

    def test_missing_duplicate_or_undeclared_retention_is_rejected(self):
        original = copy.deepcopy(self.evidence)
        for old_id in [self.old[6]["caseId"], self.old[1]["caseId"]]:
            self.evidence = copy.deepcopy(original)
            self.evidence["lineage"][0]["previousCaseId"] = old_id
            self.persist()
            with self.assertRaisesRegex(ValueError, "undeclared retention"): self.run_audit()

    def test_new_case_cannot_reuse_previous_input_even_with_new_id(self):
        self.cases[6]["prompt"] = self.old[6]["prompt"]
        self.persist()
        with self.assertRaisesRegex(ValueError, "undeclared input reuse"): self.run_audit()

    def test_all_exclusion_groups_and_new_pairs_are_required(self):
        original = copy.deepcopy(self.evidence)
        mutations = [lambda e: e["publicCasesConsidered"].pop(),
                     lambda e: e["excludedCasesConsidered"][audit.PREVIOUS].pop(),
                     lambda e: e["newCasePairs"].__setitem__(0, copy.deepcopy(e["newCasePairs"][1])),
                     lambda e: e["noveltyComparisons"][0]["nearestExcludedCases"][0].update(caseId="SE-99999"),
                     lambda e: e["noveltyComparisons"][0].update(expectedSkill="bitz-core"),
                     lambda e: e["noveltyComparisons"][0].update(caseId=e["noveltyComparisons"][1]["caseId"])]
        for change in mutations:
            with self.subTest(change=change):
                self.evidence = copy.deepcopy(original)
                change(self.evidence)
                self.persist()
                with self.assertRaises(ValueError): self.run_audit()

    def test_public_inventory_and_unsafe_declared_input_are_rejected_before_loading(self):
        (self.public / "evals/skills/cases/extra.json").write_text("[]")
        with patch.object(audit.legacy.validate, "load_cases", side_effect=AssertionError("premature load")):
            with self.assertRaisesRegex(ValueError, "public case inventory"): self.run_audit()
        self.contract["inputSha256"][".env"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "input inventory"): self.run_audit()

    def test_private_modes_symlinks_and_retention_or_review_drift_are_rejected(self):
        self.evidence_path.chmod(0o644)
        with self.assertRaisesRegex(ValueError, "private file permissions"): self.run_audit()
        self.evidence_path.chmod(0o600)
        target = self.evidence_path.with_name("original.json")
        self.evidence_path.rename(target); self.evidence_path.symlink_to(target)
        with self.assertRaisesRegex(ValueError, "symlink storage"): self.run_audit()
        self.evidence_path.unlink(); target.rename(self.evidence_path)
        for path in [self.new_root / "retention.json", self.old_root / "independent-receipt.json"]:
            original = path.read_bytes(); path.write_bytes(original + b"\n")
            with self.assertRaises(ValueError): self.run_audit()
            path.write_bytes(original)

    def test_duplicate_json_keys_and_blank_proofs_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate JSON key"): audit.load(b'{"x":1,"x":2}')
        self.evidence["noveltyComparisons"][0]["counterfactual"]["reason"] = "   "
        self.persist()
        with self.assertRaises(Exception): self.run_audit()

    def test_multiple_case_reads_must_bind_to_identical_bytes(self):
        loader = audit.legacy.validate.load_held_out_cases
        for target in [self.case_path, self.old_root / "cases.json"]:
            def drift(path):
                cases, metadata = loader(path)
                if path == target:
                    metadata["sha256"] = "0" * 64
                return cases, metadata
            with self.subTest(target=target.name), patch.object(audit.legacy.validate, "load_held_out_cases", drift):
                with self.assertRaisesRegex(ValueError, "read drift"): self.run_audit()

    def test_candidate_body_change_after_first_hash_check_is_rejected(self):
        initial = audit.legacy.audit_candidate
        def drift(contract):
            initial(contract)
            path = self.public / ".venv/snapshot" / self.manifest["skills"][0]["path"]
            path.write_text("監査後の合成改変")
        with patch.object(audit.legacy, "audit_candidate", drift):
            with self.assertRaisesRegex(ValueError, "body read drift"): self.run_audit()

    def test_cli_redacts_schema_diagnostics_and_rejects_source_before_git(self):
        self.evidence["routing"][0]["primaryRequest"] = {"secret": "PRIVATE_SENTINEL"}
        self.persist()
        contract = copy.deepcopy(self.contract); contract["sourceFiles"] = sorted(audit.SOURCE_NAMES)
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(sys, "argv", ["audit", "--source", "a" * 40, "--cases", str(self.case_path)]), \
             patch.object(audit.source_guard, "git", return_value=json.dumps(contract).encode()), \
             patch.object(audit.source_guard, "verify"), redirect_stdout(stdout), redirect_stderr(stderr):
            self.assertEqual(audit.main(), 1)
        self.assertEqual(json.loads(stdout.getvalue()), {"status": "blocked", "errorType": "ValidationError"})
        self.assertEqual(stderr.getvalue(), "")
        with patch.object(sys, "argv", ["audit", "--source", "main", "--cases", str(self.case_path)]), \
             patch.object(audit.source_guard, "git") as git, redirect_stdout(io.StringIO()):
            self.assertEqual(audit.main(), 1)
        git.assert_not_called()


if __name__ == "__main__":
    unittest.main()
