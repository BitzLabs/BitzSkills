"""`bitz.compat`（Step 5D: 外形判定と移行）の単体試験。

`00_共通契約/04_適合fixture仕様.md` §3の``runner: consumer``・``runner: migration``が対象にする
経路を、conformance fixture（MULTI-023/024）とは独立の単体規模で検証する。
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from bitz import compat


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


def _req(doc_id: str) -> str:
    return (
        f"---\nid: {doc_id}\ntitle: 認証の基準\nstatus: approved\n---\n\n# {doc_id} 認証の基準\n\n"
        "## Intent\n\n意図。\n\n## Acceptance Criteria\n\n"
        f"- [{doc_id}:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 秘密情報を出力しない。\n\n"
        "## Verification\n\n未証明。\n"
    )


def _tech(doc_id: str, *, refines: str) -> str:
    return (
        f"---\nid: {doc_id}\ntitle: 認証の実装方針\nstatus: approved\nrelations:\n  refines: [{refines}]\n"
        f"tests:\n  - path: tests/test_login.py\n    covers: [{refines}]\n    command: default\n"
        f"---\n\n# {doc_id} 認証の実装方針\n\n## Context\n\n本文。\n"
    )


class ResultShapeTests(unittest.TestCase):
    def _run(self, tmp: Path, obj: dict) -> tuple[str, int]:
        path = tmp / "result.json"
        path.write_text(json.dumps(obj), encoding="utf-8")
        cwd = os.getcwd()
        try:
            os.chdir(tmp)
            buf_out = []
            import io
            import contextlib

            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = compat.main(["consumer", "result-shape", "result.json"])
            return json.loads(out.getvalue())["outcome"], code
        finally:
            os.chdir(cwd)

    def test_single_workspace_shape_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outcome, code = self._run(Path(tmp), {"workspace": {"id": "root", "path": "."}})
            self.assertEqual(outcome, "accepted")
            self.assertEqual(code, 0)

    def test_composite_shape_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outcome, code = self._run(
                Path(tmp),
                {"multiWorkspace": {"id": "platform", "path": "."}, "workspaces": []},
            )
            self.assertEqual(outcome, "accepted")
            self.assertEqual(code, 0)

    def test_mixed_shape_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outcome, code = self._run(
                Path(tmp),
                {
                    "workspace": {"id": "platform", "path": "."},
                    "multiWorkspace": {"id": "platform", "path": "."},
                    "workspaces": [],
                },
            )
            self.assertEqual(outcome, "rejected")
            self.assertEqual(code, 1)

    def test_neither_shape_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outcome, code = self._run(Path(tmp), {"schemaVersion": "1.0"})
            self.assertEqual(outcome, "rejected")
            self.assertEqual(code, 1)


class MigrationTests(unittest.TestCase):
    def _to_multi_repo(self, root: Path) -> None:
        _init_repo(root)
        _write(
            root,
            ".spec/bitz.yaml",
            'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\nworkspace:\n  id: platform\n'
            "multiWorkspace:\n  members:\n    - id: web\n      path: apps/web\n",
        )
        _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
        _write(
            root,
            "apps/web/.spec/bitz.yaml",
            'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\nworkspace:\n  id: web\n',
        )
        _write(root, "apps/web/.spec/technical/TECH-010.md", _tech("TECH-010", refines="platform::REQ-001:AC-01"))
        _write(root, "apps/web/tests/test_login.py", "def test_login():\n    assert True\n")
        _git(root, "add", "-A")
        _git(root, "commit", "-q", "-m", "base")

    def test_to_multi_workspace_passed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._to_multi_repo(root)
            status = compat._to_multi_workspace_status(str(root), dict(os.environ))
            self.assertEqual(status, "passed")

    def test_to_multi_workspace_rejected_when_not_multi(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            _write(root, ".spec/bitz.yaml", 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\n')
            _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
            _git(root, "add", "-A")
            _git(root, "commit", "-q", "-m", "base")
            status = compat._to_multi_workspace_status(str(root), dict(os.environ))
            self.assertIsNone(status)

    def test_rollback_passed_when_unqualified(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._to_multi_repo(root)
            # rollback: apps/web/.spec配下を廃止し、rootへ単一workspaceとして統合する。
            _write(root, ".spec/bitz.yaml", 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\n')
            _write(root, ".spec/technical/TECH-010.md", _tech("TECH-010", refines="REQ-001:AC-01"))
            _write(root, "tests/test_login.py", "def test_login():\n    assert True\n")
            _git(root, "rm", "-r", "-q", "apps/web/.spec")
            _git(root, "rm", "-q", "apps/web/tests/test_login.py")
            _git(root, "add", "-A")
            status = compat._rollback_status(str(root), dict(os.environ))
            self.assertEqual(status, "passed")

    def test_rollback_rejected_when_qualified_ref_remains(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._to_multi_repo(root)
            _write(root, ".spec/bitz.yaml", 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\n')
            # 修飾参照を残したまま部分rollbackする（単一workspace化後もplatform::を保持）。
            _write(root, ".spec/technical/TECH-010.md", _tech("TECH-010", refines="platform::REQ-001:AC-01"))
            _write(root, "tests/test_login.py", "def test_login():\n    assert True\n")
            _git(root, "rm", "-r", "-q", "apps/web/.spec")
            _git(root, "rm", "-q", "apps/web/tests/test_login.py")
            _git(root, "add", "-A")
            status = compat._rollback_status(str(root), dict(os.environ))
            self.assertEqual(status, "failed")

    def test_run_migration_cli_outcomes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._to_multi_repo(root)
            cwd = os.getcwd()
            try:
                os.chdir(root)
                import io
                import contextlib

                out = io.StringIO()
                with contextlib.redirect_stdout(out):
                    code = compat.main(["migration", "to-multi-workspace"])
                self.assertEqual(json.loads(out.getvalue())["outcome"], "passed")
                self.assertEqual(code, 0)
            finally:
                os.chdir(cwd)

    def test_run_migration_unknown_case_is_argument_error(self) -> None:
        code = compat._run_migration(["bogus"])
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
