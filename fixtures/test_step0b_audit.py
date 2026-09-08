"""Regression checks that malformed evidence is not silently accepted."""
import json
import copy
from pathlib import Path
import tempfile
import shutil
import unittest
from unittest.mock import patch

import validate_step0b as audit
from conformance.diagnostic_coverage import LEDGER, validate
from conformance.target_vectors import HERE as TARGET_HERE, validate as validate_targets
from conformance.initial_fixtures import validate as validate_initial, compare_state


class AuditTests(unittest.TestCase):
    def test_initial_fixtures(self):
        result = validate_initial()
        self.assertEqual(result["errors"], [])
        self.assertEqual(len(result["prepared"]), 5)
        self.assertEqual(result["core_execution"], "Not run")

    def test_initial_fixture_rejects_corrupted_evidence(self):
        mutations = [
            ("SINGLE-004-01/expected/check.json", lambda value: value.update(status="passed")),
            ("SINGLE-004-02/expected/check.json", lambda value: value["diagnostics"][0]["source"].update(key="language")),
            ("SINGLE-003/manifest.json", lambda value: value["invocation"]["argv"].remove("--full")),
            ("SINGLE-001/side-effects.json", lambda value: value["after"]["cache"].update(lock={"kind": "directory"})),
            ("SINGLE-001/side-effects.json", lambda value: value["before"]["repository"][".spec/bitz.yaml"].update(sha256="0" * 64)),
            ("SINGLE-002/expected/doctor.json", lambda value: value["diagnostics"][0].pop("suggestedAction")),
        ]
        for relative, mutate in mutations:
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                shutil.copytree(audit.FIXTURES / "single", root / "single")
                for name in ("manifest", "result", "side-effects"):
                    shutil.copy2(audit.FIXTURES / f"{name}.schema.json", root)
                path = root / "single" / relative
                value = json.loads(path.read_text())
                mutate(value)
                path.write_text(json.dumps(value))
                self.assertTrue(validate_initial(root)["errors"])

    def test_side_effect_comparison_rejects_each_changed_boundary(self):
        state = json.loads((audit.FIXTURES / "single/SINGLE-001/side-effects.json").read_text())["after"]
        for name in ("repository", "home", "cache", "temporary"):
            changed = copy.deepcopy(state)
            changed[name]["unexpected"] = {"kind": "directory"}
            self.assertEqual(compare_state(state, changed), [name])
        changed = copy.deepcopy(state)
        changed["git"]["index"] = "changed index"
        self.assertEqual(compare_state(state, changed), ["git"])

    def test_target_vectors(self):
        data = json.loads((TARGET_HERE / "targets/cases.json").read_text())
        self.assertEqual(validate_targets(data)["errors"], [])
        missing = copy.deepcopy(data)
        missing["cases"] = [c for c in missing["cases"] if c["id"] != "BASIC-ADR-verify"]
        self.assertTrue(validate_targets(missing)["errors"])
        leaked = copy.deepcopy(data)
        case = next(c for c in leaked["cases"] if c["id"] == "REFINEMENT-TRANSITIVE")
        case["expected"]["targetStatements"].append("REQ-009:AC-01")
        self.assertTrue(validate_targets(leaked)["errors"])
        wrong_order = copy.deepcopy(data)
        case = next(c for c in wrong_order["cases"] if c["id"] == "SOURCE-LINE-ORDER")
        case["expected"]["targetStatements"].reverse()
        self.assertTrue(validate_targets(wrong_order)["errors"])
        bad_id = copy.deepcopy(data)
        bad_id["cases"][0]["graph"][0]["requires"] = ["REQ-999"]
        self.assertTrue(validate_targets(bad_id)["errors"])
        stale = copy.deepcopy(data)
        stale["contractSha256"] = "0" * 64
        self.assertTrue(validate_targets(stale)["errors"])
        wrong_kind = copy.deepcopy(data)
        wrong_kind["cases"][0]["rootKind"] = "TASK"
        self.assertTrue(validate_targets(wrong_kind)["errors"])

    def test_diagnostic_ledger_rejects_missing_unknown_and_stale(self):
        original = json.loads(LEDGER.read_text())
        self.assertEqual(validate(original)["errors"], [])
        self.assertEqual(validate(original)["semantic_coverage"], "Passed")
        missing = copy.deepcopy(original)
        missing["groups"][0]["conditionIds"].pop()
        self.assertTrue(validate(missing)["errors"])
        unknown = copy.deepcopy(original)
        unknown["groups"][0]["conditionIds"].append("UNKNOWN-CONDITION")
        self.assertTrue(validate(unknown)["errors"])
        stale = copy.deepcopy(original)
        stale["sources"][next(iter(stale["sources"]))] = "0" * 64
        self.assertTrue(validate(stale)["errors"])
        false_pass = copy.deepcopy(original)
        false_pass["reviewStatus"] = "Passed"
        false_pass["openIssues"] = ["UNRESOLVED-CONDITION"]
        self.assertTrue(validate(false_pass)["errors"])
        pending = copy.deepcopy(false_pass)
        pending["reviewStatus"] = "Pending"
        self.assertEqual(validate(pending)["semantic_coverage"], "Pending")

    def test_invalid_public_result_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "result.md").write_text('```json\n{"operation":"check"}\n```\n')
            with patch.object(audit, "DETAIL", root), patch.object(audit, "ROOT", root):
                result = audit.public_json()
            self.assertEqual(len(result["errors"]), 1)

    def test_ir_operation_is_not_a_core_result(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "ir.md").write_text('```json\n{"operation":{"kind":"THEN","text":"example"}}\n```\n')
            with patch.object(audit, "DETAIL", root), patch.object(audit, "ROOT", root):
                result = audit.public_json()
            self.assertEqual(result["errors"], [])
            self.assertEqual(len(result["non_public_result_examples"]), 1)

    def test_unknown_nonterminal_detected(self):
        with patch.object(audit, "blocks", return_value=['statement = missing, "literal" ;']):
            result = audit.grammar()
        self.assertEqual(result["errors"], ["missing"])

    def test_missing_fixture_detected(self):
        result = audit.matrix()
        self.assertGreater(result["matrix_ids"], 0)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            # Preserve real schemas but provide no acceptance fixture directories.
            for name in ("manifest.schema.json", "result.schema.json"):
                (root / name).write_text((audit.FIXTURES / name).read_text())
            with patch.object(audit, "FIXTURES", root):
                missing = audit.matrix()
        self.assertEqual(len(missing["missing_fixtures"]), missing["matrix_ids"])


if __name__ == "__main__":
    unittest.main()
