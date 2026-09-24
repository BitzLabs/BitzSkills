"""`reportio.write_report`の単体試験（`00_共通契約/02_安全な入出力・互換性.md §8`）。

排他的作成、成功時に一時fileを残さないこと、`.spec`または`.spec/reports`がdirectory以外
（file・symlink）の場合に解決せず失敗することを検査する。
"""

import os
import tempfile
import unittest

from bitz import reportio


def _listdir(path):
    try:
        return sorted(os.listdir(path))
    except OSError:
        return []


class WriteReportTests(unittest.TestCase):
    def test_success_creates_exactly_one_file_and_no_temp_files_remain(self):
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, ".spec", "reports"))
            failure = reportio.write_report(root, "root", "check", {"schemaVersion": "1.0"})
            self.assertIsNone(failure)
            names = _listdir(os.path.join(root, ".spec", "reports"))
            self.assertEqual(len(names), 1)
            self.assertRegex(names[0], r"^[0-9]{8}T[0-9]{6}Z-check(?:-[1-9][0-9]*)?\.json$")
            self.assertFalse(any(n.startswith(".") for n in names))

    def test_reports_directory_auto_created_when_missing(self):
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, ".spec"))
            failure = reportio.write_report(root, "root", "check", {"schemaVersion": "1.0"})
            self.assertIsNone(failure)
            self.assertTrue(os.path.isdir(os.path.join(root, ".spec", "reports")))

    def test_existing_file_is_not_overwritten_second_call_uses_sequence(self):
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, ".spec", "reports"))
            reportio.write_report(root, "root", "check", {"a": 1})
            reportio.write_report(root, "root", "check", {"a": 2})
            names = _listdir(os.path.join(root, ".spec", "reports"))
            self.assertEqual(len(names), 2)

    def test_reports_path_is_a_regular_file_fails(self):
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, ".spec"))
            with open(os.path.join(root, ".spec", "reports"), "w", encoding="utf-8") as f:
                f.write("not a directory\n")
            failure = reportio.write_report(root, "root", "check", {"schemaVersion": "1.0"})
            self.assertIsNotNone(failure)
            self.assertEqual(failure.code, "SPEC-REPORT-WRITE-001")
            self.assertEqual(failure.resultStatus, "error")

    def test_reports_path_is_a_symlink_fails_without_following(self):
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, ".spec"))
            target = os.path.join(root, "report-store")
            os.makedirs(target)
            os.symlink(target, os.path.join(root, ".spec", "reports"))
            failure = reportio.write_report(root, "root", "check", {"schemaVersion": "1.0"})
            self.assertIsNotNone(failure)
            self.assertEqual(failure.code, "SPEC-REPORT-WRITE-001")
            # symlink先へ書き込んでいない。
            self.assertEqual(_listdir(target), [])

    def test_spec_dir_missing_fails(self):
        with tempfile.TemporaryDirectory() as root:
            failure = reportio.write_report(root, "root", "check", {"schemaVersion": "1.0"})
            self.assertIsNotNone(failure)
            self.assertEqual(failure.code, "SPEC-REPORT-WRITE-001")


if __name__ == "__main__":
    unittest.main()
