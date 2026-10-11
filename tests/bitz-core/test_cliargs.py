"""引数列の解析の単体試験（Step 1の終了コード4のfixtureと正常な受理を対象）。"""

import unittest

from bitz.cliargs import parse_argv
from bitz.errors import CliArgError


class ParseArgvRejectionTests(unittest.TestCase):
    """`fixtures/conformance/single/SINGLE-*` の終了コード4の引数列を再現する。"""

    def assert_rejected(self, argv, expected_context=None):
        with self.assertRaises(CliArgError) as cm:
            parse_argv(argv)
        if expected_context is not None:
            self.assertEqual(cm.exception.context, expected_context)

    def test_context_rejects_report_option(self):
        # SINGLE-073-01
        self.assert_rejected(["context", "REQ-001", "--report"], "context")

    def test_doctor_rejects_report_option(self):
        # SINGLE-073-02
        self.assert_rejected(["doctor", "--report"], "doctor")

    def test_check_rejects_explicit_target_and_full(self):
        # SINGLE-074-01
        self.assert_rejected(["check", "REQ-001", "--full", "--format", "json"], "check")

    def test_verify_rejects_code_path_target(self):
        # SINGLE-074-02
        self.assert_rejected(["verify", "src/auth.py", "--format", "json"], "verify")

    def test_check_rejects_malformed_document_id(self):
        # SINGLE-074-03: REQ-1は3桁未満のため不正
        self.assert_rejected(["check", "REQ-1", "--format", "json"], "check")

    def test_check_rejects_duplicate_format(self):
        # SINGLE-127-01
        self.assert_rejected(["check", "--format", "json", "--format", "json"], "check")

    def test_check_rejects_duplicate_full(self):
        # SINGLE-127-02
        self.assert_rejected(["check", "--full", "--full", "--format", "json"], "check")

    def test_check_rejects_empty_positional(self):
        # SINGLE-127-05
        self.assert_rejected(["check", "", "--format", "json"], "check")

    def test_context_rejects_zero_roots(self):
        # SINGLE-127-06
        self.assert_rejected(["context", "--format", "json"], "context")

    def test_doctor_rejects_empty_workspace_value(self):
        # SINGLE-127-07
        self.assert_rejected(["doctor", "--workspace", "", "--format", "json"], "doctor")

    def test_check_rejects_report_with_path_value(self):
        # SINGLE-127-11
        self.assert_rejected(["check", "--report=out.json", "--format", "json"], "check")

    def test_check_rejects_name_value_format(self):
        self.assert_rejected(["check", "--format=json"], "check")

    def test_doctor_rejects_unknown_option(self):
        self.assert_rejected(["doctor", "--unknown"], "doctor")

    def test_verify_rejects_bad_timeout_leading_zero(self):
        self.assert_rejected(["verify", "REQ-001", "--timeout", "0100"])

    def test_verify_rejects_timeout_out_of_range(self):
        self.assert_rejected(["verify", "REQ-001", "--timeout", "3601"])

    def test_verify_rejects_timeout_zero(self):
        self.assert_rejected(["verify", "REQ-001", "--timeout", "0"])

    def test_unknown_operation_rejected(self):
        with self.assertRaises(CliArgError):
            parse_argv(["bogus"])

    def test_empty_argv_rejected(self):
        with self.assertRaises(CliArgError):
            parse_argv([])

    def test_check_all_workspaces_excludes_workspace_option(self):
        self.assert_rejected(["check", "--all-workspaces", "--workspace", "root"], "check")

    def test_verify_all_workspaces_excludes_explicit_target(self):
        self.assert_rejected(["verify", "REQ-001", "--all-workspaces"], "verify")

    def test_doctor_workspace_and_all_workspaces_exclusive(self):
        self.assert_rejected(["doctor", "--workspace", "root", "--all-workspaces"], "doctor")


class ParseArgvAcceptanceTests(unittest.TestCase):
    def test_doctor_default_format(self):
        parsed = parse_argv(["doctor"])
        self.assertEqual(parsed.operation, "doctor")
        self.assertNotIn("--format", parsed.single)

    def test_check_full_with_base_and_format(self):
        parsed = parse_argv(["check", "--full", "--base", "HEAD", "--format", "json"])
        self.assertIn("--full", parsed.flags)
        self.assertEqual(parsed.single["--base"], "HEAD")
        self.assertEqual(parsed.single["--format"], "json")

    def test_check_accepts_document_id_target(self):
        parsed = parse_argv(["check", "REQ-001"])
        self.assertEqual(parsed.positionals, ["REQ-001"])

    def test_check_accepts_statement_id_target(self):
        parsed = parse_argv(["check", "REQ-001:AC-01"])
        self.assertEqual(parsed.positionals, ["REQ-001:AC-01"])

    def test_check_accepts_spec_path_target(self):
        parsed = parse_argv(["check", ".spec/requirements/REQ-001.md"])
        self.assertEqual(parsed.positionals, [".spec/requirements/REQ-001.md"])

    def test_verify_rejects_adr_target(self):
        with self.assertRaises(CliArgError):
            parse_argv(["verify", "ADR-001"])

    def test_context_accepts_multiple_roots_and_expand(self):
        parsed = parse_argv(
            ["context", "REQ-001", "TECH-001", "--expand", "REQ-001", "--expand", "REQ-001"]
        )
        self.assertEqual(parsed.positionals, ["REQ-001", "TECH-001"])
        # 同じ値の`--expand`は1件へ重複排除する。
        self.assertEqual(parsed.repeat["--expand"], ["REQ-001"])

    def test_doctor_repeat_capability_dedup(self):
        parsed = parse_argv(
            ["doctor", "--require-capability", "check.v1", "--require-capability", "check.v1"]
        )
        self.assertEqual(parsed.repeat["--require-capability"], ["check.v1"])

    def test_verify_accepts_valid_timeout(self):
        parsed = parse_argv(["verify", "REQ-001", "--timeout", "3600"])
        self.assertEqual(parsed.single["--timeout"], "3600")



class DoctorPluginRequestLexicalTests(unittest.TestCase):
    """`doctor`のプラグインの要求の字句（ADR-061 Decision 1）。不一致は終了コード4（`CliArgError`）。"""

    def assert_rejected(self, option, value):
        with self.assertRaises(CliArgError, msg=f"{option} {value!r}") as cm:
            parse_argv(["doctor", option, value])
        self.assertEqual(cm.exception.context, "doctor")

    def assert_accepted(self, option, value):
        parsed = parse_argv(["doctor", option, value])
        if option == "--require-capability":
            self.assertEqual(parsed.repeat[option], [value])
        else:
            self.assertEqual(parsed.single[option], value)

    def test_plugin_id_accepted(self):
        for value in ("bitz-sdd", "a", "a1", "a1-b2-c3", "bitz", "a" * 64):
            with self.subTest(value=value):
                self.assert_accepted("--plugin", value)

    def test_plugin_id_rejected(self):
        for value in (
            "Bitz", "bitz-SDD", "1bitz", "-bitz", "bitz-", "bitz--sdd", "bitz_sdd", "bitz.sdd",
            "a" * 65, "bitz\n", "bitz-sdd\n", " bitz", "bitz ", "ｂitz", "bitzé",
        ):
            with self.subTest(value=value):
                self.assert_rejected("--plugin", value)

    def test_plugin_version_accepted(self):
        for value in (
            "0.0.0", "1.2.3", "10.20.30", "1.0.0-alpha", "1.0.0-alpha.1", "1.0.0-0.3.7", "1.0.0-x.7.z.92",
            "1.0.0-x-y-z.--", "1.0.0+20130313144700", "1.0.0-beta+exp.sha.5114f85", "1.0.0+21AF26D3----117B344092BD",
            "1.0.0-alpha-a.b-c-somethinglong+build.1-aef.1-its-okay", "1.0.0-0A.is.legal",
        ):
            with self.subTest(value=value):
                self.assert_accepted("--plugin-version", value)

    def test_plugin_version_rejected(self):
        for value in (
            "1", "1.0", "1.0.0.0", "01.0.0", "1.01.0", "1.0.01", "v1.0.0", "1.0.0-", "1.0.0-01",
            "1.0.0-alpha..1", "1.0.0-alpha.", "1.0.0+", "1.0.0+build..1", "1.0.0-alpha_beta", "1.0.0\n",
            " 1.0.0", "1.0.0 ", "1.0.0-alpha.01", "-1.0.0", "1.0.0+b+c", "１.0.0", "1.0.0-é",
        ):
            with self.subTest(value=value):
                self.assert_rejected("--plugin-version", value)

    def test_core_api_range_accepted(self):
        for value in (
            "1.0", "=1.0", ">=1.0", ">1.0", "<=1.0", "<1.0", "^1.0", "^0.9", "0.0", "10.20", ">=1.0 <2.0",
            ">=0.9 <1.0", ">=1.0 >1.0 <=3.0 <4.0", "1.0 1.0", "^1.0 <1.5",
        ):
            with self.subTest(value=value):
                self.assert_accepted("--require-core-api", value)

    def test_core_api_range_rejected(self):
        for value in (
            "01.0", "1.00", "1.01", "00.0", "1.0.0", ">=1.0.0", "^1.0.0", "1", ">=1", "~1.0", "~>1.0", "1.x",
            "1.*", "*", "x", ">=1.0 || >=2.0", "||", "1.0 - 2.0", "1.0-2.0", " >=1.0", ">=1.0 ", ">=1.0  <2.0",
            ">=1.0\t<2.0", ">=1.0\n", "1.0\n", "^1.0\n", "^^1.0", ">^1.0", "^>=1.0", "=>1.0", "== 1.0", ">= 1.0",
            "=<1.0", "!=1.0", ">=1.0,<2.0", "v1.0", ">=-1.0", "+1.0", "1.0-alpha", "1.0+build", "１.0",
            "^1.x", ">=1.0 <", "<>1.0",
        ):
            with self.subTest(value=value):
                self.assert_rejected("--require-core-api", value)

    def test_capability_accepted(self):
        for value in ("context.v1", "multiWorkspace.v1", "a.v10", "A1.v99", "doctor.v1", "context.v2", "x.v123456"):
            with self.subTest(value=value):
                self.assert_accepted("--require-capability", value)

    def test_capability_rejected(self):
        for value in (
            "context.v0", "context.V1", "context.v01", "context", "context.v", "context.1", "1context.v1",
            "context-x.v1", "context_x.v1", "context.v1.v1", "context.v1\n", " context.v1", "context.v1 ",
            ".v1", "context.v1a", "con.text.v1",
        ):
            with self.subTest(value=value):
                self.assert_rejected("--require-capability", value)

    def test_each_invalid_repeated_capability_is_rejected(self):
        with self.assertRaises(CliArgError):
            parse_argv(["doctor", "--require-capability", "context.v1", "--require-capability", "context.v0"])

    def test_capability_duplicates_are_collapsed(self):
        parsed = parse_argv(
            ["doctor", "--require-capability", "context.v1", "--require-capability", "check.v1",
             "--require-capability", "context.v1"]
        )
        self.assertEqual(parsed.repeat["--require-capability"], ["context.v1", "check.v1"])

    def test_lexical_error_precedes_missing_combination(self):
        # 字句の不一致は、組合せの不足より先に終了コード4とする。
        with self.assertRaises(CliArgError):
            parse_argv(["doctor", "--plugin", "Bad"])
        # 字句が正しければ、一部だけの指定でも解析は成功する（組合せは`doctor`が判定する）。
        parsed = parse_argv(["doctor", "--plugin", "bitz-sdd"])
        self.assertEqual(parsed.single["--plugin"], "bitz-sdd")


if __name__ == "__main__":
    unittest.main()
