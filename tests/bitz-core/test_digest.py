"""Context Digest正規化（`digest.py`）の単体試験（`00_共通契約/03_Context-Digest正規化仕様.md`）。"""

import unittest

from bitz import digest as digest_mod


class CanonicalJsonTests(unittest.TestCase):
    def test_keys_are_sorted_and_compact(self):
        data = {"b": 1, "a": [3, 2, 1], "c": {"y": 1, "x": 2}}
        out = digest_mod.canonical_bytes(data).decode("utf-8")
        self.assertEqual(out, '{"a":[3,2,1],"b":1,"c":{"x":2,"y":1}}')

    def test_no_whitespace_no_bom(self):
        out = digest_mod.canonical_bytes({"a": "v"})
        self.assertNotIn(b" ", out)
        self.assertFalse(out.startswith(b"\xef\xbb\xbf"))

    def test_nfc_normalization_applied_to_strings(self):
        # "が" として濁点結合文字（NFD）を分解形で与えても、Canonical化後は合成済み(NFC)になる。
        decomposed = "が"
        out = digest_mod.canonical_bytes({"v": decomposed}).decode("utf-8")
        self.assertIn("が", out)
        self.assertNotIn("゙", out)

    def test_same_materials_produce_same_digest(self):
        materials = {"a": 1, "b": [1, 2, 3]}
        d1 = digest_mod.compute_digest(materials)
        d2 = digest_mod.compute_digest(dict(materials))
        self.assertEqual(d1, d2)
        self.assertRegex(d1, r"^sha256:[0-9a-f]{64}$")

    def test_different_materials_produce_different_digest(self):
        d1 = digest_mod.compute_digest({"a": 1})
        d2 = digest_mod.compute_digest({"a": 2})
        self.assertNotEqual(d1, d2)

    def test_object_keys_sort_by_utf16_code_unit_not_code_point(self):
        # U+E000 (BMP、code unit 0xE000) と U+10000 (附属面、surrogate pair 0xD800,0xDC00)。
        # code point順では U+E000 < U+10000 だが、UTF-16 code unit順では最初のcode unitが
        # 0xD800 < 0xE000 のため逆転する（RFC 8785 §5「UTF-16 code unitの昇順」）。
        key_bmp = ""
        key_supplementary = "\U00010000"
        self.assertLess(key_bmp, key_supplementary)  # Pythonのcode point比較では bmp が先。

        data = {key_supplementary: "sup", key_bmp: "bmp"}
        out = digest_mod.canonical_bytes(data).decode("utf-8")
        pos_supplementary = out.index(json_dumps_key(key_supplementary))
        pos_bmp = out.index(json_dumps_key(key_bmp))
        self.assertLess(pos_supplementary, pos_bmp)  # UTF-16 code unit順では附属面文字が先。


def json_dumps_key(k: str) -> str:
    import json

    return json.dumps(k, ensure_ascii=False)


class PathSeparatorTests(unittest.TestCase):
    def test_to_slash_converts_backslash(self):
        self.assertEqual(digest_mod.to_slash("src\\auth.py"), "src/auth.py")

    def test_to_slash_leaves_forward_slash(self):
        self.assertEqual(digest_mod.to_slash("src/auth.py"), "src/auth.py")


class NormalizeBodyTextTests(unittest.TestCase):
    def test_strips_bom(self):
        self.assertEqual(digest_mod.normalize_body_text("﻿# H\n"), "# H\n")

    def test_crlf_and_cr_become_lf(self):
        self.assertEqual(digest_mod.normalize_body_text("a\r\nb\rc\n"), "a\nb\nc\n")

    def test_trailing_whitespace_per_line_is_stripped(self):
        self.assertEqual(digest_mod.normalize_body_text("a \t\nb\n"), "a\nb\n")

    def test_leading_and_trailing_blank_lines_are_removed(self):
        self.assertEqual(digest_mod.normalize_body_text("\n\n# H\n\nbody\n\n\n"), "# H\n\nbody\n")

    def test_interior_blank_lines_are_kept(self):
        self.assertEqual(digest_mod.normalize_body_text("a\n\n\nb\n"), "a\n\n\nb\n")

    def test_empty_body_becomes_empty_string(self):
        self.assertEqual(digest_mod.normalize_body_text("\n\n  \n"), "")

    def test_always_ends_with_single_trailing_lf(self):
        self.assertEqual(digest_mod.normalize_body_text("a"), "a\n")
        self.assertTrue(digest_mod.normalize_body_text("a\n\n\n").endswith("\n"))
        self.assertFalse(digest_mod.normalize_body_text("a\n\n\n").endswith("\n\n"))


if __name__ == "__main__":
    unittest.main()
