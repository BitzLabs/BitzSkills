"""メンバーの設定の診断の発生元と、ルートの版の非対応の単体試験（確認事項 C72・C37）。

欠陥（C72）: 複合ワークスペースの全体事前検査は、メンバーの設定を読めない・構文・型・必須の不正の診断を、メンバー自身の診断のまま
`{"workspaceId": null, "path": ".spec/bitz.yaml"}`で返していた。ルートの設定と区別できず、どのメンバーの設定かが分からなかった。

規範:
- 結果・診断・終了コード §5: 全体事前検査が返すメンバーの設定の診断は、`workspaceId`を`null`とし、`path`を複合ワークスペースのルートからの相対パス
  （例: `apps/web/.spec/bitz.yaml`）とする。作業ディレクトリがそのメンバーの中にある単独の操作でも同じ。
- 複合ワークスペース仕様 §2（C37）: メンバーの版の非対応は`SPEC-MULTI-VERSION-001`、ルートワークスペース自身の非対応はその設定の読込みの診断
  （`SPEC-CONFIG-SCHEMA-001`、`SPEC-EARS-VERSION-001`、`doctor`は`SPEC-DOCTOR-EARS-001`）。

この試験の対象:
1. 上限の超過、文字コードの不正、YAMLの構文、型の不正のどれでも、全体操作・ルートでの単独の操作・メンバーの中での単独の操作・`doctor`の全体操作が、
   同じ`{"workspaceId": null, "path": "apps/web/.spec/bitz.yaml"}`を返す（型の不正は`key`も保つ）。
2. ルートの版の非対応は、設定の読込みの診断で、`path`は`.spec/bitz.yaml`。
3. 結果は`result.schema.json`に適合する。
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
from bitz import doctor as doctor_mod
from bitz.cliargs import parse_argv

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULT_SCHEMA = REPO_ROOT / "docs" / "03.詳細設計" / "schemas" / "result.schema.json"

CONFIG = 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\n'
ROOT = CONFIG + "workspace:\n  id: platform\nmultiWorkspace:\n  members:\n    - id: web\n      path: apps/web\n"
_GIT_ENV = {"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}
_OPERATIONS = {"check": check_mod, "doctor": doctor_mod}


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args], cwd=root, env={**os.environ, **_GIT_ENV}, check=True, capture_output=True, text=True
    )


def _write(root: Path, rel: str, content: bytes) -> None:
    full = root / rel
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_bytes(content)


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

    def run_op(self, op: str, cwd: Path, *argv: str):
        parsed = parse_argv([op, *argv, "--format", "json"])
        result, code = _OPERATIONS[op].run(parsed, str(cwd), dict(os.environ))
        self.results.append(result)
        return result, code

    @staticmethod
    def sources(result) -> list[tuple[str, dict]]:
        return [(d["code"], d["source"]) for d in result["diagnostics"]]


class MemberConfigSourcePathTests(_Base):
    CASES = {
        "limit": (CONFIG + "workspace:\n  id: web\n" + "#" * 70000 + "\n").encode(),
        "utf8": (CONFIG + "workspace:\n  id: web\n").encode() + b"\xff\n",
        "syntax": (CONFIG + "workspace: [\n").encode(),
        "type": (CONFIG + "workspace:\n  id: web\nlanguage: 3\n").encode(),
    }
    EXPECTED_CODE = {
        "limit": "SPEC-INPUT-LIMIT-001", "utf8": "SPEC-INPUT-READ-001",
        "syntax": "SPEC-CONFIG-SCHEMA-001", "type": "SPEC-CONFIG-SCHEMA-001",
    }

    def test_member_config_diagnostic_path_is_relative_to_the_multi_workspace_root(self):
        for name, content in self.CASES.items():
            with self.subTest(case=name):
                self.setUp()
                _write(self.root, ".spec/bitz.yaml", ROOT.encode())
                _write(self.root, "apps/web/.spec/bitz.yaml", content)
                self.commit()
                expected_source = {"kind": "file", "workspaceId": None, "path": "apps/web/.spec/bitz.yaml"}
                if name == "type":
                    expected_source["key"] = "language"
                for op, cwd, argv in (
                    ("check", self.root, ("--all-workspaces",)),
                    ("doctor", self.root, ("--all-workspaces",)),
                    ("check", self.root, ("--full",)),
                    ("check", self.root / "apps" / "web", ("--full",)),
                ):
                    result, _code = self.run_op(op, cwd, *argv)
                    self.assertEqual(
                        self.sources(result), [(self.EXPECTED_CODE[name], expected_source)], (name, op, cwd, result)
                    )


class RootVersionTests(_Base):
    def test_root_version_mismatch_is_the_config_reading_diagnostic(self):
        cases = {
            "schema": (ROOT.replace('schemaVersion: "1.0"', 'schemaVersion: "2.0"'), "SPEC-CONFIG-SCHEMA-001", "SPEC-CONFIG-SCHEMA-001"),
            "ears": (ROOT.replace('earsAi: "1.0"', 'earsAi: "2.0"'), "SPEC-EARS-VERSION-001", "SPEC-DOCTOR-EARS-001"),
        }
        for name, (root_config, check_code, doctor_code) in cases.items():
            with self.subTest(case=name):
                self.setUp()
                _write(self.root, ".spec/bitz.yaml", root_config.encode())
                _write(self.root, "apps/web/.spec/bitz.yaml", (CONFIG + "workspace:\n  id: web\n").encode())
                self.commit()
                for op, code in (("check", check_code), ("doctor", doctor_code)):
                    result, exit_code = self.run_op(op, self.root, "--all-workspaces")
                    self.assertEqual((result["status"], exit_code), ("blocked", 2), result)
                    self.assertEqual([(c, s["path"]) for c, s in self.sources(result)], [(code, ".spec/bitz.yaml")])


if __name__ == "__main__":
    unittest.main()
