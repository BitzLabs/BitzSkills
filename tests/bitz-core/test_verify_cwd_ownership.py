"""コマンドの`cwd`の字句と所有の単体試験（確認事項 C82・C86）。

欠陥: 設定の検査は`verify.commands.<名前>.cwd`の型だけを見て、`verify`は`cwd`をそのまま結合して実行していた。
そのため、`cwd: ../..`、絶対パス、空のセグメント、glob、外へ出るシンボリックリンクの`cwd`でも、どの操作も止まらず、
`verify`はテストのコマンドを所有領域の外で起動していた。

規範:
- ワークスペース・設定仕様 §6: `cwd`はワークスペース相対の既存のディレクトリとし、絶対パス、`..`、ルートの外の
  シンボリックリンクを禁止する。字句の違反は設定の検査で`SPEC-CONFIG-SCHEMA-001`とし、実パスの所有は`verify`が
  テスト割当ての起動前に判定する（単一ワークスペースは`SPEC-VERIFY-BLOCKED-001`）。
- 複合ワークスペース仕様 §5・§5.1: `cwd`はメンバーのルート配下だけを所有し、ルートワークスペースはメンバーの配下を
  `cwd`として所有できない。違反は`SPEC-MULTI-OWNERSHIP-001`とし、そのテスト割当てだけを起動しない。

この試験の対象:
1. 字句の違反は、doctor、check、context、verifyのすべてで`SPEC-CONFIG-SCHEMA-001`になり、コマンドを起動しない。
2. 単独の`.`と、正しい形の相対パスは通る。
3. 単一ワークスペースで実パスがルートの外の`cwd`は、`verify`が`SPEC-VERIFY-BLOCKED-001`で起動を遮断する。
4. 複合ワークスペースで所有領域の外の`cwd`は、`SPEC-MULTI-OWNERSHIP-001`で遮断し、独立したテスト割当ては続ける。
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

from bitz import check as check_mod
from bitz import context as context_mod
from bitz import doctor as doctor_mod
from bitz import verify as verify_mod
from bitz.cliargs import parse_argv

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULT_SCHEMA = REPO_ROOT / "docs" / "03.詳細設計" / "schemas" / "result.schema.json"

CONFIG = 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\n'
_GIT_ENV = {"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}
_OPERATIONS = {"doctor": doctor_mod, "check": check_mod, "context": context_mod, "verify": verify_mod}


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args], cwd=root, env={**os.environ, **_GIT_ENV}, check=True, capture_output=True, text=True
    )


def _write(root: Path, rel: str, content: str) -> None:
    full = root / rel
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")


def _verify_config(cwd: str) -> str:
    return f'verify:\n  commands:\n    t:\n      argv: ["/bin/true", "{{tests}}"]\n      cwd: "{cwd}"\n'


def _req(doc_id: str) -> str:
    return (
        f"---\nid: {doc_id}\ntitle: {doc_id}の文書\nstatus: approved\n"
        f"tests:\n  - path: tests/t.py\n    covers: [{doc_id}:AC-01]\n    command: t\n---\n\n"
        f"# {doc_id} {doc_id}の文書\n\n## Intent\n\n意図。\n\n## Acceptance Criteria\n\n"
        f"- [{doc_id}:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] {doc_id}:AC-01を守る。\n\n"
        "## Verification\n\n未証明。\n"
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
        self.root = Path(tmp.name) / "repo"
        self.root.mkdir()
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

    @staticmethod
    def diagnostics(result) -> list[tuple[str, str, str | None, str | None]]:
        diags = list(result["diagnostics"])
        for ws in result.get("workspaces", []):
            diags.extend(ws.get("diagnostics", []))
        for target in result.get("targetResults", []):
            diags.extend(target.get("diagnostics", []))
        return sorted(
            {(d["code"], d["summary"], d["source"].get("workspaceId"), d["source"].get("key")) for d in diags},
            key=repr,
        )

    @staticmethod
    def binding_ids(result) -> list[str]:
        commands = list(result.get("commands", []))
        for ws in result.get("workspaces", []):
            commands.extend(ws.get("commands", []))
        return sorted(c["bindingId"] for c in commands)


class SingleWorkspaceLexicalTests(_Base):
    def write(self, cwd: str):
        _write(self.root, ".spec/bitz.yaml", CONFIG + _verify_config(cwd))
        _write(self.root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
        _write(self.root, "tests/t.py", "def test_t():\n    assert True\n")

    def test_lexically_invalid_cwd_stops_every_operation(self):
        invalid = ["../..", "/tmp", "tests//", "./tests", "tests/.", "tests/../tests", "t*", "a?", "[a]", "a]", ""]
        for cwd in invalid:
            with self.subTest(cwd=cwd):
                self.setUp()
                self.write(cwd)
                self.commit()
                for op, argv in (
                    ("doctor", ()), ("check", ("--full",)), ("context", ("REQ-001", "--purpose", "verify")),
                    ("verify", ("REQ-001",)),
                ):
                    result, code = self.run_op(op, *argv)
                    self.assertEqual((result["status"], code), ("error", 3), (cwd, op, result))
                    self.assertEqual(
                        self.diagnostics(result),
                        [("SPEC-CONFIG-SCHEMA-001", "作業ディレクトリのパスの形式が不正です", None, "verify.commands.t.cwd")],
                        (cwd, op),
                    )
                    self.assertEqual(result.get("commands", []), [], (cwd, op))

    def test_dot_and_relative_cwd_pass(self):
        for cwd in (".", "tests"):
            with self.subTest(cwd=cwd):
                self.setUp()
                self.write(cwd)
                self.commit()
                result, code = self.run_op("verify", "REQ-001")
                self.assertEqual((result["status"], code), ("passed", 0), result)
                self.assertEqual([c["cwd"] for c in result["commands"]], [cwd])


class SingleWorkspaceRealPathTests(_Base):
    def test_symlink_cwd_outside_the_root_is_blocked_before_execution(self):
        _write(self.root, ".spec/bitz.yaml", CONFIG + _verify_config("up"))
        _write(self.root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
        _write(self.root, "tests/t.py", "def test_t():\n    assert True\n")
        os.symlink("..", self.root / "up")
        self.commit()
        result, code = self.run_op("verify", "REQ-001")
        self.assertEqual((result["status"], code), ("blocked", 2), result)
        self.assertEqual(
            self.diagnostics(result),
            [("SPEC-VERIFY-BLOCKED-001", "コマンドの作業ディレクトリが利用できません", "root", "verify.commands.t.cwd")],
        )
        self.assertEqual(result["commands"], [])

    def test_symlink_cwd_inside_the_root_passes(self):
        _write(self.root, ".spec/bitz.yaml", CONFIG + _verify_config("inner"))
        _write(self.root, ".spec/requirements/REQ-001.md", _req("REQ-001").replace("path: tests/t.py", "path: inner/t.py"))
        _write(self.root, "real/t.py", "def test_t():\n    assert True\n")
        os.symlink("real", self.root / "inner")
        self.commit()
        result, code = self.run_op("verify", "REQ-001")
        self.assertEqual((result["status"], code), ("passed", 0), result)


class MultiWorkspaceOwnershipTests(_Base):
    def write(self, root_cwd: str, web_cwd: str):
        _write(
            self.root, ".spec/bitz.yaml",
            CONFIG + "workspace:\n  id: platform\nmultiWorkspace:\n  members:\n    - id: web\n      path: apps/web\n"
            + _verify_config(root_cwd),
        )
        _write(self.root, "apps/web/.spec/bitz.yaml", CONFIG + "workspace:\n  id: web\n" + _verify_config(web_cwd))
        _write(self.root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
        _write(self.root, "apps/web/.spec/requirements/REQ-002.md", _req("REQ-002"))
        _write(self.root, "tests/t.py", "def test_t():\n    assert True\n")
        _write(self.root, "apps/web/tests/t.py", "def test_t():\n    assert True\n")

    def ownership(self, path: str, ws: str):
        return [(
            "SPEC-MULTI-OWNERSHIP-001", f"パス{path}の解決先がワークスペース{ws}の所有領域の外です", ws,
            "verify.commands.t.cwd",
        )]

    def test_root_cwd_inside_a_member_is_outside_its_ownership(self):
        self.write("apps/web", ".")
        self.commit()
        result, code = self.run_op("verify", "--all-workspaces")
        self.assertEqual((result["status"], code), ("failed", 1), result)
        self.assertEqual(self.diagnostics(result), self.ownership("apps/web", "platform"))
        self.assertEqual(self.binding_ids(result), ["web::t"])
        # skip-binding の診断は、テスト割当てを所有するワークスペースへ置く（verify.md §6）。
        self.assertEqual(result["diagnostics"], [])
        by_id = {ws["id"]: ws for ws in result["workspaces"]}
        self.assertEqual([d["code"] for d in by_id["platform"]["diagnostics"]], ["SPEC-MULTI-OWNERSHIP-001"])
        self.assertEqual((by_id["platform"]["status"], by_id["web"]["status"]), ("failed", "passed"))

    def test_root_symlink_cwd_into_a_member_is_outside_its_ownership(self):
        self.write("lk", ".")
        os.symlink("apps/web", self.root / "lk")
        self.commit()
        result, code = self.run_op("verify", "platform::REQ-001")
        self.assertEqual((result["status"], code), ("failed", 1), result)
        self.assertEqual(self.diagnostics(result), self.ownership("lk", "platform"))
        self.assertEqual(self.binding_ids(result), [])

    def test_member_symlink_cwd_out_of_the_member_is_outside_its_ownership(self):
        self.write(".", "esc")
        os.symlink("../..", self.root / "apps" / "web" / "esc")
        self.commit()
        result, code = self.run_op("verify", "--all-workspaces")
        self.assertEqual((result["status"], code), ("failed", 1), result)
        self.assertEqual(self.diagnostics(result), self.ownership("esc", "web"))
        self.assertEqual(self.binding_ids(result), ["platform::t"])
        self.assertEqual(result["diagnostics"], [])
        by_id = {ws["id"]: ws for ws in result["workspaces"]}
        self.assertEqual([d["code"] for d in by_id["web"]["diagnostics"]], ["SPEC-MULTI-OWNERSHIP-001"])
        self.assertEqual((by_id["platform"]["status"], by_id["web"]["status"]), ("passed", "failed"))

    def test_cwd_inside_the_own_area_passes(self):
        self.write("tests", "tests")
        self.commit()
        result, code = self.run_op("verify", "--all-workspaces")
        self.assertEqual((result["status"], code), ("passed", 0), result)
        self.assertEqual(self.binding_ids(result), ["platform::t", "web::t"])


    def test_existing_skip_binding_diagnostics_go_to_the_owning_workspace(self):
        """既存の skip-binding（`VERIFY-CWD-UNAVAILABLE`）も、全体の verify では所有するワークスペースへ置く（verify.md §6）。"""

        self.write(".", "absent-dir")
        self.commit()
        result, code = self.run_op("verify", "--all-workspaces")
        self.assertEqual((result["status"], code), ("blocked", 2), result)
        self.assertEqual(result["diagnostics"], [])
        by_id = {ws["id"]: ws for ws in result["workspaces"]}
        self.assertEqual(
            [(d["code"], d["summary"]) for d in by_id["web"]["diagnostics"]],
            [("SPEC-VERIFY-BLOCKED-001", "コマンドの作業ディレクトリが利用できません")],
        )
        self.assertEqual((by_id["platform"]["status"], by_id["web"]["status"]), ("passed", "blocked"))


if __name__ == "__main__":
    unittest.main()
