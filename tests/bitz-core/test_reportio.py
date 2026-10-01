"""`reportio.write_report`の単体試験（`00_共通契約/02_安全な入出力・互換性.md §8`）。

排他的な作成、成功時に一時ファイルを残さないこと、`.spec`または`.spec/reports`がディレクトリ以外
（ファイル・シンボリックリンク）の場合に解決せず失敗することを検査する。REQ-003の3つの規範文
（AC-01: シンボリックリンクを辿らないファイルディスクリプター基準の書込み、AC-02: 検査と書込みの間の差し替えの競合状態の検出、
AC-03: 成功・失敗いずれでも一時ファイルを残さないこと）をそれぞれ確認する。
"""

import os
import shutil
import tempfile
import unittest
from unittest import mock

from bitz import reportio


def _listdir(path):
    try:
        return sorted(os.listdir(path))
    except OSError:
        return []


class WriteReportTests(unittest.TestCase):
    def test_success_creates_exactly_one_file_and_no_temp_files_remain(self):
        # REQ-003:AC-01, REQ-003:AC-03（成功時に一時ファイルを残さない）
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, ".spec", "reports"))
            failure = reportio.write_report(root, "root", "check", {"schemaVersion": "1.0"})
            self.assertIsNone(failure)
            names = _listdir(os.path.join(root, ".spec", "reports"))
            self.assertEqual(len(names), 1)
            self.assertRegex(names[0], r"^[0-9]{8}T[0-9]{6}Z-check(?:-[1-9][0-9]*)?\.json$")
            self.assertFalse(any(n.startswith(".") for n in names))

    def test_reports_directory_auto_created_when_missing(self):
        # REQ-003:AC-01（`.spec`のディレクトリのファイルディスクリプター基準で`mkdir`してから開き直す経路）
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
        # REQ-003:AC-02（ディレクトリ以外への解決を拒否する）
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, ".spec"))
            with open(os.path.join(root, ".spec", "reports"), "w", encoding="utf-8") as f:
                f.write("not a directory\n")
            failure = reportio.write_report(root, "root", "check", {"schemaVersion": "1.0"})
            self.assertIsNotNone(failure)
            self.assertEqual(failure.code, "SPEC-REPORT-WRITE-001")
            self.assertEqual(failure.resultStatus, "error")

    def test_reports_path_is_a_symlink_fails_without_following(self):
        # REQ-003:AC-01, REQ-003:AC-02（既にシンボリックリンクの場合に辿らず失敗する静的なケース）
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, ".spec"))
            target = os.path.join(root, "report-store")
            os.makedirs(target)
            os.symlink(target, os.path.join(root, ".spec", "reports"))
            failure = reportio.write_report(root, "root", "check", {"schemaVersion": "1.0"})
            self.assertIsNotNone(failure)
            self.assertEqual(failure.code, "SPEC-REPORT-WRITE-001")
            # シンボリックリンク先へ書き込んでいない。
            self.assertEqual(_listdir(target), [])

    def test_spec_dir_missing_fails(self):
        with tempfile.TemporaryDirectory() as root:
            failure = reportio.write_report(root, "root", "check", {"schemaVersion": "1.0"})
            self.assertIsNotNone(failure)
            self.assertEqual(failure.code, "SPEC-REPORT-WRITE-001")

    def test_reports_replaced_with_symlink_between_spec_open_and_reports_open(self):
        # REQ-003:AC-02: 競合状態の再現試験（ファイルディスクリプターの取得**前**の差し替え）。`.spec`のファイルディスクリプターを取得した
        # 直後（`reports`を開く直前）に`.spec/reports`を別のディレクトリへのシンボリックリンクへ差し替える
        # 割込みを差し込む。`O_NOFOLLOW`付きの単一の`open`へ検査と開封を統合しているため、
        # 差し替え先には一時ファイルもレポートも作られず、`SPEC-REPORT-WRITE-001`が返ることを確かめる。
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, ".spec", "reports"))
            diverted_target = os.path.join(root, "diverted-reports")
            os.makedirs(diverted_target)
            reports_path = os.path.join(root, ".spec", "reports")

            original_open_dir_no_follow = reportio._open_dir_no_follow

            def interrupting_open_dir_no_follow(name, dir_fd):
                if name == reportio._REPORTS_DIRNAME:
                    shutil.rmtree(reports_path)
                    os.symlink(diverted_target, reports_path)
                return original_open_dir_no_follow(name, dir_fd)

            with mock.patch.object(
                reportio,
                "_open_dir_no_follow",
                side_effect=interrupting_open_dir_no_follow,
            ):
                failure = reportio.write_report(root, "root", "check", {"schemaVersion": "1.0"})

            self.assertIsNotNone(failure)
            self.assertEqual(failure.code, "SPEC-REPORT-WRITE-001")
            self.assertEqual(_listdir(diverted_target), [])

    def test_spec_dir_replaced_with_symlink_before_open(self):
        # REQ-003:AC-02: `.spec`自体が（ファイルディスクリプターの取得**前**＝検査＝`open`の直前に）別のディレクトリへの
        # シンボリックリンクへ差し替えられた場合も、差し替え先には何も作られず失敗を返す。
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, ".spec", "reports"))
            diverted_target = os.path.join(root, "diverted-spec")
            os.makedirs(diverted_target)
            spec_path = os.path.join(root, ".spec")

            original_open_dir_no_follow = reportio._open_dir_no_follow

            def interrupting_open_dir_no_follow(name, dir_fd):
                if name == reportio._SPEC_DIRNAME:
                    shutil.rmtree(spec_path)
                    os.symlink(diverted_target, spec_path)
                return original_open_dir_no_follow(name, dir_fd)

            with mock.patch.object(
                reportio,
                "_open_dir_no_follow",
                side_effect=interrupting_open_dir_no_follow,
            ):
                failure = reportio.write_report(root, "root", "check", {"schemaVersion": "1.0"})

            self.assertIsNotNone(failure)
            self.assertEqual(failure.code, "SPEC-REPORT-WRITE-001")
            self.assertEqual(_listdir(diverted_target), [])

    def test_reports_directory_swapped_after_fd_acquired_before_link(self):
        # REQ-003:AC-02, REQ-003:AC-03: ファイルディスクリプターの取得**後**（一時ファイルの書込みの後、`os.link`の直前）に
        # `.spec/reports`を退避（リネーム）して別のディレクトリへのシンボリックリンクへ差し替える割込みを
        # 差し込む。`os.link`はファイルディスクリプター基準のため退避先（旧実ディレクトリ）へは書けてしまうが、確定
        # 直後の照合でそれを検出し、(1) シンボリックリンク先には何も作られない、(2) `SPEC-REPORT-WRITE-001`
        # が返る、(3) 退避した旧ディレクトリにもレポートと一時ファイルが残らない、ことを確かめる。
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, ".spec", "reports"))
            reports_path = os.path.join(root, ".spec", "reports")
            moved_path = os.path.join(root, "moved-reports")
            diverted_target = os.path.join(root, "diverted-reports")
            os.makedirs(diverted_target)

            original_link = reportio.os.link
            swapped = {"done": False}

            def interrupting_link(src, dst, *, src_dir_fd=None, dst_dir_fd=None):
                if not swapped["done"]:
                    swapped["done"] = True
                    os.rename(reports_path, moved_path)
                    os.symlink(diverted_target, reports_path)
                return original_link(src, dst, src_dir_fd=src_dir_fd, dst_dir_fd=dst_dir_fd)

            with mock.patch.object(reportio.os, "link", side_effect=interrupting_link):
                failure = reportio.write_report(root, "root", "check", {"schemaVersion": "1.0"})

            self.assertIsNotNone(failure)
            self.assertEqual(failure.code, "SPEC-REPORT-WRITE-001")
            self.assertEqual(_listdir(diverted_target), [])
            self.assertEqual(_listdir(moved_path), [])

    def test_spec_dir_swapped_after_fd_acquired_before_link(self):
        # REQ-003:AC-02, REQ-003:AC-03: `.spec`自体がファイルディスクリプターの取得**後**（`os.link`の直前）に
        # 退避されて別のディレクトリへのシンボリックリンクへ差し替えられた場合も、シンボリックリンク先には何も作られず、
        # 退避した旧`.spec`配下（`reports`を含む）にもレポートと一時ファイルが残らないことを確かめる。
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, ".spec", "reports"))
            spec_path = os.path.join(root, ".spec")
            moved_path = os.path.join(root, "moved-spec")
            diverted_target = os.path.join(root, "diverted-spec")
            os.makedirs(diverted_target)

            original_link = reportio.os.link
            swapped = {"done": False}

            def interrupting_link(src, dst, *, src_dir_fd=None, dst_dir_fd=None):
                if not swapped["done"]:
                    swapped["done"] = True
                    os.rename(spec_path, moved_path)
                    os.symlink(diverted_target, spec_path)
                return original_link(src, dst, src_dir_fd=src_dir_fd, dst_dir_fd=dst_dir_fd)

            with mock.patch.object(reportio.os, "link", side_effect=interrupting_link):
                failure = reportio.write_report(root, "root", "check", {"schemaVersion": "1.0"})

            self.assertIsNotNone(failure)
            self.assertEqual(failure.code, "SPEC-REPORT-WRITE-001")
            self.assertEqual(_listdir(diverted_target), [])
            self.assertEqual(_listdir(os.path.join(moved_path, "reports")), [])

    def test_temp_file_not_left_after_link_failure(self):
        # REQ-003:AC-03: 失敗時（ハードリンクの確定に失敗した場合）にも一時ファイルを残さない。
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, ".spec", "reports"))
            with mock.patch.object(reportio.os, "link", side_effect=PermissionError("denied")):
                failure = reportio.write_report(root, "root", "check", {"schemaVersion": "1.0"})
            self.assertIsNotNone(failure)
            self.assertEqual(failure.code, "SPEC-REPORT-WRITE-001")
            names = _listdir(os.path.join(root, ".spec", "reports"))
            self.assertEqual(names, [])

    def test_temp_file_not_left_after_success(self):
        # REQ-003:AC-03: 成功時、`reports`ディレクトリに残るのは最終的なレポート名のみで、
        # ドット始まりの一時ファイルが残らないことを明示的に確認する。
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, ".spec", "reports"))
            failure = reportio.write_report(root, "root", "check", {"schemaVersion": "1.0"})
            self.assertIsNone(failure)
            names = _listdir(os.path.join(root, ".spec", "reports"))
            self.assertTrue(all(not n.startswith(".bitz-report-") for n in names))


if __name__ == "__main__":
    unittest.main()
