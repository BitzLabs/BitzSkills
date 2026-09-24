"""text出力向け制御文字無害化の単体試験。"""

import unittest

from bitz.textutil import sanitize_control_chars


class SanitizeControlCharsTests(unittest.TestCase):
    def test_lf_is_escaped(self):
        self.assertEqual(sanitize_control_chars("a\nb"), "a\\u000ab")

    def test_tab_is_escaped(self):
        self.assertEqual(sanitize_control_chars("a\tb"), "a\\u0009b")

    def test_esc_is_escaped(self):
        self.assertEqual(sanitize_control_chars("\x1b[31m"), "\\u001b[31m")

    def test_del_is_escaped(self):
        self.assertEqual(sanitize_control_chars("a\x7fb"), "a\\u007fb")

    def test_c1_is_escaped(self):
        self.assertEqual(sanitize_control_chars("a\x80b"), "a\\u0080b")

    def test_normal_text_untouched(self):
        self.assertEqual(sanitize_control_chars("こんにちは"), "こんにちは")


if __name__ == "__main__":
    unittest.main()
