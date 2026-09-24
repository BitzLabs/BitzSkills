"""`gitutil.collect_changed_paths`とTASK `changes`一致規則の単体試験。

`03_操作仕様/02_check.md` §5・§7、`00_共通契約/02_安全な入出力・互換性.md` §6を検査する。
実Git CLIを一時repositoryへ対して起動する（`06_Core実行環境・CLI基盤契約 §4`のとおりargvで
直接起動する実装をそのまま検証するため、fakeやmockに置き換えない）。
"""

import os
import subprocess
import tempfile
import unittest

from bitz import gitutil

# check.pyの境界一致判定はCLI層のprivate関数だが、単体試験で仕様の一致規則
# （完全一致・末尾`/`のsegment単位接頭辞一致・`src/a`と`src/ab`の非曖昧性）を直接検査する。
from bitz import check as check_mod


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _write(root, rel_path, content):
    full = os.path.join(root, rel_path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(content)


def _head(root) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


def _collect(root, base, workspace_root=None, cwd=None):
    git = gitutil.detect_git(root, dict(os.environ))
    return gitutil.collect_changed_paths(
        git.executable, cwd or root, dict(os.environ), base, workspace_root or root
    )


class CollectChangedPathsTests(unittest.TestCase):
    def _init_repo(self, root):
        _git(root, "init", "-q")
        _git(root, "config", "user.email", "test@example.com")
        _git(root, "config", "user.name", "Test")

    def test_modified_deleted_added_untracked_and_rename(self):
        with tempfile.TemporaryDirectory() as root:
            self._init_repo(root)
            _write(root, "a.txt", "base-a\n" * 5)
            _write(root, "b.txt", "base-b\n" * 5)
            _write(root, "c.txt", "base-c\n" * 5)
            _git(root, "add", "-A")
            _git(root, "commit", "-q", "-m", "base")
            base = _head(root)

            _write(root, "a.txt", "changed\n")
            os.remove(os.path.join(root, "b.txt"))
            os.rename(os.path.join(root, "c.txt"), os.path.join(root, "c-renamed.txt"))
            _write(root, "d.txt", "untracked\n")
            # `git add -A`でc.txtの削除とc-renamed.txtの追加を両方stageしてこそ、indexが
            # rename対（100%類似）として検出できる状態になる（b.txtの削除も併せてstageする）。
            _git(root, "add", "-A")

            changed = _collect(root, base)
            by_path = {c.path: c for c in changed}
            self.assertEqual(by_path["a.txt"].status, "M")
            self.assertEqual(by_path["b.txt"].status, "D")
            self.assertEqual(by_path["d.txt"].status, "A")
            self.assertIn("c-renamed.txt", by_path)
            self.assertEqual(by_path["c-renamed.txt"].status, "R")
            self.assertEqual(by_path["c-renamed.txt"].old_path, "c.txt")

    def test_staged_then_reverted_path_is_still_in_index_diff(self):
        # base→index（staged）とindex→working tree（reverted）を別々に取る和集合でなければ、
        # `git diff <base>`（working treeと基準版の直接比較）だけでは差分が消えてしまう
        # （安全な入出力 §6・check.md §5 の「base→index」「index→working tree」の和集合）。
        with tempfile.TemporaryDirectory() as root:
            self._init_repo(root)
            _write(root, "x.txt", "base-content\n")
            _git(root, "add", "-A")
            _git(root, "commit", "-q", "-m", "base")
            base = _head(root)

            _write(root, "x.txt", "staged-content\n")
            _git(root, "add", "x.txt")
            # working treeを基準版の内容へ戻す（indexはstagedのまま）。
            _write(root, "x.txt", "base-content\n")

            # 素朴な`git diff <base>`（working treeとの直接比較）ではx.txtの差分は消える。
            direct = subprocess.run(
                ["git", "diff", "--name-status", base], cwd=root, check=True, capture_output=True, text=True
            ).stdout
            self.assertEqual(direct.strip(), "")

            changed = _collect(root, base)
            by_path = {c.path: c for c in changed}
            self.assertIn("x.txt", by_path)
            self.assertEqual(by_path["x.txt"].status, "M")

    def test_paths_with_space_and_non_ascii_are_not_mangled(self):
        # tab区切り出力はfile名にspace・非ASCIIを含む場合quotePathで`"..."`へ変換され得るため、
        # NUL区切り（`-z`）で読み、原文のpathをそのまま返すことを確認する。
        with tempfile.TemporaryDirectory() as root:
            self._init_repo(root)
            _git(root, "add", "-A")
            _write(root, "README.md", "seed\n")
            _git(root, "add", "-A")
            _git(root, "commit", "-q", "-m", "base")
            base = _head(root)

            tricky = "dir with space/ファイル テスト.txt"
            _write(root, tricky, "content\n")

            changed = _collect(root, base)
            paths = {c.path for c in changed}
            self.assertIn(tricky, paths)

    def test_subdirectory_workspace_excludes_paths_outside_workspace_root(self):
        # repository rootとworkspace rootが異なる場合（複合workspaceのmember相当）、
        # workspace root外の変更pathは変更集合から除外し、内側のpathはworkspace root相対へ
        # 変換する（安全な入出力 §6の所有境界、check.md §5）。
        with tempfile.TemporaryDirectory() as root:
            self._init_repo(root)
            _write(root, "outside.txt", "base-outside\n")
            _write(root, "sub/inside.txt", "base-inside\n")
            _git(root, "add", "-A")
            _git(root, "commit", "-q", "-m", "base")
            base = _head(root)

            _write(root, "outside.txt", "changed-outside\n")
            _write(root, "sub/inside.txt", "changed-inside\n")

            workspace_root = os.path.join(root, "sub")
            changed = _collect(root, base, workspace_root=workspace_root, cwd=workspace_root)
            paths = {c.path for c in changed}
            self.assertEqual(paths, {"inside.txt"})

    def test_cwd_below_workspace_root_still_resolves_correctly(self):
        # cwdがworkspace rootのさらに下位directoryでも（`git diff`はrepository root相対を
        # 返すため）結果は変わらない。
        with tempfile.TemporaryDirectory() as root:
            self._init_repo(root)
            _write(root, "sub/deeper/inside.txt", "base-inside\n")
            _git(root, "add", "-A")
            _git(root, "commit", "-q", "-m", "base")
            base = _head(root)

            _write(root, "sub/deeper/inside.txt", "changed-inside\n")

            workspace_root = os.path.join(root, "sub")
            cwd = os.path.join(root, "sub", "deeper")
            changed = _collect(root, base, workspace_root=workspace_root, cwd=cwd)
            paths = {c.path for c in changed}
            self.assertEqual(paths, {"deeper/inside.txt"})


class TaskBoundaryMatchTests(unittest.TestCase):
    """`check._task_own_path_allows`のfile完全一致・directory接頭辞のsegment境界。"""

    def test_exact_file_match(self):
        self.assertTrue(check_mod._task_own_path_allows("src/app.py", ["src/app.py"]))
        self.assertFalse(check_mod._task_own_path_allows("src/other.py", ["src/app.py"]))

    def test_directory_prefix_matches_descendants(self):
        self.assertTrue(check_mod._task_own_path_allows("src/auth/service.py", ["src/auth/"]))
        self.assertTrue(check_mod._task_own_path_allows("src/auth/sub/deep.py", ["src/auth/"]))

    def test_directory_prefix_is_segment_bounded(self):
        # `src/a/`は`src/ab/...`へ拡張してはならない（path segment境界での判定）。
        self.assertFalse(check_mod._task_own_path_allows("src/ab/file.py", ["src/a/"]))
        self.assertTrue(check_mod._task_own_path_allows("src/a/file.py", ["src/a/"]))

    def test_no_allowed_paths_denies_everything(self):
        self.assertFalse(check_mod._task_own_path_allows("src/app.py", []))


if __name__ == "__main__":
    unittest.main()
