"""CLIを実際に起動し、結果statusと終了コードの対応を確かめる試験（REQ-002:AC-02、AC-04）。

`resultmodel.EXIT_CODE_BY_STATUS`の対応表だけでなく、console script `bitz`の終了コードが
結果JSONのstatusと一致することを、一時directoryに作った最小のworkspaceで確かめる。
"""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

BITZ = Path(sys.executable).parent / "bitz"

CONFIG = 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\n'
STATEMENT = "- [REQ-001:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 秘密情報を出力しない。"


def requirement(extra_frontmatter="", statement=STATEMENT):
    return (
        "---\nid: REQ-001\ntitle: 終了コード\nstatus: approved\n" + extra_frontmatter + "---\n\n"
        "# REQ-001 終了コード\n\n## Intent\n\n終了コードを確かめる。\n\n"
        "## Acceptance Criteria\n\n" + statement + "\n\n## Verification\n\nCLI試験で確かめる。\n"
    )


class CliExitCodeTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        # 親directoryのGit repositoryやworkspaceを探索しないよう、探索をこのdirectoryで止める。
        self.env = dict(os.environ, GIT_CEILING_DIRECTORIES=str(self.root.parent))

    def tearDown(self):
        self._tmp.cleanup()

    def write_workspace(self, config=CONFIG, document=None):
        spec = self.root / ".spec"
        (spec / "requirements").mkdir(parents=True)
        (spec / "bitz.yaml").write_text(config, encoding="utf-8")
        if document is not None:
            (spec / "requirements" / "REQ-001.md").write_text(document, encoding="utf-8")

    def run_bitz(self, *argv):
        return subprocess.run([str(BITZ), *argv], cwd=self.root, env=self.env,
                              capture_output=True, text=True, timeout=60)

    def assert_status_and_exit(self, expected_status, expected_exit):
        completed = self.run_bitz("check", "--full", "--format", "json")
        result = json.loads(completed.stdout)
        self.assertEqual(result["status"], expected_status)
        self.assertEqual(completed.returncode, expected_exit)

    def test_passed_exits_0(self):
        self.write_workspace(document=requirement())
        self.assert_status_and_exit("passed", 0)

    def test_passed_with_warnings_exits_0(self):
        self.write_workspace(document=requirement(extra_frontmatter="future: 1\n"))
        self.assert_status_and_exit("passed_with_warnings", 0)

    def test_failed_exits_1(self):
        broken = "- [REQ-001:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 句点がない"
        self.write_workspace(document=requirement(statement=broken))
        self.assert_status_and_exit("failed", 1)

    def test_blocked_exits_2(self):
        # `.spec/bitz.yaml`がないworkspaceはSPEC-WORKSPACE-MISSING-001／blockedになる。
        self.assert_status_and_exit("blocked", 2)

    def test_error_exits_3(self):
        # 設定YAMLの構文不正はSPEC-CONFIG-SCHEMA-001／errorになる。
        self.write_workspace(config='schemaVersion: "1.0"\nearsAi: [\n', document=requirement())
        self.assert_status_and_exit("error", 3)

    def test_unparsable_argument_exits_4_without_result(self):
        self.write_workspace(document=requirement())
        completed = self.run_bitz("check", "--full", "--no-such-option")
        self.assertEqual(completed.returncode, 4)
        self.assertEqual(completed.stdout, "")
        self.assertTrue(completed.stderr.endswith("\n"))
        self.assertEqual(len(completed.stderr[:-1].split("\n")), 1)


if __name__ == "__main__":
    unittest.main()
