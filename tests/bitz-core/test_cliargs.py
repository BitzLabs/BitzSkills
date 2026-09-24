"""argv解析の単体試験（Step 1の終了コード4 fixtureと正常受理を対象）。"""

import unittest

from bitz.cliargs import parse_argv
from bitz.errors import CliArgError


class ParseArgvRejectionTests(unittest.TestCase):
    """`fixtures/conformance/single/SINGLE-*` の終了コード4 argvを再現する。"""

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
        # 同じ値の--expandは1件へ重複排除する。
        self.assertEqual(parsed.repeat["--expand"], ["REQ-001"])

    def test_doctor_repeat_capability_dedup(self):
        parsed = parse_argv(
            ["doctor", "--require-capability", "check.v1", "--require-capability", "check.v1"]
        )
        self.assertEqual(parsed.repeat["--require-capability"], ["check.v1"])

    def test_verify_accepts_valid_timeout(self):
        parsed = parse_argv(["verify", "REQ-001", "--timeout", "3600"])
        self.assertEqual(parsed.single["--timeout"], "3600")


if __name__ == "__main__":
    unittest.main()
