"""収束時の公開CLI・状態と配布内参照。人間確認は合成fixtureだけで模擬する。"""
from pathlib import Path
import re
import unittest

import test_sdd_implement_connection as implementation


ROOT = implementation.ROOT
PACKAGE = ROOT / "plugins/bitz-sdd"


class SddConvergeConnectionTests(unittest.TestCase):
    def setUp(self):
        self.fixture = implementation.SddImplementConnectionTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.workspace = self.fixture.workspace
        self.cli = self.fixture.cli

    def test_confirmed_synthetic_task_is_checked_after_done_and_git_record(self):
        self.fixture.prepare()
        initial = self.fixture.context()
        self.assertIn(self.cli("check", "TASK-001", "--base", "HEAD")["status"], implementation.PASS_STATUSES)
        confirmed = self.cli("context", "TASK-001", "--purpose", "implement",
                             "--expect-digest", initial["contextDigest"])
        self.assertEqual(initial["contextDigest"], confirmed["contextDigest"])
        (self.workspace / "src/input.py").write_text(implementation.FIXED_SOURCE)
        self.assertIn(self.cli("check", "TASK-001", "--base", "HEAD")["status"], implementation.PASS_STATUSES)
        verified = self.cli("verify", "TASK-001")
        self.assertEqual("passed", verified["status"])
        self.assertEqual(["REQ-001:AC-01"], verified["targetResults"][0]["statements"])
        self.fixture.fixture.commit_fixture()
        # この合成例だけで、確定した差分と実assertへの人間確認後を模擬する。
        # 実際の利用者の承認、製品要求の実証、品質レビューを表す記録ではない。
        task = self.workspace / ".spec/tasks/TASK-001.md"
        self.assertIn("status: open", task.read_text())
        task.write_text(task.read_text().replace("status: open", "status: done"))
        final_check = self.cli("check", "TASK-001")
        self.assertIn(final_check["status"], implementation.PASS_STATUSES)
        self.fixture.fixture.commit_fixture()
        recorded = self.cli("check", "TASK-001")
        self.assertFalse(recorded["revision"]["dirty"])
        self.assertEqual(self.fixture.fixture.git("rev-parse", "HEAD").stdout.strip(), recorded["revision"]["commit"])
        # 完了したTASKからも検証用contextと実verifyは取得できる。
        context = self.cli("context", "TASK-001", "--purpose", "verify")
        self.assertIn(context["status"], implementation.PASS_STATUSES)
        self.assertTrue(context["resolution"]["complete"])
        self.assertEqual("passed", self.cli("verify", "TASK-001")["status"])

    def test_failed_verification_does_not_write_task_state(self):
        self.fixture.prepare()
        task = self.workspace / ".spec/tasks/TASK-001.md"
        original = task.read_bytes()
        result = self.cli("verify", "TASK-001")
        self.assertEqual("failed", result["status"])
        self.assertTrue(all(c["exitCode"] == 1 for c in result["commands"]))
        self.assertEqual(original, task.read_bytes())
        self.assertIn("status: open", task.read_text())

    def test_missing_must_test_binding_cannot_be_completion_evidence(self):
        self.fixture.prepare(registered=False, source=implementation.FIXED_SOURCE)
        result = self.cli("verify", "TASK-001")
        self.assertEqual("blocked", result["status"])
        self.assertEqual([], result["commands"])
        self.assertIn("CTX-COVERAGE-TEST-001", [d["code"] for t in result["targetResults"] for d in t["diagnostics"]])
        self.assertIn("status: open", (self.workspace / ".spec/tasks/TASK-001.md").read_text())

    def test_packaged_references_resolve_inside_sdd_plugin(self):
        for file in PACKAGE.rglob("*.md"):
            for link in re.findall(r"\]\(([^)]+)\)", file.read_text()):
                if "://" not in link:
                    target = (file.parent / link.split("#", 1)[0]).resolve()
                    self.assertTrue(target.is_relative_to(PACKAGE.resolve()), (file, link))
                    self.assertTrue(target.is_file(), (file, link))


if __name__ == "__main__":
    unittest.main()
