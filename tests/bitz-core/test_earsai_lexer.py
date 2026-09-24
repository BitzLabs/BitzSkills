"""行内字句primitive（lexer.py）の単体試験。parser経由では検査しにくい境界だけを直接叩く。"""

import unittest

from bitz.earsai import ir as ir_mod
from bitz.earsai.lexer import (
    LexError,
    decode_escapes,
    normalize_text,
    read_bracket,
    scan_operation_text,
    scan_text_until_bracket,
)


class ReadBracketTests(unittest.TestCase):
    def test_simple_bracket(self):
        content, end = read_bracket("[MUST] tail", 0)
        self.assertEqual(content, "MUST")
        self.assertEqual(end, 6)

    def test_quoted_value_ignores_unescaped_close_bracket_char(self):
        # DQUOTE内の生の']'はqcharとして許可され、bracketを閉じない。
        content, end = read_bracket('[q:T="a]b"] tail', 0)
        self.assertEqual(content, 'q:T="a]b"')
        self.assertEqual(end, 11)

    def test_escaped_close_bracket_does_not_close(self):
        content, end = read_bracket(r"[a\]b] tail", 0)
        self.assertEqual(content, r"a\]b")
        self.assertEqual(end, 6)

    def test_unclosed_bracket_reports_opening_position(self):
        with self.assertRaises(LexError) as cm:
            read_bracket("[MUST no close", 0)
        self.assertEqual(cm.exception.condition, ir_mod.CONDITION_TAG_UNCLOSED)
        self.assertEqual(cm.exception.offset, 0)

    def test_unclosed_quoted_value_reports_opening_dquote_position(self):
        with self.assertRaises(LexError) as cm:
            read_bracket('[q:T="never closes] tail', 0)
        self.assertEqual(cm.exception.condition, ir_mod.CONDITION_TAG_UNCLOSED)
        self.assertEqual(cm.exception.offset, 5)

    def test_unknown_escape_reports_backslash_position(self):
        with self.assertRaises(LexError) as cm:
            read_bracket(r"[a\qb]", 0)
        self.assertEqual(cm.exception.offset, 2)


class TextScanningTests(unittest.TestCase):
    def test_stops_at_unescaped_bracket(self):
        text, pos = scan_text_until_bracket("foo bar[NEXT]", 0)
        self.assertEqual(text, "foo bar")
        self.assertEqual(pos, 7)

    def test_code_span_content_is_kept_raw_until_normalization(self):
        text, pos = scan_text_until_bracket("a `[x]` b[NEXT]", 0)
        self.assertEqual(text, "a [x] b")
        self.assertEqual(pos, 9)

    def test_escape_decodes_to_single_char(self):
        text, _ = scan_text_until_bracket(r"a \[b\] c[NEXT]", 0)
        self.assertEqual(text, "a [b] c")

    def test_missing_next_bracket_raises_tag_required(self):
        with self.assertRaises(LexError) as cm:
            scan_text_until_bracket("no more tags here", 0)
        self.assertEqual(cm.exception.condition, ir_mod.CONDITION_TAG_REQUIRED)


class OperationTextTests(unittest.TestCase):
    def test_period_must_be_the_final_character(self):
        text, period, bracket_pos = scan_operation_text("結果を返す。", 0)
        self.assertEqual(text, "結果を返す")
        self.assertEqual(period, "。")
        self.assertIsNone(bracket_pos)

    def test_ascii_period_accepted(self):
        text, period, bracket_pos = scan_operation_text("do it.", 0)
        self.assertEqual(text, "do it")
        self.assertEqual(period, ".")
        self.assertIsNone(bracket_pos)

    def test_missing_terminal_period_yields_none(self):
        text, period, bracket_pos = scan_operation_text("no period here", 0)
        self.assertIsNone(text)
        self.assertIsNone(period)
        self.assertIsNone(bracket_pos)

    def test_unescaped_bracket_stops_text_and_reports_its_position(self):
        # operationのtextにも§4.3の「未escape'['で直前textを終了する」が適用される。
        text, period, bracket_pos = scan_operation_text("keep [literal] bracket.", 0)
        self.assertIsNone(text)
        self.assertIsNone(period)
        self.assertEqual(bracket_pos, 5)

    def test_unterminated_code_span_raises_code_unclosed(self):
        with self.assertRaises(LexError) as cm:
            scan_operation_text("``unterminated", 0)
        self.assertEqual(cm.exception.condition, ir_mod.CONDITION_CODE_UNCLOSED)
        self.assertEqual(cm.exception.offset, 0)

    def test_code_span_closing_backtick_as_last_char_has_no_period(self):
        text, period, bracket_pos = scan_operation_text("`code`", 0)
        self.assertIsNone(period)
        self.assertIsNone(bracket_pos)


class NormalizeAndDecodeTests(unittest.TestCase):
    def test_normalize_trims_and_collapses_sp_tab_runs(self):
        self.assertEqual(normalize_text("  a\t\t b   c  "), "a b c")

    def test_decode_escapes_all_five_known_chars(self):
        self.assertEqual(decode_escapes(r"\[\]\\\`\""), "[]\\`\"")


if __name__ == "__main__":
    unittest.main()
