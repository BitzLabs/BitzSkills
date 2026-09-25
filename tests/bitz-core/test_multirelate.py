"""`bitz.multirelate`（修飾IDの横断解決とrelation Diagnostic）の単体試験。

`02_SPECモデル/04_関係・トレースモデル.md` §5.1（relation Diagnosticの優先順位）、
`02_SPECモデル/05_複合workspace仕様.md` §4・§5.1・§9 を対象にする（Step 5B）。
"""

from __future__ import annotations

import unittest

from bitz import multirelate
from bitz.document import DocEntry


def _entry(doc_id, kind, status, *, path=None, frontmatter=None, statements=None):
    fm = dict(frontmatter or {})
    fm.setdefault("id", doc_id)
    return DocEntry(
        path=path or f".spec/x/{doc_id}.md",
        kind=kind,
        doc_id=doc_id,
        title=doc_id,
        status=status,
        frontmatter=fm,
        statements=statements or [],
        counted=True,
        statement_count=len(statements or []),
    )


class ResolveEdgeTests(unittest.TestCase):
    """関係・トレースモデル §5.1「1つのrelation edgeは次の順に検査し…」の優先順位を確認する。"""

    def setUp(self):
        self.web_tech = _entry("TECH-010", "TECH", "approved")
        self.api_tech = _entry("TECH-010", "TECH", "approved")  # 別workspaceの同一local ID
        self.root_req = _entry(
            "REQ-001", "REQ", "approved",
            statements=[{"id": "REQ-001:AC-01", "documentId": "REQ-001"}],
        )
        self.local_id_indices = {
            "web": {"TECH-010": self.web_tech},
            "api": {"TECH-010": self.api_tech},
            "platform": {"REQ-001": self.root_req},
        }
        self.local_stmt_indices = {
            "web": {},
            "api": {},
            "platform": {"REQ-001:AC-01": {"id": "REQ-001:AC-01", "documentId": "REQ-001"}},
        }
        self.known_ws_ids = {"web", "api", "platform"}

    def test_qualified_ok(self):
        status, entry, qid = multirelate.resolve_edge(
            "platform::REQ-001:AC-01", "web", self.local_id_indices, self.local_stmt_indices, self.known_ws_ids
        )
        self.assertEqual(status, "ok")
        self.assertIs(entry, self.root_req)
        self.assertEqual(qid, "platform::REQ-001")

    def test_unqualified_local_ok(self):
        status, entry, qid = multirelate.resolve_edge(
            "TECH-010", "web", self.local_id_indices, self.local_stmt_indices, self.known_ws_ids
        )
        self.assertEqual(status, "ok")
        self.assertIs(entry, self.web_tech)
        self.assertEqual(qid, "web::TECH-010")

    def test_unqualified_target_only_in_other_workspace(self):
        # sourceがplatformの場合、TECH-010はweb/apiにしかない（横断意図を推測せずMULTI-REF）。
        status, reason, _qid = multirelate.resolve_edge(
            "TECH-010", "platform", self.local_id_indices, self.local_stmt_indices, self.known_ws_ids
        )
        self.assertEqual((status, reason), ("diag", "unqualified-elsewhere"))

    def test_qualified_lexically_invalid_workspace(self):
        status, reason, _qid = multirelate.resolve_edge(
            "NotAWorkspace::REQ-001", "web", self.local_id_indices, self.local_stmt_indices, self.known_ws_ids
        )
        self.assertEqual((status, reason), ("diag", "lexical"))

    def test_qualified_unknown_workspace(self):
        status, reason, _qid = multirelate.resolve_edge(
            "unknownws::REQ-001", "web", self.local_id_indices, self.local_stmt_indices, self.known_ws_ids
        )
        self.assertEqual((status, reason), ("diag", "workspace-unknown"))

    def test_qualified_workspace_exists_target_missing(self):
        status, reason, _qid = multirelate.resolve_edge(
            "api::REQ-999", "web", self.local_id_indices, self.local_stmt_indices, self.known_ws_ids
        )
        self.assertEqual((status, reason), ("diag", "missing"))

    def test_unqualified_missing_everywhere(self):
        status, reason, _qid = multirelate.resolve_edge(
            "TECH-999", "web", self.local_id_indices, self.local_stmt_indices, self.known_ws_ids
        )
        self.assertEqual((status, reason), ("diag", "missing"))


class FieldDiagnosticsPriorityTests(unittest.TestCase):
    """resolve_edgeの理由coを実際のDiagnostic codeへ正しく変換することを確認する。"""

    def setUp(self):
        self.root_req = _entry(
            "REQ-001", "REQ", "approved",
            statements=[{"id": "REQ-001:AC-01", "documentId": "REQ-001"}],
        )
        self.local_id_indices = {"platform": {"REQ-001": self.root_req}, "web": {}}
        self.local_stmt_indices = {
            "platform": {"REQ-001:AC-01": {"id": "REQ-001:AC-01", "documentId": "REQ-001"}},
            "web": {},
        }
        self.known_ws_ids = {"platform", "web"}

    def _diag_for(self, relation_refs):
        entry = _entry(
            "TECH-010", "TECH", "approved",
            frontmatter={"relations": relation_refs},
        )
        diags = multirelate.field_diagnostics(
            entry, "web", self.local_id_indices, self.local_stmt_indices, self.known_ws_ids
        )
        self.assertEqual(len(diags), 1, diags)
        return diags[0]

    def test_unqualified_elsewhere_is_multi_ref(self):
        # "REQ-001"はweb自身には無く、platformにだけある非修飾参照。
        d = self._diag_for({"refines": ["REQ-001"]})
        self.assertEqual(d.code, "SPEC-MULTI-REF-001")

    def test_qualified_workspace_unknown_is_multi_ref(self):
        d = self._diag_for({"refines": ["unknownws::REQ-001"]})
        self.assertEqual(d.code, "SPEC-MULTI-REF-001")

    def test_qualified_missing_target_is_relation_missing(self):
        d = self._diag_for({"requires": ["platform::REQ-999"]})
        self.assertEqual(d.code, "SPEC-RELATION-MISSING-001")

    def test_qualified_kind_mismatch_is_relation_type(self):
        # TECHのrefinesはREQ／TECHしか許可しない。ADRをrefines先に指定するとkind不適合になる。
        adr = _entry("ADR-001", "ADR", "accepted")
        self.local_id_indices["platform"]["ADR-001"] = adr
        d = self._diag_for({"refines": ["platform::ADR-001"]})
        self.assertEqual(d.code, "CTX-RELATION-TYPE-001")

    def test_qualified_resolved_is_no_diagnostic(self):
        entry = _entry(
            "TECH-010", "TECH", "approved",
            frontmatter={"relations": {"refines": ["platform::REQ-001:AC-01"]}},
        )
        diags = multirelate.field_diagnostics(
            entry, "web", self.local_id_indices, self.local_stmt_indices, self.known_ws_ids
        )
        self.assertEqual(diags, [])


class PathOwnershipTests(unittest.TestCase):
    """`_resolve_owned_path`（複合workspace仕様 §5.1）の所有境界判定を確認する。"""

    def test_symlink_outside_ownership_is_violation(self):
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            web = os.path.join(tmp, "web")
            api = os.path.join(tmp, "api")
            os.makedirs(os.path.join(web, "src"))
            os.makedirs(os.path.join(api, "src"))
            with open(os.path.join(api, "src", "session.py"), "w") as f:
                f.write("x")
            os.symlink(os.path.join(api, "src", "session.py"), os.path.join(web, "src", "shared.py"))

            ok, violation = multirelate._resolve_owned_path(web, os.path.realpath(web), "src/shared.py")
            self.assertFalse(ok)
            self.assertTrue(violation)

    def test_symlink_inside_ownership_is_ok(self):
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            web = os.path.join(tmp, "web")
            os.makedirs(os.path.join(web, "src"))
            with open(os.path.join(web, "src", "real.py"), "w") as f:
                f.write("x")
            os.symlink(os.path.join(web, "src", "real.py"), os.path.join(web, "src", "alias.py"))

            ok, violation = multirelate._resolve_owned_path(web, os.path.realpath(web), "src/alias.py")
            self.assertTrue(ok)
            self.assertFalse(violation)

    def test_missing_path_is_neither_ok_nor_violation(self):
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            ok, violation = multirelate._resolve_owned_path(tmp, os.path.realpath(tmp), "no/such/file.py")
            self.assertFalse(ok)
            self.assertFalse(violation)


class CoversAllowedRefsTests(unittest.TestCase):
    """関係・トレースモデル §9「direct refines」の横断covers許可を確認する。"""

    def test_cross_workspace_direct_refines_statement_allowed(self):
        root_req = _entry(
            "REQ-001", "REQ", "approved",
            statements=[{"id": "REQ-001:AC-01", "documentId": "REQ-001"}],
        )
        local_id_indices = {"platform": {"REQ-001": root_req}, "web": {}}
        local_stmt_indices = {
            "platform": {"REQ-001:AC-01": {"id": "REQ-001:AC-01", "documentId": "REQ-001"}},
            "web": {},
        }
        known_ws_ids = {"platform", "web"}
        entry = _entry(
            "TECH-010", "TECH", "approved",
            frontmatter={
                "relations": {"refines": ["platform::REQ-001:AC-01"]},
                "tests": [{"path": "tests/t.py", "covers": ["platform::REQ-001:AC-01"]}],
            },
        )
        allowed_stmt, allowed_doc = multirelate._covers_allowed_refs(
            entry, "web", local_id_indices, local_stmt_indices, known_ws_ids
        )
        self.assertIn("platform::REQ-001:AC-01", allowed_stmt)
        # TECH-010自身は規範文を持たないため、自身のIDも(b)により別途許可される。
        self.assertEqual(allowed_doc, {"TECH-010"})

    def test_non_refines_target_not_allowed(self):
        root_req = _entry(
            "REQ-002", "REQ", "approved",
            statements=[{"id": "REQ-002:AC-01", "documentId": "REQ-002"}],
        )
        local_id_indices = {"platform": {"REQ-002": root_req}, "web": {}}
        local_stmt_indices = {
            "platform": {"REQ-002:AC-01": {"id": "REQ-002:AC-01", "documentId": "REQ-002"}},
            "web": {},
        }
        known_ws_ids = {"platform", "web"}
        entry = _entry("TECH-010", "TECH", "approved", frontmatter={"relations": {}})
        allowed_stmt, _allowed_doc = multirelate._covers_allowed_refs(
            entry, "web", local_id_indices, local_stmt_indices, known_ws_ids
        )
        self.assertNotIn("platform::REQ-002:AC-01", allowed_stmt)


class GlobalCycleDiagnosticsTests(unittest.TestCase):
    """関係・トレースモデル §4「requiresとrefinesを合わせた意味依存graph…の循環を禁止する」。

    複合workspaceでは横断edge（修飾IDで解決したedge）も含めたgraphで循環を検出することを確認する。
    """

    def test_cross_workspace_requires_cycle_is_detected(self):
        # web::TECH-A --requires--> api::TECH-B --requires--> web::TECH-A
        web_a = _entry(
            "TECH-A", "TECH", "approved",
            frontmatter={"relations": {"requires": ["api::TECH-B"]}},
        )
        api_b = _entry(
            "TECH-B", "TECH", "approved",
            frontmatter={"relations": {"requires": ["web::TECH-A"]}},
        )
        entries_by_ws = {"web": [web_a], "api": [api_b]}
        diags = multirelate.global_cycle_diagnostics(entries_by_ws)
        codes = [(d.code, d.source["workspaceId"]) for d in diags]
        self.assertIn(("CTX-CYCLE-001", "web"), codes)
        self.assertIn(("CTX-CYCLE-001", "api"), codes)

    def test_mixed_refines_and_requires_cross_workspace_cycle_is_detected(self):
        # platform::REQ-001 --requires--> web::TECH-010 --refines--> platform::REQ-001
        root_req = _entry(
            "REQ-001", "REQ", "approved",
            frontmatter={"relations": {"requires": ["web::TECH-010"]}},
        )
        web_tech = _entry(
            "TECH-010", "TECH", "approved",
            frontmatter={"relations": {"refines": ["platform::REQ-001"]}},
        )
        entries_by_ws = {"platform": [root_req], "web": [web_tech]}
        diags = multirelate.global_cycle_diagnostics(entries_by_ws)
        codes = {(d.code, d.source["workspaceId"]) for d in diags}
        self.assertIn(("CTX-CYCLE-001", "platform"), codes)
        self.assertIn(("CTX-CYCLE-001", "web"), codes)

    def test_cross_workspace_related_cycle_is_not_detected(self):
        # relatedは循環検査の対象外（関係・トレースモデル §4「related循環は許可し探索しない」）。
        web_a = _entry(
            "TECH-A", "TECH", "approved",
            frontmatter={"relations": {"related": ["api::TECH-B"]}},
        )
        api_b = _entry(
            "TECH-B", "TECH", "approved",
            frontmatter={"relations": {"related": ["web::TECH-A"]}},
        )
        entries_by_ws = {"web": [web_a], "api": [api_b]}
        diags = multirelate.global_cycle_diagnostics(entries_by_ws)
        self.assertEqual(diags, [])

    def test_no_cycle_is_no_diagnostic(self):
        web_a = _entry(
            "TECH-A", "TECH", "approved",
            frontmatter={"relations": {"requires": ["api::TECH-B"]}},
        )
        api_b = _entry("TECH-B", "TECH", "approved")
        entries_by_ws = {"web": [web_a], "api": [api_b]}
        diags = multirelate.global_cycle_diagnostics(entries_by_ws)
        self.assertEqual(diags, [])


if __name__ == "__main__":
    unittest.main()
