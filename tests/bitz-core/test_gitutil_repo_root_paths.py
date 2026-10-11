"""Gitの呼び出しが現在のディレクトリによらずリポジトリ全体を対象にすることの単体試験。

`git ls-tree`と`git ls-files`は既定で現在のディレクトリの配下だけを列挙し、`git ls-tree`はパスの指定と出力も
現在のディレクトリからの相対で扱う。そのため複合ワークスペースのメンバーの中や、ワークスペースのサブディレクトリで
`check`を実行すると、基準版のカタログが空になって削除の検出、状態遷移、承認済み要求の保護が省かれ、
事前検査の未登録の判定も実行場所で変わっていた。

`03_操作仕様/02_check.md` §5・§9、`02_仕様文書モデル/05_複合ワークスペース仕様.md` §5.2・§8を対象にする。
実際のGit CLIを一時リポジトリに対して起動する。
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from bitz import check as check_mod
from bitz import gitutil
from bitz.cliargs import ParsedArgs

ROOT_YAML = 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\nworkspace:\n  id: platform\n'
MEMBER_YAML = 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\nworkspace:\n  id: {wid}\n'
CATALOG = "multiWorkspace:\n  members:\n    - id: web\n      path: apps/web\n    - id: api\n      path: services/api\n"


def _git_env() -> dict[str, str]:
    return {**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}


def _git(root, *args) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, env=_git_env(), check=True, capture_output=True, text=True
    ).stdout


def _init_repo(root: Path) -> None:
    _git(root, "init", "-q", "--initial-branch=main")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")


def _write(root: Path, rel: str, content: str) -> None:
    full = root / rel
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")


def _req(doc_id: str, text: str = "秘密情報を出力しない。") -> str:
    return (
        f"---\nid: {doc_id}\ntitle: REQ\nstatus: approved\n---\n\n# {doc_id} REQ\n\n"
        "## Intent\n\n意図。\n\n## Acceptance Criteria\n\n"
        f"- [{doc_id}:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] {text}\n\n"
        "## Verification\n\n未証明。\n"
    )


def _git_exe() -> str:
    git = gitutil.detect_git(os.getcwd(), _git_env())
    assert git.executable
    return git.executable


def _run_check(cwd, *, flags=None) -> tuple[dict, int]:
    parsed = ParsedArgs(
        operation="check", positionals=[], flags=set(flags or ()), single={"--base": "HEAD"}, repeat={},
    )
    return check_mod.run(parsed, str(cwd), _git_env())


def _stable(result: dict) -> dict:
    """実行時間（`durationMs`）を除いた結果。"""

    return {k: v for k, v in result.items() if k != "durationMs"}


def _codes(result: dict) -> set[str]:
    codes = {d["code"] for d in result.get("diagnostics", [])}
    for ws in result.get("workspaces", []) or []:
        codes |= {d["code"] for d in ws.get("diagnostics", [])}
    return codes


class GitutilFromSubdirectoryTests(unittest.TestCase):
    """gitutilの各関数が、現在のディレクトリがリポジトリのルートでなくても同じ結果を返すこと。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        _init_repo(self.root)
        _write(self.root, ".spec/bitz.yaml", ROOT_YAML + CATALOG)
        _write(self.root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
        _write(self.root, "apps/web/.spec/bitz.yaml", MEMBER_YAML.format(wid="web"))
        _write(self.root, "apps/web/.spec/requirements/REQ-010.md", _req("REQ-010"))
        _write(self.root, "apps/web/src/deeper/keep.txt", "keep\n")
        _write(self.root, "services/api/.spec/bitz.yaml", MEMBER_YAML.format(wid="api"))
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-q", "-m", "base")
        self.exe = _git_exe()
        self.env = _git_env()
        self.web = str(self.root / "apps" / "web")
        self.deeper = str(self.root / "apps" / "web" / "src" / "deeper")

    def tearDown(self):
        self._tmp.cleanup()

    def test_base_spec_paths_from_member_and_deeper_directory(self):
        for cwd in (str(self.root), self.web, self.deeper):
            with self.subTest(cwd=cwd):
                paths = gitutil.list_base_spec_paths(self.exe, cwd, self.env, "HEAD", self.web)
                self.assertEqual(sorted(paths), [".spec/bitz.yaml", ".spec/requirements/REQ-010.md"])

    def test_base_spec_paths_of_root_workspace_from_member(self):
        paths = gitutil.list_base_spec_paths(self.exe, self.web, self.env, "HEAD", str(self.root))
        self.assertIn(".spec/requirements/REQ-001.md", paths)
        self.assertNotIn(".spec/requirements/REQ-010.md", paths)

    def test_base_tree_entry_mode_from_deeper_directory(self):
        mode = gitutil.base_tree_entry_mode(
            self.exe, self.deeper, self.env, "HEAD", self.web, ".spec/requirements/REQ-010.md"
        )
        self.assertEqual(mode, "100644")

    def test_tree_config_paths_from_member(self):
        expected = [".spec/bitz.yaml", "apps/web/.spec/bitz.yaml", "services/api/.spec/bitz.yaml"]
        for cwd in (str(self.root), self.web):
            with self.subTest(cwd=cwd):
                self.assertEqual(sorted(gitutil.list_tree_config_paths(self.exe, cwd, self.env, "HEAD")), expected)

    def test_working_config_paths_from_member_include_untracked_outside_member(self):
        _write(self.root, "tools/x/.spec/bitz.yaml", MEMBER_YAML.format(wid="x"))
        expected = [
            ".spec/bitz.yaml", "apps/web/.spec/bitz.yaml", "services/api/.spec/bitz.yaml", "tools/x/.spec/bitz.yaml",
        ]
        for cwd in (str(self.root), self.web, self.deeper):
            with self.subTest(cwd=cwd):
                self.assertEqual(gitutil.list_working_config_paths(self.exe, cwd, self.env), expected)

    def test_submodule_paths_from_member(self):
        head = _git(self.root, "rev-parse", "HEAD").strip()
        _git(self.root, "update-index", "--add", "--cacheinfo", f"160000,{head},vendor/lib")
        for cwd in (str(self.root), self.web):
            with self.subTest(cwd=cwd):
                self.assertEqual(gitutil.list_submodule_paths(self.exe, cwd, self.env), {"vendor/lib"})

    def test_untracked_path_in_workspace_outside_cwd_is_changed(self):
        _write(self.root, "apps/web/.spec/requirements/REQ-011.md", _req("REQ-011"))
        changed = gitutil.collect_changed_paths(self.exe, self.deeper, self.env, "HEAD", self.web)
        self.assertIn(".spec/requirements/REQ-011.md", {c.path for c in changed})

    def test_diff_relative_config_does_not_narrow_changes(self):
        # `diff.relative`を設定すると、`git diff`の出力が現在のディレクトリの配下に限られ、相対パスになる。
        _git(self.root, "config", "diff.relative", "true")
        _write(self.root, "apps/web/.spec/requirements/REQ-010.md", _req("REQ-010", "変更した。"))
        changed = gitutil.collect_changed_paths(self.exe, self.deeper, self.env, "HEAD", self.web)
        self.assertEqual({c.path for c in changed}, {".spec/requirements/REQ-010.md"})


class CheckBaseComparisonFromSubdirectoryTests(unittest.TestCase):
    """`check`の基準版との比較（削除の検出、状態遷移、承認済み要求の保護）が実行場所で省かれないこと。"""

    def test_single_workspace_from_subdirectory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            _write(root, ".spec/bitz.yaml", MEMBER_YAML.format(wid="solo"))
            _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
            _write(root, ".spec/requirements/REQ-002.md", _req("REQ-002"))
            _write(root, "docs/readme.txt", "readme\n")
            _git(root, "add", "-A")
            _git(root, "commit", "-q", "-m", "base")
            _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001", "意味を変えた。"))
            (root / ".spec" / "requirements" / "REQ-002.md").unlink()

            results = {}
            for cwd in (root, root / "docs", root / ".spec" / "requirements"):
                result, _ = _run_check(cwd)
                results[str(cwd)] = _stable(result)
                with self.subTest(cwd=str(cwd)):
                    self.assertEqual(result["status"], "failed")
                    self.assertIn("SPEC-SAFETY-APPROVED-001", _codes(result))
                    self.assertIn("SPEC-STATE-TRANSITION-001", _codes(result))
            self.assertEqual(len({repr(r) for r in results.values()}), 1)

    def test_member_workspace_from_member_and_from_root_with_workspace_option(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            _write(root, ".spec/bitz.yaml", ROOT_YAML + CATALOG)
            _write(root, "apps/web/.spec/bitz.yaml", MEMBER_YAML.format(wid="web"))
            _write(root, "apps/web/.spec/requirements/REQ-010.md", _req("REQ-010"))
            _write(root, "apps/web/.spec/requirements/REQ-011.md", _req("REQ-011"))
            _write(root, "services/api/.spec/bitz.yaml", MEMBER_YAML.format(wid="api"))
            _git(root, "add", "-A")
            _git(root, "commit", "-q", "-m", "base")
            _write(root, "apps/web/.spec/requirements/REQ-010.md", _req("REQ-010", "意味を変えた。"))
            (root / "apps" / "web" / ".spec" / "requirements" / "REQ-011.md").unlink()

            from_member, _ = _run_check(root / "apps" / "web")
            parsed = ParsedArgs(
                operation="check", positionals=[], flags=set(),
                single={"--base": "HEAD", "--workspace": "web"}, repeat={},
            )
            from_root, _ = check_mod.run(parsed, str(root), _git_env())
            for name, result in (("member", from_member), ("root", from_root)):
                with self.subTest(run=name):
                    self.assertEqual(result["status"], "failed")
                    self.assertIn("SPEC-SAFETY-APPROVED-001", _codes(result))
                    self.assertIn("SPEC-STATE-TRANSITION-001", _codes(result))
            self.assertEqual(_stable(from_member), _stable(from_root))


class AllWorkspacesUnregisteredFromMemberTests(unittest.TestCase):
    def test_untracked_unregistered_config_is_blocked_from_any_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            _write(root, ".spec/bitz.yaml", ROOT_YAML + CATALOG)
            _write(root, "apps/web/.spec/bitz.yaml", MEMBER_YAML.format(wid="web"))
            _write(root, "services/api/.spec/bitz.yaml", MEMBER_YAML.format(wid="api"))
            _git(root, "add", "-A")
            _git(root, "commit", "-q", "-m", "base")
            _write(root, "tools/x/.spec/bitz.yaml", MEMBER_YAML.format(wid="x"))

            for cwd in (root, root / "apps" / "web"):
                result, code = _run_check(cwd, flags={"--all-workspaces"})
                with self.subTest(cwd=str(cwd)):
                    self.assertEqual(result["status"], "blocked")
                    self.assertIn("SPEC-MULTI-UNREGISTERED-001", _codes(result))


if __name__ == "__main__":
    unittest.main()
