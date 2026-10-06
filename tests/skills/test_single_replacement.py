"""実保持本文を使わず、1件の差替えと11件の来歴・観測可能な差を検査する。"""
from __future__ import annotations

import copy
from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


base = module("replacement_base_fixture", "tests/skills/test_held_out_remediation.py")
audit = module("single_replacement_audit", "evals/skills/routing/audit_single_replacement.py")
save = base.save


class SingleReplacementTests(unittest.TestCase):
    def setUp(self):
        self.initial = True
        base.HeldOutRemediationTests.setUp(self)
        self.initial = False
        self.previous = copy.deepcopy(self.cases)
        self.previous_root = self.new_root
        previous_sha = save(self.previous_root / "cases.json", {"setVersion": audit.PREVIOUS, "cases": self.previous})
        report = "\n".join("### " + c["caseId"] for c in self.previous)
        report += "\n### " + self.previous[6]["caseId"] + " P2\n合成の不通過理由\n"
        report_path = self.previous_root / "independent-review.md"
        report_path.write_text(report); report_path.chmod(0o600)
        report_sha = audit.digest(report_path.read_bytes())
        review_sha = save(self.previous_root / "independent-receipt.json", {
            "status": "stopped_on_p2", "severityCounts": {"P1": 0, "P2": 1}, "affectedCaseCount": 1,
            "routingSemanticsPassedCount": 12, "novelNewCaseCount": 2, "casesSha256": previous_sha,
            "filesSha256": {"independent-review.md": report_sha}})
        self.new_root = self.private / "collection-05"
        self.new_root.mkdir(mode=0o700)
        self.case_path = self.new_root / "cases.json"
        self.evidence_path = self.new_root / "evidence.json"
        for i, case in enumerate(self.cases):
            case["caseId"] = f"SE-{1200+i}"
        self.cases[6]["prompt"] = "合成の第五集合だけの新入力"
        self.retention = {"schemaVersion": "1.0", "sourceSetVersion": audit.PREVIOUS,
            "sourceCasesSha256": previous_sha, "independentReceiptSha256": review_sha,
            "independentReportSha256": report_sha,
            "retainedCaseIds": [c["caseId"] for i, c in enumerate(self.previous) if i != 6],
            "replacedCaseIds": [self.previous[6]["caseId"]],
            "retainedCaseSha256": {c["caseId"]: audit.case_digest(c) for i, c in enumerate(self.previous) if i != 6}}
        retention_sha = save(self.new_root / "retention.json", self.retention)
        (self.public / audit.EVIDENCE_NAME).write_bytes((ROOT / audit.EVIDENCE_NAME).read_bytes())
        self.contract.update(collectionVersion="production-routing-held-out-collection-0.5.0", setVersion=audit.VERSION,
            storageAuthorization={"root": str(self.new_root)},
            retention={"sha256": retention_sha, "independentReceiptSha256": review_sha, "independentReportSha256": report_sha},
            inputSha256={n: audit.digest((self.public / n).read_bytes()) for n in audit.INPUT_NAMES})
        self.contract["excludedSets"][audit.PREVIOUS] = {"path": str(self.previous_root / "cases.json"), "sha256": previous_sha}
        self.evidence["setVersion"] = audit.VERSION
        for i, record in enumerate(self.evidence["routing"]):
            record["caseId"] = self.cases[i]["caseId"]
        for i, record in enumerate(self.evidence["lineage"]):
            record.update(caseId=self.cases[i]["caseId"], origin="new" if i == 6 else "retained",
                          previousCaseId=None if i == 6 else self.previous[i]["caseId"],
                          previousCaseSha256=None if i == 6 else audit.case_digest(self.previous[i]))
        self.evidence["excludedCasesConsidered"][audit.PREVIOUS] = [c["caseId"] for c in self.previous]
        row = self.evidence["noveltyComparisons"][0]
        row["caseId"] = self.cases[6]["caseId"]
        row["nearestExcludedCases"].append({"setVersion": audit.PREVIOUS, "caseId": self.previous[6]["caseId"]})
        skill = self.manifest["skills"][0]
        cap = skill["name"]
        package, route = audit.legacy.validate.CAPABILITIES[cap]
        row["counterfactual"].update(
            beforeDecision=copy.deepcopy(self.cases[6]["expected"]),
            afterDecision={"sixSkill": cap, "threeEntry": {"entry": package, "path": route}, "outcome": "proceed",
                           "requiredEvents": [], "forbiddenEvents": []},
            source={"path": skill["path"], "sha256": self.manifest["resources"][skill["path"]],
                    "anchor": "合成の固定本文 " + cap})
        self.evidence["noveltyComparisons"] = [row]
        self.evidence["newCasePairs"] = []
        self.stack.enter_context(patch.multiple(audit, ROOT=self.public, PRIVATE_BASE=self.private))
        self.persist()

    def persist(self):
        if self.initial:
            return base.HeldOutRemediationTests.persist(self)
        self.evidence["casesSha256"] = save(self.case_path, {"setVersion": audit.VERSION, "cases": self.cases})
        save(self.evidence_path, self.evidence)

    def run_audit(self):
        return audit.audit(self.contract, self.case_path)

    def test_one_new_eleven_retained_requires_semantic_review(self):
        result = self.run_audit()
        self.assertEqual((result["newCaseCount"], result["retainedCaseCount"]), (1, 11))
        self.assertEqual(result["counterfactualDecisionCount"], 2)
        self.assertEqual(result["privateExclusionCounts"], [12, 12, 12])
        self.assertEqual(result["semanticNovelty"], "requires_independent_review")
        self.assertNotIn("PRIVATE_SENTINEL", json.dumps(result))
        self.assertFalse(result["certifiesSkillGate"])

    def test_retained_fields_and_failure_partition_cannot_change(self):
        self.cases[7]["prompt"] += "変更"
        self.persist()
        with self.assertRaisesRegex(ValueError, "retained case changed"): self.run_audit()
        self.cases[7] = copy.deepcopy(self.previous[7]); self.cases[7]["caseId"] = "SE-1207"
        self.persist()
        retained = self.retention["retainedCaseIds"]
        retained.remove(self.previous[7]["caseId"]); retained.append(self.previous[6]["caseId"])
        self.retention["replacedCaseIds"] = [self.previous[7]["caseId"]]
        self.contract["retention"]["sha256"] = save(self.new_root / "retention.json", self.retention)
        with self.assertRaisesRegex(ValueError, "retention partition"): self.run_audit()

    def test_old_receipt_or_report_changes_are_rejected(self):
        for name in ["independent-receipt.json", "independent-review.md"]:
            p = self.previous_root / name
            raw = p.read_bytes(); p.write_bytes(raw + b"\n")
            with self.assertRaisesRegex(ValueError, "retention review binding"): self.run_audit()
            p.write_bytes(raw)

    def test_report_cannot_select_unknown_or_multiple_failed_cases(self):
        good = "\n".join("### " + c["caseId"] for c in self.previous)
        for suffix in ["\n### SE-99999 P2", "", "\n### SE-1106 P2\n### SE-1107 P2"]:
            with self.subTest(suffix=suffix), self.assertRaises(ValueError):
                audit.replacement_from_report(good + suffix, self.previous)

    def test_new_input_cannot_copy_either_previous_collection(self):
        for c in [self.old[6], self.previous[6], self.previous[7]]:
            self.cases[6]["prompt"], self.cases[6]["context"] = c["prompt"], copy.deepcopy(c["context"])
            self.persist()
            with self.assertRaisesRegex(ValueError, "undeclared input reuse|duplicate inputs|重複"): self.run_audit()

    def test_all_exclusions_and_empty_new_pairs_are_required(self):
        original = copy.deepcopy(self.evidence)
        mutations = [lambda e: e["excludedCasesConsidered"][audit.PREVIOUS].pop(),
                     lambda e: e["noveltyComparisons"][0]["nearestExcludedCases"].pop(),
                     lambda e: e["noveltyComparisons"][0].update(caseId="SE-1207"),
                     lambda e: e.update(newCasePairs=[{}])]
        for mutate in mutations:
            self.evidence = copy.deepcopy(original); mutate(self.evidence); self.persist()
            with self.assertRaises(Exception): self.run_audit()

    def test_same_or_unbound_counterfactual_decision_is_rejected(self):
        proof = self.evidence["noveltyComparisons"][0]["counterfactual"]
        after = copy.deepcopy(proof["afterDecision"])
        proof["afterDecision"] = copy.deepcopy(proof["beforeDecision"])
        self.persist()
        with self.assertRaisesRegex(ValueError, "unmeasured difference"): self.run_audit()
        proof["afterDecision"] = after
        proof["beforeDecision"] = after
        self.persist()
        with self.assertRaisesRegex(ValueError, "before binding"): self.run_audit()

    def test_source_anchor_hash_and_unlisted_paths_are_rejected(self):
        original = copy.deepcopy(self.evidence)
        for field, value in [("path", "resources/bitz-core/.env"), ("sha256", "0" * 64), ("anchor", "存在しない見出し")]:
            self.evidence = copy.deepcopy(original)
            self.evidence["noveltyComparisons"][0]["counterfactual"]["source"][field] = value
            self.persist()
            with self.assertRaisesRegex(ValueError, "source binding"): self.run_audit()

    def test_counterfactual_route_unknown_events_and_consequence_are_rejected(self):
        original = copy.deepcopy(self.evidence)
        mutations = [lambda p: p["afterDecision"].update(threeEntry=None),
                     lambda p: p["afterDecision"].update(requiredEvents=["invented-event"]),
                     lambda p: p["afterDecision"].update(requiredEvents=["invoke-bitz"], forbiddenEvents=["invoke-bitz"]),
                     lambda p: p.update(measuredConsequence="question"),
                     lambda p: p.update(measuredConsequence="stop")]
        for mutate in mutations:
            self.evidence = copy.deepcopy(original)
            mutate(self.evidence["noveltyComparisons"][0]["counterfactual"])
            self.persist()
            with self.assertRaises(Exception): self.run_audit()

    def test_scope_claim_requires_outcome_or_event_difference(self):
        row = copy.deepcopy(self.evidence["noveltyComparisons"][0])
        row["counterfactual"]["beforeDecision"] = copy.deepcopy(self.cases[0]["expected"])
        row["counterfactual"]["afterDecision"] = copy.deepcopy(self.cases[1]["expected"])
        row["counterfactual"]["measuredConsequence"] = "scope"
        bodies = {r["path"]: "合成の固定本文 " + r["name"] for r in self.manifest["skills"]}
        with self.assertRaisesRegex(ValueError, "consequence unobserved"):
            audit.check_counterfactual(self.cases[0], row, self.manifest, bodies)

    def test_event_order_alone_does_not_make_measured_difference(self):
        self.cases[6]["expected"]["forbiddenEvents"] = ["invoke-bitz", "assign-q0"]
        proof = self.evidence["noveltyComparisons"][0]["counterfactual"]
        proof["beforeDecision"] = copy.deepcopy(self.cases[6]["expected"])
        proof["afterDecision"] = copy.deepcopy(proof["beforeDecision"])
        proof["afterDecision"]["forbiddenEvents"].reverse()
        self.persist()
        with self.assertRaisesRegex(ValueError, "unmeasured difference"): self.run_audit()

    def test_global_routing_still_rejects_other_applicable_skill(self):
        self.evidence["routing"][6]["skills"][0]["applicability"] = "applicable"
        self.persist()
        with self.assertRaisesRegex(ValueError, "global routing contradiction"): self.run_audit()

    def test_input_inventory_and_private_modes_are_enforced(self):
        self.contract["inputSha256"][".env"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "input inventory"): self.run_audit()
        del self.contract["inputSha256"][".env"]
        self.evidence_path.chmod(0o644)
        with self.assertRaisesRegex(ValueError, "permissions"): self.run_audit()

    def test_cli_rejects_unresolved_source_without_git_or_secret_diagnostic(self):
        output = io.StringIO()
        with patch.object(sys, "argv", ["audit", "--source", "HEAD", "--cases", str(self.case_path)]), \
                patch.object(audit.source_guard, "git", side_effect=AssertionError("PRIVATE_SENTINEL")), redirect_stdout(output):
            self.assertEqual(audit.main(), 1)
        self.assertEqual(json.loads(output.getvalue()), {"status": "blocked", "errorType": "ValueError"})
        output = io.StringIO()
        inventory = list(audit.SOURCE_NAMES) + [audit.CONTRACT_NAME]
        with patch.object(sys, "argv", ["audit", "--source", "a" * 40, "--cases", str(self.case_path)]), \
                patch.object(audit.source_guard, "git", return_value=json.dumps({"sourceFiles": inventory}).encode()), \
                patch.object(audit.source_guard, "verify", side_effect=AssertionError("premature guard")), redirect_stdout(output):
            self.assertEqual(audit.main(), 1)
        self.assertEqual(json.loads(output.getvalue()), {"status": "blocked", "errorType": "ValueError"})


if __name__ == "__main__":
    unittest.main()
