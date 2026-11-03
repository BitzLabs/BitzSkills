"""複合ワークスペースの`SPEC-IMPACT-OUTDATED-001`と`SPEC-ID-DUPLICATE-001`の単体試験（確認事項 C69・C80）。

欠陥（C69）: 複合ワークスペース内の`check`は、影響の候補（`SPEC-IMPACT-OUTDATED-001`）と文書IDの重複（`SPEC-ID-DUPLICATE-001`）の
`summary`に、作業ワークスペースの文書IDを修飾せずに差し込んでいた。ほかの診断（C47）は修飾していた。
欠陥（C80）: `check --all-workspaces`のメンバーの影響の候補は、自ワークスペースを修飾した参照（`refines: [web::REQ-001:AC-01]`）を
変更された文書へ照合せず、見落としていた。単独の操作は照合していた。

規範:
- 複合ワークスペース仕様 §4: 複合ワークスペース内で実行したCore操作は、文書IDと規範文IDを修飾IDで返す。自ワークスペースを自身のIDで
  修飾した参照は、非修飾形式と同じ文書を指す。
- `check` §8: 変更があったREQまたはTECHへ強く依存する`approved`の文書を警告する。

この試験の対象:
1. 全体操作と単独の操作の両方で、2つの診断の`summary`が作業ワークスペースのIDで修飾される。
2. 全体操作でも、自ワークスペースを修飾した参照の依存元を警告する。
3. 単一ワークスペースの`summary`は修飾しない。
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
from bitz.cliargs import parse_argv

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULT_SCHEMA = REPO_ROOT / "docs" / "03.詳細設計" / "schemas" / "result.schema.json"

CONFIG = 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\n'
_GIT_ENV = {"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args], cwd=root, env={**os.environ, **_GIT_ENV}, check=True, capture_output=True, text=True
    )


def _write(root: Path, rel: str, content: str) -> None:
    full = root / rel
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")


def _statement(stmt_id: str) -> str:
    return f"- [{stmt_id}] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] {stmt_id}を守る。\n"


def _req(doc_id: str, *, status: str = "approved", intent: str = "意図。") -> str:
    return (
        f"---\nid: {doc_id}\ntitle: {doc_id}の文書\nstatus: {status}\n---\n\n"
        f"# {doc_id} {doc_id}の文書\n\n## Intent\n\n{intent}\n\n## Acceptance Criteria\n\n{_statement(f'{doc_id}:AC-01')}\n"
        "## Verification\n\n未証明。\n"
    )


def _tech(doc_id: str, refines: str) -> str:
    return (
        f"---\nid: {doc_id}\ntitle: {doc_id}の文書\nstatus: approved\nrelations:\n  refines: [{refines}]\n---\n\n"
        f"# {doc_id} {doc_id}の文書\n\n## Context\n\n本文。\n\n## Constraints\n\n{_statement(f'{doc_id}:C-01')}"
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


class _Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.results: list[dict] = []

    def tearDown(self):
        if self.results:
            _validate_against_schema(self.results)

    def commit(self, message: str = "base"):
        if not (self.root / ".git").exists():
            _git(self.root, "init", "-q", "--initial-branch=main")
        _git(self.root, "add", ".")
        _git(self.root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", message)

    def check(self, *argv: str):
        parsed = parse_argv(["check", *argv, "--format", "json"])
        result, code = check_mod.run(parsed, str(self.root), dict(os.environ))
        self.results.append(result)
        return result, code

    @staticmethod
    def summaries(result, code: str) -> list[str]:
        diags = list(result["diagnostics"])
        for ws in result.get("workspaces", []):
            diags.extend(ws["diagnostics"])
        return sorted(d["summary"] for d in diags if d["code"] == code)


class MultiWorkspaceTests(_Base):
    def setUp(self):
        super().setUp()
        _write(
            self.root, ".spec/bitz.yaml",
            CONFIG + "workspace:\n  id: platform\nmultiWorkspace:\n  members:\n    - id: web\n      path: apps/web\n",
        )
        _write(self.root, "apps/web/.spec/bitz.yaml", CONFIG + "workspace:\n  id: web\n")
        _write(self.root, "apps/web/.spec/requirements/REQ-001.md", _req("REQ-001", status="draft"))
        _write(self.root, "apps/web/.spec/technical/TECH-010.md", _tech("TECH-010", "web::REQ-001:AC-01"))
        _write(self.root, "apps/web/.spec/technical/TECH-011.md", _tech("TECH-011", "REQ-001:AC-01"))
        self.commit()
        _write(self.root, "apps/web/.spec/requirements/REQ-001.md", _req("REQ-001", status="draft", intent="変更した意図。"))

    IMPACT = [
        "web::TECH-010が強く依存するweb::REQ-001が変更されています。再確認してください",
        "web::TECH-011が強く依存するweb::REQ-001が変更されています。再確認してください",
    ]

    def test_impact_summaries_are_qualified_and_self_qualified_references_are_matched(self):
        for argv in (("--all-workspaces", "--base", "HEAD"), ("--workspace", "web", "--full", "--base", "HEAD")):
            with self.subTest(argv=argv):
                result, code = self.check(*argv)
                self.assertEqual((result["status"], code), ("passed_with_warnings", 0), result)
                self.assertEqual(self.summaries(result, "SPEC-IMPACT-OUTDATED-001"), self.IMPACT)

    def test_duplicate_id_summary_is_qualified(self):
        _write(self.root, "apps/web/.spec/requirements/REQ-003-a.md", _req("REQ-003"))
        _write(self.root, "apps/web/.spec/requirements/REQ-003-b.md", _req("REQ-003"))
        for argv in (("--all-workspaces",), ("--workspace", "web", "--full")):
            with self.subTest(argv=argv):
                result, code = self.check(*argv)
                self.assertEqual((result["status"], code), ("failed", 1), result)
                self.assertEqual(self.summaries(result, "SPEC-ID-DUPLICATE-001"), ["文書ID web::REQ-003が重複しています"])


class SingleWorkspaceTests(_Base):
    def test_single_workspace_summaries_are_not_qualified(self):
        _write(self.root, ".spec/bitz.yaml", CONFIG)
        _write(self.root, ".spec/requirements/REQ-001.md", _req("REQ-001", status="draft"))
        _write(self.root, ".spec/technical/TECH-010.md", _tech("TECH-010", "REQ-001:AC-01"))
        self.commit()
        _write(self.root, ".spec/requirements/REQ-001.md", _req("REQ-001", status="draft", intent="変更した意図。"))
        _write(self.root, ".spec/requirements/REQ-003-a.md", _req("REQ-003"))
        _write(self.root, ".spec/requirements/REQ-003-b.md", _req("REQ-003"))
        result, _code = self.check("--full", "--base", "HEAD")
        self.assertEqual(
            self.summaries(result, "SPEC-IMPACT-OUTDATED-001"),
            ["TECH-010が強く依存するREQ-001が変更されています。再確認してください"],
        )
        self.assertEqual(self.summaries(result, "SPEC-ID-DUPLICATE-001"), ["文書ID REQ-003が重複しています"])


if __name__ == "__main__":
    unittest.main()
