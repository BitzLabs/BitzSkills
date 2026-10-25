"""`verify`の`targetResults[].statements`が出力するIDの重複なし辞書順になること（確認事項 C52）と、
コンテキストのハッシュ値の材料の規範文が`id`のコードポイント辞書順になること（確認事項 C60）の単体試験。

欠陥: `verify`は`targetResults[].statements`を、対象の規範文の内部の並び（起点の規範文を文書順・行番号で並べた後に、
具体化文書の規範文を足した順）のまま出力していた。そのため、文書の中で規範文を番号の順に書かないときや、
起点より辞書順で前の文書が起点を具体化するときに、辞書順にならなかった。

規範:
- verify §8の`targetResults[]`の表: `statements`は「検証対象が検証する規範文。重複なし辞書順」。
- 複合ワークスペース仕様 §4・§6: 複合ワークスペースの規範文IDは修飾IDで出力する。辞書順は出力する修飾IDで比べる。
- `contextDigest`は並びに依存しない（コンテキストのハッシュ値の正規化仕様 §3）。並びの修正で変わらない。

この試験の対象:
1. 1つの文書の中の並び（`AC-10`を`AC-02`より前に書く）。
2. 具体化文書の並び（`TECH-003`が`TECH-005`を具体化する）。
3. 複合ワークスペースの修飾IDの並び（`api::`の文書が`platform::`の規範文を具体化する）。
4. 対照: すでに辞書順の入力は変わらない。`contextDigest`、状態、テスト割当ては並びの修正で変わらない。
5. 結果は`result.schema.json`に適合し、`PYTHONHASHSEED`を変えても出力は同じ。
6. C60: `context`と`verify`がハッシュ値の材料（`documents[].statements`）に入れる規範文は、文書に書いた順ではなく`id`のコードポイント辞書順
   （コンテキストのハッシュ値の正規化仕様 §3の表）。修正前のCoreは文書に書いた順のまま入れていた。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from unittest import mock

from bitz import context as context_mod
from bitz import digest as digest_mod
from bitz import verify as verify_mod
from bitz.cliargs import parse_argv

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULT_SCHEMA = REPO_ROOT / "docs" / "03.詳細設計" / "schemas" / "result.schema.json"

CONFIG = 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\n'
VERIFY = 'verify:\n  commands:\n    t:\n      argv: ["/bin/true", "{tests}"]\n      cwd: .\n'
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


def _tests_block(covers: list[str]) -> str:
    return f"tests:\n  - path: tests/t.py\n    covers: [{', '.join(covers)}]\n    command: t\n"


def _req(doc_id: str, labels: list[str]) -> str:
    stmts = "".join(_statement(f"{doc_id}:{label}") for label in labels)
    return (
        f"---\nid: {doc_id}\ntitle: {doc_id}の文書\nstatus: approved\n"
        + _tests_block([f"{doc_id}:{label}" for label in labels])
        + f"---\n\n# {doc_id} {doc_id}の文書\n\n## Intent\n\n意図。\n\n## Acceptance Criteria\n\n{stmts}\n## Verification\n\n未証明。\n"
    )


def _tech(doc_id: str, label: str, refines: str | None) -> str:
    relations = f"relations:\n  refines: [{refines}]\n" if refines else ""
    return (
        f"---\nid: {doc_id}\ntitle: {doc_id}の文書\nstatus: approved\n{relations}"
        + _tests_block([f"{doc_id}:{label}"])
        + f"---\n\n# {doc_id} {doc_id}の文書\n\n## Context\n\n本文。\n\n## Constraints\n\n{_statement(f'{doc_id}:{label}')}"
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
        _write(self.root, "tests/t.py", "def test_t():\n    assert True\n")

    def tearDown(self):
        if self.results:
            _validate_against_schema(self.results)

    def commit(self):
        _git(self.root, "init", "-q", "--initial-branch=main")
        _git(self.root, "add", ".")
        _git(self.root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "base")

    def verify(self, *targets: str, cwd: Path | None = None):
        parsed = parse_argv(["verify", *targets, "--format", "json"])
        result, code = verify_mod.run(parsed, str(cwd or self.root), dict(os.environ))
        self.results.append(result)
        return result, code

    @staticmethod
    def statements(result) -> dict[str, list[str]]:
        return {t["target"]: t["statements"] for t in result["targetResults"]}


class SingleWorkspaceOrderTests(_Base):
    def setUp(self):
        super().setUp()
        _write(self.root, ".spec/bitz.yaml", CONFIG + VERIFY)

    def test_statements_written_out_of_order_in_one_document(self):
        _write(self.root, ".spec/requirements/REQ-001.md", _req("REQ-001", ["AC-10", "AC-02"]))
        self.commit()
        result, _ = self.verify("REQ-001")
        self.assertEqual(self.statements(result), {"REQ-001": ["REQ-001:AC-02", "REQ-001:AC-10"]})

    def test_refinement_statement_that_sorts_before_the_root(self):
        _write(self.root, ".spec/technical/TECH-005.md", _tech("TECH-005", "C-01", None))
        _write(self.root, ".spec/technical/TECH-003.md", _tech("TECH-003", "C-01", "TECH-005:C-01"))
        self.commit()
        result, code = self.verify("TECH-005")
        self.assertEqual(self.statements(result), {"TECH-005": ["TECH-003:C-01", "TECH-005:C-01"]})
        self.assertEqual((result["status"], code), ("passed", 0), result["diagnostics"])

    def test_already_sorted_statements_are_unchanged(self):
        _write(self.root, ".spec/requirements/REQ-001.md", _req("REQ-001", ["AC-01", "AC-02"]))
        self.commit()
        result, _ = self.verify("REQ-001")
        self.assertEqual(self.statements(result), {"REQ-001": ["REQ-001:AC-01", "REQ-001:AC-02"]})

    def test_digest_and_status_do_not_depend_on_the_written_order(self):
        _write(self.root, ".spec/requirements/REQ-001.md", _req("REQ-001", ["AC-10", "AC-02"]))
        self.commit()
        unordered, code_a = self.verify("REQ-001")
        _write(self.root, ".spec/requirements/REQ-001.md", _req("REQ-001", ["AC-02", "AC-10"]))
        _git(self.root, "add", ".")
        _git(self.root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "reorder")
        ordered, code_b = self.verify("REQ-001")
        self.assertEqual(self.statements(unordered), self.statements(ordered))
        self.assertEqual((unordered["status"], code_a), (ordered["status"], code_b))
        a, b = unordered["targetResults"][0], ordered["targetResults"][0]
        self.assertEqual(a["bindingRefs"], b["bindingRefs"])

    def test_output_is_independent_of_the_hash_seed(self):
        _write(self.root, ".spec/technical/TECH-005.md", _tech("TECH-005", "C-01", None))
        _write(self.root, ".spec/technical/TECH-003.md", _tech("TECH-003", "C-01", "TECH-005:C-01"))
        _write(self.root, ".spec/requirements/REQ-001.md", _req("REQ-001", ["AC-10", "AC-02"]))
        self.commit()
        outputs = set()
        for seed in ("0", "1", "4242"):
            proc = subprocess.run(
                [sys.executable, "-m", "bitz.cli", "verify", "REQ-001", "TECH-005", "--format", "json"],
                cwd=self.root,
                env={**os.environ, "PYTHONHASHSEED": seed, "PYTHONPATH": os.pathsep.join(sys.path)},
                capture_output=True,
                text=True,
            )
            data = json.loads(proc.stdout)
            outputs.add(json.dumps(
                [(t["target"], t["statements"], t["contextDigest"]) for t in data["targetResults"]], ensure_ascii=False
            ))
        self.assertEqual(len(outputs), 1, outputs)


class MultiWorkspaceOrderTests(_Base):
    def setUp(self):
        super().setUp()
        _write(
            self.root,
            ".spec/bitz.yaml",
            CONFIG + "workspace:\n  id: platform\nmultiWorkspace:\n  members:\n    - id: api\n      path: services/api\n" + VERIFY,
        )
        _write(self.root, "services/api/.spec/bitz.yaml", CONFIG + "workspace:\n  id: api\n" + VERIFY)
        _write(self.root, "services/api/tests/t.py", "def test_t():\n    assert True\n")
        _write(self.root, ".spec/requirements/REQ-001.md", _req("REQ-001", ["AC-01"]))
        _write(
            self.root,
            "services/api/.spec/technical/TECH-010.md",
            _tech("TECH-010", "C-01", "platform::REQ-001:AC-01"),
        )
        self.commit()

    def test_qualified_statements_are_sorted_by_the_output_id(self):
        result, _ = self.verify("REQ-001")
        self.assertEqual(
            self.statements(result),
            {"platform::REQ-001": ["api::TECH-010:C-01", "platform::REQ-001:AC-01"]},
        )


class DigestMaterialStatementOrderTests(_Base):
    """ハッシュ値の材料を`digest.canonical_bytes`の引数から取り出し、規範文の並びを確かめる（C60）。"""

    def setUp(self):
        super().setUp()
        _write(self.root, ".spec/bitz.yaml", CONFIG + VERIFY)
        _write(self.root, ".spec/requirements/REQ-001.md", _req("REQ-001", ["AC-10", "AC-02"]))
        self.commit()

    def capture(self, run):
        captured: list[dict] = []
        original = digest_mod.canonical_bytes

        def spy(materials):
            captured.append(materials)
            return original(materials)

        with mock.patch.object(digest_mod, "canonical_bytes", spy):
            run()
        self.assertTrue(captured)
        return captured

    def statement_ids(self, materials):
        return {doc["id"]: [stmt["id"] for stmt in doc["statements"]] for doc in materials["documents"]}

    def test_context_digest_material_sorts_statements_by_id(self):
        def run():
            parsed = parse_argv(["context", "REQ-001", "--format", "json"])
            result, _ = context_mod.run(parsed, str(self.root), dict(os.environ))
            self.results.append(result)

        for materials in self.capture(run):
            self.assertEqual(self.statement_ids(materials)["REQ-001"], ["REQ-001:AC-02", "REQ-001:AC-10"])

    def test_verify_digest_material_sorts_statements_by_id(self):
        for materials in self.capture(lambda: self.verify("REQ-001")):
            self.assertEqual(self.statement_ids(materials)["REQ-001"], ["REQ-001:AC-02", "REQ-001:AC-10"])

    def test_context_and_verify_digests_agree(self):
        parsed = parse_argv(["context", "REQ-001", "--purpose", "verify", "--format", "json"])
        context_result, _ = context_mod.run(parsed, str(self.root), dict(os.environ))
        self.results.append(context_result)
        verify_result, _ = self.verify("REQ-001")
        self.assertEqual(context_result["contextDigest"], verify_result["targetResults"][0]["contextDigest"])


if __name__ == "__main__":
    unittest.main()
