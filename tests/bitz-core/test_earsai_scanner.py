"""候補Scanner（EARS-AI仕様 §5）の単体試験。

候補抽出とtag妥当性検証を分離しているため、ここでは"候補になるかどうか"だけを検査する
（statement IDや発動条件の妥当性はparserの試験で扱う）。
"""

import unittest

from bitz.earsai.scanner import scan_candidates


class BasicCandidateTests(unittest.TestCase):
    def test_simple_statement_is_a_candidate(self):
        text = "- [REQ-001:AC-01] [ACTOR:X] [ALWAYS] [MUST] [THEN] 応答する。\n"
        candidates = scan_candidates(text)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].line, 1)
        self.assertEqual(candidates[0].column, 3)
        self.assertEqual(candidates[0].raw, text.rstrip("\n"))

    def test_line_number_counts_from_file_start(self):
        text = "line1\nline2\n- [REQ-001:AC-01] [ACTOR:X] [ALWAYS] [MUST] [THEN] a。\n"
        candidates = scan_candidates(text)
        self.assertEqual(candidates[0].line, 3)

    def test_crlf_is_normalized(self):
        text = "- [REQ-001:AC-01] [ACTOR:X] [ALWAYS] [MUST] [THEN] a。\r\nnext\r\n"
        candidates = scan_candidates(text)
        self.assertEqual(len(candidates), 1)
        self.assertNotIn("\r", candidates[0].raw)


class IsCandidateTokenRuleTests(unittest.TestCase):
    def test_rule1_known_prefix(self):
        self.assertEqual(len(scan_candidates("- [REQ-001:AC-01] tail\n")), 1)
        self.assertEqual(len(scan_candidates("- [TASK-9:AC-01] tail\n")), 1)

    def test_rule2_uppercase_with_hyphen_or_colon(self):
        # 未知接頭辞・桁不足でも"大文字始まりで-または:を含む"なら候補になる。
        self.assertEqual(len(scan_candidates("- [XYZ-1:AC-01] tail\n")), 1)
        self.assertEqual(len(scan_candidates("- [ACME:thing] tail\n")), 1)

    def test_rule3_core_tag_keyword(self):
        self.assertEqual(len(scan_candidates("- [ACTOR:Something] tail\n")), 1)
        self.assertEqual(len(scan_candidates("- [MUST] tail\n")), 1)

    def test_rule4_lowercase_namespace_prefix(self):
        self.assertEqual(len(scan_candidates("- [quality:LEVEL] tail\n")), 1)

    def test_non_matching_token_is_not_a_candidate(self):
        self.assertEqual(scan_candidates("- [lowercase without colon] tail\n"), [])
        self.assertEqual(scan_candidates("- [123] tail\n"), [])


class ChecklistNotCandidateTests(unittest.TestCase):
    def test_unchecked_checkbox_is_not_candidate(self):
        self.assertEqual(scan_candidates("- [ ] TODO item\n"), [])

    def test_checked_checkbox_lower_and_upper_are_not_candidates(self):
        self.assertEqual(scan_candidates("- [x] done\n"), [])
        self.assertEqual(scan_candidates("- [X] done\n"), [])


class FenceStateMachineTests(unittest.TestCase):
    def test_backtick_fence_hides_statement_like_lines(self):
        text = "```\n- [REQ-001:AC-01] [ACTOR:X] [ALWAYS] [MUST] [THEN] a。\n```\n"
        self.assertEqual(scan_candidates(text), [])

    def test_tilde_fence_hides_statement_like_lines(self):
        text = "~~~\n- [REQ-001:AC-01] [ACTOR:X] [ALWAYS] [MUST] [THEN] a。\n~~~\n"
        self.assertEqual(scan_candidates(text), [])

    def test_fence_with_info_string_still_opens(self):
        text = "```python\n- [REQ-001:AC-01] tail\n```\n"
        self.assertEqual(scan_candidates(text), [])

    def test_closing_fence_requires_run_at_least_as_long(self):
        # 開始より短いrunは閉じない。
        text = "````\n- [REQ-001:AC-01] tail\n```\nstill inside\n````\n"
        # 短い```では閉じないため、"still inside"より後のfence外候補は生まれない。
        self.assertEqual(scan_candidates(text), [])

    def test_closing_fence_with_trailing_info_string_does_not_close(self):
        text = "```\nnot a candidate line\n``` extra\n- [REQ-001:AC-01] [ACTOR:X] [ALWAYS] [MUST] [THEN] a。\n"
        # closing fenceにinfo文字列は許可しないため、閉じずにfence内が続く。
        self.assertEqual(scan_candidates(text), [])

    def test_after_fence_closes_candidates_resume(self):
        text = "```\ncode\n```\n- [REQ-001:AC-01] [ACTOR:X] [ALWAYS] [MUST] [THEN] a。\n"
        self.assertEqual(len(scan_candidates(text)), 1)

    def test_fence_indent_up_to_three_still_opens(self):
        text = "   ```\n- [REQ-001:AC-01] tail\n   ```\n"
        self.assertEqual(scan_candidates(text), [])

    def test_fence_indent_four_does_not_open(self):
        # indent>=4は独立にindented code blockとして扱われ、fenceにはならない。
        text = "    ```\n- [REQ-001:AC-01] [ACTOR:X] [ALWAYS] [MUST] [THEN] a。\n    ```\n"
        self.assertEqual(len(scan_candidates(text)), 1)


class BlockquoteAndIndentTests(unittest.TestCase):
    def test_blockquote_line_is_not_candidate(self):
        text = "> - [REQ-001:AC-01] [ACTOR:X] [ALWAYS] [MUST] [THEN] a。\n"
        self.assertEqual(scan_candidates(text), [])

    def test_blockquote_with_up_to_three_leading_sp(self):
        text = "   > - [REQ-001:AC-01] tail\n"
        self.assertEqual(scan_candidates(text), [])

    def test_four_sp_indent_is_not_candidate(self):
        text = "    - [REQ-001:AC-01] [ACTOR:X] [ALWAYS] [MUST] [THEN] a。\n"
        self.assertEqual(scan_candidates(text), [])

    def test_three_sp_indent_is_candidate(self):
        text = "   - [REQ-001:AC-01] [ACTOR:X] [ALWAYS] [MUST] [THEN] a。\n"
        candidates = scan_candidates(text)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].column, 6)

    def test_tab_is_not_treated_as_indent_or_space(self):
        text = "\t- [REQ-001:AC-01] tail\n"
        self.assertEqual(scan_candidates(text), [])


class CodeSpanBracketTests(unittest.TestCase):
    def test_bracket_inside_inline_code_span_on_a_normal_line_is_not_a_list_start(self):
        text = "prose `[REQ-001:AC-01]` more\n"
        self.assertEqual(scan_candidates(text), [])


if __name__ == "__main__":
    unittest.main()
