"""閉包を、下方向の出発点から具体化を辿り上方向へ依存を辿る到達可能性で求める規則の単体試験（ADR-071 Decision 2、関係・トレースモデル §6.1〜§6.3・§7）。

閉包は、下方向の出発点（起点がREQ・TECH・ADRなら起点文書、TASKならその`addresses`の参照先の所有文書）から`refines`を逆向きに辿った具体化文書と合わせたS、
Sから`requires`・`refines`・`addresses`の参照先を終端まで辿った上方向の閉包との和集合である。上方向の辺がSの文書へ戻る場合は、その文書へ着いたとはみなさない
（役割・到達したエッジ・距離に使わない）。状態`draft`のadvisoryはSの文書またはその規範文を`refines`する文書だけである。
各試験の期待値は、規範から導いたリテラルである（Coreの出力は根拠にしない）。修正前のCoreは、`refines`の参照先を1段だけ含め、その`requires`を辿らなかった。
"""

from __future__ import annotations

import os
import tempfile
import unittest

from bitz import context as context_mod
from bitz import document as doc_mod
from bitz import relations as rel_mod
from bitz import targetexpand as te_mod
from bitz.cliargs import ParsedArgs

WORKSPACE_ID = "root"
NO_GIT_ENV = {**os.environ, "GIT_DIR": os.devnull}


def _write(root: str, rel_path: str, content: str) -> None:
    full = os.path.join(root, rel_path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as handle:
        handle.write(content)


def _relations(**relations: list[str]) -> str:
    items = {name: refs for name, refs in relations.items() if refs}
    if not items:
        return ""
    return "relations:\n" + "".join(f"  {name}: [{', '.join(refs)}]\n" for name, refs in items.items())


def _req(doc_id: str, status: str = "approved", **relations: list[str]) -> str:
    """規範文`<doc_id>:AC-01`を1件持つREQ。"""

    return (
        f"---\nid: {doc_id}\ntitle: 要求\nstatus: {status}\n{_relations(**relations)}---\n\n# {doc_id} 要求\n\n## Intent\n\n意図。\n\n"
        f"## Acceptance Criteria\n\n- [{doc_id}:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 秘密情報を出力しない。\n\n## Verification\n\n未証明。\n"
    )


def _tech(doc_id: str, status: str = "approved", *, statement: bool = False, **relations: list[str]) -> str:
    body = (
        f"## Contract\n\n- [{doc_id}:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 入力形式を固定する。\n"
        if statement
        else "## Context\n\n規範文を持たない。\n"
    )
    return f"---\nid: {doc_id}\ntitle: 技術契約\nstatus: {status}\n{_relations(**relations)}---\n\n# {doc_id} 技術契約\n\n{body}"


def _adr(doc_id: str, status: str = "accepted") -> str:
    return (
        f"---\nid: {doc_id}\ntitle: 判断\nstatus: {status}\n---\n\n# {doc_id} 判断\n\n## Context\n\n背景。\n\n## Decision\n\n決定。\n\n## Consequences\n\n帰結。\n"
    )


def _task(doc_id: str, status: str = "open", **relations: list[str]) -> str:
    return f"---\nid: {doc_id}\ntitle: 作業\nstatus: {status}\n{_relations(**relations)}---\n\n# {doc_id} 作業\n\n## Objective\n\n作業する。\n"


class _Workspace(unittest.TestCase):
    def build(self, files: dict[str, str]) -> str:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = tmp.name
        _write(root, ".spec/bitz.yaml", 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\n')
        for rel, content in files.items():
            _write(root, rel, content)
        self.root = root
        catalog = doc_mod.build_catalog(root, WORKSPACE_ID)
        self.id_index = rel_mod.build_id_index(catalog.entries)
        self.statement_index = rel_mod.build_statement_index(catalog.entries)
        return root

    def expand(self, root_id: str, purpose: str) -> te_mod.TargetExpansionResult:
        result = te_mod.target_expansion(root_id, purpose, self.id_index, self.statement_index)
        self.assertIsNotNone(result)
        return result

    def context(self, root_id: str, purpose: str = "interpret") -> dict:
        parsed = ParsedArgs(operation="context", positionals=[root_id], flags=set(), single={"--purpose": purpose, "--detail": "standard", "--format": "json"}, repeat={})
        return context_mod.run(parsed, self.root, NO_GIT_ENV)[0]


PURPOSES = ("interpret", "implement", "verify")


class UpwardClosureTests(_Workspace):
    def test_refines_target_is_followed_to_its_requires_and_its_own_refines(self):
        """起点が`refines`する文書の`requires`と、その文書が`refines`する祖父の文書の`requires`も、終端まで閉包に含める。"""

        self.build({
            ".spec/technical/TECH-003.md": _tech("TECH-003", refines=["TECH-002"]),
            ".spec/technical/TECH-002.md": _tech("TECH-002", refines=["REQ-001"], requires=["REQ-002"]),
            ".spec/requirements/REQ-001.md": _req("REQ-001", requires=["REQ-003"]),
            ".spec/requirements/REQ-002.md": _req("REQ-002"),
            ".spec/requirements/REQ-003.md": _req("REQ-003"),
        })
        for purpose in PURPOSES:
            with self.subTest(purpose=purpose):
                result = self.expand("TECH-003", purpose)
                self.assertEqual(result.errors, [])
                self.assertEqual(result.context_documents, ["REQ-001", "REQ-002", "REQ-003", "TECH-002", "TECH-003"])
                self.assertEqual(
                    result.document_distance, {"TECH-003": 0, "TECH-002": 1, "REQ-001": 2, "REQ-002": 2, "REQ-003": 3}
                )

    def test_roles_of_documents_reached_upward(self):
        """`refines`のエッジで上方向に着いた文書は役割`refinement`、`requires`のエッジで着いた文書は`requirement`と`constraint`。"""

        self.build({
            ".spec/technical/TECH-003.md": _tech("TECH-003", refines=["TECH-002"]),
            ".spec/technical/TECH-002.md": _tech("TECH-002", refines=["REQ-001"], requires=["REQ-002"]),
            ".spec/requirements/REQ-001.md": _req("REQ-001", requires=["TECH-004"]),
            ".spec/requirements/REQ-002.md": _req("REQ-002"),
            ".spec/technical/TECH-004.md": _tech("TECH-004"),
        })
        roles = {d["id"]: d["role"] for d in self.context("TECH-003")["documents"]}
        self.assertEqual(
            roles,
            {"TECH-003": "root", "TECH-002": "refinement", "REQ-001": "refinement", "REQ-002": "requirement", "TECH-004": "constraint"},
        )

    def test_refiner_includes_its_other_parent_and_that_parents_requires(self):
        """具体化文書が`refines`する別の親と、その親の`requires`も含める。"""

        self.build({
            ".spec/requirements/REQ-001.md": _req("REQ-001"),
            ".spec/requirements/REQ-002.md": _req("REQ-002", requires=["REQ-003"]),
            ".spec/requirements/REQ-003.md": _req("REQ-003"),
            ".spec/technical/TECH-010.md": _tech("TECH-010", refines=["REQ-001", "REQ-002"]),
        })
        for purpose in PURPOSES:
            with self.subTest(purpose=purpose):
                result = self.expand("REQ-001", purpose)
                self.assertEqual(result.context_documents, ["REQ-001", "REQ-002", "REQ-003", "TECH-010"])
                self.assertEqual(result.document_distance, {"REQ-001": 0, "TECH-010": 1, "REQ-002": 2, "REQ-003": 3})
        roles = {d["id"]: d["role"] for d in self.context("REQ-001")["documents"]}
        self.assertEqual(roles["REQ-002"], "refinement")
        self.assertEqual(roles["REQ-003"], "requirement")

    def test_siblings_of_a_refiner_are_not_included(self):
        """具体化文書を起点にしたとき、同じ親を`refines`する兄弟の具体化文書は含めない（下方向へ辿るのは出発点からだけ）。"""

        self.build({
            ".spec/requirements/REQ-001.md": _req("REQ-001"),
            ".spec/technical/TECH-010.md": _tech("TECH-010", refines=["REQ-001"]),
            ".spec/technical/TECH-011.md": _tech("TECH-011", refines=["REQ-001"]),
        })
        for purpose in PURPOSES:
            with self.subTest(purpose=purpose):
                self.assertEqual(self.expand("TECH-010", purpose).context_documents, ["REQ-001", "TECH-010"])
                self.assertEqual(self.expand("REQ-001", purpose).context_documents, ["REQ-001", "TECH-010", "TECH-011"])

    def test_requires_target_is_not_a_downward_start(self):
        """`requires`で上方向に着いた文書を`refines`する文書は、含めない。"""

        self.build({
            ".spec/requirements/REQ-001.md": _req("REQ-001", requires=["REQ-002"]),
            ".spec/requirements/REQ-002.md": _req("REQ-002"),
            ".spec/technical/TECH-001.md": _tech("TECH-001", refines=["REQ-002"]),
        })
        for purpose in PURPOSES:
            with self.subTest(purpose=purpose):
                self.assertEqual(self.expand("REQ-001", purpose).context_documents, ["REQ-001", "REQ-002"])

    def test_presentation_of_an_upward_refinement_follows_the_ledger(self):
        """上方向に`refines`で着いた距離2の役割`refinement`の文書は、所有する規範文が制約台帳にあるものだけ`normative`、ないものは`full`（`context` §5）。"""

        self.build({
            ".spec/technical/TECH-003.md": _tech("TECH-003", refines=["TECH-002"], statement=True),
            ".spec/technical/TECH-002.md": _tech("TECH-002", refines=["REQ-001"]),
            ".spec/requirements/REQ-001.md": _req("REQ-001"),
        })
        documents = {d["id"]: d for d in self.context("TECH-003", "implement")["documents"]}
        self.assertEqual(documents["TECH-002"]["projection"], "full")  # 距離1
        self.assertEqual((documents["REQ-001"]["role"], documents["REQ-001"]["projection"]), ("refinement", "full"))  # 距離2、規範文が台帳にない
        self.build({
            ".spec/technical/TECH-003.md": _tech("TECH-003", refines=["TECH-002"], statement=True),
            ".spec/technical/TECH-002.md": _tech("TECH-002", refines=["TECH-001"]),
            ".spec/technical/TECH-001.md": _tech("TECH-001"),
        })
        documents = {d["id"]: d for d in self.context("TECH-003", "implement")["documents"]}
        self.assertEqual((documents["TECH-001"]["role"], documents["TECH-001"]["projection"]), ("refinement", "normative"))  # 距離2、規範文を持たない


class ReturningEdgeTests(_Workspace):
    def shape(self) -> None:
        # REQ-001（起点）を、TECH-010・TECH-011が`refines`し、TECH-012がTECH-011を、TECH-013がTECH-012を`refines`する（すべてS）。
        # TECH-010が`requires`でTECH-013（S）へ戻る辺と、TECH-010が起点REQ-001（S）を`requires`する辺は、着いたとはみなさない。
        self.build({
            ".spec/requirements/REQ-001.md": _req("REQ-001"),
            ".spec/technical/TECH-010.md": _tech("TECH-010", refines=["REQ-001"], requires=["TECH-013", "REQ-001"]),
            ".spec/technical/TECH-011.md": _tech("TECH-011", refines=["REQ-001"]),
            ".spec/technical/TECH-012.md": _tech("TECH-012", refines=["TECH-011"]),
            ".spec/technical/TECH-013.md": _tech("TECH-013", refines=["TECH-012"]),
        })

    def test_returning_edges_do_not_shorten_distances_or_add_reached_edges(self):
        self.shape()
        for purpose in PURPOSES:
            with self.subTest(purpose=purpose):
                result = self.expand("REQ-001", purpose)
                self.assertEqual(
                    result.document_distance,
                    {"REQ-001": 0, "TECH-010": 1, "TECH-011": 1, "TECH-012": 2, "TECH-013": 3},
                )
                self.assertEqual(result.document_edges["TECH-013"], [("refines", "TECH-013")])
                self.assertEqual(result.document_edges["REQ-001"], [])

    def test_returning_edge_does_not_change_the_role_or_reached_by_of_the_origin(self):
        self.shape()
        documents = {d["id"]: d for d in self.context("REQ-001")["documents"]}
        self.assertEqual((documents["REQ-001"]["role"], documents["REQ-001"]["reachedBy"]), ("root", ["root"]))
        self.assertEqual(documents["TECH-013"]["reachedBy"], ["refines:TECH-013"])


class DraftAdvisoryTests(_Workspace):
    def test_draft_refining_a_document_reached_upward_is_not_included(self):
        """上方向で着いた文書を`refines`する`draft`の文書は、advisoryにも閉包にも入らない。Sの文書を`refines`する`draft`の文書は入る。"""

        self.build({
            ".spec/technical/TECH-001.md": _tech("TECH-001", refines=["REQ-001"]),
            ".spec/requirements/REQ-001.md": _req("REQ-001"),
            ".spec/technical/TECH-005.md": _tech("TECH-005", "draft", refines=["REQ-001"]),
            ".spec/technical/TECH-006.md": _tech("TECH-006", "draft", refines=["TECH-001"]),
        })
        result = self.expand("TECH-001", "interpret")
        self.assertEqual(result.draft_advisory, {"TECH-006"})
        self.assertEqual(result.context_documents, ["REQ-001", "TECH-001", "TECH-006"])
        roles = {d["id"]: (d["role"], d["projection"]) for d in self.context("TECH-001")["documents"]}
        self.assertEqual(roles["TECH-006"], ("advisory", "reference"))
        for purpose in ("implement", "verify"):
            with self.subTest(purpose=purpose):
                result = self.expand("TECH-001", purpose)
                self.assertEqual(result.draft_advisory, set())
                self.assertEqual(result.context_documents, ["REQ-001", "TECH-001"])

    def test_draft_refining_a_refiner_is_advisory_of_the_selected_refiner(self):
        self.build({
            ".spec/requirements/REQ-001.md": _req("REQ-001"),
            ".spec/technical/TECH-001.md": _tech("TECH-001", refines=["REQ-001"]),
            ".spec/technical/TECH-006.md": _tech("TECH-006", "draft", refines=["TECH-001"]),
        })
        result = self.expand("REQ-001", "interpret")
        self.assertEqual(result.draft_advisory, {"TECH-006"})
        self.assertEqual(result.document_distance["TECH-006"], 2)


class TaskRootTests(_Workspace):
    def shape(self) -> None:
        # TASK-002（done）はREQ-009を`addresses`する。TASK-001は、TASK-002を`requires`し、REQ-001:AC-01を`addresses`する。
        # REQ-001はREQ-004を`requires`し、TECH-002が`refines`する。REQ-009はREQ-008を`requires`する。TASK-003（open）もREQ-001:AC-01を`addresses`する。
        self.build({
            ".spec/requirements/REQ-001.md": _req("REQ-001", requires=["REQ-004"]),
            ".spec/requirements/REQ-004.md": _req("REQ-004"),
            ".spec/technical/TECH-002.md": _tech("TECH-002", refines=["REQ-001"], requires=["TECH-007"]),
            ".spec/technical/TECH-007.md": _tech("TECH-007"),
            ".spec/requirements/REQ-009.md": _req("REQ-009", requires=["REQ-008"]),
            ".spec/requirements/REQ-008.md": _req("REQ-008"),
            ".spec/tasks/TASK-002.md": _task("TASK-002", "done", addresses=["REQ-009:AC-01"]),
            ".spec/tasks/TASK-001.md": _task("TASK-001", "open", requires=["TASK-002"], addresses=["REQ-001:AC-01"]),
            ".spec/tasks/TASK-003.md": _task("TASK-003", "open", addresses=["REQ-001:AC-01"]),
        })

    def test_interpret_includes_addressed_owner_refiners_and_required_task_closure(self):
        self.shape()
        result = self.expand("TASK-001", "interpret")
        self.assertEqual(result.errors, [])
        self.assertEqual(
            result.context_documents,
            ["REQ-001", "REQ-004", "REQ-008", "REQ-009", "TASK-001", "TASK-002", "TECH-002", "TECH-007"],
        )
        self.assertEqual(
            result.document_distance,
            {"TASK-001": 0, "REQ-001": 1, "TASK-002": 1, "REQ-004": 2, "TECH-002": 2, "REQ-009": 2, "TECH-007": 3, "REQ-008": 3},
        )
        self.assertEqual(result.target_statements, [])
        roles = {d["id"]: d["role"] for d in self.context("TASK-001")["documents"]}
        self.assertEqual(roles["TASK-001"], "root")
        self.assertEqual(roles["TASK-002"], "work")
        self.assertEqual(roles["REQ-001"], "requirement")
        self.assertEqual(roles["TECH-002"], "refinement")
        self.assertNotIn("TASK-003", roles)

    def test_implement_adds_prerequisite_addressed_documents_without_targets_or_other_tasks(self):
        """先行TASKの`addresses`の参照先は`contextDocuments`に入るが、`targetStatements`には入らない。ほかの状態`open`のTASKは加えない。"""

        self.shape()
        result = self.expand("TASK-001", "implement")
        self.assertEqual(result.errors, [])
        self.assertIn("REQ-009", result.context_documents)
        self.assertIn("REQ-008", result.context_documents)
        self.assertNotIn("TASK-003", result.context_documents)
        self.assertNotIn("REQ-009:AC-01", result.target_statements)
        self.assertEqual(result.target_statements, ["REQ-001:AC-01"])  # TECH-002は規範文を持たない
        self.assertEqual(
            result.context_documents,
            ["REQ-001", "REQ-004", "REQ-008", "REQ-009", "TASK-001", "TASK-002", "TECH-002", "TECH-007"],
        )

    def test_verify_does_not_include_the_required_task_range_but_checks_its_applicability(self):
        """`verify`は起点の`requires`の上方向の範囲をコンテキストへ含めない。その範囲の文書（TASKとADRを除く）の適用可能性は検査する。"""

        self.shape()
        result = self.expand("TASK-001", "verify")
        self.assertEqual(result.errors, [])
        self.assertEqual(result.context_documents, ["REQ-001", "REQ-004", "TASK-001", "TECH-002", "TECH-007"])
        self.assertEqual(sorted(result.traversed_documents), ["REQ-001", "REQ-004", "REQ-008", "REQ-009", "TASK-001", "TASK-002", "TECH-002", "TECH-007"])
        for bad, relations in (("REQ-009", {"requires": ["REQ-008"]}), ("REQ-008", {})):
            with self.subTest(document=bad):
                self.shape()
                _write(self.root, f".spec/requirements/{bad}.md", _req(bad, "outdated", **relations))
                catalog = doc_mod.build_catalog(self.root, WORKSPACE_ID)
                self.id_index = rel_mod.build_id_index(catalog.entries)
                self.statement_index = rel_mod.build_statement_index(catalog.entries)
                blocked = self.expand("TASK-001", "verify")
                self.assertEqual([(e["code"], e["resultStatus"], e["doc_id"]) for e in blocked.errors], [("CTX-STATE-001", "blocked", bad)])
                self.assertNotIn(bad, blocked.context_documents)

    def test_verify_checks_requires_type_constraints_in_the_required_task_range(self):
        """範囲の文書が`requires`する状態が`accepted`でないADRは、`CTX-RELATION-TYPE-001`を返す。"""

        self.shape()
        _write(self.root, ".spec/requirements/REQ-008.md", _req("REQ-008", requires=["ADR-001"]))
        _write(self.root, ".spec/decisions/ADR-001.md", _adr("ADR-001", "proposed"))
        catalog = doc_mod.build_catalog(self.root, WORKSPACE_ID)
        self.id_index = rel_mod.build_id_index(catalog.entries)
        self.statement_index = rel_mod.build_statement_index(catalog.entries)
        result = self.expand("TASK-001", "verify")
        self.assertEqual([(e["code"], e["doc_id"]) for e in result.errors], [("CTX-RELATION-TYPE-001", "REQ-008")])

    def test_verify_of_the_addressed_owner_does_not_walk_downward_from_upward_documents(self):
        """TASK起点でも、下方向へ辿るのは`addresses`の参照先の所有文書からだけである。上方向のREQ-004を`refines`する文書は含めない。"""

        self.shape()
        _write(self.root, ".spec/technical/TECH-020.md", _tech("TECH-020", refines=["REQ-004"]))
        catalog = doc_mod.build_catalog(self.root, WORKSPACE_ID)
        self.id_index = rel_mod.build_id_index(catalog.entries)
        self.statement_index = rel_mod.build_statement_index(catalog.entries)
        for purpose in PURPOSES:
            with self.subTest(purpose=purpose):
                self.assertNotIn("TECH-020", self.expand("TASK-001", purpose).context_documents)


class DeterminismTests(_Workspace):
    def test_two_runs_give_the_same_order(self):
        self.build({
            ".spec/requirements/REQ-001.md": _req("REQ-001"),
            ".spec/requirements/REQ-002.md": _req("REQ-002", requires=["REQ-003"]),
            ".spec/requirements/REQ-003.md": _req("REQ-003"),
            ".spec/technical/TECH-010.md": _tech("TECH-010", refines=["REQ-001", "REQ-002"]),
            ".spec/technical/TECH-011.md": _tech("TECH-011", refines=["REQ-001"]),
        })
        first = self.expand("REQ-001", "interpret")
        second = self.expand("REQ-001", "interpret")
        self.assertEqual(first.context_documents, second.context_documents)
        self.assertEqual(first.document_distance, second.document_distance)
        self.assertEqual(first.document_edges, second.document_edges)


if __name__ == "__main__":
    unittest.main()
