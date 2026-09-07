"""Regression checks that malformed evidence is not silently accepted."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import validate_step0b as audit


class AuditTests(unittest.TestCase):
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
