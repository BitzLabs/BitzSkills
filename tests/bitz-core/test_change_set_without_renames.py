"""変更集合を名前の変更の検出なしに求め、Gitの読取りの失敗をblockedにする（`check` §5、§9、ADR-083）単体試験。

- 名前の変更とコピーを検出しない（決定1）: リポジトリの設定`diff.renames`（`false`、`true`、`copies`）によらず、変更集合と`selection`が同じ。
- 件数はパスごとに数える（決定2）: 名前の変更は2つのパス、同じパスが複数の差分に現れても1つ。
- 部分クローン（`blob:none`、取得元に届かない）で仕様文書以外のブロブだけが欠けていても、引数なしの`check`、TASK境界、影響候補が働く。
- 読取りの失敗（決定3、4）: 変更集合の3つの読取りと、入れ子の判定に使う設定のパスの一覧（`list_base_config_dirs`）の失敗は
  `SPEC-GIT-CHANGES-001`、基準版の仕様文書のパスの一覧の失敗は`SPEC-GIT-BASE-001`、複合ワークスペースではどちらも`SPEC-MULTI-GIT-001`。
- 変わらないもの: ワークスペースの外との間の移動、TASK境界の移動元と移動先、ルートワークスペースのメンバーの配下の除外。

期待値は仕様のリテラルで、Coreの出力からは導かない。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from bitz import check as check_mod
from bitz import gitutil
from bitz.cliargs import parse_argv

_GIT_ENV = {"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull, "GIT_TERMINAL_PROMPT": "0"}
CONFIG = 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\n'
REQ_PATH = ".spec/requirements/REQ-001.md"
TECH_PATH = ".spec/technical/TECH-001.md"
TASK_PATH = ".spec/tasks/TASK-001.md"
CHANGES = {
    "code": "SPEC-GIT-CHANGES-001",
    "severity": "error",
    "resultStatus": "blocked",
    "summary": "変更されたパスをGitから求められません",
    "source": {"kind": "environment", "component": "git"},
}
BASE = {
    "code": "SPEC-GIT-BASE-001",
    "severity": "error",
    "resultStatus": "blocked",
    "summary": "基準版の仕様文書の内容をGitから読めません",
    "source": {"kind": "environment", "component": "git"},
}
MULTI_GIT = "SPEC-MULTI-GIT-001"
ZERO = {"changedPathCount": 0, "targetDocumentCount": 0, "excludedCodeTestPathCount": 0}


def _git(root: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=root, env={**os.environ, **_GIT_ENV}, check=True, capture_output=True, text=True
    )
    return proc.stdout.strip()


def _write(root: Path, rel: str, content: str) -> None:
    full = root / rel
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")


def _req(*, implements: list[str] | None = None, intent: str = "意図。") -> str:
    impl = f"implements: [{', '.join(implements)}]\n" if implements else ""
    return (
        f"---\nid: REQ-001\ntitle: 文書の検査\nstatus: approved\n{impl}---\n\n# REQ-001 文書の検査\n\n## Intent\n\n{intent}\n\n"
        "## Acceptance Criteria\n\n- [REQ-001:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 秘密情報を出力しない。\n\n"
        "## Verification\n\n未証明。\n"
    )


def _tech() -> str:
    return (
        "---\nid: TECH-001\ntitle: 出力の制約\nstatus: approved\nrelations:\n  requires: [REQ-001]\n---\n\n"
        "# TECH-001 出力の制約\n\n## Context\n\n本文。\n"
    )


def _task(changes: list[str]) -> str:
    lines = "".join(f"  - {c}\n" for c in changes)
    return f"---\nid: TASK-001\ntitle: 実装\nstatus: open\nchanges:\n{lines}---\n\n# TASK-001 実装\n"


LONG = "".join(f"行{i}は名前の変更の検出に使える程度に長い内容である。\n" for i in range(40))


class _Repo(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.root = self.tmp / "repo"
        self.root.mkdir()
        self.env = {**os.environ, **_GIT_ENV}
        _git(self.root, "init", "-q", "--initial-branch=main")
        _git(self.root, "config", "user.email", "t@t")
        _git(self.root, "config", "user.name", "t")

    def commit(self, message: str, *paths: str, root: Path | None = None) -> str:
        root = root or self.root
        _git(root, "add", "--", *paths)
        _git(root, "commit", "-q", "-m", message)
        return _git(root, "rev-parse", "HEAD")

    def run_check(self, *argv: str, cwd: Path | None = None) -> tuple[dict, int]:
        return check_mod.run(parse_argv(["check", *argv, "--format", "json"]), str(cwd or self.root), self.env)

    def codes(self, result: dict) -> list[tuple[str, str]]:
        return sorted((d["code"], d["source"].get("path", "")) for d in result["diagnostics"])


class RenameDetectionTests(_Repo):
    """名前の変更とコピーを検出しない（決定1）と、パスごとの件数（決定2）。"""

    def build(self) -> None:
        _write(self.root, ".spec/bitz.yaml", CONFIG)
        _write(self.root, REQ_PATH, _req(implements=["src/owned.py"]))
        _write(self.root, "src/owned.py", LONG)
        _write(self.root, "src/old.py", LONG + "old\n")
        _write(self.root, "src/source.py", LONG + "source\n")
        self.commit("base", ".")
        # ステージした名前の変更2つ（所有されるコードと、所有されないコード）と、変更した元からのコピー（`diff.renames=copies`で`C`になり得る）。
        _git(self.root, "mv", "--", "src/owned.py", "src/owned2.py")
        _git(self.root, "mv", "--", "src/old.py", "src/new.py")
        _write(self.root, "src/source.py", LONG + "source changed\n")
        _write(self.root, "src/copy.py", LONG + "source\n")
        _git(self.root, "add", "--", "src/source.py", "src/copy.py")

    def collect(self) -> list[tuple[str, str]]:
        changed = gitutil.collect_changed_paths("git", str(self.root), self.env, "HEAD", str(self.root))
        self.assertTrue(all(c.old_path is None for c in changed))
        return sorted((c.status, c.path) for c in changed)

    def test_repository_setting_does_not_change_the_change_set(self):
        self.build()
        expected_paths = [
            ("A", "src/copy.py"), ("A", "src/new.py"), ("A", "src/owned2.py"),
            ("D", "src/old.py"), ("D", "src/owned.py"), ("M", "src/source.py"),
        ]
        # 対照: このリポジトリでGitの名前の変更とコピーの検出を有効にすれば、`R`と`C`の項目が出る（入力が検出を起こす）。
        detected = _git(self.root, "-c", "diff.renames=copies", "diff", "--cached", "--name-status", "-C", "HEAD")
        self.assertIn("R100", detected)
        self.assertIn("C", "".join(line[0] for line in detected.splitlines()))
        results = []
        for setting in ("false", "true", "copies"):
            with self.subTest(setting=setting):
                _git(self.root, "config", "diff.renames", setting)
                self.assertEqual(self.collect(), expected_paths)
                result, code = self.run_check("--base", "HEAD")
                results.append((result["selection"], self.codes(result), code))
        self.assertEqual(results[0], results[1])
        self.assertEqual(results[0], results[2])
        # 6つのパス（名前の変更は2つ）。移動元の`src/owned.py`だけがREQ-001へ写り、ほかの5つは所有されない（§6、§9）。
        self.assertEqual(
            results[0][0], {"changedPathCount": 6, "targetDocumentCount": 1, "excludedCodeTestPathCount": 5}
        )
        self.assertEqual(results[0][1], [("SPEC-PATH-INVALID-001", REQ_PATH)])

    def test_same_path_in_two_diffs_counts_once(self):
        # 追加してステージした後に作業ツリーで変えたパスは、基準版からインデックスの`A`と、インデックスから作業ツリーの`M`に現れる。
        _write(self.root, ".spec/bitz.yaml", CONFIG)
        _write(self.root, REQ_PATH, _req())
        self.commit("base", ".spec")
        _write(self.root, "src/x.py", "x = 1\n")
        _git(self.root, "add", "--", "src/x.py")
        _write(self.root, "src/x.py", "x = 2\n")
        result, _code = self.run_check("--base", "HEAD")
        self.assertEqual(
            result["selection"], {"changedPathCount": 1, "targetDocumentCount": 0, "excludedCodeTestPathCount": 1}
        )


class UnchangedBehaviourTests(_Repo):
    """名前の変更を検出しなくても変わらない挙動（ワークスペースの外への写し、TASK境界、メンバーの配下の除外）。"""

    def test_moves_across_the_workspace_root_keep_only_the_inside_path(self):
        _write(self.root, "ws/.spec/bitz.yaml", CONFIG)
        _write(self.root, "ws/a.txt", LONG)
        _write(self.root, "other/b.txt", LONG + "b\n")
        self.commit("base", ".")
        _git(self.root, "mv", "--", "ws/a.txt", "other/a.txt")
        _git(self.root, "mv", "--", "other/b.txt", "ws/b.txt")
        changed = gitutil.collect_changed_paths("git", str(self.root), self.env, "HEAD", str(self.root / "ws"))
        self.assertEqual(sorted((c.status, c.path) for c in changed), [("A", "b.txt"), ("D", "a.txt")])

    def test_task_boundary_checks_both_paths_of_a_move(self):
        _write(self.root, ".spec/bitz.yaml", CONFIG)
        _write(self.root, TASK_PATH, _task(["src/new.py"]))
        _write(self.root, "src/old.py", LONG)
        self.commit("base", ".")
        _git(self.root, "mv", "--", "src/old.py", "src/new.py")
        result, code = self.run_check("TASK-001", "--base", "HEAD")
        boundary = [d["source"]["path"] for d in result["diagnostics"] if d["code"] == "SPEC-TASK-BOUNDARY-001"]
        self.assertEqual(boundary, ["src/old.py"])
        self.assertEqual(code, 1)

    def test_root_workspace_excludes_member_paths_of_a_move(self):
        _write(self.root, ".spec/bitz.yaml", CONFIG + "workspace:\n  id: platform\nmultiWorkspace:\n  members:\n    - id: web\n      path: apps/web\n")
        _write(self.root, "apps/web/.spec/bitz.yaml", CONFIG + "workspace:\n  id: web\n")
        _write(self.root, "docs/a.txt", LONG)
        self.commit("base", ".")
        _git(self.root, "mv", "--", "docs/a.txt", "apps/web/a.txt")
        result, _code = self.run_check("--base", "HEAD", "--workspace", "platform")
        # ルートワークスペースは、メンバーの配下（移動先）を所有しない。移動元の`docs/a.txt`だけを数える。
        self.assertEqual(
            result["selection"], {"changedPathCount": 1, "targetDocumentCount": 0, "excludedCodeTestPathCount": 1}
        )


class PartialCloneTests(_Repo):
    """部分クローンで仕様文書以外のブロブだけが欠けていても、変更集合を求められる（決定1の`Consequences`）。"""

    def build(self) -> tuple[Path, str]:
        _git(self.root, "config", "uploadpack.allowFilter", "true")
        _write(self.root, ".spec/bitz.yaml", CONFIG)
        _write(self.root, REQ_PATH, _req(implements=["src/a.py"]))
        _write(self.root, TECH_PATH, _tech())
        _write(self.root, TASK_PATH, _task(["docs/added.txt", REQ_PATH]))
        _write(self.root, "src/a.py", "a = 1\n")
        _write(self.root, "docs/gone.txt", LONG)
        base = self.commit("base", ".")
        # 基準版の後に、`docs/gone.txt`を削除し、似た内容の`docs/added.txt`を足す（名前の変更の検出は削除したブロブを読む）。
        _git(self.root, "rm", "-q", "--", "docs/gone.txt")
        _write(self.root, "docs/added.txt", LONG + "追記\n")
        self.commit("move", ".")
        clone = self.tmp / "clone"
        subprocess.run(
            ["git", "clone", "-q", "--filter=blob:none", f"file://{self.root}", str(clone)],
            env=self.env, check=True, capture_output=True,
        )
        shutil.move(str(self.root), str(self.tmp / "moved"))
        # 欠けているのは基準版の`docs/gone.txt`だけ（仕様文書は`HEAD`と同じなのでチェックアウトで取得済み）。
        gone = _git(clone, "rev-parse", f"{base}:docs/gone.txt")
        missing = subprocess.run(
            ["git", "rev-list", "--objects", "--all", "--missing=print"],
            cwd=clone, env={**self.env, "GIT_NO_LAZY_FETCH": "1"}, check=True, capture_output=True, text=True,
        ).stdout
        self.assertEqual({line[1:] for line in missing.splitlines() if line.startswith("?")}, {gone})
        # 対照: 名前の変更を検出する`git diff`は、遅延取得をしなければこのクローンで失敗する。
        detect = subprocess.run(
            ["git", "diff", "-M", "--name-status", "--cached", base],
            cwd=clone, env=gitutil.git_env(self.env), capture_output=True,
        )
        self.assertNotEqual(detect.returncode, 0)
        # 作業ツリーでREQ-001の説明文を変える（意味は変えない。TECH-001への影響候補になる）。
        _write(clone, REQ_PATH, _req(implements=["src/a.py"], intent="意図。補足した。"))
        return clone, base

    def test_changed_scope_task_boundary_and_impact_work(self):
        clone, base = self.build()
        result, code = self.run_check("--base", base, cwd=clone)
        # `docs/gone.txt`、`docs/added.txt`、REQ-001の3つのパス。REQ-001だけが所有文書で、ほかの2つは所有されない。
        self.assertEqual(
            result["selection"], {"changedPathCount": 3, "targetDocumentCount": 1, "excludedCodeTestPathCount": 2}
        )
        self.assertEqual(self.codes(result), [("SPEC-IMPACT-OUTDATED-001", TECH_PATH)])
        self.assertEqual(code, 0)

        task, task_code = self.run_check("TASK-001", "--base", base, cwd=clone)
        boundary = [d["source"]["path"] for d in task["diagnostics"] if d["code"] == "SPEC-TASK-BOUNDARY-001"]
        self.assertEqual(boundary, ["docs/gone.txt"])
        self.assertEqual(task["status"], "failed")
        self.assertEqual(task_code, 1)


class _FailingRun:
    """``gitutil._run``を差し替え、``predicate``に当たるGitの呼出しだけを``outcome``にする。"""

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


def _is_cached_diff(argv):
    return "diff" in argv and "--cached" in argv


def _is_worktree_diff(argv):
    return "diff" in argv and "--cached" not in argv


def _is_untracked(argv):
    return "ls-files" in argv and "--others" in argv


def _is_config_dirs(argv):
    return "ls-tree" in argv and "-r" not in argv


class ReadFailureTests(_Repo):
    """読取りの失敗は、空の結果として扱わず`blocked`にする（決定3、4）。"""

    def build(self) -> None:
        _write(self.root, ".spec/bitz.yaml", CONFIG)
        _write(self.root, REQ_PATH, _req(implements=["src/a.py"]))
        _write(self.root, TASK_PATH, _task(["src/"]))
        _write(self.root, "src/a.py", "a = 1\n")
        self.commit("base", ".")
        _write(self.root, "src/a.py", "a = 2\n")

    def assert_blocked(self, result: dict, code: int, diagnostic: dict) -> None:
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["diagnostics"], [diagnostic])
        self.assertEqual(code, 2)

    def test_each_change_set_read_failure_is_blocked(self):
        self.build()
        cases = [
            ("cached diff exit", _is_cached_diff, (128, "")),
            ("worktree diff exit", _is_worktree_diff, (128, "")),
            ("untracked exit", _is_untracked, (128, "")),
            ("cached diff launch", _is_cached_diff, OSError("起動できない")),
            ("untracked launch", _is_untracked, subprocess.TimeoutExpired("git", 30)),
            ("malformed diff", _is_worktree_diff, (0, "M\0")),
            ("rename item", _is_cached_diff, (0, "R100\0a\0b\0M\0")),
        ]
        for name, predicate, outcome in cases:
            for argv in (("--base", "HEAD"), ("--full", "--base", "HEAD"), ("REQ-001", "--base", "HEAD")):
                with self.subTest(case=name, argv=argv):
                    fake = _FailingRun(predicate, outcome)
                    with mock.patch.object(gitutil, "_run", fake):
                        result, code = self.run_check(*argv)
                    self.assertGreater(fake.hits, 0)
                    self.assert_blocked(result, code, CHANGES)
                    if argv[0] == "--base":
                        self.assertEqual(result["selection"], ZERO)
                    else:
                        self.assertEqual((result["checkedDocumentCount"], result["checkedStatementCount"]), (0, 0))

    def test_task_boundary_read_failures_are_blocked(self):
        # TASK境界の変更集合と、入れ子の判定に使う設定のパスの一覧（`list_base_config_dirs`の`git ls-tree`）。
        self.build()
        for name, predicate in (("changes", _is_worktree_diff), ("config dirs", _is_config_dirs)):
            with self.subTest(case=name):
                fake = _FailingRun(predicate, (128, ""))
                with mock.patch.object(gitutil, "_run", fake):
                    result, code = self.run_check("TASK-001", "--base", "HEAD")
                self.assertGreater(fake.hits, 0)
                self.assert_blocked(result, code, CHANGES)

    def test_config_dirs_malformed_output_raises(self):
        self.build()
        fake = _FailingRun(_is_config_dirs, (0, "壊れた出力\0"))
        with mock.patch.object(gitutil, "_run", fake), self.assertRaises(gitutil.GitChangesError):
            gitutil.list_base_config_dirs("git", str(self.root), self.env, "HEAD", str(self.root), ["src"])

    def test_base_spec_listing_failure_is_git_base(self):
        self.build()
        with mock.patch.object(gitutil, "list_base_spec_blobs", return_value=None):
            result, code = self.run_check("--base", "HEAD")
        self.assert_blocked(result, code, BASE)

    def test_success_is_not_blocked(self):
        # 対照: 差し替えなしでは通常どおり（REQ-001が`src/a.py`を所有する）。
        self.build()
        result, code = self.run_check("--base", "HEAD")
        self.assertEqual(result["selection"], {"changedPathCount": 1, "targetDocumentCount": 1, "excludedCodeTestPathCount": 0})
        self.assertEqual(code, 0)

    def test_git_absent_degradation_is_unchanged(self):
        # Git不在の縮退（安全な入出力・互換性 §8）は、この規則の対象外。
        self.build()
        result, _code = check_mod.run(
            parse_argv(["check", "--format", "json"]), str(self.root), {**self.env, "PATH": str(self.tmp / "no-git")}
        )
        self.assertEqual(result["scope"], "full")
        self.assertEqual([d["code"] for d in result["diagnostics"]], ["SPEC-GIT-DEGRADED-001"])


class MultiWorkspaceReadFailureTests(_Repo):
    """複合ワークスペースの操作では、変更集合の読取りの失敗を`SPEC-MULTI-GIT-001`にする（決定4）。"""

    def build(self) -> None:
        _write(self.root, ".spec/bitz.yaml", CONFIG + "workspace:\n  id: platform\nmultiWorkspace:\n  members:\n    - id: web\n      path: apps/web\n")
        _write(self.root, "apps/web/.spec/bitz.yaml", CONFIG + "workspace:\n  id: web\n")
        _write(self.root, f"apps/web/{REQ_PATH}", _req(implements=["src/a.py"]))
        _write(self.root, "apps/web/src/a.py", "a = 1\n")
        self.commit("base", ".")
        _write(self.root, "apps/web/src/a.py", "a = 2\n")

    def test_single_operation_in_a_member(self):
        self.build()
        fake = _FailingRun(_is_worktree_diff, (128, ""))
        with mock.patch.object(gitutil, "_run", fake):
            result, code = self.run_check("--base", "HEAD", cwd=self.root / "apps/web")
        self.assertGreater(fake.hits, 0)
        self.assertEqual([d["code"] for d in result["diagnostics"]], [MULTI_GIT])
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["selection"], ZERO)
        self.assertEqual(code, 2)

    def test_all_workspaces(self):
        self.build()
        fake = _FailingRun(_is_worktree_diff, (128, ""))
        with mock.patch.object(gitutil, "_run", fake):
            result, code = self.run_check("--all-workspaces", "--base", "HEAD")
        self.assertGreater(fake.hits, 0)
        self.assertEqual([d["code"] for d in result["diagnostics"]], [MULTI_GIT])
        self.assertEqual(result["workspaces"], [])
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(code, 2)

    def test_all_workspaces_without_failure(self):
        # 対照: 差し替えなしでは、ワークスペースの結果を返す。
        self.build()
        result, _code = self.run_check("--all-workspaces", "--base", "HEAD")
        self.assertEqual([ws["id"] for ws in result["workspaces"]], ["platform", "web"])


if __name__ == "__main__":
    unittest.main()
