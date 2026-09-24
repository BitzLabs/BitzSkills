"""relation・path・coverage検査（`relations.py`）の単体試験（Step 2 Phase C）。

`04_関係・トレースモデル.md` §3〜§5・§9、`02_文書・Frontmatter・状態仕様.md` §5・§6・§7、
`Diagnostic registry` §4 の規則を検査する。
"""

import os
import tempfile
import unittest

from bitz import document as doc_mod
from bitz import relations as rel_mod

WORKSPACE_ID = "root"


def _write(root: str, rel_path: str, content: str) -> None:
    full = os.path.join(root, rel_path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(content)


def _bitz_yaml() -> str:
    return 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\n'


def _req(doc_id: str, status: str = "approved", extra_frontmatter: str = "", statement: bool = True) -> str:
    ac = (
        f"- [{doc_id}:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 秘密情報を出力しない。\n"
        if statement
        else "statementなし。\n"
    )
    return f"""---
id: {doc_id}
title: 検査対象
status: {status}
{extra_frontmatter}---

# {doc_id} 検査対象

## Intent

意図。

## Acceptance Criteria

{ac}
## Verification

未証明。
"""


def _tech(doc_id: str, status: str = "approved", extra_frontmatter: str = "") -> str:
    return f"""---
id: {doc_id}
title: 技術契約
status: {status}
{extra_frontmatter}---

# {doc_id} 技術契約

## Context

規範文を持たない。
"""


def _adr(doc_id: str, status: str = "accepted", extra_frontmatter: str = "") -> str:
    return f"""---
id: {doc_id}
title: 判断
status: {status}
{extra_frontmatter}---

# {doc_id} 判断

## Context

背景。

## Decision

決定。

## Consequences

帰結。
"""


def _task(doc_id: str, status: str = "open", extra_frontmatter: str = "") -> str:
    return f"""---
id: {doc_id}
title: 作業
status: {status}
{extra_frontmatter}---

# {doc_id} 作業

## Objective

目的。

## Completion Criteria

完了条件。
"""


def _build(root: str):
    return doc_mod.build_catalog(root, WORKSPACE_ID)


class RelationTypeTableTests(unittest.TestCase):
    """関係・トレースモデル §4の型制約表を網羅する。"""

    def _assert_allowed(self, source_content_by_kind_dir, expect_type_error: bool):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            for path, content in source_content_by_kind_dir.items():
                _write(root, path, content)
            catalog = _build(root)
            diags = rel_mod.check_relations(catalog.entries, WORKSPACE_ID)
            codes = [d.code for d in diags]
            if expect_type_error:
                self.assertIn("CTX-RELATION-TYPE-001", codes)
            else:
                self.assertNotIn("CTX-RELATION-TYPE-001", codes)
                self.assertNotIn("SPEC-RELATION-MISSING-001", codes)

    def test_req_requires_req_tech_adr_ok(self):
        self._assert_allowed(
            {
                ".spec/requirements/REQ-001.md": _req(
                    "REQ-001", extra_frontmatter="relations:\n  requires: [REQ-002, TECH-001, ADR-001]\n"
                ),
                ".spec/requirements/REQ-002.md": _req("REQ-002"),
                ".spec/technical/TECH-001.md": _tech("TECH-001"),
                ".spec/decisions/ADR-001.md": _adr("ADR-001"),
            },
            expect_type_error=False,
        )

    def test_req_requires_task_is_type_error(self):
        self._assert_allowed(
            {
                ".spec/requirements/REQ-001.md": _req(
                    "REQ-001", extra_frontmatter="relations:\n  requires: [TASK-001]\n"
                ),
                ".spec/tasks/TASK-001.md": _task("TASK-001"),
            },
            expect_type_error=True,
        )

    def test_req_refines_tech_is_type_error(self):
        self._assert_allowed(
            {
                ".spec/requirements/REQ-001.md": _req(
                    "REQ-001", extra_frontmatter="relations:\n  refines: [TECH-001]\n"
                ),
                ".spec/technical/TECH-001.md": _tech("TECH-001"),
            },
            expect_type_error=True,
        )

    def test_req_supersedes_req_ok_tech_type_error(self):
        self._assert_allowed(
            {
                ".spec/requirements/REQ-001.md": _req(
                    "REQ-001", extra_frontmatter="relations:\n  supersedes: [REQ-002]\n"
                ),
                ".spec/requirements/REQ-002.md": _req("REQ-002"),
            },
            expect_type_error=False,
        )

    def test_tech_refines_req_or_tech_ok(self):
        self._assert_allowed(
            {
                ".spec/technical/TECH-001.md": _tech(
                    "TECH-001", extra_frontmatter="relations:\n  refines: [REQ-001]\n"
                ),
                ".spec/requirements/REQ-001.md": _req("REQ-001"),
            },
            expect_type_error=False,
        )

    def test_tech_supersedes_req_is_type_error(self):
        self._assert_allowed(
            {
                ".spec/technical/TECH-001.md": _tech(
                    "TECH-001", extra_frontmatter="relations:\n  supersedes: [REQ-001]\n"
                ),
                ".spec/requirements/REQ-001.md": _req("REQ-001"),
            },
            expect_type_error=True,
        )

    def test_adr_requires_req_tech_adr_ok(self):
        self._assert_allowed(
            {
                ".spec/decisions/ADR-001.md": _adr(
                    "ADR-001", extra_frontmatter="relations:\n  requires: [REQ-001]\n"
                ),
                ".spec/requirements/REQ-001.md": _req("REQ-001"),
            },
            expect_type_error=False,
        )

    def test_adr_supersedes_adr_ok_req_type_error(self):
        self._assert_allowed(
            {
                ".spec/decisions/ADR-001.md": _adr(
                    "ADR-001", extra_frontmatter="relations:\n  supersedes: [REQ-001]\n"
                ),
                ".spec/requirements/REQ-001.md": _req("REQ-001"),
            },
            expect_type_error=True,
        )

    def test_task_requires_req_tech_task_adr_ok(self):
        self._assert_allowed(
            {
                ".spec/tasks/TASK-001.md": _task(
                    "TASK-001",
                    extra_frontmatter="relations:\n  requires: [REQ-001, TECH-001, TASK-002, ADR-001]\n",
                ),
                ".spec/requirements/REQ-001.md": _req("REQ-001"),
                ".spec/technical/TECH-001.md": _tech("TECH-001"),
                ".spec/tasks/TASK-002.md": _task("TASK-002"),
                ".spec/decisions/ADR-001.md": _adr("ADR-001"),
            },
            expect_type_error=False,
        )

    def test_task_addresses_req_statement_ok(self):
        self._assert_allowed(
            {
                ".spec/tasks/TASK-001.md": _task(
                    "TASK-001", extra_frontmatter="relations:\n  addresses: [REQ-001:AC-01]\n"
                ),
                ".spec/requirements/REQ-001.md": _req("REQ-001"),
            },
            expect_type_error=False,
        )

    def test_task_addresses_normed_req_by_bare_doc_id_is_type_error(self):
        # 規範文を持つREQを文書IDだけで指定してはならない（本文template §5）。
        self._assert_allowed(
            {
                ".spec/tasks/TASK-001.md": _task(
                    "TASK-001", extra_frontmatter="relations:\n  addresses: [REQ-001]\n"
                ),
                ".spec/requirements/REQ-001.md": _req("REQ-001"),
            },
            expect_type_error=True,
        )

    def test_task_addresses_statementless_tech_by_bare_doc_id_ok(self):
        self._assert_allowed(
            {
                ".spec/tasks/TASK-001.md": _task(
                    "TASK-001", extra_frontmatter="relations:\n  addresses: [TECH-001]\n"
                ),
                ".spec/technical/TECH-001.md": _tech("TECH-001"),
            },
            expect_type_error=False,
        )

    def test_requires_non_accepted_adr_is_type_error(self):
        self._assert_allowed(
            {
                ".spec/requirements/REQ-001.md": _req(
                    "REQ-001", extra_frontmatter="relations:\n  requires: [ADR-001]\n"
                ),
                ".spec/decisions/ADR-001.md": _adr("ADR-001", status="proposed"),
            },
            expect_type_error=True,
        )

    def test_requires_accepted_adr_ok(self):
        self._assert_allowed(
            {
                ".spec/requirements/REQ-001.md": _req(
                    "REQ-001", extra_frontmatter="relations:\n  requires: [ADR-001]\n"
                ),
                ".spec/decisions/ADR-001.md": _adr("ADR-001", status="accepted"),
            },
            expect_type_error=False,
        )

    def test_related_allows_any_kind(self):
        self._assert_allowed(
            {
                ".spec/requirements/REQ-001.md": _req(
                    "REQ-001", extra_frontmatter="relations:\n  related: [TASK-001]\n"
                ),
                ".spec/tasks/TASK-001.md": _task("TASK-001"),
            },
            expect_type_error=False,
        )


class MissingTargetTests(unittest.TestCase):
    def test_strong_missing_is_failed(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            _write(
                root,
                ".spec/requirements/REQ-001.md",
                _req("REQ-001", extra_frontmatter="relations:\n  requires: [REQ-999]\n"),
            )
            catalog = _build(root)
            diags = rel_mod.check_relations(catalog.entries, WORKSPACE_ID)
            self.assertEqual([d.code for d in diags], ["SPEC-RELATION-MISSING-001"])
            self.assertEqual(diags[0].severity, "error")
            self.assertEqual(diags[0].resultStatus, "failed")

    def test_related_missing_is_advisory_warning(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            _write(
                root,
                ".spec/requirements/REQ-001.md",
                _req("REQ-001", extra_frontmatter="relations:\n  related: [REQ-999]\n"),
            )
            catalog = _build(root)
            diags = rel_mod.check_relations(catalog.entries, WORKSPACE_ID)
            self.assertEqual([d.code for d in diags], ["SPEC-RELATION-ADVISORY-MISSING-001"])
            self.assertEqual(diags[0].resultStatus, "passed_with_warnings")

    def test_legacy_refs_is_failed_skip_edge(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001", extra_frontmatter="refs: [REQ-002]\n"))
            _write(root, ".spec/requirements/REQ-002.md", _req("REQ-002"))
            catalog = _build(root)
            diags = rel_mod.check_relations(catalog.entries, WORKSPACE_ID)
            self.assertEqual([d.code for d in diags], ["SPEC-RELATION-LEGACY-001"])
            # skip-edge: 文書自体は完全検査済み（skip-documentではない）。
            self.assertEqual(catalog.checked_document_count, 2)


class PerEdgePrimaryTests(unittest.TestCase):
    """関係・トレースモデル §5.1: 独立したraw原因（＝別edge）はそれぞれprimaryを持つ。"""

    def test_multiple_missing_targets_in_one_field_each_get_a_diagnostic(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            _write(
                root,
                ".spec/requirements/REQ-001.md",
                _req("REQ-001", extra_frontmatter="relations:\n  requires: [REQ-998, REQ-999]\n"),
            )
            catalog = _build(root)
            diags = rel_mod.check_relations(catalog.entries, WORKSPACE_ID)
            self.assertEqual(len(diags), 2)
            for d in diags:
                self.assertEqual(d.code, "SPEC-RELATION-MISSING-001")
                self.assertEqual(d.source["key"], "relations.requires")

    def test_missing_and_type_mismatch_both_reported_independently(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            _write(
                root,
                ".spec/requirements/REQ-001.md",
                _req(
                    "REQ-001",
                    extra_frontmatter="relations:\n  refines: [REQ-999, TECH-001]\n",
                ),
            )
            _write(root, ".spec/technical/TECH-001.md", _tech("TECH-001"))
            catalog = _build(root)
            diags = rel_mod.check_relations(catalog.entries, WORKSPACE_ID)
            codes = sorted(d.code for d in diags)
            self.assertEqual(codes, ["CTX-RELATION-TYPE-001", "SPEC-RELATION-MISSING-001"])


class CoverageRefinesTests(unittest.TestCase):
    def test_covers_via_refined_document_statement_form(self):
        # refines先をstatement ID形式で直接指定した場合、そのstatementだけがcover可能。
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            fm = "tests:\n  - path: tests/test_x.py\n    covers: [REQ-001:AC-01]\nrelations:\n  refines: [REQ-001:AC-01]\n"
            _write(root, ".spec/technical/TECH-001.md", _tech("TECH-001", extra_frontmatter=fm))
            _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
            catalog = _build(root)
            diags = rel_mod.check_coverage(catalog.entries, WORKSPACE_ID)
            self.assertEqual(diags, [])

    def test_covers_not_directly_refined_document_is_invalid(self):
        # REQ-002はTECH-001がrefinesしていないため、そのstatementをcoverしてはならない。
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            fm = "tests:\n  - path: tests/test_x.py\n    covers: [REQ-002:AC-01]\n"
            _write(root, ".spec/technical/TECH-001.md", _tech("TECH-001", extra_frontmatter=fm))
            _write(root, ".spec/requirements/REQ-002.md", _req("REQ-002"))
            catalog = _build(root)
            diags = rel_mod.check_coverage(catalog.entries, WORKSPACE_ID)
            self.assertEqual([d.code for d in diags], ["SPEC-TEST-COVERAGE-001"])


class CycleTests(unittest.TestCase):
    def test_requires_self_cycle(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            _write(
                root,
                ".spec/technical/TECH-001.md",
                _tech("TECH-001", extra_frontmatter="relations:\n  requires: [TECH-001]\n"),
            )
            catalog = _build(root)
            diags = rel_mod.check_relations(catalog.entries, WORKSPACE_ID)
            self.assertEqual([d.code for d in diags], ["CTX-CYCLE-001"])

    def test_long_cycle_across_requires_and_refines(self):
        # TECH-001 --requires--> TECH-002 --refines--> REQ-001 --requires--> TECH-001 という
        # 3文書混在の長い循環（requiresとrefinesを合わせた意味依存graph全体で検出する）。
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            _write(
                root,
                ".spec/technical/TECH-001.md",
                _tech("TECH-001", extra_frontmatter="relations:\n  requires: [TECH-002]\n"),
            )
            _write(
                root,
                ".spec/technical/TECH-002.md",
                _tech("TECH-002", extra_frontmatter="relations:\n  refines: [REQ-001]\n"),
            )
            _write(
                root,
                ".spec/requirements/REQ-001.md",
                _req("REQ-001", extra_frontmatter="relations:\n  requires: [TECH-001]\n"),
            )
            catalog = _build(root)
            diags = rel_mod.check_relations(catalog.entries, WORKSPACE_ID)
            codes_by_path = sorted((d.source["path"], d.code) for d in diags if d.code == "CTX-CYCLE-001")
            self.assertEqual(
                codes_by_path,
                [
                    (".spec/requirements/REQ-001.md", "CTX-CYCLE-001"),
                    (".spec/technical/TECH-001.md", "CTX-CYCLE-001"),
                    (".spec/technical/TECH-002.md", "CTX-CYCLE-001"),
                ],
            )

    def test_related_self_cycle_is_not_detected(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            _write(
                root,
                ".spec/technical/TECH-001.md",
                _tech("TECH-001", extra_frontmatter="relations:\n  related: [TECH-001]\n"),
            )
            catalog = _build(root)
            diags = rel_mod.check_relations(catalog.entries, WORKSPACE_ID)
            self.assertEqual(diags, [])

    def test_supersedes_chain_cycle(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            _write(
                root,
                ".spec/requirements/REQ-001.md",
                _req("REQ-001", extra_frontmatter="relations:\n  supersedes: [REQ-002]\n"),
            )
            _write(
                root,
                ".spec/requirements/REQ-002.md",
                _req("REQ-002", extra_frontmatter="relations:\n  supersedes: [REQ-001]\n"),
            )
            catalog = _build(root)
            diags = rel_mod.check_relations(catalog.entries, WORKSPACE_ID)
            cyclic = [d for d in diags if d.code == "CTX-CYCLE-001"]
            self.assertEqual(len(cyclic), 2)
            for d in cyclic:
                self.assertEqual(d.source["key"], "relations.supersedes")

    def test_task_requires_cycle(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            _write(
                root,
                ".spec/tasks/TASK-001.md",
                _task("TASK-001", extra_frontmatter="relations:\n  requires: [TASK-002]\n"),
            )
            _write(
                root,
                ".spec/tasks/TASK-002.md",
                _task("TASK-002", extra_frontmatter="relations:\n  requires: [TASK-001]\n"),
            )
            catalog = _build(root)
            diags = rel_mod.check_relations(catalog.entries, WORKSPACE_ID)
            cyclic = [d for d in diags if d.code == "CTX-CYCLE-001"]
            self.assertEqual(len(cyclic), 2)


class PathTests(unittest.TestCase):
    def test_approved_missing_path_is_error(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            _write(
                root,
                ".spec/requirements/REQ-001.md",
                _req("REQ-001", extra_frontmatter="implements: [src/missing.py]\n"),
            )
            catalog = _build(root)
            diags = rel_mod.check_paths(catalog.entries, root, WORKSPACE_ID)
            self.assertEqual(len(diags), 1)
            self.assertEqual(diags[0].severity, "error")
            self.assertEqual(diags[0].resultStatus, "failed")

    def test_draft_missing_path_is_warning(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            _write(
                root,
                ".spec/requirements/REQ-001.md",
                _req("REQ-001", status="draft", extra_frontmatter="implements: [src/missing.py]\n"),
            )
            catalog = _build(root)
            diags = rel_mod.check_paths(catalog.entries, root, WORKSPACE_ID)
            self.assertEqual(len(diags), 1)
            self.assertEqual(diags[0].severity, "warning")
            self.assertEqual(diags[0].resultStatus, "passed_with_warnings")

    def test_rejected_missing_path_is_skipped(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            _write(
                root,
                ".spec/requirements/REQ-001.md",
                _req("REQ-001", status="rejected", extra_frontmatter="implements: [src/missing.py]\n", statement=False),
            )
            catalog = _build(root)
            diags = rel_mod.check_paths(catalog.entries, root, WORKSPACE_ID)
            self.assertEqual(diags, [])

    def test_existing_path_is_ok(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            _write(root, "src/present.py", "x = 1\n")
            _write(
                root,
                ".spec/requirements/REQ-001.md",
                _req("REQ-001", extra_frontmatter="implements: [src/present.py]\n"),
            )
            catalog = _build(root)
            diags = rel_mod.check_paths(catalog.entries, root, WORKSPACE_ID)
            self.assertEqual(diags, [])


class CoverageTests(unittest.TestCase):
    def test_covers_missing_statement_is_error(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            fm = "tests:\n  - path: tests/test_x.py\n    covers: [REQ-001:AC-99]\n"
            _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001", extra_frontmatter=fm))
            _write(root, "tests/test_x.py", "pass\n")
            catalog = _build(root)
            diags = rel_mod.check_coverage(catalog.entries, WORKSPACE_ID)
            self.assertEqual([d.code for d in diags], ["SPEC-TEST-COVERAGE-001"])
            self.assertEqual(diags[0].source["key"], "tests[0].covers")

    def test_covers_existing_statement_is_ok(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            fm = "tests:\n  - path: tests/test_x.py\n    covers: [REQ-001:AC-01]\n"
            _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001", extra_frontmatter=fm))
            catalog = _build(root)
            diags = rel_mod.check_coverage(catalog.entries, WORKSPACE_ID)
            self.assertEqual(diags, [])

    def test_statementless_tech_covers_own_document_id(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            fm = "tests:\n  - path: tests/test_x.py\n    covers: [TECH-001]\n"
            _write(root, ".spec/technical/TECH-001.md", _tech("TECH-001", extra_frontmatter=fm))
            catalog = _build(root)
            diags = rel_mod.check_coverage(catalog.entries, WORKSPACE_ID)
            self.assertEqual(diags, [])


if __name__ == "__main__":
    unittest.main()
