"""文書IDで`refines`する具体化文書の規範文を対象規範文に含めることの単体試験（確認事項 C54）。

欠陥: 文書を起点にした対象展開（関係・トレースモデル §6.4の規則1）は、起点の規範文を規範文IDで`refines`する文書の規範文だけを
対象規範文に含め、起点の文書を文書IDで`refines`する文書の規範文を含めていなかった。その文書は閉包に入り本文も提示されるのに、
制約台帳とカバレッジには入らず、`verify`はその文書の未テストの`MUST`を通していた。

規範:
- 用語集・関係・トレースモデル §6.4: 具体化文書は、選択した文書または規範文を`refines`する適用可能な文書で、推移的な具体化を終端まで辿る。
- §6.4の規則1: 起点の文書を文書IDで`refines`する適用可能な文書も具体化文書であり、その規範文を含める。
- §6.4の規則2: 規範文を起点にした場合は、指定した規範文の具体化文書だけを含める（文書IDで`refines`する文書は含めない）。

この試験の対象:
1. 文書IDで`refines`するTECHの規範文が、目的`implement`の制約台帳と`verify`の対象規範文に入り、未テストなら`verify`は`blocked`。
2. 推移的な具体化（文書IDの`refines`の先をさらに文書IDまたは規範文IDで`refines`する文書）も含める。
3. 適用できない文書（目的`verify`の`draft`）は含めない。
4. 規範文を起点にした場合は、文書IDで`refines`する文書の規範文を含めない。
5. 複合ワークスペースで、他のワークスペースの文書が起点の文書を修飾した文書IDで`refines`する場合も含める。
6. 結果は`result.schema.json`に適合する。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from bitz import context as context_mod
from bitz import verify as verify_mod
from bitz.cliargs import parse_argv

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULT_SCHEMA = REPO_ROOT / "docs" / "03.詳細設計" / "schemas" / "result.schema.json"

CONFIG = 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\n'
VERIFY = 'verify:\n  commands:\n    t:\n      argv: ["/bin/true", "{tests}"]\n'
_GIT_ENV = {"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}
_OPERATIONS = {"context": context_mod, "verify": verify_mod}


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


def _req(doc_id: str) -> str:
    return (
        f"---\nid: {doc_id}\ntitle: {doc_id}の文書\nstatus: approved\n"
        f"tests:\n  - path: tests/t.py\n    covers: [{doc_id}:AC-01]\n    command: t\n---\n\n"
        f"# {doc_id} {doc_id}の文書\n\n## Intent\n\n意図。\n\n## Acceptance Criteria\n\n{_statement(f'{doc_id}:AC-01')}\n"
        "## Verification\n\n未証明。\n"
    )


def _tech(doc_id: str, refines: str, *, status: str = "approved") -> str:
    return (
        f"---\nid: {doc_id}\ntitle: {doc_id}の文書\nstatus: {status}\nrelations:\n  refines: [{refines}]\n---\n\n"
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

    def commit(self):
        _git(self.root, "init", "-q", "--initial-branch=main")
        _git(self.root, "add", ".")
        _git(self.root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "base")

    def run_op(self, op: str, *argv: str):
        parsed = parse_argv([op, *argv, "--format", "json"])
        result, code = _OPERATIONS[op].run(parsed, str(self.root), dict(os.environ))
        self.results.append(result)
        return result, code

    def ledger(self, root: str) -> list[str]:
        result, _code = self.run_op("context", root, "--purpose", "implement")
        return [s["id"] for s in result["constraintLedger"]["statements"]]

    def verify_target(self, root: str):
        result, code = self.run_op("verify", root)
        (target,) = result["targetResults"]
        return result, code, target


class SingleWorkspaceTests(_Base):
    def write(self, *techs: tuple[str, str, str]):
        _write(self.root, ".spec/bitz.yaml", CONFIG + VERIFY)
        _write(self.root, "tests/t.py", "def test_t():\n    assert True\n")
        _write(self.root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
        for doc_id, refines, status in techs:
            _write(self.root, f".spec/technical/{doc_id}.md", _tech(doc_id, refines, status=status))
        self.commit()

    def test_document_id_refinement_statements_are_targets(self):
        self.write(("TECH-001", "REQ-001", "approved"))
        self.assertEqual(self.ledger("REQ-001"), ["REQ-001:AC-01", "TECH-001:C-01"])
        result, code, target = self.verify_target("REQ-001")
        self.assertEqual((result["status"], code), ("blocked", 2), result)
        self.assertEqual(target["statements"], ["REQ-001:AC-01", "TECH-001:C-01"])
        self.assertEqual([d["code"] for d in target["diagnostics"]], ["CTX-COVERAGE-TEST-001"])

    def test_transitive_refinements_are_targets(self):
        self.write(
            ("TECH-001", "REQ-001", "approved"),
            ("TECH-002", "TECH-001", "approved"),
            ("TECH-003", "TECH-002:C-01", "approved"),
        )
        _result, _code, target = self.verify_target("REQ-001")
        self.assertEqual(target["statements"], ["REQ-001:AC-01", "TECH-001:C-01", "TECH-002:C-01", "TECH-003:C-01"])

    def test_inapplicable_document_is_not_a_refinement(self):
        self.write(("TECH-001", "REQ-001", "draft"))
        result, code, target = self.verify_target("REQ-001")
        self.assertEqual((result["status"], code), ("passed", 0), result)
        self.assertEqual(target["statements"], ["REQ-001:AC-01"])

    def test_document_id_refinement_of_a_statement_refinement_is_a_target(self):
        """規範文IDで見つけた具体化文書を、さらに文書IDで`refines`する文書も辿る（文書の起点）。"""

        self.write(("TECH-002", "REQ-001:AC-01", "approved"), ("TECH-003", "TECH-002", "approved"))
        _result, _code, target = self.verify_target("REQ-001")
        self.assertEqual(target["statements"], ["REQ-001:AC-01", "TECH-002:C-01", "TECH-003:C-01"])

    def test_statement_origin_follows_document_id_refinements_of_found_documents(self):
        """規範文の起点でも、見つけた具体化文書の先は文書IDの`refines`も辿る。起点の所有文書の文書IDの`refines`は辿らない。"""

        self.write(
            ("TECH-001", "REQ-001", "approved"),
            ("TECH-002", "REQ-001:AC-01", "approved"),
            ("TECH-003", "TECH-002", "approved"),
        )
        _result, _code, target = self.verify_target("REQ-001:AC-01")
        self.assertEqual(target["statements"], ["REQ-001:AC-01", "TECH-002:C-01", "TECH-003:C-01"])

    def test_task_origin_follows_document_id_refinements_of_found_documents(self):
        self.write(("TECH-002", "REQ-001:AC-01", "approved"), ("TECH-003", "TECH-002", "approved"))
        _write(
            self.root, ".spec/tasks/TASK-001.md",
            "---\nid: TASK-001\ntitle: TASK-001の作業\nstatus: open\nrelations:\n  addresses: [REQ-001:AC-01]\nchanges: []\n---\n\n"
            "# TASK-001 TASK-001の作業\n\n## Goal\n\n目的。\n",
        )
        _git(self.root, "add", ".")
        _git(self.root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "task")
        _result, _code, target = self.verify_target("TASK-001")
        self.assertEqual(target["statements"], ["REQ-001:AC-01", "TECH-002:C-01", "TECH-003:C-01"])

    def test_statementless_tech_is_not_a_document_refinement_origin(self):
        """規則3・5: `addresses`または起点にした規範文のないTECHは、文書IDの`refines`を辿る起点にしない。"""

        _write(self.root, ".spec/bitz.yaml", CONFIG + VERIFY)
        _write(self.root, "tests/t.py", "def test_t():\n    assert True\n")
        _write(
            self.root, ".spec/technical/TECH-001.md",
            "---\nid: TECH-001\ntitle: TECH-001の文書\nstatus: approved\n"
            "tests:\n  - path: tests/t.py\n    covers: [TECH-001]\n    command: t\n---\n\n"
            "# TECH-001 TECH-001の文書\n\n## Context\n\n本文。\n",
        )
        _write(self.root, ".spec/technical/TECH-002.md", _tech("TECH-002", "TECH-001"))
        _write(
            self.root, ".spec/tasks/TASK-001.md",
            "---\nid: TASK-001\ntitle: TASK-001の作業\nstatus: open\nrelations:\n  addresses: [TECH-001]\nchanges: []\n---\n\n"
            "# TASK-001 TASK-001の作業\n\n## Goal\n\n目的。\n",
        )
        self.commit()
        for root in ("TECH-001", "TASK-001"):
            with self.subTest(root=root):
                result, code, target = self.verify_target(root)
                self.assertEqual((result["status"], code), ("passed", 0), result)
                self.assertEqual(target["statements"], [])

    def test_statement_origin_does_not_include_document_id_refinements(self):
        self.write(("TECH-001", "REQ-001", "approved"))
        self.assertEqual(self.ledger("REQ-001:AC-01"), ["REQ-001:AC-01"])
        result, code, target = self.verify_target("REQ-001:AC-01")
        self.assertEqual((result["status"], code), ("passed", 0), result)
        self.assertEqual(target["statements"], ["REQ-001:AC-01"])


class MultiWorkspaceTests(_Base):
    def test_other_workspace_document_id_refinement_is_a_target(self):
        _write(
            self.root, ".spec/bitz.yaml",
            CONFIG + "workspace:\n  id: platform\nmultiWorkspace:\n  members:\n    - id: web\n      path: apps/web\n" + VERIFY,
        )
        _write(self.root, "apps/web/.spec/bitz.yaml", CONFIG + "workspace:\n  id: web\n" + VERIFY)
        for base in ("", "apps/web/"):
            _write(self.root, f"{base}tests/t.py", "def test_t():\n    assert True\n")
        _write(self.root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
        _write(self.root, "apps/web/.spec/technical/TECH-010.md", _tech("TECH-010", "platform::REQ-001"))
        self.commit()
        result, code, target = self.verify_target("platform::REQ-001")
        self.assertEqual((result["status"], code), ("blocked", 2), result)
        self.assertEqual(target["statements"], ["platform::REQ-001:AC-01", "web::TECH-010:C-01"])


if __name__ == "__main__":
    unittest.main()
