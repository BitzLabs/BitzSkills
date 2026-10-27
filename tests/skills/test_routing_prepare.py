"""Resource freezing preserves committed provenance and repository boundaries."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "routing_prepare", REPO / "evals/skills/routing/prepare.py")
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


class RoutingPreparationTests(unittest.TestCase):
    def setUp(self):
        (REPO / ".venv").mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=REPO / ".venv", prefix="routing-test-")
        self.root = Path(self.temporary.name)
        self.environment = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_AUTHOR_NAME": "Synthetic routing", "GIT_AUTHOR_EMAIL": "routing@invalid",
            "GIT_COMMITTER_NAME": "Synthetic routing", "GIT_COMMITTER_EMAIL": "routing@invalid",
            "GIT_AUTHOR_DATE": "2026-10-06T00:00:00Z", "GIT_COMMITTER_DATE": "2026-10-06T00:00:00Z",
        }
        self.git("init", "-b", "routing-fixture")
        self.paths = []
        for name, package in prepare.SKILLS.items():
            path = self.root / f"plugins/{package}/skills/{name}/SKILL.md"
            path.parent.mkdir(parents=True)
            path.write_text(
                f"---\nname: {name}\ndescription: {name}の合成説明\n"
                "metadata:\n  version: '1.2.3'\n---\n本文\n")
            self.paths.append(path.relative_to(self.root).as_posix())
        self.commit(self.paths)
        self.ref = self.git("rev-parse", "HEAD").decode().strip()
        self.patch_root = patch.object(prepare, "ROOT", self.root)
        self.patch_root.start()
        self.addCleanup(self.patch_root.stop)
        self.addCleanup(self.temporary.cleanup)

    def git(self, *args):
        return subprocess.check_output(
            ["git", "-c", "core.hooksPath=/dev/null", *args],
            cwd=self.root, env=self.environment, stderr=subprocess.PIPE)

    def commit(self, paths):
        self.git("add", "--", *paths)
        self.git("commit", "-m", "synthetic routing source")

    def test_uncommitted_edits_do_not_enter_frozen_snapshot(self):
        path = self.root / self.paths[0]
        original = path.read_bytes()
        path.write_text("uncommitted invalid source")
        output = self.root / ".venv/snapshot"
        result = prepare.prepare(self.ref, output)
        self.assertEqual(self.ref, result["sourceCommit"])
        self.assertEqual(6, result["skillCount"])
        self.assertEqual(original, (output / "resources/bitz-core/skills/bitz-core/SKILL.md").read_bytes())
        self.assertEqual("uncommitted invalid source", path.read_text())
        manifest = json.loads((output / "manifest.json").read_text())
        self.assertEqual(hashlib.sha256(original).hexdigest(),
                         manifest["resources"]["resources/bitz-core/skills/bitz-core/SKILL.md"])

    def test_older_ref_remains_frozen_after_new_commit(self):
        path = self.root / self.paths[0]
        path.write_text(path.read_text().replace("の合成説明", "の変更した説明"))
        self.commit([self.paths[0]])
        manifest, _ = prepare.frozen_resources(self.ref)
        self.assertEqual("bitz-coreの合成説明", manifest["skills"][0]["description"])
        self.assertEqual(self.ref, manifest["sourceCommit"])

    def test_symlink_source_is_rejected_before_any_blob_read_or_output(self):
        link = self.root / "plugins/bitz-core/unsafe-link"
        link.symlink_to(self.root.parent / "never-read-routing-target")
        self.commit(["plugins/bitz-core/unsafe-link"])
        output = self.root / ".venv/rejected"
        original = prepare.git
        calls = []
        def observed(*args):
            calls.append(args)
            return original(*args)
        with patch.object(prepare, "git", side_effect=observed):
            with self.assertRaisesRegex(ValueError, "regular tracked"):
                prepare.prepare("HEAD", output)
        self.assertFalse(output.exists())
        self.assertFalse(any(args[0] == "show" for args in calls))

    def test_output_escape_and_venv_root_are_rejected_before_git(self):
        for output in [self.root.parent / "never-created-routing-output", self.root / ".venv"]:
            with self.subTest(output=output), patch.object(prepare, "git") as git:
                with self.assertRaisesRegex(ValueError, "below repository"):
                    prepare.prepare(self.ref, output)
                git.assert_not_called()

    def test_output_symlink_escape_is_rejected(self):
        (self.root / ".venv").mkdir()
        (self.root / ".venv/escape").symlink_to(self.root.parent, target_is_directory=True)
        with patch.object(prepare, "git") as git:
            with self.assertRaisesRegex(ValueError, "below repository"):
                prepare.prepare(self.ref, self.root / ".venv/escape/never-created-output")
            git.assert_not_called()

    def test_existing_snapshot_is_never_overwritten(self):
        output = self.root / ".venv/snapshot"
        prepare.prepare(self.ref, output)
        before = {p.relative_to(output): p.read_bytes() for p in output.rglob("*") if p.is_file()}
        with self.assertRaises(FileExistsError):
            prepare.prepare(self.ref, output)
        self.assertEqual(before, {p.relative_to(output): p.read_bytes()
                                  for p in output.rglob("*") if p.is_file()})

    def test_invalid_skill_identity_and_version_create_no_snapshot(self):
        original = (self.root / self.paths[0]).read_text()
        for invalid in [original.replace("name: bitz-core", "name: unknown"),
                        original.replace("'1.2.3'", "'unknown'")]:
            (self.root / self.paths[0]).write_text(invalid)
            self.commit([self.paths[0]])
            with self.assertRaises(ValueError):
                prepare.prepare("HEAD", self.root / ".venv/rejected")
            self.assertFalse((self.root / ".venv/rejected").exists())

    def test_invalid_and_protected_resource_names_are_rejected(self):
        for name in ["../x", "/x", "x//y", "x/./y", "x/../y", "x\\y",
                     "plugins/x/.env", "plugins/x/.env.local", "plugins/x/.credentials.json"]:
            with self.subTest(name=name), self.assertRaises(ValueError):
                prepare.safe_path(name)


if __name__ == "__main__":
    unittest.main()
