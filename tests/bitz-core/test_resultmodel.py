"""status集約とDiagnostic sortの単体試験。"""

import unittest

from bitz.resultmodel import (
    EXIT_CODE_BY_STATUS,
    diagnostic_sort_key,
    doctor_status,
    sort_diagnostics,
    worst_status,
)


def _diag(workspace_id, path, line=None, column=None, code="Z-Z-999", spec_refs=None):
    source = {"kind": "file", "workspaceId": workspace_id, "path": path}
    if line is not None:
        source["line"] = line
    if column is not None:
        source["column"] = column
    return {
        "code": code,
        "severity": "error",
        "resultStatus": "failed",
        "summary": "x",
        "source": source,
        "specRefs": spec_refs or [],
    }


class WorstStatusTests(unittest.TestCase):
    def test_empty_is_passed(self):
        self.assertEqual(worst_status([]), "passed")

    def test_order(self):
        self.assertEqual(worst_status(["passed", "passed_with_warnings"]), "passed_with_warnings")
        self.assertEqual(worst_status(["passed_with_warnings", "blocked"]), "blocked")
        self.assertEqual(worst_status(["blocked", "failed"]), "failed")
        self.assertEqual(worst_status(["failed", "error"]), "error")


class ExitCodeTests(unittest.TestCase):
    def test_each_status_maps_to_contract_exit_code(self):
        self.assertEqual(
            EXIT_CODE_BY_STATUS,
            {"passed": 0, "passed_with_warnings": 0, "failed": 1, "blocked": 2, "error": 3},
        )

    def test_argument_error_code_is_not_a_result_status(self):
        # 終了コード4はCLI引数不正専用で、結果statusから導かない（結果契約 §2）。
        self.assertNotIn(4, EXIT_CODE_BY_STATUS.values())


class DoctorStatusTests(unittest.TestCase):
    def test_info_check_does_not_change_status(self):
        checks = [{"name": "impact", "status": "info"}]
        self.assertEqual(doctor_status(checks, []), "passed")

    def test_warning_check_becomes_passed_with_warnings(self):
        checks = [{"name": "git", "status": "warning"}]
        self.assertEqual(doctor_status(checks, []), "passed_with_warnings")

    def test_blocked_check_wins_over_warning(self):
        checks = [{"name": "git", "status": "warning"}, {"name": "command", "status": "blocked"}]
        self.assertEqual(doctor_status(checks, []), "blocked")


class DiagnosticSortTests(unittest.TestCase):
    def test_null_workspace_id_sorts_before_string(self):
        a = _diag(None, ".spec/bitz.yaml")
        b = _diag("root", ".spec/bitz.yaml")
        self.assertEqual(sort_diagnostics([b, a]), [a, b])

    def test_sort_by_path_then_line_then_column_then_code(self):
        a = _diag("root", "a.md", line=1, column=1, code="A-A-001")
        b = _diag("root", "a.md", line=1, column=2, code="A-A-001")
        c = _diag("root", "b.md", line=1, column=1, code="A-A-001")
        self.assertEqual(sort_diagnostics([c, b, a]), [a, b, c])

    def test_sort_key_is_deterministic_tuple(self):
        d = _diag("root", "a.md", line=1, column=1, code="A-A-001", spec_refs=["REQ-001"])
        key = diagnostic_sort_key(d)
        self.assertEqual(key[-1], ("REQ-001",))


if __name__ == "__main__":
    unittest.main()
