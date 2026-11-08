"""基準版の文書と同じパスに、現在版でIDを読めないファイルがある場合の`check`の単体試験（確認事項C105、`check` §5、文書・フロントマター・状態仕様 §9）。

規範（`check` §5）: 基準版の文書と同じパスに、現在版でIDを読めない（フロントマターの不正などで索引に入らない）ファイルが存在する場合は、
削除（`SPEC-STATE-TRANSITION-001`）とせず、その文書の状態遷移、承認済み要求の保護（`SPEC-SAFETY-APPROVED-001`）、影響候補
（`SPEC-IMPACT-OUTDATED-001`）の比較も行わない（比べる現在版がないため）。そのファイル自身の診断（`SPEC-FM-SCHEMA-001`など）は、引数なしの`check`でも、
変更されたパスの診断として返す。IDでもパスでも現在版と対応しない場合（パスの変更とIDを読めない破損が同時に起きた場合を含む）は、従来どおり削除とする。

修正前のCoreは、IDを読めない現在版を削除として`SPEC-STATE-TRANSITION-001`を返し、依存元へ`SPEC-IMPACT-OUTDATED-001`を返し、
そのファイル自身の`SPEC-FM-SCHEMA-001`は引数なしの`check`で返さなかった。各試験の期待値は規範のリテラルで、Coreの出力からは導かない。
対照の試験（削除、パスの変更と破損、IDを読める変更）は、修正前のCoreも通る。
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from bitz import check as check_mod
from bitz.cliargs import parse_argv

_GIT_ENV = {"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}
SCHEMA = "SPEC-FM-SCHEMA-001"
TRANSITION = "SPEC-STATE-TRANSITION-001"
IMPACT = "SPEC-IMPACT-OUTDATED-001"
SAFETY = "SPEC-SAFETY-APPROVED-001"
MISSING = "SPEC-RELATION-MISSING-001"
TECH_2 = ".spec/technical/TECH-002.md"
HEAD = 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\n'
TECH_1 = ".spec/technical/TECH-001.md"


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, env={**os.environ, **_GIT_ENV}, check=True, capture_output=True, text=True)


def _write(root: Path, rel: str, content: str) -> None:
    full = root / rel
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")


def _req(doc_id: str, *, title: str = "REQ", status: str = "approved") -> str:
    return (
        f"---\nid: {doc_id}\ntitle: {title}\nstatus: {status}\n---\n\n# {doc_id} {title}\n\n## Intent\n\n意図。\n\n## Acceptance Criteria\n\n"
        f"- [{doc_id}:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 秘密情報を出力しない。\n\n## Verification\n\n未証明。\n"
    )


def _tech(doc_id: str, *, status: str = "approved", requires: list[str] | None = None) -> str:
    relations = f"relations:\n  requires: [{', '.join(requires)}]\n" if requires else ""
    return f"---\nid: {doc_id}\ntitle: TECH\nstatus: {status}\n{relations}---\n\n# {doc_id} TECH\n\n## Context\n\n本文。\n"


BROKEN_STATUS = "bogus"


class _Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.env = {**os.environ, **_GIT_ENV}

    def commit(self) -> None:
        _git(self.root, "init", "-q", "--initial-branch=main")
        _git(self.root, "config", "user.email", "t@t")
        _git(self.root, "config", "user.name", "t")
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-q", "-m", "base")

    def check(self, *argv: str, cwd: Path | None = None) -> dict:
        return check_mod.run(parse_argv(["check", *argv, "--format", "json"]), str(cwd or self.root), self.env)[0]

    def found(self, *argv: str) -> list[tuple[str, str]]:
        """診断の``(コード, パス)``。"""

        return sorted((d["code"], d["source"].get("path", "")) for d in self.check(*argv)["diagnostics"])


class SingleWorkspaceTests(_Base):
    """`REQ-001`と、それを必要とする`TECH-001`、`TECH-001`を必要とする`TECH-002`（`TECH-001`の変更の影響候補）を基準版に置く。"""

    def build(self) -> None:
        _write(self.root, ".spec/bitz.yaml", HEAD)
        _write(self.root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
        _write(self.root, TECH_1, _tech("TECH-001"))
        _write(self.root, ".spec/technical/TECH-002.md", _tech("TECH-002", requires=["TECH-001"]))
        self.commit()

    def break_tech_1(self, rel: str = TECH_1) -> None:
        _write(self.root, rel, _tech("TECH-001", status=BROKEN_STATUS))

    # --- 欠陥（修正前のCoreが失敗する） -----------------------------------------------------

    def test_broken_file_at_the_same_path_is_not_a_deletion_and_returns_its_own_diagnostic(self):
        """再現済みの欠陥: `status`を不正値にした`TECH-001`は、削除ではなく、影響候補も出さず、自身の`SPEC-FM-SCHEMA-001`だけを返す。"""

        self.build()
        self.break_tech_1()
        # `TECH-001`を`requires`する`TECH-002`は、その文書への直接の逆参照として完全検査の対象に入り、索引にない参照先の不在を返す（`check` §5）。
        self.assertEqual(self.found(), [(SCHEMA, TECH_1), (MISSING, TECH_2)])

    def test_full_check_does_not_report_a_deletion_either(self):
        self.build()
        self.break_tech_1()
        # 全体の検査は文書の一覧全体を検査するので、`TECH-001`を必要とする`TECH-002`は、索引にない参照先の`SPEC-RELATION-MISSING-001`を返す。
        self.assertEqual(self.found("--full"), [(SCHEMA, TECH_1), (MISSING, TECH_2)])

    def test_broken_file_with_unreadable_front_matter_delimiter(self):
        """フロントマターの区切りがなく、IDを読めない場合も同じ。"""

        self.build()
        _write(self.root, TECH_1, "# TECH-001 TECH\n\n本文。\n")
        self.assertEqual(self.found(), [(SCHEMA, TECH_1), (MISSING, TECH_2)])

    def test_approved_protection_is_not_compared(self):
        """承認済み要求の保護を比べない: `REQ-001`の意味（`title`）を変えて破損しても`SPEC-SAFETY-APPROVED-001`を返さない。"""

        self.build()
        _write(self.root, ".spec/requirements/REQ-001.md", _req("REQ-001", title="変えた", status=BROKEN_STATUS))
        self.assertEqual(self.found(), [(SCHEMA, ".spec/requirements/REQ-001.md")])

    def test_new_file_with_unreadable_id_returns_its_own_diagnostic(self):
        """未追跡の新しいファイルでIDを読めなければ、変更されたパスの診断として返す。"""

        self.build()
        _write(self.root, ".spec/technical/TECH-009.md", _tech("TECH-009", status=BROKEN_STATUS))
        self.assertEqual(self.found(), [(SCHEMA, ".spec/technical/TECH-009.md")])

    def test_selection_counts_the_owner_of_the_broken_file_but_not_a_new_broken_file(self):
        """引数なしの`check`は、IDを読めないファイルを基準版のIDの所有文書として`targetDocumentCount`に数える。基準版にない新規のファイルは数えない。"""

        self.build()
        self.break_tech_1()
        self.assertEqual(self.check()["selection"], {"changedPathCount": 1, "targetDocumentCount": 1, "excludedCodeTestPathCount": 0})
        _git(self.root, "checkout", "--", TECH_1)
        _write(self.root, ".spec/technical/TECH-009.md", _tech("TECH-009", status=BROKEN_STATUS))
        self.assertEqual(self.check()["selection"], {"changedPathCount": 1, "targetDocumentCount": 0, "excludedCodeTestPathCount": 0})

    def test_only_direct_references_to_the_unreadable_document_join_the_full_inspection(self):
        """完全検査の対象に加えるのは、IDを読めない文書への直接の逆参照だけである。無関係な文書は検査しない。"""

        _write(self.root, ".spec/technical/TECH-003.md", _tech("TECH-003", requires=["TECH-099"]))
        self.build()
        self.break_tech_1()
        found = self.found()
        self.assertIn((MISSING, TECH_2), found)
        self.assertNotIn((MISSING, ".spec/technical/TECH-003.md"), found)

    def test_moved_document_with_a_broken_file_left_behind_is_still_compared_by_id(self):
        """基準版のIDが現在版の別のパスにあれば、元のパスに壊れたファイルがあっても、IDで対応付けて比べる（承認済み要求の保護と影響候補を失わない）。"""

        _write(self.root, ".spec/technical/TECH-003.md", _tech("TECH-003").replace("status: approved\n", "status: approved\nrelations:\n  refines: [REQ-001]\n"))
        self.build()
        _write(self.root, ".spec/requirements/REQ-001-moved.md", _req("REQ-001", title="変えた"))
        _write(self.root, ".spec/requirements/REQ-001.md", _req("REQ-001", status=BROKEN_STATUS))
        self.assertEqual(
            self.found(),
            [(SCHEMA, ".spec/requirements/REQ-001.md"), (IMPACT, ".spec/technical/TECH-003.md"), (SAFETY, ".spec/requirements/REQ-001-moved.md")],
        )

    # --- 対照 -------------------------------------------------------------------------------

    def test_deleted_file_is_still_a_deletion(self):
        """対照: 同じパスに何もなければ削除。"""

        self.build()
        (self.root / TECH_1).unlink()
        codes = self.found()
        self.assertIn((TRANSITION, TECH_1), codes)

    def test_move_and_break_at_the_same_time_is_a_deletion(self):
        """対照: パスの変更とIDを読めない破損が同時に起きた場合は、IDでもパスでも対応しないので削除（従来どおり依存元へ影響候補も返す）。"""

        self.build()
        (self.root / TECH_1).unlink()
        self.break_tech_1(".spec/technical/TECH-001-moved.md")
        found = self.found()
        self.assertIn((TRANSITION, TECH_1), found)
        self.assertIn((IMPACT, TECH_2), found)

    def test_move_and_break_at_the_same_time_returns_the_broken_file_diagnostic(self):
        """パスの変更と破損が同時でも、破損したファイル自身の診断は、変更されたパスの診断として返す。"""

        self.build()
        (self.root / TECH_1).unlink()
        self.break_tech_1(".spec/technical/TECH-001-moved.md")
        self.assertEqual(
            self.found(), [(SCHEMA, ".spec/technical/TECH-001-moved.md"), (IMPACT, TECH_2), (TRANSITION, TECH_1)]
        )

    def test_valid_change_still_reports_impact_candidate(self):
        """対照: IDを読める変更（`approved`から`outdated`）では、依存元の影響候補を返す（比較が働くことの確認）。"""

        self.build()
        _write(self.root, TECH_1, _tech("TECH-001", status="outdated"))
        self.assertEqual(self.found(), [(IMPACT, ".spec/technical/TECH-002.md")])

    def test_valid_meaning_change_of_approved_requirement_is_still_protected(self):
        """対照: IDを読める意味の変更では`SPEC-SAFETY-APPROVED-001`を返す。"""

        self.build()
        _write(self.root, ".spec/requirements/REQ-001.md", _req("REQ-001", title="変えた"))
        self.assertIn((SAFETY, ".spec/requirements/REQ-001.md"), self.found())

    def test_changing_to_another_readable_id_is_a_deletion(self):
        """対照: 同じパスでも、IDを読める別のIDに変えた場合は、IDを読めないのではないので削除。"""

        self.build()
        _write(self.root, TECH_1, _tech("TECH-007"))
        self.assertIn((TRANSITION, TECH_1), self.found())

    def test_unchanged_repository_has_no_diagnostics(self):
        self.build()
        self.assertEqual(self.found(), [])


class MultiWorkspaceTests(_Base):
    """複合ワークスペース`platform`（ルート）と`web`。`web`の文書を基準版に置く。"""

    def build(self) -> None:
        _write(self.root, ".spec/bitz.yaml", HEAD + "workspace:\n  id: platform\nmultiWorkspace:\n  members:\n    - id: web\n      path: apps/web\n")
        _write(self.root, "apps/web/.spec/bitz.yaml", HEAD + "workspace:\n  id: web\n")
        _write(self.root, "apps/web/.spec/technical/TECH-001.md", _tech("TECH-001"))
        _write(self.root, "apps/web/.spec/technical/TECH-002.md", _tech("TECH-002", requires=["TECH-001"]))
        self.commit()

    def test_all_workspaces_broken_member_file_is_not_a_deletion(self):
        self.build()
        _write(self.root, "apps/web/.spec/technical/TECH-001.md", _tech("TECH-001", status=BROKEN_STATUS))
        result = self.check("--all-workspaces")
        web = next(w for w in result["workspaces"] if w["id"] == "web")
        self.assertEqual(
            [(d["code"], d["source"]["path"]) for d in web["diagnostics"]],
            [(SCHEMA, ".spec/technical/TECH-001.md"), (MISSING, ".spec/technical/TECH-002.md")],
        )
        self.assertEqual(result["diagnostics"], [])

    def test_all_workspaces_deleted_member_file_is_still_a_deletion(self):
        """対照: 何もなければ削除。"""

        self.build()
        (self.root / "apps/web/.spec/technical/TECH-001.md").unlink()
        result = self.check("--all-workspaces")
        web = next(w for w in result["workspaces"] if w["id"] == "web")
        self.assertIn((TRANSITION, ".spec/technical/TECH-001.md"), [(d["code"], d["source"]["path"]) for d in web["diagnostics"]])

    def test_working_member_broken_file_is_not_a_deletion(self):
        """複合ワークスペース内の単独操作（`--workspace web`）でも同じ。"""

        self.build()
        _write(self.root, "apps/web/.spec/technical/TECH-001.md", _tech("TECH-001", status=BROKEN_STATUS))
        result = self.check("--workspace", "web")
        self.assertEqual(
            [(d["code"], d["source"]["path"]) for d in result["diagnostics"]],
            [(SCHEMA, ".spec/technical/TECH-001.md"), (MISSING, ".spec/technical/TECH-002.md")],
        )

    def test_moved_member_document_with_a_broken_file_left_behind_is_still_compared_by_id(self):
        """メンバーの比較（`--all-workspaces`と、複合ワークスペース内の単独操作）でも、基準版のIDが別のパスにあればIDで対応付けて比べる。"""

        _write(self.root, "apps/web/.spec/requirements/REQ-100.md", _req("REQ-100"))
        self.build()
        _write(self.root, "apps/web/.spec/requirements/REQ-100-moved.md", _req("REQ-100", title="変えた"))
        _write(self.root, "apps/web/.spec/requirements/REQ-100.md", _req("REQ-100", status=BROKEN_STATUS))
        expected = [(SCHEMA, ".spec/requirements/REQ-100.md"), (SAFETY, ".spec/requirements/REQ-100-moved.md")]
        web = next(w for w in self.check("--all-workspaces")["workspaces"] if w["id"] == "web")
        self.assertEqual(sorted((d["code"], d["source"]["path"]) for d in web["diagnostics"]), expected)
        single = self.check("--workspace", "web")
        self.assertEqual(sorted((d["code"], d["source"]["path"]) for d in single["diagnostics"]), expected)


if __name__ == "__main__":
    unittest.main()
