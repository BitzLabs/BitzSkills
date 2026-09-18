"""fixture基盤の、時間上限のある自己試験（Linux／POSIX）。"""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest

from harness import differences, git, safe_path, setup, snapshot, tree_digest_bytes

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

    def build_structure_fixture(self, root, operation):
        """submodule／worktree opを試すための最小のfixture directoryを作る。"""
        fixture = root / "fixture"
        (fixture / "repo/.spec").mkdir(parents=True)
        (fixture / "repo/.spec/bitz.yaml").write_text('schemaVersion: "1.0"\n', encoding="utf-8")
        (fixture / "changes/member/.spec").mkdir(parents=True)
        (fixture / "changes/member/.spec/bitz.yaml").write_text("workspace:\n  id: web\n", encoding="utf-8")
        manifest = {"setup": {"git": True, "baseCommit": {"message": "base", "paths": ["."]},
                              "operations": [{"op": operation, "path": "apps/web",
                                              "source": "changes/member"}]}}
        return fixture, manifest

    def test_git_structure_operations(self):
        """ADR-048のsubmodule／worktreeが、2回のsetupで同じGit構造を作る。"""
        for operation in ("submodule", "worktree"):
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                fixture, manifest = self.build_structure_fixture(root, operation)
                states = []
                for run in range(2):
                    repository = setup(fixture, manifest, root / f"run{run}")
                    marker = repository / "apps/web/.git"
                    self.assertTrue((repository / "apps/web/.spec/bitz.yaml").is_file())
                    # 入れ子のGitのmetadataはsnapshotへ現れない。
                    self.assertNotIn("apps/web/.git", snapshot(repository))
                    if operation == "submodule":
                        self.assertTrue(marker.is_dir())
                        entry = git(repository, "ls-files", "--stage", "--", "apps/web").decode()
                        self.assertTrue(entry.startswith("160000"))
                        self.assertIn("apps/web", (repository / ".gitmodules").read_text())
                    else:
                        self.assertTrue(marker.is_file())
                        self.assertTrue(marker.read_text().startswith("gitdir:"))
                        self.assertIn("apps/web", git(repository, "worktree", "list").decode())
                    states.append((snapshot(repository),
                                   git(repository, "status", "--porcelain=v1", "--untracked-files=all").decode(),
                                   git(repository, "ls-files", "--stage").decode()))
                self.assertEqual(states[0], states[1])

    def test_generated_input_setup(self):
        """生成入力のsetupは、渡した(path, 内容)の列だけをtreeへ書き出す。"""
        entries = [(".spec/bitz.yaml", b'schemaVersion: "1.0"\n'),
                   ("apps/web/.spec/bitz.yaml", b"workspace:\n  id: web\n")]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = root / "fixture"
            fixture.mkdir()
            manifest = {"setup": {"git": True,
                                  "generate": {"dataset": "dataset.json",
                                               "treeDigest": tree_digest_bytes(entries)},
                                  "baseCommit": {"message": "base", "paths": ["."]},
                                  "operations": []}}
            repository = setup(fixture, manifest, root / "run", generated=entries)
            self.assertEqual(sorted(path for path, entry in snapshot(repository).items()
                                    if entry["kind"] == "file"),
                             [".spec/bitz.yaml", "apps/web/.spec/bitz.yaml"])
            self.assertEqual(git(repository, "status", "--porcelain=v1").decode(), "")
            with self.assertRaises(ValueError):
                setup(fixture, manifest, root / "missing")

    def test_tree_digest_depends_on_path_and_content(self):
        base = [("a.txt", b"one"), ("b.txt", b"two")]
        self.assertEqual(tree_digest_bytes(base), tree_digest_bytes(list(reversed(base))))
        self.assertNotEqual(tree_digest_bytes(base), tree_digest_bytes([("a.txt", b"one"), ("b.txt", b"three")]))
        self.assertNotEqual(tree_digest_bytes(base), tree_digest_bytes([("a.txt", b"one"), ("c.txt", b"two")]))

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
