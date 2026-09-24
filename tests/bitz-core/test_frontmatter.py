"""Frontmatter Schema検証（`02_SPECモデル/02_文書・Frontmatter・状態仕様.md`）の単体試験。

型・null・空文字・title文字数・scalar配列とtests要素の重複・未知key・`x-`拡張・
`SPEC-FM-UNAVAILABLE-001`・必須fieldをFrontmatter Schema検証だけ（YAML構文層を介さず）で検査する。
"""

import unittest

from bitz import frontmatter as fm


def _base(**overrides):
    value = {"id": "REQ-001", "title": "件名", "status": "approved"}
    value.update(overrides)
    return value


class RequiredFieldTests(unittest.TestCase):
    def test_missing_title_is_required_error(self):
        value = {"id": "REQ-001", "status": "approved"}
        outcome = fm.validate(value, "REQ")
        self.assertEqual(len(outcome.hard), 1)
        self.assertEqual(outcome.hard[0].code, "SPEC-FM-REQUIRED-001")
        self.assertEqual(outcome.hard[0].key, "title")

    def test_all_required_present_passes(self):
        outcome = fm.validate(_base(), "REQ")
        self.assertEqual(outcome.hard, [])
        self.assertIsNotNone(outcome.value)


class NullAndTypeTests(unittest.TestCase):
    def test_null_title_is_schema_error(self):
        outcome = fm.validate(_base(title=None), "REQ")
        self.assertEqual(outcome.hard[0].code, "SPEC-FM-SCHEMA-001")
        self.assertIn("null", outcome.hard[0].summary)

    def test_title_wrong_type(self):
        outcome = fm.validate(_base(title=42), "REQ")
        self.assertEqual(outcome.hard[0].summary, "Frontmatter titleはstringが必要です")

    def test_changes_wrong_type(self):
        outcome = fm.validate(_base(changes=42), "REQ")
        self.assertEqual(outcome.hard[0].summary, "Frontmatter changesはstringの配列が必要です")


class TitleLengthTests(unittest.TestCase):
    def test_title_exactly_120_is_accepted(self):
        outcome = fm.validate(_base(title="界" * 120), "REQ")
        self.assertEqual(outcome.hard, [])

    def test_title_121_is_rejected(self):
        outcome = fm.validate(_base(title="界" * 121), "REQ")
        self.assertEqual(outcome.hard[0].summary, fm.messages.TITLE_LENGTH_RULE)

    def test_title_empty_is_rejected(self):
        outcome = fm.validate(_base(title=""), "REQ")
        self.assertEqual(outcome.hard[0].summary, fm.messages.TITLE_LENGTH_RULE)

    def test_title_whitespace_only_is_rejected(self):
        outcome = fm.validate(_base(title=" \t "), "REQ")
        self.assertEqual(outcome.hard[0].summary, fm.messages.TITLE_LENGTH_RULE)

    def test_title_with_newline_is_rejected(self):
        outcome = fm.validate(_base(title="前\n後"), "REQ")
        self.assertEqual(outcome.hard[0].summary, fm.messages.TITLE_LENGTH_RULE)


class DuplicateArrayTests(unittest.TestCase):
    def test_relations_scalar_array_duplicate(self):
        outcome = fm.validate(_base(relations={"related": ["REQ-001", "REQ-001"]}), "REQ")
        self.assertEqual(outcome.hard[0].code, "SPEC-FM-SCHEMA-001")
        self.assertEqual(outcome.hard[0].key, "relations.related")

    def test_tests_duplicate_by_key_tuple_ignores_covers_order(self):
        tests = [
            {"path": "t.py", "covers": ["REQ-001:AC-01", "REQ-001:AC-02"], "command": "default"},
            {"path": "t.py", "covers": ["REQ-001:AC-02", "REQ-001:AC-01"], "command": "default"},
        ]
        outcome = fm.validate(_base(tests=tests), "REQ")
        self.assertEqual(outcome.hard[0].summary, fm.messages.TESTS_DUPLICATE)

    def test_tests_same_path_different_command_is_allowed(self):
        tests = [
            {"path": "t.py", "covers": ["REQ-001:AC-01"], "command": "default"},
            {"path": "t.py", "covers": ["REQ-001:AC-01"], "command": "other"},
        ]
        outcome = fm.validate(_base(tests=tests), "REQ")
        self.assertEqual(outcome.hard, [])

    def test_tests_covers_empty_is_rejected(self):
        tests = [{"path": "t.py", "covers": []}]
        outcome = fm.validate(_base(tests=tests), "REQ")
        self.assertEqual(outcome.hard[0].summary, fm.messages.TESTS_COVERS_EMPTY)
        self.assertEqual(outcome.hard[0].key, "tests[0].covers")


class UnknownKeyTests(unittest.TestCase):
    def test_relations_unknown_key(self):
        outcome = fm.validate(_base(relations={"future": []}), "REQ")
        self.assertEqual(outcome.hard[0].key, "relations.future")

    def test_tests_unknown_key(self):
        tests = [{"path": "t.py", "covers": ["REQ-001:AC-01"], "future": True}]
        outcome = fm.validate(_base(tests=tests), "REQ")
        self.assertEqual(outcome.hard[0].key, "tests[0].future")

    def test_top_level_unknown_field_is_soft_warning(self):
        outcome = fm.validate(_base(futureOption=True), "REQ")
        self.assertEqual(outcome.hard, [])
        self.assertEqual(len(outcome.soft), 1)
        self.assertEqual(outcome.soft[0].code, "SPEC-FM-UNKNOWN-001")
        self.assertEqual(outcome.soft[0].key, "futureOption")

    def test_x_prefixed_field_is_silently_kept(self):
        outcome = fm.validate(_base(**{"x-owners": ["team"]}), "REQ")
        self.assertEqual(outcome.hard, [])
        self.assertEqual(outcome.soft, [])
        self.assertIn("x-owners", outcome.value)


class UnavailableFieldTests(unittest.TestCase):
    def test_req_changes_is_unavailable_warning(self):
        outcome = fm.validate(_base(changes=["src/a.py"]), "REQ")
        self.assertEqual(outcome.hard, [])
        self.assertEqual(outcome.soft[0].code, "SPEC-FM-UNAVAILABLE-001")
        self.assertEqual(outcome.soft[0].summary, "REQではchangesを使用できません")

    def test_type_error_precedes_unavailable_warning(self):
        # 型不正のfieldはSCHEMA-001だけを返し、UNAVAILABLE warningを重ねない。
        outcome = fm.validate(_base(changes=42), "REQ")
        self.assertEqual(len(outcome.hard), 1)
        self.assertEqual(outcome.hard[0].code, "SPEC-FM-SCHEMA-001")

    def test_task_changes_is_available(self):
        value = {"id": "TASK-001", "title": "件名", "status": "open", "changes": ["src/a.py"]}
        outcome = fm.validate(value, "TASK")
        self.assertEqual(outcome.hard, [])
        self.assertEqual(outcome.soft, [])

    def test_adr_implements_is_unavailable(self):
        value = {"id": "ADR-001", "title": "件名", "status": "accepted", "implements": ["src/a.py"]}
        outcome = fm.validate(value, "ADR")
        self.assertEqual(outcome.soft[0].summary, "ADRではimplementsを使用できません")


class ArrayCountLimitTests(unittest.TestCase):
    def test_tests_covers_over_limit(self):
        covers = [f"REQ-001:AC-{i:04d}" for i in range(1001)]
        tests = [{"path": "t.py", "covers": covers}]
        outcome = fm.validate(_base(tests=tests), "REQ")
        self.assertEqual(outcome.hard[0].code, "SPEC-INPUT-LIMIT-001")
        self.assertEqual(outcome.hard[0].key, "tests[0].covers")

    def test_tests_covers_at_limit_is_accepted(self):
        covers = [f"REQ-001:AC-{i:04d}" for i in range(1000)]
        tests = [{"path": "t.py", "covers": covers}]
        outcome = fm.validate(_base(tests=tests), "REQ")
        self.assertEqual(outcome.hard, [])


class NonMapRootTests(unittest.TestCase):
    def test_non_dict_root_is_schema_error(self):
        outcome = fm.validate(["not", "a", "map"], "REQ")
        self.assertEqual(outcome.hard[0].code, "SPEC-FM-SCHEMA-001")
        self.assertIsNone(outcome.value)


class DeterministicOrderTests(unittest.TestCase):
    def test_unavailable_warnings_follow_schema_property_order(self):
        # relations/implements/tests/verify/changesのSchema properties順で複数warningを出す。
        value = {
            "id": "ADR-001",
            "title": "件名",
            "status": "accepted",
            "implements": ["src/a.py"],
            "tests": [{"path": "t.py", "covers": ["ADR-001:AC-01"]}],
        }
        outcome = fm.validate(value, "ADR")
        self.assertEqual(outcome.hard, [])
        keys = [w.key for w in outcome.soft]
        self.assertEqual(keys, ["implements", "tests"])

    def test_order_is_stable_across_repeated_calls(self):
        value = {
            "id": "ADR-001",
            "title": "件名",
            "status": "accepted",
            "changes": ["src/a.py"],
            "verify": "default",
            "implements": ["src/a.py"],
        }
        first = [w.key for w in fm.validate(value, "ADR").soft]
        for _ in range(20):
            self.assertEqual([w.key for w in fm.validate(value, "ADR").soft], first)


class RelationIdFormatTests(unittest.TestCase):
    def test_relations_value_must_match_id_string_pattern(self):
        outcome = fm.validate(_base(relations={"requires": ["not-an-id"]}), "REQ")
        self.assertEqual(outcome.hard[0].code, "SPEC-FM-SCHEMA-001")
        self.assertEqual(outcome.hard[0].key, "relations.requires")

    def test_relations_value_bare_document_id_is_accepted(self):
        outcome = fm.validate(_base(relations={"requires": ["ADR-001"]}), "REQ")
        self.assertEqual(outcome.hard, [])

    def test_relations_value_qualified_statement_id_is_accepted(self):
        outcome = fm.validate(_base(relations={"related": ["team::REQ-001:AC-01"]}), "REQ")
        self.assertEqual(outcome.hard, [])

    def test_tests_covers_must_match_id_string_pattern(self):
        tests = [{"path": "t.py", "covers": ["not-an-id"]}]
        outcome = fm.validate(_base(tests=tests), "REQ")
        self.assertEqual(outcome.hard[0].key, "tests[0].covers")


class ExtensionValueDomainTests(unittest.TestCase):
    def test_x_field_with_object_array_is_rejected(self):
        outcome = fm.validate(_base(**{"x-bad": [{"a": 1}]}), "REQ")
        self.assertEqual(outcome.hard[0].code, "SPEC-FM-SCHEMA-001")
        self.assertEqual(outcome.hard[0].key, "x-bad")

    def test_x_field_with_duplicate_scalar_array_is_rejected(self):
        outcome = fm.validate(_base(**{"x-bad": [1, 1]}), "REQ")
        self.assertEqual(outcome.hard[0].key, "x-bad")

    def test_unknown_field_with_invalid_domain_does_not_also_warn(self):
        outcome = fm.validate(_base(futureOption=[{"a": 1}]), "REQ")
        self.assertEqual(outcome.hard[0].code, "SPEC-FM-SCHEMA-001")
        self.assertEqual(outcome.soft, [])

    def test_nested_extension_map_is_accepted(self):
        outcome = fm.validate(_base(**{"x-reviewed": {"team": "quality", "enabled": True}}), "REQ")
        self.assertEqual(outcome.hard, [])
        self.assertEqual(outcome.soft, [])


class RefsFieldTests(unittest.TestCase):
    def test_refs_valid_type_is_not_unknown_warning(self):
        outcome = fm.validate(_base(refs=["REQ-999"]), "REQ")
        self.assertEqual(outcome.hard, [])
        self.assertEqual(outcome.soft, [])
        self.assertIn("refs", outcome.value)

    def test_refs_wrong_type_is_schema_error(self):
        outcome = fm.validate(_base(refs="not-an-array"), "REQ")
        self.assertEqual(outcome.hard[0].code, "SPEC-FM-SCHEMA-001")
        self.assertEqual(outcome.hard[0].key, "refs")


class VerifyCommandNameTests(unittest.TestCase):
    def test_verify_empty_string_message(self):
        outcome = fm.validate(_base(verify=""), "REQ")
        self.assertIn("空文字列", outcome.hard[0].summary)

    def test_verify_pattern_mismatch_message_differs_from_empty(self):
        outcome = fm.validate(_base(verify="Not Valid"), "REQ")
        self.assertNotIn("空文字列", outcome.hard[0].summary)
        self.assertEqual(outcome.hard[0].summary, "Frontmatter verifyはcommand名が必要です")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
