"""`basecompare.state_transition_diagnostics`の単体試験。

`02_SPECモデル/02_文書・Frontmatter・状態仕様.md §6・§9`の遷移表を、REQ/TECH/ADR/TASKそれぞれの
全許可・禁止遷移で検査する。新規文書（基準版に不在）、rename（path差だけ）、削除、
ID重複でcheckの索引から除かれた文書を削除と誤検出しないことも確認する。
"""

import unittest

from bitz import basecompare
from bitz.document import DocEntry


def _entry(doc_id: str, kind: str, status: str, path: str | None = None) -> DocEntry:
    path = path or f".spec/{kind.lower()}/{doc_id}.md"
    return DocEntry(path=path, kind=kind, doc_id=doc_id, title="t", status=status, frontmatter={"id": doc_id, "title": "t", "status": status})


# 文書・Frontmatter・状態仕様 §6の許可遷移表（自己ループ含む）。
_REQ_TECH_ALLOWED = {
    ("draft", "draft"), ("draft", "approved"), ("draft", "rejected"),
    ("approved", "approved"), ("approved", "draft"), ("approved", "outdated"),
    ("outdated", "outdated"), ("outdated", "draft"), ("outdated", "approved"),
    ("rejected", "rejected"),
}
_ALL_REQ_TECH_STATUSES = ("draft", "approved", "outdated", "rejected")

_ADR_ALLOWED = {
    ("proposed", "proposed"), ("proposed", "accepted"), ("proposed", "rejected"),
    ("accepted", "accepted"), ("accepted", "superseded"),
    ("rejected", "rejected"),
    ("superseded", "superseded"),
}
_ALL_ADR_STATUSES = ("proposed", "accepted", "rejected", "superseded")

_TASK_ALLOWED = {
    ("open", "open"), ("open", "done"), ("open", "cancelled"),
    ("done", "done"),
    ("cancelled", "cancelled"),
}
_ALL_TASK_STATUSES = ("open", "done", "cancelled")


class TransitionMatrixTests(unittest.TestCase):
    def _assert_matrix(self, kind: str, all_statuses: tuple[str, ...], allowed: set[tuple[str, str]]) -> None:
        for from_status in all_statuses:
            for to_status in all_statuses:
                base_by_id = {"X-001": _entry("X-001", kind, from_status)}
                current_by_id = {"X-001": _entry("X-001", kind, to_status)}
                diags = basecompare.state_transition_diagnostics(base_by_id, current_by_id, "root")
                with self.subTest(kind=kind, frm=from_status, to=to_status):
                    if (from_status, to_status) in allowed:
                        self.assertEqual(diags, [], f"{kind} {from_status}->{to_status}は許可されるべき")
                    else:
                        self.assertEqual(len(diags), 1)
                        self.assertEqual(diags[0].code, "SPEC-STATE-TRANSITION-001")
                        self.assertEqual(diags[0].source["key"], "status")

    def test_req_tech_matrix(self):
        self._assert_matrix("REQ", _ALL_REQ_TECH_STATUSES, _REQ_TECH_ALLOWED)
        self._assert_matrix("TECH", _ALL_REQ_TECH_STATUSES, _REQ_TECH_ALLOWED)

    def test_adr_matrix(self):
        self._assert_matrix("ADR", _ALL_ADR_STATUSES, _ADR_ALLOWED)

    def test_task_matrix(self):
        self._assert_matrix("TASK", _ALL_TASK_STATUSES, _TASK_ALLOWED)

    def test_forbidden_message_mentions_kind_and_statuses(self):
        base_by_id = {"TASK-001": _entry("TASK-001", "TASK", "done")}
        current_by_id = {"TASK-001": _entry("TASK-001", "TASK", "open")}
        diags = basecompare.state_transition_diagnostics(base_by_id, current_by_id, "root")
        self.assertEqual(len(diags), 1)
        self.assertEqual(diags[0].summary, "done TASKをopenへ戻すことはできません")

    def test_new_document_not_in_base_is_not_diagnosed(self):
        # 基準版に存在しない新規文書は比較対象外（過去状態を推測しない）。
        base_by_id: dict = {}
        current_by_id = {"REQ-001": _entry("REQ-001", "REQ", "draft")}
        diags = basecompare.state_transition_diagnostics(base_by_id, current_by_id, "root")
        self.assertEqual(diags, [])

    def test_rename_same_id_different_path_is_not_deletion(self):
        base_by_id = {"REQ-001": _entry("REQ-001", "REQ", "approved", path=".spec/requirements/REQ-001-old.md")}
        current_by_id = {"REQ-001": _entry("REQ-001", "REQ", "approved", path=".spec/requirements/REQ-001-new.md")}
        diags = basecompare.state_transition_diagnostics(base_by_id, current_by_id, "root")
        self.assertEqual(diags, [])

    def test_deleted_document_is_flagged(self):
        base_by_id = {"TECH-001": _entry("TECH-001", "TECH", "approved")}
        current_by_id: dict = {}
        diags = basecompare.state_transition_diagnostics(base_by_id, current_by_id, "root")
        self.assertEqual(len(diags), 1)
        self.assertEqual(diags[0].code, "SPEC-STATE-TRANSITION-001")
        self.assertEqual(diags[0].summary, "管理済みSPECが削除されています")
        self.assertNotIn("key", diags[0].source)
        self.assertEqual(diags[0].source["path"], ".spec/tech/TECH-001.md")

    def test_id_collision_removed_from_index_is_not_treated_as_deleted(self):
        # ID重複で現在版のcheck索引（id_index）から除かれた文書は、削除ではなく重複として
        # 別のDiagnostic（SPEC-ID-DUPLICATE-001）が既に扱う。ここで二重にDiagnosticを作らない。
        base_by_id = {"TECH-001": _entry("TECH-001", "TECH", "approved")}
        current_by_id: dict = {}  # 重複によりid_indexから除外された想定
        diags = basecompare.state_transition_diagnostics(
            base_by_id, current_by_id, "root", current_ids_present={"TECH-001"}
        )
        self.assertEqual(diags, [])


if __name__ == "__main__":
    unittest.main()
