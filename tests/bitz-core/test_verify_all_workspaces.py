"""`verify`の複合ワークスペース対応（Step 5C）の単体試験。

`02_SPECモデル/05_複合workspace仕様.md` §8・§9・§10、`03_操作仕様/03_verify.md` §10を対象にする。
`tests/bitz-core/test_verify.py`は単一ワークスペースだけを対象にするため、本ファイルは
`--all-workspaces`のメンバーの集約・横断するテスト割当ての1回の実行・`verifyBindingCount`の上限の優先判定、
および修飾した検証対象（単独の呼び出しでの横断するコンテキスト）を扱う。
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from bitz import multiws
from bitz import verify as verify_mod
from bitz.cliargs import ParsedArgs

ROOT_YAML = 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\nworkspace:\n  id: platform\n'
MEMBER_YAML = 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\nworkspace:\n  id: {wid}\n'


def _git_env() -> dict[str, str]:
    return {**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}


def _git(root, *args) -> None:
    subprocess.run(["git", *args], cwd=root, env=_git_env(), check=True, capture_output=True, text=True)


def _init_repo(root: Path) -> None:
    _git(root, "init", "-q", "--initial-branch=main")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")


def _write(root: Path, rel: str, content: str) -> None:
    full = root / rel
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")


def _req(doc_id: str, title: str = "REQ", status: str = "approved") -> str:
    return (
        f"---\nid: {doc_id}\ntitle: {title}\nstatus: {status}\n---\n\n# {doc_id} {title}\n\n"
        "## Intent\n\n意図。\n\n## Acceptance Criteria\n\n"
        f"- [{doc_id}:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 秘密情報を出力しない。\n\n"
        "## Verification\n\n未証明。\n"
    )


def _tech_doc_unit(doc_id: str, *, refines: str, test_path: str, covers: str, command: str) -> str:
    return (
        f"---\nid: {doc_id}\ntitle: TECH\nstatus: approved\n"
        f"relations:\n  refines: [{refines}]\n"
        f"tests:\n  - path: {test_path}\n    covers: [{covers}]\n    command: {command}\n---\n\n"
        f"# {doc_id} TECH\n\n## Context\n\n本文。\n"
    )


def _run_all(root, *, report=False, timeout=None) -> tuple[dict, int]:
    flags = {"--all-workspaces"}
    if report:
        flags.add("--report")
    single = {}
    if timeout is not None:
        single["--timeout"] = str(timeout)
    parsed = ParsedArgs(operation="verify", positionals=[], flags=flags, single=single, repeat={})
    return verify_mod.run(parsed, str(root), dict(os.environ))


class SharedBindingExecutesOnceTests(unittest.TestCase):
    """MULTI-013と同じ形: 2つの独立した検証対象が同じ（ワークスペース, コマンド）の組のテスト割当てを共有する場合、
    テスト割当ての実行は1回だけであり、実体は所有ワークスペースの``commands[]``へ1回だけ置かれる（verify.md §4）。
    """

    def test_shared_binding_runs_once_and_is_owned_by_one_member(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            _write(
                root, ".spec/bitz.yaml",
                ROOT_YAML + "multiWorkspace:\n  members:\n    - id: web\n      path: apps/web\n",
            )
            _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
            _write(
                root, "apps/web/.spec/bitz.yaml",
                MEMBER_YAML.format(wid="web")
                + 'verify:\n  commands:\n    frontend:\n      argv: ["/bin/true", "{tests}"]\n      cwd: .\n',
            )
            _write(
                root, "apps/web/.spec/technical/TECH-010.md",
                _tech_doc_unit(
                    "TECH-010", refines="platform::REQ-001:AC-01", test_path="tests/test_login.py",
                    covers="platform::REQ-001:AC-01", command="frontend",
                ),
            )
            (root / "apps/web/tests").mkdir(parents=True, exist_ok=True)
            (root / "apps/web/tests/test_login.py").write_text("x\n", encoding="utf-8")
            _git(root, "add", "-A")
            _git(root, "commit", "-q", "-m", "base")

            result, exit_code = _run_all(root)
            self.assertEqual(exit_code, 0, result)
            self.assertEqual(result["status"], "passed")

            platform_ws = next(w for w in result["workspaces"] if w["id"] == "platform")
            web_ws = next(w for w in result["workspaces"] if w["id"] == "web")

            # REQ-001（`platform`）とTECH-010（`web`）の両方が同じテスト割当て "web::frontend" を要求する。
            self.assertEqual(platform_ws["targetResults"][0]["bindingRefs"], ["web::frontend"])
            self.assertEqual(web_ws["targetResults"][0]["bindingRefs"], ["web::frontend"])

            # コマンドの実体は所有ワークスペース（`web`）の `commands[]` に 1 回だけ置かれ、`platform`側は空。
            self.assertEqual(platform_ws["commands"], [])
            self.assertEqual(len(web_ws["commands"]), 1)
            self.assertEqual(web_ws["commands"][0]["bindingId"], "web::frontend")


class MemberZeroTargetTests(unittest.TestCase):
    """verify.md §10「ワークスペース単位の引数なしの対象が0件の場合、`SPEC-VERIFY-BLOCKED-002`を
    重大度`warning`としてメンバーの結果を`passed_with_warnings`にする。複合ワークスペース全体の対象が0件の場合だけ
    重大度`error`、結果への効果`blocked`とする」。
    """

    def _repo_with_empty_member(self, root: Path) -> None:
        _init_repo(root)
        _write(
            root, ".spec/bitz.yaml",
            ROOT_YAML + "multiWorkspace:\n  members:\n    - id: web\n      path: apps/web\n"
            "    - id: api\n      path: services/api\n",
        )
        _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
        _write(
            root, "apps/web/.spec/bitz.yaml",
            MEMBER_YAML.format(wid="web")
            + 'verify:\n  commands:\n    frontend:\n      argv: ["/bin/true", "{tests}"]\n      cwd: .\n',
        )
        _write(
            root, "apps/web/.spec/technical/TECH-010.md",
            _tech_doc_unit(
                "TECH-010", refines="platform::REQ-001:AC-01", test_path="tests/test_login.py",
                covers="platform::REQ-001:AC-01", command="frontend",
            ),
        )
        (root / "apps/web/tests").mkdir(parents=True, exist_ok=True)
        (root / "apps/web/tests/test_login.py").write_text("x\n", encoding="utf-8")
        # `api`は文書を持たない（既定の対象0件）。
        _write(root, "services/api/.spec/bitz.yaml", MEMBER_YAML.format(wid="api"))
        _git(root, "add", "-A")
        _git(root, "commit", "-q", "-m", "base")

    def test_member_with_zero_targets_is_warning_not_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._repo_with_empty_member(root)

            result, exit_code = _run_all(root)
            self.assertEqual(exit_code, 0, result)
            self.assertEqual(result["status"], "passed_with_warnings")
            api_ws = next(w for w in result["workspaces"] if w["id"] == "api")
            self.assertEqual(api_ws["status"], "passed_with_warnings")
            self.assertEqual(api_ws["targetResults"], [])
            self.assertEqual(api_ws["commands"], [])
            self.assertEqual(len(api_ws["diagnostics"]), 1)
            self.assertEqual(api_ws["diagnostics"][0]["code"], "SPEC-VERIFY-BLOCKED-002")
            self.assertEqual(api_ws["diagnostics"][0]["severity"], "warning")
            # 全体は`api`単独の警告では`blocked`にならない（全体が0件のときだけ`blocked`）。
            self.assertNotEqual(result["status"], "blocked")

    def test_all_members_zero_targets_is_blocked_overall(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            _write(
                root, ".spec/bitz.yaml",
                ROOT_YAML + "multiWorkspace:\n  members:\n    - id: web\n      path: apps/web\n",
            )
            _write(root, "apps/web/.spec/bitz.yaml", MEMBER_YAML.format(wid="web"))
            _git(root, "add", "-A")
            _git(root, "commit", "-q", "-m", "base")

            result, exit_code = _run_all(root)
            self.assertEqual(exit_code, 2)
            self.assertEqual(result["status"], "blocked")
            self.assertEqual(len(result["diagnostics"]), 1)
            self.assertEqual(result["diagnostics"][0]["code"], "SPEC-VERIFY-BLOCKED-002")
            self.assertEqual(result["diagnostics"][0]["severity"], "error")
            for w in result["workspaces"]:
                self.assertEqual(w["status"], "passed_with_warnings")


class VerifyBindingCountPriorityTests(unittest.TestCase):
    """複合ワークスペース仕様 §10「`verifyBindingCount`は`commandDefinitionCount`の部分集合...複数の
    次元が同時に超過する場合は、`verify`の実行計画の次元を優先して報告する」。
    """

    def test_verify_binding_limit_reports_verify_binding_count_not_command_definition_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            _write(
                root, ".spec/bitz.yaml",
                ROOT_YAML + "multiWorkspace:\n  members:\n    - id: web\n      path: apps/web\n",
            )
            _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
            _write(
                root, "apps/web/.spec/bitz.yaml",
                MEMBER_YAML.format(wid="web")
                + 'verify:\n  commands:\n    frontend:\n      argv: ["/bin/true", "{tests}"]\n      cwd: .\n',
            )
            _write(
                root, "apps/web/.spec/technical/TECH-010.md",
                _tech_doc_unit(
                    "TECH-010", refines="platform::REQ-001:AC-01", test_path="tests/test_login.py",
                    covers="platform::REQ-001:AC-01", command="frontend",
                ),
            )
            (root / "apps/web/tests").mkdir(parents=True, exist_ok=True)
            (root / "apps/web/tests/test_login.py").write_text("x\n", encoding="utf-8")
            _git(root, "add", "-A")
            _git(root, "commit", "-q", "-m", "base")

            # このfixtureの`verifyBindingCount`は1（"web::frontend"のみ）。上限を1未満（0）へ
            # 一時的に下げ、`verifyBindingCount`を優先する判定の経路（`SPEC-MULTI-LIMIT-001`、
            # `dimension: verifyBindingCount`）が正しく選ばれることを確認する
            # （`commandDefinitionCount`の一般の事前検査は`skip_limit_dimensions`で迂回している）。
            with mock.patch.object(verify_mod, "_VERIFY_BINDING_LIMIT", 0):
                result, exit_code = _run_all(root)

            self.assertEqual(exit_code, 2)
            self.assertEqual(result["status"], "blocked")
            self.assertEqual(result["workspaces"], [])
            self.assertEqual(len(result["diagnostics"]), 1)
            diag = result["diagnostics"][0]
            self.assertEqual(diag["code"], "SPEC-MULTI-LIMIT-001")
            self.assertEqual(diag["evidence"]["dimension"], "verifyBindingCount")
            self.assertEqual(diag["evidence"]["limit"], 0)
            self.assertGreaterEqual(diag["evidence"]["observedAtLeast"], 1)


class CommandDefinitionCountDeferredTests(unittest.TestCase):
    """複合ワークスペース仕様 §10「`verifyBindingCount`は`commandDefinitionCount`の部分集合…複数の
    次元が同時に超過する場合は、`verify`の実行計画の次元を優先して報告する」の是正の確認。

    `commandDefinitionCount`だけが超過する場合は`verify`もそれを`SPEC-MULTI-LIMIT-001`で遮断し、
    両方が同時に超過する場合だけ`verifyBindingCount`を優先する。判定はテスト割当ての実行計画の確定後、
    コマンドを1件も起動する前に行う（`_run_all_workspaces_members`が`_plan_and_run_bindings`より
    前に判定する）。
    """

    def _repo_with_extra_unused_commands(self, root: Path) -> None:
        _init_repo(root)
        _write(
            root, ".spec/bitz.yaml",
            ROOT_YAML + "multiWorkspace:\n  members:\n    - id: web\n      path: apps/web\n",
        )
        _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
        _write(
            root, "apps/web/.spec/bitz.yaml",
            MEMBER_YAML.format(wid="web")
            + "verify:\n  commands:\n"
            + '    frontend:\n      argv: ["/bin/true", "{tests}"]\n      cwd: .\n'
            + '    extra1:\n      argv: ["/bin/true"]\n      cwd: .\n'
            + '    extra2:\n      argv: ["/bin/true"]\n      cwd: .\n',
        )
        _write(
            root, "apps/web/.spec/technical/TECH-010.md",
            _tech_doc_unit(
                "TECH-010", refines="platform::REQ-001:AC-01", test_path="tests/test_login.py",
                covers="platform::REQ-001:AC-01", command="frontend",
            ),
        )
        (root / "apps/web/tests").mkdir(parents=True, exist_ok=True)
        (root / "apps/web/tests/test_login.py").write_text("x\n", encoding="utf-8")
        _git(root, "add", "-A")
        _git(root, "commit", "-q", "-m", "base")

    def test_command_definition_count_alone_blocks_verify(self):
        # `commandDefinitionCount`=3（`frontend`/`extra1`/`extra2`）。実際に必要なテスト割当ては"web::frontend"の
        # 1件だけなので`verifyBindingCount`は上限内のまま。`commandDefinitionCount`の上限だけを2へ
        # 下げ、その超過だけで`verify`が遮断されることを確認する（コマンドは1件も起動しない）。
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._repo_with_extra_unused_commands(root)

            with mock.patch.dict(multiws.HARD_LIMITS, {"commandDefinitionCount": 2}):
                result, exit_code = _run_all(root)

            self.assertEqual(exit_code, 2, result)
            self.assertEqual(result["status"], "blocked")
            self.assertEqual(result["workspaces"], [])
            self.assertEqual(len(result["diagnostics"]), 1)
            diag = result["diagnostics"][0]
            self.assertEqual(diag["code"], "SPEC-MULTI-LIMIT-001")
            self.assertEqual(diag["evidence"]["dimension"], "commandDefinitionCount")
            self.assertEqual(diag["evidence"]["limit"], 2)
            self.assertEqual(diag["evidence"]["observedAtLeast"], 3)

    def test_both_exceeded_reports_verify_binding_count_not_command_definition_count(self):
        # `commandDefinitionCount`（3>2）と`verifyBindingCount`（1>0）を同時に超過させ、
        # 報告される次元が`verifyBindingCount`の優先であることを確認する。
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._repo_with_extra_unused_commands(root)

            with mock.patch.dict(multiws.HARD_LIMITS, {"commandDefinitionCount": 2}), \
                 mock.patch.object(verify_mod, "_VERIFY_BINDING_LIMIT", 0):
                result, exit_code = _run_all(root)

            self.assertEqual(exit_code, 2, result)
            diag = result["diagnostics"][0]
            self.assertEqual(diag["code"], "SPEC-MULTI-LIMIT-001")
            self.assertEqual(diag["evidence"]["dimension"], "verifyBindingCount")

    def test_check_general_precheck_still_enforces_command_definition_count(self):
        # `verify`だけが`commandDefinitionCount`の一般の事前検査を迂回する（`skip_limit_dimensions`）。
        # `check`が使う既定の呼び出し（`skip`の指定なし）は従来どおり`commandDefinitionCount`を検査する。
        from bitz import gitutil

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._repo_with_extra_unused_commands(root)

            env = dict(os.environ)
            git = gitutil.detect_git(str(root), env)
            with mock.patch.dict(multiws.HARD_LIMITS, {"commandDefinitionCount": 2}):
                pre = multiws.precheck(str(root), git, env)

            self.assertFalse(pre.ok)
            self.assertEqual(len(pre.diagnostics), 1)
            self.assertEqual(pre.diagnostics[0].code, "SPEC-MULTI-LIMIT-001")
            self.assertEqual(pre.diagnostics[0].evidence["dimension"], "commandDefinitionCount")


class SkipLimitDimensionsTests(unittest.TestCase):
    """`multiws._first_exceeded`の``skip_dimensions``（`verify`専用の迂回、Step 5C追加分）。"""

    def test_skipped_dimension_is_not_reported_but_others_still_are(self):
        totals = {
            "specFileCount": 0, "inputBytes": 0, "statementCount": 0,
            "relationEdgeCount": 0, "traceEntryCount": 0,
            "commandDefinitionCount": multiws.HARD_LIMITS["commandDefinitionCount"] + 1,
        }
        self.assertIsNone(multiws._first_exceeded(totals, frozenset({"commandDefinitionCount"})))
        self.assertEqual(multiws._first_exceeded(totals, frozenset()), "commandDefinitionCount")


if __name__ == "__main__":
    unittest.main()
