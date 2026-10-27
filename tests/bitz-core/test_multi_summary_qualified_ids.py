"""複合ワークスペースの診断の`summary`が、作業ワークスペースの文書IDと規範文IDも修飾することの単体試験（確認事項 C47・C65）。

欠陥: 複合ワークスペースの次の`summary`は、作業ワークスペースの文書IDと規範文IDを修飾せず、他のメンバーのIDだけを修飾していた。
同じ出力の中で修飾の有無が混在し、すでに修飾していた`CTX-STATE-SUPERSEDED-*`や、`verify`の`CTX-COVERAGE-TEST-001`とも食い違った。
- `CTX-STATE-001`（目的に適用できない状態）の`summary`
- `CTX-TASK-DEPENDENCY-001`（先行するTASKが未完了）の`summary`と`suggestedAction`
- `context`の`CTX-COVERAGE-TASK-001`と`CTX-COVERAGE-TEST-001`の`summary`

規範:
- 複合ワークスペース仕様 §4: 複合ワークスペース内で実行したCore操作の文書`id`、`statements`などは複合ワークスペースの正規形式で返す。
- 表記規則 §3.5の6・7: 差し込む値はそのまま差し込み、同じ条件IDの診断は操作によらず同じ文型にする。
- `summary`のIDの形は規範文で1つに決まらないため、`CTX-STATE-SUPERSEDED-*`と`verify`の先例にそろえる（ユーザーの決定 2026-10-26）。

この試験の対象:
1. 作業ワークスペースの文書・規範文のIDも、他のメンバーのIDと同じく修飾する（起点、依存先、先行するTASK、テスト対応、TASK対応）。
2. 他のメンバーを作業ワークスペースにしたときは、そのメンバーのIDで修飾する。
3. 対照: 単一ワークスペースでは修飾しない。
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

from bitz import context as context_mod
from bitz import verify as verify_mod
from bitz.cliargs import parse_argv

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULT_SCHEMA = REPO_ROOT / "docs" / "03.詳細設計" / "schemas" / "result.schema.json"

CONFIG = 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\n'
VERIFY = 'verify:\n  commands:\n    t:\n      argv: ["/bin/true", "{tests}"]\n      cwd: .\n'
ROOT_YAML = CONFIG + "workspace:\n  id: platform\nmultiWorkspace:\n  members:\n    - id: api\n      path: services/api\n" + VERIFY
API_YAML = CONFIG + "workspace:\n  id: api\n" + VERIFY
_GIT_ENV = {"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args], cwd=root, env={**os.environ, **_GIT_ENV}, check=True, capture_output=True, text=True
    )


def _write(root: Path, rel: str, content: str) -> None:
    full = root / rel
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")


def _statement(stmt_id: str, modality: str = "MUST") -> str:
    return f"- [{stmt_id}] [ACTOR:TargetSystem] [ALWAYS] [{modality}] [CONSTRAINT] {stmt_id}を守る。\n"


def _req(doc_id: str, status: str = "approved", *, requires: list[str] | None = None, tested: bool = True) -> str:
    relations = f"relations:\n  requires: [{', '.join(requires)}]\n" if requires else ""
    tests = f"tests:\n  - path: tests/t.py\n    covers: [{doc_id}:AC-01]\n    command: t\n" if tested else ""
    return (
        f"---\nid: {doc_id}\ntitle: {doc_id}の文書\nstatus: {status}\n{relations}{tests}---\n\n"
        f"# {doc_id} {doc_id}の文書\n\n## Intent\n\n意図。\n\n## Acceptance Criteria\n\n{_statement(f'{doc_id}:AC-01')}\n"
        "## Verification\n\n未証明。\n"
    )


def _task(doc_id: str, status: str, addresses: str, *, requires: list[str] | None = None) -> str:
    relations = f"relations:\n  addresses: [{addresses}]\n"
    if requires:
        relations += f"  requires: [{', '.join(requires)}]\n"
    return (
        f"---\nid: {doc_id}\ntitle: {doc_id}の文書\nstatus: {status}\n{relations}changes: [src/work.py]\n---\n\n"
        f"# {doc_id} {doc_id}の文書\n\n## Objective\n\n目的。\n"
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
    multi = True

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        _write(self.root, ".spec/bitz.yaml", ROOT_YAML if self.multi else CONFIG + VERIFY)
        _write(self.root, "tests/t.py", "def test_t():\n    assert True\n")
        if self.multi:
            _write(self.root, "services/api/.spec/bitz.yaml", API_YAML)
            _write(self.root, "services/api/tests/t.py", "def test_t():\n    assert True\n")
        self.results: list[dict] = []
        self.populate()
        _git(self.root, "init", "-q", "--initial-branch=main")
        _git(self.root, "add", ".")
        _git(self.root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "base")

    def populate(self):
        spec = ".spec/requirements"
        _write(self.root, f"{spec}/REQ-001.md", _req("REQ-001", "draft"))
        _write(self.root, f"{spec}/REQ-002.md", _req("REQ-002", requires=["REQ-003"]))
        _write(self.root, f"{spec}/REQ-003.md", _req("REQ-003", "draft"))
        _write(self.root, f"{spec}/REQ-050.md", _req("REQ-050", tested=False))
        _write(self.root, ".spec/tasks/TASK-001.md", _task("TASK-001", "open", "REQ-050:AC-01"))
        _write(self.root, ".spec/tasks/TASK-002.md", _task("TASK-002", "open", "REQ-050:AC-01", requires=["TASK-001"]))
        if self.multi:
            _write(self.root, f"{spec}/REQ-004.md", _req("REQ-004", requires=["api::REQ-100"]))
            api = "services/api/.spec"
            _write(self.root, f"{api}/requirements/REQ-100.md", _req("REQ-100", "draft"))
            _write(self.root, f"{api}/requirements/REQ-101.md", _req("REQ-101"))
            _write(self.root, f"{api}/tasks/TASK-100.md", _task("TASK-100", "open", "REQ-101:AC-01"))
            _write(
                self.root, f"{api}/tasks/TASK-101.md",
                _task("TASK-101", "open", "REQ-101:AC-01", requires=["TASK-100"]),
            )

    def context(self, *argv: str):
        parsed = parse_argv(["context", *argv, "--format", "json"])
        result, code = context_mod.run(parsed, str(self.root), dict(os.environ))
        self.results.append(result)
        return result, code

    def verify(self, *argv: str):
        parsed = parse_argv(["verify", *argv, "--format", "json"])
        result, code = verify_mod.run(parsed, str(self.root), dict(os.environ))
        self.results.append(result)
        return result, code

    def tearDown(self):
        if self.results:
            _validate_against_schema(self.results)

    @staticmethod
    def summaries(result, code: str) -> list[str]:
        diags = list(result["diagnostics"])
        for target in result.get("targetResults", []):
            diags.extend(target["diagnostics"])
        return [d["summary"] for d in diags if d["code"] == code]

    @staticmethod
    def actions(result, code: str) -> list[str]:
        return [d.get("suggestedAction") for d in result["diagnostics"] if d["code"] == code]


class StateSummaryTests(_Base):
    def test_origin_of_the_active_workspace_is_qualified(self):
        result, _ = self.context("REQ-001", "--purpose", "implement")
        self.assertEqual(
            self.summaries(result, "CTX-STATE-001"), ["platform::REQ-001は状態draftのため目的implementに適用できません"]
        )

    def test_dependency_in_the_active_and_another_workspace_are_both_qualified(self):
        own, _ = self.context("REQ-002", "--purpose", "implement")
        other, _ = self.context("REQ-004", "--purpose", "implement")
        self.assertEqual(self.summaries(own, "CTX-STATE-001"), ["platform::REQ-003は状態draftのため目的implementに適用できません"])
        self.assertEqual(self.summaries(other, "CTX-STATE-001"), ["api::REQ-100は状態draftのため目的implementに適用できません"])

    def test_verify_target_uses_the_same_form(self):
        result, _ = self.verify("REQ-001")
        self.assertEqual(
            self.summaries(result, "CTX-STATE-001"), ["platform::REQ-001は状態draftのため目的verifyに適用できません"]
        )


class TaskDependencySummaryTests(_Base):
    def test_prerequisite_of_the_active_workspace_is_qualified(self):
        result, _ = self.context("TASK-002", "--purpose", "implement")
        self.assertEqual(
            self.summaries(result, "CTX-TASK-DEPENDENCY-001"), ["先行するplatform::TASK-001が状態openで、状態doneではありません"]
        )
        self.assertEqual(
            self.actions(result, "CTX-TASK-DEPENDENCY-001"),
            ["先行するplatform::TASK-001を完了して状態doneにするか、起点のTASKのフィールドrequiresから外してください"],
        )

    def test_another_member_as_the_active_workspace_uses_its_own_id(self):
        result, _ = self.context("api::TASK-101", "--purpose", "implement")
        self.assertEqual(
            self.summaries(result, "CTX-TASK-DEPENDENCY-001"), ["先行するapi::TASK-100が状態openで、状態doneではありません"]
        )


class CoverageSummaryTests(_Base):
    def test_implement_coverage_summaries_are_qualified(self):
        result, _ = self.context("REQ-050", "--purpose", "implement")
        self.assertEqual(
            self.summaries(result, "CTX-COVERAGE-TEST-001"), ["対象規範文MUST platform::REQ-050:AC-01にテスト対応がありません"]
        )

    def test_verify_purpose_coverage_summary_matches_verify(self):
        context_result, _ = self.context("REQ-050", "--purpose", "verify")
        verify_result, _ = self.verify("REQ-050")
        self.assertEqual(
            self.summaries(context_result, "CTX-COVERAGE-TEST-001"),
            ["対象規範文MUST platform::REQ-050:AC-01にテスト対応がありません"],
        )
        self.assertEqual(
            self.summaries(context_result, "CTX-COVERAGE-TEST-001"), self.summaries(verify_result, "CTX-COVERAGE-TEST-001")
        )


class SingleWorkspaceControlTests(_Base):
    multi = False

    def test_single_workspace_ids_are_not_qualified(self):
        state, _ = self.context("REQ-001", "--purpose", "implement")
        task, _ = self.context("TASK-002", "--purpose", "implement")
        coverage, _ = self.context("REQ-050", "--purpose", "verify")
        self.assertEqual(self.summaries(state, "CTX-STATE-001"), ["REQ-001は状態draftのため目的implementに適用できません"])
        self.assertEqual(
            self.summaries(task, "CTX-TASK-DEPENDENCY-001"), ["先行するTASK-001が状態openで、状態doneではありません"]
        )
        self.assertEqual(
            self.summaries(coverage, "CTX-COVERAGE-TEST-001"), ["対象規範文MUST REQ-050:AC-01にテスト対応がありません"]
        )


if __name__ == "__main__":
    unittest.main()
