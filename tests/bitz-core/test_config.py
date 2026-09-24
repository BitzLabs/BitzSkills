"""`.spec/bitz.yaml`読込みのレビュー是正点に対する単体試験。

- BOM warningがstop有無にかかわらず残ること（source.workspaceIdの同一性反映を含む）
- schemaVersion majorの判定が他fieldの型・必須検査より先に行われること
- 独立した型・必須errorが全件返ること
"""

import unittest

from bitz.config import load_config


def _bytes(text: str) -> bytes:
    return text.encode("utf-8")


class BomWarningTests(unittest.TestCase):
    def test_bom_warning_present_on_success(self):
        raw = b"\xef\xbb\xbf" + _bytes('schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\n')
        outcome = load_config(raw)
        self.assertFalse(outcome.stop)
        codes = [d.code for d in outcome.warnings]
        self.assertIn("SPEC-INPUT-BOM-001", codes)
        bom = next(d for d in outcome.warnings if d.code == "SPEC-INPUT-BOM-001")
        # 同一性が確定した場合は実効workspace idを使う。
        self.assertEqual(bom.source["workspaceId"], "root")

    def test_bom_warning_present_when_stopped_with_null_identity(self):
        raw = b"\xef\xbb\xbf" + _bytes('schemaVersion: "1.0"\nlanguage: 1\nearsAi: "1.0"\n')
        outcome = load_config(raw)
        self.assertTrue(outcome.stop)
        self.assertEqual(outcome.workspace_id, None)
        codes = [d.code for d in outcome.warnings]
        self.assertIn("SPEC-INPUT-BOM-001", codes)
        bom = next(d for d in outcome.warnings if d.code == "SPEC-INPUT-BOM-001")
        # 同一性不成立で停止した場合はnull。
        self.assertIsNone(bom.source["workspaceId"])

    def test_bom_warning_present_when_stopped_at_schema_major(self):
        raw = b"\xef\xbb\xbf" + _bytes('schemaVersion: "2.0"\nlanguage: ja\nearsAi: "1.0"\n')
        outcome = load_config(raw)
        self.assertTrue(outcome.stop)
        self.assertEqual(outcome.stop_stage, "schema-major")
        self.assertEqual(outcome.workspace_id, "root")
        bom = next(d for d in outcome.warnings if d.code == "SPEC-INPUT-BOM-001")
        self.assertEqual(bom.source["workspaceId"], "root")


class SchemaMajorOrderingTests(unittest.TestCase):
    def test_major_mismatch_wins_over_unrelated_type_errors(self):
        raw = _bytes('schemaVersion: "2.0"\nlanguage: 1\nearsAi: "1.0"\nfutureOption: true\n')
        outcome = load_config(raw)
        self.assertTrue(outcome.stop)
        self.assertEqual(outcome.stop_stage, "schema-major")
        self.assertEqual(len(outcome.diagnostics), 1)
        self.assertEqual(outcome.diagnostics[0].code, "SPEC-CONFIG-SCHEMA-001")
        self.assertEqual(outcome.diagnostics[0].resultStatus, "blocked")
        self.assertEqual(outcome.diagnostics[0].summary, "未対応のSchema majorです")

    def test_schema_version_type_error_wins_over_major_check(self):
        # schemaVersion自体が型不正なら、majorの検討に進まずschemaVersionの型errorを返す。
        raw = _bytes("schemaVersion: 2\nlanguage: ja\nearsAi: \"1.0\"\n")
        outcome = load_config(raw)
        self.assertTrue(outcome.stop)
        self.assertEqual(outcome.stop_stage, "config")
        self.assertEqual(len(outcome.diagnostics), 1)
        self.assertEqual(outcome.diagnostics[0].summary, "schemaVersionはstringで指定してください")


class IndependentHardErrorsTests(unittest.TestCase):
    def test_all_independent_field_errors_are_returned(self):
        raw = _bytes('schemaVersion: "1.0"\nlanguage: 1\nearsAi: 2\n')
        outcome = load_config(raw)
        self.assertTrue(outcome.stop)
        self.assertEqual(outcome.stop_stage, "config")
        summaries = sorted(d.summary for d in outcome.diagnostics)
        self.assertEqual(
            summaries,
            ["earsAiはstringで指定してください", "languageはstringで指定してください"],
        )
        for d in outcome.diagnostics:
            self.assertIsNone(d.source["workspaceId"])

    def test_no_duplicate_diagnostic_for_same_key(self):
        raw = _bytes('schemaVersion: "1.0"\nlanguage: 1\nearsAi: "1.0"\n')
        outcome = load_config(raw)
        self.assertEqual(len(outcome.diagnostics), 1)


class EarsMajorAfterOtherFieldsTests(unittest.TestCase):
    def test_ears_major_stop_keeps_soft_warnings(self):
        raw = _bytes('schemaVersion: "1.0"\nlanguage: ja\nearsAi: "2.0"\nfutureOption: true\n')
        outcome = load_config(raw)
        self.assertTrue(outcome.stop)
        self.assertEqual(outcome.stop_stage, "ears-major")
        self.assertEqual(outcome.workspace_id, "root")
        codes = [d.code for d in outcome.warnings]
        self.assertIn("SPEC-CONFIG-UNKNOWN-001", codes)


if __name__ == "__main__":
    unittest.main()
