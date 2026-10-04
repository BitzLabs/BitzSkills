"""配布SPEC例の構文、草案からの実装遮断、TASK境界を公開CLIで検査する。"""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "plugins/bitz-sdd/skills/sdd-plan/examples"


def snapshot(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("*") if p.is_file() and ".git" not in p.relative_to(root).parts}


class SddPlanExampleTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="bitz-sdd-plan-")
        self.addCleanup(self.temporary.cleanup)
        self.workspace = Path(self.temporary.name)
        for path in (".spec/requirements", ".spec/tasks", "src", "tests"):
            (self.workspace / path).mkdir(parents=True)
        (self.workspace / ".spec/bitz.yaml").write_text(
            'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\n')
        for kind, name in (("requirements", "REQ-001.md"), ("tasks", "TASK-001.md")):
            shutil.copyfile(EXAMPLES / name, self.workspace / ".spec" / kind / name)
        for path in ("src/input.py", "tests/test_input.py", "outside.py"):
            (self.workspace / path).write_text("# 検査専用の未実装ファイル\n")
        self.git("init", "-b", "sdd-plan-test")

    def git(self, *arguments):
        return subprocess.run(["git", *arguments], cwd=self.workspace, check=True,
                              capture_output=True, text=True)

    def commit_fixture(self):
        for path in sorted(snapshot(self.workspace)):
            self.git("add", "--", path)
        self.git("-c", "user.name=SDD example test", "-c", "user.email=example@invalid",
                 "commit", "-m", "test fixture")

    def cli(self, *arguments):
        before = snapshot(self.workspace)
        process = subprocess.run([sys.executable, "-m", "bitz.cli", *arguments, "--format", "json"],
                                 cwd=self.workspace, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
                                 text=True, capture_output=True, timeout=20)
        self.assertIn(process.returncode, (0, 1, 2, 3), process.stderr)
        result = json.loads(process.stdout)
        self.assertEqual("1.0", result["schemaVersion"])
        self.assertEqual(arguments[0], result["operation"])
        self.assertEqual({"passed": 0, "passed_with_warnings": 0, "failed": 1,
                          "blocked": 2, "error": 3}[result["status"]], process.returncode)
        self.assertEqual(before, snapshot(self.workspace), "検査がworkspaceへ暗黙に書き込んだ")
        return result

    def test_draft_examples_are_inspectable_but_not_implementation_roots(self):
        self.commit_fixture()
        for identifier in ("REQ-001", "TASK-001"):
            with self.subTest(identifier=identifier):
                self.assertIn(self.cli("check", identifier)["status"], ("passed", "passed_with_warnings"))
        result = self.cli("context", "REQ-001", "--purpose", "interpret")
        self.assertIn(result["status"], ("passed", "passed_with_warnings"))
        self.assertTrue(result["resolution"]["complete"])
        self.assertTrue(result["contextDigest"])
        self.assertEqual("draft", result["documents"][0]["status"])
        self.assertEqual("blocked", self.cli("context", "TASK-001", "--purpose", "implement")["status"])

    def test_published_task_paths_allow_the_plan_and_reject_outside_changes(self):
        # 合成fixtureだけで人間の承認後を模擬する。製品・利用者のREQを承認しない。
        requirement = self.workspace / ".spec/requirements/REQ-001.md"
        requirement.write_text(requirement.read_text().replace("status: draft", "status: approved"))
        self.commit_fixture()
        (self.workspace / "src/input.py").write_text("# 境界内の検査用差分\n")
        result = self.cli("check", "TASK-001", "--base", "HEAD")
        self.assertIn(result["status"], ("passed", "passed_with_warnings"), result["diagnostics"])
        (self.workspace / "outside.py").write_text("# 境界外の検査用差分\n")
        result = self.cli("check", "TASK-001", "--base", "HEAD")
        self.assertEqual("failed", result["status"])
        self.assertTrue(any("BOUNDARY" in d["code"] for d in result["diagnostics"]), result["diagnostics"])


if __name__ == "__main__":
    unittest.main()
