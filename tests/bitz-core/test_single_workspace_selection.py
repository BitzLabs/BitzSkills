"""単一ワークスペースの`--workspace`と`--all-workspaces`の単体試験（確認事項 C73・C64）。

欠陥（C73）: 単一ワークスペースで設定を読めない（同一性を構成できない）とき、または設定がないとき、`--workspace`は値によらず
終了コード4（指定したワークスペースが見つかりません）になり、`--workspace`を付けない場合の停止の結果を返さなかった。
欠陥（C64）: `multiWorkspace`を宣言しない単一ワークスペースでも、`--all-workspaces`が成功していた（入れ子の`.spec`があれば未登録の診断で`blocked`）。

規範:
- Core実行環境・CLI基盤契約 §6: 単一ワークスペースの`--workspace`は、構成した同一性と比べる。設定がない場合と、同一性を構成できない場合は
  比べず、`--workspace`を付けない場合と同じ停止の結果を返す。
- 複合ワークスペース仕様 §8: 設定の読込みを通過したルートの設定（版の非対応の設定を含む）が`multiWorkspace`を宣言しなければ、`--all-workspaces`は
  複合ワークスペースを発見できない引数不正（終了コード4）。ルートの設定を読めない場合は、全体事前検査の停止の結果を返す。

この試験の対象:
1. 設定を読めない場合と設定がない場合、`check`・`context`・`verify`・`doctor`の`--workspace`は、値によらず`--workspace`なしと同じ停止の結果を返す。
2. 同一性を構成できる場合（既定値`root`、明示のID、版の非対応）は、従来どおり一致しない値を終了コード4とする。
3. 宣言のない読める設定（版の非対応を含む）と入れ子の`.spec`があっても、`--all-workspaces`は終了コード4。読めない設定は停止の結果のまま。
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
from bitz import context as context_mod
from bitz import doctor as doctor_mod
from bitz import verify as verify_mod
from bitz.cliargs import parse_argv
from bitz.errors import CliArgError

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULT_SCHEMA = REPO_ROOT / "docs" / "03.詳細設計" / "schemas" / "result.schema.json"

CONFIG = 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\n'
_GIT_ENV = {"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}
_OPERATIONS = {"check": check_mod, "context": context_mod, "verify": verify_mod, "doctor": doctor_mod}
_ARGS = {"check": ("--full",), "context": ("REQ-001", "--purpose", "interpret"), "verify": ("REQ-001",), "doctor": ()}


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
    def setUp(self):
        self.results: list[dict] = []
        self.reset_repository()

    def tearDown(self):
        if self.results:
            _validate_against_schema(self.results)

    def reset_repository(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / "repo"
        self.root.mkdir()

    def commit(self):
        _write(self.root, "README.md", "x\n")
        _git(self.root, "init", "-q", "--initial-branch=main")
        _git(self.root, "add", ".")
        _git(self.root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "base")

    def run_op(self, op: str, *argv: str):
        parsed = parse_argv([op, *argv, "--format", "json"])
        result, code = _OPERATIONS[op].run(parsed, str(self.root), dict(os.environ))
        self.results.append(result)
        return result, code

    @staticmethod
    def shape(result, code):
        return result["status"], code, [d["code"] for d in result["diagnostics"]]


class WorkspaceOptionTests(_Base):
    UNCONSTRUCTED = {
        "syntax": CONFIG + "workspace: [\n",
        "type": CONFIG.replace("language: ja", "language: 3"),
        "limit": CONFIG + "#" * 70000 + "\n",
        "missing": None,
    }

    def test_workspace_option_is_not_compared_when_identity_cannot_be_constructed(self):
        for name, config in self.UNCONSTRUCTED.items():
            with self.subTest(case=name):
                self.reset_repository()
                if config is not None:
                    _write(self.root, ".spec/bitz.yaml", config)
                self.commit()
                for op in _OPERATIONS:
                    without, without_code = self.run_op(op, *_ARGS[op])
                    for value in ("root", "app"):
                        with_option, with_code = self.run_op(op, "--workspace", value, *_ARGS[op])
                        self.assertEqual(
                            self.shape(with_option, with_code), self.shape(without, without_code), (name, op, value)
                        )
                        self.assertNotEqual(with_code, 4, (name, op, value))

    def test_workspace_option_is_compared_when_identity_is_constructed(self):
        cases = {
            "default-root": (CONFIG, "root"),
            "explicit": (CONFIG + "workspace:\n  id: app\n", "app"),
            "schema-major": (CONFIG.replace('schemaVersion: "1.0"', 'schemaVersion: "2.0"'), "root"),
        }
        for name, (config, identity) in cases.items():
            with self.subTest(case=name):
                self.reset_repository()
                _write(self.root, ".spec/bitz.yaml", config)
                self.commit()
                for op in _OPERATIONS:
                    with self.assertRaises(CliArgError, msg=(name, op)):
                        self.run_op(op, "--workspace", "other", *_ARGS[op])
                    result, code = self.run_op(op, "--workspace", identity, *_ARGS[op])
                    self.assertNotEqual(code, 4, (name, op))


class AllWorkspacesDeclarationTests(_Base):
    def test_all_workspaces_without_declaration_is_an_argument_error(self):
        cases = {
            "single": {".spec/bitz.yaml": CONFIG},
            "explicit-id": {".spec/bitz.yaml": CONFIG + "workspace:\n  id: app\n"},
            "nested-spec": {".spec/bitz.yaml": CONFIG, "sub/.spec/bitz.yaml": CONFIG + "workspace:\n  id: sub\n"},
            "schema-major": {".spec/bitz.yaml": CONFIG.replace('schemaVersion: "1.0"', 'schemaVersion: "2.0"')},
            "no-config": {},
        }
        for name, files in cases.items():
            with self.subTest(case=name):
                self.reset_repository()
                for rel, content in files.items():
                    _write(self.root, rel, content)
                self.commit()
                for op in ("check", "verify", "doctor"):
                    with self.assertRaises(CliArgError, msg=(name, op)):
                        self.run_op(op, "--all-workspaces")

    def test_unreadable_root_config_returns_the_preflight_stop_result(self):
        cases = {
            "syntax": (CONFIG + "workspace: [\n", "error", 3, "SPEC-CONFIG-SCHEMA-001"),
            "limit": (CONFIG + "#" * 70000 + "\n", "failed", 1, "SPEC-INPUT-LIMIT-001"),
        }
        for name, (config, status, exit_code, diagnostic) in cases.items():
            with self.subTest(case=name):
                self.reset_repository()
                _write(self.root, ".spec/bitz.yaml", config)
                self.commit()
                for op in ("check", "verify", "doctor"):
                    result, code = self.run_op(op, "--all-workspaces")
                    self.assertEqual(self.shape(result, code), (status, exit_code, [diagnostic]), (name, op))


if __name__ == "__main__":
    unittest.main()
