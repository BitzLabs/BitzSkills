"""`doctor`が、ルートの設定で全体事前検査が止まっても、Gitの境界を確定できなければ`SPEC-MULTI-GIT-001`を返す規則の単体試験
（実装の確認事項C33、ADR-065）。

`04_doctor.md` §3、`05_複合ワークスペース仕様.md` §3、ADR-063の決定4・5、ADR-065の決定を対象にする。

- `doctor`（`--all-workspaces`と、複合ワークスペースと判定される単独の`doctor`）は、Gitの不在と設定の停止を独立した2つの原因とし、
  ルートの設定（構文、型、必須フィールド、スキーマまたはEARS-AIのメジャーバージョン）で止まっても、設定の診断に加えて`SPEC-MULTI-GIT-001`を返す。
  検査項目`git`は`blocked`である。スキーマまたはEARS-AIのメジャーバージョンが非対応なら検査項目`catalog`も`blocked`で置く。
- 構文、型、必須フィールドの不正は、有効なルートワークスペースのIDを構成できないので、全体結果の`multiWorkspace.id`は`null`で、`catalog`は置かない。
  単独の`doctor`は、読めない設定を複合ワークスペースと判定しない（ADR-063の決定4）ので、単一ワークスペースの`doctor`として扱う。
- 対照: `context`、`check`、`verify`は、設定の停止の診断だけを返す。Gitがあれば`doctor`も設定の診断だけを返す。
- 出力が`docs/03.詳細設計/schemas/result.schema.json`に適合し、`PYTHONHASHSEED`を変えても同じ出力になる。

診断の並び: 環境の発生元（`SPEC-MULTI-GIT-001`）とファイルの発生元（`workspaceId: null`）の相対順は、結果・診断・終了コード §7が定めていないので、
構文などの不正の試験は順序を固定せず、診断の集合だけを確かめる。ワークスペースIDが`platform`の設定の診断との相対順は、IDを持たない環境の発生元が先である。
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

import bitz
from bitz import check as check_mod
from bitz import context as context_mod
from bitz import doctor as doctor_mod
from bitz import verify as verify_mod
from bitz.cliargs import parse_argv

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULT_SCHEMA = REPO_ROOT / "docs" / "03.詳細設計" / "schemas" / "result.schema.json"

GIT_ABSENT = "SPEC-MULTI-GIT-001"
GIT_ABSENT_SUMMARY = "Gitのリポジトリの境界を確定できません"


def _root_yaml(*, schema: str = "1.0", ears: str = "1.0", language: str = "ja") -> str:
    return (
        f'schemaVersion: "{schema}"\nlanguage: {language}\nearsAi: "{ears}"\nworkspace:\n  id: platform\n'
        "multiWorkspace:\n  members:\n    - id: web\n      path: apps/web\n"
    )


WEB_YAML = 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\nworkspace:\n  id: web\n'
REQ = (
    "---\nid: REQ-001\ntitle: REQ\nstatus: approved\n---\n\n# REQ-001 REQ\n\n## Intent\n\n意図。\n\n## Acceptance Criteria\n\n"
    "- [REQ-001:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 秘密情報を出力しない。\n\n## Verification\n\n未証明。\n"
)

# バージョンの非対応: (名前, ルートの設定, 診断コード〈doctorとそれ以外〉, 発生元のキー)
VERSION_STOPS = {
    "ears": (_root_yaml(ears="2.0"), ("SPEC-DOCTOR-EARS-001", "SPEC-EARS-VERSION-001"), "earsAi"),
    "schema": (_root_yaml(schema="2.0"), ("SPEC-CONFIG-SCHEMA-001", "SPEC-CONFIG-SCHEMA-001"), "schemaVersion"),
}
# 構文、型、必須フィールドの不正: 有効なルートワークスペースのIDを構成できない。
INVALID_STOPS = {
    "syntax": _root_yaml() + "  : bad: [\n",
    "anchor": _root_yaml(language="&a ja"),
    "type": _root_yaml(language="5"),
    "required": _root_yaml().replace('schemaVersion: "1.0"\n', ""),
}


def _write(root: Path, rel: str, content: str) -> None:
    full = root / rel
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")


def _git(root: Path, *args: str) -> None:
    env = {**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}
    subprocess.run(["git", *args], cwd=root, env=env, check=True, capture_output=True, text=True)


def _validate_against_schema(results: list[dict]) -> None:
    """結果が公開スキーマに適合することを確かめる。Coreの環境に`jsonschema`がないため、`uv`で一時的に用意して別プロセスで検証する。"""

    uv = shutil.which("uv")
    if uv is None:
        raise unittest.SkipTest("uvがないためスキーマ適合を確認できません")
    script = (
        "import json, sys\n"
        "from jsonschema import Draft202012Validator\n"
        "schema = json.load(open(sys.argv[1], encoding='utf-8'))\n"
        "validator = Draft202012Validator(schema)\n"
        "bad = []\n"
        "for item in json.load(sys.stdin):\n"
        "    errors = [e.message for e in validator.iter_errors(item)]\n"
        "    if errors:\n"
        "        bad.append(errors[:3])\n"
        "print(json.dumps(bad, ensure_ascii=False))\n"
    )
    proc = subprocess.run(
        [uv, "run", "--quiet", "--no-project", "--with", "jsonschema==4.23.0", "python", "-I", "-c", script, str(RESULT_SCHEMA)],
        input=json.dumps(results),
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise unittest.SkipTest(f"jsonschemaを用意できません: {proc.stderr.strip()[-200:]}")
    bad = json.loads(proc.stdout)
    if bad:
        raise AssertionError(f"result.schema.jsonに適合しません: {bad}")


class _Base(unittest.TestCase):
    """ルート`platform`、メンバー`web`の複合ワークスペースの木。Gitのリポジトリにはしない（Gitなしの環境を`env`で作る）。"""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.results: list[dict] = []
        # Gitの不在: 実行ファイルを見つけられない環境、またはGitのリポジトリでない作業ツリー。
        self.no_git_env = {**os.environ, "PATH": str(self.root / "no-such-bin")}
        self.not_a_repo_env = dict(os.environ)
        self.git_envs = {"git-missing": self.no_git_env, "not-a-repository": self.not_a_repo_env}
        _write(self.root, "apps/web/.spec/bitz.yaml", WEB_YAML)
        _write(self.root, ".spec/requirements/REQ-001.md", REQ)
        _write(self.root, "docs/note.md", "メモ。\n")

    def tearDown(self):
        if self.results:
            _validate_against_schema(self.results)

    def put_root(self, yaml: str) -> None:
        _write(self.root, ".spec/bitz.yaml", yaml)

    def make_repository(self) -> None:
        """現在の木をGitのリポジトリにしてコミットする（Gitがある環境の対照）。"""

        _git(self.root, "init", "-q", "--initial-branch=main")
        _git(self.root, "config", "user.email", "t@t")
        _git(self.root, "config", "user.name", "t")
        _git(self.root, "add", ".")
        _git(self.root, "commit", "-q", "-m", "base")

    def run_op(self, module, name: str, cwd: Path, argv: tuple[str, ...], env: dict):
        parsed = parse_argv([name, *argv, "--format", "json"])
        result, code = module.run(parsed, str(cwd), env)
        self.results.append(result)
        return result, code

    def doctor_all(self, env, cwd=None):
        return self.run_op(doctor_mod, "doctor", cwd or self.root, ("--all-workspaces",), env)

    def doctor_single(self, env, cwd=None):
        return self.run_op(doctor_mod, "doctor", cwd or self.root, (), env)

    def codes(self, result) -> list[str]:
        return [d["code"] for d in result["diagnostics"]]

    def git_diagnostics(self, result) -> list[dict]:
        return [d for d in result["diagnostics"] if d["code"] == GIT_ABSENT]

    def assert_git_absent_diagnostic(self, result):
        found = self.git_diagnostics(result)
        self.assertEqual(len(found), 1, result["diagnostics"])
        self.assertEqual(found[0]["summary"], GIT_ABSENT_SUMMARY)
        self.assertEqual(found[0]["severity"], "error")
        self.assertEqual(found[0]["resultStatus"], "blocked")
        self.assertEqual(found[0]["source"], {"kind": "environment", "component": "git"})


class VersionStopWithGitAbsentTests(_Base):
    """スキーマまたはEARS-AIのメジャーバージョンが非対応で止まっても、`doctor`はGitの不在を加える（ADR-065の決定2）。"""

    def assert_stop(self, result, code, *, config_code, key):
        self.assertEqual((result["status"], code), ("blocked", 2), result["diagnostics"])
        self.assertEqual(self.codes(result)[0], GIT_ABSENT)  # IDを持たない環境の発生元が、ID`platform`の設定の診断より先
        self.assertEqual(sorted(self.codes(result)), sorted([GIT_ABSENT, config_code]))
        self.assert_git_absent_diagnostic(result)
        config = next(d for d in result["diagnostics"] if d["code"] == config_code)
        self.assertEqual(config["source"], {"kind": "file", "workspaceId": "platform", "path": ".spec/bitz.yaml", "key": key})
        self.assertEqual(config["resultStatus"], "blocked")
        # 検査項目: コアは通過、Gitと、版の非対応の`catalog`が`blocked`（`doctor` §3）。ワークスペース固有の検査項目は置かない。
        self.assertEqual(result["checks"], [
            {"name": "core", "status": "passed"}, {"name": "git", "status": "blocked"}, {"name": "catalog", "status": "blocked"}])

    def test_all_workspaces_returns_both_diagnostics(self):
        for name, (yaml, (doctor_code, _), key) in VERSION_STOPS.items():
            self.put_root(yaml)
            for label, env in self.git_envs.items():
                with self.subTest(stop=name, git=label):
                    result, code = self.doctor_all(env)
                    self.assert_stop(result, code, config_code=doctor_code, key=key)
                    self.assertEqual(result["multiWorkspace"], {"id": "platform", "path": "."})
                    self.assertEqual(result["workspaces"], [])
                    self.assertNotIn("workspace", result)

    def test_single_doctor_returns_both_diagnostics(self):
        # 単独の`doctor`の全体事前検査も同じ（`doctor` §3）。最も近い設定がルートの設定になる、ルートとサブディレクトリから実行する。
        for name, (yaml, (doctor_code, _), key) in VERSION_STOPS.items():
            self.put_root(yaml)
            for label, env in self.git_envs.items():
                for cwd in (self.root, self.root / "docs"):
                    with self.subTest(stop=name, git=label, cwd="root" if cwd == self.root else cwd.name):
                        result, code = self.doctor_single(env, cwd)
                        self.assert_stop(result, code, config_code=doctor_code, key=key)
                        self.assertEqual(result["workspace"], {"id": "platform", "path": "."})
                        self.assertNotIn("multiWorkspace", result)
                        self.assertNotIn("workspaces", result)

    def test_text_format_shows_both_diagnostics(self):
        # `--format`は表示だけを変える。既定の`text`でも、同じ2件の診断と終了コードを返す（結果・診断・終了コード §7）。
        self.put_root(VERSION_STOPS["ears"][0])
        for argv in (["doctor", "--all-workspaces"], ["doctor"]):
            with self.subTest(argv=argv):
                proc = subprocess.run(
                    [sys.executable, "-m", "bitz.cli", *argv], cwd=self.root, capture_output=True, text=True,
                    env={**self.no_git_env, "PYTHONPATH": str(Path(bitz.__file__).resolve().parents[1])},
                )
                lines = proc.stdout.splitlines()
                self.assertEqual(proc.returncode, 2, proc.stderr)
                self.assertIn("diagnostics=2", lines[0])
                self.assertEqual(sum(": SPEC-" in line for line in lines), 2, proc.stdout)
                self.assertTrue(any(GIT_ABSENT in line for line in lines))
                self.assertTrue(any("SPEC-DOCTOR-EARS-001" in line for line in lines))

    def test_member_directory_does_not_see_the_root_config_stop(self):
        # メンバーの中では、Gitなしではルートを発見できず、メンバーの設定は`multiWorkspace`を宣言しない（ADR-063の決定5）。
        # ルートの設定の停止も、`SPEC-MULTI-GIT-001`も返さず、単一ワークスペースの`doctor`（Git不在は警告）として扱う。
        self.put_root(VERSION_STOPS["ears"][0])
        # Gitの実行ファイルがなければ警告`SPEC-DOCTOR-GIT-001`、Gitはあるがリポジトリでなければ診断なし。
        expected = {"git-missing": ("passed_with_warnings", ["SPEC-DOCTOR-GIT-001"]), "not-a-repository": ("passed", [])}
        for label, env in self.git_envs.items():
            with self.subTest(git=label):
                result, code = self.doctor_single(env, self.root / "apps" / "web")
                self.assertEqual((result["status"], self.codes(result), code), (*expected[label], 0))
                self.assertEqual(result["workspace"], {"id": "web", "path": "."})


class InvalidConfigStopWithGitAbsentTests(_Base):
    """構文、型、必須フィールドの不正で止まっても、`doctor --all-workspaces`はGitの不在を加える（ADR-065の決定2）。"""

    def test_all_workspaces_returns_both_diagnostics(self):
        for name, yaml in INVALID_STOPS.items():
            self.put_root(yaml)
            for label, env in self.git_envs.items():
                with self.subTest(stop=name, git=label):
                    result, code = self.doctor_all(env)
                    # 設定の不正は`error`、Gitの不在は`blocked`。最悪値の`error`／終了コード3。
                    self.assertEqual((result["status"], code), ("error", 3), result["diagnostics"])
                    self.assertEqual(sorted(self.codes(result)), sorted(["SPEC-CONFIG-SCHEMA-001", GIT_ABSENT]))
                    self.assert_git_absent_diagnostic(result)
                    config = next(d for d in result["diagnostics"] if d["code"] == "SPEC-CONFIG-SCHEMA-001")
                    self.assertEqual(config["resultStatus"], "error")
                    # 同一性を構成できない設定の診断は`workspaceId`が`null`、`path`は`.spec/bitz.yaml`（結果・診断・終了コード §5）。
                    self.assertEqual((config["source"]["workspaceId"], config["source"]["path"]), (None, ".spec/bitz.yaml"))
                    # 有効なルートのIDを構成できないので`multiWorkspace.id`は`null`、`catalog`は置かない（`doctor` §3は版の非対応だけ）。
                    self.assertEqual(result["multiWorkspace"], {"id": None, "path": "."})
                    self.assertEqual(result["workspaces"], [])
                    self.assertEqual(result["checks"], [{"name": "core", "status": "passed"}, {"name": "git", "status": "blocked"}])

    def test_single_doctor_treats_an_unreadable_root_config_as_single_workspace(self):
        # 読めない設定は複合ワークスペースと判定しない（ADR-063の決定4）。単一ワークスペースのGit不在は警告で、`SPEC-MULTI-GIT-001`を返さない。
        for name, yaml in INVALID_STOPS.items():
            self.put_root(yaml)
            for label, env in self.git_envs.items():
                with self.subTest(stop=name, git=label):
                    result, code = self.doctor_single(env)
                    self.assertEqual((result["status"], code), ("error", 3), result["diagnostics"])
                    # Gitの実行ファイルがなければ警告`SPEC-DOCTOR-GIT-001`（検査項目`git`は`warning`）。Gitはあるがリポジトリでなければ診断なし。
                    git_missing = label == "git-missing"
                    self.assertEqual(sorted(self.codes(result)),
                                     sorted(["SPEC-CONFIG-SCHEMA-001", *(["SPEC-DOCTOR-GIT-001"] if git_missing else [])]))
                    self.assertEqual(self.git_diagnostics(result), [])
                    self.assertEqual(result["workspace"], {"id": None, "path": "."})
                    statuses = {c["name"]: c["status"] for c in result["checks"]}
                    self.assertNotIn("catalog", statuses)
                    self.assertEqual(statuses["git"], "warning" if git_missing else "passed")


class ControlTests(_Base):
    """対照: ほかの操作は設定の停止の診断だけ。Gitがあれば`doctor`も設定の診断だけ。Gitの不在だけなら1件。"""

    def operations(self):
        yield "check", check_mod, ("--full",)
        yield "check-all", check_mod, ("--all-workspaces",)
        yield "verify", verify_mod, ()
        yield "verify-all", verify_mod, ("--all-workspaces",)
        yield "context", context_mod, ("REQ-001",)

    def test_other_operations_return_only_the_config_diagnostic(self):
        stops = {name: (yaml, codes[1]) for name, (yaml, codes, _) in VERSION_STOPS.items()}
        stops.update({name: (yaml, "SPEC-CONFIG-SCHEMA-001") for name, yaml in INVALID_STOPS.items()})
        for name, (yaml, expected) in stops.items():
            self.put_root(yaml)
            for label, env in self.git_envs.items():
                for op_name, module, argv in self.operations():
                    with self.subTest(stop=name, git=label, operation=op_name):
                        result, code = self.run_op(module, op_name.split("-")[0], self.root, argv, env)
                        self.assertEqual(self.codes(result), [expected], result["diagnostics"])
                        self.assertEqual(self.git_diagnostics(result), [])
                        self.assertIn(code, (2, 3))
                        self.assertIsNone(result["revision"])

    def test_doctor_with_git_returns_only_the_config_diagnostic(self):
        stops = {name: (yaml, codes[0]) for name, (yaml, codes, _) in VERSION_STOPS.items()}
        stops.update({name: (yaml, "SPEC-CONFIG-SCHEMA-001") for name, yaml in INVALID_STOPS.items()})
        for name, (yaml, expected) in stops.items():
            self.put_root(yaml)
            self.make_repository()
            try:
                for op_name, runner in (("all-workspaces", self.doctor_all), ("single", self.doctor_single)):
                    with self.subTest(stop=name, form=op_name):
                        result, code = runner(self.not_a_repo_env)
                        self.assertEqual(self.codes(result), [expected], result["diagnostics"])
                        names = {c["name"]: c["status"] for c in result["checks"]}
                        self.assertEqual(names["git"], "passed")
            finally:
                shutil.rmtree(self.root / ".git")

    def test_git_absent_alone_is_reported_once(self):
        # 設定が正しければ従来どおり、`SPEC-MULTI-GIT-001`の1件だけ（二重に加えない）。
        self.put_root(_root_yaml())
        for label, env in self.git_envs.items():
            for runner in (self.doctor_all, self.doctor_single):
                with self.subTest(git=label, runner=runner.__name__):
                    result, code = runner(env)
                    self.assertEqual((result["status"], code), ("blocked", 2))
                    self.assertEqual(self.codes(result), [GIT_ABSENT])
                    self.assertEqual(result["checks"], [{"name": "core", "status": "passed"}, {"name": "git", "status": "blocked"}])

    def test_member_config_stop_is_not_a_root_config_stop(self):
        # メンバーの設定の不正は、ルートの設定の停止ではない。Gitなしでは従来どおり`SPEC-MULTI-GIT-001`の1件で、メンバーの診断を始めない。
        self.put_root(_root_yaml())
        _write(self.root, "apps/web/.spec/bitz.yaml", WEB_YAML.replace('earsAi: "1.0"', 'earsAi: "2.0"'))
        for env in self.git_envs.values():
            result, _ = self.doctor_all(env)
            self.assertEqual(self.codes(result), [GIT_ABSENT])
            self.assertEqual(result["workspaces"], [])


class DeterminismTests(_Base):
    def test_output_is_identical_across_hash_seeds(self):
        source = Path(bitz.__file__).resolve().parents[1]  # 試験対象のCoreのsrc（PYTHONPATHで差し替えた場合も追従する）
        cases = {**{name: yaml for name, (yaml, _, _) in VERSION_STOPS.items()}, **INVALID_STOPS}
        for name, yaml in cases.items():
            self.put_root(yaml)
            outputs = []
            for seed in ("0", "12345", "777"):
                env = {"PATH": str(self.root / "no-such-bin"), "PYTHONHASHSEED": seed, "PYTHONPATH": str(source), "HOME": str(self.root)}
                row = []
                for argv in (["doctor", "--all-workspaces"], ["doctor"]):
                    proc = subprocess.run(
                        [sys.executable, "-m", "bitz.cli", *argv, "--format", "json"],
                        cwd=self.root, env=env, capture_output=True, text=True,
                    )
                    payload = json.loads(proc.stdout)
                    payload.pop("durationMs")
                    row.append((proc.returncode, payload))
                outputs.append(row)
            with self.subTest(stop=name):
                self.assertEqual(outputs[0], outputs[1])
                self.assertEqual(outputs[0], outputs[2])
                # 診断の並びも一定である。バージョンの非対応は、全体結果で`SPEC-MULTI-GIT-001`を含む2件。
                all_workspaces = outputs[0][0][1]
                self.assertIn(GIT_ABSENT, [d["code"] for d in all_workspaces["diagnostics"]])
                self.assertEqual(len(all_workspaces["diagnostics"]), 2)


if __name__ == "__main__":
    unittest.main()
