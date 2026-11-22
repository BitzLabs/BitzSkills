"""`basecompare.approved_protection_diagnostics`の単体試験（文書・フロントマター・状態仕様 §8、§8.2）。

保護の対象は、基準版で`approved`のREQとTECH（ADR-072の決定1）。途中のコミットの判定（§8.1）は、ここでは``history``の差し替えで扱い、
実際のGitの履歴は`test_approved_history.py`が確かめる。

`title`、EARS-AI規範文の意味フィールド、強い関係の変更は保護対象、`implements`・`tests`・`verify`・
`related`・`x-`拡張・説明文だけの変更は対象外であることを検査する。
"""

import unittest

from bitz import approvedhistory, basecompare
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

    def test_tech_meaning_change_is_protected(self):
        # 文書・フロントマター・状態仕様 §8は、基準版で状態`approved`のREQとTECHを保護する（ADR-072の決定1）。
        base_entry = DocEntry(
            path=".spec/technical/TECH-001.md", kind="TECH", doc_id="TECH-001", title="旧",
            status="approved", frontmatter={"id": "TECH-001", "title": "旧", "status": "approved"},
        )
        current_entry = DocEntry(
            path=".spec/technical/TECH-001.md", kind="TECH", doc_id="TECH-001", title="新",
            status="approved", frontmatter={"id": "TECH-001", "title": "新", "status": "approved"},
        )
        diags = basecompare.approved_protection_diagnostics({"TECH-001": base_entry}, {"TECH-001": current_entry}, "root")
        self.assertEqual(len(diags), 1)
        self.assertEqual(diags[0].summary, "状態approvedのTECHの意味変更時に文書の状態が戻されていません")
        self.assertEqual(diags[0].source, {"kind": "file", "workspaceId": "root", "path": ".spec/technical/TECH-001.md", "key": "title"})
        self.assertIsNone(diags[0].evidence)

    def test_req_summary_names_the_kind(self):
        diags = basecompare.approved_protection_diagnostics(
            {"REQ-001": _req(title="旧title")}, {"REQ-001": _req(title="新title")}, "root"
        )
        self.assertEqual(diags[0].summary, "状態approvedのREQの意味変更時に文書の状態が戻されていません")
        self.assertIsNone(diags[0].evidence)

    def test_adr_kind_is_not_protected(self):
        # `accepted`のADRの本文は保護の対象にしない（§8）。ADRは`approved`の状態を持たない。
        base_entry = DocEntry(
            path=".spec/decisions/ADR-001.md", kind="ADR", doc_id="ADR-001", title="旧",
            status="accepted", frontmatter={"id": "ADR-001", "title": "旧", "status": "accepted"},
        )
        current_entry = DocEntry(
            path=".spec/decisions/ADR-001.md", kind="ADR", doc_id="ADR-001", title="新",
            status="accepted", frontmatter={"id": "ADR-001", "title": "新", "status": "accepted"},
        )
        diags = basecompare.approved_protection_diagnostics({"ADR-001": base_entry}, {"ADR-001": current_entry}, "root")
        self.assertEqual(diags, [])

    def test_one_diagnostic_per_document_with_the_first_changed_key(self):
        # §8.2: 1文書に1件。`source.key`は`title`、`relations.<型>`（requires、refines、addresses、supersedes）、`statements`の順の最初。
        changed_stmt = dict(_STMT, modality="SHOULD")
        cases = [
            (
                {"title": "旧", "relations": {"supersedes": ["REQ-009"]}, "statements": [_STMT]},
                {"title": "新", "relations": {"supersedes": ["REQ-008"]}, "statements": [changed_stmt]},
                "title",
            ),
            (
                {"relations": {"requires": ["TECH-001"], "refines": ["REQ-002"]}},
                {"relations": {"requires": ["TECH-002"], "refines": ["REQ-003"]}},
                "relations.requires",
            ),
            (
                {"relations": {"refines": ["REQ-002"], "addresses": ["REQ-004"]}, "statements": [_STMT]},
                {"relations": {"refines": ["REQ-003"], "addresses": ["REQ-005"]}, "statements": [changed_stmt]},
                "relations.refines",
            ),
            (
                {"relations": {"addresses": ["REQ-004"], "supersedes": ["REQ-009"]}},
                {"relations": {"addresses": ["REQ-005"], "supersedes": ["REQ-008"]}},
                "relations.addresses",
            ),
            (
                {"relations": {"supersedes": ["REQ-009"]}, "statements": [_STMT]},
                {"relations": {"supersedes": ["REQ-008"]}, "statements": [changed_stmt]},
                "relations.supersedes",
            ),
            ({"statements": [_STMT]}, {"statements": []}, "statements"),
            ({"statements": [_STMT]}, {"statements": [dict(_STMT, id="REQ-001:AC-02")]}, "statements"),
        ]
        for base_kwargs, current_kwargs, key in cases:
            with self.subTest(key=key, current=current_kwargs):
                diags = basecompare.approved_protection_diagnostics(
                    {"REQ-001": _req(**base_kwargs)}, {"REQ-001": _req(**current_kwargs)}, "root"
                )
                self.assertEqual([d.source.get("key") for d in diags], [key])

    def test_history_is_called_only_with_candidates(self):
        calls = []

        def history(ids):
            calls.append(set(ids))
            return approvedhistory.Verdict(incomplete=False, recognized=frozenset())

        unchanged = basecompare.approved_protection_diagnostics(
            {"REQ-001": _req()}, {"REQ-001": _req()}, "root", history=history
        )
        self.assertEqual(unchanged, [])
        self.assertEqual(calls, [])
        basecompare.approved_protection_diagnostics(
            {"REQ-001": _req(title="旧")}, {"REQ-001": _req(title="新")}, "root", history=history
        )
        self.assertEqual(calls, [{"REQ-001"}])

    def test_recognized_intermediate_state_removes_the_violation(self):
        def history(ids):
            return approvedhistory.Verdict(incomplete=False, recognized=frozenset({"REQ-001"}))

        diags = basecompare.approved_protection_diagnostics(
            {"REQ-001": _req(title="旧")}, {"REQ-001": _req(title="新")}, "root", history=history
        )
        self.assertEqual(diags, [])

    def test_incomplete_history_keeps_the_violation_with_history_wording(self):
        def history(ids):
            return approvedhistory.INCOMPLETE

        diags = basecompare.approved_protection_diagnostics(
            {"REQ-001": _req(title="旧")}, {"REQ-001": _req(title="新")}, "root", history=history
        )
        self.assertEqual(len(diags), 1)
        self.assertEqual(
            diags[0].summary, "状態approvedのREQの意味変更時に文書の状態が戻されていません（途中のコミットを完全には読めません）"
        )
        self.assertEqual(diags[0].source["key"], "title")

    def test_protection_setting(self):
        self.assertTrue(basecompare.protection_enabled(None))
        self.assertTrue(basecompare.protection_enabled({}))
        self.assertTrue(basecompare.protection_enabled({"safety": {}}))
        self.assertTrue(basecompare.protection_enabled({"safety": {"protectApprovedRequirements": True}}))
        self.assertFalse(basecompare.protection_enabled({"safety": {"protectApprovedRequirements": False}}))

    def test_draft_base_req_is_not_protected(self):
        base = {"REQ-001": _req(title="旧", status="draft")}
        current = {"REQ-001": _req(title="新", status="approved")}
        self.assertEqual(basecompare.approved_protection_diagnostics(base, current, "root"), [])


if __name__ == "__main__":
    unittest.main()
