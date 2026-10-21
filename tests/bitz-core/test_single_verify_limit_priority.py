"""複合ワークスペースの単独の`verify`が、リソースの上限を実行計画の確定後に判定する単体試験（確認事項 C40、ADR-066）。

- 複合ワークスペースの単独の`verify`（`verify <修飾ID>`、引数なし、`--workspace`）は、`--all-workspaces`と同じく、`commandDefinitionCount`を
  全体事前検査では判定せず、実行計画を確定した後（対象展開とテスト割当ての重複排除の後、コマンドを1件も起動する前）に、
  `verifyBindingCount`、`commandDefinitionCount`の順で判定する。両方が超過していれば`verifyBindingCount`を報告する
  （複合ワークスペース仕様 §7・§10）。
- ほかの次元（`specFileCount`など）は今までどおり全体事前検査で判定する。全体事前検査が非成功なら、終了コード4より診断を優先する
  （ADR-063の決定3）。`commandDefinitionCount`だけが超過し、`--workspace`のIDがカタログにないときは、全体事前検査が成功するため
  引数不正（終了コード4）になる（ADR-066のConsequences）。
- 上限の絶対値は大きいため、`multiws.HARD_LIMITS`と`verify._VERIFY_BINDING_LIMIT`を一時的に小さくして試す。
- 出力が`docs/03.詳細設計/schemas/result.schema.json`に適合し、`PYTHONHASHSEED`を変えても同じ出力になる。
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

from bitz import multiws
from bitz import verify as verify_mod
from bitz.cliargs import parse_argv
from bitz.errors import CliArgError

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULT_SCHEMA = REPO_ROOT / "docs" / "03.詳細設計" / "schemas" / "result.schema.json"
LIMIT = "SPEC-MULTI-LIMIT-001"
EMPTY_TARGETS = "SPEC-VERIFY-BLOCKED-002"
_GIT_ENV = {"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}

CONFIG = 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\n'
SOLO_YAML = (
    CONFIG + "workspace:\n  id: solo\nverify:\n  commands:\n"
    '    frontend:\n      argv: ["/bin/sh", "-c", "touch ran.marker", "{tests}"]\n      cwd: .\n'
)
ROOT_YAML = (
    CONFIG + "workspace:\n  id: platform\nmultiWorkspace:\n  members:\n"
    "    - id: web\n      path: apps/web\n    - id: api\n      path: apps/api\n"
)
API_YAML = CONFIG + "workspace:\n  id: api\n"
# `frontend`は実行すると`ran.marker`を作る。コマンドの起動の有無を、実ファイルで確かめる。`extra1`・`extra2`は成功するだけのコマンド。
WEB_YAML = (
    CONFIG + "workspace:\n  id: web\nverify:\n  commands:\n"
    '    frontend:\n      argv: ["/bin/sh", "-c", "touch ran.marker", "{tests}"]\n      cwd: .\n'
    '    extra1:\n      argv: ["/bin/true", "{tests}"]\n      cwd: .\n'
    '    extra2:\n      argv: ["/bin/true", "{tests}"]\n      cwd: .\n'
)


def _git(root: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=root, env={**os.environ, **_GIT_ENV}, check=True, capture_output=True, text=True
    )
    return proc.stdout.strip()


def _write(root: Path, rel: str, content: str) -> None:
    full = root / rel
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")


def _req(doc_id: str, status: str = "approved") -> str:
    return (
        f"---\nid: {doc_id}\ntitle: REQ\nstatus: {status}\n---\n\n# {doc_id} REQ\n\n## Intent\n\n意図。\n\n"
        "## Acceptance Criteria\n\n"
        f"- [{doc_id}:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 秘密情報を出力しない。\n\n"
        "## Verification\n\n未証明。\n"
    )


def _tech(doc_id: str, *, refines: str, test_path: str, covers: str, command: str) -> str:
    return (
        f"---\nid: {doc_id}\ntitle: TECH\nstatus: approved\n"
        f"relations:\n  refines: [{refines}]\n"
        f"tests:\n  - path: {test_path}\n    covers: [{covers}]\n    command: {command}\n---\n\n"
        f"# {doc_id} TECH\n\n## Context\n\n本文。\n"
    )


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
    """複合ワークスペース（`platform`、メンバー`web`・`api`）を作る。

    コマンド定義は`web`に3件（`frontend`・`extra1`・`extra2`）。`approved`のREQ-001に対する実行計画のテスト割当ては、既定で
    `web::frontend`の1件、`two_bindings`なら`web::frontend`と`web::extra1`の2件になる。
    """

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.env = {**os.environ, **_GIT_ENV}
        self.results: list[dict] = []
        self.addCleanup(lambda: _validate_against_schema(self.results) if self.results else None)

    def build(self, *, two_bindings: bool = False, draft_only: bool = False, same_command: bool = False) -> str:
        r = self.root
        _write(r, ".spec/bitz.yaml", ROOT_YAML)
        _write(r, ".spec/requirements/REQ-001.md", _req("REQ-001", "draft" if draft_only else "approved"))
        _write(r, "apps/web/.spec/bitz.yaml", WEB_YAML)
        _write(r, "apps/api/.spec/bitz.yaml", API_YAML)
        if not draft_only:
            _write(
                r, "apps/web/.spec/technical/TECH-010.md",
                _tech("TECH-010", refines="platform::REQ-001:AC-01", test_path="tests/test_a.py",
                      covers="platform::REQ-001:AC-01", command="frontend"),
            )
            _write(r, "apps/web/tests/test_a.py", "x\n")
            if two_bindings:
                _write(
                    r, "apps/web/.spec/technical/TECH-011.md",
                    _tech("TECH-011", refines="platform::REQ-001:AC-01", test_path="tests/test_b.py",
                          covers="platform::REQ-001:AC-01",
                          command="frontend" if same_command else "extra1"),
                )
                _write(r, "apps/web/tests/test_b.py", "x\n")
        _git(r, "init", "-q", "--initial-branch=main")
        _git(r, "config", "user.email", "t@t")
        _git(r, "config", "user.name", "t")
        _git(r, "add", "-A")
        _git(r, "commit", "-q", "-m", "base")
        self.head = _git(r, "rev-parse", "HEAD")
        return self.head

    def verify(self, *argv: str, cwd: Path | None = None):
        parsed = parse_argv(["verify", *argv, "--format", "json"])
        result, code = verify_mod.run(parsed, str(cwd or self.root), self.env)
        self.results.append(result)
        return result, code

    @property
    def marker(self) -> Path:
        return self.root / "apps" / "web" / "ran.marker"

    def assert_limit_stop(self, result: dict, code: int, dimension: str, limit: int, observed: int) -> None:
        """単独の停止結果の形（`workspace`、`revision`、`targetResults`、`commands`）と、上限の診断を確かめる。"""

        self.assertEqual((result["status"], code), ("blocked", 2), result["diagnostics"])
        self.assertEqual(result["operation"], "verify")
        self.assertNotIn("workspaces", result)
        self.assertEqual((result["targetResults"], result["commands"]), ([], []))
        self.assertEqual(result["revision"], {"commit": self.head, "dirty": False})
        self.assertEqual(len(result["diagnostics"]), 1, result["diagnostics"])
        diag = result["diagnostics"][0]
        self.assertEqual(diag["code"], LIMIT)
        self.assertEqual(diag["resultStatus"], "blocked")
        self.assertEqual(diag["source"], {"kind": "file", "workspaceId": "platform", "path": ".spec/bitz.yaml"})
        self.assertEqual(diag["evidence"], {"dimension": dimension, "limit": limit, "observedAtLeast": observed})
        self.assertFalse(self.marker.exists(), "上限で止まるときはコマンドを1件も起動しない")


class PlanPriorityTests(_Base):
    """(a)(b)(g): 実行計画を確定した後の判定と、`verifyBindingCount`の優先。"""

    # 呼び出しの形: 引数と、その結果の`workspace`・`scope`。ルートから実行する。
    VARIANTS = {
        "qualified-id": (("platform::REQ-001",), "selected"),
        "no-arguments": ((), "all"),
        "workspace-flag": (("--workspace", "platform"), "all"),
        "workspace-flag-and-id": (("--workspace", "platform", "REQ-001"), "selected"),
    }

    def test_both_exceeded_reports_verify_binding_count(self):
        self.build()
        for name, (argv, scope) in self.VARIANTS.items():
            with self.subTest(variant=name), mock.patch.dict(multiws.HARD_LIMITS, {"commandDefinitionCount": 2}), \
                    mock.patch.object(verify_mod, "_VERIFY_BINDING_LIMIT", 0):
                result, code = self.verify(*argv)
                self.assert_limit_stop(result, code, "verifyBindingCount", 0, 1)
                self.assertEqual((result["scope"], result["workspace"]), (scope, {"id": "platform", "path": "."}))

    def test_binding_count_alone_reports_verify_binding_count(self):
        self.build(two_bindings=True)
        with mock.patch.object(verify_mod, "_VERIFY_BINDING_LIMIT", 1):
            result, code = self.verify("platform::REQ-001")
        self.assert_limit_stop(result, code, "verifyBindingCount", 1, 2)

    def test_binding_count_is_the_plan_after_deduplication(self):
        # 同じコマンドへの2つのテスト割当ては、重複排除の後で1件になる。上限が1なら超過しない。
        self.build(two_bindings=True, same_command=True)
        with mock.patch.object(verify_mod, "_VERIFY_BINDING_LIMIT", 1):
            result, code = self.verify("platform::REQ-001")
        self.assertEqual((result["status"], code), ("passed", 0), result["diagnostics"])
        self.assertEqual([c["name"] for c in result["commands"]], ["frontend"])

    def test_command_definition_count_alone_is_reported_with_small_plan(self):
        self.build()
        for name, (argv, scope) in self.VARIANTS.items():
            with self.subTest(variant=name), mock.patch.dict(multiws.HARD_LIMITS, {"commandDefinitionCount": 2}):
                result, code = self.verify(*argv)
                self.assert_limit_stop(result, code, "commandDefinitionCount", 2, 3)
                self.assertEqual((result["scope"], result["workspace"]), (scope, {"id": "platform", "path": "."}))

    def test_member_working_directory_reports_member_workspace(self):
        # メンバーの配下から`verify`しても、停止結果の`workspace`は作業ワークスペース（`web`）。
        self.build()
        with mock.patch.dict(multiws.HARD_LIMITS, {"commandDefinitionCount": 2}):
            result, code = self.verify(cwd=self.root / "apps" / "web")
        self.assertEqual((result["status"], code), ("blocked", 2))
        self.assertEqual(result["workspace"], {"id": "web", "path": "apps/web"})
        self.assertEqual(result["diagnostics"][0]["evidence"]["dimension"], "commandDefinitionCount")
        self.assertFalse(self.marker.exists())

    def test_within_limits_runs_normally(self):
        self.build()
        for name, (argv, scope) in self.VARIANTS.items():
            with self.subTest(variant=name):
                self.marker.unlink(missing_ok=True)
                # 上限ちょうど（commandDefinitionCount=3、verifyBindingCount=1）は超過ではない。
                with mock.patch.dict(multiws.HARD_LIMITS, {"commandDefinitionCount": 3}), \
                        mock.patch.object(verify_mod, "_VERIFY_BINDING_LIMIT", 1):
                    result, code = self.verify(*argv)
                self.assertEqual((result["status"], code), ("passed", 0), result["diagnostics"])
                self.assertEqual(result["scope"], scope)
                self.assertEqual([c["name"] for c in result["commands"]], ["frontend"])
                self.assertEqual(len(result["targetResults"]), 1)
                self.assertTrue(self.marker.exists(), "上限内ならコマンドを起動する")

    def test_no_command_is_started_when_stopped(self):
        # プロセスの起動そのものを数える（マーカーの有無に加えて）。上限内では起動し、超過では起動しない。
        self.build()
        with mock.patch.object(verify_mod.procrun, "run", wraps=verify_mod.procrun.run) as spy:
            with mock.patch.dict(multiws.HARD_LIMITS, {"commandDefinitionCount": 2}):
                self.verify("platform::REQ-001")
            with mock.patch.object(verify_mod, "_VERIFY_BINDING_LIMIT", 0):
                self.verify("platform::REQ-001")
            self.assertEqual(spy.call_count, 0)
            self.verify("platform::REQ-001")
            self.assertEqual(spy.call_count, 1)

    def test_empty_plan_still_judges_command_definition_count(self):
        # 検証対象が0件（`approved`のREQがない）でも、`--all-workspaces`と同じく、上限を対象0件の診断より先に判定する。
        self.build(draft_only=True)
        result, code = self.verify()
        self.assertEqual((result["status"], code), ("blocked", 2))
        self.assertEqual([d["code"] for d in result["diagnostics"]], [EMPTY_TARGETS])
        with mock.patch.dict(multiws.HARD_LIMITS, {"commandDefinitionCount": 2}):
            result, code = self.verify()
        self.assert_limit_stop(result, code, "commandDefinitionCount", 2, 3)

    def test_report_is_saved_for_the_stop_result(self):
        self.build()
        with mock.patch.dict(multiws.HARD_LIMITS, {"commandDefinitionCount": 2}):
            result, code = self.verify("platform::REQ-001", "--report")
        self.assertEqual((result["status"], code), ("blocked", 2))
        saved = sorted((self.root / ".spec" / "reports").glob("*-verify*.json"))
        self.assertEqual(len(saved), 1, saved)
        self.assertEqual(json.loads(saved[0].read_text(encoding="utf-8")), result)


class PrecheckBoundaryTests(_Base):
    """(d)(e): 全体事前検査との境界。"""

    def test_unknown_workspace_with_command_definition_count_is_argument_error(self):
        # 全体事前検査が成功するため、カタログにない`--workspace`は引数不正（終了コード4）。ADR-066のConsequences。
        self.build()
        with mock.patch.dict(multiws.HARD_LIMITS, {"commandDefinitionCount": 2}):
            with self.assertRaises(CliArgError) as ctx:
                self.verify("--workspace", "nope")
        self.assertIn("nope", str(ctx.exception))
        # 上限内でも同じ（対照）。
        with self.assertRaises(CliArgError):
            self.verify("--workspace", "nope")

    def test_unknown_workspace_exits_4_through_cli(self):
        self.build()
        proc = subprocess.run(
            [sys.executable, "-c",
             "import sys\nfrom unittest import mock\nfrom bitz import multiws, cli\n"
             "with mock.patch.dict(multiws.HARD_LIMITS, {'commandDefinitionCount': 2}):\n"
             "    sys.exit(cli.main(['verify', '--workspace', 'nope', '--format', 'json']))\n"],
            cwd=self.root, env={**self.env, "PYTHONPATH": os.pathsep.join(sys.path)}, capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 4, proc.stdout + proc.stderr)

    def test_other_dimensions_stop_in_precheck_even_with_unknown_workspace(self):
        # `specFileCount`は今までどおり全体事前検査で判定する。全体事前検査が非成功なら、終了コード4より診断を優先する（ADR-063の決定3）。
        self.build()
        cases = {
            "qualified-id": ("platform::REQ-001",),
            "no-arguments": (),
            "unknown-workspace": ("--workspace", "nope"),
        }
        for name, argv in cases.items():
            # `commandDefinitionCount`も同時に超過させても、先に全体事前検査の次元（`specFileCount`）が報告される。
            with self.subTest(variant=name), mock.patch.dict(
                multiws.HARD_LIMITS, {"specFileCount": 1, "commandDefinitionCount": 2}
            ), mock.patch.object(verify_mod, "_VERIFY_BINDING_LIMIT", 0):
                result, code = self.verify(*argv)
                self.assertEqual((result["status"], code), ("blocked", 2), result["diagnostics"])
                self.assertEqual([d["code"] for d in result["diagnostics"]], [LIMIT])
                evidence = result["diagnostics"][0]["evidence"]
                self.assertEqual((evidence["dimension"], evidence["limit"]), ("specFileCount", 1))
                self.assertEqual((result["targetResults"], result["commands"]), ([], []))
                self.assertFalse(self.marker.exists())

    def test_non_composite_workspace_is_unchanged(self):
        # 複合を宣言しない単一ワークスペースには、全体事前検査も実行計画の上限の判定もない。
        r = self.root
        _write(r, ".spec/bitz.yaml", SOLO_YAML)
        _write(r, ".spec/requirements/REQ-001.md", _req("REQ-001"))
        _write(
            r, ".spec/technical/TECH-010.md",
            _tech("TECH-010", refines="REQ-001:AC-01", test_path="tests/test_a.py", covers="REQ-001:AC-01", command="frontend"),
        )
        _write(r, "tests/test_a.py", "x\n")
        _git(r, "init", "-q", "--initial-branch=main")
        _git(r, "config", "user.email", "t@t")
        _git(r, "config", "user.name", "t")
        _git(r, "add", "-A")
        _git(r, "commit", "-q", "-m", "base")
        with mock.patch.dict(multiws.HARD_LIMITS, {"commandDefinitionCount": 0, "specFileCount": 0}), \
                mock.patch.object(verify_mod, "_VERIFY_BINDING_LIMIT", 0):
            result, code = self.verify("REQ-001")
        self.assertEqual((result["status"], code), ("passed", 0), result["diagnostics"])
        self.assertEqual(result["workspace"], {"id": "solo", "path": "."})
        self.assertTrue((r / "ran.marker").exists())
        with self.assertRaises(CliArgError):
            self.verify("--workspace", "nope")


class AllWorkspacesUnchangedTests(_Base):
    """(f): `--all-workspaces`の判定は変わらない。"""

    def run_all(self):
        parsed = parse_argv(["verify", "--all-workspaces", "--format", "json"])
        result, code = verify_mod.run(parsed, str(self.root), self.env)
        self.results.append(result)
        return result, code

    def test_all_workspaces_priority_and_shape(self):
        self.build()
        cases = [
            ({"commandDefinitionCount": 2}, 10_000, "commandDefinitionCount", 2, 3),
            ({"commandDefinitionCount": 2}, 0, "verifyBindingCount", 0, 1),
            ({}, 0, "verifyBindingCount", 0, 1),
        ]
        for hard, binding_limit, dimension, limit, observed in cases:
            with self.subTest(dimension=dimension, hard=hard), mock.patch.dict(multiws.HARD_LIMITS, hard), \
                    mock.patch.object(verify_mod, "_VERIFY_BINDING_LIMIT", binding_limit):
                result, code = self.run_all()
                self.assertEqual((result["status"], code), ("blocked", 2))
                self.assertEqual((result["scope"], result["workspaces"]), ("all-workspaces", []))
                self.assertEqual(result["diagnostics"][0]["evidence"],
                                 {"dimension": dimension, "limit": limit, "observedAtLeast": observed})
                self.assertFalse(self.marker.exists())
        # 上限内なら通常どおり実行する（対象のないメンバー`api`の警告で`passed_with_warnings`になる）。
        result, code = self.run_all()
        self.assertEqual((result["status"], code), ("passed_with_warnings", 0), result["diagnostics"])
        self.assertTrue(self.marker.exists())


class DeterminismTests(_Base):
    """`PYTHONHASHSEED`を変えても、停止結果が同じこと。"""

    SCRIPT = (
        "import json, os, sys\n"
        "from unittest import mock\n"
        "from bitz import multiws, verify\n"
        "from bitz.cliargs import parse_argv\n"
        "out = []\n"
        "for limits, binding in (({'commandDefinitionCount': 2}, 10000), ({'commandDefinitionCount': 2}, 0)):\n"
        "    with mock.patch.dict(multiws.HARD_LIMITS, limits), mock.patch.object(verify, '_VERIFY_BINDING_LIMIT', binding):\n"
        "        result, code = verify.run(parse_argv(['verify', '--format', 'json']), os.getcwd(), dict(os.environ))\n"
        "    result.pop('durationMs')\n"
        "    out.append([code, result])\n"
        "print(json.dumps(out, ensure_ascii=False, sort_keys=False))\n"
    )

    def test_output_is_independent_of_hash_seed(self):
        self.build(two_bindings=True)
        outputs = {}
        for seed in ("0", "1", "12345"):
            proc = subprocess.run(
                [sys.executable, "-c", self.SCRIPT], cwd=self.root,
                env={**self.env, "PYTHONHASHSEED": seed, "PYTHONPATH": os.pathsep.join(sys.path)},
                capture_output=True, text=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            outputs[seed] = proc.stdout
        self.assertEqual(len(set(outputs.values())), 1, outputs)
        decoded = json.loads(outputs["0"])
        self.assertEqual(
            [r["diagnostics"][0]["evidence"]["dimension"] for _code, r in decoded],
            ["commandDefinitionCount", "verifyBindingCount"],
        )


if __name__ == "__main__":
    unittest.main()
