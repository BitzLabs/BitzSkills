"""`gitutil.collect_changed_paths`とTASK `changes`の一致規則の単体試験。

`03_操作仕様/02_check.md` §5・§7、`00_共通契約/02_安全な入出力・互換性.md` §6を検査する。
実際のGit CLIを一時リポジトリに対して起動する（`06_Core実行環境・CLI基盤契約 §4`のとおり引数列で
直接起動する実装をそのまま検証するため、フェイクやモックに置き換えない）。
"""

import os
import subprocess
import tempfile
import unittest

from bitz import gitutil

# `check.py`の境界の一致判定はCLI層の非公開の関数だが、単体試験で仕様の一致規則
# （完全一致・末尾`/`のセグメント単位の接頭辞一致・`src/a`と`src/ab`の非曖昧性）を直接検査する。
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
            # `git add -A`で`c.txt`の削除と`c-renamed.txt`の追加を両方ステージしてこそ、インデックスが
            # リネームの対（100%類似）として検出できる状態になる（`b.txt`の削除も併せてステージする）。
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
        # 基準版→インデックス（ステージ済み）とインデックス→作業ツリー（戻した状態）を別々に取る和集合でなければ、
        # `git diff <base>`（作業ツリーと基準版の直接比較）だけでは差分が消えてしまう
        # （安全な入出力 §6・check.md §5 の「基準版→インデックス」「インデックス→作業ツリー」の和集合）。
        with tempfile.TemporaryDirectory() as root:
            self._init_repo(root)
            _write(root, "x.txt", "base-content\n")
            _git(root, "add", "-A")
            _git(root, "commit", "-q", "-m", "base")
            base = _head(root)

            _write(root, "x.txt", "staged-content\n")
            _git(root, "add", "x.txt")
            # 作業ツリーを基準版の内容へ戻す（インデックスはステージ済みのまま）。
            _write(root, "x.txt", "base-content\n")

            # 素朴な`git diff <base>`（作業ツリーとの直接比較）では`x.txt`の差分は消える。
            direct = subprocess.run(
                ["git", "diff", "--name-status", base], cwd=root, check=True, capture_output=True, text=True
            ).stdout
            self.assertEqual(direct.strip(), "")

            changed = _collect(root, base)
            by_path = {c.path: c for c in changed}
            self.assertIn("x.txt", by_path)
            self.assertEqual(by_path["x.txt"].status, "M")

    def test_paths_with_space_and_non_ascii_are_not_mangled(self):
        # タブ区切りの出力はファイル名にスペース・非ASCIIを含む場合`quotePath`で`"..."`へ変換され得るため、
        # NUL区切り（`-z`）で読み、原文のパスをそのまま返すことを確認する。
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
        # リポジトリのルートとワークスペースのルートが異なる場合（複合ワークスペースのメンバー相当）、
        # ワークスペースのルート外の変更パスは変更集合から除外し、内側のパスはワークスペースのルートからの相対パスへ
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
        # 現在のディレクトリがワークスペースのルートのさらに下位のディレクトリでも（`git diff`はリポジトリのルートからの相対パスを
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
    """`check._task_own_path_allows`のファイルの完全一致・ディレクトリの接頭辞のセグメント境界。"""

    def test_exact_file_match(self):
        self.assertTrue(check_mod._task_own_path_allows("src/app.py", ["src/app.py"]))
        self.assertFalse(check_mod._task_own_path_allows("src/other.py", ["src/app.py"]))

    def test_directory_prefix_matches_descendants(self):
        self.assertTrue(check_mod._task_own_path_allows("src/auth/service.py", ["src/auth/"]))
        self.assertTrue(check_mod._task_own_path_allows("src/auth/sub/deep.py", ["src/auth/"]))

    def test_directory_prefix_is_segment_bounded(self):
        # `src/a/`は`src/ab/...`へ拡張してはならない（パスのセグメント境界での判定）。
        self.assertFalse(check_mod._task_own_path_allows("src/ab/file.py", ["src/a/"]))
        self.assertTrue(check_mod._task_own_path_allows("src/a/file.py", ["src/a/"]))

    def test_no_allowed_paths_denies_everything(self):
        self.assertFalse(check_mod._task_own_path_allows("src/app.py", []))


if __name__ == "__main__":
    unittest.main()
