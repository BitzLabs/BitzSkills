"""複合ワークスペースの全体事前検査で、Gitが認識する設定のパスの一覧の読取りが失敗した場合の単体試験
（複合ワークスペース仕様 §2、§8、ADR-083の`Notes`）。

全体事前検査（UNREGISTERED段階）は、基準版などのリビジョンの設定のパスの一覧（`git ls-tree -r`）と、現在のスナップショットの
追跡対象の一覧（`git ls-files`）と未追跡の一覧（`git ls-files --others`）を読む。どれかの読取りが失敗した場合（Gitの起動の失敗、
0でない終了コード、出力の形の不正）は、空の一覧として扱わず`SPEC-MULTI-GIT-001`（`blocked`）にし、全体事前検査で止まった結果と同じ形にする。

この読取りを行うのは、`--all-workspaces`の`check`、`verify`、`doctor`と、単独の`doctor`である（単独の`check`、`context`、`verify`は、
Gitが認識する設定の列挙と比較しない。`activews.select_active`の`compare_git_configs`）。対照として、成功の場合、Git不在の場合、
比較しない単独の操作が従来どおりであることを確かめる。期待値は仕様のリテラルで、Coreの出力からは導かない。
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from bitz import check as check_mod
from bitz import context as context_mod
from bitz import doctor as doctor_mod
from bitz import gitutil
from bitz import verify as verify_mod
from bitz.cliargs import parse_argv

_GIT_ENV = {"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull, "GIT_TERMINAL_PROMPT": "0"}
CONFIG = 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\n'
ROOT_CONFIG = CONFIG + "workspace:\n  id: platform\nmultiWorkspace:\n  members:\n    - id: web\n      path: apps/web\n"
MULTI_GIT = {
    "code": "SPEC-MULTI-GIT-001",
    "severity": "error",
    "resultStatus": "blocked",
    "summary": "Gitのリポジトリの境界を確定できません",
    "source": {"kind": "environment", "component": "git"},
}
REQ = (
    "---\nid: REQ-010\ntitle: 文書\nstatus: draft\n---\n\n# REQ-010 文書\n\n## Intent\n\n意図。\n\n## Acceptance Criteria\n\n"
    "- [REQ-010:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 秘密情報を出力しない。\n\n## Verification\n\n未証明。\n"
)
OPERATIONS = {"check": check_mod, "context": context_mod, "doctor": doctor_mod, "verify": verify_mod}


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, env={**os.environ, **_GIT_ENV}, check=True, capture_output=True)


def _write(root: Path, rel: str, content: str) -> None:
    full = root / rel
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")


def _is_tree_listing(argv):
    # `list_tree_config_paths`（リビジョンの全体の`git ls-tree -r`）。
    return "ls-tree" in argv and "-r" in argv


def _is_tracked_listing(argv):
    # `list_working_config_paths`の追跡対象の一覧（`git ls-files -z --full-name`）。
    return "ls-files" in argv and not ({"--others", "--stage", "--error-unmatch"} & set(argv))


def _is_untracked_listing(argv):
    return "ls-files" in argv and "--others" in argv


class _FailingRun:
    """``gitutil._run``を差し替え、``predicate``に当たる呼出しだけを``outcome``（例外、または終了コードと標準出力）にする。"""

    def __init__(self, predicate, outcome):
        self.predicate = predicate
        self.outcome = outcome
        self.real = gitutil._run
        self.hits = 0

    def __call__(self, argv, cwd, env):
        if self.predicate(argv):
            self.hits += 1
            if isinstance(self.outcome, BaseException):
                raise self.outcome
            return subprocess.CompletedProcess(argv, self.outcome[0], stdout=self.outcome[1], stderr="")
        return self.real(argv, cwd, env)


class ConfigListingFailureTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.env = {**os.environ, **_GIT_ENV}
        _git(self.root, "init", "-q", "--initial-branch=main")
        _git(self.root, "config", "user.email", "t@t")
        _git(self.root, "config", "user.name", "t")
        _write(self.root, ".spec/bitz.yaml", ROOT_CONFIG)
        _write(self.root, "apps/web/.spec/bitz.yaml", CONFIG + "workspace:\n  id: web\n")
        _write(self.root, "apps/web/.spec/requirements/REQ-010.md", REQ)
        _git(self.root, "add", "--", ".")
        _git(self.root, "commit", "-q", "-m", "base")

    def run_op(self, argv: list[str], cwd: Path | None = None, env: dict[str, str] | None = None) -> tuple[dict, int]:
        module = OPERATIONS[argv[0]]
        return module.run(parse_argv([*argv, "--format", "json"]), str(cwd or self.root), env or self.env)

    def assert_stopped(self, argv: list[str], result: dict, code: int) -> None:
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["diagnostics"], [MULTI_GIT])
        self.assertEqual(code, 2)
        if "--all-workspaces" in argv:
            # 全体事前検査で止まった結果と同じく、ワークスペースの結果を持たない。
            self.assertEqual(result["workspaces"], [])
            self.assertEqual(result["multiWorkspace"], {"id": "platform", "path": "."})
        if argv[0] == "doctor":
            top = {c["name"]: c["status"] for c in result["checks"]}
            self.assertEqual(top.get("catalog"), "blocked")
            self.assertEqual(top.get("git"), "passed")

    # 操作と、その操作の全体事前検査が行う読取り。`check --all-workspaces`は基準版（`HEAD`）、`doctor`は`HEAD`の設定のパスの一覧も読む。
    CASES = [
        (["check", "--all-workspaces"], None, ("tree", "tracked", "untracked")),
        (["verify", "--all-workspaces"], None, ("tracked", "untracked")),
        (["doctor", "--all-workspaces"], None, ("tree", "tracked", "untracked")),
        (["doctor"], "apps/web", ("tree", "tracked", "untracked")),
    ]
    PREDICATES = {"tree": _is_tree_listing, "tracked": _is_tracked_listing, "untracked": _is_untracked_listing}

    def test_each_listing_failure_stops_each_operation(self):
        outcomes = {
            "exit": (128, ""),
            "launch": OSError("起動できない"),
            "timeout": subprocess.TimeoutExpired("git", 30),
        }
        for argv, cwd, reads in self.CASES:
            for read in reads:
                for name, outcome in outcomes.items():
                    with self.subTest(argv=argv, read=read, outcome=name):
                        fake = _FailingRun(self.PREDICATES[read], outcome)
                        with mock.patch.object(gitutil, "_run", fake):
                            result, code = self.run_op(argv, self.root / cwd if cwd else None)
                        self.assertGreater(fake.hits, 0)
                        self.assert_stopped(argv, result, code)

    def test_malformed_tree_listing_stops(self):
        # 出力の形の不正（`git ls-tree`の項目にタブがない）。
        for argv in (["check", "--all-workspaces"], ["doctor", "--all-workspaces"]):
            with self.subTest(argv=argv):
                fake = _FailingRun(_is_tree_listing, (0, "壊れた出力\0"))
                with mock.patch.object(gitutil, "_run", fake):
                    result, code = self.run_op(argv)
                self.assertGreater(fake.hits, 0)
                self.assert_stopped(argv, result, code)

    def test_success_is_unchanged(self):
        # 対照: 差し替えなしでは、ワークスペースの結果を返す。
        for argv in (["check", "--all-workspaces"], ["doctor", "--all-workspaces"]):
            with self.subTest(argv=argv):
                result, code = self.run_op(argv)
                self.assertEqual([ws["id"] for ws in result["workspaces"]], ["platform", "web"])
                self.assertEqual(result["diagnostics"], [])
                self.assertEqual(code, 0)
        result, code = self.run_op(["doctor"], self.root / "apps/web")
        self.assertEqual(result["status"], "passed")

    def test_unregistered_config_is_still_reported(self):
        # 対照: 読取りが成功すれば、カタログにない設定は従来どおり`SPEC-MULTI-UNREGISTERED-001`。
        _write(self.root, "apps/other/.spec/bitz.yaml", CONFIG + "workspace:\n  id: other\n")
        result, _code = self.run_op(["doctor", "--all-workspaces"])
        self.assertEqual([d["code"] for d in result["diagnostics"]], ["SPEC-MULTI-UNREGISTERED-001"])

    def test_operations_without_the_comparison_do_not_read_the_listings(self):
        # 単独の`check`、`context`、`verify`は、Gitが認識する設定の列挙と比較しないので、この読取りの失敗の影響を受けない。
        fake = _FailingRun(lambda argv: _is_tree_listing(argv) or _is_tracked_listing(argv), (128, ""))
        with mock.patch.object(gitutil, "_run", fake):
            check_result, _ = self.run_op(["check", "--full"], self.root / "apps/web")
            context_result, _ = self.run_op(["context", "REQ-010"], self.root / "apps/web")
        self.assertEqual(fake.hits, 0)
        self.assertNotIn(MULTI_GIT, check_result["diagnostics"])
        self.assertNotIn(MULTI_GIT, context_result["diagnostics"])

    def test_git_absent_is_unchanged(self):
        # 対照: Git不在は既存の規則のまま（複合ワークスペースでは`SPEC-MULTI-GIT-001`、`doctor`の`git`は`blocked`）。
        env = {**self.env, "PATH": str(self.root / "no-git")}
        result, code = self.run_op(["doctor", "--all-workspaces"], env=env)
        self.assertEqual([d["code"] for d in result["diagnostics"]], ["SPEC-MULTI-GIT-001"])
        self.assertEqual({c["name"]: c["status"] for c in result["checks"]}.get("git"), "blocked")
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
