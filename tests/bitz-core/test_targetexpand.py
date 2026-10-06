"""`TargetExpansion(root, purpose)`（`targetexpand.py`）の単体試験。

`04_関係・トレースモデル.md` §6.1・§6.4の`interpret`閉包規則（`requires`を終端まで辿ること、`refines`の順方向／
逆方向、`refines`する`draft`の文書を役割`advisory`として含めること、ADRと規範文を起点にした解決）を検査する。
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


def _task(doc_id: str, status: str = "open", extra_frontmatter: str = "") -> str:
    return f"""---
id: {doc_id}
title: 作業
status: {status}
{extra_frontmatter}---

# {doc_id} 作業

## Objective

作業する。
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
        # TECH-001 `refines` REQ-001（`applicable`）。TECH-001はTECH-002を`requires`する。
        # REQ-001を起点にすると、逆参照でTECH-001を含め、さらにTECH-001の`requires`の閉包
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
            # `draft`の文書自体は`advisory`として含めるが、その`requires`（TECH-002）は辿らない。
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


class ImplementVerifyPurposeTests(unittest.TestCase):
    """`implement`/`verify`はStep 3で実装済み。素のREQを起点（依存なし）にして基本形を確認する。"""

    def test_implement_purpose_returns_target_statements(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
            id_index, stmt_index = _indexes(root)
            result = te_mod.target_expansion("REQ-001", "implement", id_index, stmt_index)
            self.assertEqual(result.errors, [])
            self.assertEqual(result.target_statements, ["REQ-001:AC-01"])

    def test_verify_purpose_returns_target_statements(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
            id_index, stmt_index = _indexes(root)
            result = te_mod.target_expansion("REQ-001", "verify", id_index, stmt_index)
            self.assertEqual(result.errors, [])
            self.assertEqual(result.target_statements, ["REQ-001:AC-01"])


class TaskImplementDependencyTests(unittest.TestCase):
    """目的`implement`でTASKを起点にした場合の、先行TASKの状態の検査（関係・トレースモデル §6.2、文書・フロントマター・状態仕様 §7）。"""

    def _expand(self, dependency_status: str, root_status: str = "open"):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
            _write(
                root,
                ".spec/tasks/TASK-001.md",
                _task("TASK-001", root_status, "relations:\n  requires: [TASK-002]\n  addresses: [REQ-001:AC-01]\n"),
            )
            _write(root, ".spec/tasks/TASK-002.md", _task("TASK-002", dependency_status))
            id_index, stmt_index = _indexes(root)
            return te_mod.target_expansion("TASK-001", "implement", id_index, stmt_index)

    def test_done_dependency_is_not_blocked(self):
        # 先行TASKが`done`であることは§6.2の前提であり、起点ではない`done`のTASKを`blocked`にしない。
        result = self._expand("done")
        self.assertEqual(result.errors, [])
        self.assertIn("TASK-002", result.context_documents)
        self.assertEqual(result.target_statements, ["REQ-001:AC-01"])

    def test_incomplete_dependency_is_blocked_by_task_dependency(self):
        result = self._expand("open")
        self.assertEqual([e["code"] for e in result.errors], ["CTX-TASK-DEPENDENCY-001"])

    def test_done_root_is_still_blocked(self):
        # `done`のTASKを目的`implement`の起点にした場合は、従来どおり`CTX-STATE-001`とする。
        result = self._expand("done", root_status="done")
        self.assertIn("CTX-STATE-001", [e["code"] for e in result.errors])



class TaskVerifyDependencyTests(unittest.TestCase):
    """目的`verify`でTASKを起点にした場合の、先行TASKの状態の検査（ADR-029 Decision 1、`verify` §4の手順2）。"""

    def _expand(self, dependency_status: str, root_status: str = "open"):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
            _write(
                root,
                ".spec/tasks/TASK-001.md",
                _task("TASK-001", root_status, "relations:\n  requires: [TASK-002]\n  addresses: [REQ-001:AC-01]\n"),
            )
            _write(root, ".spec/tasks/TASK-002.md", _task("TASK-002", dependency_status))
            id_index, stmt_index = _indexes(root)
            return te_mod.target_expansion("TASK-001", "verify", id_index, stmt_index)

    def test_done_dependency_passes_without_including_requires_closure(self):
        # §6.3: `verify`では起点のTASKの`requires`の閉包をコンテキストへ含めない。
        result = self._expand("done")
        self.assertEqual(result.errors, [])
        self.assertNotIn("TASK-002", result.context_documents)
        self.assertEqual(result.target_statements, ["REQ-001:AC-01"])

    def test_incomplete_dependency_is_blocked_by_task_dependency(self):
        for status in ("open", "cancelled"):
            with self.subTest(status=status):
                result = self._expand(status)
                self.assertEqual([e["code"] for e in result.errors], ["CTX-TASK-DEPENDENCY-001"])
                self.assertEqual(result.errors[0]["resultStatus"], "blocked")

    def test_done_root_with_incomplete_dependency_is_blocked(self):
        # 状態`done`のTASKは再検証できる（§6.3）が、先行TASKの検査は起点の状態によらない。
        result = self._expand("open", root_status="done")
        self.assertEqual([e["code"] for e in result.errors], ["CTX-TASK-DEPENDENCY-001"])

    def test_done_root_with_done_dependency_passes(self):
        result = self._expand("done", root_status="done")
        self.assertEqual(result.errors, [])



def _tech_ac(doc_id: str, extra_frontmatter: str = "") -> str:
    """規範文`<doc_id>:AC-01`を1件持つ、状態`approved`のTECH。"""
    return f"""---
id: {doc_id}
title: 技術契約
status: approved
{extra_frontmatter}---

# {doc_id} 技術契約

## Contract

- [{doc_id}:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 具体化された制約。
"""


class ShortestDistanceTests(unittest.TestCase):
    """距離は、閉包を作るときに辿ったエッジ1本を1段とした、起点からの最短の段数（関係・トレースモデル §7の6.）。"""

    def test_refines_target_reached_first_by_requires_has_distance_one(self):
        # 起点が直接`refines`する文書は、`requires`の鎖で先に到達しても距離1。
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            _write(root, ".spec/requirements/REQ-001.md",
                   _req("REQ-001", extra_frontmatter="relations:\n  requires: [REQ-002]\n  refines: [REQ-003]\n"))
            _write(root, ".spec/requirements/REQ-002.md",
                   _req("REQ-002", extra_frontmatter="relations:\n  requires: [REQ-003]\n"))
            _write(root, ".spec/requirements/REQ-003.md", _req("REQ-003"))
            id_index, stmt_index = _indexes(root)
            for purpose in ("interpret", "implement", "verify"):
                with self.subTest(purpose=purpose):
                    result = te_mod.target_expansion("REQ-001", purpose, id_index, stmt_index)
                    self.assertEqual(result.document_distance, {"REQ-001": 0, "REQ-002": 1, "REQ-003": 1})

    def test_draft_refinement_takes_the_nearest_refined_document(self):
        # 状態`draft`のREQ-009は閉包のREQ-003（距離2）とREQ-001（距離0）を`refines`する。宣言の順によらず距離1。
        for refines in ("[REQ-003, REQ-001]", "[REQ-001, REQ-003]"):
            with self.subTest(refines=refines), tempfile.TemporaryDirectory() as root:
                _write(root, ".spec/bitz.yaml", _bitz_yaml())
                _write(root, ".spec/requirements/REQ-001.md",
                       _req("REQ-001", extra_frontmatter="relations:\n  requires: [REQ-002]\n"))
                _write(root, ".spec/requirements/REQ-002.md",
                       _req("REQ-002", extra_frontmatter="relations:\n  requires: [REQ-003]\n"))
                _write(root, ".spec/requirements/REQ-003.md", _req("REQ-003"))
                _write(root, ".spec/requirements/REQ-009.md",
                       _req("REQ-009", status="draft", extra_frontmatter=f"relations:\n  refines: {refines}\n"))
                id_index, stmt_index = _indexes(root)
                result = te_mod.target_expansion("REQ-001", "interpret", id_index, stmt_index)
                self.assertIn("REQ-009", result.draft_advisory)
                self.assertEqual(result.document_distance["REQ-009"], 1)

    def test_draft_refining_another_draft_is_not_counted_through_it(self):
        # REQ-008（draft）はREQ-007（draft、距離1）とREQ-003（距離2）を`refines`する。`advisory`の文書を`refines`するエッジは
        # 辿らない（§6.1の6.）ので、REQ-007を経由せず、REQ-003から数えて距離3。
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            _write(root, ".spec/requirements/REQ-001.md",
                   _req("REQ-001", extra_frontmatter="relations:\n  requires: [REQ-002]\n"))
            _write(root, ".spec/requirements/REQ-002.md",
                   _req("REQ-002", extra_frontmatter="relations:\n  requires: [REQ-003]\n"))
            _write(root, ".spec/requirements/REQ-003.md", _req("REQ-003"))
            _write(root, ".spec/requirements/REQ-007.md",
                   _req("REQ-007", status="draft", extra_frontmatter="relations:\n  refines: [REQ-001]\n"))
            _write(root, ".spec/requirements/REQ-008.md",
                   _req("REQ-008", status="draft", extra_frontmatter="relations:\n  refines: [REQ-007, REQ-003]\n"))
            id_index, stmt_index = _indexes(root)
            result = te_mod.target_expansion("REQ-001", "interpret", id_index, stmt_index)
            self.assertEqual(result.document_distance["REQ-007"], 1)
            self.assertEqual(result.document_distance["REQ-008"], 3)

    def test_refining_document_reached_from_two_refined_documents_takes_the_minimum(self):
        # TECH-030はTECH-010（距離2）とTECH-020（`requires`で距離1）を`refines`する。後から見つかった参照先からの到達も数え、距離2。
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            _write(root, ".spec/requirements/REQ-001.md",
                   _req("REQ-001", extra_frontmatter="relations:\n  requires: [TECH-020]\n"))
            _write(root, ".spec/technical/TECH-001.md", _tech("TECH-001", extra_frontmatter="relations:\n  refines: [REQ-001]\n"))
            _write(root, ".spec/technical/TECH-010.md", _tech("TECH-010", extra_frontmatter="relations:\n  refines: [TECH-001]\n"))
            _write(root, ".spec/technical/TECH-011.md", _tech("TECH-011", extra_frontmatter="relations:\n  refines: [TECH-001]\n"))
            _write(root, ".spec/technical/TECH-020.md", _tech("TECH-020", extra_frontmatter="relations:\n  refines: [TECH-011]\n"))
            _write(root, ".spec/technical/TECH-030.md",
                   _tech("TECH-030", extra_frontmatter="relations:\n  refines: [TECH-010, TECH-020]\n"))
            id_index, stmt_index = _indexes(root)
            result = te_mod.target_expansion("REQ-001", "interpret", id_index, stmt_index)
            self.assertEqual(result.document_distance["TECH-020"], 1)
            self.assertEqual(result.document_distance["TECH-030"], 2)

    def test_successor_of_superseded_root_has_distance_one(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            _write(root, ".spec/technical/TECH-001.md", _tech("TECH-001"))
            _write(root, ".spec/technical/TECH-002.md",
                   _tech("TECH-002", extra_frontmatter="relations:\n  supersedes: [TECH-001]\n"))
            id_index, stmt_index = _indexes(root)
            result = te_mod.target_expansion("TECH-001", "interpret", id_index, stmt_index)
            self.assertEqual(result.superseded_origin, ("TECH-001", "TECH-002"))
            self.assertEqual(result.document_distance["TECH-002"], 1)

    def _refinement_chain(self, root: str) -> None:
        # REQ-001:AC-01 <- TECH-002（規範文単位で具体化）<- TECH-003（TECH-002:AC-01を具体化）。TASK-009はTECH-003:AC-01に対応する。
        _write(root, ".spec/bitz.yaml", _bitz_yaml())
        _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
        _write(root, ".spec/technical/TECH-002.md",
               _tech_ac("TECH-002", "relations:\n  refines: [REQ-001:AC-01]\n"))
        _write(root, ".spec/technical/TECH-003.md",
               _tech_ac("TECH-003", "relations:\n  refines: [TECH-002:AC-01]\n"))
        _write(root, ".spec/tasks/TASK-009.md", _task("TASK-009", "open", "relations:\n  addresses: [TECH-003:AC-01]\n"))

    def test_transitive_refinement_and_addressing_task_count_each_edge(self):
        with tempfile.TemporaryDirectory() as root:
            self._refinement_chain(root)
            id_index, stmt_index = _indexes(root)
            result = te_mod.target_expansion("REQ-001", "implement", id_index, stmt_index)
            self.assertEqual(result.errors, [])
            self.assertIn("TECH-003:AC-01", result.target_statements)
            # TASK-009は、`addresses`する対象規範文を所有するTECH-003（距離2）から1段。
            self.assertEqual(result.document_distance,
                             {"REQ-001": 0, "TECH-002": 1, "TECH-003": 2, "TASK-009": 3})

    def test_task_root_refinements_are_counted_from_the_addressed_document(self):
        with tempfile.TemporaryDirectory() as root:
            self._refinement_chain(root)
            _write(root, ".spec/tasks/TASK-001.md",
                   _task("TASK-001", "open", "relations:\n  addresses: [REQ-001:AC-01]\n"))
            id_index, stmt_index = _indexes(root)
            for purpose in ("implement", "verify"):
                with self.subTest(purpose=purpose):
                    result = te_mod.target_expansion("TASK-001", purpose, id_index, stmt_index)
                    self.assertEqual(result.errors, [])
                    distance = result.document_distance
                    self.assertEqual((distance["REQ-001"], distance["TECH-002"], distance["TECH-003"]), (1, 2, 3))

    def test_verify_task_root_takes_the_minimum_over_addressed_documents(self):
        # TASK-001はREQ-001とREQ-002の規範文に対応し、REQ-001はREQ-002を`requires`する。REQ-002は起点から1段。
        with tempfile.TemporaryDirectory() as root:
            _write(root, ".spec/bitz.yaml", _bitz_yaml())
            _write(root, ".spec/requirements/REQ-001.md",
                   _req("REQ-001", extra_frontmatter="relations:\n  requires: [REQ-002]\n"))
            _write(root, ".spec/requirements/REQ-002.md", _req("REQ-002"))
            _write(root, ".spec/tasks/TASK-001.md",
                   _task("TASK-001", "open", "relations:\n  addresses: [REQ-001:AC-01, REQ-002:AC-01]\n"))
            id_index, stmt_index = _indexes(root)
            result = te_mod.target_expansion("TASK-001", "verify", id_index, stmt_index)
            self.assertEqual(result.errors, [])
            self.assertEqual(result.document_distance, {"TASK-001": 0, "REQ-001": 1, "REQ-002": 1})


class DraftRefinementPurposeTests(unittest.TestCase):
    """`refines`する状態`draft`の文書は目的`interpret`だけで役割`advisory`として含め、`implement`と`verify`では閉包へ含めない
    （関係・トレースモデル §6.1の6.と末尾）。"""

    def _write_base(self, root: str) -> None:
        _write(root, ".spec/bitz.yaml", _bitz_yaml())
        _write(root, ".spec/requirements/REQ-001.md", _req("REQ-001"))
        _write(root, ".spec/technical/TECH-005.md",
               _tech("TECH-005", status="draft", extra_frontmatter="relations:\n  refines: [REQ-001]\n"))

    def test_only_interpret_includes_draft_refinement(self):
        with tempfile.TemporaryDirectory() as root:
            self._write_base(root)
            id_index, stmt_index = _indexes(root)
            interpret = te_mod.target_expansion("REQ-001", "interpret", id_index, stmt_index)
            self.assertEqual(interpret.draft_advisory, {"TECH-005"})
            self.assertIn("TECH-005", interpret.context_documents)
            for purpose in ("implement", "verify"):
                with self.subTest(purpose=purpose):
                    result = te_mod.target_expansion("REQ-001", purpose, id_index, stmt_index)
                    self.assertEqual(result.errors, [])
                    self.assertEqual(result.draft_advisory, set())
                    self.assertEqual(result.context_documents, ["REQ-001"])

    def test_task_root_is_not_blocked_by_draft_refinement(self):
        # 修正前は、`draft`の文書を閉包へ含めたうえで状態を検査し、`CTX-STATE-001`で止めていた。
        with tempfile.TemporaryDirectory() as root:
            self._write_base(root)
            _write(root, ".spec/requirements/REQ-002.md",
                   _req("REQ-002", extra_frontmatter="relations:\n  requires: [REQ-001]\n"))
            _write(root, ".spec/tasks/TASK-001.md",
                   _task("TASK-001", "open", "relations:\n  requires: [REQ-001]\n  addresses: [REQ-002:AC-01]\n"))
            _write(root, ".spec/tasks/TASK-002.md",
                   _task("TASK-002", "open", "relations:\n  addresses: [REQ-001:AC-01]\n"))
            id_index, stmt_index = _indexes(root)
            for root_id, purpose in (("TASK-001", "implement"), ("TASK-002", "verify")):
                with self.subTest(root=root_id, purpose=purpose):
                    result = te_mod.target_expansion(root_id, purpose, id_index, stmt_index)
                    self.assertEqual(result.errors, [])
                    self.assertNotIn("TECH-005", result.context_documents)


if __name__ == "__main__":
    unittest.main()
