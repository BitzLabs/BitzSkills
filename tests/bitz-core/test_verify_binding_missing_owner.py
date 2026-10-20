"""複合ワークスペースの`verify`が、テスト割当ての欠落（`SPEC-VERIFY-BLOCKED-001`）の診断を所有ワークスペースごとに返す単体試験（確認事項 C23）。

コマンド名が設定に定義されていないテスト対応は、テスト割当てを構成できない条件（診断レジストリの`VERIFY-BINDING-MISSING`、継続単位`skip-target`）で、
検証対象の`diagnostics`へ置く。独立した元の原因（テストのエントリ単位）はそれぞれ主診断を持つ（診断レジストリ §2）。
診断の`source`は`workspaceId`と`path`の組で一意である（結果・診断・終了コード §4・§5）ので、複合ワークスペースで検証対象の閉包に、
別のワークスペースの同じ相対パス（例: どちらも`.spec/technical/TECH-001.md`）の文書があれば、所有ワークスペースが異なる別の原因である。

- 別のワークスペースの同じ相対パスの文書の、同じ位置（`tests[0].command`）の欠落は、2件の診断を返す（片方を落とさない）。
- 同じワークスペースの同じエントリを複数の規範文が指しても、同じ元の原因なので1件に畳む（今までどおり）。
- 単一ワークスペースの対照。
- 出力が`docs/03.詳細設計/schemas/result.schema.json`に適合すること、`PYTHONHASHSEED`を変えても出力が同じこと。
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

from bitz import verify as verify_mod
from bitz.cliargs import parse_argv

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULT_SCHEMA = REPO_ROOT / "docs" / "03.詳細設計" / "schemas" / "result.schema.json"

CONFIG = 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\n'
# 設定に定義するコマンド名は`t`だけである。文書のテスト対応は定義のない名前（`missing`・`absent`）を指す。
VERIFY = 'verify:\n  commands:\n    t:\n      argv: ["/bin/true", "{tests}"]\n      cwd: .\n'
_GIT_ENV = {"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}
TECH_PATH = ".spec/technical/TECH-001.md"


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args], cwd=root, env={**os.environ, **_GIT_ENV}, check=True, capture_output=True, text=True
    )


def _write(root: Path, rel: str, content: str) -> None:
    full = root / rel
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")


def _root_yaml(ws_id: str, members: list[tuple[str, str]]) -> str:
    text = CONFIG + f"workspace:\n  id: {ws_id}\nmultiWorkspace:\n  members:\n"
    for mid, mpath in members:
        text += f"    - id: {mid}\n      path: {mpath}\n"
    return text + VERIFY


def _single_yaml(ws_id: str) -> str:
    return CONFIG + f"workspace:\n  id: {ws_id}\n" + VERIFY


def _req(doc_id: str, *, statements: int = 1, requires: list[str] | None = None) -> str:
    front = f"---\nid: {doc_id}\ntitle: REQ\nstatus: approved\n"
    if requires:
        front += f"relations:\n  requires: [{', '.join(requires)}]\n"
    lines = "".join(
        f"- [{doc_id}:AC-{n:02d}] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 規範文{n}を満たす。\n"
        for n in range(1, statements + 1)
    )
    return (
        f"{front}---\n\n# {doc_id} REQ\n\n## Intent\n\n意図。\n\n## Acceptance Criteria\n\n{lines}\n"
        "## Verification\n\n未証明。\n"
    )


def _tech(doc_id: str, *, refines: str | None, covers: list[str], command: str) -> str:
    """規範文を持たず、`covers`を1つのテスト対応（`tests[0]`）で宣言するTECH。コマンド名は設定に定義のない`command`を指す。"""
    front = f"---\nid: {doc_id}\ntitle: TECH\nstatus: approved\n"
    if refines:
        front += f"relations:\n  refines: [{refines}]\n"
    front += f"tests:\n  - path: tests/t.py\n    covers: [{', '.join(covers)}]\n    command: {command}\n"
    return f"{front}---\n\n# {doc_id} TECH\n\n## Context\n\n本文。\n"


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


def _without_durations(value):
    """実行時間（`durationMs`）は実行ごとに変わるため、比較から除く。"""

    if isinstance(value, dict):
        return {k: _without_durations(v) for k, v in value.items() if k != "durationMs"}
    if isinstance(value, list):
        return [_without_durations(v) for v in value]
    return value


def _run_cli(cwd: Path, seed: str, *argv: str) -> str:
    """CLIを別プロセスで実行し、`durationMs`を除いた出力を返す。"""

    proc = subprocess.run(
        [sys.executable, "-m", "bitz.cli", *argv, "--format", "json"], cwd=cwd,
        env={**os.environ, "PYTHONHASHSEED": seed, "PYTHONPATH": os.pathsep.join(sys.path)},
        capture_output=True, text=True,
    )
    return json.dumps([proc.returncode, _without_durations(json.loads(proc.stdout))], ensure_ascii=False)


class _Base(unittest.TestCase):
    """一時のGitリポジトリを作り、`verify`を同一プロセスで実行して結果をスキーマ適合の検証へ集める。"""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(os.path.realpath(tmp.name))
        self.env = dict(os.environ)
        self.results: list[dict] = []
        _git(self.root, "init", "-q", "--initial-branch=main")
        _git(self.root, "config", "user.email", "t@t")
        _git(self.root, "config", "user.name", "t")
        self.build()
        _git(self.root, "add", ".")
        _git(self.root, "commit", "-q", "-m", "base")

    def build(self) -> None:
        raise NotImplementedError

    def tearDown(self):
        if self.results:
            _validate_against_schema(self.results)

    def verify(self, *argv: str):
        parsed = parse_argv(["verify", *argv, "--format", "json"])
        result, code = verify_mod.run(parsed, str(self.root), self.env)
        self.results.append(result)
        return result, code

    def target(self, result: dict, name: str) -> dict:
        """`verify <ID>`は`targetResults`、`--all-workspaces`はワークスペースごとの`targetResults`から検証対象を探す。"""
        targets = list(result.get("targetResults", []))
        for workspace in result.get("workspaces", []):
            targets += workspace["targetResults"]
        (found,) = [item for item in targets if item["target"] == name]
        return found

    @staticmethod
    def blocked(target: dict) -> list[tuple[str, str, str, str, str]]:
        """テスト割当ての欠落の診断を(所有ワークスペース, path, key, summary, 結果への効果)の並びで返す。"""
        return [
            (d["source"]["workspaceId"], d["source"]["path"], d["source"]["key"], d["summary"], d["resultStatus"])
            for d in target["diagnostics"]
            if d["code"] == "SPEC-VERIFY-BLOCKED-001"
        ]


def _member_tree(root: Path, member_id: str, member_path: str) -> None:
    _write(root, f"{member_path}/.spec/bitz.yaml", _single_yaml(member_id))
    _write(root, f"{member_path}/tests/t.py", "x\n")


class CompositeSamePathTests(_Base):
    """複合ワークスペース: `web`と`api`が同じ相対パス`.spec/technical/TECH-001.md`のTECHを持ち、どちらのテスト対応も定義のないコマンド名を指す。

    ```
    platform(ルート, 文書なし)
    web  REQ-001(MUST 1件) <- TECH-001 (refines, tests[0].command: missing)
    api  TECH-001 (refines: web::REQ-001:AC-01, tests[0].command: absent)
    ```
    """

    def build(self) -> None:
        r = self.root
        _write(r, ".spec/bitz.yaml", _root_yaml("platform", [("web", "apps/web"), ("api", "apps/api")]))
        _member_tree(r, "web", "apps/web")
        _member_tree(r, "api", "apps/api")
        _write(r, "apps/web/.spec/requirements/REQ-001.md", _req("REQ-001"))
        _write(r, f"apps/web/{TECH_PATH}",
               _tech("TECH-001", refines="REQ-001", covers=["REQ-001:AC-01"], command="missing"))
        _write(r, f"apps/api/{TECH_PATH}",
               _tech("TECH-001", refines="web::REQ-001", covers=["web::REQ-001:AC-01"], command="absent"))

    expected = [
        ("api", TECH_PATH, "tests[0].command", "コマンド名absentが設定に定義されていません", "blocked"),
        ("web", TECH_PATH, "tests[0].command", "コマンド名missingが設定に定義されていません", "blocked"),
    ]

    def test_verify_returns_one_diagnostic_per_owning_workspace(self):
        result, code = self.verify("web::REQ-001")
        self.assertEqual((result["status"], code), ("blocked", 2))
        target = self.target(result, "web::REQ-001")
        self.assertEqual(target["status"], "blocked")
        self.assertEqual(target["bindingRefs"], [])
        self.assertEqual(self.blocked(target), self.expected)
        self.assertEqual(len(target["diagnostics"]), 2)
        self.assertEqual(result["commands"], [])

    def test_verify_all_workspaces_returns_one_diagnostic_per_owning_workspace(self):
        result, code = self.verify("--all-workspaces")
        self.assertEqual((result["status"], code), ("blocked", 2))
        self.assertEqual(self.blocked(self.target(result, "web::REQ-001")), self.expected)
        # 規範文を持たないTECHが起点の対象は、自身のテスト対応の欠落だけを1件ずつ返す。
        self.assertEqual(self.blocked(self.target(result, "web::TECH-001")), self.expected[1:])
        self.assertEqual(self.blocked(self.target(result, "api::TECH-001")), self.expected[:1])

    def test_each_owning_workspace_keeps_its_own_diagnostic_when_command_names_are_the_same(self):
        """欠落しているコマンド名が同じでも、所有ワークスペースが異なれば別の原因である。"""
        _write(self.root, f"apps/api/{TECH_PATH}",
               _tech("TECH-001", refines="web::REQ-001", covers=["web::REQ-001:AC-01"], command="missing"))
        result, _ = self.verify("web::REQ-001")
        target = self.target(result, "web::REQ-001")
        self.assertEqual(
            [(w, p, k, s) for w, p, k, s, _ in self.blocked(target)],
            [("api", TECH_PATH, "tests[0].command", "コマンド名missingが設定に定義されていません"),
             ("web", TECH_PATH, "tests[0].command", "コマンド名missingが設定に定義されていません")],
        )

    def test_output_is_independent_of_hash_seed(self):
        for argv in (("verify", "web::REQ-001"), ("verify", "--all-workspaces")):
            outputs = {seed: _run_cli(self.root, seed, *argv) for seed in ("0", "1", "12345")}
            with self.subTest(argv=argv):
                self.assertEqual(len(set(outputs.values())), 1, outputs)
                self.assertIn('"workspaceId": "api"', next(iter(outputs.values())))


class CompositeRequiresTests(_Base):
    """同じ構成を`requires`で結ぶ。起点のREQが`web`のTECH-001と`api::TECH-001`を`requires`し、どちらもREQの規範文を`covers`する。"""

    def build(self) -> None:
        r = self.root
        _write(r, ".spec/bitz.yaml", _root_yaml("platform", [("web", "apps/web"), ("api", "apps/api")]))
        _member_tree(r, "web", "apps/web")
        _member_tree(r, "api", "apps/api")
        _write(r, "apps/web/.spec/requirements/REQ-001.md", _req("REQ-001", requires=["TECH-001", "api::TECH-001"]))
        _write(r, f"apps/web/{TECH_PATH}",
               _tech("TECH-001", refines=None, covers=["REQ-001:AC-01"], command="missing"))
        _write(r, f"apps/api/{TECH_PATH}",
               _tech("TECH-001", refines=None, covers=["web::REQ-001:AC-01"], command="absent"))

    def test_verify_returns_one_diagnostic_per_owning_workspace(self):
        for argv in (("web::REQ-001",), ("--all-workspaces",)):
            with self.subTest(argv=argv):
                result, code = self.verify(*argv)
                self.assertEqual((result["status"], code), ("blocked", 2))
                self.assertEqual(
                    [(w, p) for w, p, *_ in self.blocked(self.target(result, "web::REQ-001"))],
                    [("api", TECH_PATH), ("web", TECH_PATH)],
                )


class CompositeFoldTests(_Base):
    """同じワークスペースの同じエントリを複数の規範文が指しても、同じ元の原因なので所有ワークスペースごとに1件へ畳む。

    web・apiのTECH-001は、それぞれ1つのテスト対応（`tests[0]`）でREQ-001の規範文2件（AC-01・AC-02）を`covers`する。
    """

    def build(self) -> None:
        r = self.root
        _write(r, ".spec/bitz.yaml", _root_yaml("platform", [("web", "apps/web"), ("api", "apps/api")]))
        _member_tree(r, "web", "apps/web")
        _member_tree(r, "api", "apps/api")
        _write(r, "apps/web/.spec/requirements/REQ-001.md", _req("REQ-001", statements=2))
        _write(r, f"apps/web/{TECH_PATH}",
               _tech("TECH-001", refines="REQ-001", covers=["REQ-001:AC-01", "REQ-001:AC-02"], command="missing"))
        _write(r, f"apps/api/{TECH_PATH}",
               _tech("TECH-001", refines="web::REQ-001",
                     covers=["web::REQ-001:AC-01", "web::REQ-001:AC-02"], command="absent"))

    def test_one_diagnostic_per_owning_workspace(self):
        result, code = self.verify("web::REQ-001")
        self.assertEqual((result["status"], code), ("blocked", 2))
        target = self.target(result, "web::REQ-001")
        self.assertEqual(target["statements"], ["web::REQ-001:AC-01", "web::REQ-001:AC-02"])
        self.assertEqual(
            [(w, p, k) for w, p, k, *_ in self.blocked(target)],
            [("api", TECH_PATH, "tests[0].command"), ("web", TECH_PATH, "tests[0].command")],
        )

    def test_only_the_owning_workspace_when_the_other_has_no_such_document(self):
        (self.root / "apps/api" / TECH_PATH).unlink()
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-q", "-m", "drop api tech")
        result, _ = self.verify("web::REQ-001")
        self.assertEqual(
            [(w, p, k) for w, p, k, *_ in self.blocked(self.target(result, "web::REQ-001"))],
            [("web", TECH_PATH, "tests[0].command")],
        )


class SingleWorkspaceControlTests(_Base):
    """対照: 単一ワークスペースでは同じエントリを複数の規範文が指しても1件、別々のエントリ（`tests[0]`・`tests[1]`）は別の原因として2件。"""

    def build(self) -> None:
        r = self.root
        _write(r, ".spec/bitz.yaml", _single_yaml("solo"))
        _write(r, "tests/t.py", "x\n")
        _write(r, ".spec/requirements/REQ-001.md", _req("REQ-001", statements=2))
        _write(r, TECH_PATH,
               _tech("TECH-001", refines="REQ-001", covers=["REQ-001:AC-01", "REQ-001:AC-02"], command="missing"))

    def test_same_entry_pointed_by_two_statements_is_one_diagnostic(self):
        result, code = self.verify("REQ-001")
        self.assertEqual((result["status"], code), ("blocked", 2))
        target = self.target(result, "REQ-001")
        self.assertEqual(
            self.blocked(target),
            [("solo", TECH_PATH, "tests[0].command", "コマンド名missingが設定に定義されていません", "blocked")],
        )
        self.assertEqual(len(target["diagnostics"]), 1)

    def test_distinct_entries_are_distinct_causes(self):
        _write(
            self.root, TECH_PATH,
            "---\nid: TECH-001\ntitle: TECH\nstatus: approved\nrelations:\n  refines: [REQ-001]\n"
            "tests:\n  - path: tests/t.py\n    covers: [REQ-001:AC-01]\n    command: missing\n"
            "  - path: tests/t.py\n    covers: [REQ-001:AC-02]\n    command: missing\n"
            "---\n\n# TECH-001 TECH\n\n## Context\n\n本文。\n",
        )
        result, _ = self.verify("REQ-001")
        self.assertEqual(
            [(w, p, k) for w, p, k, *_ in self.blocked(self.target(result, "REQ-001"))],
            [("solo", TECH_PATH, "tests[0].command"), ("solo", TECH_PATH, "tests[1].command")],
        )


if __name__ == "__main__":
    unittest.main()
