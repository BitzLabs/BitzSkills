"""計画の配布例から公開Coreの実装・検証・引渡しへ接続する合成試験。"""

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

from jsonschema import Draft202012Validator
import test_sdd_plan_examples as plan_examples


PASS_STATUSES = ("passed", "passed_with_warnings")
ROOT = plan_examples.ROOT
BROKEN_SOURCE = "def validate(value):\n    return []\n"
FIXED_SOURCE = 'def validate(value):\n    return ["入力エラー"] if value == "" else []\n'
REAL_TEST = '''import importlib.util
from pathlib import Path
import unittest

source = Path(__file__).resolve().parents[1] / "src/input.py"
spec = importlib.util.spec_from_file_location("planned_input", source)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class InputContractTest(unittest.TestCase):
    def test_empty_input_returns_one_error(self):
        self.assertEqual(1, len(module.validate("")))

if __name__ == "__main__":
    unittest.main()
'''


class SddImplementConnectionTests(unittest.TestCase):
    def setUp(self):
        self.fixture = plan_examples.SddPlanExampleTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.workspace = self.fixture.workspace
        self.cli = self.fixture.cli

    def prepare(self, registered=True, source=BROKEN_SOURCE):
        # /tmpの合成例だけで要求レビューと人間の承認後を模擬する。
        requirement = self.workspace / ".spec/requirements/REQ-001.md"
        text = requirement.read_text().replace("status: draft", "status: approved")
        if registered:
            text = text.replace("status: approved\n", "status: approved\nimplements: [src/input.py]\n"
                                "tests:\n  - path: tests/test_input.py\n"
                                "    covers: [REQ-001:AC-01]\n    command: default\n")
            config = {"schemaVersion": "1.0", "language": "ja", "earsAi": "1.0",
                      "verify": {"commands": {"default": {
                          "argv": [sys.executable, "-I", "-B", "{tests}"], "cwd": "."}}}}
            (self.workspace / ".spec/bitz.yaml").write_text(json.dumps(config))
        requirement.write_text(text)
        (self.workspace / "src/input.py").write_text(source)
        (self.workspace / "tests/test_input.py").write_text(REAL_TEST)
        self.fixture.commit_fixture()

    def context(self):
        result = self.cli("context", "TASK-001", "--purpose", "implement")
        self.assertIn(result["status"], PASS_STATUSES, result["diagnostics"])
        self.assertTrue(result["resolution"]["complete"])
        self.assertTrue(result["contextDigest"])
        return result

    def test_passing_context_does_not_replace_failed_precheck(self):
        self.prepare()
        # 先に存在する利用者の境界外差分。context成功を許可に読み替えない。
        outside = self.workspace / "outside.py"
        outside.write_text("# 利用者が先に変更したファイル\n")
        self.context()
        result = self.cli("check", "TASK-001", "--base", "HEAD")
        self.assertEqual("failed", result["status"])
        self.assertTrue(any("BOUNDARY" in d["code"] for d in result["diagnostics"]))
        self.assertEqual("# 利用者が先に変更したファイル\n", outside.read_text())
        self.assertEqual(BROKEN_SOURCE, (self.workspace / "src/input.py").read_text())

    def test_changed_specification_is_blocked_by_the_saved_digest(self):
        self.prepare()
        initial = self.context()
        self.assertIn(self.cli("check", "TASK-001")["status"], PASS_STATUSES)
        requirement = self.workspace / ".spec/requirements/REQ-001.md"
        requirement.write_text(requirement.read_text() + "\n## Notes\n\n説明の更新を検出する。\n")
        stale = self.cli("context", "TASK-001", "--purpose", "implement",
                         "--expect-digest", initial["contextDigest"])
        self.assertEqual("blocked", stale["status"])
        self.assertIn("CTX-STALE-001", [d["code"] for d in stale["diagnostics"]])
        self.assertNotEqual(initial["contextDigest"], self.context()["contextDigest"])
        self.assertEqual(BROKEN_SOURCE, (self.workspace / "src/input.py").read_text())

    def test_source_content_requires_separate_review_even_if_digest_matches(self):
        self.prepare()
        initial = self.context()
        (self.workspace / "src/input.py").write_text(FIXED_SOURCE)
        current = self.cli("context", "TASK-001", "--purpose", "implement",
                           "--expect-digest", initial["contextDigest"])
        self.assertIn(current["status"], PASS_STATUSES)
        self.assertEqual(initial["contextDigest"], current["contextDigest"])
        self.assertIn(self.cli("check", "TASK-001", "--base", "HEAD")["status"], PASS_STATUSES)

    def test_unfinished_task_dependency_blocks_implementation(self):
        self.prepare()
        dependency = self.workspace / ".spec/tasks/TASK-002.md"
        dependency.write_text('---\nid: TASK-002\ntitle: 先行作業\nstatus: open\n'
                              'relations:\n  addresses: [REQ-001:AC-01]\nchanges: []\n---\n\n'
                              '# TASK-002 先行作業\n\n## Objective\n\n先行する作業。\n')
        task = self.workspace / ".spec/tasks/TASK-001.md"
        task.write_text(task.read_text().replace("relations:\n", "relations:\n  requires: [TASK-002]\n"))
        result = self.cli("context", "TASK-001", "--purpose", "implement")
        self.assertEqual("blocked", result["status"])
        self.assertIn("CTX-TASK-DEPENDENCY-001", [d["code"] for d in result["diagnostics"]])

    def test_verify_without_must_test_binding_is_blocked_without_commands(self):
        self.prepare(registered=False)
        self.context()
        result = self.cli("verify", "TASK-001")
        self.assertEqual("blocked", result["status"])
        self.assertEqual([], result["commands"])
        self.assertIn("CTX-COVERAGE-TEST-001", [d["code"] for target in result["targetResults"]
                                               for d in target["diagnostics"]])

    def test_real_test_failure_repair_and_handoff_keep_human_review_pending(self):
        self.prepare()
        initial = self.context()
        precheck = self.cli("check", "TASK-001", "--base", "HEAD")
        self.assertIn(precheck["status"], PASS_STATUSES)
        self.cli("context", "TASK-001", "--purpose", "implement",
                 "--expect-digest", initial["contextDigest"])
        # この固定テストは標準Pythonで指定srcを読みassertするだけ。通信・秘密・書込みなし。
        failed = self.cli("verify", "TASK-001")
        self.assertEqual("failed", failed["status"])
        self.assertTrue(failed["commands"])
        self.assertTrue(all(c["termination"] == "exit" and c["exitCode"] == 1
                            for c in failed["commands"]))
        (self.workspace / "src/input.py").write_text(FIXED_SOURCE)
        postcheck = self.cli("check", "TASK-001", "--base", "HEAD")
        self.assertIn(postcheck["status"], PASS_STATUSES)
        verified = self.cli("verify", "TASK-001")
        self.assertEqual("passed", verified["status"])
        self.assertTrue(all(c["argv"][:3] == [sys.executable, "-I", "-B"]
                            and c["exitCode"] == 0 for c in verified["commands"]))
        self.assertEqual(["REQ-001:AC-01"], verified["targetResults"][0]["statements"])
        self.assertTrue(verified["targetResults"][0]["bindingRefs"])
        # 検分対象を確定するための合成fixture専用コミット。TASKはopenのまま。
        self.fixture.commit_fixture()
        subject = self.fixture.git("rev-parse", "HEAD").stdout.strip()
        final_check = self.cli("check", "TASK-001")
        final_verify = self.cli("verify", "TASK-001")
        self.assertEqual("passed", final_verify["status"])
        self.assertEqual(subject, final_verify["revision"]["commit"])
        self.assertFalse(final_verify["revision"]["dirty"])
        self.assertIn("status: open", (self.workspace / ".spec/tasks/TASK-001.md").read_text())
        with tempfile.TemporaryDirectory(prefix="bitz-sdd-evidence-") as directory:
            evidence = []
            for identifier, result in (("check", final_check), ("verify", final_verify)):
                path = Path(directory) / (identifier + ".json")
                path.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True))
                evidence.append({"evidenceId": identifier, "kind": "core-result", "source": str(path),
                                 "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
            record = {"schemaVersion": "1.0", "subjectCommit": subject, "originIds": ["TASK-001"],
                      "changedPaths": ["src/input.py"],
                      "risk": {"band": "Q1", "dimensions": ["maintainability"],
                               "rationale": "合成入力関数内の可逆な変更"},
                      "requiredEvidence": evidence, "collectedEvidence": evidence,
                      "missingEvidence": [{"evidenceId": "human-review", "reason": "人手レビューは未実施"}],
                      "checks": [{"name": name, "command": ["bitz", operation, "TASK-001", "--format", "json"],
                                  "result": "passed"} for name, operation in (("post-check", "check"), ("verify", "verify"))]
                      + [{"name": "human-review", "command": None, "result": "not-run"}]}
            schema = json.loads((ROOT / "evals/skills/schemas/handoff.schema.json").read_text())
            validator = Draft202012Validator(schema)
            self.assertEqual([], list(validator.iter_errors(record)))
            for item in record["collectedEvidence"]:
                self.assertEqual(item["sha256"], hashlib.sha256(Path(item["source"]).read_bytes()).hexdigest())
            incomplete = dict(record)
            del incomplete["missingEvidence"]
            self.assertTrue(list(validator.iter_errors(incomplete)))


if __name__ == "__main__":
    unittest.main()
