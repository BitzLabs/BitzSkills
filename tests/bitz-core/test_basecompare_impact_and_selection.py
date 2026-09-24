"""`check.md §6`（changed対象選択）・§8（影響候補）の単体試験。"""

import unittest

from bitz import basecompare
from bitz.document import DocEntry
from bitz.gitutil import ChangedPath


def _entry(doc_id, kind, status, path, *, relations=None, implements=None, tests=None):
    fm = {"id": doc_id, "title": "t", "status": status}
    if relations is not None:
        fm["relations"] = relations
    if implements is not None:
        fm["implements"] = implements
    if tests is not None:
        fm["tests"] = tests
    return DocEntry(path=path, kind=kind, doc_id=doc_id, title="t", status=status, frontmatter=fm)


class ImpactCandidateTests(unittest.TestCase):
    def test_strong_dependency_on_changed_doc_is_flagged(self):
        current = {
            "TECH-001": _entry("TECH-001", "TECH", "approved", ".spec/technical/TECH-001.md"),
            "TECH-002": _entry(
                "TECH-002", "TECH", "approved", ".spec/technical/TECH-002.md",
                relations={"requires": ["TECH-001"]},
            ),
        }
        diags = basecompare.impact_candidate_diagnostics({"TECH-001"}, current, "root")
        self.assertEqual(len(diags), 1)
        self.assertEqual(diags[0].code, "SPEC-IMPACT-OUTDATED-001")
        self.assertEqual(diags[0].severity, "warning")
        self.assertEqual(diags[0].source["key"], "relations.requires")
        self.assertIn("TECH-002", diags[0].summary)
        self.assertIn("TECH-001", diags[0].summary)

    def test_related_relation_does_not_trigger_impact(self):
        current = {
            "TECH-001": _entry("TECH-001", "TECH", "approved", ".spec/technical/TECH-001.md"),
            "TECH-002": _entry(
                "TECH-002", "TECH", "approved", ".spec/technical/TECH-002.md",
                relations={"related": ["TECH-001"]},
            ),
        }
        self.assertEqual(basecompare.impact_candidate_diagnostics({"TECH-001"}, current, "root"), [])

    def test_draft_dependent_is_not_flagged(self):
        current = {
            "TECH-001": _entry("TECH-001", "TECH", "approved", ".spec/technical/TECH-001.md"),
            "TECH-002": _entry(
                "TECH-002", "TECH", "draft", ".spec/technical/TECH-002.md",
                relations={"requires": ["TECH-001"]},
            ),
        }
        self.assertEqual(basecompare.impact_candidate_diagnostics({"TECH-001"}, current, "root"), [])

    def test_changed_spec_document_ids_ignores_code_and_test_paths(self):
        # §8「related、code、testを起点にしない」。code/test pathが変更されても
        # 影響候補の起点（`changed_spec_document_ids`）には入らない。
        current_by_path = {
            ".spec/technical/TECH-001.md": _entry(
                "TECH-001", "TECH", "approved", ".spec/technical/TECH-001.md", implements=["src/a.py"]
            ),
        }
        changed = [ChangedPath(status="M", path="src/a.py")]
        ids = basecompare.changed_spec_document_ids(changed, current_by_path, {})
        self.assertEqual(ids, set())

    def test_changed_spec_document_ids_includes_direct_spec_path_change(self):
        current_by_path = {
            ".spec/technical/TECH-001.md": _entry("TECH-001", "TECH", "approved", ".spec/technical/TECH-001.md"),
        }
        changed = [ChangedPath(status="M", path=".spec/technical/TECH-001.md")]
        ids = basecompare.changed_spec_document_ids(changed, current_by_path, {})
        self.assertEqual(ids, {"TECH-001"})


class ChangedSelectionTests(unittest.TestCase):
    def test_code_path_maps_to_implements_owner(self):
        current_by_id = {
            "REQ-001": _entry("REQ-001", "REQ", "approved", ".spec/requirements/REQ-001.md", implements=["src/a.py"]),
        }
        implements_index = basecompare.build_reverse_index(current_by_id, "implements")
        tests_index = basecompare.build_reverse_index(current_by_id, "tests")
        changed = [ChangedPath(status="M", path="src/a.py")]
        owning, count, excluded = basecompare.changed_selection(changed, {}, {}, implements_index, tests_index)
        self.assertEqual(owning, {"REQ-001"})
        self.assertEqual(count, 1)
        self.assertEqual(excluded, 0)

    def test_test_path_maps_to_tests_owner(self):
        current_by_id = {
            "REQ-001": _entry(
                "REQ-001", "REQ", "approved", ".spec/requirements/REQ-001.md",
                tests=[{"path": "tests/test_a.py", "covers": ["REQ-001:AC-01"], "command": "default"}],
            ),
        }
        tests_index = basecompare.build_reverse_index(current_by_id, "tests")
        implements_index = basecompare.build_reverse_index(current_by_id, "implements")
        changed = [ChangedPath(status="M", path="tests/test_a.py")]
        owning, _count, excluded = basecompare.changed_selection(changed, {}, {}, implements_index, tests_index)
        self.assertEqual(owning, {"REQ-001"})
        self.assertEqual(excluded, 0)

    def test_rejected_req_is_excluded_from_reverse_index(self):
        current_by_id = {
            "REQ-001": _entry(
                "REQ-001", "REQ", "rejected", ".spec/requirements/REQ-001.md", implements=["src/a.py"]
            ),
        }
        implements_index = basecompare.build_reverse_index(current_by_id, "implements")
        self.assertEqual(implements_index, {})

    def test_unowned_code_path_is_only_counted(self):
        changed = [ChangedPath(status="M", path="src/unowned.py")]
        owning, count, excluded = basecompare.changed_selection(changed, {}, {}, {}, {})
        self.assertEqual(owning, set())
        self.assertEqual(count, 1)
        self.assertEqual(excluded, 1)

    def test_spec_path_maps_to_frontmatter_id(self):
        current_by_path = {
            ".spec/tasks/TASK-001.md": _entry("TASK-001", "TASK", "open", ".spec/tasks/TASK-001.md"),
        }
        changed = [ChangedPath(status="M", path=".spec/tasks/TASK-001.md")]
        owning, count, excluded = basecompare.changed_selection(changed, current_by_path, {}, {}, {})
        self.assertEqual(owning, {"TASK-001"})
        self.assertEqual(count, 1)
        self.assertEqual(excluded, 0)


if __name__ == "__main__":
    unittest.main()
