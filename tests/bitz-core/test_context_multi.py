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


def _tech_with_statement(doc_id: str, refines: str) -> str:
    return (
        f"---\nid: {doc_id}\ntitle: TECH\nstatus: approved\nrelations:\n  refines: [{refines}]\n---\n\n"
        f"# {doc_id} TECH\n\n## Contract\n\n"
        f"- [{doc_id}:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] {doc_id}の制約。\n"
    )


class RefinementProjectionAcrossWorkspacesTests(unittest.TestCase):
    """他のワークスペースの具体化文書の提示形式（`context`仕様 §5）。所有する規範文が制約台帳（対象規範文）にあるかを、
    対象規範文と同じ`ws::local`の表現で照合することを確かめる。
    """

    def _repo(self, root: Path) -> None:
        _init_repo(root)
        _write(root, ".spec/bitz.yaml",
               ROOT_YAML + "multiWorkspace:\n  members:\n    - id: web\n      path: apps/web\n")
        _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
        _write(root, "apps/web/.spec/bitz.yaml", MEMBER_YAML.format(wid="web"))
        # 規範文単位の具体化の鎖（対象規範文になる）と、文書単位の具体化（対象規範文にならない）。
        _write(root, "apps/web/.spec/technical/TECH-010.md", _tech_with_statement("TECH-010", "platform::REQ-001:AC-01"))
        _write(root, "apps/web/.spec/technical/TECH-011.md", _tech_with_statement("TECH-011", "TECH-010:AC-01"))
        _write(root, "apps/web/.spec/technical/TECH-012.md", _tech_with_statement("TECH-012", "TECH-010"))
        _git(root, "add", "-A")
        _git(root, "commit", "-q", "-m", "base")

    def test_statement_level_refinement_in_other_workspace_is_normative(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._repo(root)
            result, exit_code = _run_context(root, "platform::REQ-001", purpose="verify")
            by_id = {d["id"]: d for d in result["documents"]}
            ledger = {s["id"] for s in result["constraintLedger"]["statements"]}
            self.assertIn("web::TECH-011:AC-01", ledger, result)
            self.assertEqual(by_id["web::TECH-011"]["role"], "refinement")
            self.assertEqual(by_id["web::TECH-011"]["projection"], "normative")
            # 規範文が制約台帳にない文書単位の具体化文書は、`full`で本文を返す。
            if "web::TECH-012:AC-01" not in ledger:
                self.assertEqual(by_id["web::TECH-012"]["projection"], "full")
                self.assertIn("TECH-012の制約", by_id["web::TECH-012"]["bodyText"])



class NonAcceptedAdrAcrossWorkspacesTests(unittest.TestCase):
    """他のメンバーの文書が状態`accepted`でないADRを`requires`する場合も、閉包を構成する`requires`の辺の型制約として
    `CTX-RELATION-TYPE-001`を返す（関係・トレースモデル §4・§6.3、複合ワークスペース仕様 §6）。発生元は関係を宣言した文書。"""

    def test_other_member_requires_to_proposed_adr_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            _write(root, ".spec/bitz.yaml", ROOT_YAML + "multiWorkspace:\n  members:\n    - id: web\n      path: apps/web\n    - id: api\n      path: services/api\n")
            _write(root, "apps/web/.spec/bitz.yaml", MEMBER_YAML.format(wid="web"))
            _write(root, "services/api/.spec/bitz.yaml", MEMBER_YAML.format(wid="api"))
            _write(root, "apps/web/.spec/requirements/REQ-001.md",
                   _req("REQ-001").replace("status: approved\n", "status: approved\nrelations:\n  requires: [api::TECH-020]\n"))
            _write(root, "services/api/.spec/technical/TECH-020.md",
                   "---\nid: TECH-020\ntitle: TECH\nstatus: approved\nrelations:\n  requires: [ADR-001]\n---\n\n# TECH-020 TECH\n\n## Context\n\n本文。\n")
            _write(root, "services/api/.spec/decisions/ADR-001.md",
                   "---\nid: ADR-001\ntitle: 判断\nstatus: proposed\n---\n\n# ADR-001 判断\n\n## Context\n\n背景。\n\n## Decision\n\n決定。\n\n## Consequences\n\n帰結。\n")
            _git(root, "add", "-A")
            _git(root, "commit", "-q", "-m", "base")
            result, exit_code = _run_context(root / "apps/web", "REQ-001", purpose="implement")
            self.assertEqual((result["status"], exit_code), ("failed", 1), result)
            self.assertEqual(
                [(d["code"], d["source"]["workspaceId"], d["source"]["path"], d["source"].get("key"), d.get("evidence"))
                 for d in result["diagnostics"]],
                [("CTX-RELATION-TYPE-001", "api", ".spec/technical/TECH-020.md", "relations.requires", "ADR-001")],
            )

    def test_document_reached_by_two_ids_reports_the_edge_once(self):
        # web の REQ-002 は、REQ-001 から非修飾で、api の TECH-020 から`web::REQ-002`で到達する。同じ辺 REQ-002 -> ADR-002 の
        # 型制約の診断は1件だけ返す（同じ原因から同義の診断を複数生成しない）。
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            _write(root, ".spec/bitz.yaml", ROOT_YAML + "multiWorkspace:\n  members:\n    - id: web\n      path: apps/web\n    - id: api\n      path: services/api\n")
            _write(root, "apps/web/.spec/bitz.yaml", MEMBER_YAML.format(wid="web"))
            _write(root, "services/api/.spec/bitz.yaml", MEMBER_YAML.format(wid="api"))
            _write(root, "apps/web/.spec/requirements/REQ-001.md",
                   _req("REQ-001").replace("status: approved\n", "status: approved\nrelations:\n  requires: [api::TECH-020, REQ-002]\n"))
            _write(root, "apps/web/.spec/requirements/REQ-002.md",
                   _req("REQ-002").replace("status: approved\n", "status: approved\nrelations:\n  requires: [ADR-002]\n"))
            _write(root, "apps/web/.spec/decisions/ADR-002.md",
                   "---\nid: ADR-002\ntitle: 判断\nstatus: proposed\n---\n\n# ADR-002 判断\n\n## Context\n\n背景。\n\n## Decision\n\n決定。\n\n## Consequences\n\n帰結。\n")
            _write(root, "services/api/.spec/technical/TECH-020.md",
                   "---\nid: TECH-020\ntitle: TECH\nstatus: approved\nrelations:\n  requires: [web::REQ-002]\n---\n\n# TECH-020 TECH\n\n## Context\n\n本文。\n")
            _git(root, "add", "-A")
            _git(root, "commit", "-q", "-m", "base")
            result, exit_code = _run_context(root / "apps/web", "REQ-001", purpose="implement")
            self.assertEqual(
                [(d["code"], d["source"]["workspaceId"], d["source"]["path"]) for d in result["diagnostics"]],
                [("CTX-RELATION-TYPE-001", "web", ".spec/requirements/REQ-002.md")],
            )
            self.assertEqual(result["resolution"]["unresolvedStrongRelations"], 1)



class DigestCommandMaterialsAcrossWorkspacesTests(unittest.TestCase):
    """複合ワークスペースでも、ハッシュ値の材料の`commands`と`verifyTimeouts`は、所有ワークスペースの設定で解決した収録したテスト割当てだけから作り、
    `context --purpose verify`と`verify`で一致する（正規化仕様 §3、複合ワークスペース仕様の許可リスト）。"""

    def _repo(self, root: Path, *, web_argv: str, web_req_extra: str, api_tech: str) -> None:
        _init_repo(root)
        _write(root, ".spec/bitz.yaml", ROOT_YAML + "multiWorkspace:\n  members:\n    - id: web\n      path: apps/web\n    - id: api\n      path: services/api\n")
        _write(root, "apps/web/.spec/bitz.yaml", MEMBER_YAML.format(wid="web")
               + f'verify:\n  commands:\n    frontend:\n      argv: ["{web_argv}", "{{tests}}"]\n      cwd: .\n')
        _write(root, "services/api/.spec/bitz.yaml", MEMBER_YAML.format(wid="api")
               + 'verify:\n  commands:\n    backend:\n      argv: ["/bin/true", "{tests}"]\n      cwd: .\n')
        _write(root, "apps/web/.spec/requirements/REQ-001.md",
               _req("REQ-001").replace("status: approved\n", "status: approved\n" + web_req_extra))
        _write(root, "apps/web/tests/test_web.py", "def test_x():\n    assert True\n")
        _write(root, "services/api/.spec/technical/TECH-020.md", api_tech)
        _write(root, "services/api/tests/test_api.py", "def test_x():\n    assert True\n")
        _git(root, "add", "-A")
        _git(root, "commit", "-q", "-m", "base")

    def _digests(self, root: Path) -> tuple:
        from bitz import verify as verify_mod
        from bitz.cliargs import parse_argv
        ctx, _ = _run_context(root, "web::REQ-001", purpose="verify")
        ver, _ = verify_mod.run(parse_argv(["verify", "web::REQ-001", "--format", "json"]), str(root), dict(os.environ))
        return ctx["contextDigest"], ver["targetResults"][0]["contextDigest"]

    def _api_tech(self, tests_line: str, verify_line: str = "") -> str:
        return ("---\nid: TECH-020\ntitle: TECH\nstatus: approved\n" + verify_line + tests_line
                + "---\n\n# TECH-020 TECH\n\n## Context\n\n本文。\n")

    def test_both_operations_agree_and_the_document_default_is_in_the_digest(self):
        web_extra = ("relations:\n  requires: [api::TECH-020]\nverify: frontend\n"
                     "tests:\n  - path: tests/test_web.py\n    covers: [REQ-001:AC-01]\n")
        cases = {
            # (a) web の文書の`verify`で`frontend`を解決する
            "document-default": self._api_tech(""),
            # (b) api のテスト対応の`command`が未定義
            "undefined-command": self._api_tech("tests:\n  - path: tests/test_api.py\n    covers: [TECH-020]\n    command: nope\n"),
            # (c) api の文書の`verify`が、web にだけ定義のある名前
            "other-member-name": self._api_tech("tests:\n  - path: tests/test_api.py\n    covers: [TECH-020]\n", "verify: frontend\n"),
        }
        for name, api_tech in cases.items():
            with self.subTest(name), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                self._repo(root, web_argv="/bin/true", web_req_extra=web_extra, api_tech=api_tech)
                ctx_digest, verify_digest = self._digests(root)
                self.assertIsNotNone(ctx_digest)
                self.assertEqual(ctx_digest, verify_digest)
        # (c) のコマンド名は、所有ワークスペース（api）の設定だけで解決し、web の設定では解決しない（正規化仕様 §3）。
        from bitz.document import DocEntry
        entry = DocEntry.__new__(DocEntry)
        entry.frontmatter = {"verify": "frontend", "tests": [{"path": "tests/test_api.py", "covers": ["TECH-020"]}]}
        defined = {("web", "frontend"): {"argv": ["/bin/true", "{tests}"], "cwd": "."}}
        materials = context_mod.digest_command_materials(
            ["api::TECH-020"], {"api::TECH-020": entry}, lambda d: "api",
            lambda wid, name: defined.get((wid, name)), lambda wid: 300,
        )
        self.assertEqual(materials, ([], []))
        # (a) の`frontend`の定義を変えると、両操作のハッシュ値が変わる（文書の`verify`で解決したコマンドが材料に入る）。
        results = []
        for argv in ("/bin/true", "/usr/bin/true"):
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                self._repo(root, web_argv=argv, web_req_extra=web_extra, api_tech=cases["document-default"])
                results.append(self._digests(root))
        self.assertNotEqual(results[0][0], results[1][0])
        self.assertNotEqual(results[0][1], results[1][1])



class TaskAddressingQualifiedTechTests(unittest.TestCase):
    """TASKが他のメンバーの規範文のないTECHを修飾IDで`addresses`する場合も、規範文と取り違えず、そのTECHの文書単位のテスト割当てを
    所有ワークスペースのコマンドで作る。"""

    def test_qualified_tech_without_statements_is_a_document_unit_binding(self):
        from bitz import verify as verify_mod
        from bitz.cliargs import parse_argv
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            _write(root, ".spec/bitz.yaml", ROOT_YAML + "multiWorkspace:\n  members:\n    - id: web\n      path: apps/web\n    - id: api\n      path: services/api\n")
            _write(root, "apps/web/.spec/bitz.yaml", MEMBER_YAML.format(wid="web"))
            _write(root, "services/api/.spec/bitz.yaml", MEMBER_YAML.format(wid="api")
                   + 'verify:\n  commands:\n    backend:\n      argv: ["/bin/true", "{tests}"]\n      cwd: .\n')
            _write(root, "apps/web/.spec/tasks/TASK-001.md",
                   "---\nid: TASK-001\ntitle: 作業\nstatus: open\nrelations:\n  addresses: [api::TECH-020]\n---\n\n# TASK-001 作業\n\n## Objective\n\n作業する。\n")
            _write(root, "services/api/.spec/technical/TECH-020.md",
                   "---\nid: TECH-020\ntitle: TECH\nstatus: approved\ntests:\n  - path: tests/test_api.py\n    covers: [TECH-020]\n    command: backend\n"
                   "---\n\n# TECH-020 TECH\n\n## Context\n\n規範文を持たない。\n")
            _write(root, "services/api/tests/test_api.py", "x\n")
            _git(root, "add", "-A")
            _git(root, "commit", "-q", "-m", "base")
            result, exit_code = verify_mod.run(parse_argv(["verify", "web::TASK-001", "--format", "json"]), str(root), dict(os.environ))
            self.assertEqual((result["status"], exit_code), ("passed", 0), result)
            target = result["targetResults"][0]
            self.assertEqual(target["statements"], [])
            self.assertEqual(target["bindingRefs"], ["api::backend"])
            # 目的`implement`と`verify`の`context`も、修飾IDを規範文と取り違えずに構成する。
            for purpose in ("implement", "verify"):
                with self.subTest(purpose=purpose):
                    ctx, _ = _run_context(root, "web::TASK-001", purpose=purpose)
                    self.assertIn("api::TECH-020", {d["id"] for d in ctx["documents"]}, ctx)
                    self.assertEqual(ctx["constraintLedger"]["statements"], [])

    def test_unresolved_command_of_other_member_is_reported_with_its_owner(self):
        from bitz import verify as verify_mod
        from bitz.cliargs import parse_argv
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            _write(root, ".spec/bitz.yaml", ROOT_YAML + "multiWorkspace:\n  members:\n    - id: web\n      path: apps/web\n    - id: api\n      path: services/api\n")
            # web だけが backend を定義し、api には定義がない。
            _write(root, "apps/web/.spec/bitz.yaml", MEMBER_YAML.format(wid="web")
                   + 'verify:\n  commands:\n    backend:\n      argv: ["/bin/true", "{tests}"]\n      cwd: .\n')
            _write(root, "services/api/.spec/bitz.yaml", MEMBER_YAML.format(wid="api"))
            _write(root, "apps/web/.spec/tasks/TASK-001.md",
                   "---\nid: TASK-001\ntitle: 作業\nstatus: open\nrelations:\n  addresses: [api::TECH-020]\n---\n\n# TASK-001 作業\n\n## Objective\n\n作業する。\n")
            _write(root, "services/api/.spec/technical/TECH-020.md",
                   "---\nid: TECH-020\ntitle: TECH\nstatus: approved\ntests:\n  - path: tests/test_api.py\n    covers: [TECH-020]\n    command: backend\n"
                   "---\n\n# TECH-020 TECH\n\n## Context\n\n規範文を持たない。\n")
            _write(root, "services/api/tests/test_api.py", "x\n")
            _git(root, "add", "-A")
            _git(root, "commit", "-q", "-m", "base")
            result, exit_code = verify_mod.run(parse_argv(["verify", "web::TASK-001", "--format", "json"]), str(root), dict(os.environ))
            self.assertEqual((result["status"], exit_code), ("blocked", 2), result)
            diags = result["targetResults"][0]["diagnostics"]
            self.assertEqual([(d["code"], d["source"]["workspaceId"], d["source"]["path"]) for d in diags],
                             [("SPEC-VERIFY-BLOCKED-001", "api", ".spec/technical/TECH-020.md")])


if __name__ == "__main__":
    unittest.main()
