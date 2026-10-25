"""`--all-workspaces`の早期の結果が`--report`を保存することの単体試験（確認事項 C53）。

欠陥: `check --all-workspaces`と`verify --all-workspaces`は、全体事前検査で止まったとき、`verify`は実行計画の上限を超えたときも、
結果をそのまま返し、`--report`を指定しても`.spec/reports/`へ保存しなかった。

規範:
- 結果・診断・終了コード §8: `check`と`verify`は、状態にかかわらず、`--report`が指定された場合だけ結果のJSONを保存する。
  全体レポートはルートワークスペースの`.spec/reports/`へ保存する。保存の失敗は`SPEC-REPORT-WRITE-001`（`error`）とし、元の結果と診断は端末に保持する。
- 同 §5: ルートの同一性を構成できない診断の`source.workspaceId`は`null`。

この試験の対象:
1. `check`・`verify`の全体事前検査の停止と、`verify`の上限超過で、ルートの`.spec/reports/`に1件だけ保存し、内容は端末の結果と同じ。
2. 保存の失敗は`SPEC-REPORT-WRITE-001`を§7の順に加え、状態は`error`、終了コードは3。
3. ルートの同一性が確定しない停止（ルートの`workspace.id`の省略）でも保存し、保存の失敗の`source.workspaceId`は`null`。
4. 対照: `--report`がなければ何も作らない。メンバーの`.spec/reports/`には保存しない。
5. 結果は`result.schema.json`に適合する。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from bitz import check as check_mod
from bitz import multiws
from bitz import verify as verify_mod
from bitz.cliargs import parse_argv
from bitz.resultmodel import sort_diagnostics

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULT_SCHEMA = REPO_ROOT / "docs" / "03.詳細設計" / "schemas" / "result.schema.json"

CONFIG = 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\n'
VERIFY = 'verify:\n  commands:\n    t:\n      argv: ["/bin/true", "{tests}"]\n      cwd: .\n'
MEMBERS = "multiWorkspace:\n  members:\n    - id: web\n      path: apps/web\n"
ROOT_YAML = CONFIG + "workspace:\n  id: platform\n" + MEMBERS + VERIFY
WEB_YAML = CONFIG + "workspace:\n  id: web\n" + VERIFY
REQ = (
    "---\nid: REQ-001\ntitle: REQ\nstatus: approved\ntests:\n  - path: tests/t.py\n    covers: [REQ-001:AC-01]\n    command: t\n---\n\n"
    "# REQ-001 REQ\n\n## Intent\n\n意図。\n\n## Acceptance Criteria\n\n"
    "- [REQ-001:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 秘密情報を出力しない。\n\n## Verification\n\n未証明。\n"
)

_GIT_ENV = {"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args], cwd=root, env={**os.environ, **_GIT_ENV}, check=True, capture_output=True, text=True
    )


def _write(root: Path, rel: str, content: str) -> None:
    full = root / rel
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")


def _validate_against_schema(results: list[dict]) -> None:
    uv = shutil.which("uv")
    if uv is None:
        raise unittest.SkipTest("uvがないためスキーマ適合を確認できません")
    script = (
        "import json, sys\n"
        "from jsonschema import Draft202012Validator\n"
        "schema = json.load(open(sys.argv[1], encoding='utf-8'))\n"
        "validator = Draft202012Validator(schema)\n"
        "for index, result in enumerate(json.load(sys.stdin)):\n"
        "    errors = sorted(validator.iter_errors(result), key=lambda e: list(e.path))\n"
        "    if errors:\n"
        "        print(index, errors[0].message, list(errors[0].path))\n"
        "        sys.exit(1)\n"
    )
    proc = subprocess.run(
        [uv, "run", "--no-project", "--with", "jsonschema==4.23.0", "python", "-c", script, str(RESULT_SCHEMA)],
        input=json.dumps(results),
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise AssertionError(f"スキーマに適合しません: {proc.stdout}{proc.stderr}")


class _Base(unittest.TestCase):
    root_yaml = ROOT_YAML

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        _write(self.root, ".spec/bitz.yaml", self.root_yaml)
        _write(self.root, "apps/web/.spec/bitz.yaml", WEB_YAML)
        _write(self.root, ".spec/requirements/REQ-001.md", REQ)
        _write(self.root, "tests/t.py", "def test_t():\n    assert True\n")
        self.results: list[dict] = []

    def tearDown(self):
        if self.results:
            _validate_against_schema(self.results)

    def commit(self):
        _git(self.root, "init", "-q", "--initial-branch=main")
        _git(self.root, "add", ".")
        _git(self.root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "base")

    def run_op(self, module, name: str, *flags: str):
        parsed = parse_argv([name, "--all-workspaces", *flags, "--format", "json"])
        result, code = module.run(parsed, str(self.root), dict(os.environ))
        self.results.append(result)
        return result, code

    def reports(self, base: Path | None = None) -> list[Path]:
        directory = (base or self.root) / ".spec" / "reports"
        return sorted(directory.iterdir()) if directory.is_dir() else []

    def assert_saved_once(self, result, operation: str):
        reports = self.reports()
        self.assertEqual(len(reports), 1, reports)
        self.assertRegex(reports[0].name, rf"^\d{{8}}T\d{{6}}Z-{operation}(-\d+)?\.json$")
        self.assertEqual(json.loads(reports[0].read_text(encoding="utf-8")), result)
        self.assertEqual(self.reports(self.root / "apps" / "web"), [])


class PrecheckStopReportTests(_Base):
    """メンバーの設定を消して、全体事前検査を`SPEC-MULTI-MEMBER-001`で止める。"""

    def setUp(self):
        super().setUp()
        self.commit()
        (self.root / "apps" / "web" / ".spec" / "bitz.yaml").unlink()

    def test_check_saves_the_stopped_result(self):
        result, code = self.run_op(check_mod, "check", "--report")
        self.assertEqual((result["status"], code), ("failed", 1), result["diagnostics"])
        self.assertEqual([d["code"] for d in result["diagnostics"]], ["SPEC-MULTI-MEMBER-001"])
        self.assert_saved_once(result, "check")

    def test_verify_saves_the_stopped_result(self):
        result, code = self.run_op(verify_mod, "verify", "--report")
        self.assertEqual((result["status"], code), ("failed", 1), result["diagnostics"])
        self.assert_saved_once(result, "verify")

    def test_without_report_nothing_is_written(self):
        for module, name in ((check_mod, "check"), (verify_mod, "verify")):
            result, code = self.run_op(module, name)
            self.assertEqual(code, 1, result["diagnostics"])
        self.assertFalse((self.root / ".spec" / "reports").exists())

    def test_write_failure_is_added_in_section7_order(self):
        _write(self.root, ".spec/reports", "block\n")
        for module, name in ((check_mod, "check"), (verify_mod, "verify")):
            result, code = self.run_op(module, name, "--report")
            self.assertEqual((result["status"], code), ("error", 3), result["diagnostics"])
            self.assertEqual(
                [(d["code"], d["source"].get("path")) for d in result["diagnostics"]],
                [("SPEC-MULTI-MEMBER-001", ".spec/bitz.yaml"), ("SPEC-REPORT-WRITE-001", ".spec/reports")],
            )
            self.assertEqual(result["diagnostics"], sort_diagnostics(result["diagnostics"]))
            failure = result["diagnostics"][1]
            self.assertEqual(failure["source"]["workspaceId"], "platform")


class VerifyPlanLimitReportTests(_Base):
    def setUp(self):
        super().setUp()
        self.commit()

    def test_plan_limit_result_is_saved(self):
        with mock.patch.dict(multiws.HARD_LIMITS, {"commandDefinitionCount": 1}):
            result, code = self.run_op(verify_mod, "verify", "--report")
        self.assertEqual((result["status"], code), ("blocked", 2), result["diagnostics"])
        self.assertEqual([d["code"] for d in result["diagnostics"]], ["SPEC-MULTI-LIMIT-001"])
        self.assert_saved_once(result, "verify")

    def test_plan_limit_without_report_writes_nothing(self):
        with mock.patch.dict(multiws.HARD_LIMITS, {"commandDefinitionCount": 1}):
            result, code = self.run_op(verify_mod, "verify")
        self.assertEqual(code, 2, result["diagnostics"])
        self.assertFalse((self.root / ".spec" / "reports").exists())


class RootIdentityUnknownReportTests(_Base):
    """ルートの`workspace.id`の省略で、ルートの同一性を構成せずに止める（C42）。"""

    root_yaml = CONFIG + MEMBERS + VERIFY

    def setUp(self):
        super().setUp()
        self.commit()

    def test_stopped_result_with_null_identity_is_saved_to_the_root(self):
        for module, name in ((check_mod, "check"), (verify_mod, "verify")):
            result, code = self.run_op(module, name, "--report")
            self.assertEqual((result["status"], code), ("failed", 1), result["diagnostics"])
            self.assertEqual(result["multiWorkspace"], {"id": None, "path": "."})
        self.assertEqual(
            sorted(p.name.split("-", 1)[1] for p in self.reports()), ["check.json", "verify.json"]
        )

    def test_write_failure_has_null_workspace_id(self):
        _write(self.root, ".spec/reports", "block\n")
        result, code = self.run_op(check_mod, "check", "--report")
        self.assertEqual((result["status"], code), ("error", 3), result["diagnostics"])
        failure = [d for d in result["diagnostics"] if d["code"] == "SPEC-REPORT-WRITE-001"]
        self.assertEqual(
            [d["source"] for d in failure], [{"kind": "file", "workspaceId": None, "path": ".spec/reports"}]
        )


if __name__ == "__main__":
    unittest.main()
