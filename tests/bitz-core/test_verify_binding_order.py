"""テスト割当ての実行順と`commands[]`の並びの単体試験（確認事項 C62・C61）。

欠陥: `verify`はテスト割当てを``(workspace_id, コマンド名)``の素の辞書順で実行し、単独の操作の`commands[]`も同じ順に並べていた。
ルートワークスペースのIDがメンバーのIDより辞書順で後ろのとき、`verify --all-workspaces`はメンバーのテスト割当てを先に実行し、
verify.md §10の「ルートワークスペースを先頭、その後をワークスペースIDの辞書順」と食い違った。

規範:
- verify.md §4の6.・§10: ワークスペースの処理順（ルートを先頭、その後をワークスペースIDの辞書順）、コマンド名の辞書順でテスト割当てを逐次実行する。
  単独の操作の`commands[]`も同じ順に並べる。
- verify.md §8: `commands[].covers`は重複なしの辞書順。

この試験の対象:
1. `verify --all-workspaces`は、ルートのIDが辞書順で後ろでも、ルートのテスト割当てを先に実行する。同じワークスペースではコマンド名の辞書順。
2. 単独の操作の`commands[]`は、ルートのテスト割当てを先に並べる。
3. `commands[].covers`は辞書順。
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

from bitz import verify as verify_mod
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


def _verify_config(ws_id: str, *names: str) -> str:
    """実行したテスト割当ての`<ワークスペースID>::<コマンド名>`を、環境変数`BITZ_ORDER_LOG`のファイルへ追記するコマンド。"""

    commands = "".join(
        f'    {name}:\n      argv: ["/bin/sh", "-c", "echo $0 >> \\"$BITZ_ORDER_LOG\\"", "{ws_id}::{name}", "{{tests}}"]\n'
        "      cwd: .\n"
        for name in names
    )
    return "verify:\n  commands:\n" + commands


def _statement(stmt_id: str) -> str:
    return f"- [{stmt_id}] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] {stmt_id}を守る。\n"


def _req(doc_id: str, tests: list[tuple[str, list[str], str]]) -> str:
    entries = "".join(
        f"  - path: {path}\n    covers: [{', '.join(covers)}]\n    command: {command}\n" for path, covers, command in tests
    )
    statements = "".join(_statement(f"{doc_id}:AC-0{index}") for index in (1, 2))
    return (
        f"---\nid: {doc_id}\ntitle: {doc_id}の文書\nstatus: approved\ntests:\n{entries}---\n\n"
        f"# {doc_id} {doc_id}の文書\n\n## Intent\n\n意図。\n\n## Acceptance Criteria\n\n{statements}\n"
        "## Verification\n\n未証明。\n"
    )


def _tech(doc_id: str, refines: str, covers: list[str], command: str) -> str:
    return (
        f"---\nid: {doc_id}\ntitle: {doc_id}の文書\nstatus: approved\nrelations:\n  refines: [{refines}]\n"
        f"tests:\n  - path: tests/t.py\n    covers: [{', '.join(covers)}]\n    command: {command}\n---\n\n"
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


class BindingOrderTests(unittest.TestCase):
    """ルートワークスペース`zeta`（ルートのIDが辞書順で最後）と、メンバー`alpha`、`beta`。"""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / "repo"
        self.root.mkdir()
        self.log = Path(tmp.name) / "order.log"
        self.results: list[dict] = []
        _write(
            self.root, ".spec/bitz.yaml",
            CONFIG + "workspace:\n  id: zeta\nmultiWorkspace:\n  members:\n"
            "    - id: beta\n      path: apps/beta\n    - id: alpha\n      path: apps/alpha\n"
            + _verify_config("zeta", "b", "a"),
        )
        for member in ("alpha", "beta"):
            _write(
                self.root, f"apps/{member}/.spec/bitz.yaml",
                CONFIG + f"workspace:\n  id: {member}\n" + _verify_config(member, "t"),
            )
            _write(self.root, f"apps/{member}/tests/t.py", "def test_t():\n    assert True\n")
            _write(
                self.root, f"apps/{member}/.spec/technical/TECH-001.md",
                _tech("TECH-001", "zeta::REQ-001:AC-01", ["zeta::REQ-001:AC-01", "TECH-001:C-01"], "t"),
            )
        _write(self.root, "tests/a.py", "def test_a():\n    assert True\n")
        _write(self.root, "tests/b.py", "def test_b():\n    assert True\n")
        _write(
            self.root, ".spec/requirements/REQ-001.md",
            _req("REQ-001", [("tests/b.py", ["REQ-001:AC-02", "REQ-001:AC-01"], "b"), ("tests/a.py", ["REQ-001:AC-02"], "a")]),
        )
        _git(self.root, "init", "-q", "--initial-branch=main")
        _git(self.root, "add", ".")
        _git(self.root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "base")

    def tearDown(self):
        if self.results:
            _validate_against_schema(self.results)

    def verify(self, *argv: str):
        parsed = parse_argv(["verify", *argv, "--format", "json"])
        result, code = verify_mod.run(parsed, str(self.root), {**os.environ, "BITZ_ORDER_LOG": str(self.log)})
        self.results.append(result)
        return result, code

    def executed(self) -> list[str]:
        return self.log.read_text(encoding="utf-8").split()

    def test_all_workspaces_runs_the_root_first(self):
        result, code = self.verify("--all-workspaces")
        self.assertEqual((result["status"], code), ("passed", 0), result)
        self.assertEqual(self.executed(), ["zeta::a", "zeta::b", "alpha::t", "beta::t"])
        self.assertEqual([ws["id"] for ws in result["workspaces"]], ["zeta", "alpha", "beta"])

    def test_single_operation_lists_root_commands_first(self):
        result, code = self.verify("zeta::REQ-001")
        self.assertEqual((result["status"], code), ("passed", 0), result)
        self.assertEqual([c["bindingId"] for c in result["commands"]], ["zeta::a", "zeta::b", "alpha::t", "beta::t"])
        self.assertEqual(self.executed(), ["zeta::a", "zeta::b", "alpha::t", "beta::t"])

    def test_commands_covers_are_in_dictionary_order(self):
        result, _code = self.verify("zeta::REQ-001")
        by_id = {c["bindingId"]: c for c in result["commands"]}
        self.assertEqual(by_id["zeta::b"]["covers"], ["zeta::REQ-001:AC-01", "zeta::REQ-001:AC-02"])
        for binding_id in ("zeta::a", "zeta::b", "alpha::t", "beta::t"):
            self.assertEqual(by_id[binding_id]["covers"], sorted(by_id[binding_id]["covers"]), binding_id)


if __name__ == "__main__":
    unittest.main()
