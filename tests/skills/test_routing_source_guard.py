from __future__ import annotations
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
SPEC=importlib.util.spec_from_file_location("routing_source_guard",ROOT/"evals/skills/routing/source_guard.py")
guard=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(guard)


class SourceGuardTests(unittest.TestCase):
    def setUp(self):
        (ROOT/".venv").mkdir(exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/".venv");self.addCleanup(self.temp.cleanup)
        self.repo=Path(self.temp.name)
        self.command("init","-b","source-guard-fixture")
        self.command("config","user.name","Synthetic")
        self.command("config","user.email","synthetic@example.invalid")
        self.path=self.repo/"fixed.json";self.path.write_text('{"fixed":true}\n')
        self.command("add","fixed.json");self.command("commit","-m","fixture")
        self.ref=self.command("rev-parse","HEAD").strip()

    def command(self,*args):
        return guard.git(self.repo,*args).decode()

    def test_unrelated_committed_head_change_does_not_change_fixed_source(self):
        initial=guard.verify(self.repo,self.ref,["fixed.json"])
        (self.repo/"result.md").write_text("合成の結果記録")
        self.command("add","result.md");self.command("commit","-m","result")
        later=guard.verify(self.repo,self.ref,["fixed.json"])
        self.assertNotEqual(initial["observedHead"],later["observedHead"])
        self.assertEqual(initial["sourceSha256"],later["sourceSha256"])
        self.assertFalse(later["headIsCondition"])

    def test_uncommitted_and_committed_target_changes_are_rejected(self):
        self.path.write_text("changed")
        with self.assertRaisesRegex(ValueError,"fixed source drift"):
            guard.verify(self.repo,self.ref,["fixed.json"])
        self.command("add","fixed.json");self.command("commit","-m","changed")
        with self.assertRaisesRegex(ValueError,"fixed source drift"):
            guard.verify(self.repo,self.ref,["fixed.json"])

    def test_invalid_ref_or_protected_path_is_rejected_before_git_or_read(self):
        with patch.object(guard,"git",side_effect=AssertionError("unexpected git")), patch.object(Path,"read_bytes",side_effect=AssertionError("unexpected read")):
            for ref in ["HEAD","main","-x"]:
                with self.assertRaises(ValueError):guard.verify(self.repo,ref,["fixed.json"])
            for path in ["../outside",str(self.path),".env","dir/.env.local",".git/config","dir//file"]:
                with self.assertRaises(ValueError):guard.verify(self.repo,self.ref,["fixed.json",path])

    def test_same_bytes_symlink_is_rejected_before_git_or_read(self):
        other=self.repo/"other.json";self.path.rename(other);self.path.symlink_to(other)
        with patch.object(guard,"git",side_effect=AssertionError("unexpected git")):
            with self.assertRaisesRegex(ValueError,"source symlink"):
                guard.verify(self.repo,self.ref,["fixed.json"])


if __name__=="__main__":unittest.main()
