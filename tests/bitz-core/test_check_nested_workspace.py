"""単一ワークスペースのTASK境界から入れ子のワークスペースを除く処理と、予約した`.spec/journal`・`.spec/plans`の単体試験（ADR-074）。

適合fixture（`SINGLE-184-*`・`SINGLE-185-*`・`MULTI-070-01`）で表しにくい次の点を、実際のGitリポジトリで確かめる。

- 入れ子のワークスペースが仕様文書を持つ、`sandbox/<名前>/`の実際の置き方での外側の`check <TASK>`
- 基準版にだけある設定（入れ子のディレクトリ全体を作業ツリーから消した場合）と、ワークスペースのルートがリポジトリのルートより下の場合
- 深い入れ子、途中のディレクトリがシンボリックリンクの場合、パスに`*`を含む場合（`git ls-tree`のパスを字句どおりに扱う）
- 入れ子から外へのリネーム、複合ワークスペースの経路（`exclude_nested=False`）で規則を変えないこと
- 性能の目安: 境界の外の候補がなければ判定しない、候補の祖先だけを見て関係のないツリーを走査しない、基準版の問い合わせを分割する
"""

import os
import subprocess
import tempfile
import time
import unittest
from unittest import mock

from bitz import check as check_mod
from bitz import document as document_mod
from bitz import gitutil
from bitz.cliargs import ParsedArgs


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _init_repo(root):
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test")
    _git(root, "config", "core.autocrlf", "false")


def _commit(root, message="base"):
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", message)


def _write(root, rel_path, content):
    full = os.path.join(root, *rel_path.split("/"))
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(content)


def _bitz_yaml() -> str:
    return 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\n'


def _task(changes: list[str]) -> str:
    lines = "".join(f"  - {c}\n" for c in changes)
    return (
        "---\nid: TASK-001\ntitle: 実装\nstatus: open\nchanges:\n"
        f"{lines}---\n\n# TASK-001 実装\n"
    )


def _req(doc_id: str) -> str:
    return (
        f"---\nid: {doc_id}\ntitle: 試し\nstatus: draft\n---\n\n"
        f"# {doc_id} 試し\n\n## Intent\n\n意図。\n\n## Acceptance Criteria\n\n"
        f"- [{doc_id}:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 秘密情報を出力しない。\n\n"
        "## Verification\n\n未証明。\n"
    )


def _outer_workspace(root, prefix=""):
    _write(root, f"{prefix}.spec/bitz.yaml", _bitz_yaml())
    _write(root, f"{prefix}.spec/tasks/TASK-001.md", _task(["src/"]))
    _write(root, f"{prefix}src/inside.py", "x = 1\n")


def _check_task(cwd):
    parsed = ParsedArgs(operation="check", positionals=["TASK-001"], flags=set(), single={"--base": "HEAD"}, repeat={})
    return check_mod.run(parsed, cwd, dict(os.environ))


def _boundary_paths(result):
    return [d["source"]["path"] for d in result["diagnostics"] if d["code"] == "SPEC-TASK-BOUNDARY-001"]


class NestedWorkspaceBoundaryTests(unittest.TestCase):
    def test_sandbox_workspace_with_spec_documents_does_not_break_outer_task(self):
        # `sandbox/exp1/`に仕様文書を持つ独立のワークスペースを置き、その中で文書・コード・結果を変えても、
        # 外側の`check TASK-001`は境界の外にしない。入れ子の中の`check`は入れ子を独立のワークスペースとして扱う。
        with tempfile.TemporaryDirectory() as root:
            _init_repo(root)
            _outer_workspace(root)
            _write(root, "sandbox/exp1/.spec/bitz.yaml", _bitz_yaml())
            _write(root, "sandbox/exp1/.spec/requirements/REQ-001.md", _req("REQ-001"))
            _write(root, "sandbox/exp1/result.md", "結果\n")
            _commit(root)

            _write(root, "sandbox/exp1/.spec/requirements/REQ-001.md", _req("REQ-001") + "\n追記\n")
            _write(root, "sandbox/exp1/.spec/requirements/REQ-002.md", _req("REQ-002"))  # 未追跡
            _write(root, "sandbox/exp1/result.md", "結果2\n")
            _write(root, "sandbox/exp1/.spec/journal/2026-11-18.md", "経過\n")
            _write(root, "src/inside.py", "x = 2\n")

            result, exit_code = _check_task(root)
            self.assertEqual(result["status"], "passed", result["diagnostics"])
            self.assertEqual(exit_code, 0)

            inner, inner_exit = check_mod.run(
                ParsedArgs(operation="check", positionals=[], flags={"--full"}, single={}, repeat={}),
                os.path.join(root, "sandbox", "exp1"),
                dict(os.environ),
            )
            self.assertEqual(inner["status"], "passed", inner["diagnostics"])
            self.assertEqual(inner["checkedDocumentCount"], 2)
            self.assertEqual(inner_exit, 0)

    def test_config_only_in_base_after_removing_whole_nested_directory(self):
        # 基準版にだけ設定がある（入れ子のディレクトリ全体を作業ツリーから消した）場合も、削除を除く。
        with tempfile.TemporaryDirectory() as root:
            _init_repo(root)
            _outer_workspace(root)
            _write(root, "sandbox/exp1/.spec/bitz.yaml", _bitz_yaml())
            _write(root, "sandbox/exp1/a/b/note.md", "メモ\n")
            _write(root, "sandbox/exp2/note.md", "メモ\n")
            _commit(root)

            _git(root, "rm", "-q", "-r", "sandbox/exp1")
            os.remove(os.path.join(root, "sandbox", "exp2", "note.md"))

            result, _ = _check_task(root)
            self.assertEqual(_boundary_paths(result), ["sandbox/exp2/note.md"])

    def test_config_only_in_base_with_workspace_below_repository_root(self):
        # ワークスペースのルートがリポジトリのルートより下（`app`）でも、基準版の設定をリポジトリ相対のパスで調べる。
        with tempfile.TemporaryDirectory() as root:
            _init_repo(root)
            _outer_workspace(root, "app/")
            _write(root, "app/sandbox/x/.spec/bitz.yaml", _bitz_yaml())
            _write(root, "app/sandbox/x/note.md", "メモ\n")
            # リポジトリのルートの直下にも同じ相対パスの入れ子を置き、取り違えないことを確かめる。
            _write(root, "sandbox/y/.spec/bitz.yaml", _bitz_yaml())
            _write(root, "app/sandbox/y/note.md", "メモ\n")
            _commit(root)

            _git(root, "rm", "-q", "-r", "app/sandbox/x/.spec")
            _write(root, "app/sandbox/x/note.md", "メモ2\n")
            _write(root, "app/sandbox/y/note.md", "メモ2\n")

            result, _ = _check_task(os.path.join(root, "app"))
            self.assertEqual(_boundary_paths(result), ["sandbox/y/note.md"])

    def test_deep_nesting_and_sibling_outside(self):
        with tempfile.TemporaryDirectory() as root:
            _init_repo(root)
            _outer_workspace(root)
            _write(root, "a/b/c/d/e/.spec/bitz.yaml", _bitz_yaml())
            _write(root, "a/b/c/d/e/f/g/h/deep.md", "1\n")
            _write(root, "a/b/c/d/e2/f/near.md", "1\n")
            _write(root, "a/b/c/d/e/f/g/h/i/.spec/bitz.yaml", _bitz_yaml())
            _write(root, "a/b/c/d/e/f/g/h/i/j/deeper.md", "1\n")
            _commit(root)

            for rel in ("a/b/c/d/e/f/g/h/deep.md", "a/b/c/d/e2/f/near.md", "a/b/c/d/e/f/g/h/i/j/deeper.md"):
                _write(root, rel, "2\n")

            result, _ = _check_task(root)
            self.assertEqual(_boundary_paths(result), ["a/b/c/d/e2/f/near.md"])

    def test_symlinked_ancestor_directory_is_not_followed(self):
        # 作業ツリーで途中のディレクトリがシンボリックリンクになり、リンク先に`.spec/bitz.yaml`があっても、たどらない。
        with tempfile.TemporaryDirectory() as root:
            _init_repo(root)
            _outer_workspace(root)
            _write(root, "sb/exp/note.md", "1\n")
            _write(root, "real/exp/.spec/bitz.yaml", _bitz_yaml())
            _commit(root)

            _git(root, "rm", "-q", "-r", "--cached", "sb")
            os.remove(os.path.join(root, "sb", "exp", "note.md"))
            os.rmdir(os.path.join(root, "sb", "exp"))
            os.rmdir(os.path.join(root, "sb"))
            os.symlink("real", os.path.join(root, "sb"))

            result, _ = _check_task(root)
            self.assertEqual(sorted(_boundary_paths(result)), ["sb", "sb/exp/note.md"])

    def test_glob_characters_in_path_are_literal_for_base_lookup(self):
        # 基準版の設定の問い合わせはパスを字句どおりに扱い、`s*`が`sx`に一致しない。
        with tempfile.TemporaryDirectory() as root:
            _init_repo(root)
            _outer_workspace(root)
            _write(root, "s*/.spec/bitz.yaml", _bitz_yaml())
            _write(root, "s*/note.md", "1\n")
            _write(root, "sx/note.md", "1\n")
            _commit(root)

            _git(root, "rm", "-q", "s*/.spec/bitz.yaml")
            _write(root, "s*/note.md", "2\n")
            _write(root, "sx/note.md", "2\n")

            result, _ = _check_task(root)
            self.assertEqual(_boundary_paths(result), ["sx/note.md"])

    def test_rename_out_of_nested_workspace_reports_only_destination(self):
        with tempfile.TemporaryDirectory() as root:
            _init_repo(root)
            _outer_workspace(root)
            _write(root, "sandbox/exp1/.spec/bitz.yaml", _bitz_yaml())
            _write(root, "sandbox/exp1/moved.md", "移す内容の行\n" * 5)
            _commit(root)

            os.makedirs(os.path.join(root, "docs"))
            _git(root, "mv", "sandbox/exp1/moved.md", "docs/moved.md")

            result, _ = _check_task(root)
            self.assertEqual(_boundary_paths(result), ["docs/moved.md"])

    def test_multi_workspace_path_keeps_rule(self):
        # 複合ワークスペースの経路（`exclude_nested=False`）では入れ子を除かない（規則を変えない）。
        with tempfile.TemporaryDirectory() as root:
            _init_repo(root)
            _outer_workspace(root)
            _write(root, "sandbox/exp1/.spec/bitz.yaml", _bitz_yaml())
            _write(root, "sandbox/exp1/note.md", "1\n")
            _commit(root)
            _write(root, "sandbox/exp1/note.md", "2\n")

            git = gitutil.detect_git(root, dict(os.environ))
            base = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True
            ).stdout.strip()
            entry = document_mod.DocEntry(
                path=".spec/tasks/TASK-001.md", kind="TASK", doc_id="TASK-001", frontmatter={"changes": ["src/"]}
            )
            kept = check_mod._task_boundary_diagnostics(
                entry, git, root, dict(os.environ), base, "root", root, exclude_nested=False
            )
            self.assertEqual([d.source["path"] for d in kept], ["sandbox/exp1/note.md"])
            excluded = check_mod._task_boundary_diagnostics(
                entry, git, root, dict(os.environ), base, "root", root, exclude_nested=True
            )
            self.assertEqual(excluded, [])


class NestedWorkspacePerformanceTests(unittest.TestCase):
    def test_no_candidate_outside_boundary_skips_detection(self):
        with tempfile.TemporaryDirectory() as root:
            _init_repo(root)
            _outer_workspace(root)
            _write(root, "sandbox/exp1/.spec/bitz.yaml", _bitz_yaml())
            _commit(root)
            _write(root, "src/inside.py", "x = 2\n")

            with mock.patch.object(check_mod, "_nested_workspace_paths", wraps=check_mod._nested_workspace_paths) as spy:
                result, _ = _check_task(root)
            self.assertEqual(result["diagnostics"], [])
            spy.assert_not_called()

    def test_only_candidate_ancestors_are_examined(self):
        # 関係のない大きなツリーがあっても、`lstat`は候補の祖先の数で決まり、ツリーの大きさによらない。
        with tempfile.TemporaryDirectory() as root:
            _init_repo(root)
            _outer_workspace(root)
            for i in range(300):
                _write(root, f"big/d{i:03d}/f.md", "1\n")
            _write(root, "sandbox/exp1/.spec/bitz.yaml", _bitz_yaml())
            _write(root, "sandbox/exp1/note.md", "1\n")
            _commit(root)

            real_lstat = os.lstat
            calls: list[str] = []

            def _counting_lstat(path, *args, **kwargs):
                calls.append(os.fspath(path))
                return real_lstat(path, *args, **kwargs)

            base = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True
            ).stdout.strip()
            with mock.patch("os.lstat", side_effect=_counting_lstat):
                nested = check_mod._nested_workspace_paths(
                    ["sandbox/exp1/note.md", "other/x.md"], "git", root, dict(os.environ), base, root
                )
            self.assertEqual(nested, {"sandbox/exp1/note.md"})
            self.assertFalse(any(os.sep + "big" in c for c in calls), calls)
            self.assertLessEqual(len(calls), 10)

    def test_base_lookup_is_batched(self):
        # 作業ツリーで決まらない候補が多くても、基準版の問い合わせは分割した少数の`git ls-tree`で済ませる。
        with tempfile.TemporaryDirectory() as root:
            _init_repo(root)
            _outer_workspace(root)
            _write(root, "keep.md", "1\n")
            _commit(root)
            paths = [f"many/d{i:04d}/f.md" for i in range(1200)]
            for p in paths:
                _write(root, p, "1\n")
            base = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True
            ).stdout.strip()

            real_run = gitutil._run
            ls_tree_calls: list[list[str]] = []

            def _spy(argv, cwd, env):
                if "ls-tree" in argv:
                    ls_tree_calls.append(argv)
                return real_run(argv, cwd, env)

            started = time.monotonic()
            with mock.patch.object(gitutil, "_run", side_effect=_spy):
                nested = check_mod._nested_workspace_paths(paths, "git", root, dict(os.environ), base, root)
            elapsed = time.monotonic() - started
            self.assertEqual(nested, set())
            # 候補のディレクトリは`many`と1200個の`many/dNNNN`と1200個のファイル自身で2401個。512個ずつで5回。
            self.assertEqual(len(ls_tree_calls), 5)
            self.assertLess(elapsed, 20.0)


class ReservedSpecEntriesTests(unittest.TestCase):
    def test_reserved_entries_are_known_for_any_kind(self):
        with tempfile.TemporaryDirectory() as root:
            spec = os.path.join(root, ".spec")
            os.makedirs(os.path.join(spec, "journal", "sub"))
            with open(os.path.join(spec, "plans"), "w", encoding="utf-8") as f:
                f.write("x\n")
            os.makedirs(os.path.join(root, "outside"))
            os.symlink(os.path.join("..", "outside"), os.path.join(spec, "reports"))
            os.symlink("missing", os.path.join(spec, "journals"))
            with open(os.path.join(spec, "Plans.md"), "w", encoding="utf-8") as f:
                f.write("x\n")
            self.assertEqual(document_mod._discover_top_level(spec), ["Plans.md", "journals"])

    def test_symlinked_reserved_directory_is_not_followed(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            _write(root, "outside/REQ-001.md", _req("REQ-001"))
            _write(root, "outside/broken.md", "---\nid: [\n---\n")
            os.symlink(os.path.join("..", "outside"), os.path.join(root, ".spec", "plans"))
            os.makedirs(os.path.join(root, ".spec", "journal"))
            os.symlink(os.path.join("..", "..", "outside"), os.path.join(root, ".spec", "journal", "linked"))
            result, exit_code = check_mod.run(
                ParsedArgs(operation="check", positionals=[], flags={"--full"}, single={}, repeat={}),
                root,
                dict(os.environ),
            )
            self.assertEqual(result["diagnostics"], [])
            self.assertEqual(result["checkedDocumentCount"], 0)
            self.assertEqual(exit_code, 0)


if __name__ == "__main__":
    unittest.main()
