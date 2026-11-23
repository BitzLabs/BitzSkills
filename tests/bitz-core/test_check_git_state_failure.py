"""`check`のリポジトリのルート、作業ツリーの状態、`HEAD`の参照の読取りの失敗（`check` §5、ADR-083の`Notes`）の単体試験。

- F-1: 変更集合のパスを写すためのリポジトリのルートの読取り（`rev-parse --show-toplevel`）が失敗したら、`cwd`で代えずに止める。
- R-2: `revision.dirty`を決める作業ツリーの状態の読取り（`status --porcelain`）が失敗したら、`false`にせずに止める。
- R-3: `HEAD`がコミットを指さない場合は、Gitがその参照の不在を示したとき（コミットのないリポジトリ）だけ、コミットのないリポジトリとして扱う。
  壊れた参照、参照の先のコミットの欠落は止める。
- F-2: `head_is_unborn`の`symbolic-ref`の失敗の経路（参照のファイルが壊れた複合ワークスペースの`doctor`は`blocked`）。

止める診断は、単一ワークスペースで`SPEC-GIT-CHANGES-001`、複合ワークスペースで`SPEC-MULTI-GIT-001`（どちらも`blocked`）。
対照は、成功、Git不在、コミットのないリポジトリ、リポジトリの外。期待値は仕様のリテラルで、Coreの出力からは導かない。
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from bitz import check as check_mod
from bitz import doctor as doctor_mod
from bitz import gitutil
from bitz.cliargs import parse_argv

_GIT_ENV = {"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull, "GIT_TERMINAL_PROMPT": "0"}
CONFIG = 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\n'
ROOT_CONFIG = CONFIG + "workspace:\n  id: platform\nmultiWorkspace:\n  members:\n    - id: web\n      path: apps/web\n"
REQ_PATH = ".spec/requirements/REQ-001.md"
TASK_PATH = ".spec/tasks/TASK-001.md"
CHANGES = {
    "code": "SPEC-GIT-CHANGES-001",
    "severity": "error",
    "resultStatus": "blocked",
    "summary": "変更されたパスをGitから求められません",
    "source": {"kind": "environment", "component": "git"},
}
MULTI_GIT = "SPEC-MULTI-GIT-001"
ZERO = {"changedPathCount": 0, "targetDocumentCount": 0, "excludedCodeTestPathCount": 0}


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, env={**os.environ, **_GIT_ENV}, check=True, capture_output=True)


def _write(root: Path, rel: str, content: str) -> None:
    full = root / rel
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")


def _req(doc_id: str = "REQ-001") -> str:
    return (
        f"---\nid: {doc_id}\ntitle: 文書\nstatus: approved\nimplements: [src/a.py]\n---\n\n# {doc_id} 文書\n\n## Intent\n\n意図。\n\n"
        f"## Acceptance Criteria\n\n- [{doc_id}:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 秘密情報を出力しない。\n\n"
        "## Verification\n\n未証明。\n"
    )


class _FailingRun:
    """``gitutil._run``を差し替え、``predicate``に当たる呼出しだけを終了コード128にする。"""

    def __init__(self, predicate):
        self.predicate = predicate
        self.real = gitutil._run
        self.hits = 0

    def __call__(self, argv, cwd, env):
        if self.predicate(argv):
            self.hits += 1
            return subprocess.CompletedProcess(argv, 128, stdout="", stderr="")
        return self.real(argv, cwd, env)


def _is_toplevel(argv):
    return "rev-parse" in argv and "--show-toplevel" in argv


def _is_status(argv):
    return "status" in argv and "--porcelain" in argv


class _Repo(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / "repo"
        self.root.mkdir()
        self.env = {**os.environ, **_GIT_ENV}
        _git(self.root, "init", "-q", "--initial-branch=main")
        _git(self.root, "config", "user.email", "t@t")
        _git(self.root, "config", "user.name", "t")

    def commit(self) -> None:
        _git(self.root, "add", "--", ".")
        _git(self.root, "commit", "-q", "-m", "base")

    def run_check(self, *argv: str, cwd: Path | None = None) -> tuple[dict, int]:
        return check_mod.run(parse_argv(["check", *argv, "--format", "json"]), str(cwd or self.root), self.env)

    def break_head(self, content: str) -> None:
        (self.root / ".git/refs/heads/main").write_text(content)


class SingleWorkspaceTests(_Repo):
    """ワークスペースはリポジトリのルートの下位`ws/`にある（リポジトリのルートを`cwd`で代えると、パスを写し違える）。"""

    def setUp(self):
        super().setUp()
        self.ws = self.root / "ws"
        _write(self.ws, ".spec/bitz.yaml", CONFIG)
        _write(self.ws, REQ_PATH, _req())
        _write(self.ws, TASK_PATH, "---\nid: TASK-001\ntitle: 実装\nstatus: open\nchanges:\n  - src/\n---\n\n# TASK-001 実装\n")
        _write(self.ws, "src/a.py", "a = 1\n")
        self.commit()
        # REQ-001が所有する`src/a.py`を消す（正常時は、所有文書のREQ-001が対象になり、実装パスの不在で`failed`）。
        os.remove(self.ws / "src/a.py")

    def assert_blocked(self, result: dict, code: int) -> None:
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["diagnostics"], [CHANGES])
        self.assertEqual(code, 2)

    def test_success_control(self):
        result, code = self.run_check("--base", "HEAD", cwd=self.ws)
        self.assertEqual(result["selection"], {"changedPathCount": 1, "targetDocumentCount": 1, "excludedCodeTestPathCount": 0})
        self.assertEqual(result["status"], "failed")
        self.assertEqual(code, 1)

    def test_toplevel_failure_in_change_set_paths_is_blocked(self):
        # F-1: 変更集合のパスを写す経路の`show_toplevel`だけを失敗させる（`collect_changed_paths`、`list_base_config_dirs`、
        # `_ls_files_others_z`、基準版の一覧の`_repo_root_relative_offset`と`_toplevel_or_cwd`）。
        for argv in (("--base", "HEAD"), ("--full", "--base", "HEAD"), ("REQ-001", "--base", "HEAD"), ("TASK-001", "--base", "HEAD")):
            with self.subTest(argv=argv):
                with mock.patch.object(gitutil, "show_toplevel", return_value=None):
                    result, code = self.run_check(*argv, cwd=self.ws)
                self.assert_blocked(result, code)
                if argv[0] == "--base":
                    self.assertEqual(result["selection"], ZERO)

    def test_toplevel_failure_in_the_revision_is_blocked(self):
        fake = _FailingRun(_is_toplevel)
        real_run = subprocess.run

        def run(argv, *a, **kw):
            if isinstance(argv, list) and "--show-toplevel" in argv:
                return subprocess.CompletedProcess(argv, 128, stdout="", stderr="fatal: 読めない\n")
            return real_run(argv, *a, **kw)

        with mock.patch.object(gitutil, "_run", fake), mock.patch.object(subprocess, "run", run):
            result, code = self.run_check("--base", "HEAD", cwd=self.ws)
        self.assert_blocked(result, code)
        self.assertIsNone(result["revision"])

    def test_each_path_mapping_read_refuses_to_fall_back_to_cwd(self):
        # F-1: リポジトリのルートを使う各経路が、それぞれ単独で`cwd`へ代えないこと（`_repo_root_relative_offset`と`_toplevel_or_cwd`）。
        cwd, ws = str(self.ws), str(self.ws)
        calls = {
            "collect_changed_paths": lambda: gitutil.collect_changed_paths("git", cwd, self.env, "HEAD", ws),
            "list_base_config_dirs": lambda: gitutil.list_base_config_dirs("git", cwd, self.env, "HEAD", ws, ["src"]),
            "_ls_files_others_z": lambda: gitutil._ls_files_others_z("git", cwd, self.env, strict=True),
            "list_base_spec_blobs": lambda: gitutil.list_base_spec_blobs("git", cwd, self.env, "HEAD", ws),
        }
        for name, call in calls.items():
            with self.subTest(read=name):
                with mock.patch.object(gitutil, "show_toplevel", return_value=None), \
                        self.assertRaises(gitutil.GitToplevelError):
                    call()
        # 対照: 読めれば、ワークスペースのルートからの相対のパスを返す。
        self.assertEqual([(c.status, c.path) for c in calls["collect_changed_paths"]()], [("D", "src/a.py")])

    def test_head_that_git_does_not_report_absent_is_blocked(self):
        # R-3: `HEAD`をコミットへ解決できず、Gitが参照の不在を示さない場合（ここでは解決だけを失敗させる）は止める。
        real = gitutil.resolve_commit

        def resolve(executable, cwd, env, rev):
            return None if rev == "HEAD" else real(executable, cwd, env, rev)

        with mock.patch.object(gitutil, "resolve_commit", resolve):
            result, code = self.run_check("--full", cwd=self.ws)
        self.assert_blocked(result, code)

    def test_status_failure_is_blocked(self):
        # R-2: `revision.dirty`を偽にしない。
        fake = _FailingRun(_is_status)
        with mock.patch.object(gitutil, "_run", fake):
            result, code = self.run_check("--base", "HEAD", cwd=self.ws)
        self.assertGreater(fake.hits, 0)
        self.assert_blocked(result, code)
        self.assertEqual(result["selection"], ZERO)

    def test_broken_head_reference_is_blocked(self):
        # R-3: 壊れた参照（中身が不正）と、参照の先のコミットの欠落。
        for content in ("garbage\n", "1" * 40 + "\n"):
            with self.subTest(content=content.strip()[:8]):
                self.break_head(content)
                for argv in (("--base", "HEAD"), ("--full",)):
                    result, code = self.run_check(*argv, cwd=self.ws)
                    self.assert_blocked(result, code)

    def test_git_absent_control(self):
        result, _code = check_mod.run(
            parse_argv(["check", "--format", "json"]), str(self.ws), {**self.env, "PATH": str(self.root / "no-git")}
        )
        self.assertEqual(result["scope"], "full")
        self.assertIn("SPEC-GIT-DEGRADED-001", [d["code"] for d in result["diagnostics"]])
        self.assertIsNone(result["revision"])


class CommitlessAndOutsideTests(unittest.TestCase):
    """対照: コミットのないリポジトリと、リポジトリの外は、従来どおり`revision: null`の全体検査へ縮退する。"""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.env = {**os.environ, **_GIT_ENV}
        _write(self.root, ".spec/bitz.yaml", CONFIG)

    def check(self) -> dict:
        return check_mod.run(parse_argv(["check", "--format", "json"]), str(self.root), self.env)[0]

    def test_commitless_repository(self):
        _git(self.root, "init", "-q", "--initial-branch=main")
        self.assertTrue(gitutil.head_is_unborn("git", str(self.root), self.env))
        result = self.check()
        self.assertEqual((result["scope"], result["status"], result["revision"], result["diagnostics"]), ("full", "passed", None, []))

    def test_outside_a_repository(self):
        self.assertIsNone(gitutil.repository_toplevel("git", str(self.root), self.env))
        result = self.check()
        self.assertEqual((result["scope"], result["status"], result["revision"], result["diagnostics"]), ("full", "passed", None, []))


class MultiWorkspaceTests(_Repo):
    def setUp(self):
        super().setUp()
        _write(self.root, ".spec/bitz.yaml", ROOT_CONFIG)
        _write(self.root, "apps/web/.spec/bitz.yaml", CONFIG + "workspace:\n  id: web\n")
        _write(self.root, "apps/web/.spec/requirements/REQ-010.md", _req("REQ-010"))
        _write(self.root, "apps/web/src/a.py", "a = 1\n")
        self.commit()
        os.remove(self.root / "apps/web/src/a.py")

    def runs(self) -> list[tuple[tuple[str, ...], Path]]:
        # 単独の操作はルートで`--workspace web`を指定する（ルートの設定が複合ワークスペースを宣言する）。
        return [
            (("--base", "HEAD"), self.root / "apps/web"),
            (("--workspace", "web", "--base", "HEAD"), self.root),
            (("--all-workspaces", "--base", "HEAD"), self.root),
        ]

    def assert_multi_blocked(self, argv, result: dict, code: int) -> None:
        self.assertEqual([d["code"] for d in result["diagnostics"]], [MULTI_GIT])
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(code, 2)
        if "--all-workspaces" in argv:
            self.assertEqual(result["workspaces"], [])

    def test_success_control(self):
        for argv, cwd in self.runs():
            with self.subTest(argv=argv):
                result, code = self.run_check(*argv, cwd=cwd)
                self.assertEqual(result["status"], "failed")
                self.assertEqual(code, 1)

    def test_toplevel_failure(self):
        for argv, cwd in self.runs()[1:]:
            with self.subTest(argv=argv):
                with mock.patch.object(gitutil, "show_toplevel", return_value=None):
                    result, code = self.run_check(*argv, cwd=cwd)
                self.assert_multi_blocked(argv, result, code)
        # メンバーのディレクトリからの単独の操作では、リポジトリのルートを読めないと複合ワークスペースの宣言を見つけられず
        # （複合ワークスペース仕様 §3。最も近い設定のメンバーは`multiWorkspace`を宣言しない）、単一ワークスペースとして止まる。
        with mock.patch.object(gitutil, "show_toplevel", return_value=None):
            result, code = self.run_check("--base", "HEAD", cwd=self.root / "apps/web")
        self.assertEqual(result["diagnostics"], [CHANGES])
        self.assertEqual(code, 2)

    def test_toplevel_failure_in_the_change_set_only(self):
        # 全体事前検査と`revision`は成功し、変更集合のパスを写す経路だけでリポジトリのルートを読めない。
        real = gitutil._repo_root_relative_offset

        def offset(executable, cwd, env, workspace_root, toplevel=None):
            raise gitutil.GitToplevelError("読めない")

        for argv, cwd in self.runs():
            with self.subTest(argv=argv):
                with mock.patch.object(gitutil, "_repo_root_relative_offset", offset):
                    result, code = self.run_check(*argv, cwd=cwd)
                self.assert_multi_blocked(argv, result, code)
        self.assertIsNotNone(real)

    def test_status_failure(self):
        for argv, cwd in self.runs():
            with self.subTest(argv=argv):
                fake = _FailingRun(_is_status)
                with mock.patch.object(gitutil, "_run", fake):
                    result, code = self.run_check(*argv, cwd=cwd)
                self.assertGreater(fake.hits, 0)
                self.assert_multi_blocked(argv, result, code)

    def test_broken_head_reference(self):
        for content in ("garbage\n", "1" * 40 + "\n"):
            self.break_head(content)
            for argv, cwd in self.runs():
                with self.subTest(content=content.strip()[:8], argv=argv):
                    result, code = self.run_check(*argv, cwd=cwd)
                    self.assert_multi_blocked(argv, result, code)

    def test_doctor_with_garbage_reference_is_blocked(self):
        # F-2: 参照のファイルが壊れていると`symbolic-ref`が失敗する。コミットのないリポジトリとせず、読めないとする。
        self.break_head("garbage\n")
        with self.assertRaises(gitutil.GitReadError):
            gitutil.head_is_unborn("git", str(self.root), self.env)
        result, code = doctor_mod.run(parse_argv(["doctor", "--all-workspaces", "--format", "json"]), str(self.root), self.env)
        self.assertEqual(result["status"], "blocked")
        self.assertIn(MULTI_GIT, [d["code"] for d in result["diagnostics"]])
        self.assertEqual(code, 2)

    def test_detached_head_is_not_unborn(self):
        # F-2: 切り離した`HEAD`（`symbolic-ref`は枝の名前を返さない）がコミットを解決できなければ、読めないとする。
        (self.root / ".git/HEAD").write_text("2" * 40 + "\n")
        with self.assertRaises(gitutil.GitReadError):
            gitutil.head_is_unborn("git", str(self.root), self.env)


if __name__ == "__main__":
    unittest.main()
