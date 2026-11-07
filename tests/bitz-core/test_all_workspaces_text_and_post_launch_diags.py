"""全体操作のtext出力と、全体の`verify`の起動した後の診断の置き場所の単体試験（確認事項C94・C89）。

規範は、結果・診断・終了コード §7と`verify` §6である。期待値は規範から導いた値で、Coreの出力を写したものではない。

- C94（`textrender`）: `targets`は`check`／`all-workspaces`ではすべての`workspaces[].checkedDocumentCount`の和、`verify`／`all-workspaces`では
  すべての`workspaces[].targetResults.length`の和。`diagnostics`は結果の木構造に実在する診断の総数（最上位、すべての`workspaces[].diagnostics`、
  すべての`targetResults[].diagnostics`）。出力の順は最上位の診断を先に、続けてワークスペースの処理順に、ワークスペースの診断とその検証対象の診断（検証対象のID順）。
  単一ワークスペースは変わらない（対照）。
- C89（`verify`）: 起動した後の診断（`SPEC-VERIFY-TIMEOUT-001`、`SPEC-VERIFY-COMMAND-001`のシグナルと起動失敗）も、起動前の`skip-binding`と同じく、
  複合ワークスペースの全体の`verify`ではテスト割当てを所有するワークスペースの`diagnostics`へ1件だけ置き、最上位へ複製しない。
  単一ワークスペースと、複合ワークスペースの単独の操作は最上位のまま（対照）。
"""

from __future__ import annotations

import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from bitz import verify as verify_mod
from bitz.cliargs import ParsedArgs
from bitz.textrender import render_check_text, render_verify_text

SUMMARY = {
    "timeout": "コマンドが実効タイムアウト1秒で終了しませんでした",
    "signal": "コマンドがシグナルで終了しました",
    "spawn_error": "コマンドの実行形式をOSが拒否しプロセスを生成できません",
}


def _file_diag(code: str, workspace: str, path: str, severity: str = "error", summary: str = "要約") -> dict:
    status = {"error": "failed", "warning": "passed_with_warnings"}[severity]
    return {"code": code, "severity": severity, "resultStatus": status, "summary": summary,
            "source": {"kind": "file", "workspaceId": workspace, "path": path}}


def _env_diag(code: str, identifier: str, summary: str) -> dict:
    return {"code": code, "severity": "error", "resultStatus": "error", "summary": summary,
            "source": {"kind": "environment", "component": "command", "identifier": identifier}}


def _lines(text: str) -> list[str]:
    return text.splitlines()


class CheckAllWorkspacesTextTests(unittest.TestCase):
    """`check --all-workspaces`のtext: ワークスペースの診断を数えて出し、件数をJSONの結果と一致させる。"""

    RESULT = {
        "operation": "check", "status": "failed", "scope": "all-workspaces", "durationMs": 7,
        "diagnostics": [_file_diag("SPEC-MULTI-CONFIG-001", "platform", ".spec/bitz.yaml", summary="最上位")],
        "workspaces": [
            {"id": "platform", "checkedDocumentCount": 2, "diagnostics": []},
            {"id": "api", "checkedDocumentCount": 3, "diagnostics": [
                _file_diag("SPEC-CONFIG-UNKNOWN-001", "api", ".spec/bitz.yaml", "warning", "api警告"),
                _file_diag("SPEC-RELATION-MISSING-001", "api", ".spec/requirements/REQ-001.md", summary="apiエラー")]},
            {"id": "web", "checkedDocumentCount": 4, "diagnostics": [
                _file_diag("SPEC-INPUT-BOM-001", "web", ".spec/bitz.yaml", "warning", "web警告")]},
        ],
    }

    def test_summary_counts_tree_diagnostics_and_sums_checked_documents(self):
        self.assertEqual(_lines(render_check_text(self.RESULT))[0],
                         "check failed scope=all-workspaces targets=9 diagnostics=4 (7ms)")

    def test_top_level_diagnostics_come_first_then_workspaces_in_processing_order(self):
        self.assertEqual(_lines(render_check_text(self.RESULT))[1:], [
            "platform:.spec/bitz.yaml::: error: SPEC-MULTI-CONFIG-001: 最上位",
            "api:.spec/bitz.yaml::: warning: SPEC-CONFIG-UNKNOWN-001: api警告",
            "api:.spec/requirements/REQ-001.md::: error: SPEC-RELATION-MISSING-001: apiエラー",
            "web:.spec/bitz.yaml::: warning: SPEC-INPUT-BOM-001: web警告",
        ])

    def test_workspace_order_is_kept_even_when_ids_are_not_sorted(self):
        # 並べ替えず、結果の`workspaces`の順（処理順）で出す。
        result = {**self.RESULT, "diagnostics": [], "workspaces": list(reversed(self.RESULT["workspaces"]))}
        self.assertEqual([line.split(":", 1)[0] for line in _lines(render_check_text(result))[1:]], ["web", "api", "api"])

    def test_no_diagnostics_is_a_single_summary_line(self):
        result = {**self.RESULT, "status": "passed", "diagnostics": [],
                  "workspaces": [{"id": "platform", "checkedDocumentCount": 1, "diagnostics": []}]}
        self.assertEqual(render_check_text(result), "check passed scope=all-workspaces targets=1 diagnostics=0 (7ms)\n")

    def test_single_workspace_text_is_unchanged(self):
        """対照: 単一ワークスペース（`full`・`selected`・`changed`）は、最上位の診断と`checkedDocumentCount`・`selection`だけで数える。"""
        diag = _file_diag("SPEC-RELATION-MISSING-001", "root", ".spec/technical/TECH-001.md")
        for scope, extra in (("full", {"checkedDocumentCount": 3}), ("selected", {"checkedDocumentCount": 3}),
                             ("changed", {"selection": {"targetDocumentCount": 3}})):
            with self.subTest(scope=scope):
                result = {"operation": "check", "status": "failed", "scope": scope, "durationMs": 0, "diagnostics": [diag], **extra}
                self.assertEqual(render_check_text(result), (
                    f"check failed scope={scope} targets=3 diagnostics=1 (0ms)\n"
                    "root:.spec/technical/TECH-001.md::: error: SPEC-RELATION-MISSING-001: 要約\n"))


class VerifyAllWorkspacesTextTests(unittest.TestCase):
    """`verify --all-workspaces`のtext: 件数はすべての`workspaces[].targetResults.length`の和、診断は木構造の総数、順は最上位→ワークスペース→検証対象のID順。"""

    @staticmethod
    def _target(name: str, diags: list[dict]) -> dict:
        return {"target": name, "status": "blocked", "contextDigest": None, "statements": [], "bindingRefs": [], "diagnostics": diags}

    def _result(self) -> dict:
        return {
            "operation": "verify", "status": "blocked", "scope": "all-workspaces", "durationMs": 3,
            "diagnostics": [_file_diag("SPEC-VERIFY-BLOCKED-002", "platform", ".spec/bitz.yaml", summary="最上位")],
            "workspaces": [
                {"id": "platform", "targetResults": [], "commands": [], "diagnostics": [
                    _file_diag("SPEC-VERIFY-BLOCKED-002", "platform", ".spec/bitz.yaml", "warning", "platformの診断")]},
                {"id": "api", "targetResults": [self._target("api::TECH-001", [_file_diag("SPEC-VERIFY-BLOCKED-001", "api", ".spec/technical/TECH-001.md", summary="apiの検証対象")])],
                 "commands": [], "diagnostics": []},
                # 検証対象はID順（結果の並びの順）。ワークスペースの診断を先に、続けて検証対象の診断を出す。
                {"id": "web", "targetResults": [
                    self._target("web::REQ-001", [_file_diag("SPEC-VERIFY-BLOCKED-001", "web", ".spec/technical/TECH-001.md", summary="web・REQ-001の1件目"),
                                                  _file_diag("SPEC-VERIFY-BLOCKED-001", "web", ".spec/technical/TECH-002.md", summary="web・REQ-001の2件目")]),
                    self._target("web::TECH-001", [_file_diag("SPEC-VERIFY-BLOCKED-001", "web", ".spec/technical/TECH-003.md", summary="web・TECH-001")]),
                ], "commands": [], "diagnostics": [_file_diag("SPEC-CONFIG-UNKNOWN-001", "web", ".spec/bitz.yaml", "warning", "webの診断")]},
            ],
        }

    def test_summary_sums_workspace_targets_and_counts_every_diagnostic_in_the_tree(self):
        self.assertEqual(_lines(render_verify_text(self._result()))[0],
                         "verify blocked scope=all-workspaces targets=3 diagnostics=7 (3ms)")

    def test_order_is_top_level_then_workspace_diagnostics_then_its_targets(self):
        self.assertEqual([line.rsplit(": ", 1)[1] for line in _lines(render_verify_text(self._result()))[1:]], [
            "最上位", "platformの診断", "apiの検証対象", "webの診断", "web・REQ-001の1件目", "web・REQ-001の2件目", "web・TECH-001"])

    def test_targets_are_not_taken_from_a_top_level_field(self):
        # 全体操作の最上位は`targetResults`を持たないので、ワークスペースごとの`targetResults`の和だけが`targets`になる。
        result = self._result()
        self.assertNotIn("targetResults", result)
        self.assertIn("targets=3 ", _lines(render_verify_text(result))[0])

    def test_workspace_without_targets_or_diagnostics_adds_nothing(self):
        result = {"operation": "verify", "status": "passed", "scope": "all-workspaces", "durationMs": 0, "diagnostics": [],
                  "workspaces": [{"id": "platform", "targetResults": [], "commands": [], "diagnostics": []}]}
        self.assertEqual(render_verify_text(result), "verify passed scope=all-workspaces targets=0 diagnostics=0 (0ms)\n")

    def test_single_workspace_text_is_unchanged(self):
        """対照: 単一ワークスペースは最上位の診断と`targetResults`だけで数え、最上位の診断を先に、続けて検証対象の診断を出す。"""
        result = {"operation": "verify", "status": "error", "scope": "selected", "durationMs": 5,
                  "diagnostics": [_env_diag("SPEC-VERIFY-TIMEOUT-001", "root::default", SUMMARY["timeout"])],
                  "targetResults": [self._target("REQ-001", [_file_diag("SPEC-VERIFY-BLOCKED-001", "root", ".spec/technical/TECH-001.md", summary="検証対象")]),
                                    self._target("REQ-002", [])]}
        self.assertEqual(render_verify_text(result), (
            "verify error scope=selected targets=2 diagnostics=2 (5ms)\n"
            f"command:::: error: SPEC-VERIFY-TIMEOUT-001: {SUMMARY['timeout']}\n"
            "root:.spec/technical/TECH-001.md::: error: SPEC-VERIFY-BLOCKED-001: 検証対象\n"))


# --- 実リポジトリでの試験（C89と、C94の件数がJSONと一致すること） ------------------------------

ROOT_YAML = 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\nworkspace:\n  id: platform\n'
MEMBER_YAML = 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\nworkspace:\n  id: web\n'
REQ = ("---\nid: REQ-001\ntitle: REQ\nstatus: approved\n---\n\n# REQ-001 REQ\n\n## Intent\n\n意図。\n\n## Acceptance Criteria\n\n"
       "- [REQ-001:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 秘密情報を出力しない。\n\n## Verification\n\n未証明。\n")
TECH = ("---\nid: TECH-010\ntitle: TECH\nstatus: approved\nrelations:\n  refines: [platform::REQ-001:AC-01]\n"
        "tests:\n  - path: tests/test_login.py\n    covers: [platform::REQ-001:AC-01]\n    command: frontend\n---\n\n# TECH-010 TECH\n\n## Context\n\n本文。\n")
SINGLE_TECH = ("---\nid: TECH-010\ntitle: TECH\nstatus: approved\nrelations:\n  refines: [REQ-001:AC-01]\n"
               "tests:\n  - path: tests/test_login.py\n    covers: [REQ-001:AC-01]\n    command: frontend\n---\n\n# TECH-010 TECH\n\n## Context\n\n本文。\n")
# コマンドの終了の種類ごとの、コマンドの定義（`argv`）とファイル。
COMMANDS = {
    "timeout": (["/bin/sleep", "60"], None),
    "signal": (["bin/hang"], "#!/bin/sh\nkill -TERM $$\n"),
    "spawn_error": (["bin/hang"], "this file is executable but is not a program\n"),
}
CODE = {"timeout": "SPEC-VERIFY-TIMEOUT-001", "signal": "SPEC-VERIFY-COMMAND-001", "spawn_error": "SPEC-VERIFY-COMMAND-001"}


def _git(root: Path, *args: str) -> None:
    env = {**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}
    subprocess.run(["git", *args], cwd=root, env=env, check=True, capture_output=True, text=True)


def _write(root: Path, rel: str, content: str, executable: bool = False) -> None:
    full = root / rel
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")
    if executable:
        full.chmod(full.stat().st_mode | stat.S_IXUSR)


def _commit(root: Path, paths: list[str]) -> None:
    _git(root, "add", *paths)
    _git(root, "commit", "-q", "-m", "base")


def _config(kind: str) -> str:
    argv, _ = COMMANDS[kind]
    quoted = ", ".join(f'"{a}"' for a in argv)
    return f"verify:\n  commands:\n    frontend:\n      argv: [{quoted}]\n      cwd: .\n"


def _build_multi(root: Path, kind: str) -> None:
    """ルート`platform`（REQ-001）とメンバー`web`（REQ-001を`refines`するTECH-010。テスト割当て`web::frontend`を所有する）。"""
    _git(root, "init", "-q", "--initial-branch=main")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    _write(root, ".spec/bitz.yaml", ROOT_YAML + "multiWorkspace:\n  members:\n    - id: web\n      path: apps/web\n")
    _write(root, ".spec/requirements/REQ-001.md", REQ)
    _write(root, "apps/web/.spec/bitz.yaml", MEMBER_YAML + _config(kind))
    _write(root, "apps/web/.spec/technical/TECH-010.md", TECH)
    _write(root, "apps/web/tests/test_login.py", "x\n")
    script = COMMANDS[kind][1]
    paths = [".spec", "apps"]
    if script is not None:
        _write(root, "apps/web/bin/hang", script, executable=True)
    _commit(root, paths)


def _build_single(root: Path, kind: str) -> None:
    _git(root, "init", "-q", "--initial-branch=main")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    _write(root, ".spec/bitz.yaml", 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\n' + _config(kind))
    _write(root, ".spec/requirements/REQ-001.md", REQ)
    _write(root, ".spec/technical/TECH-010.md", SINGLE_TECH)
    _write(root, "tests/test_login.py", "x\n")
    script = COMMANDS[kind][1]
    if script is not None:
        _write(root, "bin/hang", script, executable=True)
    _commit(root, [".spec", "tests"] + (["bin"] if script is not None else []))


def _run(root: Path, *, all_workspaces: bool, positionals: list[str] | None = None, timeout: int = 1) -> tuple[dict, int]:
    parsed = ParsedArgs(operation="verify", positionals=positionals or [], flags={"--all-workspaces"} if all_workspaces else set(),
                        single={"--timeout": str(timeout)}, repeat={})
    return verify_mod.run(parsed, str(root), dict(os.environ))


def _tree_codes(result: dict) -> list[tuple[str, str]]:
    """(置き場所, 診断のcode)。置き場所は`top`、`ws:<ID>`、`target:<対象>`。"""
    found = [("top", d["code"]) for d in result["diagnostics"]]
    for workspace in result.get("workspaces", []):
        found += [(f"ws:{workspace['id']}", d["code"]) for d in workspace["diagnostics"]]
        for target in workspace["targetResults"]:
            found += [(f"target:{target['target']}", d["code"]) for d in target["diagnostics"]]
    for target in result.get("targetResults", []):
        found += [(f"target:{target['target']}", d["code"]) for d in target["diagnostics"]]
    return found


class PostLaunchDiagnosticPlacementTests(unittest.TestCase):
    """起動した後の診断は、全体の`verify`ではテスト割当てを所有するワークスペースの`diagnostics`へ1件だけ置き、最上位へ残さない（`verify` §6）。"""

    def _all_workspaces(self, kind: str) -> tuple[dict, int]:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        _build_multi(root, kind)
        return _run(root, all_workspaces=True)

    def test_each_post_launch_condition_is_placed_in_the_owning_workspace(self):
        for kind in COMMANDS:
            with self.subTest(kind=kind):
                result, exit_code = self._all_workspaces(kind)
                self.assertEqual((result["status"], exit_code), ("error", 3))
                # 診断は1件だけで、テスト割当てを所有する`web`にあり、要求側の`platform`にも最上位にもない（複製しない）。
                self.assertEqual(_tree_codes(result), [("ws:web", CODE[kind])])
                self.assertEqual(result["diagnostics"], [])
                web = next(w for w in result["workspaces"] if w["id"] == "web")
                self.assertEqual(web["status"], "error")
                self.assertEqual([d["source"] for d in web["diagnostics"]],
                                 [{"kind": "environment", "component": "command", "identifier": "web::frontend"}])
                self.assertEqual([c["termination"] for c in web["commands"]], [kind])

    def test_timeout_summary_and_text_output_count_the_workspace_diagnostic(self):
        result, _ = self._all_workspaces("timeout")
        self.assertEqual([d["summary"] for d in result["workspaces"][1]["diagnostics"]], [SUMMARY["timeout"]])
        text = render_verify_text(result)
        self.assertEqual(_lines(text)[0].split(" (")[0], "verify error scope=all-workspaces targets=2 diagnostics=1")
        self.assertEqual(_lines(text)[1:], [f"command:::: error: SPEC-VERIFY-TIMEOUT-001: {SUMMARY['timeout']}"])

    def test_spawn_error_placement_with_mocked_process_result(self):
        """起動失敗を、OSに依存せずモックで確かめる（`procrun.run`が`spawn_error`を返す）。"""
        outcome = {"termination": "spawn_error", "exit_code": None, "stdout_excerpt": "", "stderr_excerpt": "",
                   "stdout_truncated": False, "stderr_truncated": False, "duration_ms": 0}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _build_multi(root, "timeout")
            with mock.patch.object(verify_mod.procrun, "run", return_value=outcome) as run:
                result, exit_code = _run(root, all_workspaces=True)
            self.assertEqual(run.call_count, 1)
        self.assertEqual(exit_code, 3)
        self.assertEqual(_tree_codes(result), [("ws:web", "SPEC-VERIFY-COMMAND-001")])
        self.assertEqual([d["summary"] for d in result["workspaces"][1]["diagnostics"]], [SUMMARY["spawn_error"]])
        self.assertEqual(result["diagnostics"], [])

    def test_post_launch_and_pre_launch_diagnostics_both_go_to_their_owning_workspaces(self):
        """起動前の遮断（実行可能ファイルの不在）と起動した後の診断が1回の実行で併存しても、どちらも所有ワークスペースへ置き、最上位は空である。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _build_multi(root, "timeout")
            # `platform`のTECH-020は、実行可能ファイルのないコマンド`backend`を使うので、起動前に遮断される。
            _write(root, ".spec/bitz.yaml", ROOT_YAML + "multiWorkspace:\n  members:\n    - id: web\n      path: apps/web\n"
                   'verify:\n  commands:\n    backend:\n      argv: ["./missing"]\n      cwd: .\n')
            _write(root, ".spec/requirements/REQ-002.md", REQ.replace("REQ-001", "REQ-002"))
            _write(root, ".spec/technical/TECH-020.md", "---\nid: TECH-020\ntitle: TECH\nstatus: approved\nrelations:\n  refines: [REQ-002:AC-01]\n"
                   "tests:\n  - path: tests/t.py\n    covers: [REQ-002:AC-01]\n    command: backend\n---\n\n# TECH-020 TECH\n\n## Context\n\n本文。\n")
            _write(root, "tests/t.py", "x\n")
            _commit(root, [".spec", "tests"])
            result, _ = _run(root, all_workspaces=True)
        self.assertEqual(sorted(_tree_codes(result)), [("ws:platform", "SPEC-VERIFY-BLOCKED-001"), ("ws:web", "SPEC-VERIFY-TIMEOUT-001")])
        self.assertEqual(result["diagnostics"], [])

    def test_single_workspace_keeps_the_diagnostic_at_the_top_level(self):
        """対照: 単一ワークスペースは、起動した後の診断を最上位へ置く。"""
        for kind in COMMANDS:
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                _build_single(root, kind)
                result, exit_code = _run(root, all_workspaces=False, positionals=["REQ-001"])
                self.assertEqual(exit_code, 3)
                self.assertEqual(_tree_codes(result), [("top", CODE[kind])])
                self.assertEqual(result["diagnostics"][0]["source"]["identifier"], "root::frontend")

    def test_single_operation_in_a_multi_workspace_keeps_the_diagnostic_at_the_top_level(self):
        """対照: 複合ワークスペースの単独の操作（`--all-workspaces`ではない）は、今までどおり最上位へ置く。"""
        for kind in COMMANDS:
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                _build_multi(root, kind)
                result, exit_code = _run(root, all_workspaces=False, positionals=["REQ-001"])
                self.assertEqual(exit_code, 3)
                self.assertNotIn("workspaces", result)
                self.assertEqual(_tree_codes(result), [("top", CODE[kind])])
                self.assertEqual(result["diagnostics"][0]["source"]["identifier"], "web::frontend")


class TextCountMatchesJsonTests(unittest.TestCase):
    """全体操作の実際の結果で、textの件数が木構造の診断の総数と一致する（`text`とJSONで件数を変えない）。"""

    def test_verify_all_workspaces_text_matches_the_json_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _build_multi(root, "timeout")
            result, _ = _run(root, all_workspaces=True)
        total = len(_tree_codes(result))
        self.assertGreaterEqual(total, 1)
        first = _lines(render_verify_text(result))[0]
        self.assertIn(f" diagnostics={total} ", first)
        self.assertIn(f" targets={sum(len(w['targetResults']) for w in result['workspaces'])} ", first)
        self.assertEqual(len(_lines(render_verify_text(result))) - 1, total)


if __name__ == "__main__":
    unittest.main()
