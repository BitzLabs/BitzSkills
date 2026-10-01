"""配布スキルの操作例を公開CLIで確認する。モデルの行動評価・Gate認定とは別の検査。"""

import hashlib
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
import json


ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "plugins/bitz-core/skills/bitz-core"


def snapshot(root):
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in root.rglob("*") if path.is_file()}


class CoreSkillCommandTests(unittest.TestCase):
    def test_published_single_workspace_examples_without_implicit_writes(self):
        examples = re.findall(r"`(bitz [^`]+)`", (SKILL / "references/operations.md").read_text())
        self.assertEqual(8, len(examples))
        with tempfile.TemporaryDirectory(prefix="bitz-skill-commands-") as directory:
            workspace = Path(directory) / "workspace"
            # このfixtureの登録コマンドは /bin/true {tests}、cwdはワークスペース内。
            # ネットワーク・資格情報・書込みを使わないコマンドだけをこの検査で起動する。
            shutil.copytree(ROOT / "fixtures/conformance/single/SINGLE-113/repo", workspace)
            subprocess.run(["git", "init", "-b", "skill-test"], cwd=workspace, check=True, capture_output=True)
            for path in sorted(snapshot(workspace)):
                if not path.startswith(".git/"):
                    subprocess.run(["git", "add", "--", path], cwd=workspace, check=True, capture_output=True)
            before = snapshot(workspace)
            env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
            for example in examples:
                with self.subTest(command=example):
                    process = subprocess.run([sys.executable, "-m", "bitz.cli", *shlex.split(example)[1:]],
                                             cwd=workspace, env=env, capture_output=True, text=True, timeout=20)
                    self.assertIn(process.returncode, (0, 1, 2, 3), process.stderr)
                    result = json.loads(process.stdout)
                    self.assertEqual(shlex.split(example)[1], result["operation"])
                    self.assertEqual("1.0", result["schemaVersion"])
                    self.assertEqual({"passed": 0, "passed_with_warnings": 0, "failed": 1,
                                      "blocked": 2, "error": 3}[result["status"]], process.returncode)
                    if result["operation"] == "context":
                        self.assertTrue(result["resolution"]["complete"])
                    if result["operation"] == "verify":
                        self.assertEqual("passed", result["status"], result["diagnostics"])
                        self.assertTrue(result["targetResults"])
                        self.assertTrue(result["commands"])
                        self.assertTrue(all(command["argv"][0] == "/bin/true" for command in result["commands"]))
            self.assertEqual(before, snapshot(workspace))


if __name__ == "__main__":
    unittest.main()
