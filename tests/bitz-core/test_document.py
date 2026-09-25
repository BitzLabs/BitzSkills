"""文書catalog構築（`document.py`）の単体試験。

file名規則、H1／REQ必須section／規範文配置、draftのseverity写像（EARS-AI hard条件の
継続units）、`checkedDocumentCount`／`checkedStatementCount`の列挙を検査する。
relation解決・path存在・covers解決はPhase C（次段）のため対象外。
"""

import os
import tempfile
import unittest

from bitz import document as doc_mod

WORKSPACE_ID = "root"


def _write(root: str, rel_path: str, content: str) -> None:
    full = os.path.join(root, rel_path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(content)


REQ_OK = """---
id: REQ-001
title: 検査対象
status: approved
---

# REQ-001 検査対象

## Intent

意図。

## Acceptance Criteria

- [REQ-001:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 秘密情報を出力しない。

## Verification

未証明。
"""


class FileNameTests(unittest.TestCase):
    def test_mismatched_file_name_is_skip_document(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", "schemaVersion: \"1.0\"\nearsAi: \"1.0\"\n")
            _write(root, ".spec/requirements/REQ-002.md", REQ_OK.replace("REQ-001", "REQ-001"))
            catalog = doc_mod.build_catalog(root, WORKSPACE_ID)
            codes = [d.code for d in catalog.diagnostics]
            self.assertIn("SPEC-FILE-NAME-001", codes)
            self.assertEqual(catalog.checked_document_count, 0)

    def test_slug_suffix_is_accepted(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", "schemaVersion: \"1.0\"\nearsAi: \"1.0\"\n")
            _write(root, ".spec/requirements/REQ-001-login.md", REQ_OK)
            catalog = doc_mod.build_catalog(root, WORKSPACE_ID)
            self.assertEqual(catalog.diagnostics, [])
            self.assertEqual(catalog.checked_document_count, 1)


class H1Tests(unittest.TestCase):
    def test_h1_mismatch(self):
        text = REQ_OK.replace("# REQ-001 検査対象", "# REQ-001 異なる見出し", 1)
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", "schemaVersion: \"1.0\"\nearsAi: \"1.0\"\n")
            _write(root, ".spec/requirements/REQ-001.md", text)
            catalog = doc_mod.build_catalog(root, WORKSPACE_ID)
            codes = [d.code for d in catalog.diagnostics]
            self.assertIn("SPEC-STYLE-H1-001", codes)
            # continueなのでdocumentは引き続き数えられる。
            self.assertEqual(catalog.checked_document_count, 1)


class SectionTests(unittest.TestCase):
    def test_missing_required_section(self):
        text = REQ_OK.replace("## Verification\n\n未証明。\n", "")
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", "schemaVersion: \"1.0\"\nearsAi: \"1.0\"\n")
            _write(root, ".spec/requirements/REQ-001.md", text)
            catalog = doc_mod.build_catalog(root, WORKSPACE_ID)
            section_diags = [d for d in catalog.diagnostics if d.code == "SPEC-STYLE-SECTION-001"]
            self.assertEqual(len(section_diags), 1)
            self.assertIn("Verification", section_diags[0].summary)
            self.assertEqual(catalog.checked_document_count, 1)


class PlacementTests(unittest.TestCase):
    def test_statement_outside_allowed_section_is_excluded_from_count(self):
        text = REQ_OK.replace(
            "## Intent\n\n意図。\n",
            "## Intent\n\n- [REQ-001:AC-02] [ACTOR:TargetSystem] [ALWAYS] [MUST] [THEN] 誤配置。\n\n",
        )
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", "schemaVersion: \"1.0\"\nearsAi: \"1.0\"\n")
            _write(root, ".spec/requirements/REQ-001.md", text)
            catalog = doc_mod.build_catalog(root, WORKSPACE_ID)
            placement = [d for d in catalog.diagnostics if d.code == "SPEC-STYLE-PLACEMENT-001"]
            self.assertEqual(len(placement), 1)
            # 誤配置statementを除いた1件だけが数えられる（doc自体はcontinueで数える）。
            self.assertEqual(catalog.checked_document_count, 1)
            self.assertEqual(catalog.checked_statement_count, 1)

    def test_adr_statement_is_always_misplaced(self):
        text = """---
id: ADR-001
title: 判断
status: accepted
---

# ADR-001 判断

## Context

背景。

## Decision

- [ADR-001:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 秘密情報を出力しない。

## Consequences

規範契約はREQへ置く。
"""
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", "schemaVersion: \"1.0\"\nearsAi: \"1.0\"\n")
            _write(root, ".spec/decisions/ADR-001.md", text)
            catalog = doc_mod.build_catalog(root, WORKSPACE_ID)
            placement = [d for d in catalog.diagnostics if d.code == "SPEC-STYLE-PLACEMENT-001"]
            self.assertEqual(len(placement), 1)
            self.assertEqual(catalog.checked_statement_count, 0)
            self.assertEqual(catalog.checked_document_count, 1)


class DraftSeverityTests(unittest.TestCase):
    def test_draft_tag_order_is_warning_and_keeps_document(self):
        text = REQ_OK.replace("status: approved", "status: draft").replace(
            "[REQ-001:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 秘密情報を出力しない。",
            "[REQ-001:AC-01] [ALWAYS] [ACTOR:TargetSystem] [MUST] [CONSTRAINT] 秘密情報を出力しない。",
        )
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", "schemaVersion: \"1.0\"\nearsAi: \"1.0\"\n")
            _write(root, ".spec/requirements/REQ-001.md", text)
            catalog = doc_mod.build_catalog(root, WORKSPACE_ID)
            tag_order = [d for d in catalog.diagnostics if d.code == "EAI-CORE-SYNTAX-001"]
            self.assertEqual(len(tag_order), 1)
            self.assertEqual(tag_order[0].severity, "warning")
            self.assertEqual(tag_order[0].resultStatus, "passed_with_warnings")
            self.assertEqual(catalog.checked_document_count, 1)
            self.assertEqual(catalog.checked_statement_count, 0)

    def test_approved_tag_order_is_error_and_skips_document(self):
        text = REQ_OK.replace(
            "[REQ-001:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 秘密情報を出力しない。",
            "[REQ-001:AC-01] [ALWAYS] [ACTOR:TargetSystem] [MUST] [CONSTRAINT] 秘密情報を出力しない。",
        )
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", "schemaVersion: \"1.0\"\nearsAi: \"1.0\"\n")
            _write(root, ".spec/requirements/REQ-001.md", text)
            catalog = doc_mod.build_catalog(root, WORKSPACE_ID)
            tag_order = [d for d in catalog.diagnostics if d.code == "EAI-CORE-SYNTAX-001"]
            self.assertEqual(tag_order[0].severity, "error")
            self.assertEqual(tag_order[0].resultStatus, "failed")
            self.assertEqual(catalog.checked_document_count, 0)
            self.assertEqual(catalog.checked_statement_count, 0)

    def test_id_format_is_always_error_even_in_draft(self):
        text = REQ_OK.replace("status: approved", "status: draft").replace(
            "REQ-001:AC-01", "REQ-01:AC-01"
        )
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", "schemaVersion: \"1.0\"\nearsAi: \"1.0\"\n")
            _write(root, ".spec/requirements/REQ-001.md", text)
            catalog = doc_mod.build_catalog(root, WORKSPACE_ID)
            id_fmt = [d for d in catalog.diagnostics if d.code == "EAI-CORE-ID-001"]
            self.assertEqual(len(id_fmt), 1)
            self.assertEqual(id_fmt[0].severity, "error")
            self.assertEqual(catalog.checked_document_count, 0)


class CatalogEnumerationTests(unittest.TestCase):
    def test_multiple_documents_are_counted_independently(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", "schemaVersion: \"1.0\"\nearsAi: \"1.0\"\n")
            _write(root, ".spec/requirements/REQ-001.md", REQ_OK)
            _write(
                root,
                ".spec/technical/TECH-001.md",
                "---\nid: TECH-001\ntitle: 前提\nstatus: approved\n---\n\n# TECH-001 前提\n\n## Context\n\n規範文なし。\n",
            )
            catalog = doc_mod.build_catalog(root, WORKSPACE_ID)
            self.assertEqual(catalog.diagnostics, [])
            self.assertEqual(catalog.checked_document_count, 2)
            self.assertEqual(catalog.checked_statement_count, 1)

    def test_duplicate_document_id_skips_both_and_reports_once(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", "schemaVersion: \"1.0\"\nearsAi: \"1.0\"\n")
            tech = "---\nid: TECH-001\ntitle: 前提技術\nstatus: approved\n---\n\n# TECH-001 前提技術\n\n## Context\n\n規範文なし。\n"
            _write(root, ".spec/technical/TECH-001-a.md", tech)
            _write(root, ".spec/technical/TECH-001-b.md", tech)
            catalog = doc_mod.build_catalog(root, WORKSPACE_ID)
            dup = [d for d in catalog.diagnostics if d.code == "SPEC-ID-DUPLICATE-001"]
            self.assertEqual(len(dup), 1)
            self.assertEqual(dup[0].source["path"], ".spec/technical/TECH-001-a.md")
            self.assertEqual(catalog.checked_document_count, 0)

    def test_unknown_spec_entry_is_warning(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", "schemaVersion: \"1.0\"\nearsAi: \"1.0\"\n")
            _write(root, ".spec/notes.txt", "memo\n")
            catalog = doc_mod.build_catalog(root, WORKSPACE_ID)
            codes = [d.code for d in catalog.diagnostics]
            self.assertIn("SPEC-WORKSPACE-UNKNOWN-001", codes)


class LimitTests(unittest.TestCase):
    def test_spec_markdown_over_1mib_is_skip_document(self):
        padding = "この段落はSPEC Markdownの1 MiB上限を超えるための固定文である。\n" * 20000
        text = REQ_OK + padding
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", "schemaVersion: \"1.0\"\nearsAi: \"1.0\"\n")
            _write(root, ".spec/requirements/REQ-001.md", text)
            self.assertGreater(len(text.encode("utf-8")), 1024 * 1024)
            catalog = doc_mod.build_catalog(root, WORKSPACE_ID)
            codes = [d.code for d in catalog.diagnostics]
            self.assertIn("SPEC-INPUT-LIMIT-001", codes)
            self.assertEqual(catalog.checked_document_count, 0)


class DuplicateIdWarningPreservationTests(unittest.TestCase):
    def test_warnings_before_duplicate_are_not_lost(self):
        # BOM警告（continue継続単位）は、文書ID重複によるskip-documentでも消えない。
        tech_text = (
            "---\nid: TECH-001\ntitle: 前提技術\nstatus: approved\n---\n\n"
            "# TECH-001 前提技術\n\n## Context\n\n規範文なし。\n"
        )
        tech_with_bom = ("﻿" + tech_text).encode("utf-8")
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", "schemaVersion: \"1.0\"\nearsAi: \"1.0\"\n")
            os.makedirs(os.path.join(root, ".spec/technical"), exist_ok=True)
            with open(os.path.join(root, ".spec/technical/TECH-001-a.md"), "wb") as f:
                f.write(tech_with_bom)
            with open(os.path.join(root, ".spec/technical/TECH-001-b.md"), "w", encoding="utf-8") as f:
                f.write(tech_text)  # BOMなし。重複IDのDiagnosticは1件だけ。
            catalog = doc_mod.build_catalog(root, WORKSPACE_ID)
            codes = [d.code for d in catalog.diagnostics]
            self.assertIn("SPEC-ID-DUPLICATE-001", codes)
            self.assertIn("SPEC-INPUT-BOM-001", codes)
            bom = next(d for d in catalog.diagnostics if d.code == "SPEC-INPUT-BOM-001")
            self.assertEqual(bom.source["path"], ".spec/technical/TECH-001-a.md")
            self.assertEqual(catalog.checked_document_count, 0)


class FenceHeadingExclusionTests(unittest.TestCase):
    def test_fenced_comment_hash_is_not_counted_as_h1(self):
        text = REQ_OK.replace(
            "## Intent\n\n意図。\n",
            "## Intent\n\n```text\n# comment\n```\n\n意図。\n",
        )
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", "schemaVersion: \"1.0\"\nearsAi: \"1.0\"\n")
            _write(root, ".spec/requirements/REQ-001.md", text)
            catalog = doc_mod.build_catalog(root, WORKSPACE_ID)
            h1 = [d for d in catalog.diagnostics if d.code == "SPEC-STYLE-H1-001"]
            self.assertEqual(h1, [])
            self.assertEqual(catalog.checked_document_count, 1)

    def test_indented_and_blockquoted_hash_is_not_counted_as_h2(self):
        text = REQ_OK.replace(
            "## Verification\n\n未証明。\n",
            "## Verification\n\n    ## fake section\n\n> ## also fake\n\n未証明。\n",
        )
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", "schemaVersion: \"1.0\"\nearsAi: \"1.0\"\n")
            _write(root, ".spec/requirements/REQ-001.md", text)
            catalog = doc_mod.build_catalog(root, WORKSPACE_ID)
            self.assertEqual(catalog.diagnostics, [])
            self.assertEqual(catalog.checked_document_count, 1)


class StatementDocumentIdMismatchTests(unittest.TestCase):
    def test_statement_with_foreign_document_id_is_rejected(self):
        text = REQ_OK.replace("REQ-001:AC-01", "REQ-002:AC-01")
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", "schemaVersion: \"1.0\"\nearsAi: \"1.0\"\n")
            _write(root, ".spec/requirements/REQ-001.md", text)
            catalog = doc_mod.build_catalog(root, WORKSPACE_ID)
            id_fmt = [d for d in catalog.diagnostics if d.code == "EAI-CORE-ID-001"]
            self.assertEqual(len(id_fmt), 1)
            self.assertEqual(id_fmt[0].summary, "規範文IDの文書部分が文書IDと一致しません")
            self.assertEqual(catalog.checked_document_count, 0)


class NestedUnknownEntryTests(unittest.TestCase):
    def test_non_markdown_file_under_kind_directory_is_warning(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", "schemaVersion: \"1.0\"\nearsAi: \"1.0\"\n")
            _write(root, ".spec/requirements/REQ-001.md", REQ_OK)
            _write(root, ".spec/requirements/.hidden", "temp\n")
            catalog = doc_mod.build_catalog(root, WORKSPACE_ID)
            unknown = [d for d in catalog.diagnostics if d.code == "SPEC-WORKSPACE-UNKNOWN-001"]
            self.assertEqual(len(unknown), 1)
            self.assertEqual(unknown[0].source["path"], ".spec/requirements/.hidden")
            self.assertEqual(catalog.checked_document_count, 1)


class SymlinkExclusionTests(unittest.TestCase):
    def test_symlinked_markdown_file_is_not_read(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", "schemaVersion: \"1.0\"\nearsAi: \"1.0\"\n")
            outside = os.path.join(root, "outside.md")
            with open(outside, "w", encoding="utf-8") as f:
                f.write(REQ_OK)
            os.makedirs(os.path.join(root, ".spec/requirements"), exist_ok=True)
            link_path = os.path.join(root, ".spec/requirements/REQ-001.md")
            os.symlink(outside, link_path)
            catalog = doc_mod.build_catalog(root, WORKSPACE_ID)
            unknown = [d for d in catalog.diagnostics if d.code == "SPEC-WORKSPACE-UNKNOWN-001"]
            self.assertEqual(len(unknown), 1)
            self.assertEqual(unknown[0].source["path"], ".spec/requirements/REQ-001.md")
            self.assertEqual(catalog.checked_document_count, 0)
            self.assertEqual(catalog.entries, [])

    def test_symlinked_kind_directory_is_not_walked(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", "schemaVersion: \"1.0\"\nearsAi: \"1.0\"\n")
            real_dir = os.path.join(root, "real-requirements")
            os.makedirs(real_dir, exist_ok=True)
            with open(os.path.join(real_dir, "REQ-001.md"), "w", encoding="utf-8") as f:
                f.write(REQ_OK)
            os.makedirs(os.path.join(root, ".spec"), exist_ok=True)
            os.symlink(real_dir, os.path.join(root, ".spec/requirements"))
            catalog = doc_mod.build_catalog(root, WORKSPACE_ID)
            unknown = [d for d in catalog.diagnostics if d.code == "SPEC-WORKSPACE-UNKNOWN-001"]
            self.assertEqual(len(unknown), 1)
            self.assertEqual(unknown[0].source["path"], ".spec/requirements")
            self.assertEqual(catalog.checked_document_count, 0)


class SpecFileCountLimitTests(unittest.TestCase):
    def test_file_count_over_limit_stops_without_reading(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", "schemaVersion: \"1.0\"\nearsAi: \"1.0\"\n")
            for i in range(1, 4):
                _write(root, f".spec/requirements/REQ-{i:03d}.md", REQ_OK.replace("REQ-001", f"REQ-{i:03d}"))
            catalog = doc_mod.build_catalog(root, WORKSPACE_ID, spec_file_count_limit=2)
            self.assertEqual(len(catalog.diagnostics), 1)
            diag = catalog.diagnostics[0]
            self.assertEqual(diag.code, "SPEC-INPUT-LIMIT-001")
            self.assertEqual(diag.summary, "SPEC fileが2件上限を超過しました")
            self.assertEqual(diag.source["path"], ".spec")
            self.assertEqual(catalog.checked_document_count, 0)
            self.assertEqual(catalog.entries, [])

    def test_file_count_at_limit_is_processed_normally(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", "schemaVersion: \"1.0\"\nearsAi: \"1.0\"\n")
            for i in range(1, 3):
                _write(root, f".spec/requirements/REQ-{i:03d}.md", REQ_OK.replace("REQ-001", f"REQ-{i:03d}"))
            catalog = doc_mod.build_catalog(root, WORKSPACE_ID, spec_file_count_limit=2)
            self.assertEqual(catalog.diagnostics, [])
            self.assertEqual(catalog.checked_document_count, 2)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
