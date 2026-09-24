"""YAML部分集合の禁止構文拒否とscalar解決の単体試験。"""

import unittest

from bitz.yamlsafe import YamlForbiddenError, YamlSyntaxError, parse_yaml_subset


class ScalarResolutionTests(unittest.TestCase):
    def test_plain_null_variants(self):
        self.assertIsNone(parse_yaml_subset("a: null\n")["a"])
        self.assertIsNone(parse_yaml_subset("a: ~\n")["a"])
        self.assertIsNone(parse_yaml_subset("a:\n")["a"])

    def test_plain_booleans_are_lowercase_only(self):
        value = parse_yaml_subset("a: true\nb: false\nc: yes\nd: no\n")
        self.assertIs(value["a"], True)
        self.assertIs(value["b"], False)
        self.assertEqual(value["c"], "yes")
        self.assertEqual(value["d"], "no")

    def test_decimal_integer_leading_zero_is_not_octal(self):
        value = parse_yaml_subset("a: 007\nb: -12\n")
        self.assertEqual(value["a"], 7)
        self.assertEqual(value["b"], -12)

    def test_finite_decimal_number(self):
        value = parse_yaml_subset("a: 1.5\nb: -0.25\n")
        self.assertEqual(value["a"], 1.5)
        self.assertEqual(value["b"], -0.25)

    def test_quoted_scalar_stays_string_even_if_number_like(self):
        value = parse_yaml_subset('a: "1.0"\nb: "true"\n')
        self.assertEqual(value["a"], "1.0")
        self.assertEqual(value["b"], "true")

    def test_timestamp_like_value_stays_string(self):
        value = parse_yaml_subset("a: 2020-01-01\n")
        self.assertEqual(value["a"], "2020-01-01")

    def test_nested_sequence_and_map(self):
        value = parse_yaml_subset("a:\n  - 1\n  - two\nb:\n  c: 3\n")
        self.assertEqual(value["a"], [1, "two"])
        self.assertEqual(value["b"], {"c": 3})


class ForbiddenSyntaxTests(unittest.TestCase):
    def test_anchor_rejected(self):
        with self.assertRaises(YamlForbiddenError):
            parse_yaml_subset("a: &x 1\n")

    def test_alias_rejected(self):
        with self.assertRaises(YamlForbiddenError):
            parse_yaml_subset("a: &x 1\nb: *x\n")

    def test_explicit_tag_rejected(self):
        with self.assertRaises(YamlForbiddenError):
            parse_yaml_subset("a: !!str 1\n")

    def test_merge_key_rejected(self):
        with self.assertRaises(YamlForbiddenError):
            parse_yaml_subset("base: &b\n  x: 1\na:\n  <<: *b\n  y: 2\n")

    def test_complex_key_rejected(self):
        with self.assertRaises(YamlForbiddenError):
            parse_yaml_subset("? [1, 2]\n: v\n")

    def test_multiple_documents_rejected(self):
        with self.assertRaises(YamlForbiddenError):
            parse_yaml_subset("a: 1\n---\nb: 2\n")

    def test_duplicate_mapping_key_rejected(self):
        with self.assertRaises(YamlForbiddenError):
            parse_yaml_subset("a: 1\na: 2\n")

    def test_non_string_key_rejected(self):
        with self.assertRaises(YamlForbiddenError):
            parse_yaml_subset("true: 1\n")


class SyntaxErrorTests(unittest.TestCase):
    def test_malformed_flow_sequence(self):
        with self.assertRaises(YamlSyntaxError):
            parse_yaml_subset("a: [1, 2\n")


if __name__ == "__main__":
    unittest.main()
