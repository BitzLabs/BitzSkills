"""Gitの境界を確定できない`doctor`が、カタログの不適合も返すことの単体試験（確認事項 C50）。

欠陥: Gitがない（またはリポジトリの外の）複合ワークスペースで、`doctor`は`SPEC-MULTI-GIT-001`だけを返し、ルートの設定の本文だけで判定できるカタログの不適合
（`multiWorkspace`の型と件数、除外のパス、ルートの`workspace.id`の省略）を隠していた。Gitがあれば同じ入力で`SPEC-MULTI-CONFIG-001`を返す。

規範:
- `04_doctor.md` §3: `doctor`は設定の不適合とGitの不在を独立した原因とする。Gitの境界を確定できずに止まる場合も、ルートの設定の本文だけで判定できるカタログの不適合
  （`SPEC-MULTI-CONFIG-001`）を並べて返し、検査項目`catalog`を`failed`とする。ルートの候補の位置に依存する検査（メンバーの設定、パス、未登録の設定）は行わない（ADR-070）。
- 複合ワークスペース仕様 §3: ほかの操作は`SPEC-MULTI-GIT-001`だけを返す。

この試験の対象:
1. Gitがないとき、`doctor`と`doctor --all-workspaces`は、形状（`multiWorkspace`の値の欠落・非マッピング、`maxMembers`の範囲外、`members`の欠落・非配列・0件・要素の型）、
   除外のパス（字句、`.spec`、重複、入れ子、複数の要素）、ルートのIDの省略の不適合を`SPEC-MULTI-GIT-001`と並べて返し、`catalog`は`failed`、全体は`failed`／1。
2. 診断の中身と件数は、Gitがある場合の`doctor`の`SPEC-MULTI-CONFIG-001`と同じ。Gitはあるがリポジトリの外で実行した場合も同じ。
3. カタログが妥当なら、`SPEC-MULTI-GIT-001`だけ（修正前と同じ）。
4. `check`と`verify`は、どの入力でも`SPEC-MULTI-GIT-001`だけ。
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
from bitz import doctor as doctor_mod
from bitz import verify as verify_mod
from bitz.cliargs import parse_argv

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULT_SCHEMA = REPO_ROOT / "docs" / "03.詳細設計" / "schemas" / "result.schema.json"

CONFIG = 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\n'
MEMBERS = "  members:\n    - id: web\n      path: apps/web\n"
_GIT_ENV = {"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}
_OPERATIONS = {"check": check_mod, "verify": verify_mod, "doctor": doctor_mod}

CASES = {
    "members-empty": CONFIG + "workspace:\n  id: platform\nmultiWorkspace:\n  members: []\n",
    "members-type": CONFIG + "workspace:\n  id: platform\nmultiWorkspace:\n  members: 3\n",
    "exclude-invalid": CONFIG + "workspace:\n  id: platform\nmultiWorkspace:\n" + MEMBERS + "  exclude: [../x]\n",
    "members-missing": CONFIG + "workspace:\n  id: platform\nmultiWorkspace:\n  maxMembers: 5\n",
    "member-entry-type": CONFIG + "workspace:\n  id: platform\nmultiWorkspace:\n  members: [web]\n",
    "max-members-range": CONFIG + "workspace:\n  id: platform\nmultiWorkspace:\n  maxMembers: 0\n" + MEMBERS,
    "not-mapping": CONFIG + "workspace:\n  id: platform\nmultiWorkspace: [web]\n",
    "null-declaration": CONFIG + "workspace:\n  id: platform\nmultiWorkspace:\n",
    "exclude-spec": CONFIG + "workspace:\n  id: platform\nmultiWorkspace:\n" + MEMBERS + "  exclude: [tools/.spec]\n",
    "exclude-duplicate": CONFIG + "workspace:\n  id: platform\nmultiWorkspace:\n" + MEMBERS + "  exclude: [tools, tools]\n",
    "exclude-nested": CONFIG + "workspace:\n  id: platform\nmultiWorkspace:\n" + MEMBERS + "  exclude: [tools, tools/x]\n",
    "exclude-two": CONFIG + "workspace:\n  id: platform\nmultiWorkspace:\n" + MEMBERS + "  exclude: [../x, /abs]\n",
    "root-id-omitted": CONFIG + "multiWorkspace:\n" + MEMBERS,
}


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


class DoctorWithoutGitTests(unittest.TestCase):
    def setUp(self):
        self.results: list[dict] = []
        self.no_git = {**os.environ, "PATH": ""}

    def tearDown(self):
        if self.results:
            _validate_against_schema(self.results)

    def make(self, root_config: str, *, git: bool) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name) / "repo"
        _write(root, ".spec/bitz.yaml", root_config)
        _write(root, "apps/web/.spec/bitz.yaml", CONFIG + "workspace:\n  id: web\n")
        if git:
            if subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=root, capture_output=True).returncode == 0:
                raise unittest.SkipTest("一時ディレクトリがGitのリポジトリの中にあります")
            env = {**os.environ, **_GIT_ENV}
            for args in (["init", "-q", "--initial-branch=main"], ["add", "."],
                         ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "base"]):
                subprocess.run(["git", *args], cwd=root, env=env, check=True, capture_output=True)
        return root

    def run_op(self, op: str, root: Path, env: dict, *argv: str):
        parsed = parse_argv([op, *argv, "--format", "json"])
        result, code = _OPERATIONS[op].run(parsed, str(root), env)
        self.results.append(result)
        return result, code

    @staticmethod
    def config_diagnostics(result) -> list[dict]:
        return [d for d in result["diagnostics"] if d["code"] == "SPEC-MULTI-CONFIG-001"]

    def test_doctor_returns_catalog_defects_together_with_the_git_diagnostic(self):
        for name, root_config in CASES.items():
            with self.subTest(case=name):
                with_git, _code = self.run_op("doctor", self.make(root_config, git=True), dict(os.environ))
                expected = self.config_diagnostics(with_git)
                self.assertEqual(len(expected), 2 if name == "exclude-two" else 1, (name, with_git["diagnostics"]))
                self.assertEqual(len(with_git["diagnostics"]), len(expected), (name, with_git["diagnostics"]))
                root = self.make(root_config, git=False)
                # Gitがない場合と、Gitはあるがリポジトリの外で実行した場合。
                for env in (self.no_git, dict(os.environ)):
                    for argv in ((), ("--all-workspaces",)):
                        result, code = self.run_op("doctor", root, env, *argv)
                        self.assertEqual((result["status"], code), ("failed", 1), (name, argv, result))
                        self.assertEqual(
                            sorted(d["code"] for d in result["diagnostics"]),
                            ["SPEC-MULTI-CONFIG-001"] * len(expected) + ["SPEC-MULTI-GIT-001"],
                        )
                        self.assertEqual(self.config_diagnostics(result), expected, (name, argv))
                        checks = {c["name"]: c["status"] for c in result["checks"]}
                        self.assertEqual((checks.get("git"), checks.get("catalog")), ("blocked", "failed"), (name, argv))

    def test_valid_catalog_without_git_returns_only_the_git_diagnostic(self):
        root = self.make(CONFIG + "workspace:\n  id: platform\nmultiWorkspace:\n" + MEMBERS, git=False)
        result, code = self.run_op("doctor", root, self.no_git, "--all-workspaces")
        self.assertEqual((result["status"], code), ("blocked", 2), result)
        self.assertEqual([d["code"] for d in result["diagnostics"]], ["SPEC-MULTI-GIT-001"])
        self.assertNotIn("catalog", {c["name"] for c in result["checks"]})

    def test_other_operations_return_only_the_git_diagnostic(self):
        for name, root_config in CASES.items():
            with self.subTest(case=name):
                root = self.make(root_config, git=False)
                for op in ("check", "verify"):
                    result, code = self.run_op(op, root, self.no_git, "--all-workspaces")
                    self.assertEqual((result["status"], code), ("blocked", 2), (name, op, result))
                    self.assertEqual([d["code"] for d in result["diagnostics"]], ["SPEC-MULTI-GIT-001"], (name, op))


if __name__ == "__main__":
    unittest.main()
