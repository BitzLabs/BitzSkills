"""`TargetExpansion(root, purpose)`（`targetexpand.py`）の単体試験。

`04_関係・トレースモデル.md` §6.1・§6.4の`interpret`閉包規則（requires終端、refines forward/
backward、draft refinementのadvisory包含、ADRとstatement起点の解決）を検査する。
"""

import os
import tempfile
import unittest

from bitz import document as doc_mod
from bitz import relations as rel_mod
from bitz import targetexpand as te_mod

WORKSPACE_ID = "root"


def _write(root: str, rel_path: str, content: str) -> None:
    full = os.path.join(root, rel_path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(content)


def _bitz_yaml() -> str:
    return 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\n'


def _req(doc_id: str, status: str = "approved", extra_frontmatter: str = "") -> str:
    return f"""---
id: {doc_id}
title: 検査対象
status: {status}
{extra_frontmatter}---

# {doc_id} 検査対象

## Intent

意図。

## Acceptance Criteria

- [{doc_id}:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 秘密情報を出力しない。

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


def _adr(doc_id: str, status: str = "accepted") -> str:
    return f"""---
id: {doc_id}
title: 判断
status: {status}
---

# {doc_id} 判断

## Context

背景。

## Decision

決定。

## Consequences

帰結。
"""


def _indexes(root: str):
    catalog = doc_mod.build_catalog(root, WORKSPACE_ID)
    id_index = rel_mod.build_id_index(catalog.entries)
    statement_index = rel_mod.build_statement_index(catalog.entries)
    return id_index, statement_index


class RequiresClosureTests(unittest.TestCase):
    def test_requires_closure_is_transitive(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            _write(
                root,
                ".spec/requirements/REQ-001.md",
                _req("REQ-001", extra_frontmatter="relations:\n  requires: [REQ-002]\n"),
            )
            _write(
                root,
                ".spec/requirements/REQ-002.md",
                _req("REQ-002", extra_frontmatter="relations:\n  requires: [REQ-003]\n"),
            )
            _write(root, ".spec/requirements/REQ-003.md", _req("REQ-003"))
            id_index, stmt_index = _indexes(root)
            result = te_mod.target_expansion("REQ-001", "interpret", id_index, stmt_index)
            self.assertEqual(result.context_documents, ["REQ-001", "REQ-002", "REQ-003"])


class RefinesTests(unittest.TestCase):
    def test_forward_refines_included(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            _write(
                root,
                ".spec/technical/TECH-001.md",
                _tech("TECH-001", extra_frontmatter="relations:\n  refines: [REQ-001]\n"),
            )
            _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
            id_index, stmt_index = _indexes(root)
            result = te_mod.target_expansion("TECH-001", "interpret", id_index, stmt_index)
            self.assertIn("REQ-001", result.context_documents)

    def test_backward_applicable_refinement_and_its_requires_included(self):
        # TECH-001 refines REQ-001（applicable）。TECH-001はTECH-002をrequiresする。
        # REQ-001を起点にすると、逆参照でTECH-001を含め、さらにTECH-001のrequires閉包
        # （TECH-002）も含める（§6.1「4.」）。
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
            _write(
                root,
                ".spec/technical/TECH-001.md",
                _tech(
                    "TECH-001",
                    extra_frontmatter="relations:\n  refines: [REQ-001]\n  requires: [TECH-002]\n",
                ),
            )
            _write(root, ".spec/technical/TECH-002.md", _tech("TECH-002"))
            id_index, stmt_index = _indexes(root)
            result = te_mod.target_expansion("REQ-001", "interpret", id_index, stmt_index)
            self.assertEqual(result.context_documents, ["REQ-001", "TECH-001", "TECH-002"])

    def test_draft_refinement_is_advisory_included_without_following_further(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
            _write(
                root,
                ".spec/technical/TECH-001.md",
                _tech(
                    "TECH-001",
                    status="draft",
                    extra_frontmatter="relations:\n  refines: [REQ-001]\n  requires: [TECH-002]\n",
                ),
            )
            _write(root, ".spec/technical/TECH-002.md", _tech("TECH-002"))
            id_index, stmt_index = _indexes(root)
            result = te_mod.target_expansion("REQ-001", "interpret", id_index, stmt_index)
            # draft文書自体はadvisoryとして含めるが、そのrequires（TECH-002）は辿らない。
            self.assertIn("TECH-001", result.context_documents)
            self.assertNotIn("TECH-002", result.context_documents)

    def test_outdated_refinement_is_not_backward_included(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
            _write(
                root,
                ".spec/technical/TECH-001.md",
                _tech("TECH-001", status="outdated", extra_frontmatter="relations:\n  refines: [REQ-001]\n"),
            )
            id_index, stmt_index = _indexes(root)
            result = te_mod.target_expansion("REQ-001", "interpret", id_index, stmt_index)
            self.assertEqual(result.context_documents, ["REQ-001"])


class RootFormTests(unittest.TestCase):
    def test_adr_root_resolves_to_itself_only(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            _write(root, ".spec/decisions/ADR-001.md", _adr("ADR-001"))
            id_index, stmt_index = _indexes(root)
            result = te_mod.target_expansion("ADR-001", "interpret", id_index, stmt_index)
            self.assertEqual(result.root_documents, ["ADR-001"])
            self.assertEqual(result.context_documents, ["ADR-001"])
            self.assertEqual(result.target_statements, [])

    def test_statement_root_resolves_to_owning_document(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
            id_index, stmt_index = _indexes(root)
            result = te_mod.target_expansion("REQ-001:AC-01", "interpret", id_index, stmt_index)
            self.assertEqual(result.root_documents, ["REQ-001"])

    def test_unresolvable_root_returns_none(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
            id_index, stmt_index = _indexes(root)
            result = te_mod.target_expansion("REQ-999", "interpret", id_index, stmt_index)
            self.assertIsNone(result)


class UnimplementedPurposeTests(unittest.TestCase):
    """`implement`/`verify`はStep 3で実装するまで、黙ってinterpretと同じ結果を返してはならない。"""

    def test_implement_purpose_raises(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
            id_index, stmt_index = _indexes(root)
            with self.assertRaises(NotImplementedError):
                te_mod.target_expansion("REQ-001", "implement", id_index, stmt_index)

    def test_verify_purpose_raises(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
            id_index, stmt_index = _indexes(root)
            with self.assertRaises(NotImplementedError):
                te_mod.target_expansion("REQ-001", "verify", id_index, stmt_index)


if __name__ == "__main__":
    unittest.main()
