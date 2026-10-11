"""複合ワークスペース内の、修飾IDを持たない単独操作の`check`の単体試験。

`02_仕様文書モデル/05_複合ワークスペース仕様.md` §3・§4・§5・§6・§7、`03_操作仕様/02_check.md` §2・§3・§6を対象にする。
引数なしの`check`（`scope: changed`）と`--full`、および`--workspace`が、複合ワークスペースを認識して
統合索引で動くことを確かめる。具体的には次のとおり。

- 修飾した参照（`api::TECH-020`、`platform::REQ-001:AC-01`）を、存在しない参照として誤検出しない。
- 作業ワークスペースは、現在のディレクトリの最寄りの設定または`--workspace`で決め、結果の`workspace.path`に反映する。
- 強い関係の閉包がワークスペースをまたぎ、到達した他のメンバーの文書の誤りを所有ワークスペースの名前で返す。
- 作業ワークスペースの文書を参照する他のメンバーの文書は対象にするが、閉包で到達した他のメンバーの文書の
  逆参照へは広げない。無関係なメンバーの文書は対象にしない。
- ルートワークスペースは、登録したメンバーの配下の変更パスを出発点にしない。
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from bitz import basecompare
from bitz import check as check_mod
from bitz.cliargs import ParsedArgs
from bitz.errors import CliArgError

ROOT_YAML = 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\nworkspace:\n  id: platform\n'
MEMBER_YAML = 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\nworkspace:\n  id: {wid}\n'
CATALOG = "multiWorkspace:\n  members:\n    - id: web\n      path: apps/web\n    - id: api\n      path: services/api\n"


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
        f"---\nid: {doc_id}\ntitle: REQ\nstatus: approved\n---\n\n# {doc_id} REQ\n\n"
        "## Intent\n\n意図。\n\n## Acceptance Criteria\n\n"
        f"- [{doc_id}:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 秘密情報を出力しない。\n\n"
        "## Verification\n\n未証明。\n"
    )


def _tech(doc_id: str, *, relations: dict[str, list[str]] | None = None, implements: list[str] | None = None,
          body: str = "本文。") -> str:
    fm = f"---\nid: {doc_id}\ntitle: TECH\nstatus: approved\n"
    if relations:
        fm += "relations:\n" + "".join(f"  {k}: [{', '.join(v)}]\n" for k, v in relations.items())
    if implements:
        fm += f"implements: [{', '.join(implements)}]\n"
    return f"{fm}---\n\n# {doc_id} TECH\n\n## Context\n\n{body}\n"


def _run(cwd, positionals=None, *, flags=None, single=None) -> tuple[dict, int]:
    parsed = ParsedArgs(
        operation="check", positionals=list(positionals or []), flags=set(flags or ()),
        single={"--base": "HEAD", **(single or {})}, repeat={},
    )
    return check_mod.run(parsed, str(cwd), dict(os.environ))


def _doc_diags(result: dict, ws: str, path: str) -> list[dict]:
    return [d for d in result["diagnostics"] if d["source"].get("workspaceId") == ws and d["source"].get("path") == path]


def _make_repo(root: Path) -> None:
    """platform（ルート）、web、apiの複合ワークスペース。

    web::TECH-030 -requires-> api::TECH-020 -requires-> web::TECH-031（作業ワークスペースの別名）、
    web::TECH-030 -refines-> platform::REQ-001:AC-01。
    api::TECH-040 -refines-> web::TECH-030（作業ワークスペースの文書を直接参照する他のメンバーの文書）。
    api::TECH-060 -refines-> api::TECH-020（閉包で到達した他のメンバーの文書の逆参照）。
    api::TECH-050はどれとも関係がない。誤りを持つ文書は、どのワークスペースの何の文書かを診断で見分けられるようにしてある。
    """

    _init_repo(root)
    _write(root, ".spec/bitz.yaml", ROOT_YAML + CATALOG)
    _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
    _write(root, "apps/web/.spec/bitz.yaml", MEMBER_YAML.format(wid="web"))
    _write(root, "apps/web/.spec/technical/TECH-030.md", _tech(
        "TECH-030", relations={"requires": ["api::TECH-020"], "refines": ["platform::REQ-001:AC-01"]}))
    # 別名経由で完全検査の対象に入ることを、実装パスの不在（SPEC-PATH-INVALID-001）で見分ける。
    _write(root, "apps/web/.spec/technical/TECH-031.md", _tech("TECH-031", implements=["src/missing_web.py"]))
    _write(root, "services/api/.spec/bitz.yaml", MEMBER_YAML.format(wid="api"))
    _write(root, "services/api/.spec/technical/TECH-020.md", _tech(
        "TECH-020", relations={"requires": ["web::TECH-031", "TECH-999"]}))
    _write(root, "services/api/.spec/technical/TECH-040.md", _tech(
        "TECH-040", relations={"refines": ["web::TECH-030"]}, implements=["src/missing_040.py"]))
    _write(root, "services/api/.spec/technical/TECH-050.md", _tech(
        "TECH-050", relations={"requires": ["TECH-998"]}, implements=["src/missing_050.py"]))
    _write(root, "services/api/.spec/technical/TECH-060.md", _tech(
        "TECH-060", relations={"refines": ["TECH-020"]}, implements=["src/missing_060.py"]))
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "base")


class ChangedScopeInMemberTests(unittest.TestCase):
    def _changed_repo(self, root: Path) -> None:
        _make_repo(root)
        _write(root, "apps/web/.spec/technical/TECH-030.md", _tech(
            "TECH-030", relations={"requires": ["api::TECH-020"], "refines": ["platform::REQ-001:AC-01"]},
            body="変更した本文。"))

    def test_closure_crosses_workspaces_and_reports_with_owner_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._changed_repo(root)

            result, exit_code = _run(root / "apps/web")
            self.assertEqual(result["scope"], "changed")
            self.assertEqual(result["workspace"], {"id": "web", "path": "apps/web"})
            self.assertEqual(result["selection"]["targetDocumentCount"], 1)
            self.assertEqual(exit_code, 1, result["diagnostics"])

            # 修飾した参照を存在しない参照として誤検出しない（web側の宣言には誤りがない）。
            self.assertEqual(_doc_diags(result, "web", ".spec/technical/TECH-030.md"), [])
            # 閉包で到達した他のメンバーの文書の誤りを、所有ワークスペースのIDとそのルート相対のパスで返す。
            api_020 = _doc_diags(result, "api", ".spec/technical/TECH-020.md")
            self.assertEqual([(d["code"], d.get("evidence")) for d in api_020], [("SPEC-RELATION-MISSING-001", "TECH-999")])
            # 閉包が作業ワークスペースの別名（web::TECH-031）へ入っても、作業ワークスペースの文書として検査する。
            web_031 = _doc_diags(result, "web", ".spec/technical/TECH-031.md")
            self.assertEqual([d["code"] for d in web_031], ["SPEC-PATH-INVALID-001"])

    def test_direct_reverse_reference_of_working_workspace_document_is_checked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._changed_repo(root)

            result, _exit_code = _run(root / "apps/web")
            # 作業ワークスペースの変更した文書を`refines`するapiの文書は、完全検査の対象になる。
            api_040 = _doc_diags(result, "api", ".spec/technical/TECH-040.md")
            self.assertEqual([d["code"] for d in api_040], ["SPEC-PATH-INVALID-001"])

    def test_unrelated_and_closure_reverse_reference_documents_are_not_checked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._changed_repo(root)

            result, _exit_code = _run(root / "apps/web")
            # 無関係な文書（TECH-050）も、閉包で到達した文書の逆参照（TECH-060）も対象にしない。
            self.assertEqual(_doc_diags(result, "api", ".spec/technical/TECH-050.md"), [])
            self.assertEqual(_doc_diags(result, "api", ".spec/technical/TECH-060.md"), [])

    def test_unrelated_member_change_is_not_a_starting_point(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_repo(root)
            # webの文書は変更せず、無関係なapiの文書だけを変更する。
            _write(root, "services/api/.spec/technical/TECH-050.md", _tech(
                "TECH-050", relations={"requires": ["TECH-998"]}, implements=["src/missing_050.py"], body="変更。"))

            result, exit_code = _run(root / "apps/web")
            self.assertEqual(result["selection"], {
                "changedPathCount": 0, "targetDocumentCount": 0, "excludedCodeTestPathCount": 0})
            self.assertEqual(exit_code, 0, result["diagnostics"])

    def test_repeated_runs_give_identical_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._changed_repo(root)
            first, _ = _run(root / "apps/web")
            second, _ = _run(root / "apps/web")
            for r in (first, second):
                r.pop("durationMs", None)
            self.assertEqual(first, second)


class FullScopeInMemberTests(unittest.TestCase):
    def test_full_in_member_resolves_qualified_refs_and_reports_member_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_repo(root)

            result, _exit_code = _run(root / "apps/web", flags={"--full"})
            self.assertEqual(result["scope"], "full")
            self.assertEqual(result["workspace"], {"id": "web", "path": "apps/web"})
            self.assertEqual(_doc_diags(result, "web", ".spec/technical/TECH-030.md"), [])
            codes = [d["code"] for d in result["diagnostics"]]
            self.assertNotIn("SPEC-RELATION-MISSING-001", [
                d["code"] for d in result["diagnostics"] if d["source"].get("workspaceId") == "web"])
            self.assertIn("SPEC-PATH-INVALID-001", codes)

    def test_full_includes_reached_documents_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_repo(root)

            result, _exit_code = _run(root / "apps/web", flags={"--full"})
            api_paths = {d["source"]["path"] for d in result["diagnostics"] if d["source"].get("workspaceId") == "api"}
            # 閉包で到達したTECH-020と、webの文書を直接参照するTECH-040だけが対象になる。
            self.assertEqual(api_paths, {".spec/technical/TECH-020.md", ".spec/technical/TECH-040.md"})
            # web（2件）、platform::REQ-001（1件）、api::TECH-020、api::TECH-040。
            self.assertEqual(result["checkedDocumentCount"], 5)
            self.assertEqual(result["checkedStatementCount"], 1)


class SelectedScopeInMemberTests(unittest.TestCase):
    def test_selected_unqualified_id_includes_reverse_reference_of_working_workspace_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_repo(root)

            result, _exit_code = _run(root / "apps/web", ["TECH-030"])
            self.assertEqual(result["scope"], "selected")
            self.assertEqual(result["workspace"], {"id": "web", "path": "apps/web"})
            api_paths = {d["source"]["path"] for d in result["diagnostics"] if d["source"].get("workspaceId") == "api"}
            self.assertEqual(api_paths, {".spec/technical/TECH-020.md", ".spec/technical/TECH-040.md"})


class WorkspaceOptionTests(unittest.TestCase):
    def test_workspace_option_at_root_selects_member(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_repo(root)

            result, exit_code = _run(root, flags={"--full"}, single={"--workspace": "web"})
            self.assertEqual(result["workspace"], {"id": "web", "path": "apps/web"})
            self.assertEqual(_doc_diags(result, "web", ".spec/technical/TECH-030.md"), [])
            self.assertEqual(exit_code, 1)

    def test_workspace_option_can_select_root_from_member(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_repo(root)

            result, _exit_code = _run(root / "apps/web", flags={"--full"}, single={"--workspace": "platform"})
            self.assertEqual(result["workspace"], {"id": "platform", "path": "."})

    def test_unknown_workspace_is_an_argument_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_repo(root)
            with self.assertRaises(CliArgError):
                _run(root, flags={"--full"}, single={"--workspace": "missing"})

    def test_workspace_option_conflicting_with_qualified_root_is_an_argument_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_repo(root)
            with self.assertRaises(CliArgError):
                _run(root, ["api::TECH-020"], single={"--workspace": "web"})


class RootWorkspaceOwnershipTests(unittest.TestCase):
    def test_root_ignores_changes_under_members(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_repo(root)
            _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001") + "\n補足。\n")
            _write(root, "apps/web/.spec/technical/TECH-031.md", _tech(
                "TECH-031", implements=["src/missing_web.py"], body="変更。"))
            _write(root, "apps/web/src/new.py", "x = 1\n")

            result, _exit_code = _run(root)
            self.assertEqual(result["workspace"], {"id": "platform", "path": "."})
            # ルートが所有する変更は`REQ-001.md`の1件だけで、メンバーの配下の2件は数えない。
            self.assertEqual(result["selection"], {
                "changedPathCount": 1, "targetDocumentCount": 1, "excludedCodeTestPathCount": 0})


class ReverseReferenceOwnerRuleTests(unittest.TestCase):
    """直接の逆参照の採用規則（check §6）。作業ワークスペースの文書は、完全検査の対象のどの文書を参照していても採用する。
    他のメンバーの文書は、作業ワークスペースの文書を参照するものだけを採用する。
    """

    def _repo(self, root: Path) -> None:
        _make_repo(root)
        # webのTECH-012は、閉包で到達するapi::TECH-020だけを`related`で参照し、実装パスが存在しない。
        _write(root, "apps/web/.spec/technical/TECH-012.md", _tech(
            "TECH-012", relations={"related": ["api::TECH-020"]}, implements=["src/missing_012.py"]))
        _git(root, "add", "-A")
        _git(root, "commit", "-q", "-m", "TECH-012")
        _write(root, "apps/web/.spec/technical/TECH-030.md", _tech(
            "TECH-030", relations={"requires": ["api::TECH-020"], "refines": ["platform::REQ-001:AC-01"]},
            body="変更した本文。"))

    def test_changed_checks_working_workspace_document_that_references_only_closure_document(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._repo(root)

            result, _exit_code = _run(root / "apps/web")
            web_012 = _doc_diags(result, "web", ".spec/technical/TECH-012.md")
            self.assertEqual([d["code"] for d in web_012], ["SPEC-PATH-INVALID-001"])
            # 他のメンバーの文書は、閉包の文書だけを参照するもの(TECH-060)を引き続き対象にしない。
            self.assertEqual(_doc_diags(result, "api", ".spec/technical/TECH-060.md"), [])

    def test_selected_checks_working_workspace_document_that_references_only_context_document(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._repo(root)

            result, _exit_code = _run(root / "apps/web", ["TECH-030"])
            web_012 = _doc_diags(result, "web", ".spec/technical/TECH-012.md")
            self.assertEqual([d["code"] for d in web_012], ["SPEC-PATH-INVALID-001"])
            self.assertEqual(_doc_diags(result, "api", ".spec/technical/TECH-060.md"), [])

    def test_full_still_excludes_other_member_document_that_references_only_closure_document(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._repo(root)

            result, _exit_code = _run(root / "apps/web", flags={"--full"})
            self.assertEqual(len(_doc_diags(result, "web", ".spec/technical/TECH-012.md")), 1)
            self.assertEqual(_doc_diags(result, "api", ".spec/technical/TECH-060.md"), [])


class ImpactCandidateScopeTests(unittest.TestCase):
    """影響候補（`SPEC-IMPACT-OUTDATED-001`）は作業ワークスペースの文書だけに、1文書につき1件出す（check §8）。"""

    def test_impact_candidates_are_limited_to_working_workspace_documents_without_duplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_repo(root)
            _write(root, "apps/web/.spec/technical/TECH-032.md", _tech("TECH-032", relations={"requires": ["TECH-030"]}))
            _write(root, "apps/web/.spec/technical/TECH-033.md", _tech("TECH-033", relations={"requires": ["web::TECH-030"]}))
            _git(root, "add", "-A")
            _git(root, "commit", "-q", "-m", "impact")
            _write(root, "apps/web/.spec/technical/TECH-030.md", _tech(
                "TECH-030", relations={"requires": ["api::TECH-020"], "refines": ["platform::REQ-001:AC-01"]},
                body="変更した本文。"))

            result, _exit_code = _run(root / "apps/web")
            impact = sorted(
                (d["source"]["workspaceId"], d["source"]["path"])
                for d in result["diagnostics"] if d["code"] == "SPEC-IMPACT-OUTDATED-001"
            )
            # webの2文書に1件ずつ。作業ワークスペースの別名による重複も、他のメンバーの文書(api::TECH-040が
            # web::TECH-030をrefinesしている)への警告もない。
            self.assertEqual(impact, [
                ("web", ".spec/technical/TECH-032.md"), ("web", ".spec/technical/TECH-033.md"),
            ])


class ReachedDocumentCatalogDiagnosticsTests(unittest.TestCase):
    """到達した他のメンバーの文書のファイル単位の診断(フロントマター、EARS-AI、スタイル)を、所有ワークスペースの名前で返す。"""

    def test_style_diagnostic_of_reached_document_is_reported_with_owner(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_repo(root)
            broken = _tech("TECH-020", relations={"requires": ["web::TECH-031"]}).replace("# TECH-020 TECH", "# 違う見出し")
            _write(root, "services/api/.spec/technical/TECH-020.md", broken)
            _write(root, "services/api/.spec/technical/TECH-050.md", _tech("TECH-050").replace("# TECH-050 TECH", "# 無関係な見出し"))
            _git(root, "add", "-A")
            _git(root, "commit", "-q", "-m", "style")
            _write(root, "apps/web/.spec/technical/TECH-030.md", _tech(
                "TECH-030", relations={"requires": ["api::TECH-020"], "refines": ["platform::REQ-001:AC-01"]},
                body="変更した本文。"))

            result, _exit_code = _run(root / "apps/web")
            reached = _doc_diags(result, "api", ".spec/technical/TECH-020.md")
            self.assertEqual([d["code"] for d in reached], ["SPEC-STYLE-H1-001"])
            # 到達していない文書の診断は返さない。
            self.assertEqual(_doc_diags(result, "api", ".spec/technical/TECH-050.md"), [])


class CycleDiagnosticsScopeTests(unittest.TestCase):
    """循環の診断（`CTX-CYCLE-001`）は、完全検査の対象の文書へ帰属するものだけを返す（`check.md §3`）。"""

    def _repo_with_cycles(self, root: Path) -> None:
        _make_repo(root)
        # webの対象外の循環。
        _write(root, "apps/web/.spec/technical/TECH-070.md", _tech("TECH-070", relations={"requires": ["TECH-071"]}))
        _write(root, "apps/web/.spec/technical/TECH-071.md", _tech("TECH-071", relations={"requires": ["TECH-070"]}))
        # apiの無関係な循環。
        _write(root, "services/api/.spec/technical/TECH-080.md", _tech("TECH-080", relations={"requires": ["TECH-081"]}))
        _write(root, "services/api/.spec/technical/TECH-081.md", _tech("TECH-081", relations={"requires": ["TECH-080"]}))
        # 閉包で到達するTECH-020が属する循環。
        _write(root, "services/api/.spec/technical/TECH-020.md", _tech(
            "TECH-020", relations={"requires": ["web::TECH-031", "TECH-999", "TECH-072"]}))
        _write(root, "services/api/.spec/technical/TECH-072.md", _tech("TECH-072", relations={"requires": ["TECH-020"]}))
        _git(root, "add", "-A")
        _git(root, "commit", "-q", "-m", "cycles")
        _write(root, "apps/web/.spec/technical/TECH-030.md", _tech(
            "TECH-030", relations={"requires": ["api::TECH-020"], "refines": ["platform::REQ-001:AC-01"]},
            body="変更した本文。"))

    def test_cycles_outside_the_checked_documents_are_not_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._repo_with_cycles(root)

            result, _exit_code = _run(root / "apps/web")
            cycle_paths = {
                (d["source"]["workspaceId"], d["source"]["path"])
                for d in result["diagnostics"] if d["code"] == "CTX-CYCLE-001"
            }
            self.assertEqual(cycle_paths, {
                ("api", ".spec/technical/TECH-020.md"), ("api", ".spec/technical/TECH-072.md"),
            })


class BasecompareQualifiedIdTests(unittest.TestCase):
    def test_ref_document_id_keeps_workspace_qualifier(self):
        self.assertEqual(basecompare.ref_document_id("DOC-1"), "DOC-1")
        self.assertEqual(basecompare.ref_document_id("DOC-1:AC-01"), "DOC-1")
        self.assertEqual(basecompare.ref_document_id("ws::DOC-1"), "ws::DOC-1")
        self.assertEqual(basecompare.ref_document_id("ws::DOC-1:AC-01"), "ws::DOC-1")


if __name__ == "__main__":
    unittest.main()
