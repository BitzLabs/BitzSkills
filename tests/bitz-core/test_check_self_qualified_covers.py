"""複合ワークスペースの`check`が、自ワークスペースを自身のIDで修飾した`tests[].covers`を非修飾形式と同じに扱うことの単体試験（確認事項 C56）。

欠陥: `check`の`tests[].covers`の検査（`multirelate.coverage_diagnostics`）は、許可集合の自ワークスペースの分を非修飾の形だけで作り、
宣言の参照を修飾のまま比べていた。そのため、`web`の文書の`covers: [web::REQ-001:AC-01]`を`SPEC-TEST-COVERAGE-001`で拒否し、
`refines`と`covers`の書き方（修飾の有無、文書IDか規範文IDか）の組合せによって、同じ対象が通ったり拒否されたりした。
`context`と`verify`は同じ入力を通していた。

規範:
- 複合ワークスペース仕様 §4: `relations`と`tests[].covers`は、同じワークスペースを自身のIDで修飾した参照も許可し、非修飾形式と同じ文書または規範文を指すものとして扱う。
  診断の`evidence`は宣言どおりの表記を保つ。
- 文書・フロントマター・状態仕様と関係・トレースモデル §9: `covers`は、自身の規範文、規範文を持たない場合の自身の文書ID、`refines`で直接参照する文書の規範文または規範文そのもの。

この試験の対象:
1. 自ワークスペースの修飾の`covers`を、`check`の全体操作・単独操作・明示した対象のすべてで通す。修飾の有無で`check`の出力は同じ。
2. `refines`と`covers`の書き方の組合せのすべてで、同じ対象を通す。
3. 対照: 存在しない規範文、`refines`していない規範文、他のワークスペースの不在の規範文と、実在するが`refines`していない他のワークスペースの規範文は、
   修飾の有無によらず拒否し、`evidence`は宣言どおり。
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
VERIFY = 'verify:\n  commands:\n    t:\n      argv: ["/bin/true", "{tests}"]\n      cwd: .\n'
ROOT_YAML = (
    CONFIG + "workspace:\n  id: platform\nmultiWorkspace:\n  members:\n    - id: web\n      path: apps/web\n"
    + "    - id: api\n      path: services/api\n" + VERIFY
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


def _statement(stmt_id: str) -> str:
    return f"- [{stmt_id}] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] {stmt_id}を守る。\n"


def _req(doc_id: str, covers: list[str]) -> str:
    return (
        f"---\nid: {doc_id}\ntitle: {doc_id}の文書\nstatus: approved\n"
        f"tests:\n  - path: tests/t.py\n    covers: [{', '.join(covers)}]\n    command: t\n---\n\n"
        f"# {doc_id} {doc_id}の文書\n\n## Intent\n\n意図。\n\n## Acceptance Criteria\n\n{_statement(f'{doc_id}:AC-01')}\n"
        "## Verification\n\n未証明。\n"
    )


def _tech(doc_id: str, refines: str | None, covers: list[str], *, with_statement: bool = True) -> str:
    relations = f"relations:\n  refines: [{refines}]\n" if refines else ""
    body = f"## Constraints\n\n{_statement(f'{doc_id}:C-01')}" if with_statement else ""
    return (
        f"---\nid: {doc_id}\ntitle: {doc_id}の文書\nstatus: approved\n{relations}"
        f"tests:\n  - path: tests/t.py\n    covers: [{', '.join(covers)}]\n    command: t\n---\n\n"
        f"# {doc_id} {doc_id}の文書\n\n## Context\n\n本文。\n\n{body}"
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
        self.web = self.root / "apps" / "web"
        _write(self.root, ".spec/bitz.yaml", ROOT_YAML)
        _write(self.root, "apps/web/.spec/bitz.yaml", CONFIG + "workspace:\n  id: web\n" + VERIFY)
        _write(self.root, "services/api/.spec/bitz.yaml", CONFIG + "workspace:\n  id: api\n" + VERIFY)
        for base in ("", "apps/web/", "services/api/"):
            _write(self.root, f"{base}tests/t.py", "def test_t():\n    assert True\n")
        _write(self.root, "services/api/.spec/requirements/REQ-001.md", _req("REQ-001", ["REQ-001:AC-01"]))
        self.results: list[dict] = []

    def tearDown(self):
        if self.results:
            _validate_against_schema(self.results)

    def commit(self):
        _git(self.root, "init", "-q", "--initial-branch=main")
        _git(self.root, "add", ".")
        _git(self.root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "base")

    def check(self, cwd: Path, *argv: str):
        parsed = parse_argv(["check", *argv, "--format", "json"])
        result, code = check_mod.run(parsed, str(cwd), dict(os.environ))
        self.results.append(result)
        return result, code

    @staticmethod
    def coverage(result) -> list[tuple[str, str]]:
        diags = list(result["diagnostics"])
        for ws in result.get("workspaces", []):
            diags.extend(ws["diagnostics"])
        return sorted(
            (d["source"]["path"], d["evidence"]) for d in diags if d["code"] == "SPEC-TEST-COVERAGE-001"
        )


class SelfQualifiedCoversTests(_Base):
    def write_web(self, qualified: bool):
        prefix = "web::" if qualified else ""
        _write(self.root, "apps/web/.spec/requirements/REQ-001.md", _req("REQ-001", [f"{prefix}REQ-001:AC-01"]))
        _write(
            self.root, "apps/web/.spec/technical/TECH-010.md",
            _tech("TECH-010", f"{prefix}REQ-001:AC-01", [f"{prefix}REQ-001:AC-01", f"{prefix}TECH-010:C-01"]),
        )
        _write(
            self.root, "apps/web/.spec/technical/TECH-011.md",
            _tech("TECH-011", None, [f"{prefix}TECH-011"], with_statement=False),
        )

    def runs(self):
        return {
            "all": self.check(self.root, "--all-workspaces"),
            "workspace": self.check(self.root, "--workspace", "web", "--full"),
            "member-cwd": self.check(self.web, "--full"),
            "selected": self.check(self.root, "web::REQ-001"),
        }

    def test_self_qualified_covers_pass_in_every_check_scope(self):
        self.write_web(qualified=True)
        self.commit()
        for name, (result, code) in self.runs().items():
            self.assertEqual((result["status"], code), ("passed", 0), (name, result))
            self.assertEqual(self.coverage(result), [], name)

    def test_check_output_is_the_same_with_and_without_qualification(self):
        self.write_web(qualified=True)
        self.commit()
        qualified = {k: (r["status"], c, self.coverage(r)) for k, (r, c) in self.runs().items()}
        self.write_web(qualified=False)
        _git(self.root, "add", ".")
        _git(self.root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "unqualified")
        unqualified = {k: (r["status"], c, self.coverage(r)) for k, (r, c) in self.runs().items()}
        self.assertEqual(qualified, unqualified)


class RefinesAndCoversCombinationTests(_Base):
    """`refines`と`covers`の書き方の組合せ。どれも`web`の`REQ-002:AC-01`を指す（調査で拒否が割れた組を含む）。"""

    COMBINATIONS = (
        ("web::REQ-002:AC-01", "REQ-002:AC-01"),
        ("REQ-002:AC-01", "web::REQ-002:AC-01"),
        ("web::REQ-002", "REQ-002:AC-01"),
        ("REQ-002", "web::REQ-002:AC-01"),
        ("web::REQ-002:AC-01", "web::REQ-002:AC-01"),
        ("web::REQ-002", "web::REQ-002:AC-01"),
        ("REQ-002:AC-01", "REQ-002:AC-01"),
    )

    def test_every_combination_is_accepted(self):
        _write(self.root, "apps/web/.spec/requirements/REQ-002.md", _req("REQ-002", ["REQ-002:AC-01"]))
        for index, (refines, covers) in enumerate(self.COMBINATIONS):
            doc_id = f"TECH-{20 + index:03d}"
            _write(
                self.root, f"apps/web/.spec/technical/{doc_id}.md",
                _tech(doc_id, refines, [covers, f"{doc_id}:C-01"]),
            )
        self.commit()
        result, code = self.check(self.root, "--all-workspaces")
        self.assertEqual(self.coverage(result), [])
        self.assertEqual((result["status"], code), ("passed", 0), result)


class InvalidCoversControlTests(_Base):
    def test_invalid_targets_are_rejected_with_the_declared_evidence(self):
        _write(self.root, "apps/web/.spec/requirements/REQ-002.md", _req("REQ-002", ["REQ-002:AC-01"]))
        _write(
            self.root, "apps/web/.spec/requirements/REQ-001.md",
            _req("REQ-001", ["web::REQ-001:AC-01", "web::REQ-001:AC-99", "REQ-001:AC-98"]),
        )
        _write(
            self.root, "apps/web/.spec/technical/TECH-010.md",
            _tech(
                "TECH-010", None,
                ["TECH-010:C-01", "web::REQ-002:AC-01", "api::REQ-001:AC-07", "api::REQ-001:AC-01", "web::REQ-099"],
            ),
        )
        self.commit()
        result, code = self.check(self.root, "--all-workspaces")
        self.assertEqual((result["status"], code), ("failed", 1))
        self.assertEqual(
            self.coverage(result),
            [
                (".spec/requirements/REQ-001.md", "REQ-001:AC-98"),
                (".spec/requirements/REQ-001.md", "web::REQ-001:AC-99"),
                (".spec/technical/TECH-010.md", "api::REQ-001:AC-01"),
                (".spec/technical/TECH-010.md", "api::REQ-001:AC-07"),
                (".spec/technical/TECH-010.md", "web::REQ-002:AC-01"),
                (".spec/technical/TECH-010.md", "web::REQ-099"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
