"""EARS-AI Parser（EARS-AI仕様 §3・§4・§6・§7）の単体試験。

正例のSemantic IR、各EAI条件の反例、同一raw原因のprimary 1件規則、code spanのrun長、
escape、quoted value、全角句点、TAB／全角文字のcolumn、決定性を検査する。
draft差分によるseverity決定はPhase Bの責務のため、ここでは`ir.CONDITION_*` kindを検査する。
"""

import unittest

from bitz.earsai import ir as ir_mod
from bitz.earsai.parser import parse_document


def _one(text: str, path: str = "x.md"):
    result = parse_document(text, path)
    return result


class HappyPathTests(unittest.TestCase):
    def test_minimal_always_must_then(self):
        result = _one("- [REQ-001:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [THEN] 応答する。\n")
        self.assertEqual(len(result.statements), 1)
        self.assertEqual(result.conditions, [])
        stmt = result.statements[0]
        self.assertEqual(stmt["id"], "REQ-001:AC-01")
        self.assertEqual(stmt["documentId"], "REQ-001")
        self.assertEqual(stmt["localId"], "AC-01")
        self.assertEqual(stmt["activation"], {"kind": "ALWAYS"})
        self.assertEqual(stmt["modality"], "MUST")
        self.assertIsNone(stmt["reason"])
        self.assertEqual(stmt["operation"], {"kind": "THEN", "text": "応答する"})
        self.assertEqual(stmt["extensions"], [])
        self.assertEqual(stmt["unknownExtensions"], [])
        self.assertTrue(stmt["untrustedText"])
        self.assertEqual(stmt["schemaVersion"], "1.0")

    def test_should_with_reason(self):
        text = "- [REQ-001:AC-02] [ACTOR:X] [WHEN] 保存した場合 [SHOULD] [REASON] 確認のため [THEN] 結果を返す。\n"
        result = _one(text)
        stmt = result.statements[0]
        self.assertEqual(stmt["reason"], "確認のため")
        self.assertEqual(result.conditions, [])

    def test_field_order_matches_spec_section_6(self):
        text = "- [REQ-001:AC-01] [ACTOR:X] [ALWAYS] [MUST] [THEN] a。\n"
        stmt = _one(text).statements[0]
        expected_order = [
            "schemaVersion", "id", "documentId", "localId", "source", "actor",
            "activation", "modality", "reason", "operation", "extensions",
            "unknownExtensions", "untrustedText", "raw",
        ]
        self.assertEqual(list(stmt.keys()), expected_order)

    def test_source_points_to_id_opening_bracket(self):
        text = "prelude\n- [REQ-001:AC-01] [ACTOR:X] [ALWAYS] [MUST] [THEN] a。\n"
        stmt = _one(text).statements[0]
        self.assertEqual(stmt["source"], {"path": "x.md", "line": 2, "column": 3})

    def test_raw_preserves_original_line_without_newline(self):
        raw_line = "- [REQ-001:AC-01] [ACTOR:X] [ALWAYS] [MUST] [THEN] a。"
        stmt = _one(raw_line + "\n").statements[0]
        self.assertEqual(stmt["raw"], raw_line)


class ExtensionTests(unittest.TestCase):
    def test_bare_extension_value(self):
        text = "- [REQ-001:AC-01] [quality:LEVEL=high] [ACTOR:X] [ALWAYS] [MUST] [THEN] a。\n"
        result = _one(text)
        stmt = result.statements[0]
        self.assertEqual(stmt["extensions"], [{"namespace": "quality", "term": "LEVEL", "value": "high"}])
        self.assertEqual(stmt["unknownExtensions"], stmt["extensions"])
        self.assertEqual(result.conditions, [{"kind": ir_mod.CONDITION_EXTENSION_UNKNOWN, "line": 1, "column": 19}])

    def test_extension_without_value(self):
        text = "- [REQ-001:AC-01] [quality:LEVEL] [ACTOR:X] [ALWAYS] [MUST] [THEN] a。\n"
        stmt = _one(text).statements[0]
        self.assertEqual(stmt["extensions"], [{"namespace": "quality", "term": "LEVEL", "value": None}])

    def test_quoted_value_with_escaped_dquote(self):
        text = '- [REQ-001:AC-01] [quality:LEVEL="say \\"hello\\""] [ACTOR:X] [ALWAYS] [MUST] [THEN] a。\n'
        stmt = _one(text).statements[0]
        self.assertEqual(stmt["extensions"][0]["value"], 'say "hello"')

    def test_multiple_extensions_each_produce_a_condition_in_order(self):
        text = "- [REQ-001:AC-01] [a:B] [c:D] [ACTOR:X] [ALWAYS] [MUST] [THEN] a。\n"
        result = _one(text)
        kinds = [c["kind"] for c in result.conditions]
        self.assertEqual(kinds, [ir_mod.CONDITION_EXTENSION_UNKNOWN, ir_mod.CONDITION_EXTENSION_UNKNOWN])
        self.assertEqual(len(result.statements[0]["extensions"]), 2)


class CodeSpanTests(unittest.TestCase):
    def test_run_length_must_match_to_close(self):
        text = "- [REQ-001:AC-01] [ACTOR:X] [ALWAYS] [MUST] [THEN] 値 ``two`x`` を保持する。\n"
        stmt = _one(text).statements[0]
        self.assertEqual(stmt["operation"]["text"], "値 two`x を保持する")

    def test_different_length_runs_are_kept_literal_inside_span(self):
        text = "- [REQ-001:AC-01] [ACTOR:X] [ALWAYS] [MUST] [CONSTRAINT] ```three``end``` を保持する。\n"
        stmt = _one(text).statements[0]
        self.assertEqual(stmt["operation"]["text"], "three``end を保持する")

    def test_unclosed_code_span_reports_opening_backtick_position(self):
        text = "- [REQ-001:AC-01] [ACTOR:X] [ALWAYS] [MUST] [THEN] ``unterminated。\n"
        result = _one(text)
        self.assertEqual(result.statements, [])
        expected_column = text.index("``") + 1
        self.assertEqual(
            result.conditions, [{"kind": ir_mod.CONDITION_CODE_UNCLOSED, "line": 1, "column": expected_column}]
        )


class EscapeTests(unittest.TestCase):
    def test_all_five_known_escapes_decode_to_one_char_each(self):
        text = '- [REQ-001:AC-01] [ACTOR:X] [ALWAYS] [MUST] [CONSTRAINT] 記号 \\[ \\] \\\\ \\` \\" を保持する。\n'
        stmt = _one(text).statements[0]
        self.assertEqual(stmt["operation"]["text"], '記号 [ ] \\ ` " を保持する')

    def test_unknown_escape_reports_backslash_position(self):
        text = "- [REQ-001:AC-01] [ACTOR:X] [ALWAYS] [MUST] [THEN] a\\qb。\n"
        result = _one(text)
        self.assertEqual(result.statements, [])
        condition = result.conditions[0]
        self.assertEqual(condition["kind"], ir_mod.CONDITION_TAG_UNCLOSED)
        self.assertEqual(text[condition["column"] - 1], "\\")


class SpTabNormalizationTests(unittest.TestCase):
    def test_internal_runs_collapse_to_single_sp(self):
        text = "- [REQ-001:AC-01] [ACTOR:X] [WHEN]  複数  空白  [MUST] [THEN] a。\n"
        stmt = _one(text).statements[0]
        self.assertEqual(stmt["activation"]["text"], "複数 空白")


class SyntaxErrorConditionTests(unittest.TestCase):
    def test_unclosed_tag_no_ir(self):
        result = _one("- [REQ-001:AC-01] [ACTOR:X] [ALWAYS] [MUST] [THEN a。\n")
        self.assertEqual(result.statements, [])
        self.assertEqual(result.conditions, [{"kind": ir_mod.CONDITION_TAG_UNCLOSED, "line": 1, "column": 45}])

    def test_id_format_unknown_prefix(self):
        result = _one("- [XYZ-001:AC-01] [ACTOR:X] [ALWAYS] [MUST] [THEN] a。\n")
        self.assertEqual(result.statements, [])
        self.assertEqual(result.conditions, [{"kind": ir_mod.CONDITION_ID_FORMAT, "line": 1, "column": 3}])

    def test_id_format_missing_digits(self):
        result = _one("- [REQ-1:AC-01] [ACTOR:X] [ALWAYS] [MUST] [THEN] a。\n")
        self.assertEqual(result.conditions[0]["kind"], ir_mod.CONDITION_ID_FORMAT)

    def test_id_format_three_tier(self):
        result = _one("- [REQ-001:AC-01:extra] [ACTOR:X] [ALWAYS] [MUST] [THEN] a。\n")
        self.assertEqual(result.conditions[0]["kind"], ir_mod.CONDITION_ID_FORMAT)

    def test_tag_order_reason_after_must(self):
        result = _one("- [REQ-001:AC-01] [ACTOR:X] [ALWAYS] [MUST] [REASON] x [THEN] a。\n")
        self.assertEqual(result.statements, [])
        self.assertEqual(result.conditions[0]["kind"], ir_mod.CONDITION_TAG_ORDER)

    def test_tag_order_reason_after_may(self):
        result = _one("- [REQ-001:AC-01] [ACTOR:X] [ALWAYS] [MAY] [REASON] x [THEN] a。\n")
        self.assertEqual(result.conditions[0]["kind"], ir_mod.CONDITION_TAG_ORDER)

    def test_trigger_multiple(self):
        result = _one("- [REQ-001:AC-01] [ACTOR:X] [WHEN] a [WHILE] b [MUST] [THEN] a。\n")
        self.assertEqual(result.statements, [])
        self.assertEqual(result.conditions[0]["kind"], ir_mod.CONDITION_TRIGGER_MULTIPLE)

    def test_period_missing(self):
        result = _one("- [REQ-001:AC-01] [ACTOR:X] [ALWAYS] [MUST] [THEN] a\n")
        self.assertEqual(result.statements, [])
        self.assertEqual(result.conditions[0]["kind"], ir_mod.CONDITION_PERIOD_MISSING)

    def test_operand_missing_empty_operation_text(self):
        result = _one("- [REQ-001:AC-01] [ACTOR:X] [ALWAYS] [MUST] [THEN] 。\n")
        self.assertEqual(result.statements, [])
        self.assertEqual(result.conditions[0]["kind"], ir_mod.CONDITION_OPERAND_MISSING)

    def test_should_reason_missing_still_returns_ir(self):
        result = _one("- [REQ-001:AC-01] [ACTOR:X] [ALWAYS] [SHOULD] [THEN] a。\n")
        self.assertEqual(len(result.statements), 1)
        self.assertIsNone(result.statements[0]["reason"])
        self.assertEqual(result.conditions, [{"kind": ir_mod.CONDITION_SHOULD_REASON_MISSING, "line": 1, "column": 38}])

    def test_id_duplicate_reports_second_occurrence(self):
        text = (
            "- [REQ-001:AC-01] [ACTOR:X] [ALWAYS] [MUST] [THEN] a。\n"
            "- [REQ-001:AC-01] [ACTOR:X] [ALWAYS] [MUST] [THEN] b。\n"
        )
        result = _one(text)
        self.assertEqual(len(result.statements), 2)
        self.assertEqual(result.conditions, [{"kind": ir_mod.CONDITION_ID_DUPLICATE, "line": 2, "column": 3}])


class PrimarySelectionTests(unittest.TestCase):
    """同一raw原因から複数の構文候補が生じる場合、primaryを1件だけ返す（§4末尾）。"""

    def test_unclosed_code_span_wins_over_unclosed_tag(self):
        # 未閉鎖code spanが行末までの残りをすべて飲み込むため、後続の[が閉じないtagにもなり得るが、
        # primaryはcode-unclosedだけを返す。
        text = "- [REQ-001:AC-01] [ACTOR:X] [ALWAYS] [MUST] [THEN] ``a [MUST\n"
        result = _one(text)
        self.assertEqual(len(result.conditions), 1)
        self.assertEqual(result.conditions[0]["kind"], ir_mod.CONDITION_CODE_UNCLOSED)

    def test_unclosed_tag_wins_over_id_format(self):
        # IDのbracketそのものが閉じないため、内容がstatement-id形式かどうかは判定しない。
        text = "- [REQ-001 no closing bracket for id\n"
        result = _one(text)
        self.assertEqual(len(result.conditions), 1)
        self.assertEqual(result.conditions[0]["kind"], ir_mod.CONDITION_TAG_UNCLOSED)


class MultibyteAndTabColumnTests(unittest.TestCase):
    def test_column_counts_full_width_and_tab_as_one_each(self):
        # 全角文字とTABを含むtext部分があっても、後続tagのcolumnはUnicode code point単位で数える。
        text = "- [REQ-001:AC-01] [ACTOR:X] [WHEN] 全角\tTAB [MUST] [THEN a。\n"
        result = _one(text)
        self.assertEqual(result.statements, [])
        condition = result.conditions[0]
        self.assertEqual(condition["kind"], ir_mod.CONDITION_TAG_UNCLOSED)
        self.assertEqual(text[condition["column"] - 1], "[")

    def test_full_width_period_is_accepted_as_terminal(self):
        text = "- [REQ-001:AC-01] [ACTOR:X] [ALWAYS] [MUST] [THEN] 応答する。\n"
        stmt = _one(text).statements[0]
        self.assertEqual(stmt["operation"]["text"], "応答する")


class DeterminismTests(unittest.TestCase):
    def test_same_input_yields_identical_result_across_runs(self):
        text = "- [REQ-001:AC-01] [ACTOR:X] [ALWAYS] [MUST] [THEN] a。\n"
        first = _one(text)
        second = _one(text)
        self.assertEqual(first.statements, second.statements)
        self.assertEqual(first.conditions, second.conditions)


class OperationTrailingBracketTests(unittest.TestCase):
    """作業依頼2026-09 #1: operation textの未escape`[`は§4.3どおりtextを終端する。"""

    def test_unclosed_trailing_bracket_is_tag_unclosed(self):
        text = "- [REQ-001:AC-01] [ACTOR:X] [ALWAYS] [MUST] [CONSTRAINT] keep [literal open。\n"
        result = _one(text)
        self.assertEqual(result.statements, [])
        condition = result.conditions[0]
        self.assertEqual(condition["kind"], ir_mod.CONDITION_TAG_UNCLOSED)
        self.assertEqual(text[condition["column"] - 1], "[")

    def test_closed_trailing_core_tag_is_tag_order(self):
        text = "- [REQ-001:AC-01] [ACTOR:X] [ALWAYS] [MUST] [CONSTRAINT] keep [MUST] open。\n"
        result = _one(text)
        self.assertEqual(result.statements, [])
        self.assertEqual(result.conditions, [{"kind": ir_mod.CONDITION_TAG_ORDER, "line": 1, "column": 63}])

    def test_closed_trailing_unknown_bracket_is_tag_unclosed(self):
        text = "- [REQ-001:AC-01] [ACTOR:X] [ALWAYS] [MUST] [CONSTRAINT] keep [zzz] open。\n"
        result = _one(text)
        self.assertEqual(result.statements, [])
        self.assertEqual(result.conditions, [{"kind": ir_mod.CONDITION_TAG_UNCLOSED, "line": 1, "column": 63}])

    def test_full_width_and_tab_before_unknown_bracket_reported_in_single_120(self):
        # SINGLE-102相当: 全角文字とTABの後に未知tagを置いても、[の位置をcode point単位で報告する。
        text = (
            "- [REQ-001:AC-01] [ACTOR:X] [ALWAYS] [MUST] [CONSTRAINT] "
            "全角文字と\tタブの後に[未知tagを置かない。\n"
        )
        result = _one(text)
        self.assertEqual(result.statements, [])
        condition = result.conditions[0]
        self.assertEqual(condition["kind"], ir_mod.CONDITION_TAG_UNCLOSED)
        self.assertEqual(text[condition["column"] - 1], "[")


class BracketInteriorBracketTests(unittest.TestCase):
    """作業依頼2026-09 #2: `read_bracket`はquote外・未escapeの`[`を開始`[`の位置で破綻させる。"""

    def test_unescaped_bracket_inside_id_bracket_reports_opening_position(self):
        # SINGLE-103-02相当: IDのbracketが閉じる前に別の[が現れる。
        text = "- [REQ-01:AC-02 [ACTOR:TargetSystem] [ALWAYS] [MUST] [THEN] a。\n"
        result = _one(text)
        self.assertEqual(result.statements, [])
        self.assertEqual(result.conditions, [{"kind": ir_mod.CONDITION_TAG_UNCLOSED, "line": 1, "column": 3}])
        self.assertEqual(text[2], "[")

    def test_escaped_bracket_inside_extension_value_does_not_break(self):
        text = r'- [REQ-001:AC-01] [q:T="a\[b"] [ACTOR:X] [ALWAYS] [MUST] [THEN] a。' + "\n"
        result = _one(text)
        self.assertEqual(len(result.statements), 1)
        self.assertEqual(result.statements[0]["extensions"][0]["value"], "a[b")


class ExtensionValueGrammarTests(unittest.TestCase):
    """作業依頼2026-09 #3: extension値はbare-valueまたはquoted-valueだけを妥当とする。"""

    def test_bare_value_with_dot_hyphen_underscore_is_valid(self):
        text = "- [REQ-001:AC-01] [q:T=a-b_c.d] [ACTOR:X] [ALWAYS] [MUST] [THEN] a。\n"
        result = _one(text)
        self.assertEqual(result.statements[0]["extensions"][0]["value"], "a-b_c.d")

    def test_unquoted_dquote_in_bare_value_is_tag_unclosed(self):
        text = '- [REQ-001:AC-01] [q:T=x"y] [ACTOR:X] [ALWAYS] [MUST] [THEN] a。\n'
        result = _one(text)
        self.assertEqual(result.statements, [])
        self.assertEqual(result.conditions[0]["kind"], ir_mod.CONDITION_TAG_UNCLOSED)

    def test_empty_value_after_equals_is_tag_unclosed(self):
        text = "- [REQ-001:AC-01] [q:T=] [ACTOR:X] [ALWAYS] [MUST] [THEN] a。\n"
        result = _one(text)
        self.assertEqual(result.statements, [])
        self.assertEqual(
            result.conditions, [{"kind": ir_mod.CONDITION_TAG_UNCLOSED, "line": 1, "column": 19}]
        )

    def test_value_with_two_quoted_segments_is_tag_unclosed(self):
        # "a"b"c" のような複数quoted segmentは単一のquoted-valueとして妥当ではない。
        text = '- [REQ-001:AC-01] [q:T="a"b"c"] [ACTOR:X] [ALWAYS] [MUST] [THEN] a。\n'
        result = _one(text)
        self.assertEqual(result.statements, [])
        self.assertEqual(result.conditions[0]["kind"], ir_mod.CONDITION_TAG_UNCLOSED)

    def test_actor_with_empty_identifier_is_operand_missing(self):
        text = "- [REQ-001:AC-01] [ACTOR:] [ALWAYS] [MUST] [THEN] a。\n"
        result = _one(text)
        self.assertEqual(result.statements, [])
        self.assertEqual(result.conditions[0]["kind"], ir_mod.CONDITION_OPERAND_MISSING)

    def test_actor_with_invalid_identifier_is_tag_unclosed(self):
        text = "- [REQ-001:AC-01] [ACTOR:123] [ALWAYS] [MUST] [THEN] a。\n"
        result = _one(text)
        self.assertEqual(result.statements, [])
        self.assertEqual(result.conditions[0]["kind"], ir_mod.CONDITION_TAG_UNCLOSED)


class WrongSlotClassificationTests(unittest.TestCase):
    """作業依頼2026-09 #4: 期待slotと違う既知tagは、後方に期待tagが実在すればtag順序不正、
    実在しなければ必須tag不足へ分類する（ヒューリスティックではなく実在探索）。"""

    def test_all_tags_present_but_out_of_order_is_tag_order(self):
        # modalityとactivationが入れ替わっている。ACTORの次に来るのはactivation slotのはずが
        # [MUST]が現れ、後方に本来のactivation tag[ALWAYS]が実在するためtag順序不正。
        text = "- [REQ-001:AC-01] [ACTOR:X] [MUST] [ALWAYS] [THEN] a。\n"
        result = _one(text)
        self.assertEqual(result.statements, [])
        self.assertEqual(result.conditions, [{"kind": ir_mod.CONDITION_TAG_ORDER, "line": 1, "column": 29}])

    def test_actor_missing_entirely_is_tag_required(self):
        # ACTORがどこにも存在しない場合は必須tag不足。
        text = "- [REQ-001:AC-01] [ALWAYS] [MUST] [THEN] a。\n"
        result = _one(text)
        self.assertEqual(result.statements, [])
        self.assertEqual(result.conditions, [{"kind": ir_mod.CONDITION_TAG_REQUIRED, "line": 1, "column": 19}])

    def test_actor_present_later_out_of_order_is_tag_order(self):
        # ACTORが本来の位置になく、activationの後に現れる（後方に実在する）。
        text = "- [REQ-001:AC-01] [ALWAYS] [ACTOR:X] [MUST] [THEN] a。\n"
        result = _one(text)
        self.assertEqual(result.statements, [])
        self.assertEqual(result.conditions, [{"kind": ir_mod.CONDITION_TAG_ORDER, "line": 1, "column": 19}])

    def test_completely_unrecognized_bracket_is_tag_unclosed(self):
        text = "- [REQ-001:AC-01] [ACTOR:X] [zzz] [MUST] [THEN] a。\n"
        result = _one(text)
        self.assertEqual(result.statements, [])
        self.assertEqual(result.conditions[0]["kind"], ir_mod.CONDITION_TAG_UNCLOSED)


if __name__ == "__main__":
    unittest.main()
