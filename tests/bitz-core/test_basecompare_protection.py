"""`basecompare.approved_protection_diagnostics`の単体試験（文書・Frontmatter・状態仕様 §8）。

`title`、EARS-AI規範文の意味field、強い関係の変更は保護対象、`implements`・`tests`・`verify`・
`related`・`x-`拡張・説明文だけの変更は対象外であることを検査する。
"""

import unittest

from bitz import basecompare
from bitz.document import DocEntry

_STMT = {
    "id": "REQ-001:AC-01",
    "documentId": "REQ-001",
    "localId": "AC-01",
    "source": {"path": ".spec/requirements/REQ-001.md", "line": 10, "column": 1},
    "actor": "TargetSystem",
    "activation": {"kind": "ALWAYS"},
    "modality": "MUST",
    "reason": None,
    "operation": {"text": "秘密情報を出力しない"},
    "extensions": [],
}


def _req(*, title="対象", status="approved", relations=None, statements=None, path=".spec/requirements/REQ-001.md"):
    fm = {"id": "REQ-001", "title": title, "status": status}
    if relations is not None:
        fm["relations"] = relations
    entry = DocEntry(path=path, kind="REQ", doc_id="REQ-001", title=title, status=status, frontmatter=fm)
    entry.statements = statements if statements is not None else [_STMT]
    return entry


class ApprovedProtectionTests(unittest.TestCase):
    def test_unchanged_is_not_flagged(self):
        base = {"REQ-001": _req()}
        current = {"REQ-001": _req()}
        self.assertEqual(basecompare.approved_protection_diagnostics(base, current, "root"), [])

    def test_title_change_without_status_revert_is_flagged(self):
        base = {"REQ-001": _req(title="旧title")}
        current = {"REQ-001": _req(title="新title")}
        diags = basecompare.approved_protection_diagnostics(base, current, "root")
        self.assertEqual(len(diags), 1)
        self.assertEqual(diags[0].code, "SPEC-SAFETY-APPROVED-001")
        self.assertEqual(diags[0].source["key"], "title")

    def test_title_change_with_status_reverted_to_draft_is_allowed(self):
        base = {"REQ-001": _req(title="旧title")}
        current = {"REQ-001": _req(title="新title", status="draft")}
        self.assertEqual(basecompare.approved_protection_diagnostics(base, current, "root"), [])

    def test_strong_relation_change_is_flagged(self):
        base = {"REQ-001": _req(relations={"requires": ["TECH-001"]})}
        current = {"REQ-001": _req(relations={"requires": ["TECH-002"]})}
        diags = basecompare.approved_protection_diagnostics(base, current, "root")
        self.assertEqual(len(diags), 1)
        self.assertEqual(diags[0].source["key"], "relations.requires")

    def test_statement_semantic_change_is_flagged(self):
        changed_stmt = dict(_STMT, modality="SHOULD")
        base = {"REQ-001": _req(statements=[_STMT])}
        current = {"REQ-001": _req(statements=[changed_stmt])}
        diags = basecompare.approved_protection_diagnostics(base, current, "root")
        self.assertEqual(len(diags), 1)
        self.assertEqual(diags[0].source["key"], "statements")

    def test_implements_change_only_is_not_flagged(self):
        base = _req()
        base.frontmatter["implements"] = ["src/a.py"]
        current = _req()
        current.frontmatter["implements"] = ["src/b.py"]
        diags = basecompare.approved_protection_diagnostics({"REQ-001": base}, {"REQ-001": current}, "root")
        self.assertEqual(diags, [])

    def test_related_relation_change_only_is_not_flagged(self):
        base = {"REQ-001": _req(relations={"related": ["TECH-001"]})}
        current = {"REQ-001": _req(relations={"related": ["TECH-002"]})}
        self.assertEqual(basecompare.approved_protection_diagnostics(base, current, "root"), [])

    def test_x_extension_change_only_is_not_flagged(self):
        base = _req()
        base.frontmatter["x-risk"] = "low"
        current = _req()
        current.frontmatter["x-risk"] = "high"
        diags = basecompare.approved_protection_diagnostics({"REQ-001": base}, {"REQ-001": current}, "root")
        self.assertEqual(diags, [])

    def test_non_req_kind_is_not_protected(self):
        # 文書・Frontmatter・状態仕様 §8は「approved REQ」だけを保護する（TECHは対象外）。
        base_entry = DocEntry(
            path=".spec/technical/TECH-001.md", kind="TECH", doc_id="TECH-001", title="旧",
            status="approved", frontmatter={"id": "TECH-001", "title": "旧", "status": "approved"},
        )
        current_entry = DocEntry(
            path=".spec/technical/TECH-001.md", kind="TECH", doc_id="TECH-001", title="新",
            status="approved", frontmatter={"id": "TECH-001", "title": "新", "status": "approved"},
        )
        diags = basecompare.approved_protection_diagnostics({"TECH-001": base_entry}, {"TECH-001": current_entry}, "root")
        self.assertEqual(diags, [])

    def test_draft_base_req_is_not_protected(self):
        base = {"REQ-001": _req(title="旧", status="draft")}
        current = {"REQ-001": _req(title="新", status="approved")}
        self.assertEqual(basecompare.approved_protection_diagnostics(base, current, "root"), [])


if __name__ == "__main__":
    unittest.main()
