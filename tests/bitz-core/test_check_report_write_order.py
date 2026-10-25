"""`check --report`の保存に失敗したときの`SPEC-REPORT-WRITE-001`の並びの単体試験（確認事項 C51）。

欠陥: `check`は、レポートの保存に失敗した診断を、並べ終えた`diagnostics`の末尾に足していた。そのため、発生元の`path`が
`.spec/reports`の診断が`.spec/technical/TECH-001.md`の診断より後に並び、結果・診断・終了コード §7の
「発生元のワークスペースID、`path`、`line`、`column`、`code`、`specRefs`の辞書順」と食い違った。`verify`は並べ直していた。

この試験の対象:
1. 単独の`check --report`で、保存の失敗の診断が§7の順に入る（`.spec/decisions` < `.spec/reports` < `.spec/technical`）。
   `check --all-workspaces --report`の最上位の診断でも、発生元のワークスペースIDの順に入る。
2. 保存の失敗の診断の内容（コード、状態、発生元）と、結果の`status`と終了コードは変わらない。
3. 対照: `verify --report`の並びは今までどおり。
4. 結果は`result.schema.json`に適合する。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from bitz import check as check_mod
from bitz import verify as verify_mod
from bitz.cliargs import parse_argv
from bitz.resultmodel import sort_diagnostics

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULT_SCHEMA = REPO_ROOT / "docs" / "03.詳細設計" / "schemas" / "result.schema.json"
BASE_REPO = REPO_ROOT / "fixtures" / "conformance" / "single" / "SINGLE-072" / "repo"
MULTI_REPO = REPO_ROOT / "fixtures" / "conformance" / "multi" / "MULTI-011" / "repo"

_GIT_ENV = {"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}

REPORT_WRITE = ("SPEC-REPORT-WRITE-001", ".spec/reports")
RELATION_MISSING_TECH = ("SPEC-RELATION-MISSING-001", ".spec/technical/TECH-001.md")
RELATION_MISSING_ADR = ("SPEC-RELATION-MISSING-001", ".spec/decisions/ADR-002.md")

ADR_002 = (
    "---\nid: ADR-002\ntitle: 追加の判断\nstatus: accepted\nrelations:\n  requires: [TECH-998]\n---\n\n"
    "# ADR-002 追加の判断\n\n## Context\n\n判断の背景。\n\n## Decision\n\n採用する。\n"
)


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args], cwd=root, env={**os.environ, **_GIT_ENV}, check=True, capture_output=True, text=True
    )


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


class CheckReportWriteOrderTests(unittest.TestCase):
    """`.spec/reports`を通常のファイルにして、レポートの保存を失敗させる（SINGLE-072の入力を使う）。"""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / "repo"
        shutil.copytree(BASE_REPO, self.root)
        self.assertTrue((self.root / ".spec" / "reports").is_file())
        self.results: list[dict] = []

    def tearDown(self):
        if self.results:
            _validate_against_schema(self.results)

    def commit(self):
        _git(self.root, "init", "-q", "--initial-branch=main")
        _git(self.root, "add", ".")
        _git(self.root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "base")

    def run_op(self, module, argv: list[str]):
        parsed = parse_argv([*argv, "--format", "json"])
        result, code = module.run(parsed, str(self.root), dict(os.environ))
        self.results.append(result)
        return result, code

    @staticmethod
    def keys(result):
        return [(d["code"], d["source"].get("path")) for d in result["diagnostics"]]

    def test_report_write_failure_is_sorted_by_path(self):
        self.commit()
        result, code = self.run_op(check_mod, ["check", "--full", "--base", "HEAD", "--report"])
        self.assertEqual(self.keys(result), [REPORT_WRITE, RELATION_MISSING_TECH])
        self.assertEqual(result["diagnostics"], sort_diagnostics(result["diagnostics"]))
        self.assertEqual((result["status"], code), ("error", 3))
        failure = result["diagnostics"][0]
        self.assertEqual(
            (failure["severity"], failure["resultStatus"], failure["source"]),
            ("error", "error", {"kind": "file", "workspaceId": "root", "path": ".spec/reports"}),
        )

    def test_report_write_failure_is_placed_between_earlier_and_later_paths(self):
        (self.root / ".spec" / "decisions" / "ADR-002.md").write_text(ADR_002, encoding="utf-8")
        self.commit()
        result, _ = self.run_op(check_mod, ["check", "--full", "--base", "HEAD", "--report"])
        self.assertEqual(self.keys(result), [RELATION_MISSING_ADR, REPORT_WRITE, RELATION_MISSING_TECH])

    def test_without_report_the_order_is_unchanged(self):
        self.commit()
        result, code = self.run_op(check_mod, ["check", "--full", "--base", "HEAD"])
        self.assertEqual(self.keys(result), [RELATION_MISSING_TECH])
        self.assertEqual((result["status"], code), ("failed", 1))

    def test_verify_report_write_failure_keeps_its_sorted_order(self):
        (self.root / ".spec" / "decisions" / "ADR-002.md").write_text(ADR_002, encoding="utf-8")
        self.commit()
        result, _ = self.run_op(verify_mod, ["verify", "--report"])
        self.assertIn(REPORT_WRITE, self.keys(result))
        self.assertEqual(result["diagnostics"], sort_diagnostics(result["diagnostics"]))


class AllWorkspacesReportWriteOrderTests(unittest.TestCase):
    """MULTI-011の入力に、基準版だけにあるメンバーを足して作業ツリーで消し、最上位に削除の診断を置く。"""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / "repo"
        shutil.copytree(MULTI_REPO, self.root)
        self.results: list[dict] = []

    def tearDown(self):
        if self.results:
            _validate_against_schema(self.results)

    def prepare(self, removed_id: str, block_reports: bool) -> None:
        cfg = self.root / ".spec" / "bitz.yaml"
        base_cfg = cfg.read_text(encoding="utf-8")
        cfg.write_text(base_cfg + f"    - id: {removed_id}\n      path: services/{removed_id}\n", encoding="utf-8")
        member = self.root / "services" / removed_id / ".spec"
        (member / "requirements").mkdir(parents=True)
        (member / "bitz.yaml").write_text(
            f'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\nworkspace:\n  id: {removed_id}\n', encoding="utf-8"
        )
        req = (self.root / ".spec" / "requirements" / "REQ-001.md").read_text(encoding="utf-8")
        (member / "requirements" / "REQ-900.md").write_text(req.replace("REQ-001", "REQ-900"), encoding="utf-8")
        _git(self.root, "init", "-q", "--initial-branch=main")
        _git(self.root, "add", ".")
        _git(self.root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "base")
        cfg.write_text(base_cfg, encoding="utf-8")
        shutil.rmtree(self.root / "services" / removed_id)
        if block_reports:
            (self.root / ".spec" / "reports").write_text("block\n", encoding="utf-8")

    def run_check(self):
        parsed = parse_argv(["check", "--all-workspaces", "--base", "HEAD", "--report", "--format", "json"])
        result, code = check_mod.run(parsed, str(self.root), dict(os.environ))
        self.results.append(result)
        return result, code

    @staticmethod
    def top(result):
        return [(d["code"], d["source"].get("workspaceId")) for d in result["diagnostics"]]

    def test_report_write_failure_is_sorted_by_workspace_id(self):
        # `platform`（保存先のルート）は削除した`zz`より前に並ぶ。
        self.prepare("zz", block_reports=True)
        result, code = self.run_check()
        self.assertEqual(
            self.top(result), [("SPEC-REPORT-WRITE-001", "platform"), ("SPEC-STATE-TRANSITION-001", "zz")]
        )
        self.assertEqual(result["diagnostics"], sort_diagnostics(result["diagnostics"]))
        self.assertEqual((result["status"], code), ("error", 3))

    def test_report_write_failure_after_an_earlier_workspace_id(self):
        self.prepare("aa", block_reports=True)
        result, _ = self.run_check()
        self.assertEqual(
            self.top(result), [("SPEC-STATE-TRANSITION-001", "aa"), ("SPEC-REPORT-WRITE-001", "platform")]
        )

    def test_without_write_failure_the_status_is_unchanged(self):
        self.prepare("zz", block_reports=False)
        result, code = self.run_check()
        self.assertEqual(self.top(result), [("SPEC-STATE-TRANSITION-001", "zz")])
        self.assertEqual((result["status"], code), ("failed", 1))


if __name__ == "__main__":
    unittest.main()
