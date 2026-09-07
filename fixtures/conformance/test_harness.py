"""Bounded self-tests for fixture infrastructure (Linux/POSIX)."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest

from harness import differences, git, safe_path, setup, snapshot

HERE = Path(__file__).resolve().parent


class HarnessTests(unittest.TestCase):
    def test_git_states_twice(self):
        fixture = HERE / "harness-input"
        for vector in json.loads((fixture / "git-vectors.json").read_text()):
            with self.subTest(vector=vector["id"]), tempfile.TemporaryDirectory() as temporary:
                observations = []
                for index in range(2):
                    root = setup(fixture, vector, Path(temporary) / str(index))
                    status = git(root, "status", "--porcelain=v1").decode()
                    self.assertEqual(status, vector["status"])
                    head = git(root, "rev-parse", "HEAD").decode().strip() if vector["hasHead"] else None
                    if not vector["hasHead"]:
                        with self.assertRaises(subprocess.CalledProcessError):
                            git(root, "rev-parse", "--verify", "HEAD")
                    observations.append((status, head, snapshot(root), git(root, "ls-files", "--stage")))
                self.assertEqual(*observations)

    def test_snapshot_and_path_boundary(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "file").write_bytes(b"base")
            before = snapshot(root)
            self.assertEqual(differences(before, snapshot(root)), [])
            (root / "file").write_bytes(b"changed")
            self.assertEqual(differences(before, snapshot(root)), ["file"])
            before = snapshot(root)
            (root / "file").chmod(0o755)
            self.assertEqual(differences(before, snapshot(root)), ["file"])
            (root / "link").symlink_to("missing")
            before = snapshot(root)
            (root / "link").unlink()
            (root / "link").symlink_to("elsewhere")
            self.assertEqual(differences(before, snapshot(root)), ["link"])
            for path in ["../escape", "/absolute", "a/../escape", ".git/config", "link/child"]:
                with self.subTest(path=path), self.assertRaises(ValueError):
                    safe_path(root, path)

    def test_process_behaviors(self):
        helper = [sys.executable, str(HERE / "process_helper.py")]
        for code in (0, 7):
            self.assertEqual(subprocess.run([*helper, "exit", str(code)], timeout=5).returncode, code)
        self.assertEqual(subprocess.run([*helper, "signal"], timeout=5).returncode, -signal.SIGTERM)
        for mode in ("timeout", "pipe"):
            with self.subTest(mode=mode):
                process = subprocess.Popen([*helper, mode], stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
                start = time.monotonic()
                try:
                    with self.assertRaises(subprocess.TimeoutExpired):
                        process.communicate(timeout=0.5)
                finally:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    process.communicate(timeout=5)
                self.assertLess(time.monotonic() - start, 5.5)


if __name__ == "__main__":
    unittest.main()
