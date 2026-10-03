"""`context`の複合ワークスペース対応（Step 5C、および是正）の単体試験。

`02_仕様文書モデル/05_複合ワークスペース仕様.md` §4・§6を対象にする。特に、他のワークスペースの文書が
**自分のワークスペース内**を非修飾で参照する関係（§4「同じワークスペースを参照するとき非修飾形式を
許可」）が、起点ワークスペースの視点だけの索引ではなく、参照元のワークスペースで解決されることを確認する
（是正: `multirelate._qualified_relations_view`）。
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from bitz import context as context_mod
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


def _run_context(root, target, *, purpose="interpret") -> tuple[dict, int]:
    parsed = ParsedArgs(
        operation="context", positionals=[target], flags=set(), single={"--purpose": purpose}, repeat={},
    )
    return context_mod.run(parsed, str(root), dict(os.environ))


class SameWorkspaceUnqualifiedRefResolvedByDeclarerTests(unittest.TestCase):
    """`web`のTECHが同じ`web`のREQ-002を非修飾で`requires`し、`platform`起点のコンテキストから
    `web`のTECH経由で到達する場合、REQ-002が閉包へ入り、ワークスペース内のエッジは
    ``resolution.crossWorkspaceEdges``へ含まれないことを確認する。
    """

    def _repo(self, root: Path) -> None:
        _init_repo(root)
        _write(
            root, ".spec/bitz.yaml",
            ROOT_YAML + "multiWorkspace:\n  members:\n    - id: web\n      path: apps/web\n",
        )
        _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
        _write(root, "apps/web/.spec/bitz.yaml", MEMBER_YAML.format(wid="web"))
        _write(root, "apps/web/.spec/requirements/REQ-002.md", _req("REQ-002", title="web内部の要求"))
        _write(
            root, "apps/web/.spec/technical/TECH-010.md",
            "---\nid: TECH-010\ntitle: TECH\nstatus: approved\n"
            "relations:\n  refines: [platform::REQ-001:AC-01]\n  requires: [REQ-002]\n"
            "---\n\n# TECH-010 TECH\n\n## Context\n\n本文。\n",
        )
        _git(root, "add", "-A")
        _git(root, "commit", "-q", "-m", "base")

    def test_same_workspace_unqualified_requires_is_resolved_within_declarer_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._repo(root)

            result, exit_code = _run_context(root, "platform::REQ-001", purpose="interpret")
            self.assertEqual(exit_code, 0, result)
            self.assertEqual(result["status"], "passed")

            doc_ids = {d["id"] for d in result["documents"]}
            self.assertIn("platform::REQ-001", doc_ids)
            self.assertIn("web::TECH-010", doc_ids)
            # `web::TECH-010`が非修飾`requires`した`web`自身のREQ-002が閉包に入っている。
            self.assertIn("web::REQ-002", doc_ids)

            # ワークスペース内（`web` -> `web`）の`requires`エッジは`crossWorkspaceEdges`に含めない。
            cross_edges = result["resolution"]["crossWorkspaceEdges"]
            for edge in cross_edges:
                self.assertFalse(
                    edge["source"].startswith("web::") and edge["target"].startswith("web::"),
                    f"workspace内edgeが横断edgeに混入している: {edge}",
                )
            # `web`（`refines`の参照元）から`platform`（`refines`の参照先）への横断エッジは1件だけ含まれる。
            self.assertEqual(
                [e for e in cross_edges if e["source"] == "web::TECH-010" and e["relation"] == "refines"],
                [{"relation": "refines", "source": "web::TECH-010", "target": "platform::REQ-001:AC-01"}],
            )

            # ハッシュ値が計算できている（`contextDigest`の算出時に解決できなければ設定不適合などで`None`になる）。
            self.assertIsNotNone(result["contextDigest"])
            self.assertTrue(result["contextDigest"].startswith("sha256:"))

    def test_unqualified_root_uses_declared_multi_workspace_catalog(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._repo(root)

            result, exit_code = _run_context(root, "REQ-001", purpose="interpret")
            self.assertEqual(exit_code, 0, result)
            self.assertEqual(result["status"], "passed")
            self.assertEqual(result["workspace"], {"id": "platform", "path": "."})
            self.assertIn("web::TECH-010", {d["id"] for d in result["documents"]})

    def test_unqualified_member_uses_declared_multi_workspace_catalog(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._repo(root)

            result, exit_code = _run_context(root / "apps/web", "TECH-010", purpose="interpret")
            self.assertEqual(exit_code, 0, result)
            self.assertEqual(result["status"], "passed")
            self.assertEqual(result["workspace"], {"id": "web", "path": "apps/web"})
            self.assertIn("platform::REQ-001", {d["id"] for d in result["documents"]})


if __name__ == "__main__":
    unittest.main()
