"""`bitz.execfile`の単体試験（doctorとverifyが共有する実行file解決）。"""

import os
import stat
import tempfile
import unittest
from pathlib import Path

from bitz import execfile


def _make_executable(path: Path) -> None:
    path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


class ResolveExecutableTests(unittest.TestCase):
    def test_slash_relative_resolves_against_cwd(self):
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "bin" / "run.sh"
            script.parent.mkdir()
            _make_executable(script)
            resolved = execfile.resolve_executable("bin/run.sh", tmp, {})
            self.assertEqual(resolved, str(script))

    def test_slash_absolute_ignores_cwd(self):
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "run.sh"
            _make_executable(script)
            resolved = execfile.resolve_executable(str(script), "/nonexistent", {})
            self.assertEqual(resolved, str(script))

    def test_no_slash_searches_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "mytool"
            _make_executable(script)
            resolved = execfile.resolve_executable("mytool", "/", {"PATH": tmp})
            self.assertEqual(resolved, str(script))

    def test_empty_path_element_resolves_against_cwd(self):
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "mytool"
            _make_executable(script)
            resolved = execfile.resolve_executable("mytool", tmp, {"PATH": "/nonexistent:"})
            self.assertEqual(resolved, str(script))

    def test_missing_file_returns_none(self):
        self.assertIsNone(execfile.resolve_executable("bin/absent.sh", "/tmp", {}))
        self.assertIsNone(execfile.resolve_executable("absent-tool", "/", {"PATH": "/nonexistent"}))

    def test_non_executable_file_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "run.sh"
            script.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            resolved = execfile.resolve_executable("run.sh", tmp, {})
            self.assertIsNone(resolved)


if __name__ == "__main__":
    unittest.main()
