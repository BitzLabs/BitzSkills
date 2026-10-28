"""不正な証拠を黙って受理しないことを確認する回帰試験。"""
import json
import copy
import os
import re
from pathlib import Path
import subprocess
import sys
import tempfile
import shutil
import unittest
from unittest.mock import patch

from jsonschema import Draft202012Validator, ValidationError

import validate_conformance as audit
from conformance.schemas import schema_path
import certify_gate_a as certify
from conformance import step_assignment
from conformance.diagnostic_coverage import LEDGER, validate
from conformance.target_vectors import HERE as TARGET_HERE, validate as validate_targets
from conformance.initial_fixtures import validate as validate_initial, compare_state, check_command_preconditions
from conformance.ears_fixtures import validate as validate_ears
from conformance.document_fixtures import validate as validate_documents
from conformance.trace_fixtures import validate as validate_trace
from conformance.graph_fixtures import validate as validate_graph
from conformance.git_fixtures import validate as validate_git_fixtures, check_git_states, reviewed_manifest as git_manifest
from conformance.harness import setup as fixture_setup, git as fixture_git
from conformance.task_fixtures import validate as validate_tasks, check_git_states as check_task_git_states, reviewed_manifest as task_manifest
from conformance.selection_fixtures import validate as validate_selection, check_git_states as check_selection_git_states, reviewed_manifest as selection_manifest
from conformance.git_environment_fixtures import (validate as validate_git_environment,
    check_cli_error_output,
    check_environment, reviewed_manifest as environment_manifest)
from conformance.context_failure_fixtures import (validate as validate_context_failures,
    check_unborn as check_context_unborn, reviewed_manifest as context_failure_manifest)
from conformance import digest_crosscheck, digest_reference
from conformance import context_failure_fixtures
from conformance.digest_fixtures import validate as validate_digest
from conformance import context_limit_fixtures
from conformance.context_limit_fixtures import validate as validate_context_limits
from conformance import context_coverage_fixtures, projection_limit_fixtures
from conformance.context_coverage_fixtures import validate as validate_context_coverage
from conformance.projection_limit_fixtures import validate as validate_projection_limit
from conformance import verify_fixtures
from conformance.verify_fixtures import validate as validate_verify
from conformance import verify_binding_fixtures
from conformance.verify_binding_fixtures import validate as validate_verify_bindings
from conformance import verify_process_fixtures
from conformance.verify_process_fixtures import validate as validate_verify_process
from conformance import verify_output_fixtures
from conformance.verify_output_fixtures import validate as validate_verify_output
from conformance import verify_document_fixtures
from conformance.verify_document_fixtures import validate as validate_verify_document
from conformance import verify_task_root_fixtures
from conformance.verify_task_root_fixtures import validate as validate_verify_task_root
from conformance import cli_error_fixtures, report_absent_fixtures
from conformance.report_absent_fixtures import validate as validate_report_absent
from conformance.cli_error_fixtures import validate as validate_cli_errors
from conformance import report_write_fixtures
from conformance.report_write_fixtures import validate as validate_report_write
from conformance import text_fixtures
from conformance import frontmatter_fixtures
from conformance import input_limit_fixtures
from conformance import registry_closure_fixtures
from conformance import context_config_fixtures
from conformance import digest_command_fixtures
from conformance import verify_task_tech_fixtures
from conformance import scanner_fixtures
from conformance import presentation_fixtures
from conformance import target_root_fixtures
from conformance import expansion_fixtures
from conformance import ordering_fixtures
from conformance import environment_fixtures
from conformance import target_vectors
from conformance import multi_catalog_fixtures, multi_digest_fixtures, multi_doctor_fixtures, multi_identity_fixtures
from conformance import multi_member_fixtures, multi_ownership_fixtures, multi_reference
from conformance import multi_verify_fixtures, multi_report_fixtures, multi_compat_fixtures
from conformance import multi_generator, multi_limit_fixtures, multi_relation_type_fixtures, multi_check_fixtures
from conformance import multi_crosscheck, repo_root_fixtures, multi_workspace_option_fixtures
from conformance import multi_active_workspace_fixtures, multi_single_precheck_fixtures, multi_exclude_fixtures
from conformance import multi_closure_alias_fixtures, multi_binding_missing_fixtures, multi_doctor_git_fixtures
from conformance import multi_single_verify_limit_fixtures
from conformance import doctor_plugin_fixtures
from conformance import verify_stop_revision_fixtures
from conformance import context_stop_revision_fixtures
from conformance import multi_context_order_fixtures
from conformance import multi_qualified_summary_fixtures
from conformance import multi_null_declaration_fixtures
from conformance import multi_null_base_fixtures
from conformance import multi_verify_order_fixtures
from conformance import multi_early_report_fixtures
from conformance import multi_workspace_id_fixtures
from conformance import multi_self_qualified_covers_fixtures


class AuditTests(unittest.TestCase):
    def test_target_root_fixtures(self):
        result = target_root_fixtures.validate()
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["prepared"], list(target_root_fixtures.CASES))
        self.assertEqual(result["core_execution"], "Not run")

    def test_target_root_audit_rejects_substituted_roots(self):
        mutations = [
            # 不在の起点を終了コード4や既知文書の`check`へ置き換えない。
            ("SINGLE-111-01", "expected/check.json", lambda v: v.update(checkedDocumentCount=1)),
            ("SINGLE-111-02", "expected/check.json",
             lambda v: v["diagnostics"][0]["source"].update(argument="REQ-001")),
            ("SINGLE-111-03", "manifest.json", lambda v: v["expect"].update(exitCode=4)),
            ("SINGLE-111-04", "expected/verify.json",
             lambda v: v["targetResults"][0].update(bindingRefs=["root::default"])),
            ("SINGLE-111-04", "expected/verify.json",
             lambda v: v["targetResults"][0].update(diagnostics=[])),
            # ADRの起点はテスト義務へ展開せず、ハッシュ値の材料もADRだけである。
            ("SINGLE-112-01", "expected/context.json",
             lambda v: v["constraintLedger"]["statements"].append({"id": "REQ-001:AC-01"})),
            ("SINGLE-112-01", "expected/context.json",
             lambda v: v.update(contextDigest="sha256:" + "0" * 64)),
            ("SINGLE-112-03", "expected/check.json", lambda v: v.update(checkedStatementCount=1)),
            ("SINGLE-112-03", "manifest.json", lambda v: v["setup"].pop("baseCommit")),
        ]
        for identifier, relative, mutate in mutations:
            with self.subTest(identifier=identifier, relative=relative), \
                    tempfile.TemporaryDirectory() as temporary:
                root = self.copy_fixture(temporary, identifier)
                shutil.copy2(schema_path(audit.FIXTURES, "frontmatter"), root)
                path = root / "single" / identifier / relative
                value = json.loads(path.read_text())
                mutate(value)
                path.write_text(json.dumps(value))
                result = target_root_fixtures.validate(root, {identifier})
                self.assertEqual(result["status"], "Failed")

    def test_expansion_fixtures(self):
        result = expansion_fixtures.validate()
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["prepared"], list(expansion_fixtures.CASES))
        self.assertEqual(result["core_execution"], "Not run")

    def test_expansion_audit_rejects_changed_sets_and_roles(self):
        def document(index, **changes):
            return lambda v: v["documents"][index].update(changes)

        def as_normative(entry):
            entry["projection"] = "normative"
            del entry["frontmatter"], entry["bodyText"]

        def swap_documents(first, second):
            def mutate(value):
                documents = value["documents"]
                documents[first], documents[second] = documents[second], documents[first]
            return mutate
        mutations = [
            # `requires`先の役割は種別で決まり、REQは役割`requirement`、TECHは役割`constraint`である。
            ("SINGLE-107-01", "expected/context.json", document(1, role="constraint")),
            ("SINGLE-108-01", "expected/context.json", document(2, role="requirement")),
            # 距離2の具体化文書は`normative`で提示する。
            ("SINGLE-107-01", "expected/context.json", document(3, projection="full")),
            # `advisory`は`reference`だけで提示し、本文や`statementRefs`を持たない。
            ("SINGLE-106-03", "expected/context.json", document(1, statementRefs=["TECH-005:AC-01"])),
            ("SINGLE-106-03", "expected/context.json",
             lambda v: v["constraintLedger"]["statements"].append({"id": "TECH-005:AC-01"})),
            # `statementRefs`は所有する全規範文、兄弟句は`adjacent`だけに置く。
            ("SINGLE-109", "expected/context.json", document(0, statementRefs=["REQ-001:AC-01"])),
            ("SINGLE-109", "expected/context.json", lambda v: v["coverage"].update(adjacent=[])),
            ("SINGLE-109", "expected/context.json",
             lambda v: v["coverage"]["must"]["total"].append("REQ-001:AC-02")),
            # `verify`の起点TASKは`requires`先のTASKをコンテキストへ含めない。
            ("SINGLE-110", "expected/context.json",
             lambda v: v["documents"].append(dict(v["documents"][0], id="TASK-002", role="work",
                                                  reachedBy=["requires:TASK-001"]))),
            # 目的`implement`の起点TASKは、先行TASKがすべて`done`なら止まらない。先行TASKを閉包から落とさず、
            # `CTX-STATE-001`や`CTX-TASK-DEPENDENCY-001`で`blocked`にしない。
            ("SINGLE-134", "expected/context.json", lambda v: v["documents"].pop()),
            ("SINGLE-134", "expected/context.json",
             lambda v: v["diagnostics"][0].update(code="CTX-STATE-001", resultStatus="blocked", severity="error")),
            ("SINGLE-134", "expected/context.json", lambda v: v.update(status="blocked")),
            ("SINGLE-134", "manifest.json", lambda v: v["expect"].update(status="passed")),
            ("SINGLE-134", "expected/context.json",
             lambda v: v["coverage"]["must"].update(tested=["REQ-001:AC-01"], untested=[])),
            # 目的`implement`の起点TASKは、直接の先行TASKが`done`なら、`requires`の閉包で推移的に到達した`cancelled`のTASKの
            # 状態を検査しない（関係・トレースモデル §6.2）。推移的なTASKを閉包から落とさず、`CTX-STATE-001`で`blocked`にしない。
            ("SINGLE-145", "expected/context.json", lambda v: v["documents"].pop()),
            ("SINGLE-145", "expected/context.json", lambda v: v["documents"].pop(2)),
            ("SINGLE-145", "expected/context.json", document(3, role="advisory")),
            ("SINGLE-145", "expected/context.json", document(3, status="done")),
            ("SINGLE-145", "expected/context.json", document(3, reachedBy=["requires:TASK-001"])),
            ("SINGLE-145", "expected/context.json", swap_documents(2, 3)),
            ("SINGLE-145", "expected/context.json",
             lambda v: v["diagnostics"].append(dict(v["diagnostics"][0], code="CTX-STATE-001", severity="error",
                                                    resultStatus="blocked"))),
            ("SINGLE-145", "expected/context.json",
             lambda v: v["diagnostics"].__setitem__(0, dict(v["diagnostics"][0], code="CTX-TASK-DEPENDENCY-001",
                                                            severity="error", resultStatus="blocked"))),
            ("SINGLE-145", "expected/context.json", lambda v: v.update(status="blocked")),
            ("SINGLE-145", "expected/context.json", lambda v: v.update(status="passed")),
            ("SINGLE-145", "manifest.json", lambda v: v["expect"].update(status="blocked", exitCode=2)),
            ("SINGLE-145", "manifest.json", lambda v: v["expect"].update(status="passed")),
            # 制約台帳にない規範文を持つ具体化文書は、距離によらず提示形式`full`で提示し、`MUST`の本文を落とさない
            # （`bitz context`仕様 §5、ADR-014の`Decision`の4番目の項目）。`normative`への変更、役割の取り違え、
            # 対象規範文でない規範文の制約台帳への昇格を拒否する。
            ("SINGLE-135", "expected/context.json", lambda v: as_normative(v["documents"][2])),
            ("SINGLE-135", "expected/context.json", document(2, role="requirement")),
            ("SINGLE-135", "expected/context.json", document(2, reachedBy=["requires:REQ-002"])),
            ("SINGLE-135", "expected/context.json",
             lambda v: v["constraintLedger"]["statements"].append({"id": "REQ-003:AC-01"})),
            ("SINGLE-135", "manifest.json", lambda v: v["expect"].update(status="passed")),
            ("SINGLE-136", "expected/context.json", lambda v: as_normative(v["documents"][2])),
            ("SINGLE-136", "expected/context.json", document(2, role="constraint")),
            ("SINGLE-136", "expected/context.json",
             lambda v: v["constraintLedger"]["statements"].append({"id": "TECH-003:AC-01"})),
            # 文書の距離は、閉包を作るときに辿ったエッジによる最短の段数である（関係・トレースモデル §7の6.）。
            # 並び順の入替え、提示形式`normative`の`full`への改変、役割の取り違え、後継の`reachedBy`の取り違えを拒否する。
            ("SINGLE-139", "expected/context.json", swap_documents(1, 2)),
            ("SINGLE-139", "expected/context.json", document(1, role="requirement")),
            ("SINGLE-139", "expected/context.json", document(2, role="refinement")),
            ("SINGLE-139", "expected/context.json", document(1, reachedBy=["refines:REQ-001"])),
            ("SINGLE-140", "expected/context.json",
             lambda v: v["documents"].__setitem__(2, expansion_fixtures.bundle_document(
                 "SINGLE-140", "TECH-002", "refinement", "full", ["refines:TECH-002"]))),
            ("SINGLE-140", "expected/context.json",
             lambda v: v["documents"].__setitem__(3, expansion_fixtures.bundle_document(
                 "SINGLE-140", "TECH-003", "refinement", "full", ["refines:TECH-003"]))),
            ("SINGLE-140", "expected/context.json", swap_documents(1, 2)),
            ("SINGLE-140", "expected/context.json", swap_documents(2, 3)),
            ("SINGLE-140", "expected/context.json", document(1, role="work")),
            ("SINGLE-140", "expected/context.json", lambda v: v["constraintLedger"]["statements"].pop()),
            ("SINGLE-140", "expected/context.json", lambda v: v["diagnostics"].pop()),
            ("SINGLE-140", "manifest.json", lambda v: v["expect"].update(status="passed")),
            ("SINGLE-141", "expected/context.json", swap_documents(1, 2)),
            ("SINGLE-141", "expected/context.json", swap_documents(0, 1)),
            ("SINGLE-141", "expected/context.json", document(2, role="constraint")),
            ("SINGLE-141", "expected/context.json", document(0, role="root")),
            ("SINGLE-141", "expected/context.json", document(2, reachedBy=["supersedes:TECH-005"])),
            # 目的`implement`と`verify`は、`refines`する状態`draft`の文書を閉包へ含めない（関係・トレースモデル §6.1の末尾）。
            # `draft`の文書の追加、そのテスト対応のテスト済みへの計上、状態の`blocked`への改変、診断の欠落を拒否する。
            ("SINGLE-142", "expected/context.json",
             lambda v: v["documents"].append(expansion_fixtures.bundle_document(
                 "SINGLE-142", "TECH-005", "advisory", "reference", ["refines:TECH-005"]))),
            ("SINGLE-142", "expected/context.json",
             lambda v: v["coverage"]["must"].update(tested=["REQ-001:AC-01"], untested=[])),
            ("SINGLE-142", "expected/context.json", lambda v: v["diagnostics"].pop()),
            ("SINGLE-142", "expected/context.json", lambda v: v["diagnostics"].reverse()),
            ("SINGLE-142", "expected/context.json",
             lambda v: v["constraintLedger"]["statements"].append({"id": "TECH-005:AC-01"})),
            ("SINGLE-142", "manifest.json", lambda v: v["expect"].update(status="passed")),
            ("SINGLE-142", "manifest.json", lambda v: v["invocation"]["argv"].__setitem__(3, "interpret")),
            ("SINGLE-143", "expected/verify.json",
             lambda v: v["commands"][0]["tests"].append("tests/test_candidate.py")),
            ("SINGLE-143", "expected/verify.json",
             lambda v: v["targetResults"][0].update(status="blocked", contextDigest=None)),
            ("SINGLE-143", "expected/verify.json",
             lambda v: v["targetResults"][0].update(contextDigest="sha256:" + "0" * 64)),
            ("SINGLE-143", "expected/verify.json",
             lambda v: v["targetResults"][0]["statements"].append("TECH-005:AC-01")),
            ("SINGLE-143", "manifest.json", lambda v: v["expect"].update(status="blocked", exitCode=2)),
            # `verify`は`context`と同じ対象の集合とハッシュ値を使う。
            ("SINGLE-107-02", "expected/verify.json",
             lambda v: v["targetResults"][0]["statements"].pop()),
            ("SINGLE-108-02", "expected/verify.json",
             lambda v: v["targetResults"][0].update(contextDigest="sha256:" + "0" * 64)),
            ("SINGLE-113", "expected/verify.json", lambda v: v["targetResults"].pop()),
            ("SINGLE-113", "expected/verify.json",
             lambda v: v["commands"][0]["tests"].append("tests/test_root.py")),
        ]
        for identifier, relative, mutate in mutations:
            with self.subTest(identifier=identifier, relative=relative), \
                    tempfile.TemporaryDirectory() as temporary:
                root = self.copy_fixture(temporary, identifier)
                for source in ("SINGLE-107-01", "SINGLE-108-01"):
                    if not (root / "single" / source).exists():
                        shutil.copytree(audit.FIXTURES / "single" / source, root / "single" / source)
                shutil.copy2(schema_path(audit.FIXTURES, "frontmatter"), root)
                path = root / "single" / identifier / relative
                value = json.loads(path.read_text())
                mutate(value)
                path.write_text(json.dumps(value))
                result = expansion_fixtures.validate(root, {identifier})
                self.assertEqual(result["status"], "Failed")

    def test_expansion_contract_rejects_normative_without_ledger(self):
        """完全比較とは別に、`check_contract`だけが、制約台帳にない規範文を持つ文書の`normative`を拒否する。"""
        for identifier, index in (("SINGLE-135", 2), ("SINGLE-136", 2)):
            path = audit.FIXTURES / "single" / identifier / "expected/context.json"
            with self.subTest(identifier=identifier):
                value = json.loads(path.read_text())
                expansion_fixtures.check_contract(identifier, value, audit.FIXTURES)
                entry = value["documents"][index]
                entry["projection"] = "normative"
                del entry["frontmatter"], entry["bodyText"]
                with self.assertRaises(ValueError):
                    expansion_fixtures.check_contract(identifier, value, audit.FIXTURES)

    def test_expansion_contract_rejects_changed_distance_order_and_roles(self):
        """完全比較とは別に、`check_contract`だけが、距離に基づく並び、提示形式、役割の改変を拒否する。"""
        def swap(first, second):
            def mutate(value):
                documents = value["documents"]
                documents[first], documents[second] = documents[second], documents[first]
            return mutate

        def projection(index, name, role, reached):
            return lambda v: v["documents"].__setitem__(index, expansion_fixtures.bundle_document(
                "SINGLE-140", name, role, "full", reached))
        changes = [
            ("SINGLE-139", swap(1, 2)),
            ("SINGLE-139", lambda v: v["documents"][1].update(role="requirement")),
            ("SINGLE-140", swap(2, 3)),
            ("SINGLE-140", projection(2, "TECH-002", "refinement", ["refines:TECH-002"])),
            ("SINGLE-140", projection(3, "TECH-003", "refinement", ["refines:TECH-003"])),
            ("SINGLE-141", swap(1, 2)),
            ("SINGLE-141", lambda v: v["documents"][2].update(role="constraint")),
        ]
        for identifier, mutate in changes:
            path = audit.FIXTURES / "single" / identifier / "expected/context.json"
            with self.subTest(identifier=identifier, mutation=mutate.__qualname__):
                value = json.loads(path.read_text())
                expansion_fixtures.check_contract(identifier, value, audit.FIXTURES)
                mutate(value)
                with self.assertRaises(ValueError):
                    expansion_fixtures.check_contract(identifier, value, audit.FIXTURES)

    def test_expansion_contract_rejects_state_checks_of_transitive_tasks(self):
        """完全比較とは別に、`check_contract`だけが、推移的に到達した`cancelled`のTASKの状態の診断と、その`blocked`、
        閉包からの除外を拒否する（`SINGLE-145`、関係・トレースモデル §6.2）。"""
        state = {"code": "CTX-STATE-001", "severity": "error", "resultStatus": "blocked",
                 "summary": "TASK-003は状態cancelledのため目的implementに適用できません",
                 "source": {"kind": "file", "workspaceId": "root", "path": ".spec/tasks/TASK-003.md"}}
        dependency = {"code": "CTX-TASK-DEPENDENCY-001", "severity": "error", "resultStatus": "blocked",
                      "summary": "先行するTASK-003が状態cancelledで、状態doneではありません",
                      "source": {"kind": "file", "workspaceId": "root", "path": ".spec/tasks/TASK-002.md",
                                 "key": "relations.requires"}}

        def replaced(diagnostic):
            return lambda v: v.update(status="blocked", diagnostics=[diagnostic])

        changes = [
            lambda v: v["diagnostics"].append(state),
            lambda v: v["diagnostics"].append(dependency),
            replaced(state),
            replaced(dependency),
            lambda v: v.update(diagnostics=[]),
            lambda v: v["documents"].pop(),
            lambda v: v["documents"][3].update(role="advisory"),
        ]
        path = audit.FIXTURES / "single/SINGLE-145/expected/context.json"
        for index, mutate in enumerate(changes):
            with self.subTest(index=index):
                value = json.loads(path.read_text())
                expansion_fixtures.check_contract("SINGLE-145", value, audit.FIXTURES)
                mutate(value)
                with self.assertRaises(ValueError):
                    expansion_fixtures.check_contract("SINGLE-145", value, audit.FIXTURES)

    def test_expansion_contract_rejects_draft_documents_in_implement_and_verify(self):
        """完全比較とは別に、`check_contract`だけが、目的`implement`と`verify`の結果に現れる、`refines`する
        状態`draft`の文書、そのテスト対応の計上、状態を理由とした`blocked`を拒否する。"""
        blocked = {"code": "CTX-STATE-001", "severity": "error", "resultStatus": "blocked",
                   "summary": "TECH-005が適用できません",
                   "source": {"kind": "file", "workspaceId": "root", "path": ".spec/technical/TECH-005.md"}}

        def advisory(value):
            value["documents"].append(expansion_fixtures.bundle_document(
                "SINGLE-142", "TECH-005", "advisory", "reference", ["refines:TECH-005"]))
            value["resolution"]["documentCount"] = 2

        def counted(value):
            value["coverage"]["must"].update(tested=["REQ-001:AC-01"], untested=[])

        def one_diagnostic(value):
            value["diagnostics"].pop()

        def candidate_test(value):
            value["commands"][0]["tests"].append("tests/test_candidate.py")
            value["commands"][0]["argv"].append("tests/test_candidate.py")

        def blocked_target(value):
            value["status"] = "blocked"
            value["targetResults"][0].update(status="blocked", contextDigest=None, statements=[], bindingRefs=[],
                                             diagnostics=[blocked])
            value["commands"] = []

        def state_only(value):
            value["targetResults"][0]["diagnostics"] = [blocked]
        changes = [
            ("SINGLE-142", "context", advisory),
            ("SINGLE-142", "context", counted),
            ("SINGLE-142", "context", one_diagnostic),
            ("SINGLE-143", "verify", candidate_test),
            ("SINGLE-143", "verify", blocked_target),
            ("SINGLE-143", "verify", state_only),
        ]
        for identifier, operation, mutate in changes:
            path = audit.FIXTURES / "single" / identifier / f"expected/{operation}.json"
            with self.subTest(identifier=identifier, mutation=mutate.__qualname__):
                value = json.loads(path.read_text())
                expansion_fixtures.check_contract(identifier, value, audit.FIXTURES)
                mutate(value)
                with self.assertRaises(ValueError):
                    expansion_fixtures.check_contract(identifier, value, audit.FIXTURES)

    def test_distance_reference_orders_by_the_shortest_path(self):
        """参照計算Bの閉包は、辿ったエッジによる最短の段数、種別、IDの順に文書を並べる。
        陽性対照（3件のfixture）と、経路や関係を変えて並びが変わる陰性対照を置く。"""
        def load(identifier):
            documents = digest_crosscheck.load_documents(audit.FIXTURES / "single" / identifier / "repo")
            return copy.deepcopy(documents)

        def ordered(documents, root, purpose):
            return digest_crosscheck.closure(documents, root, purpose)[0]
        # 139: REQ-002は`refines`の1段と`requires`の2段で到達し、距離は最短の1。
        documents = load("SINGLE-139")
        self.assertEqual(ordered(documents, "REQ-001", "interpret"), ["REQ-001", "REQ-002", "REQ-003"])
        # `refines`を外すと、REQ-002は`requires`の2段だけになり、距離が2になって並びが変わる。
        documents["REQ-001"]["frontmatter"]["relations"].pop("refines")
        self.assertEqual(ordered(documents, "REQ-001", "interpret"), ["REQ-001", "REQ-003", "REQ-002"])
        # 140: 具体化の鎖は距離が1段ずつ増える。
        documents = load("SINGLE-140")
        self.assertEqual(ordered(documents, "TASK-001", "implement"), ["TASK-001", "REQ-001", "TECH-002", "TECH-003"])
        # 141: 後継は距離1で、起点の`requires`の参照先とIDの順に並び、役割`replacement`になる。
        documents = load("SINGLE-141")
        selected, advisory, replacement = digest_crosscheck._closure(documents, "TECH-005", "interpret")
        self.assertEqual((selected, advisory, replacement),
                         (["TECH-005", "TECH-007", "TECH-009"], {"TECH-005"}, {"TECH-009"}))
        # 後継のIDを起点の前提より前にしても、距離1の2件はIDの順に並ぶ。
        documents["TECH-001"] = copy.deepcopy(documents.pop("TECH-009"))
        documents["TECH-001"]["frontmatter"]["id"] = "TECH-001"
        selected, advisory, replacement = digest_crosscheck._closure(documents, "TECH-005", "interpret")
        self.assertEqual((selected, replacement), (["TECH-005", "TECH-001", "TECH-007"], {"TECH-001"}))
        # `supersedes`されていない起点は、置換済みとして扱わない。
        documents = load("SINGLE-141")
        documents["TECH-009"]["frontmatter"]["relations"].pop("supersedes")
        selected, advisory, replacement = digest_crosscheck._closure(documents, "TECH-005", "interpret")
        self.assertEqual((selected, advisory, replacement), (["TECH-005", "TECH-007"], set(), set()))
        # 後継が複数ある起点は、参照計算Bの対象外として拒否する（`CTX-STATE-SUPERSEDED-002`の場面）。
        documents = load("SINGLE-141")
        documents["TECH-010"] = copy.deepcopy(documents["TECH-009"])
        documents["TECH-010"]["frontmatter"]["id"] = "TECH-010"
        with self.assertRaisesRegex(ValueError, "有効な後継が複数"):
            digest_crosscheck._closure(documents, "TECH-005", "interpret")

    def test_reference_closure_excludes_draft_refinements_unless_interpret(self):
        """参照計算Bは、`refines`する状態`draft`の文書を、目的`interpret`だけで役割`advisory`として含め、
        `implement`と`verify`では閉包へ含めない（関係・トレースモデル §6.1の末尾）。陽性対照と陰性対照を置く。"""
        def load(identifier):
            return copy.deepcopy(digest_crosscheck.load_documents(audit.FIXTURES / "single" / identifier / "repo"))
        documents = load("SINGLE-142")
        self.assertEqual(digest_crosscheck.closure(documents, "REQ-001", "interpret"),
                         (["REQ-001", "TECH-005"], {"TECH-005"}))
        self.assertEqual(digest_crosscheck.closure(documents, "REQ-001", "implement"), (["REQ-001"], set()))
        self.assertEqual(digest_crosscheck.closure(documents, "REQ-001", "verify"), (["REQ-001"], set()))
        documents = load("SINGLE-143")
        self.assertEqual(digest_crosscheck.closure(documents, "TASK-001", "verify"),
                         (["TASK-001", "REQ-001"], set()))
        # 状態を`approved`にすると、具体化する適用可能な文書として、目的を問わず閉包へ含める。
        documents["TECH-005"]["frontmatter"]["status"] = "approved"
        self.assertEqual(digest_crosscheck.closure(documents, "TASK-001", "verify")[0],
                         ["TASK-001", "REQ-001", "TECH-005"])
        # 状態`draft`以外の適用可能でない文書（`rejected`）は、黙って捨てず、閉包の外の強いエッジとして拒否する。
        documents["TECH-005"]["frontmatter"]["status"] = "rejected"
        with self.assertRaisesRegex(ValueError, "閉包の外の強いエッジ"):
            digest_crosscheck.closure(documents, "TASK-001", "verify")

    def test_ordering_fixtures(self):
        result = ordering_fixtures.validate()
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["prepared"], list(ordering_fixtures.CASES))

    def test_ordering_audit_rejects_declared_order_and_converted_separators(self):
        def canonical(transform):
            def mutate(raw):
                value = json.loads(raw.decode())
                transform(value)
                return digest_reference.canonical_bytes(value)
            return mutate
        mutations = [
            # 宣言順のままでは完全順序にならない。
            ("SINGLE-122", "expected/context.canonical.json",
             canonical(lambda v: v["documents"][1]["frontmatter"]["tests"].reverse())),
            ("SINGLE-123", "expected/context.canonical.json",
             canonical(lambda v: v["documents"][0]["statements"][0]["extensions"].reverse())),
            # パスの型以外のバックスラッシュをスラッシュへ変換しない。
            ("SINGLE-124", "expected/context.canonical.json",
             lambda raw: raw.replace(b"src\\\\auth", b"src/auth")),
            ("SINGLE-123", "expected/context.json",
             lambda raw: json.dumps(dict(json.loads(raw), diagnostics=json.loads(raw)["diagnostics"][:1])).encode()),
        ]
        for identifier, relative, mutate in mutations:
            with self.subTest(identifier=identifier, relative=relative), \
                    tempfile.TemporaryDirectory() as temporary:
                root = self.copy_fixture(temporary, identifier)
                shutil.copy2(schema_path(audit.FIXTURES, "frontmatter"), root)
                path = root / "single" / identifier / relative
                before = path.read_bytes()
                path.write_bytes(mutate(before))
                self.assertNotEqual(path.read_bytes(), before)
                result = ordering_fixtures.validate(root, {identifier})
                self.assertEqual(result["status"], "Failed")

    def test_reference_b_resolves_omitted_command_and_sorts_extensions(self):
        statement = {"extensions": [{"namespace": "q", "term": "L", "value": "b"},
                                    {"namespace": "q", "term": "L", "value": None}]}
        self.assertEqual([e["value"] for e in digest_crosscheck._sorted_extensions(statement)["extensions"]],
                         [None, "b"])
        payload = json.loads(ordering_fixtures.canonical("SINGLE-122").decode())
        self.assertEqual([c["name"] for c in payload["settings"]["commands"]], ["default", "other"])

    def test_environment_fixtures(self):
        result = environment_fixtures.validate()
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["prepared"], list(environment_fixtures.CASES))

    def test_environment_audit_rejects_wrong_versions_and_mixed_causes(self):
        mutations = [
            # 下限未満は下限の直前、下限は同じ版でなければならない。
            ("SINGLE-127-15", "manifest.json", lambda v: v["invocation"].update(gitVersion="2.30.0")),
            ("SINGLE-127-16", "manifest.json", lambda v: v["invocation"].update(gitVersion="2.31.0")),
            ("SINGLE-127-15", "expected/doctor.json", lambda v: v.update(diagnostics=[])),
            ("SINGLE-127-15", "expected/doctor.json", lambda v: v["diagnostics"][0].pop("suggestedAction")),
            ("SINGLE-127-19", "manifest.json", lambda v: v["invocation"].update(python="3.13")),
            ("SINGLE-127-17", "expected/package.json", lambda v: v.update(outcome="rejected")),
            ("SINGLE-127-18", "manifest.json", lambda v: v["invocation"].update(argv=["metadata"])),
        ]
        for identifier, relative, mutate in mutations:
            with self.subTest(identifier=identifier, relative=relative), \
                    tempfile.TemporaryDirectory() as temporary:
                root = self.copy_fixture(temporary, identifier)
                path = root / "single" / identifier / relative
                value = json.loads(path.read_text())
                mutate(value)
                path.write_text(json.dumps(value))
                result = environment_fixtures.validate(root, {identifier})
                self.assertEqual(result["status"], "Failed")

    def test_manifest_schema_limits_harness_fields(self):
        validator = Draft202012Validator(json.loads((audit.FIXTURES / "manifest.schema.json").read_text()))
        base = json.loads((audit.FIXTURES / "single/SINGLE-127-15/manifest.json").read_text())
        validator.validate(base)
        invalid = [
            dict(base, invocation=dict(base["invocation"], env={"PATH": "/usr/bin"})),
            dict(base, invocation=dict(base["invocation"], gitVersion="2.30")),
            dict(base, invocation=dict(base["invocation"], python="3.11.4")),
        ]
        package = json.loads((audit.FIXTURES / "single/SINGLE-127-17/manifest.json").read_text())
        validator.validate(package)
        invalid.append(dict(package, invocation=dict(package["invocation"], python="3.11")))
        for manifest in invalid:
            with self.subTest(invocation=manifest["invocation"]):
                self.assertFalse(validator.is_valid(manifest))

    def test_verify_task_root_does_not_follow_requires(self):
        """関係・トレースモデル §6.3: `verify`だけが起点TASKの`requires`先を辿らない。"""
        data = json.loads((target_vectors.HERE / "targets/cases.json").read_text())
        case = next(c for c in data["cases"] if c["id"] == "TASK-REQUIRES-NOT-TARGET")
        self.assertEqual(target_vectors.reference(case)["contextDocuments"], ["TASK-001", "REQ-001"])
        implement = dict(case, purpose="implement")
        self.assertIn("TASK-002", target_vectors.reference(implement)["contextDocuments"])

    def test_target_root_audit_rejects_adr_reference_in_corpus(self):
        original = target_root_fixtures.reviewed_inputs

        def with_reference(identifier):
            inputs = original(identifier)
            if identifier.startswith("SINGLE-112"):
                inputs[".spec/technical/TECH-001.md"] = b"related: [ADR-001]\n"
            return inputs
        with patch.object(target_root_fixtures, "reviewed_inputs", with_reference):
            result = target_root_fixtures.validate(identifiers={"SINGLE-112-03"})
        self.assertEqual(result["status"], "Failed")

    def test_presentation_fixtures(self):
        result = presentation_fixtures.validate()
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["prepared"], list(presentation_fixtures.CASES))
        self.assertEqual(result["core_execution"], "Not run")

    def test_presentation_audit_rejects_text_and_revision_mismatches(self):
        mutations = [
            ("SINGLE-104-02", "expected/check.txt", lambda v: v.replace(b"targets=3", b"targets=2")),
            ("SINGLE-104-03", "expected/verify.txt", lambda v: v.replace(b"scope=selected ", b"")),
            ("SINGLE-104-04", "expected/doctor.txt",
             lambda v: v.replace(b"doctor passed ", b"doctor passed scope=full ")),
            ("SINGLE-106-05", "expected/verify.txt", lambda v: v.rsplit(b"invocation", 1)[0]),
        ]
        for identifier, relative, mutate in mutations:
            with self.subTest(identifier=identifier), tempfile.TemporaryDirectory() as temporary:
                root = self.copy_fixture(temporary, identifier)
                path = root / "single" / identifier / relative
                path.write_bytes(mutate(path.read_bytes()))
                self.assertTrue(presentation_fixtures.validate(root, [identifier])["errors"])

    def test_presentation_audit_rejects_changed_results(self):
        mutations = [
            ("SINGLE-105-01", "expected/context.json", lambda v: v.update(revision=None)),
            ("SINGLE-105-02", "expected/verify.json",
             lambda v: v.update(revision={"commit": "0" * 40, "dirty": False})),
            ("SINGLE-106-04", "expected/verify.json",
             lambda v: v["commands"][0].update(stdoutTruncated=True)),
            ("SINGLE-106-05", "expected/verify.json",
             lambda v: v["targetResults"].pop()),
            ("SINGLE-104-04", "side-effects.json",
             lambda v: v["after"].update(cache={"doctor": {"kind": "directory"}})),
            ("SINGLE-105-02", "side-effects.json",
             lambda v: v["before"].update(git={"status": "", "index": ""})),
        ]
        for identifier, relative, mutate in mutations:
            with self.subTest(identifier=identifier, file=relative), tempfile.TemporaryDirectory() as temporary:
                root = self.copy_fixture(temporary, identifier)
                path = root / "single" / identifier / relative
                value = json.loads(path.read_text()); mutate(value); path.write_text(json.dumps(value))
                self.assertTrue(presentation_fixtures.validate(root, [identifier])["errors"])

    def test_presentation_markdown_audit_rejects_altered_bundles(self):
        identifier = "SINGLE-104-01"
        mutations = [
            lambda v: v.replace("## Work Boundary\n\n- none\n\n", "", 1),
            lambda v: v.replace("- projection: detail=standard", "- projection: detail=full", 1),
            lambda v: v.replace("秘密情報を出力しない。\n", "秘密情報を出力しない。\u001b[31m\n", 1),
            lambda v: v.replace("# Context Bundle\n", "# Context Bundle\n\n- durationMs: 24\n", 1),
            lambda v: v.replace("\n## Advisory Documents\n\n- none\n", "\n"),
        ]
        for index, mutate in enumerate(mutations):
            with self.subTest(mutation=index), tempfile.TemporaryDirectory() as temporary:
                root = self.copy_fixture(temporary, identifier)
                path = root / "single" / identifier / "expected/context.txt"
                path.write_text(mutate(path.read_text()))
                self.assertTrue(presentation_fixtures.validate(root, [identifier])["errors"])

    def test_presentation_markdown_reference_follows_the_fixed_rules(self):
        from conformance import markdown_reference
        result = presentation_fixtures.reviewed_result("SINGLE-104-01")
        text = markdown_reference.render(result)
        self.assertEqual(text.count("# Context Bundle"), 1)
        self.assertEqual([line[3:] for line in text.splitlines() if line.startswith("## ")][:1],
                         ["Bundle Manifest"])
        # より長いバッククォートの連続列を含む本文では、フェンスを長くしなければならない。
        document = copy.deepcopy(result["documents"][0])
        document["bodyText"] = "````\ncode\n````\n"
        self.assertEqual(markdown_reference.fence(document["bodyText"]), "`" * 5)
        self.assertIn("`````markdown", markdown_reference.document_block(document))
        # `compact`は見出しを残し、本文を落とす。
        compact = markdown_reference.document_block(result["documents"][0], "compact")
        self.assertNotIn("bodyText", compact)
        self.assertIn("### REQ-001 — .spec/requirements/REQ-001.md", compact)

    def test_presentation_audit_rejects_output_from_the_silent_command(self):
        identifier = "SINGLE-106-04"
        with tempfile.TemporaryDirectory() as temporary:
            root = self.copy_fixture(temporary, identifier)
            path = root / "single" / identifier / "repo" / presentation_fixtures.verify_output_fixtures.COMMAND_PATH
            path.write_text("#!/bin/sh\necho noise\nexit 0\n")
            self.assertTrue(presentation_fixtures.validate(root, [identifier])["errors"])

    def test_scanner_fixtures(self):
        result = scanner_fixtures.validate()
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["prepared"], list(scanner_fixtures.CASES))
        self.assertEqual(len(result["prepared"]), 16)
        self.assertEqual(result["core_execution"], "Not run")

    def test_scanner_audit_rejects_changed_positions_and_primaries(self):
        mutations = [
            ("SINGLE-096-02", "expected/check.json", lambda v: v["diagnostics"][0]["source"].update(column=72)),
            ("SINGLE-099-01", "expected/check.json", lambda v: v.update(checkedStatementCount=0)),
            ("SINGLE-100-04", "expected/check.json",
             lambda v: v["diagnostics"][0].update(code="EAI-CORE-SYNTAX-002")),
            ("SINGLE-101-03", "expected/check.json",
             lambda v: v["diagnostics"].append(copy.deepcopy(v["diagnostics"][0]))),
            ("SINGLE-102", "expected/check.json", lambda v: v["diagnostics"][0]["source"].pop("column")),
            # 共有する元の原因は、優先順位の低い条件ではなく、レビュー済みの主診断を保つ必要がある。
            ("SINGLE-103-01", "expected/check.json",
             lambda v: v["diagnostics"][0].update(code="EAI-CORE-SYNTAX-004")),
            ("SINGLE-103-02", "side-effects.json",
             lambda v: v["after"].update(cache={"scanner": {"kind": "directory"}})),
        ]
        for identifier, relative, mutate in mutations:
            with self.subTest(identifier=identifier), tempfile.TemporaryDirectory() as temporary:
                root = self.copy_fixture(temporary, identifier)
                path = root / "single" / identifier / relative
                value = json.loads(path.read_text()); mutate(value); path.write_text(json.dumps(value))
                self.assertTrue(scanner_fixtures.validate(root, [identifier])["errors"])

    def test_scanner_audit_rejects_unwrapped_or_replaced_statements(self):
        module = scanner_fixtures
        for identifier in module.CASES:
            unwrapped = {"SINGLE-099-01": module.CANDIDATE, "SINGLE-099-02": module.CANDIDATE,
                         "SINGLE-099-03": module.CANDIDATE, "SINGLE-099-04": module.CANDIDATE}
            line = unwrapped.get(identifier, "- [x] 確認済み。")
            with self.subTest(identifier=identifier), tempfile.TemporaryDirectory() as temporary:
                root = self.copy_fixture(temporary, identifier)
                path = root / "single" / identifier / "repo" / module.SPEC_PATH
                path.write_text(module.reviewed_document("approved", line))
                self.assertTrue(scanner_fixtures.validate(root, [identifier])["errors"])

    def test_registry_closure_fixtures(self):
        result = registry_closure_fixtures.validate()
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["prepared"], ["SINGLE-089", "SINGLE-090", "SINGLE-091",
                                              "SINGLE-092", "SINGLE-093", "SINGLE-094", "SINGLE-095"])
        self.assertEqual(result["core_execution"], "Not run")

    def test_registry_closure_audit_rejects_changed_expectations(self):
        mutations = [
            ("SINGLE-089", "expected/check.json", lambda v: v["diagnostics"][0]["source"].update(column=48)),
            ("SINGLE-090", "expected/check.json", lambda v: v["diagnostics"][0].update(severity="error")),
            ("SINGLE-091", "expected/check.json", lambda v: v["workspace"].update(id="root")),
            ("SINGLE-092", "expected/doctor.json", lambda v: v["checks"][2].update(status="passed")),
            ("SINGLE-093", "expected/doctor.json", lambda v: v["checks"][5]["lostGuarantees"].pop()),
            ("SINGLE-093", "expected/doctor.json", lambda v: v["diagnostics"][0].pop("suggestedAction")),
            ("SINGLE-093", "side-effects.json",
             lambda v: v["before"].update(git={"status": "", "index": ""})),
            ("SINGLE-094", "expected/check.json",
             lambda v: v["diagnostics"][0].update(code="SPEC-DOCTOR-WORKSPACE-001")),
            ("SINGLE-095", "side-effects.json",
             lambda v: v["after"].update(cache={"ears": {"kind": "directory"}})),
        ]
        for identifier, relative, mutate in mutations:
            with self.subTest(identifier=identifier, file=relative), tempfile.TemporaryDirectory() as temporary:
                root = self.copy_fixture(temporary, identifier)
                path = root / "single" / identifier / relative
                value = json.loads(path.read_text()); mutate(value); path.write_text(json.dumps(value))
                self.assertTrue(registry_closure_fixtures.validate(root, [identifier])["errors"])

    def test_registry_closure_audit_rejects_repaired_or_extended_inputs(self):
        module = registry_closure_fixtures
        # 唯一の原因を修復した場合や、ケースが否定するワークスペースを加えた場合は通過してはいけない。
        flips = {
            "SINGLE-089": (module.REQ_PATH, module.DOCUMENT.encode()),
            "SINGLE-090": (module.REQ_PATH, module.DOCUMENT.encode()),
            "SINGLE-091": (module.CONFIG_PATH, module.CONFIG.encode()),
            "SINGLE-092": (module.CONFIG_PATH, module.CONFIG.encode()),
            "SINGLE-093": (module.CONFIG_PATH, module.ANCHOR_CONFIG.encode()),
            "SINGLE-094": (module.CONFIG_PATH, module.CONFIG.encode()),
            "SINGLE-095": (module.CONFIG_PATH, module.CONFIG.encode()),
        }
        for identifier, (relative, content) in flips.items():
            with self.subTest(identifier=identifier), tempfile.TemporaryDirectory() as temporary:
                root = self.copy_fixture(temporary, identifier)
                path = root / "single" / identifier / "repo" / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
                self.assertTrue(registry_closure_fixtures.validate(root, [identifier])["errors"])

    def test_input_limit_fixtures(self):
        result = input_limit_fixtures.validate()
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["prepared"], ["SINGLE-078", "SINGLE-079-01", "SINGLE-079-02",
                                              "SINGLE-080-01", "SINGLE-080-02", "SINGLE-080-03", "SINGLE-083"])
        self.assertEqual(result["core_execution"], "Not run")

    def test_input_limit_audit_rejects_changed_expectations(self):
        mutations = [
            ("SINGLE-078", "expected/check.json", lambda v: v.update(checkedDocumentCount=1)),
            # 設定を読めずに止まる結果は、既定値`root`を同一性に補わず`null`にする（確認事項C59）。
            ("SINGLE-078", "expected/check.json", lambda v: v["workspace"].update(id="root")),
            ("SINGLE-078", "expected/check.json", lambda v: v["diagnostics"][0]["source"].update(workspaceId="root")),
            ("SINGLE-079-01", "expected/check.json",
             lambda v: v["diagnostics"][0]["source"].update(path=".spec/bitz.yaml")),
            ("SINGLE-079-02", "expected/check.json",
             lambda v: v["diagnostics"][0].update(code="SPEC-INPUT-READ-001")),
            ("SINGLE-080-01", "expected/check.json", lambda v: v.update(checkedStatementCount=999)),
            ("SINGLE-080-02", "expected/check.json", lambda v: v["diagnostics"][0].update(severity="warning")),
            ("SINGLE-080-03", "expected/check.json", lambda v: v["diagnostics"][0]["source"].pop("key")),
            ("SINGLE-083", "side-effects.json",
             lambda v: v["after"].update(cache={"limits": {"kind": "directory"}})),
        ]
        for identifier, relative, mutate in mutations:
            with self.subTest(identifier=identifier), tempfile.TemporaryDirectory() as temporary:
                root = self.copy_fixture(temporary, identifier)
                path = root / "single" / identifier / relative
                value = json.loads(path.read_text()); mutate(value); path.write_text(json.dumps(value))
                self.assertTrue(input_limit_fixtures.validate(root, [identifier])["errors"])

    def test_input_limit_audit_rejects_inputs_that_move_across_the_limit(self):
        module = input_limit_fixtures
        # 各置換えは、fixtureをレビュー済みの次元の反対側へ移す。
        flips = {
            "SINGLE-078": (module.CONFIG_PATH, module.CONFIG.encode()),
            "SINGLE-079-01": (module.REQ_PATH, module.DOCUMENT.encode()),
            "SINGLE-079-02": (module.REQ_PATH, module.DOCUMENT.encode()),
            "SINGLE-080-01": (module.REQ_PATH,
                              module.requirement(module.ITEM_LIMIT + 1, module.covers_ids(module.ITEM_LIMIT))),
            "SINGLE-080-02": (module.REQ_PATH,
                              module.requirement(module.ITEM_LIMIT, module.covers_ids(module.ITEM_LIMIT))),
            "SINGLE-080-03": (module.REQ_PATH,
                              module.requirement(module.ITEM_LIMIT, module.covers_ids(module.ITEM_LIMIT))),
            "SINGLE-083": (module.UNKNOWN_PATH, None),
        }
        for identifier, (relative, content) in flips.items():
            with self.subTest(identifier=identifier), tempfile.TemporaryDirectory() as temporary:
                root = self.copy_fixture(temporary, identifier)
                path = root / "single" / identifier / "repo" / relative
                if content is None:
                    path.unlink()
                else:
                    path.write_bytes(content)
                self.assertTrue(input_limit_fixtures.validate(root, [identifier])["errors"])

    def test_context_config_fixtures(self):
        result = context_config_fixtures.validate()
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["prepared"], ["SINGLE-150", "SINGLE-151", "SINGLE-152", "SINGLE-153"])
        self.assertEqual(result["references"], 2)
        self.assertEqual(result["core_execution"], "Not run")

    def copy_config_fixture(self, temporary, identifier):
        root = self.copy_fixture(temporary, identifier)
        shutil.copy2(schema_path(audit.FIXTURES, "frontmatter"), root)
        return root

    def test_context_config_audit_rejects_replaced_or_lost_diagnostics(self):
        """設定の不適合を`SPEC-WORKSPACE-MISSING-001`へ置換する、発生元を改変する、警告を消す、といった期待値を拒否する。"""
        missing = {"kind": "environment", "component": "workspace", "identifier": "."}
        mutations = [
            # 型の不正と値の範囲外は、設定の診断で返す。不在の診断への置換、発生元の`environment`化、`key`の消去・改変を拒否する。
            ("SINGLE-150", "expected/context.json", lambda v: v["diagnostics"][0].update(
                code="SPEC-WORKSPACE-MISSING-001", resultStatus="blocked", summary=".spec/bitz.yamlがありません", source=missing)),
            ("SINGLE-150", "expected/context.json", lambda v: v["diagnostics"][0].update(source=missing)),
            ("SINGLE-150", "expected/context.json", lambda v: v["diagnostics"][0].update(
                source={"kind": "file", "workspaceId": None, "path": ".spec/bitz.yaml"})),
            ("SINGLE-150", "expected/context.json", lambda v: v["diagnostics"][0]["source"].update(key="earsAi")),
            ("SINGLE-150", "expected/context.json", lambda v: v.update(status="blocked")),
            ("SINGLE-150", "expected/context.json", lambda v: v.update(status="failed")),
            ("SINGLE-150", "expected/context.json", lambda v: v.update(diagnostics=[])),
            ("SINGLE-150", "expected/context.json", lambda v: v["diagnostics"].append(copy.deepcopy(v["diagnostics"][0]))),
            ("SINGLE-150", "expected/context.json", lambda v: v["workspace"].update(id="root")),
            ("SINGLE-150", "expected/context.json", lambda v: v.update(contextDigest="sha256:" + "0" * 64)),
            ("SINGLE-150", "expected/context.json", lambda v: v["resolution"].update(complete=True)),
            ("SINGLE-150", "manifest.json", lambda v: v["expect"].update(status="blocked", exitCode=2)),
            ("SINGLE-150", "manifest.json", lambda v: v["expect"].update(exitCode=2)),
            ("SINGLE-150", "manifest.json", lambda v: v["invocation"]["argv"].__setitem__(0, "check")),
            ("SINGLE-151", "expected/context.json", lambda v: v["diagnostics"][0].update(
                code="SPEC-WORKSPACE-MISSING-001", resultStatus="blocked", summary=".spec/bitz.yamlがありません", source=missing)),
            ("SINGLE-151", "expected/context.json", lambda v: v["diagnostics"][0].update(source=missing)),
            ("SINGLE-151", "expected/context.json", lambda v: v["diagnostics"][0]["source"].pop("key")),
            ("SINGLE-151", "expected/context.json", lambda v: v["diagnostics"][0]["source"].update(key="context.maxDocuments")),
            ("SINGLE-151", "expected/context.json", lambda v: v.update(diagnostics=[])),
            ("SINGLE-151", "expected/context.json", lambda v: v.update(status="blocked")),
            ("SINGLE-151", "manifest.json", lambda v: v["expect"].update(exitCode=2)),
            # 設定の不在は、`environment`を発生元とする`SPEC-WORKSPACE-MISSING-001`（`blocked`）で返す。設定の診断や`file`の発生元へ置換しない。
            ("SINGLE-152", "expected/context.json", lambda v: v["diagnostics"][0].update(
                code="SPEC-CONFIG-SCHEMA-001", resultStatus="error", summary="設定キーlanguageは文字列で指定してください")),
            ("SINGLE-152", "expected/context.json", lambda v: v["diagnostics"][0].update(
                source={"kind": "file", "workspaceId": None, "path": ".spec/bitz.yaml"})),
            ("SINGLE-152", "expected/context.json", lambda v: v["diagnostics"][0]["source"].update(identifier=".spec")),
            ("SINGLE-152", "expected/context.json", lambda v: v["diagnostics"][0]["source"].update(component="git")),
            ("SINGLE-152", "expected/context.json", lambda v: v.update(status="error")),
            ("SINGLE-152", "expected/context.json", lambda v: v.update(status="failed")),
            ("SINGLE-152", "expected/context.json", lambda v: v.update(diagnostics=[])),
            ("SINGLE-152", "expected/context.json", lambda v: v["workspace"].update(id="root")),
            ("SINGLE-152", "manifest.json", lambda v: v["expect"].update(status="error", exitCode=3)),
            ("SINGLE-152", "manifest.json", lambda v: v["expect"].update(exitCode=3)),
            # 警告は成功した結果へ加える。警告の消去、重大度や状態の改変、ハッシュ値の改変、完全解決の取消しを拒否する。
            ("SINGLE-153", "expected/context.json", lambda v: v.update(diagnostics=[])),
            ("SINGLE-153", "expected/context.json", lambda v: v.update(status="passed")),
            ("SINGLE-153", "expected/context.json", lambda v: v.update(status="error")),
            ("SINGLE-153", "expected/context.json", lambda v: v["diagnostics"][0].update(severity="error")),
            ("SINGLE-153", "expected/context.json", lambda v: v["diagnostics"][0].update(code="SPEC-CONFIG-SCHEMA-001")),
            ("SINGLE-153", "expected/context.json", lambda v: v["diagnostics"][0]["source"].pop("key")),
            ("SINGLE-153", "expected/context.json", lambda v: v["diagnostics"][0]["source"].update(key="profiles")),
            ("SINGLE-153", "expected/context.json", lambda v: v["diagnostics"].append(copy.deepcopy(v["diagnostics"][0]))),
            ("SINGLE-153", "expected/context.json", lambda v: v.update(contextDigest=None)),
            ("SINGLE-153", "expected/context.json", lambda v: v.update(contextDigest="sha256:" + "0" * 64)),
            ("SINGLE-153", "expected/context.json", lambda v: v["resolution"].update(complete=False)),
            ("SINGLE-153", "expected/context.json", lambda v: v.update(documents=[])),
            ("SINGLE-153", "expected/context.json", lambda v: v["constraintLedger"].update(statements=[{"id": "REQ-001:AC-01"}])),
            ("SINGLE-153", "manifest.json", lambda v: v["expect"].update(status="passed")),
            ("SINGLE-153", "manifest.json", lambda v: v["expect"].update(exitCode=3)),
        ]
        for identifier, relative, mutate in mutations:
            with self.subTest(identifier=identifier, file=relative, mutation=mutations.index((identifier, relative, mutate))), \
                    tempfile.TemporaryDirectory() as temporary:
                root = self.copy_config_fixture(temporary, identifier)
                path = root / "single" / identifier / relative
                value = json.loads(path.read_text()); mutate(value); path.write_text(json.dumps(value))
                self.assertTrue(context_config_fixtures.validate(root, [identifier])["errors"])

    def test_context_config_audit_rejects_digest_material_changes(self):
        """正規JSONが参照計算から離れる改変（未知のキーの混入、許可リストの設定値の改変）を拒否する。"""
        mutations = [
            lambda text: text.replace('"settings":{', '"settings":{"futureOption":"preserve-me",', 1),
            lambda text: text.replace('"language":"ja"', '"language":"en"', 1),
            lambda text: text.replace('"purpose":"interpret"', '"purpose":"verify"', 1),
            lambda text: text.replace('"verifyTimeouts":[]', '"verifyTimeouts":[{"timeoutSeconds":300,"workspaceId":"root"}]', 1),
        ]
        for index, mutate in enumerate(mutations):
            with self.subTest(index=index), tempfile.TemporaryDirectory() as temporary:
                root = self.copy_config_fixture(temporary, "SINGLE-153")
                path = root / "single/SINGLE-153/expected/context.canonical.json"
                changed = mutate(path.read_text())
                self.assertNotEqual(changed, path.read_text())
                path.write_text(changed)
                self.assertTrue(context_config_fixtures.validate(root, ["SINGLE-153"])["errors"])
        with tempfile.TemporaryDirectory() as temporary:
            root = self.copy_config_fixture(temporary, "SINGLE-153")
            path = root / "single/SINGLE-153/expected/context.canonical.json"
            path.write_bytes(path.read_bytes() + b"\n")
            self.assertTrue(context_config_fixtures.validate(root, ["SINGLE-153"])["errors"])
        # 他のfixtureは、ハッシュ値を計算しないので正規JSONを持てない。
        with tempfile.TemporaryDirectory() as temporary:
            root = self.copy_config_fixture(temporary, "SINGLE-150")
            (root / "single/SINGLE-150/expected/context.canonical.json").write_bytes(b"{}")
            self.assertTrue(context_config_fixtures.validate(root, ["SINGLE-150"])["errors"])

    def test_context_config_audit_rejects_repaired_or_confounded_inputs(self):
        """唯一の原因を直した入力、別の原因を足した入力、起点を消した入力は、期待値と組にならない。"""
        module = context_config_fixtures
        config, req = module.CONFIG_PATH, module.REQ_PATH
        edits = [
            # 型の不正を直す、値の範囲を満たす、設定を足す
            ("SINGLE-150", config, lambda text: text.replace("language: 42", "language: ja")),
            ("SINGLE-150", config, lambda text: text.replace("language: 42", "language: en")),
            ("SINGLE-151", config, lambda text: text.replace("maxBytes: 100", "maxBytes: 4096")),
            ("SINGLE-151", config, lambda text: text.replace("maxBytes: 100", "maxBytes: 131072")),
            ("SINGLE-151", config, lambda text: text.replace("maxBytes: 100", "maxBytes: 5000000")),
            ("SINGLE-151", config, lambda text: text + "futureOption: x\n"),
            ("SINGLE-153", config, lambda text: text.replace("futureOption: preserve-me\n", "")),
            ("SINGLE-153", config, lambda text: text.replace("futureOption", "profiles")),
            ("SINGLE-153", config, lambda text: text + "otherOption: 1\n"),
            ("SINGLE-153", config, lambda text: text.replace("preserve-me", "changed")),
            # 起点の文書を変える。ハッシュ値の材料と本文が変わる
            ("SINGLE-153", req, lambda text: text.replace("文書構造を検査する。", "文書構造を検査する。\n")),
            ("SINGLE-153", req, lambda text: text.replace("[MUST]", "[SHOULD] [REASON] 確認のため")),
            ("SINGLE-150", req, lambda text: text.replace("status: approved", "status: draft")),
        ]
        for identifier, relative, edit in edits:
            with self.subTest(identifier=identifier, file=relative, edit=edits.index((identifier, relative, edit))), \
                    tempfile.TemporaryDirectory() as temporary:
                root = self.copy_config_fixture(temporary, identifier)
                path = root / "single" / identifier / "repo" / relative
                changed = edit(path.read_text())
                self.assertNotEqual(changed, path.read_text())
                path.write_text(changed)
                self.assertTrue(module.validate(root, [identifier])["errors"])
        # 起点の文書を消す（起点の不在が原因に混ざる）、設定を消す、設定を足す、不要なファイルを足す
        for identifier, action in (("SINGLE-150", "remove-req"), ("SINGLE-151", "remove-req"), ("SINGLE-153", "remove-req"),
                                   ("SINGLE-150", "remove-config"), ("SINGLE-153", "remove-config"),
                                   ("SINGLE-152", "add-config"), ("SINGLE-152", "add-minimal-config"),
                                   ("SINGLE-152", "remove-req"), ("SINGLE-150", "add-file")):
            with self.subTest(identifier=identifier, action=action), tempfile.TemporaryDirectory() as temporary:
                root = self.copy_config_fixture(temporary, identifier)
                repo = root / "single" / identifier / "repo"
                if action == "remove-req":
                    (repo / req).unlink()
                elif action == "remove-config":
                    (repo / config).unlink()
                elif action == "add-config":
                    (repo / config).write_text(module.CONFIGS["SINGLE-004-01"])
                elif action == "add-minimal-config":
                    (repo / config).write_text(module.CONFIGS["SINGLE-001"])
                else:
                    (repo / "extra.txt").write_text("x")
                self.assertTrue(module.validate(root, [identifier])["errors"])

    def test_context_config_audit_rejects_changed_side_effects_and_git_state(self):
        mutations = [
            ("SINGLE-150", lambda v: v["after"].update(cache={"ears": {"kind": "directory"}})),
            ("SINGLE-152", lambda v: v["before"].update(git={"status": "", "index": ""})),
            ("SINGLE-153", lambda v: v["before"]["repository"][".spec/bitz.yaml"].update(executable=True)),
            ("SINGLE-153", lambda v: v["after"]["repository"].pop(".spec/bitz.yaml")),
        ]
        for identifier, mutate in mutations:
            with self.subTest(identifier=identifier), tempfile.TemporaryDirectory() as temporary:
                root = self.copy_config_fixture(temporary, identifier)
                path = root / "single" / identifier / "side-effects.json"
                value = json.loads(path.read_text()); mutate(value); path.write_text(json.dumps(value))
                self.assertTrue(context_config_fixtures.validate(root, [identifier])["errors"])
        # コミットのないリポジトリの作業ツリーだけで準備する。基準のコミットを足すと拒否する。
        for identifier in context_config_fixtures.CASES:
            with self.subTest(identifier=identifier, change="baseCommit"), tempfile.TemporaryDirectory() as temporary:
                root = self.copy_config_fixture(temporary, identifier)
                path = root / "single" / identifier / "manifest.json"
                value = json.loads(path.read_text())
                value["setup"]["baseCommit"] = {"message": "base", "paths": ["."]}
                path.write_text(json.dumps(value))
                self.assertTrue(context_config_fixtures.validate(root, [identifier])["errors"])

    def copy_command_fixtures(self, temporary):
        """`SINGLE-155`の検証は`SINGLE-154`の正規JSONを共有するので、2件とも複製する。"""
        root = self.copy_config_fixture(temporary, "SINGLE-154")
        other = self.copy_fixture(Path(temporary) / "other", "SINGLE-155")
        shutil.copytree(other / "single/SINGLE-155", root / "single/SINGLE-155", symlinks=True)
        return root

    def test_digest_command_fixtures(self):
        result = digest_command_fixtures.validate()
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["prepared"], ["SINGLE-154", "SINGLE-155"])
        self.assertEqual(result["references"], 2)
        self.assertEqual(result["core_execution"], "Not run")
        # 複製した状態でも2件とも通る（以降の拒否の試験が、複製の不備で空振りしていないことの陽性対照）。
        with tempfile.TemporaryDirectory() as temporary:
            root = self.copy_command_fixtures(temporary)
            self.assertEqual(digest_command_fixtures.validate(root)["errors"], [])
        canonical = (audit.FIXTURES / "single/SINGLE-154/expected/context.canonical.json").read_bytes()
        settings = json.loads(canonical)["settings"]
        self.assertEqual([c["name"] for c in settings["commands"]], ["default"])
        self.assertEqual(settings["verifyTimeouts"], [{"timeoutSeconds": 300, "workspaceId": "root"}])
        # 2件のハッシュ値は同じ値である。
        context = json.loads((audit.FIXTURES / "single/SINGLE-154/expected/context.json").read_text())
        verify = json.loads((audit.FIXTURES / "single/SINGLE-155/expected/verify.json").read_text())
        self.assertEqual(context["contextDigest"], verify["targetResults"][0]["contextDigest"])
        self.assertEqual(context["contextDigest"], digest_command_fixtures.literal_digest())

    def test_digest_command_audit_rejects_changed_expectations(self):
        """ハッシュ値の食い違い、実行したコマンドの改変、起動条件の改変を拒否する。"""
        zero = "sha256:" + "0" * 64
        mutations = [
            ("SINGLE-154", "expected/context.json", lambda v: v.update(contextDigest=zero)),
            ("SINGLE-154", "expected/context.json", lambda v: v.update(contextDigest=None)),
            ("SINGLE-154", "expected/context.json", lambda v: v.update(status="passed_with_warnings")),
            ("SINGLE-154", "expected/context.json", lambda v: v["documents"][0]["frontmatter"].pop("verify")),
            ("SINGLE-154", "expected/context.json", lambda v: v["documents"][0]["frontmatter"]["tests"][0].update(command="default")),
            ("SINGLE-154", "expected/context.json", lambda v: v["coverage"]["must"].update(tested=[], untested=["REQ-001:AC-01"])),
            ("SINGLE-154", "expected/context.json", lambda v: v.update(purpose="implement")),
            ("SINGLE-154", "manifest.json", lambda v: v["invocation"]["argv"].__setitem__(3, "implement")),
            ("SINGLE-154", "manifest.json", lambda v: v["invocation"]["argv"].__delitem__(slice(2, 4))),
            ("SINGLE-155", "expected/verify.json", lambda v: v["targetResults"][0].update(contextDigest=zero)),
            ("SINGLE-155", "expected/verify.json", lambda v: v["targetResults"][0].update(contextDigest=None)),
            ("SINGLE-155", "expected/verify.json", lambda v: v.update(commands=[])),
            ("SINGLE-155", "expected/verify.json", lambda v: v["targetResults"][0].update(bindingRefs=[])),
            ("SINGLE-155", "expected/verify.json", lambda v: v["commands"][0].update(argv=["/bin/true"])),
            ("SINGLE-155", "expected/verify.json", lambda v: v["commands"][0].update(timeoutSeconds=1)),
            ("SINGLE-155", "expected/verify.json", lambda v: v["commands"][0].update(cwd="src")),
            ("SINGLE-155", "expected/verify.json", lambda v: v.update(status="failed")),
            ("SINGLE-155", "manifest.json", lambda v: v["setup"].update(operations=[])),
            ("SINGLE-155", "manifest.json", lambda v: v["invocation"]["argv"].append("--all-workspaces")),
        ]
        for index, (identifier, relative, mutate) in enumerate(mutations):
            with self.subTest(index=index, identifier=identifier, file=relative), tempfile.TemporaryDirectory() as temporary:
                root = self.copy_command_fixtures(temporary)
                path = root / "single" / identifier / relative
                value = json.loads(path.read_text()); mutate(value); path.write_text(json.dumps(value))
                self.assertTrue(digest_command_fixtures.validate(root, [identifier])["errors"])

    def test_digest_command_audit_rejects_digest_material_changes(self):
        """材料から`commands`または`verifyTimeouts`を消す改変、その内容の改変、正規JSONと結果の食い違いを拒否する。"""
        command = '"commands":[{"argv":["/bin/true","{tests}"],"cwd":".","name":"default","workspaceId":"root"}]'
        timeout = '"verifyTimeouts":[{"timeoutSeconds":300,"workspaceId":"root"}]'
        mutations = [
            lambda text: text.replace(command, '"commands":[]', 1),
            lambda text: text.replace(timeout, '"verifyTimeouts":[]', 1),
            lambda text: text.replace(command, '"commands":[]', 1).replace(timeout, '"verifyTimeouts":[]', 1),
            lambda text: text.replace('"/bin/true","{tests}"', '"/bin/true","tests/test_auth.py"', 1),
            lambda text: text.replace('"cwd":"."', '"cwd":"src"', 1),
            lambda text: text.replace('"timeoutSeconds":300', '"timeoutSeconds":301', 1),
            lambda text: text.replace('"name":"default"', '"name":"other"', 1),
            lambda text: text.replace('"verify":"default"', '"verify":null', 1),
            lambda text: text.replace('"command":null', '"command":"default"', 1),
        ]
        for index, mutate in enumerate(mutations):
            for identifier in ("SINGLE-154", "SINGLE-155"):
                with self.subTest(index=index, identifier=identifier), tempfile.TemporaryDirectory() as temporary:
                    root = self.copy_command_fixtures(temporary)
                    path = root / "single/SINGLE-154/expected/context.canonical.json"
                    changed = mutate(path.read_text())
                    self.assertNotEqual(changed, path.read_text())
                    path.write_text(changed)
                    self.assertTrue(digest_command_fixtures.validate(root, [identifier])["errors"])
        with tempfile.TemporaryDirectory() as temporary:
            root = self.copy_command_fixtures(temporary)
            path = root / "single/SINGLE-154/expected/context.canonical.json"
            path.write_bytes(path.read_bytes() + b"\n")
            self.assertTrue(digest_command_fixtures.validate(root, ["SINGLE-154"])["errors"])
        # `SINGLE-155`は正規JSONを持たない（`SINGLE-154`のものを共有する）。
        with tempfile.TemporaryDirectory() as temporary:
            root = self.copy_command_fixtures(temporary)
            (root / "single/SINGLE-155/expected/context.canonical.json").write_bytes(
                (root / "single/SINGLE-154/expected/context.canonical.json").read_bytes())
            self.assertTrue(digest_command_fixtures.validate(root, ["SINGLE-155"])["errors"])

    def test_digest_command_audit_rejects_repaired_or_confounded_inputs(self):
        """コマンド名の与え方（文書の`verify`だけ）を変えた入力、設定やテストを変えた入力は、期待値と組にならない。"""
        module = digest_command_fixtures
        config, req, test = module.CONFIG_PATH, module.REQ_PATH, module.TEST_PATH
        edits = [
            # 文書の`verify`を消す、テスト対応に`command`を足す（解決の経路が変わる）、別名にする
            (req, lambda text: text.replace("verify: default\n", "")),
            (req, lambda text: text.replace("verify: default\n", "").replace(
                "covers: [REQ-001:AC-01]\n", "covers: [REQ-001:AC-01]\n    command: default\n")),
            (req, lambda text: text.replace("verify: default", "verify: other")),
            (req, lambda text: text.replace("covers: [REQ-001:AC-01]\n", "covers: [REQ-001:AC-01]\n    command: default\n")),
            (req, lambda text: text.replace("文書構造を検査する。", "文書構造を検査する。\n")),
            (req, lambda text: text.replace("[MUST]", "[SHOULD] [REASON] 確認のため")),
            (config, lambda text: text.replace("default:", "other:")),
            (config, lambda text: text.replace("      cwd: .\n", "")),
            (config, lambda text: text.replace('"/bin/true", "{tests}"', '"/bin/true"')),
            (config, lambda text: text + "  timeoutSeconds: 60\n"),
            (test, lambda text: text + "# 変更\n"),
        ]
        for index, (relative, edit) in enumerate(edits):
            for identifier in ("SINGLE-154", "SINGLE-155"):
                with self.subTest(index=index, identifier=identifier), tempfile.TemporaryDirectory() as temporary:
                    root = self.copy_command_fixtures(temporary)
                    path = root / "single" / identifier / "repo" / relative
                    changed = edit(path.read_text())
                    self.assertNotEqual(changed, path.read_text())
                    path.write_text(changed)
                    self.assertTrue(module.validate(root, [identifier])["errors"])
        for identifier in ("SINGLE-154", "SINGLE-155"):
            for action in ("remove-test", "remove-req", "remove-config", "add-file"):
                with self.subTest(identifier=identifier, action=action), tempfile.TemporaryDirectory() as temporary:
                    root = self.copy_command_fixtures(temporary)
                    repo = root / "single" / identifier / "repo"
                    if action == "add-file":
                        (repo / "extra.txt").write_text("x")
                    else:
                        (repo / {"remove-test": test, "remove-req": req, "remove-config": config}[action]).unlink()
                    self.assertTrue(module.validate(root, [identifier])["errors"])

    def test_digest_command_audit_rejects_changed_side_effects_and_git_state(self):
        mutations = [
            ("SINGLE-154", lambda v: v["after"].update(cache={"ears": {"kind": "directory"}})),
            ("SINGLE-154", lambda v: v["before"].update(git={"status": "", "index": ""})),
            ("SINGLE-155", lambda v: v["before"].update(git={"status": "", "index": ""})),
            ("SINGLE-155", lambda v: v["after"]["repository"].pop("tests/test_auth.py")),
            ("SINGLE-155", lambda v: v["before"]["repository"][".spec/bitz.yaml"].update(executable=True)),
        ]
        for index, (identifier, mutate) in enumerate(mutations):
            with self.subTest(index=index, identifier=identifier), tempfile.TemporaryDirectory() as temporary:
                root = self.copy_command_fixtures(temporary)
                path = root / "single" / identifier / "side-effects.json"
                value = json.loads(path.read_text()); mutate(value); path.write_text(json.dumps(value))
                self.assertTrue(digest_command_fixtures.validate(root, [identifier])["errors"])
        # `SINGLE-154`はコミットのないリポジトリで準備する。基準のコミットを足すと拒否する。
        with tempfile.TemporaryDirectory() as temporary:
            root = self.copy_command_fixtures(temporary)
            path = root / "single/SINGLE-154/manifest.json"
            value = json.loads(path.read_text())
            value["setup"]["baseCommit"] = {"message": "base", "paths": ["."]}
            path.write_text(json.dumps(value))
            self.assertTrue(digest_command_fixtures.validate(root, ["SINGLE-154"])["errors"])

    def copy_task_tech_fixture(self, temporary, identifier):
        """`SINGLE-156`、`SINGLE-157`、`MULTI-028`は独立した入力なので、1件ずつ複製する。"""
        if identifier.startswith("MULTI-"):
            return self.copy_multi_fixture(temporary, identifier)
        return self.copy_config_fixture(temporary, identifier)

    def task_tech_directory(self, root, identifier):
        return verify_task_tech_fixtures.fixture_directory(root, identifier)

    def test_verify_task_tech_fixtures(self):
        result = verify_task_tech_fixtures.validate()
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["prepared"], ["SINGLE-156", "SINGLE-157", "MULTI-028"])
        self.assertEqual(result["references"], 2)
        self.assertEqual(result["core_execution"], "Not run")
        # 複製した状態でも通る（以降の拒否の試験が、複製の不備で空振りしていないことの陽性対照）。
        for identifier in verify_task_tech_fixtures.CASES:
            with self.subTest(identifier=identifier), tempfile.TemporaryDirectory() as temporary:
                root = self.copy_task_tech_fixture(temporary, identifier)
                self.assertEqual(verify_task_tech_fixtures.validate(root, [identifier])["errors"], [])
        # 3件は、規範文のないTECHの文書単位のテスト割当てを、TASKの起点で実行する。
        expected = {"SINGLE-156": ([], ["root::default"], ["tests/test_tech.py"], ["TECH-001"]),
                    "SINGLE-157": (["REQ-001:AC-01"], ["root::default"],
                                   ["tests/test_req.py", "tests/test_tech.py"], ["REQ-001:AC-01", "TECH-001"]),
                    "MULTI-028": ([], ["api::backend"], ["tests/test_audit.py"], ["api::TECH-020"])}
        for identifier, (statements, bindings, tests, covers) in expected.items():
            fixture = self.task_tech_directory(audit.FIXTURES, identifier)
            value = json.loads((fixture / "expected/verify.json").read_text())
            target = value["targetResults"][0]
            self.assertEqual((target["statements"], target["bindingRefs"]), (statements, bindings))
            self.assertEqual([(c["bindingId"], c["tests"], c["covers"]) for c in value["commands"]],
                             [(bindings[0], tests, covers)])
            self.assertEqual(target["contextDigest"], verify_task_tech_fixtures.literal_digest(identifier))
        # 3件はそれぞれ別の入力のハッシュ値を持つ。
        self.assertEqual(len({verify_task_tech_fixtures.literal_digest(i) for i in verify_task_tech_fixtures.CASES}), 3)

    def test_verify_task_tech_audit_rejects_changed_expectations(self):
        """`bindingRefs`や`commands`の消去、規範文の追加、テストの欠落、修飾の改変、ハッシュ値の改変を拒否する。"""
        zero = "sha256:" + "0" * 64
        mutations = []
        for identifier in verify_task_tech_fixtures.CASES:
            mutations += [
                (identifier, "expected/verify.json", lambda v: v["targetResults"][0].update(bindingRefs=[])),
                (identifier, "expected/verify.json", lambda v: v.update(commands=[])),
                (identifier, "expected/verify.json", lambda v: v.update(commands=[], targetResults=[
                    dict(v["targetResults"][0], bindingRefs=[])])),
                (identifier, "expected/verify.json", lambda v: v["targetResults"][0].update(contextDigest=zero)),
                (identifier, "expected/verify.json", lambda v: v["targetResults"][0].update(contextDigest=None)),
                (identifier, "expected/verify.json", lambda v: v["targetResults"][0]["statements"].append("TECH-001")),
                (identifier, "expected/verify.json", lambda v: v["commands"][0].update(tests=[])),
                (identifier, "expected/verify.json", lambda v: v["commands"][0].update(covers=[])),
                (identifier, "expected/verify.json", lambda v: v["commands"][0].update(argv=["/bin/true"])),
                (identifier, "expected/verify.json", lambda v: v["commands"][0].update(timeoutSeconds=1)),
                (identifier, "expected/verify.json", lambda v: v["commands"][0].update(cwd="src")),
                (identifier, "expected/verify.json", lambda v: v["commands"][0].update(status="failed", exitCode=1)),
                (identifier, "expected/verify.json", lambda v: v.update(commands=v["commands"] * 2)),
                (identifier, "expected/verify.json", lambda v: v.update(status="failed")),
                (identifier, "expected/verify.json", lambda v: v.update(status="blocked")),
                (identifier, "expected/verify.json", lambda v: v["targetResults"][0].update(status="blocked")),
                (identifier, "expected/verify.json", lambda v: v.update(diagnostics=[{
                    "code": "SPEC-VERIFY-BLOCKED-001", "severity": "error", "resultStatus": "blocked",
                    "summary": "テストがありません"}])),
                (identifier, "manifest.json", lambda v: v["expect"].update(status="blocked", exitCode=2)),
                (identifier, "manifest.json", lambda v, identifier=identifier: v["invocation"]["argv"].__setitem__(
                    1, "api::TECH-020" if identifier == "MULTI-028" else "TECH-001")),
                (identifier, "manifest.json", lambda v: v["invocation"]["argv"].append("--all-workspaces")),
            ]
        mutations += [
            ("SINGLE-156", "expected/verify.json", lambda v: v["targetResults"][0].update(statements=["TECH-001"])),
            ("SINGLE-157", "expected/verify.json", lambda v: v["targetResults"][0].update(statements=[])),
            ("SINGLE-157", "expected/verify.json", lambda v: v["targetResults"][0].update(statements=["REQ-001:AC-01", "TECH-001"])),
            ("SINGLE-157", "expected/verify.json", lambda v: v["commands"][0].update(
                tests=["tests/test_req.py"], argv=["/bin/true", "tests/test_req.py"], covers=["REQ-001:AC-01"])),
            ("SINGLE-157", "expected/verify.json", lambda v: v["commands"][0].update(
                tests=["tests/test_tech.py"], argv=["/bin/true", "tests/test_tech.py"], covers=["TECH-001"])),
            ("SINGLE-157", "expected/verify.json", lambda v: v["commands"][0].update(tests=["tests/test_tech.py", "tests/test_req.py"])),
            ("SINGLE-156", "expected/verify.json", lambda v: v["commands"][0].update(
                tests=["tests/test_req.py"], argv=["/bin/true", "tests/test_req.py"])),
            ("SINGLE-156", "manifest.json", lambda v: v["setup"].update(operations=[])),
            ("MULTI-028", "expected/verify.json", lambda v: v["targetResults"][0].update(bindingRefs=["web::backend"])),
            ("MULTI-028", "expected/verify.json", lambda v: v["commands"][0].update(bindingId="web::backend", workspaceId="web")),
            ("MULTI-028", "expected/verify.json", lambda v: v["commands"][0].update(covers=["TECH-020"])),
            ("MULTI-028", "expected/verify.json", lambda v: v["targetResults"][0].update(target="TASK-001")),
            ("MULTI-028", "expected/verify.json", lambda v: v.update(workspace={"id": "api", "path": "services/api"})),
            ("MULTI-028", "expected/verify.json", lambda v: v.update(revision=None)),
            ("MULTI-028", "manifest.json", lambda v: v["setup"].pop("baseCommit")),
        ]
        for index, (identifier, relative, mutate) in enumerate(mutations):
            with self.subTest(index=index, identifier=identifier, file=relative), tempfile.TemporaryDirectory() as temporary:
                root = self.copy_task_tech_fixture(temporary, identifier)
                path = self.task_tech_directory(root, identifier) / relative
                value = json.loads(path.read_text())
                before = json.dumps(value, sort_keys=True)
                mutate(value)
                self.assertNotEqual(json.dumps(value, sort_keys=True), before)
                path.write_text(json.dumps(value))
                self.assertTrue(verify_task_tech_fixtures.validate(root, [identifier])["errors"])

    def test_verify_task_tech_result_check_rejects_lost_or_added_binding_and_statements(self):
        """入力の木構造から導く計画との比較が、`bindingRefs`・`commands`の消去、規範文の追加、テストの欠落を拒否する。"""
        module = verify_task_tech_fixtures
        for identifier in module.CASES:
            multi = identifier in module.MULTI
            root_id = "web::TASK-001" if multi else "TASK-001"
            fixture = self.task_tech_directory(audit.FIXTURES, identifier)
            result = json.loads((fixture / "expected/verify.json").read_text())
            plan = module.reference_plan(fixture / "repo", root_id, multi)
            module.check_result(result, plan)

            def erase_binding(value):
                value["targetResults"][0]["bindingRefs"] = []
                value["commands"] = []

            def add_statement(value):
                value["targetResults"][0]["statements"].append("TECH-001" if not multi else "api::TECH-020")

            def drop_tests(value):
                value["commands"][0]["tests"] = value["commands"][0]["tests"][:-1]

            def drop_covers(value):
                value["commands"][0]["covers"] = value["commands"][0]["covers"][:-1]

            def unqualify(value):
                value["commands"][0]["covers"] = [item.rpartition("::")[2] for item in value["commands"][0]["covers"]]

            changes = [erase_binding, add_statement, drop_tests, drop_covers,
                       lambda value: value["targetResults"][0].update(bindingRefs=[]),
                       lambda value: value.update(commands=[])]
            if multi:
                changes.append(unqualify)
            for index, change in enumerate(changes):
                with self.subTest(identifier=identifier, index=index):
                    changed = copy.deepcopy(result)
                    change(changed)
                    with self.assertRaises(ValueError):
                        module.check_result(changed, plan)

    def test_verify_task_tech_reference_plan_follows_the_inputs(self):
        """計画は入力の木構造から導く。TECHの`tests`の消去、`addresses`の変更、規範文の追加で計画が変わり、期待値と食い違う。"""
        module = verify_task_tech_fixtures
        edits = [
            ("SINGLE-156", module.TECH_PATH, "tests:\n  - path: tests/test_tech.py\n    covers: [TECH-001]\n    command: default\n", ""),
            ("SINGLE-156", module.TASK_PATH, "addresses: [TECH-001]", "related: [TECH-001]"),
            ("SINGLE-156", module.TECH_PATH, "covers: [TECH-001]", "covers: [TECH-002]"),
            ("SINGLE-157", module.TECH_PATH, "tests:\n  - path: tests/test_tech.py\n    covers: [TECH-001]\n    command: default\n", ""),
            ("SINGLE-157", module.REQ_PATH, "tests:\n  - path: tests/test_req.py\n    covers: [REQ-001:AC-01]\n    command: default\n", ""),
            ("SINGLE-157", module.TASK_PATH, "addresses: [REQ-001:AC-01, TECH-001]", "addresses: [REQ-001:AC-01]"),
            ("SINGLE-157", module.TASK_PATH, "addresses: [REQ-001:AC-01, TECH-001]", "addresses: [TECH-001]"),
            ("MULTI-028", "services/api/.spec/technical/TECH-020.md",
             "tests:\n  - path: tests/test_audit.py\n    covers: [TECH-020]\n    command: backend\n", ""),
            ("MULTI-028", module.M_TASK_PATH, "addresses: [api::TECH-020]", "related: [api::TECH-020]"),
        ]
        for index, (identifier, relative, old, new) in enumerate(edits):
            multi = identifier in module.MULTI
            root_id = "web::TASK-001" if multi else "TASK-001"
            with self.subTest(index=index, identifier=identifier), tempfile.TemporaryDirectory() as temporary:
                fixture = self.task_tech_directory(audit.FIXTURES, identifier)
                repository = Path(temporary) / "repo"
                shutil.copytree(fixture / "repo", repository)
                path = repository / relative
                self.assertIn(old, path.read_text())
                path.write_text(path.read_text().replace(old, new))
                result = json.loads((fixture / "expected/verify.json").read_text())
                with self.assertRaises(ValueError):
                    module.check_result(result, module.reference_plan(repository, root_id, multi))
        # 規範文を持つTECHを文書IDだけで`addresses`することは、規範文を持たない文書の規則に反する。
        with tempfile.TemporaryDirectory() as temporary:
            fixture = self.task_tech_directory(audit.FIXTURES, "SINGLE-156")
            repository = Path(temporary) / "repo"
            shutil.copytree(fixture / "repo", repository)
            path = repository / module.TECH_PATH
            path.write_text(path.read_text() + "\n## Contract\n\n"
                            "- [TECH-001:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 秘密情報を出力しない。\n")
            with self.assertRaises(ValueError):
                module.reference_plan(repository, "TASK-001", False)

    def test_verify_task_tech_audit_rejects_changed_inputs(self):
        """原因は、TASKが規範文のないTECHを`addresses`し、そのTECHが文書単位の`tests`を持つことだけである。入力を変えた写しは、期待値が同じでも拒否する。"""
        module = verify_task_tech_fixtures
        tech, req, task, config = module.TECH_PATH, module.REQ_PATH, module.TASK_PATH, module.CONFIG_PATH
        web_task, api_tech = module.M_TASK_PATH, module.M_TECH_PATH
        api_config, web_config = multi_reference.API_CONFIG_PATH, multi_reference.WEB_CONFIG_PATH
        schema = json.loads(schema_path(audit.FIXTURES, "frontmatter").read_text())
        both = ("SINGLE-156", "SINGLE-157")
        edits = [
            (both, tech, lambda text: text.replace("    command: default\n", "")),
            (both, tech, lambda text: text.replace("covers: [TECH-001]", "covers: [TECH-001, TECH-002]")),
            (both, tech, lambda text: text.replace("tests:\n", "verify: default\ntests:\n")),
            (both, tech, lambda text: text.replace("command: default", "command: other")),
            (both, tech, lambda text: text.replace("status: approved", "status: draft")),
            (both, tech, lambda text: text.replace("status: approved\n", "status: approved\nrelations:\n  requires: [REQ-009]\n")),
            (both, tech, lambda text: text.replace("規範文を持たず、", "規範文を持たず、\n\n- [TECH-001:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 何かを行う。\n")),
            (both, task, lambda text: text.replace("status: open", "status: done")),
            (both, task, lambda text: text.replace("relations:", "changes: [src/auth.py]\nrelations:")),
            (both, task, lambda text: text.replace("addresses:", "requires: [TASK-002]\n  addresses:")),
            (both, task, lambda text: text.replace("addresses: [", "addresses: [REQ-009, ")),
            (both, config, lambda text: text.replace("default:", "other:")),
            (both, config, lambda text: text + "  timeoutSeconds: 60\n"),
            (both, config, lambda text: text.replace("{tests}", "tests/test_tech.py")),
            (("SINGLE-157",), req, lambda text: text.replace("[MUST]", "[SHOULD] [REASON] 確認のため")),
            (("SINGLE-157",), req, lambda text: text.replace("path: tests/test_req.py", "path: tests/test_tech.py")),
            (("SINGLE-157",), req, lambda text: text.replace("command: default", "command: other")),
            (("SINGLE-157",), req, lambda text: text.replace("status: approved", "status: draft")),
            (("SINGLE-157",), req, lambda text: text.replace("tests:", "relations:\n  refines: [TECH-001]\ntests:")),
            (("MULTI-028",), api_tech, lambda text: text.replace("    command: backend\n", "")),
            (("MULTI-028",), api_tech, lambda text: text.replace("covers: [TECH-020]", "covers: [api::TECH-020]")),
            (("MULTI-028",), api_tech, lambda text: text.replace("status: approved", "status: draft")),
            (("MULTI-028",), api_tech, lambda text: text.replace("tests:\n", "verify: backend\ntests:\n")),
            (("MULTI-028",), web_task, lambda text: text.replace("api::TECH-020", "TECH-020")),
            (("MULTI-028",), web_task, lambda text: text.replace("status: open", "status: done")),
            (("MULTI-028",), api_config, lambda text: text.replace("backend:", "frontend:")),
            (("MULTI-028",), web_config, lambda text: text + "verify:\n  commands:\n    backend:\n      argv: [\"/bin/false\", \"{tests}\"]\n      cwd: .\n"),
        ]
        for index, (identifiers, relative, edit) in enumerate(edits):
            for identifier in identifiers:
                with self.subTest(index=index, identifier=identifier, file=relative), tempfile.TemporaryDirectory() as temporary:
                    root = self.copy_task_tech_fixture(temporary, identifier)
                    path = self.task_tech_directory(root, identifier) / "repo" / relative
                    changed = edit(path.read_text())
                    self.assertNotEqual(changed, path.read_text())
                    path.write_text(changed)
                    self.assertTrue(module.validate(root, [identifier])["errors"])
                    # 入力の一致の検査と別に、原因の単一性の検査が、入力の木構造から拒否する。
                    with self.assertRaises(ValueError):
                        module.check_conditions(identifier, path.parents[len(Path(relative).parents) - 1], schema)
        # 末尾の空行とテストのファイルの本文は原因に関与しないが、入力のバイト列の一致の検査が拒否する。
        byte_only = [(both, tech, "\n"), (both, "tests/test_tech.py", "# 変更\n"),
                     (("MULTI-028",), "services/api/tests/test_audit.py", "# 変更\n")]
        for identifiers, relative, suffix in byte_only:
            for identifier in identifiers:
                with self.subTest(identifier=identifier, file=relative, edit="append"), tempfile.TemporaryDirectory() as temporary:
                    root = self.copy_task_tech_fixture(temporary, identifier)
                    path = self.task_tech_directory(root, identifier) / "repo" / relative
                    path.write_text(path.read_text() + suffix)
                    self.assertTrue(module.validate(root, [identifier])["errors"])
        removals = {"SINGLE-156": [tech, task, config, "tests/test_tech.py"],
                    "SINGLE-157": [tech, task, req, config, "tests/test_tech.py", "tests/test_req.py"],
                    "MULTI-028": [api_tech, web_task, api_config, web_config, "services/api/tests/test_audit.py"]}
        for identifier, names in removals.items():
            for name in [*names, "add-file"]:
                with self.subTest(identifier=identifier, removed=name), tempfile.TemporaryDirectory() as temporary:
                    root = self.copy_task_tech_fixture(temporary, identifier)
                    repo = self.task_tech_directory(root, identifier) / "repo"
                    if name == "add-file":
                        (repo / "extra.txt").write_text("x")
                    else:
                        (repo / name).unlink()
                    self.assertTrue(module.validate(root, [identifier])["errors"])

    def test_verify_task_tech_audit_rejects_changed_digest_and_side_effects(self):
        """ハッシュ値の材料（参照計算A）と入力の木構造（参照計算B）が食い違う写し、副作用の期待値とGitの状態の改変を拒否する。"""
        module = verify_task_tech_fixtures
        for identifier in module.CASES:
            for change in ("commands", "document", "roots", "timeout"):
                with self.subTest(identifier=identifier, change=change), tempfile.TemporaryDirectory() as temporary:
                    root = self.copy_task_tech_fixture(temporary, identifier)
                    original = module.reviewed_digest_input

                    def tampered(name, original=original, change=change):
                        value = copy.deepcopy(original(name))
                        if change == "commands":
                            value["settings"]["commands"] = []
                        elif change == "document":
                            value["documents"][0]["bodyText"] += "\n"
                        elif change == "roots":
                            value["roots"].append("TECH-001")
                        else:
                            value["settings"]["verifyTimeouts"] = []
                        return value

                    with patch.object(module, "reviewed_digest_input", tampered):
                        self.assertTrue(module.validate(root, [identifier])["errors"])
                        # 参照計算Aだけを差し替えると、入力の木構造から導く参照計算Bと食い違う。
                        with self.assertRaises(ValueError):
                            module.references(identifier, self.task_tech_directory(audit.FIXTURES, identifier) / "repo")
        mutations = [
            ("SINGLE-156", lambda v: v["after"].update(cache={"ears": {"kind": "directory"}})),
            ("SINGLE-156", lambda v: v["before"].update(git={"status": "", "index": ""})),
            ("SINGLE-157", lambda v: v["before"]["repository"].pop("tests/test_req.py")),
            ("SINGLE-157", lambda v: v["before"]["repository"][".spec/bitz.yaml"].update(executable=True)),
            ("MULTI-028", lambda v: v["before"].update(git={"status": "", "index": ""})),
            ("MULTI-028", lambda v: v["after"]["repository"].pop("services/api/tests/test_audit.py")),
        ]
        for index, (identifier, mutate) in enumerate(mutations):
            with self.subTest(index=index, identifier=identifier), tempfile.TemporaryDirectory() as temporary:
                root = self.copy_task_tech_fixture(temporary, identifier)
                path = self.task_tech_directory(root, identifier) / "side-effects.json"
                value = json.loads(path.read_text()); mutate(value); path.write_text(json.dumps(value))
                self.assertTrue(module.validate(root, [identifier])["errors"])

    def test_multi_reference_closure_includes_the_addresses_of_a_task_root(self):
        """複合ワークスペースの参照計算Bは、TASK起点の`addresses`の先を距離1で閉包へ含め、`requires`を持つTASK起点を拒否する。"""
        fixture = audit.FIXTURES / "multi/MULTI-028"
        payload = multi_crosscheck.build(fixture / "repo", root="web::TASK-001")
        self.assertEqual([item["id"] for item in payload["documents"]], ["api::TECH-020", "web::TASK-001"])
        self.assertEqual(payload["crossWorkspaceEdges"],
                         [{"relation": "addresses", "source": "web::TASK-001", "target": "api::TECH-020"}])
        self.assertEqual([item["id"] for item in payload["workspaces"]], ["web", "api"])
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "repo"
            shutil.copytree(fixture / "repo", repository)
            path = repository / verify_task_tech_fixtures.M_TASK_PATH
            path.write_text(path.read_text().replace("addresses:", "requires: [api::TECH-020]\n  addresses:"))
            with self.assertRaises(ValueError):
                multi_crosscheck.build(repository, root="web::TASK-001")
            path.write_text(path.read_text().replace("requires: [api::TECH-020]\n  ", "").replace(
                "addresses: [api::TECH-020]", "addresses: [api::TECH-999]"))
            with self.assertRaises(ValueError):
                multi_crosscheck.build(repository, root="web::TASK-001")

    def copy_fixture(self, temporary, identifier):
        root = Path(temporary)
        shutil.copytree(audit.FIXTURES / "single" / identifier, root / "single" / identifier, symlinks=True)
        for name in ("manifest", "result", "side-effects"):
            shutil.copy2(schema_path(audit.FIXTURES, name), root)
        return root

    def copy_multi_fixture(self, temporary, identifier):
        root = Path(temporary)
        shutil.copytree(audit.FIXTURES / "multi" / identifier, root / "multi" / identifier, symlinks=True)
        for name in ("manifest", "result", "side-effects", "frontmatter"):
            shutil.copy2(schema_path(audit.FIXTURES, name), root)
        return root

    def test_multi_digest_fixtures(self):
        result = multi_digest_fixtures.validate()
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["prepared"], list(multi_digest_fixtures.CASES))
        self.assertEqual(result["references"], 2)
        self.assertEqual(result["core_execution"], "Not run")

    def test_multi_golden_material_holds_qualified_ids_and_reached_workspaces(self):
        material = multi_reference.reviewed_digest_input()
        self.assertEqual(material["requestWorkspaceId"], "platform")
        self.assertEqual([entry["id"] for entry in material["workspaces"]], ["platform", "api", "web"])
        self.assertEqual([document["id"] for document in material["documents"]],
                         ["api::TECH-010", "platform::REQ-001", "web::TECH-010"])
        self.assertEqual([edge["source"] for edge in material["crossWorkspaceEdges"]],
                         ["api::TECH-010", "web::TECH-010"])
        # 設定は到達ワークスペースだけへ射影し、カタログの列挙順と`maxMembers`を材料へ入れない。
        self.assertEqual([entry["id"] for entry in material["settings"]["workspaces"]],
                         ["api", "platform", "web"])
        self.assertNotIn("maxMembers", json.dumps(material))

    def test_multi_digest_audit_rejects_changed_material(self):
        mutations = [
            ("MULTI-002-01", "expected/context.json",
             lambda v: v["resolution"]["workspaces"].reverse()),
            ("MULTI-002-01", "expected/context.json",
             lambda v: v["resolution"]["crossWorkspaceEdges"].clear()),
            ("MULTI-002-01", "expected/context.json",
             lambda v: v.update(contextDigest="sha256:" + "0" * 64)),
            # メンバーの文書は所有ワークスペースを持つ。ルートワークスペースへ付け替えない。
            ("MULTI-002-01", "expected/context.json",
             lambda v: v["documents"][1].update(workspaceId="platform")),
            ("MULTI-002-02", "expected/verify.json",
             lambda v: v["targetResults"][0].update(bindingRefs=["web::frontend"])),
            ("MULTI-002-02", "expected/verify.json",
             lambda v: v["commands"][0].update(workspaceId="platform")),
            ("MULTI-002-02", "manifest.json", lambda v: v["setup"].pop("baseCommit")),
        ]
        for identifier, relative, mutate in mutations:
            with self.subTest(identifier=identifier, relative=relative), \
                    tempfile.TemporaryDirectory() as temporary:
                root = self.copy_multi_fixture(temporary, identifier)
                path = root / "multi" / identifier / relative
                value = json.loads(path.read_text())
                mutate(value)
                path.write_text(json.dumps(value))
                self.assertEqual(multi_digest_fixtures.validate(root, {identifier})["status"], "Failed")

    def test_multi_golden_material_follows_the_input_tree(self):
        """入力の木構造を変えれば参照計算Bの材料も変わり、コミットした正規JSONと一致しなくなる。"""
        with tempfile.TemporaryDirectory() as temporary:
            root = self.copy_multi_fixture(temporary, "MULTI-002-01")
            path = root / "multi/MULTI-002-01/repo/apps/web/.spec/technical/TECH-010.md"
            path.write_bytes(path.read_bytes().replace(b"command: frontend", b"command: backend"))
            result = multi_digest_fixtures.validate(root, {"MULTI-002-01"})
        self.assertEqual(result["status"], "Failed")

    def test_multi_identity_fixtures(self):
        result = multi_identity_fixtures.validate()
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["prepared"], list(multi_identity_fixtures.CASES))
        self.assertEqual(result["core_execution"], "Not run")

    def test_multi_identity_audit_rejects_mixed_causes_and_wrong_codes(self):
        mutations = [
            # 同じローカルIDの衝突を、非成功や件数の変更で置き換えない。
            ("MULTI-001", "expected/check.json", lambda v: v.update(status="failed")),
            ("MULTI-001", "expected/check.json",
             lambda v: v["workspaces"][1].update(checkedStatementCount=2)),
            ("MULTI-001", "expected/check.json", lambda v: v["workspaces"].reverse()),
            # 非修飾参照と、存在するワークスペースにない参照先を取り違えない。
            ("MULTI-003", "expected/check.json",
             lambda v: v["workspaces"][2]["diagnostics"][0].update(code="SPEC-RELATION-MISSING-001")),
            ("MULTI-004-01", "expected/context.json",
             lambda v: v["diagnostics"][0].update(code="SPEC-MULTI-REF-001")),
            ("MULTI-004-01", "expected/context.json",
             lambda v: v["resolution"].update(complete=True)),
            ("MULTI-004-02", "expected/check.json", lambda v: v.update(checkedDocumentCount=1)),
            # 不在の起点は終了コード4ではなく、操作の結果として返す。
            ("MULTI-025-01", "manifest.json", lambda v: v["expect"].update(exitCode=4)),
            ("MULTI-025-02", "expected/verify.json",
             lambda v: v.update(diagnostics=v["targetResults"][0]["diagnostics"])),
        ]
        for identifier, relative, mutate in mutations:
            with self.subTest(identifier=identifier, relative=relative), \
                    tempfile.TemporaryDirectory() as temporary:
                root = self.copy_multi_fixture(temporary, identifier)
                path = root / "multi" / identifier / relative
                value = json.loads(path.read_text())
                mutate(value)
                path.write_text(json.dumps(value))
                self.assertEqual(multi_identity_fixtures.validate(root, {identifier})["status"], "Failed")

    def test_multi_relation_type_fixtures(self):
        result = multi_relation_type_fixtures.validate()
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["prepared"], list(multi_relation_type_fixtures.CASES))
        self.assertEqual(result["core_execution"], "Not run")

    def test_multi_relation_type_audit_rejects_state_diagnostic_and_erased_diagnostic(self):
        """他のメンバーの文書の型制約を、状態の診断への置換、診断の消去（成功への改変）、発生元の改変で崩した写しを拒否する。"""
        def to_state(diagnostic):
            diagnostic.update(code="CTX-STATE-001", resultStatus="blocked", summary="ADR-001は状態proposedのため目的implementに適用できません")
            diagnostic["source"] = {"kind": "file", "workspaceId": "api", "path": ".spec/decisions/ADR-001.md"}
            diagnostic.pop("evidence")

        def erase_context(value):
            value.update(status="passed")
            value["diagnostics"] = []
            value["resolution"].update(complete=True, unresolvedStrongRelations=0)

        def erase_verify(value):
            value.update(status="passed")
            value["targetResults"][0].update(status="passed", diagnostics=[])

        mutations = [
            ("MULTI-027-01", "expected/context.json", lambda v: to_state(v["diagnostics"][0])),
            ("MULTI-027-02", "expected/verify.json", lambda v: to_state(v["targetResults"][0]["diagnostics"][0])),
            ("MULTI-027-01", "expected/context.json", erase_context),
            ("MULTI-027-02", "expected/verify.json", erase_verify),
            ("MULTI-027-01", "expected/context.json", lambda v: v.update(diagnostics=[])),
            ("MULTI-027-01", "expected/context.json",
             lambda v: v["diagnostics"][0]["source"].update(workspaceId="web")),
            ("MULTI-027-02", "expected/verify.json",
             lambda v: v["targetResults"][0]["diagnostics"][0]["source"].update(workspaceId="web")),
            ("MULTI-027-01", "expected/context.json",
             lambda v: v["diagnostics"][0]["source"].update(path=".spec/requirements/REQ-001.md")),
            ("MULTI-027-01", "expected/context.json",
             lambda v: v["diagnostics"][0].update(evidence="api::ADR-001")),
            ("MULTI-027-02", "expected/verify.json",
             lambda v: v["targetResults"][0]["diagnostics"][0]["source"].pop("key")),
            ("MULTI-027-01", "expected/context.json",
             lambda v: v["resolution"].update(unresolvedStrongRelations=0)),
            ("MULTI-027-01", "expected/context.json", lambda v: v.update(status="blocked")),
            ("MULTI-027-02", "expected/verify.json",
             lambda v: v.update(diagnostics=v["targetResults"][0]["diagnostics"])),
            ("MULTI-027-02", "expected/verify.json",
             lambda v: v["targetResults"][0].update(bindingRefs=["web::frontend"])),
            ("MULTI-027-01", "manifest.json", lambda v: v["expect"].update(status="blocked", exitCode=2)),
            ("MULTI-027-02", "manifest.json", lambda v: v["expect"].update(exitCode=4)),
            ("MULTI-027-01", "manifest.json", lambda v: v["invocation"].update(cwd=".")),
        ]
        for identifier, relative, mutate in mutations:
            with self.subTest(identifier=identifier, relative=relative), \
                    tempfile.TemporaryDirectory() as temporary:
                root = self.copy_multi_fixture(temporary, identifier)
                path = root / "multi" / identifier / relative
                value = json.loads(path.read_text())
                mutate(value)
                path.write_text(json.dumps(value))
                self.assertEqual(multi_relation_type_fixtures.validate(root, {identifier})["status"], "Failed")

    def test_multi_relation_type_audit_rejects_changed_corpus(self):
        """原因はTECH-020から状態`proposed`のADR-001への`requires`の1つだけである。入力を変えた写しは、期待値が同じでも拒否する。"""
        edits = [
            ("services/api/.spec/decisions/ADR-001.md", b"status: proposed", b"status: accepted"),
            ("apps/web/.spec/requirements/REQ-001.md", b"requires: [api::TECH-020]",
             b"requires: [api::TECH-020]\n  refines: [api::TECH-020]"),
            ("services/api/.spec/technical/TECH-020.md", b"requires: [ADR-001]", b"requires: [api::ADR-001]"),
        ]
        for relative, old, new in edits:
            with self.subTest(relative=relative, new=new), tempfile.TemporaryDirectory() as temporary:
                root = self.copy_multi_fixture(temporary, "MULTI-027-01")
                path = root / "multi/MULTI-027-01/repo" / relative
                self.assertIn(old, path.read_bytes())
                path.write_bytes(path.read_bytes().replace(old, new))
                self.assertEqual(multi_relation_type_fixtures.validate(root, {"MULTI-027-01"})["status"], "Failed")
        # 入力の一致の検査と別に、原因の単一性の検査が、入力の木構造と参照計算から拒否する。
        for relative, old, new in edits[:2]:
            with self.subTest(single_cause=relative), tempfile.TemporaryDirectory() as temporary:
                fixture = audit.FIXTURES / "multi/MULTI-027-01"
                repository = Path(temporary) / "repo"
                shutil.copytree(fixture / "repo", repository)
                path = repository / relative
                path.write_bytes(path.read_bytes().replace(old, new))
                result = json.loads((fixture / "expected/context.json").read_text())
                with self.assertRaises(ValueError):
                    multi_relation_type_fixtures.check_single_cause("MULTI-027-01", repository, result)

    def test_multi_check_fixtures(self):
        result = multi_check_fixtures.validate()
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["prepared"], ["MULTI-029-01", "MULTI-029-02", "MULTI-029-03"])
        self.assertEqual(result["core_execution"], "Not run")
        # 複製した状態でも通る（以降の拒否の試験が、複製の不備で空振りしていないことの陽性対照）。
        for identifier in multi_check_fixtures.CASES:
            with self.subTest(identifier=identifier), tempfile.TemporaryDirectory() as temporary:
                root = self.copy_multi_fixture(temporary, identifier)
                self.assertEqual(multi_check_fixtures.validate(root, {identifier})["errors"], [])

    def test_multi_check_reference_follows_the_inputs(self):
        """参照計算は入力の木構造とGitの変更集合から、作業ワークスペース、完全検査の対象、件数、診断を導く。"""
        module = multi_check_fixtures
        expected = {
            "MULTI-029-01": ("full", "apps/web", None, ["api::TECH-020", "platform::REQ-001", "web::TECH-010", "web::TECH-011"]),
            "MULTI-029-02": ("full", ".", "web", ["api::TECH-020", "platform::REQ-001", "web::TECH-010", "web::TECH-011"]),
            "MULTI-029-03": ("changed", "apps/web", None, ["api::TECH-020", "api::TECH-040", "web::TECH-030"]),
        }
        for identifier, (kind, cwd, option, inspected) in expected.items():
            with self.subTest(identifier=identifier), tempfile.TemporaryDirectory() as temporary:
                root = self.copy_multi_fixture(temporary, identifier)
                fixture = root / "multi" / identifier
                manifest = json.loads((fixture / "manifest.json").read_text())
                repository = fixture_setup(fixture, manifest, Path(temporary) / "work" / "repo")
                reference = module.reference_check(repository, kind, "web", cwd, option)
                self.assertEqual(reference["workspace"], {"id": "web", "path": "apps/web"})
                self.assertEqual(reference["inspected"], inspected)
                self.assertEqual(reference["documentCount"], len(inspected))
                result = json.loads((fixture / "expected/check.json").read_text())
                module.check_result_against_reference(result, reference)
                # オプションと実行ディレクトリが作業ワークスペースを決める。ルートの既定は`platform`、メンバーの中は`web`。
                _, workspaces, _ = multi_crosscheck.load_workspaces(repository)
                self.assertEqual(module.select_workspace(workspaces, ".", None), "platform")
                self.assertEqual(module.select_workspace(workspaces, "apps/web", None), "web")
                self.assertEqual(module.select_workspace(workspaces, "apps/web/src", None), "web")
                self.assertEqual(module.select_workspace(workspaces, ".", "api"), "api")
                self.assertEqual(module.select_workspace(workspaces, "apps/web", "platform"), "platform")
                with self.assertRaises(ValueError):
                    module.select_workspace(workspaces, ".", "missing")
                # 作業ワークスペースの取り違え（ルート）では、期待と一致しない。
                with self.assertRaises(ValueError):
                    module.reference_check(repository, kind, "web", ".", None)
                # 期待値の改変（修正前の値、他の範囲、所有ワークスペースの取り違え）を、参照計算との比較が拒否する。
                changes = [lambda v: v["workspace"].update(path="."),
                           lambda v: v["workspace"].update(id="platform", path="."),
                           lambda v: v.update(status="passed" if v["status"] == "failed" else "failed")]
                if kind == "full":
                    changes += [lambda v: v.update(checkedDocumentCount=2), lambda v: v.update(checkedDocumentCount=5),
                                lambda v: v.update(checkedStatementCount=0), lambda v: v.update(checkedStatementCount=2)]
                else:
                    changes += [lambda v: v.update(diagnostics=[]),
                                lambda v: v["selection"].update(targetDocumentCount=3),
                                lambda v: v["selection"].update(changedPathCount=2),
                                lambda v: v["selection"].update(excludedCodeTestPathCount=1),
                                lambda v: v["diagnostics"][0]["source"].update(workspaceId="web"),
                                lambda v: v["diagnostics"][1]["source"].update(workspaceId="platform"),
                                lambda v: v["diagnostics"].reverse(),
                                lambda v: v["diagnostics"].append(copy.deepcopy(v["diagnostics"][0]))]
                for index, change in enumerate(changes):
                    with self.subTest(identifier=identifier, change=index):
                        changed = copy.deepcopy(result)
                        change(changed)
                        self.assertNotEqual(changed, result)
                        with self.assertRaises(ValueError):
                            module.check_result_against_reference(changed, reference)

    def test_multi_check_audit_rejects_changed_expectations(self):
        """修正前の誤検出、`workspace.path`の改変、件数の改変、他のメンバーの診断の所有ワークスペースの改変などを拒否する。"""
        pre_fix = {
            "code": "SPEC-RELATION-MISSING-001", "severity": "error", "resultStatus": "failed",
            "summary": "強い関係の参照先が存在しません", "evidence": "api::TECH-020",
            "source": {"kind": "file", "workspaceId": "web", "path": ".spec/technical/TECH-010.md",
                       "key": "relations.requires"}}

        def false_positive(value):
            value.update(status="failed", diagnostics=[copy.deepcopy(pre_fix)])

        full = [
            false_positive,
            lambda v: v["workspace"].update(path="."),
            lambda v: v["workspace"].update(id="platform", path="."),
            lambda v: v["workspace"].update(id="api", path="services/api"),
            lambda v: v.update(checkedDocumentCount=2),
            lambda v: v.update(checkedDocumentCount=3),
            lambda v: v.update(checkedDocumentCount=5),
            lambda v: v.update(checkedStatementCount=0),
            lambda v: v.update(checkedStatementCount=2),
            lambda v: v.update(scope="selected"),
            lambda v: v["revision"].update(dirty=True),
            lambda v: v.update(status="passed_with_warnings"),
            lambda v: v.update(diagnostics=[{
                "code": "SPEC-RELATION-MISSING-001", "severity": "error", "resultStatus": "failed",
                "summary": "強い関係の参照先が存在しません", "evidence": "TECH-998",
                "source": {"kind": "file", "workspaceId": "api", "path": ".spec/technical/TECH-050.md",
                           "key": "relations.requires"}}], status="failed"),
        ]
        changed = [
            lambda v: v["diagnostics"][0]["source"].update(workspaceId="web"),
            lambda v: v["diagnostics"][0]["source"].update(workspaceId="platform"),
            lambda v: v["diagnostics"][1]["source"].update(workspaceId="web"),
            lambda v: v["diagnostics"][0].update(evidence="api::TECH-999"),
            lambda v: v["diagnostics"][0]["source"].update(path=".spec/technical/TECH-030.md"),
            lambda v: v["diagnostics"].pop(0),
            lambda v: v["diagnostics"].pop(1),
            lambda v: v["diagnostics"].reverse(),
            lambda v: v["diagnostics"].append({
                "code": "SPEC-RELATION-MISSING-001", "severity": "error", "resultStatus": "failed",
                "summary": "強い関係の参照先が存在しません", "evidence": "TECH-996",
                "source": {"kind": "file", "workspaceId": "api", "path": ".spec/technical/TECH-060.md",
                           "key": "relations.requires"}}),
            lambda v: v["diagnostics"].append({
                "code": "SPEC-RELATION-MISSING-001", "severity": "error", "resultStatus": "failed",
                "summary": "強い関係の参照先が存在しません", "evidence": "TECH-998",
                "source": {"kind": "file", "workspaceId": "api", "path": ".spec/technical/TECH-050.md",
                           "key": "relations.requires"}}),
            lambda v: v.update(diagnostics=[], status="passed"),
            lambda v: v["workspace"].update(path="."),
            lambda v: v["workspace"].update(id="platform", path="."),
            lambda v: v["selection"].update(targetDocumentCount=3),
            lambda v: v["selection"].update(targetDocumentCount=0),
            lambda v: v["selection"].update(changedPathCount=2),
            lambda v: v["selection"].update(excludedCodeTestPathCount=1),
            lambda v: v.pop("selection"),
            lambda v: v["revision"].update(dirty=False),
            lambda v: v.update(scope="full", checkedDocumentCount=3, checkedStatementCount=0),
        ]
        mutations = [(identifier, "expected/check.json", change)
                     for identifier in ("MULTI-029-01", "MULTI-029-02") for change in full]
        mutations += [("MULTI-029-03", "expected/check.json", change) for change in changed]
        mutations += [
            ("MULTI-029-01", "manifest.json", lambda v: v["invocation"].update(cwd=".")),
            ("MULTI-029-01", "manifest.json", lambda v: v["invocation"]["argv"].remove("--full")),
            ("MULTI-029-02", "manifest.json", lambda v: v["invocation"]["argv"].__delitem__(slice(1, 3))),
            ("MULTI-029-02", "manifest.json", lambda v: v["invocation"].update(cwd="apps/web")),
            ("MULTI-029-03", "manifest.json", lambda v: v["setup"].update(operations=[])),
            ("MULTI-029-03", "manifest.json", lambda v: v["invocation"].update(cwd=".")),
            ("MULTI-029-03", "manifest.json", lambda v: v["invocation"]["argv"].insert(1, "--full")),
            ("MULTI-029-03", "manifest.json", lambda v: v["expect"].update(status="passed", exitCode=0)),
            ("MULTI-029-01", "side-effects.json", lambda v: v["before"].update(git={"status": "", "index": ""})),
            ("MULTI-029-03", "side-effects.json", lambda v: v["before"].update(git={"status": "", "index": ""})),
        ]
        for index, (identifier, relative, mutate) in enumerate(mutations):
            with self.subTest(index=index, identifier=identifier, file=relative), \
                    tempfile.TemporaryDirectory() as temporary:
                root = self.copy_multi_fixture(temporary, identifier)
                path = root / "multi" / identifier / relative
                value = json.loads(path.read_text())
                before = json.dumps(value, sort_keys=True)
                mutate(value)
                self.assertNotEqual(json.dumps(value, sort_keys=True), before)
                path.write_text(json.dumps(value))
                self.assertEqual(multi_check_fixtures.validate(root, {identifier})["status"], "Failed")

    def test_multi_check_audit_rejects_changed_corpus(self):
        """原因の構成は、無関係な誤りの文書を完全検査の対象に入れず、閉包と直接の逆参照だけを入れることである。入力を変えた写しは拒否する。"""
        module = multi_check_fixtures
        full_ids = ("MULTI-029-01", "MULTI-029-02")
        web_tech = "repo/apps/web/.spec/technical/TECH-010.md"
        api_20 = "repo/services/api/.spec/technical/TECH-020.md"
        api_50 = "repo/services/api/.spec/technical/TECH-050.md"
        api_40 = "repo/services/api/.spec/technical/TECH-040.md"
        api_60 = "repo/services/api/.spec/technical/TECH-060.md"
        web_30 = "changes/TECH-030.md"
        edits = [
            # `--full`: 無関係な文書の誤りを消すと、完全検査の対象に入らないことの陰性対照が成り立たない。
            (full_ids, api_50, "requires: [TECH-998]", "requires: [TECH-020]"),
            # 他のメンバーの文書から作業ワークスペースの文書への参照は、直接の逆参照の解釈に依存するので置かない。
            (full_ids, api_20, "status: approved\n", "status: approved\nrelations:\n  related: [web::TECH-011]\n"),
            (full_ids, api_50, "requires: [TECH-998]", "requires: [TECH-998]\n  refines: [web::TECH-010]"),
            # 2つ目の原因（存在しない参照）と、閉包の変更。
            (full_ids, web_tech, "requires: [api::TECH-020]", "requires: [api::TECH-999]"),
            (full_ids, web_tech, "platform::REQ-001:AC-01", "platform::REQ-001:AC-09"),
            (full_ids, web_tech, "  requires: [api::TECH-020]\n", ""),
            (full_ids, web_tech, "status: approved", "status: draft"),
            (full_ids, "repo/apps/web/.spec/technical/TECH-011.md", "status: approved\n",
             "status: approved\nrelations:\n  requires: [TECH-010]\n"),
            # `changed`: 影響候補を避けるための`draft`、閉包の逆参照と無関係な文書の位置づけ、文書ごとに1件の誤り。
            (("MULTI-029-03",), api_40, "status: draft", "status: approved"),
            (("MULTI-029-03",), api_60, "refines: [TECH-020]", "refines: [web::TECH-030]"),
            (("MULTI-029-03",), api_60, "refines: [TECH-020]", "refines: [TECH-050]"),
            (("MULTI-029-03",), api_50, "requires: [TECH-998]", "requires: [TECH-998]\n  related: [web::TECH-030]"),
            (("MULTI-029-03",), api_40, "requires: [TECH-997]", "requires: [TECH-997, TECH-995]"),
            (("MULTI-029-03",), api_40, "refines: [web::TECH-030]", "refines: [web::TECH-031]"),
            (("MULTI-029-03",), api_20, "requires: [TECH-999]", "requires: [TECH-050]"),
            (("MULTI-029-03",), api_50, "requires: [TECH-998]", "requires: [TECH-020]"),
            (("MULTI-029-03",), web_30, "  requires: [api::TECH-020]\n", ""),
            (("MULTI-029-03",), web_30, "変更後の本文。", "変更前の本文。"),
            (("MULTI-029-03",), "repo/apps/web/.spec/technical/TECH-030.md", "変更前の本文。", "変更後の本文。"),
        ]
        for index, (identifiers, relative, old, new) in enumerate(edits):
            for identifier in identifiers:
                with self.subTest(index=index, identifier=identifier, file=relative), \
                        tempfile.TemporaryDirectory() as temporary:
                    root = self.copy_multi_fixture(temporary, identifier)
                    fixture = root / "multi" / identifier
                    path = fixture / relative
                    self.assertIn(old, path.read_text())
                    path.write_text(path.read_text().replace(old, new))
                    # 入力のバイト列の一致の検査が拒否する。
                    self.assertEqual(module.validate(root, {identifier})["status"], "Failed")
                    # 入力の一致の検査と別に、原因の構成の検査が、入力の木構造から拒否する。
                    manifest = json.loads((fixture / "manifest.json").read_text())
                    repository = fixture_setup(fixture, manifest, Path(temporary) / "work" / "repo")
                    with self.assertRaises(ValueError):
                        module.check_conditions(identifier, repository)
        # 入力のバイト列だけを変える写し、入力の欠落と余分なファイルを拒否する。
        for identifier in module.CASES:
            for name in ("repo/.spec/bitz.yaml", "extra"):
                with self.subTest(identifier=identifier, file=name), tempfile.TemporaryDirectory() as temporary:
                    root = self.copy_multi_fixture(temporary, identifier)
                    fixture = root / "multi" / identifier
                    if name == "extra":
                        (fixture / "repo/extra.txt").write_text("x")
                    else:
                        (fixture / name).unlink()
                    self.assertEqual(module.validate(root, {identifier})["status"], "Failed")

    def test_multi_workspace_option_fixtures(self):
        module = multi_workspace_option_fixtures
        result = module.validate()
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["prepared"], ["MULTI-031-01", "MULTI-031-02"])
        self.assertEqual(result["references"], 2)
        self.assertEqual(result["core_execution"], "Not run")
        # 複製した状態でも通る（以降の拒否の試験が、複製の不備で空振りしていないことの陽性対照）。
        for identifier in module.CASES:
            with self.subTest(identifier=identifier), tempfile.TemporaryDirectory() as temporary:
                root = self.copy_multi_fixture(temporary, identifier)
                self.assertEqual(module.validate(root, {identifier})["errors"], [])

    def test_multi_workspace_option_reference_follows_the_inputs(self):
        """参照計算は、`--workspace`が最寄りの設定より優先されること、同じローカルIDが指す文書が作業ワークスペースで決まることを、入力の木構造から導く。"""
        module = multi_workspace_option_fixtures
        with tempfile.TemporaryDirectory() as temporary:
            root = self.copy_multi_fixture(temporary, "MULTI-031-01")
            fixture = root / "multi/MULTI-031-01"
            manifest = json.loads((fixture / "manifest.json").read_text())
            repository = fixture_setup(fixture, manifest, Path(temporary) / "work" / "repo")
            full = multi_check_fixtures.reference_check(repository, "full", "platform", "apps/web", "platform")
            self.assertEqual(full["workspace"], {"id": "platform", "path": "."})
            self.assertEqual((full["inspected"], full["documentCount"], full["statementCount"], full["diagnostics"]),
                             (["platform::REQ-001"], 1, 2, []))
            # `--workspace`がなければ最寄りの設定の`web`が作業ワークスペースで、期待の`platform`とは一致しない。
            with self.assertRaises(ValueError):
                multi_check_fixtures.reference_check(repository, "full", "platform", "apps/web", None)
            fallback = multi_check_fixtures.reference_check(repository, "full", "web", "apps/web", None)
            self.assertEqual((fallback["workspace"], fallback["inspected"], fallback["statementCount"]),
                             ({"id": "web", "path": "apps/web"}, ["web::REQ-001", "web::TECH-010"], 1))
            # 結果の改変を、参照計算との比較が拒否する。
            result = json.loads((fixture / "expected/check.json").read_text())
            multi_check_fixtures.check_result_against_reference(result, full)
            for index, change in enumerate([
                lambda v: v["workspace"].update(id="web", path="apps/web"),
                lambda v: v["workspace"].update(path="apps/web"),
                lambda v: v["workspace"].update(id="web"),
                lambda v: v.update(checkedDocumentCount=2),
                lambda v: v.update(checkedDocumentCount=4),
                lambda v: v.update(checkedDocumentCount=0),
                lambda v: v.update(checkedStatementCount=1),
                lambda v: v.update(checkedStatementCount=3),
                lambda v: v.update(status="failed"),
                lambda v: v["diagnostics"].append({"code": "SPEC-RELATION-MISSING-001"}),
            ]):
                with self.subTest(change=index):
                    changed = copy.deepcopy(result)
                    change(changed)
                    with self.assertRaises(ValueError):
                        multi_check_fixtures.check_result_against_reference(changed, full)
            # `context`: 非修飾の起点は、`--workspace`、なければ最寄りの設定のワークスペースで解決する。
            platform = module.reference_context(repository, "apps/web", "platform", "REQ-001")
            self.assertEqual((platform["workspace"], platform["roots"]), ({"id": "platform", "path": "."}, ["platform::REQ-001"]))
            self.assertEqual([item["id"] for item in platform["documents"]], ["platform::REQ-001"])
            self.assertEqual(platform["documents"][0]["path"], ".spec/requirements/REQ-001.md")
            self.assertEqual(platform["documents"][0]["statementRefs"], ["platform::REQ-001:AC-01", "platform::REQ-001:AC-02"])
            nearest = module.reference_context(repository, "apps/web", None, "REQ-001")
            self.assertEqual((nearest["workspace"], nearest["roots"]), ({"id": "web", "path": "apps/web"}, ["web::REQ-001"]))
            # 文書の`path`は所有ワークスペースのルートからの相対で、`workspaceId`との組で一意にする。
            self.assertEqual((nearest["documents"][0]["workspaceId"], nearest["documents"][0]["path"]),
                             ("web", ".spec/requirements/REQ-001.md"))
            self.assertEqual(nearest["documents"][0]["statementRefs"], ["web::REQ-001:AC-01"])
            self.assertEqual(module.reference_context(repository, ".", None, "REQ-001")["roots"], ["platform::REQ-001"])
            self.assertEqual(module.reference_context(repository, "apps/web", "platform", "web::REQ-001")["roots"], ["web::REQ-001"])
            expected = json.loads((audit.FIXTURES / "multi/MULTI-031-02/expected/context.json").read_text())
            module.check_context_against_reference(expected, platform)
            with self.assertRaises(ValueError):
                module.check_context_against_reference(expected, nearest)
            for index, change in enumerate([
                lambda v: v["workspace"].update(id="web", path="apps/web"),
                lambda v: v.update(roots=["web::REQ-001"]),
                lambda v: v.update(roots=["REQ-001"]),
                lambda v: v["documents"][0].update(id="web::REQ-001"),
                lambda v: v["documents"][0].update(workspaceId="web"),
                lambda v: v["documents"][0].update(path="apps/web/.spec/requirements/REQ-001.md"),
                lambda v: v["documents"][0]["frontmatter"].update(title="Webの画面の基準"),
                lambda v: v["documents"][0].update(bodyText=v["documents"][0]["bodyText"].replace("ルート", "メンバー")),
                lambda v: v["documents"][0].update(statementRefs=["platform::REQ-001:AC-01"]),
                lambda v: v["documents"][0].update(statementRefs=["REQ-001:AC-01", "REQ-001:AC-02"]),
                lambda v: v["resolution"].update(documentCount=2),
                lambda v: v["resolution"]["workspaces"].append({"id": "web", "path": "apps/web"}),
                lambda v: v["resolution"].update(workspaces=[{"id": "web", "path": "apps/web"}]),
            ]):
                with self.subTest(context_change=index):
                    changed = copy.deepcopy(expected)
                    change(changed)
                    with self.assertRaises(ValueError):
                        module.check_context_against_reference(changed, platform)

    def test_multi_workspace_option_audit_rejects_changed_expectations(self):
        """`workspace`の改変（メンバー、パス）、件数の改変、起点・文書・到達ワークスペースの取り違え、`--workspace`の削除などを拒否する。"""
        module = multi_workspace_option_fixtures
        check_changes = [
            lambda v: v["workspace"].update(id="web", path="apps/web"),
            lambda v: v["workspace"].update(path="apps/web"),
            lambda v: v["workspace"].update(id="web"),
            lambda v: v["workspace"].update(id="api", path="services/api"),
            lambda v: v.update(checkedDocumentCount=2),
            lambda v: v.update(checkedDocumentCount=4),
            lambda v: v.update(checkedDocumentCount=0),
            lambda v: v.update(checkedStatementCount=0),
            lambda v: v.update(checkedStatementCount=1),
            lambda v: v.update(checkedStatementCount=3),
            lambda v: v.update(scope="selected"),
            lambda v: v.update(status="failed"),
            lambda v: v.update(status="passed_with_warnings"),
            lambda v: v["revision"].update(dirty=True),
            lambda v: v.update(diagnostics=[{
                "code": "SPEC-RELATION-MISSING-001", "severity": "error", "resultStatus": "failed",
                "summary": "強い関係の参照先が存在しません", "evidence": "TECH-998",
                "source": {"kind": "file", "workspaceId": "web", "path": ".spec/technical/TECH-010.md",
                           "key": "relations.requires"}}], status="failed"),
            lambda v: v.update(selection={"changedPathCount": 0, "targetDocumentCount": 0, "excludedCodeTestPathCount": 0}),
        ]
        context_changes = [
            lambda v: v["workspace"].update(id="web", path="apps/web"),
            lambda v: v["workspace"].update(path="apps/web"),
            lambda v: v.update(roots=["web::REQ-001"]),
            lambda v: v.update(roots=["REQ-001"]),
            lambda v: v.update(purpose="verify"),
            lambda v: v.update(contextDigest="sha256:" + "0" * 64),
            lambda v: v.update(contextDigest=None),
            lambda v: v.update(status="failed"),
            lambda v: v["revision"].update(dirty=True),
            lambda v: v["documents"][0].update(id="web::REQ-001"),
            lambda v: v["documents"][0].update(workspaceId="web"),
            lambda v: v["documents"][0].update(path="apps/web/.spec/requirements/REQ-001.md"),
            lambda v: v["documents"][0].update(role="refinement"),
            lambda v: v["documents"][0]["frontmatter"].update(title="Webの画面の基準"),
            lambda v: v["documents"][0].update(bodyText=v["documents"][0]["bodyText"].replace("ルート", "メンバー")),
            lambda v: v["documents"][0].update(statementRefs=["platform::REQ-001:AC-01"]),
            lambda v: v["documents"][0].update(reachedBy=["refines:web::TECH-010"]),
            lambda v: v["documents"].append(copy.deepcopy(v["documents"][0])),
            lambda v: v["resolution"].update(documentCount=2),
            lambda v: v["resolution"].update(complete=False),
            lambda v: v["resolution"]["workspaces"].append({"id": "web", "path": "apps/web"}),
            lambda v: v["resolution"].update(workspaces=[{"id": "web", "path": "apps/web"}]),
            lambda v: v["resolution"].update(crossWorkspaceEdges=[
                {"relation": "refines", "source": "web::TECH-010", "target": "platform::REQ-001"}]),
            lambda v: v["constraintLedger"]["statements"].append({"id": "platform::REQ-001:AC-01"}),
            lambda v: v["coverage"]["must"].update(total=["platform::REQ-001:AC-01"]),
            lambda v: v["coverage"].update(adjacent=["platform::REQ-001:AC-02"]),
            lambda v: v.update(diagnostics=[{"code": "CTX-ROOT-MISSING-001"}]),
        ]
        mutations = [("MULTI-031-01", "expected/check.json", change) for change in check_changes]
        mutations += [("MULTI-031-02", "expected/context.json", change) for change in context_changes]
        mutations += [
            # `--workspace`の削除と、別のIDへの変更は、最寄りの設定の`web`が作業ワークスペースになる入力にする。
            ("MULTI-031-01", "manifest.json", lambda v: v["invocation"]["argv"].__delitem__(slice(1, 3))),
            ("MULTI-031-01", "manifest.json", lambda v: v["invocation"]["argv"].__setitem__(2, "web")),
            ("MULTI-031-01", "manifest.json", lambda v: v["invocation"]["argv"].__setitem__(2, "api")),
            ("MULTI-031-01", "manifest.json", lambda v: v["invocation"]["argv"].remove("--full")),
            ("MULTI-031-01", "manifest.json", lambda v: v["invocation"].update(cwd=".")),
            ("MULTI-031-01", "manifest.json", lambda v: v["invocation"].update(cwd="services/api")),
            ("MULTI-031-01", "manifest.json", lambda v: v["setup"].update(operations=[
                {"op": "update", "path": ".spec/requirements/REQ-001.md", "source": "changes/x.md"}])),
            ("MULTI-031-01", "manifest.json", lambda v: v["expect"].update(status="failed", exitCode=1)),
            ("MULTI-031-01", "manifest.json", lambda v: v["expect"].update(exitCode=4)),
            ("MULTI-031-02", "manifest.json", lambda v: v["invocation"]["argv"].__delitem__(slice(1, 3))),
            ("MULTI-031-02", "manifest.json", lambda v: v["invocation"]["argv"].__setitem__(2, "web")),
            ("MULTI-031-02", "manifest.json", lambda v: v["invocation"]["argv"].__setitem__(3, "platform::REQ-001")),
            ("MULTI-031-02", "manifest.json", lambda v: v["invocation"]["argv"].__setitem__(3, "web::REQ-001")),
            ("MULTI-031-02", "manifest.json", lambda v: v["invocation"]["argv"].__setitem__(5, "implement")),
            ("MULTI-031-02", "manifest.json", lambda v: v["invocation"]["argv"].__setitem__(5, "verify")),
            ("MULTI-031-02", "manifest.json", lambda v: v["invocation"].update(cwd=".")),
            ("MULTI-031-02", "manifest.json", lambda v: v["expect"].update(status="failed", exitCode=1)),
            ("MULTI-031-01", "side-effects.json", lambda v: v["before"].update(git={"status": "", "index": ""})),
            ("MULTI-031-02", "side-effects.json", lambda v: v["before"].update(git={"status": "", "index": ""})),
        ]
        for index, (identifier, relative, mutate) in enumerate(mutations):
            with self.subTest(index=index, identifier=identifier, file=relative), \
                    tempfile.TemporaryDirectory() as temporary:
                root = self.copy_multi_fixture(temporary, identifier)
                path = root / "multi" / identifier / relative
                value = json.loads(path.read_text())
                before = json.dumps(value, sort_keys=True)
                mutate(value)
                self.assertNotEqual(json.dumps(value, sort_keys=True), before)
                path.write_text(json.dumps(value))
                self.assertEqual(module.validate(root, {identifier})["status"], "Failed")
        # 正規JSONの改変と、`check`のfixtureへの正規JSONの混入を拒否する。
        with tempfile.TemporaryDirectory() as temporary:
            root = self.copy_multi_fixture(temporary, "MULTI-031-02")
            path = root / "multi/MULTI-031-02/expected/context.canonical.json"
            path.write_bytes(path.read_bytes().replace("ルート".encode(), "メンバー".encode()))
            self.assertEqual(module.validate(root, {"MULTI-031-02"})["status"], "Failed")
        with tempfile.TemporaryDirectory() as temporary:
            root = self.copy_multi_fixture(temporary, "MULTI-031-01")
            (root / "multi/MULTI-031-01/expected/context.canonical.json").write_bytes(b"{}")
            self.assertEqual(module.validate(root, {"MULTI-031-01"})["status"], "Failed")

    def test_multi_workspace_option_audit_rejects_changed_corpus(self):
        """原因の構成は、ルートとメンバーが同じローカルIDのREQを持ち、最寄りの設定の`web`と`--workspace platform`が区別できることである。入力を変えた写しは拒否する。"""
        module = multi_workspace_option_fixtures
        root_req = "repo/.spec/requirements/REQ-001.md"
        web_req = "repo/apps/web/.spec/requirements/REQ-001.md"
        web_tech = "repo/apps/web/.spec/technical/TECH-010.md"
        api_tech = "repo/services/api/.spec/technical/TECH-020.md"
        # 原因の構成の検査が、入力の木構造から拒否する写し。
        breaking = [
            (root_req, "status: approved", "status: draft"),
            (web_req, "status: approved", "status: draft"),
            (web_tech, "status: approved\n", "status: approved\nrelations:\n  refines: [platform::REQ-001:AC-01]\n"),
            (api_tech, "status: approved\n", "status: approved\nrelations:\n  related: [platform::REQ-001]\n"),
            (root_req, "title: ルートの共通基準", "title: Webの画面の基準"),
            (web_req, "title: Webの画面の基準", "title: ルートの共通基準"),
            # ルートとwebの規範文の数が同じになると、最寄りの設定の`web`との区別が件数からできない。
            (web_req, "- [REQ-001:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 画面に利用者のIDを表示しない。\n",
             "- [REQ-001:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 画面に利用者のIDを表示しない。\n"
             "- [REQ-001:AC-02] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 画面に端末の情報を表示しない。\n"),
        ]
        for index, (relative, old, new) in enumerate(breaking):
            for identifier in module.CASES:
                with self.subTest(index=index, identifier=identifier, file=relative), \
                        tempfile.TemporaryDirectory() as temporary:
                    root = self.copy_multi_fixture(temporary, identifier)
                    fixture = root / "multi" / identifier
                    path = fixture / relative
                    self.assertIn(old, path.read_text())
                    path.write_text(path.read_text().replace(old, new))
                    self.assertEqual(module.validate(root, {identifier})["status"], "Failed")
                    manifest = json.loads((fixture / "manifest.json").read_text())
                    repository = fixture_setup(fixture, manifest, Path(temporary) / "work" / "repo")
                    with self.assertRaises(ValueError):
                        module.check_conditions(identifier, repository)
        # 文書の欠落と余分な文書、設定の変更も、入力のバイト列の検査が拒否する。
        for identifier in module.CASES:
            for name in ("repo/.spec/bitz.yaml", web_req, api_tech, "extra"):
                with self.subTest(identifier=identifier, file=name), tempfile.TemporaryDirectory() as temporary:
                    root = self.copy_multi_fixture(temporary, identifier)
                    fixture = root / "multi" / identifier
                    if name == "extra":
                        (fixture / "repo/extra.txt").write_text("x")
                    else:
                        (fixture / name).unlink()
                    self.assertEqual(module.validate(root, {identifier})["status"], "Failed")

    def test_multi_active_workspace_fixtures(self):
        """`MULTI-034-01`〜`05`（`verify`）と`MULTI-035-01`〜`03`（`doctor`）: 作業ワークスペースの決定を固定する（実装の確認事項C24、C38）。"""
        module = multi_active_workspace_fixtures
        result = module.validate()
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["prepared"], [f"MULTI-034-0{number}" for number in range(1, 7)]
                         + [f"MULTI-035-0{number}" for number in range(1, 4)])
        self.assertEqual(result["references"], 2)
        self.assertEqual(result["core_execution"], "Not run")
        # 複製した状態でも通る（以降の拒否の試験が、複製の不備で空振りしていないことの陽性対照）。
        for identifier in module.CASES:
            with self.subTest(identifier=identifier), tempfile.TemporaryDirectory() as temporary:
                root = self.copy_multi_fixture(temporary, identifier)
                self.assertEqual(module.validate(root, {identifier})["errors"], [])

    def test_multi_active_workspace_reference_follows_the_inputs(self):
        """参照計算は、`--workspace`、最寄りの設定、非修飾のIDの解決、既定の対象が作業ワークスペースの文書だけであることを、入力の木構造から導く。"""
        module = multi_active_workspace_fixtures
        with tempfile.TemporaryDirectory() as temporary:
            root = self.copy_multi_fixture(temporary, "MULTI-034-01")
            fixture = root / "multi/MULTI-034-01"
            manifest = json.loads((fixture / "manifest.json").read_text())
            repository = fixture_setup(fixture, manifest, Path(temporary) / "work" / "repo")
            _, workspaces, documents = multi_crosscheck.load_workspaces(repository)
            # 3つのワークスペースが、既定の対象を1件ずつ持つ。統合索引を列挙すると3件が混ざる（陰性対照）。
            self.assertEqual({name: module.default_targets(documents, name) for name in workspaces},
                             {"platform": ["platform::REQ-001"], "web": ["web::TECH-010"], "api": ["api::TECH-010"]})
            for cwd, option, positionals, active, scope, targets, bindings in [
                ("apps/web", None, ["TECH-010"], {"id": "web", "path": "apps/web"}, "selected", ["web::TECH-010"], ["web::frontend"]),
                (".", "web", ["TECH-010"], {"id": "web", "path": "apps/web"}, "selected", ["web::TECH-010"], ["web::frontend"]),
                (".", "web", [], {"id": "web", "path": "apps/web"}, "all", ["web::TECH-010"], ["web::frontend"]),
                (".", None, [], {"id": "platform", "path": "."}, "all", ["platform::REQ-001"], ["web::frontend"]),
                ("apps/web", None, [], {"id": "web", "path": "apps/web"}, "all", ["web::TECH-010"], ["web::frontend"]),
                ("apps/web", "api", ["TECH-010"], {"id": "api", "path": "services/api"}, "selected", ["api::TECH-010"], ["api::backend"]),
                ("services/api", None, [], {"id": "api", "path": "services/api"}, "all", ["api::TECH-010"], ["api::backend"]),
            ]:
                with self.subTest(cwd=cwd, option=option, positionals=positionals):
                    reference = module.reference_verify(repository, cwd, option, positionals)
                    self.assertEqual((reference["workspace"], reference["scope"], reference["status"]), (active, scope, "passed"))
                    self.assertEqual([item["target"] for item in reference["targets"]], targets)
                    self.assertEqual([item["bindingRefs"] for item in reference["targets"]], [bindings])
                    self.assertEqual([item["bindingId"] for item in reference["commands"]], bindings)
            # ルートで非修飾の`TECH-010`を、`--workspace`なしで指定すると、ルートに存在しない。作業ワークスペースで修飾した正規IDの`platform::TECH-010`で
            # `CTX-ROOT-MISSING-001`を返す（`verify` §8）。メンバーの中の存在しない`REQ-009`は`web::REQ-009`。
            missing = module.reference_verify(repository, ".", None, ["TECH-010"])
            self.assertEqual((missing["status"], [item["target"] for item in missing["targets"]], missing["commands"]),
                             ("failed", ["platform::TECH-010"], []))
            missing = module.reference_verify(repository, "apps/web", None, ["REQ-009"])
            self.assertEqual((missing["status"], missing["workspace"], [item["target"] for item in missing["targets"]]),
                             ("failed", {"id": "web", "path": "apps/web"}, ["web::REQ-009"]))
            self.assertEqual(missing["targets"][0]["diagnostics"],
                             [{"code": "CTX-ROOT-MISSING-001", "severity": "error", "resultStatus": "failed",
                               "summary": "起点REQ-009が存在しません",
                               "source": {"kind": "invocation", "argument": "REQ-009"}}])
            self.assertEqual(module.reference_verify(repository, "apps/web", "api", ["REQ-009"])["targets"][0]["target"], "api::REQ-009")
            expected = json.loads((audit.FIXTURES / "multi/MULTI-034-06/expected/verify.json").read_text())
            module.check_verify_against_reference(expected, module.reference_verify(repository, "apps/web", None, ["REQ-009"]))
            for index, change in enumerate([
                lambda v: v["targetResults"][0].update(target="REQ-009"),
                lambda v: v["targetResults"][0].update(target="platform::REQ-009"),
                lambda v: v["targetResults"][0].update(diagnostics=[]),
                lambda v: v["targetResults"][0]["diagnostics"][0]["source"].update(argument="web::REQ-009"),
                lambda v: v["targetResults"][0]["diagnostics"][0].update(code="SPEC-VERIFY-BLOCKED-001"),
                lambda v: v["targetResults"][0].update(status="blocked"),
                lambda v: v.update(status="passed"),
                lambda v: v["targetResults"][0].update(contextDigest="sha256:" + "0" * 64),
                lambda v: v["workspace"].update(id="platform", path="."),
            ]):
                with self.subTest(missing_change=index):
                    changed = copy.deepcopy(expected)
                    change(changed)
                    with self.assertRaises(ValueError):
                        module.check_verify_against_reference(
                            changed, module.reference_verify(repository, "apps/web", None, ["REQ-009"]))
            # 通るリテラルの期待値と、参照計算の一致。他のワークスペースの対象の混入を拒否する。
            for identifier in ("MULTI-034-03", "MULTI-034-04", "MULTI-034-05"):
                with self.subTest(identifier=identifier):
                    case = module.CASES[identifier]
                    expected = json.loads((audit.FIXTURES / f"multi/{identifier}/expected/verify.json").read_text())
                    reference = module.reference_verify(repository, case[module.CWD], case[module.OPTION], case[module.POSITIONALS])
                    module.check_verify_against_reference(expected, reference)
                    mixed = copy.deepcopy(expected)
                    mixed["targetResults"] += [
                        multi_active_workspace_fixtures.target_entry(name, "passed", expected["targetResults"][0]["contextDigest"],
                                                                     bindings=["web::frontend"])
                        for name in ("platform::REQ-001", "web::TECH-010", "api::TECH-010")
                        if name != expected["targetResults"][0]["target"]]
                    with self.assertRaises(ValueError):
                        module.check_verify_against_reference(mixed, reference)
                    mixed = copy.deepcopy(expected)
                    mixed["targetResults"].append(
                        multi_active_workspace_fixtures.target_entry("api::TECH-010", "passed", None, bindings=["api::backend"]))
                    with self.assertRaises(ValueError):
                        module.check_verify_against_reference(mixed, reference)
            # `doctor`: 作業ワークスペースの`id`と`path`は、`--workspace`、なければ最寄りの設定で決まる。
            root = self.copy_multi_fixture(temporary, "MULTI-035-01")
            fixture = root / "multi/MULTI-035-01"
            manifest = json.loads((fixture / "manifest.json").read_text())
            repository = fixture_setup(fixture, manifest, Path(temporary) / "work2" / "repo")
            for cwd, option, active in [
                ("apps/web", "platform", {"id": "platform", "path": "."}),
                (".", "web", {"id": "web", "path": "apps/web"}),
                ("apps/web", None, {"id": "web", "path": "apps/web"}),
                (".", None, {"id": "platform", "path": "."}),
                ("services/api", "web", {"id": "web", "path": "apps/web"}),
            ]:
                with self.subTest(doctor_cwd=cwd, option=option):
                    reference = module.reference_doctor(repository, cwd, option)
                    self.assertEqual((reference["workspace"], reference["status"]), (active, "passed"))
                    self.assertEqual([item["name"] for item in reference["checks"]],
                                     ["core", "workspace", "config", "catalog", "schema", "ears", "git", "command", "impact"])
            # 参照計算の陽性対照: 作業ワークスペースのコマンドが解決できなければ`command`は`blocked`になり、ほかの作業ワークスペースには及ばない。
            web_config = repository / "apps/web/.spec/bitz.yaml"
            web_config.write_text(web_config.read_text() + "verify:\n  commands:\n    frontend:\n      argv: [./missing-command]\n      cwd: .\n")
            blocked = module.reference_doctor(repository, "apps/web", None)
            self.assertEqual(blocked["status"], "blocked")
            self.assertEqual([item["status"] for item in blocked["checks"] if item["name"] == "command"], ["blocked"])
            self.assertEqual(module.reference_doctor(repository, "apps/web", "platform")["status"], "passed")
            # 結果の改変を、参照計算との比較が拒否する。
            expected = json.loads((audit.FIXTURES / "multi/MULTI-035-01/expected/doctor.json").read_text())
            reference = module.reference_doctor(
                fixture_setup(fixture, manifest, Path(temporary) / "work3" / "repo"), "apps/web", "platform")
            module.check_doctor_against_reference(expected, reference)
            for index, change in enumerate([
                lambda v: v["workspace"].update(id="web", path="apps/web"),
                lambda v: v["workspace"].update(path="apps/web"),
                lambda v: v["workspace"].update(id="web"),
                lambda v: v["checks"].pop(),
                lambda v: v["checks"].remove({"name": "catalog", "status": "passed"}),
                lambda v: v["checks"].append({"name": "catalog", "status": "passed"}),
                lambda v: v["checks"][3].update(status="blocked"),
                lambda v: v["checks"][7].update(status="blocked"),
                lambda v: v.update(status="blocked"),
            ]):
                with self.subTest(doctor_change=index):
                    changed = copy.deepcopy(expected)
                    change(changed)
                    with self.assertRaises(ValueError):
                        module.check_doctor_against_reference(changed, reference)

    def test_multi_active_workspace_audit_rejects_changed_expectations(self):
        """`workspace`の改変、`scope`・状態・対象・コマンド・ハッシュ値の改変、他のワークスペースの対象の混入、実行ディレクトリと`--workspace`の改変を拒否する。"""
        module = multi_active_workspace_fixtures
        target = module.target_entry
        other = {"platform": "web", "web": "platform", "api": "web"}

        def swap_workspace(v):
            active = v["workspace"]["id"]
            v["workspace"].update(id=other[active], path="." if other[active] == "platform" else "apps/web")

        verify_changes = [
            swap_workspace,
            lambda v: v["workspace"].update(path="apps/web" if v["workspace"]["path"] == "." else "."),
            lambda v: v["workspace"].update(id="api", path="services/api"),
            lambda v: v.update(scope="all" if v["scope"] == "selected" else "selected"),
            lambda v: v.update(status="failed"),
            lambda v: v.update(status="blocked"),
            lambda v: v.update(status="passed_with_warnings"),
            lambda v: v["revision"].update(dirty=True),
            lambda v: v["targetResults"][0].update(target="TECH-010" if "::" in v["targetResults"][0]["target"] else "x"),
            lambda v: v["targetResults"][0].update(
                target="api::TECH-010" if v["targetResults"][0]["target"] != "api::TECH-010" else "web::TECH-010"),
            lambda v: v["targetResults"][0].update(
                target="platform::REQ-001" if v["targetResults"][0]["target"] != "platform::REQ-001" else "web::TECH-010"),
            lambda v: v["targetResults"][0].update(status="blocked"),
            lambda v: v["targetResults"][0].update(statements=["platform::REQ-001:AC-01"] if not v["targetResults"][0]["statements"] else []),
            lambda v: v["targetResults"][0].update(bindingRefs=[]),
            lambda v: v["targetResults"][0].update(bindingRefs=["api::backend"]),
            lambda v: v["targetResults"][0].update(contextDigest=None),
            lambda v: v["targetResults"][0].update(contextDigest="sha256:" + "0" * 64),
            lambda v: v["targetResults"][0]["diagnostics"].append({"code": "CTX-ROOT-MISSING-001"}),
            lambda v: v["targetResults"].append(target("api::TECH-010", "passed", v["targetResults"][0]["contextDigest"],
                                                      bindings=["api::backend"])),
            lambda v: v["targetResults"].append(target("platform::REQ-001" if v["targetResults"][0]["target"] != "platform::REQ-001"
                                                      else "web::TECH-010", "passed", v["targetResults"][0]["contextDigest"],
                                                      bindings=["web::frontend"])),
            lambda v: v.update(targetResults=[]),
            lambda v: v.update(commands=[]),
            lambda v: v["commands"][0].update(bindingId="api::backend", workspaceId="api", name="backend"),
            lambda v: v["commands"][0].update(tests=["tests/test_audit.py"]),
            lambda v: v["commands"][0].update(covers=["api::TECH-010"]),
            lambda v: v["commands"][0].update(covers=["REQ-001:AC-01"]),
            lambda v: v["commands"][0].update(argv=["/bin/true"]),
            lambda v: v["commands"][0].update(status="failed", exitCode=1),
            lambda v: v["commands"].append(copy.deepcopy(v["commands"][0])),
            lambda v: v["diagnostics"].append({"code": "SPEC-VERIFY-BLOCKED-002"}),
        ]
        doctor_changes = [
            lambda v: v["workspace"].update(id="web" if v["workspace"]["id"] == "platform" else "platform",
                                            path="apps/web" if v["workspace"]["id"] == "platform" else "."),
            lambda v: v["workspace"].update(path="apps/web" if v["workspace"]["path"] == "." else "."),
            lambda v: v["workspace"].update(path="services/api"),
            lambda v: v["workspace"].update(id="api", path="services/api"),
            lambda v: v.update(status="blocked"),
            lambda v: v.update(status="passed_with_warnings"),
            lambda v: v["checks"].pop(),
            lambda v: v["checks"].remove({"name": "catalog", "status": "passed"}),
            lambda v: v["checks"].insert(2, v["checks"].pop(3)),
            lambda v: v["checks"].reverse(),
            lambda v: v["checks"][3].update(status="blocked"),
            lambda v: v["checks"][7].update(status="blocked"),
            lambda v: v["checks"][6].update(status="warning"),
            lambda v: v["checks"][8].update(status="passed"),
            lambda v: v.update(multiWorkspace={"id": "platform", "path": "."}),
            lambda v: v.update(workspaces=[]),
            lambda v: v["diagnostics"].append({"code": "SPEC-DOCTOR-COMMAND-001"}),
            lambda v: v["core"].update(capabilities=[]),
        ]
        missing_changes = [
            swap_workspace,
            lambda v: v["workspace"].update(path="."),
            lambda v: v.update(scope="all"),
            lambda v: v.update(status="blocked"),
            lambda v: v.update(status="passed"),
            lambda v: v["targetResults"][0].update(target="REQ-009"),
            lambda v: v["targetResults"][0].update(target="platform::REQ-009"),
            lambda v: v["targetResults"][0].update(status="blocked"),
            lambda v: v["targetResults"][0].update(contextDigest="sha256:" + "0" * 64),
            lambda v: v["targetResults"][0].update(bindingRefs=["web::frontend"]),
            lambda v: v["targetResults"][0].update(statements=["web::REQ-009:AC-01"]),
            lambda v: v["targetResults"][0].update(diagnostics=[]),
            lambda v: v["targetResults"][0]["diagnostics"][0].update(code="CTX-STATE-001"),
            lambda v: v["targetResults"][0]["diagnostics"][0].update(severity="warning"),
            lambda v: v["targetResults"][0]["diagnostics"][0]["source"].update(argument="web::REQ-009"),
            lambda v: v["targetResults"][0]["diagnostics"][0]["source"].update(kind="file"),
            lambda v: v["targetResults"].append(copy.deepcopy(v["targetResults"][0])),
            lambda v: v["commands"].append(module.web_command()),
            lambda v: v["diagnostics"].append({"code": "CTX-ROOT-MISSING-001"}),
            lambda v: v["revision"].update(dirty=True),
        ]
        mutations = []
        for identifier, (kind, *_rest) in module.CASES.items():
            relative = module.RESULT_FILES[kind]
            for change in (missing_changes if identifier in module.MISSING
                           else verify_changes if kind == "verify" else doctor_changes):
                mutations.append((identifier, relative, change))

        def drop_option(v):
            argv = v["invocation"]["argv"]
            argv.__delitem__(slice(argv.index("--workspace"), argv.index("--workspace") + 2))

        def change_option(value):
            def mutate(v):
                argv = v["invocation"]["argv"]
                argv[argv.index("--workspace") + 1] = value
            return mutate

        def add_option(value):
            return lambda v: v["invocation"]["argv"].insert(1, "--workspace") or v["invocation"]["argv"].insert(2, value)

        def drop_positional(name):
            return lambda v: v["invocation"]["argv"].remove(name)

        def change_positional(name, value):
            return lambda v: v["invocation"]["argv"].__setitem__(v["invocation"]["argv"].index(name), value)

        for identifier, (kind, cwd, argv, option, positionals, *_rest) in module.CASES.items():
            if option is not None:
                for value in ("platform", "web", "api"):
                    if value != option:
                        mutations.append((identifier, "manifest.json", change_option(value)))
                mutations.append((identifier, "manifest.json", drop_option))
            else:
                for value in ("platform", "web", "api"):
                    mutations.append((identifier, "manifest.json", add_option(value)))
            if positionals:
                mutations.append((identifier, "manifest.json", drop_positional(positionals[0])))
                for value in ("api::TECH-010", "web::TECH-010", "web::REQ-009", "TECH-010"):
                    if value != positionals[0]:
                        mutations.append((identifier, "manifest.json", change_positional(positionals[0], value)))
            elif kind == "verify":
                mutations.append((identifier, "manifest.json", lambda v: v["invocation"]["argv"].insert(1, "TECH-010")))
            for value in (".", "apps/web", "services/api"):
                if value != cwd:
                    mutations.append((identifier, "manifest.json", lambda v, value=value: v["invocation"].update(cwd=value)))
            mutations.append((identifier, "manifest.json", lambda v: v["expect"].update(status="blocked", exitCode=2)))
            if identifier in module.MISSING:
                # 期待がすでに`failed`／1なので、`passed`／0への改変を試す。
                mutations.append((identifier, "manifest.json", lambda v: v["expect"].update(status="passed", exitCode=0)))
            else:
                mutations.append((identifier, "manifest.json", lambda v: v["expect"].update(status="failed", exitCode=1)))
            mutations.append((identifier, "manifest.json", lambda v: v["expect"].update(exitCode=4)))
            mutations.append((identifier, "manifest.json", lambda v: v["setup"].update(operations=[
                {"op": "update", "path": ".spec/bitz.yaml", "source": "changes/x.md"}])))
            mutations.append((identifier, "side-effects.json", lambda v: v["before"].update(git={"status": "", "index": ""})))
        for index, (identifier, relative, mutate) in enumerate(mutations):
            with self.subTest(index=index, identifier=identifier, file=relative), \
                    tempfile.TemporaryDirectory() as temporary:
                root = self.copy_multi_fixture(temporary, identifier)
                path = root / "multi" / identifier / relative
                value = json.loads(path.read_text())
                before = json.dumps(value, sort_keys=True)
                mutate(value)
                self.assertNotEqual(json.dumps(value, sort_keys=True), before)
                path.write_text(json.dumps(value))
                self.assertEqual(module.validate(root, {identifier})["status"], "Failed")

    def test_multi_active_workspace_audit_rejects_changed_corpus(self):
        """原因の構成は、3つのワークスペースが既定の対象を1件ずつ持ち、`web`と`api`が同じローカルIDを持つことである。入力を変えた写しは拒否する。"""
        module = multi_active_workspace_fixtures
        web_tech = "repo/apps/web/.spec/technical/TECH-010.md"
        api_tech = "repo/services/api/.spec/technical/TECH-010.md"
        root_req = "repo/.spec/requirements/REQ-001.md"
        # 原因の構成の検査が、入力の木構造から拒否する写し。
        breaking_verify = [
            (root_req, "status: approved", "status: draft"),
            (web_tech, "status: approved", "status: draft"),
            (api_tech, "status: approved", "status: draft"),
            # `api`が既定の対象を持たなくなる（`tests`の削除）。
            (api_tech, "tests:\n  - path: tests/test_audit.py\n    covers: [TECH-010]\n    command: backend\n", ""),
            # `web`が既定の対象を持たなくなる。
            (web_tech, "tests:\n  - path: tests/auth/test_login.py\n    covers: [platform::REQ-001:AC-01]\n    command: frontend\n", ""),
            # `api`の文書が関係を持つ。
            (api_tech, "status: approved\n", "status: approved\nrelations:\n  related: [platform::REQ-001]\n"),
            # `web`と`api`が同じローカルIDでなくなる。
            (api_tech, "id: TECH-010", "id: TECH-020"),
        ]
        for index, (relative, old, new) in enumerate(breaking_verify):
            for identifier in [name for name, case in module.CASES.items() if case[0] == "verify"]:
                with self.subTest(index=index, identifier=identifier, file=relative), \
                        tempfile.TemporaryDirectory() as temporary:
                    root = self.copy_multi_fixture(temporary, identifier)
                    fixture = root / "multi" / identifier
                    path = fixture / relative
                    self.assertIn(old, path.read_text())
                    path.write_text(path.read_text().replace(old, new))
                    self.assertEqual(module.validate(root, {identifier})["status"], "Failed")
                    manifest = json.loads((fixture / "manifest.json").read_text())
                    repository = fixture_setup(fixture, manifest, Path(temporary) / "work" / "repo")
                    with self.assertRaises(ValueError):
                        module.check_conditions(identifier, repository)
        # `doctor`: 仕様文書を置くと、作業ワークスペースの同一性だけを見る構成ではなくなる。
        for identifier in [name for name, case in module.CASES.items() if case[0] == "doctor"]:
            with self.subTest(identifier=identifier, file="document"), tempfile.TemporaryDirectory() as temporary:
                root = self.copy_multi_fixture(temporary, identifier)
                fixture = root / "multi" / identifier
                extra = fixture / "repo/.spec/requirements/REQ-001.md"
                extra.parent.mkdir(parents=True, exist_ok=True)
                extra.write_bytes(module.requirement("REQ-001", "認証の基準", "REQ-001:AC-01").encode())
                self.assertEqual(module.validate(root, {identifier})["status"], "Failed")
                manifest = json.loads((fixture / "manifest.json").read_text())
                repository = fixture_setup(fixture, manifest, Path(temporary) / "work" / "repo")
                with self.assertRaises(ValueError):
                    module.check_conditions(identifier, repository)
        # 文書とテストの欠落、設定の変更と余分なファイルも、入力のバイト列の検査が拒否する。
        for identifier, case in module.CASES.items():
            names = ["repo/.spec/bitz.yaml", "repo/apps/web/.spec/bitz.yaml", "extra"]
            if case[0] == "verify":
                names += [web_tech, api_tech, root_req, "repo/apps/web/tests/auth/test_login.py"]
            for name in names:
                with self.subTest(identifier=identifier, file=name), tempfile.TemporaryDirectory() as temporary:
                    root = self.copy_multi_fixture(temporary, identifier)
                    fixture = root / "multi" / identifier
                    if name == "extra":
                        (fixture / "repo/extra.txt").write_text("x")
                    else:
                        (fixture / name).unlink()
                    self.assertEqual(module.validate(root, {identifier})["status"], "Failed")

    def test_multi_single_precheck_fixtures(self):
        """`MULTI-036-01`〜`13`: 複合ワークスペースの単独操作が全体事前検査で停止すること、停止しない境界を固定する（実装の確認事項C27、ADR-063）。"""
        module = multi_single_precheck_fixtures
        result = module.validate()
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["prepared"], [f"MULTI-036-{number:02d}" for number in range(1, 14)])
        self.assertEqual(result["references"], 1)
        self.assertEqual(result["core_execution"], "Not run")
        # 複製した状態でも通る（以降の拒否の試験が、複製の不備で空振りしていないことの陽性対照）。
        for identifier in module.CASES:
            with self.subTest(identifier=identifier), tempfile.TemporaryDirectory() as temporary:
                root = self.copy_multi_fixture(temporary, identifier)
                self.assertEqual(module.validate(root, {identifier})["errors"], [])

    def single_precheck_repository(self, temporary, identifier, name="work"):
        root = self.copy_multi_fixture(temporary, identifier)
        fixture = root / "multi" / identifier
        manifest = json.loads((fixture / "manifest.json").read_text())
        return root, fixture, manifest, fixture_setup(fixture, manifest, Path(temporary) / name / "repo")

    def test_multi_single_precheck_reference_follows_the_inputs(self):
        """参照計算は、停止の原因と停止結果の`workspace`を、入力の木構造とGitの状態から導く。入力を変えると原因が変わる（陰性対照）。"""
        module = multi_single_precheck_fixtures
        for identifier, case in module.CASES.items():
            with self.subTest(identifier=identifier), tempfile.TemporaryDirectory() as temporary:
                _, _, _, repository = self.single_precheck_repository(temporary, identifier)
                reference = module.reference_decision(repository, case["op"], case["cwd"], case["git"])
                self.assertEqual((reference["cause"], reference["workspace"]), (case["cause"], module.WORKSPACES[identifier]))
        with tempfile.TemporaryDirectory() as temporary:
            # 最も近い設定をカタログに登録するか、登録済みのディレクトリへ移ると、止まらない。
            _, _, manifest, repository = self.single_precheck_repository(temporary, "MULTI-036-01")
            self.assertEqual(module.reference_decision(repository, "check", "apps/web", True)["cause"], None)
            root_config = repository / ".spec/bitz.yaml"
            root_config.write_text(root_config.read_text() + "    - id: x\n      path: tools/x\n")
            self.assertEqual(module.reference_decision(repository, "check", "tools/x", True),
                             {"mode": "multi", "cause": None, "workspace": {"id": "x", "path": "tools/x"}, "unregistered": [], "config": True})
        with tempfile.TemporaryDirectory() as temporary:
            # 単独の`check`は、Gitが認識する設定を列挙しない。`HEAD`にだけある未登録の設定は、`doctor`だけが拾う。
            _, _, _, repository = self.single_precheck_repository(temporary, "MULTI-036-10")
            self.assertEqual(module.reference_decision(repository, "doctor", ".", True)["cause"], "unregistered-git")
            self.assertEqual(module.reference_decision(repository, "check", ".", True)["cause"], None)
            self.assertEqual(module.git_unregistered(repository), ["tools/x/.spec/bitz.yaml"])
            (repository / "tools/x/.spec").mkdir(parents=True, exist_ok=True)
            (repository / "tools/x/.spec/bitz.yaml").write_text(module.tools_config())
            # 作業ツリーに戻しても、Gitが認識する設定の集合は変わらず、選択した設定の照合が別に働く。
            with self.assertRaises(ValueError):
                module.reference_decision(repository, "doctor", "tools/x", True)
        with tempfile.TemporaryDirectory() as temporary:
            # 無視された未追跡の設定は、ルートの`doctor`では止まらず、選択した設定になる`tools/x`の`doctor`だけが止まる。
            _, _, _, repository = self.single_precheck_repository(temporary, "MULTI-036-13")
            self.assertEqual(module.git_unregistered(repository), [])
            self.assertEqual(module.reference_decision(repository, "doctor", ".", True)["cause"], None)
            self.assertEqual(module.reference_decision(repository, "doctor", "tools/x", True)["cause"], "unregistered-selected")
        with tempfile.TemporaryDirectory() as temporary:
            # Git不在: 最も近い設定が`multiWorkspace`を宣言するかどうかで、複合か単一かが決まる（ルートの宣言は、メンバーの中の判定に使わない）。
            _, _, _, repository = self.single_precheck_repository(temporary, "MULTI-036-06")
            self.assertEqual(module.reference_decision(repository, "check", "apps/web", False)["mode"], "single")
            self.assertEqual(module.reference_decision(repository, "check", "apps/web/tests", False)["mode"], "single")
            self.assertEqual(module.reference_decision(repository, "check", ".", False)["cause"], "git")
            # メンバーの設定が`multiWorkspace`を宣言すると、最も近い設定が複合を宣言するので止まる。
            web_config = repository / "apps/web/.spec/bitz.yaml"
            web_config.write_text(web_config.read_text() + "multiWorkspace:\n  members:\n    - id: z\n      path: z\n")
            self.assertEqual(module.reference_decision(repository, "check", "apps/web", False)["cause"], "git")
        with tempfile.TemporaryDirectory() as temporary:
            # 読めないルートの設定は複合と判定しない。読める設定へ戻すと複合になる。
            _, _, _, repository = self.single_precheck_repository(temporary, "MULTI-036-08")
            self.assertEqual(module.reference_decision(repository, "check", ".", True)["mode"], "single")
            root_config = repository / ".spec/bitz.yaml"
            root_config.write_text(root_config.read_text().replace("&label ", ""))
            self.assertEqual(module.reference_decision(repository, "check", ".", True)["mode"], "multi")
        with tempfile.TemporaryDirectory() as temporary:
            # メンバーの設定を足すと、メンバーの不在では止まらない。非対応のメジャーバージョンを戻すと、バージョンでは止まらない。
            _, _, _, repository = self.single_precheck_repository(temporary, "MULTI-036-03")
            self.assertEqual(module.reference_decision(repository, "verify", "apps/web", True)["cause"], "member")
            (repository / "services/api/.spec").mkdir()
            (repository / "services/api/.spec/bitz.yaml").write_text(module.multi_reference.plain_config("api"))
            self.assertIsNone(module.reference_decision(repository, "verify", "apps/web", True)["cause"])
        with tempfile.TemporaryDirectory() as temporary:
            _, _, _, repository = self.single_precheck_repository(temporary, "MULTI-036-07")
            self.assertEqual(module.reference_decision(repository, "context", ".", True)["cause"], "version")
            root_config = repository / ".spec/bitz.yaml"
            root_config.write_text(root_config.read_text().replace('earsAi: "2.0"', 'earsAi: "1.0"'))
            self.assertIsNone(module.reference_decision(repository, "context", ".", True)["cause"])
            root_config.write_text(root_config.read_text().replace('schemaVersion: "1.0"', 'schemaVersion: "2.0"'))
            self.assertEqual(module.reference_decision(repository, "context", ".", True)["cause"], "version")

    def test_multi_single_precheck_audit_rejects_changed_expectations(self):
        """`workspace`、状態、診断のコードと文言、`revision`の有無、`scope`、検査項目、複合固有のフィールド、起動条件の改変を拒否する。"""
        module = multi_single_precheck_fixtures
        stop_changes = [
            lambda v: v.update(status="passed" if v["status"] != "passed" else "blocked"),
            lambda v: v.update(status="failed" if v["status"] != "failed" else "blocked"),
            lambda v: v["workspace"].update(id="web" if v["workspace"]["id"] != "web" else "platform"),
            lambda v: v["workspace"].update(id=None if v["workspace"]["id"] is not None else "x"),
            lambda v: v["workspace"].update(path="apps/web" if v["workspace"]["path"] != "apps/web" else "."),
            lambda v: v["diagnostics"].clear(),
            lambda v: v["diagnostics"].append(copy.deepcopy(v["diagnostics"][0])),
            lambda v: v["diagnostics"][0].update(code="SPEC-MULTI-GIT-001" if v["diagnostics"][0]["code"] != "SPEC-MULTI-GIT-001" else "SPEC-MULTI-UNREGISTERED-001"),
            lambda v: v["diagnostics"][0].update(resultStatus="failed" if v["diagnostics"][0]["resultStatus"] != "failed" else "blocked"),
            lambda v: v["diagnostics"][0].update(severity="info" if v["diagnostics"][0]["severity"] == "warning" else "warning"),
            lambda v: v["diagnostics"][0].update(summary=v["diagnostics"][0]["summary"] + "。"),
            lambda v: v["diagnostics"][0].update(
                summary=module.UNREGISTERED_GIT if v["diagnostics"][0]["summary"] == module.UNREGISTERED_SELECTED else module.UNREGISTERED_SELECTED),
            lambda v: v["diagnostics"][0]["source"].update(workspaceId="web"),
            lambda v: v["diagnostics"][0]["source"].update(path="apps/web/.spec/bitz.yaml"),
            lambda v: v.update(multiWorkspace={"id": "platform", "path": "."}),
            lambda v: v.update(workspaces=[]),
        ]
        by_operation = {
            "check": [
                lambda v: v.update(revision=None if v["revision"] is not None else {"base": module.COMMIT, "commit": module.COMMIT, "dirty": False}),
                lambda v: v.update(scope="changed" if v["scope"] != "changed" else "full"),
                lambda v: v.update(scope="selected"),
                lambda v: v.update(checkedDocumentCount=v["checkedDocumentCount"] + 1) if "checkedDocumentCount" in v else v.update(selection={
                    "changedPathCount": 1, "targetDocumentCount": 0, "excludedCodeTestPathCount": 0}),
                lambda v: v.update(checkedStatementCount=v["checkedStatementCount"] + 1) if "checkedStatementCount" in v else v.pop("selection"),
            ],
            "context": [
                lambda v: v.update(revision=None),
                lambda v: v.update(contextDigest="sha256:" + "0" * 64),
                lambda v: v["resolution"].update(complete=True),
                lambda v: v["resolution"].update(workspaces=[{"id": "web", "path": "apps/web"}], crossWorkspaceEdges=[]),
                lambda v: v["resolution"].update(documentCount=1),
                lambda v: v.update(roots=["REQ-010"]),
                lambda v: v["documents"].append({}),
            ],
            "verify": [
                lambda v: v.update(revision=None),
                lambda v: v.update(scope="selected"),
                lambda v: v.update(targetResults=[{"target": "web::TECH-010"}]),
                lambda v: v["commands"].append({"bindingId": "web::frontend"}),
            ],
            "doctor": [
                lambda v: v["checks"].pop(),
                lambda v: v["checks"].append({"name": "catalog", "status": "blocked"}),
                lambda v: v["checks"].append({"name": "config", "status": "passed"}),
                lambda v: v["checks"].insert(1, {"name": "workspace", "status": "passed"}),
                lambda v: v["checks"].reverse(),
                lambda v: v["checks"][1].update(status="passed" if v["checks"][1]["status"] != "passed" else "blocked"),
                lambda v: v.update(revision={"commit": module.COMMIT, "dirty": False}),
            ],
        }
        mutations = []
        for identifier, case in module.CASES.items():
            relative = module.RESULT_FILES[case["op"]]
            if case["cause"] is not None or identifier in {"MULTI-036-06", "MULTI-036-08"}:
                for change in stop_changes + by_operation[case["op"]]:
                    mutations.append((identifier, relative, change))
            else:
                # 止まらない`verify`: 状態、作業ワークスペース、診断の追加、停止結果の形への改変を拒否する。
                for change in stop_changes[:5] + by_operation["verify"] + [
                        lambda v: v["diagnostics"].append({"code": "SPEC-MULTI-UNREGISTERED-001"}),
                        lambda v: v["targetResults"].clear()]:
                    mutations.append((identifier, relative, change))
            argv = case["argv"]
            mutations.append((identifier, "manifest.json", lambda v: v["expect"].update(status="passed", exitCode=0) if v["expect"]["status"] != "passed"
                              else v["expect"].update(status="blocked", exitCode=2)))
            mutations.append((identifier, "manifest.json", lambda v: v["expect"].update(exitCode=4)))
            for value in (".", "apps/web", "tools/x", "docs"):
                if value != case["cwd"]:
                    mutations.append((identifier, "manifest.json", lambda v, value=value: v["invocation"].update(cwd=value)))
            mutations.append((identifier, "manifest.json", lambda v: v["invocation"]["argv"].insert(1, "--all-workspaces")))
            if "--workspace" in argv:
                mutations.append((identifier, "manifest.json", lambda v: v["invocation"]["argv"].__setitem__(
                    v["invocation"]["argv"].index("--workspace") + 1, "api")))
                mutations.append((identifier, "manifest.json", lambda v: (v["invocation"]["argv"].pop(v["invocation"]["argv"].index("--workspace") + 1),
                                                                         v["invocation"]["argv"].remove("--workspace"))))
            else:
                mutations.append((identifier, "manifest.json", lambda v: v["invocation"]["argv"].insert(1, "--workspace") or v["invocation"]["argv"].insert(2, "web")))
            if case["git"]:
                mutations.append((identifier, "manifest.json", lambda v: v["setup"].update(git=False) or v["setup"].pop("baseCommit")))
                mutations.append((identifier, "manifest.json", lambda v: v["invocation"].update(env={"PATH": "/dev/null"})))
            else:
                mutations.append((identifier, "manifest.json", lambda v: v["invocation"].update(env={})))
                mutations.append((identifier, "manifest.json", lambda v: v["setup"].update(
                    git=True, baseCommit={"message": "base", "paths": ["."]})))
            mutations.append((identifier, "side-effects.json", lambda v: v["before"]["repository"].update(extra={"kind": "directory"})))
        for index, (identifier, relative, mutate) in enumerate(mutations):
            with self.subTest(index=index, identifier=identifier, file=relative), tempfile.TemporaryDirectory() as temporary:
                root = self.copy_multi_fixture(temporary, identifier)
                path = root / "multi" / identifier / relative
                value = json.loads(path.read_text())
                before = json.dumps(value, sort_keys=True)
                mutate(value)
                self.assertNotEqual(json.dumps(value, sort_keys=True), before)
                path.write_text(json.dumps(value))
                self.assertEqual(module.validate(root, {identifier})["status"], "Failed")

    def test_multi_single_precheck_audit_rejects_changed_corpus(self):
        """原因の構成は入力が決める。設定の削除、余分なファイル、カタログへの登録、`.gitignore`の削除、メンバーの設定の追加を拒否する。"""
        module = multi_single_precheck_fixtures
        edits = {
            # 未登録の設定が登録される、またはルートの設定が変わると、原因が消える。
            "MULTI-036-01": [("repo/.spec/bitz.yaml", "      path: services/api\n", "      path: services/api\n    - id: x\n      path: tools/x\n")],
            "MULTI-036-02": [("repo/.spec/bitz.yaml", "      path: services/api\n", "      path: services/api\n    - id: x\n      path: tools/x\n")],
            "MULTI-036-07": [("repo/.spec/bitz.yaml", 'earsAi: "2.0"', 'earsAi: "1.0"')],
            "MULTI-036-08": [("repo/.spec/bitz.yaml", "&label ", "")],
            "MULTI-036-10": [("repo/.spec/bitz.yaml", "      path: services/api\n", "      path: services/api\n    - id: x\n      path: tools/x\n")],
            "MULTI-036-13": [("repo/.gitignore", "tools/x/.spec/", "other/"),
                             ("changes/x-bitz.yaml", "id: x", "id: web")],
            "MULTI-036-06": [("repo/apps/web/.spec/bitz.yaml", "id: web\n", "id: web\nmultiWorkspace:\n  members:\n    - id: z\n      path: z\n")],
            "MULTI-036-12": [("repo/tools/x/.spec/bitz.yaml", "id: x", "id: y")],
        }
        for identifier, changes in edits.items():
            for relative, old, new in changes:
                with self.subTest(identifier=identifier, file=relative), tempfile.TemporaryDirectory() as temporary:
                    root = self.copy_multi_fixture(temporary, identifier)
                    path = root / "multi" / identifier / relative
                    self.assertIn(old, path.read_text())
                    path.write_text(path.read_text().replace(old, new))
                    self.assertEqual(module.validate(root, {identifier})["status"], "Failed")
        # 設定、仕様文書、余分なファイルの欠落と追加も、入力のバイト列の検査が拒否する。
        for identifier, case in module.CASES.items():
            names = ["repo/.spec/bitz.yaml", "repo/apps/web/.spec/bitz.yaml", "repo/services/api/.spec/bitz.yaml", "extra"]
            if identifier == "MULTI-036-13":
                names += ["repo/.gitignore", "changes/x-bitz.yaml"]
            if identifier in {"MULTI-036-01", "MULTI-036-02", "MULTI-036-10", "MULTI-036-12"}:
                names.append("repo/tools/x/.spec/bitz.yaml")
            for name in names:
                if name == "repo/services/api/.spec/bitz.yaml" and identifier in {"MULTI-036-03", "MULTI-036-09", "MULTI-036-12"}:
                    continue
                with self.subTest(identifier=identifier, file=name), tempfile.TemporaryDirectory() as temporary:
                    root = self.copy_multi_fixture(temporary, identifier)
                    fixture = root / "multi" / identifier
                    if name == "extra":
                        (fixture / "repo/extra.txt").write_text("x")
                    else:
                        (fixture / name).unlink()
                    self.assertEqual(module.validate(root, {identifier})["status"], "Failed")
        # メンバー`api`の設定を足すと、`MULTI-036-03`と`MULTI-036-09`の原因が消える。
        for identifier in ("MULTI-036-03", "MULTI-036-09"):
            with self.subTest(identifier=identifier, file="api"), tempfile.TemporaryDirectory() as temporary:
                root = self.copy_multi_fixture(temporary, identifier)
                path = root / "multi" / identifier / "repo/services/api/.spec/bitz.yaml"
                path.parent.mkdir(parents=True)
                path.write_text(module.multi_reference.plain_config("api"))
                self.assertEqual(module.validate(root, {identifier})["status"], "Failed")
                fixture = root / "multi" / identifier
                manifest = json.loads((fixture / "manifest.json").read_text())
                repository = fixture_setup(fixture, manifest, Path(temporary) / "work" / "repo")
                with self.assertRaises(ValueError):
                    module.check_conditions(identifier, repository)

    def exclude_repository(self, temporary, identifier, name="work"):
        root = self.copy_multi_fixture(temporary, identifier)
        fixture = root / "multi" / identifier
        manifest = json.loads((fixture / "manifest.json").read_text())
        return root, fixture, manifest, fixture_setup(fixture, manifest, Path(temporary) / name / "repo")

    def test_multi_exclude_fixtures(self):
        """`MULTI-037-01`〜`27`: 複合ワークスペースの除外の指定と入れ子の複合ワークスペースを固定する（ADR-064）。"""
        module = multi_exclude_fixtures
        result = module.validate()
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["prepared"], [f"MULTI-037-{number:02d}" for number in range(1, 28)])
        self.assertEqual(result["references"], 1)
        self.assertEqual(result["core_execution"], "Not run")
        # 複製した状態でも通る（以降の拒否の試験が、複製の不備で空振りしていないことの陽性対照）。
        for identifier in module.CASES:
            with self.subTest(identifier=identifier), tempfile.TemporaryDirectory() as temporary:
                root = self.copy_multi_fixture(temporary, identifier)
                self.assertEqual(module.validate(root, {identifier})["errors"], [])

    def test_multi_exclude_rules_follow_the_normative_text(self):
        """除外の字句と不正の原因の順（複合ワークスペース仕様 §2、ADR-064 決定1）。"""
        module = multi_exclude_fixtures

        def problem(exclude, members=None):
            members = members if members is not None else [{"id": "web", "path": "apps/web"}]
            return module.exclude_problem({"multiWorkspace": {"members": members, "exclude": exclude}})

        self.assertIsNone(problem([]))
        self.assertIsNone(problem(["cases", "apps/web/tests/data", "generated", "apps/web2"]))
        for value in ("/abs", "", ".", "..", "a/../b", "a//b", "a/", "a/./b", "a/*", "a?b", "a/[b]", "a/b]"):
            with self.subTest(value=value):
                self.assertEqual(problem([value]), "exclude-format")
        self.assertEqual(problem("cases"), "exclude-type")
        self.assertEqual(problem(["a", 1]), "exclude-type")
        self.assertEqual(problem({"a": {}}), "exclude-type")
        self.assertEqual(problem([f"ex{number:03d}" for number in range(100)]), None)
        self.assertEqual(problem([f"ex{number:03d}" for number in range(101)]), "exclude-count")
        self.assertEqual(problem([".spec"]), "exclude-spec")
        self.assertEqual(problem(["a/.spec/b"]), "exclude-spec")
        self.assertIsNone(problem([".specs"]))
        self.assertEqual(problem(["a", "a"]), "exclude-duplicate")
        self.assertEqual(problem(["a", "a/b"]), "exclude-nested")
        self.assertEqual(problem(["a/b", "a"]), "exclude-nested")
        self.assertIsNone(problem(["a", "ab"]))
        # メンバーのパスが除外のパスと同じ、またはその配下: メンバーの配下のディレクトリは除外に書ける。
        self.assertEqual(problem(["apps"]), "member-excluded")
        self.assertEqual(problem(["apps/web"]), "member-excluded")
        self.assertIsNone(problem(["apps/web/tests"]))
        self.assertIsNone(problem(["apps/webx"]))
        # 字句が不正なメンバーのパスは`SPEC-MULTI-PATH-001`（ほかの不備）であり、重なりの判定に使わない（§2.1）。
        self.assertIsNone(problem(["cases"], [{"id": "web", "path": "cases/x/"}]))
        self.assertIsNone(problem(["cases"], [{"id": "web", "path": "../cases"}]))
        self.assertEqual(problem(["cases"], [{"id": "web", "path": "cases/x"}]), "member-excluded")
        # 字句、型、件数、`.spec`、重複、入れ子、メンバーの重なりの順に検査する。
        self.assertEqual(problem(["a/", "a", "a"]), "exclude-format")
        self.assertEqual(problem(["a/.spec", "a"]), "exclude-spec")
        self.assertEqual(problem(["apps", "apps"]), "exclude-duplicate")
        # `multiWorkspace`の設定不適合（`members`の不在・型・0件、`maxMembers`の範囲）は、`exclude`が妥当でも除外を信用しない。
        multi = lambda **fields: module.exclude_problem({"multiWorkspace": fields})
        members = [{"id": "web", "path": "apps/web"}]
        self.assertEqual(multi(exclude=["cases"]), "members-required")
        self.assertEqual(multi(members=[], exclude=["cases"]), "members-required")
        self.assertEqual(multi(members="web", exclude=["cases"]), "members-type")
        self.assertEqual(multi(members={"id": "web"}, exclude=["cases"]), "members-type")
        self.assertIsNone(multi(members=members, exclude=["cases"]))
        self.assertIsNone(multi(members=members, maxMembers="1"))
        self.assertIsNone(multi(members=members, maxMembers="100"))
        for value in ("0", "101", "x", "-1", ""):
            with self.subTest(maxMembers=value):
                self.assertEqual(multi(members=members, maxMembers=value, exclude=["cases"]), "max-members")
        self.assertEqual(multi(maxMembers="0", exclude=["a", "a"]), "max-members")
        self.assertEqual(multi(members="web", exclude=["a", "a"]), "members-type")
        self.assertEqual(module.within("a/b/c", "a/b"), True)
        self.assertEqual(module.within("a/bc", "a/b"), False)
        self.assertEqual(module.within("a/b", "a/b"), True)

    def test_multi_exclude_reference_follows_the_inputs(self):
        """参照計算は、探索の開始位置の場所を、入力の木構造から導く。入力を変えると場所が変わる（陰性対照）。"""
        module = multi_exclude_fixtures

        def rewrite(repository, path, old, new):
            target = repository / path
            self.assertIn(old, target.read_text())
            target.write_text(target.read_text().replace(old, new))

        with tempfile.TemporaryDirectory() as temporary:
            _, _, _, repository = self.exclude_repository(temporary, "MULTI-037-01")
            scope = lambda cwd: module.reference_scope(repository, cwd)
            self.assertEqual(scope(".")["via"], "outer")
            self.assertEqual(scope("apps/web")["via"], "outer")
            self.assertEqual(scope("apps/web")["workspace"], {"id": "web", "path": "apps/web"})
            # 除外した範囲の中: 経路の上に設定がなければ外側の規則、`multiWorkspace`を宣言した設定があれば入れ子、なければ単一ワークスペース。
            self.assertEqual(scope("cases")["via"], "outer")
            self.assertEqual(scope("apps/web/tests/data")["via"], "outer")
            self.assertEqual((scope("cases/single")["kind"], scope("cases/single")["directory"]), ("single", "cases/single"))
            self.assertEqual((scope(module.X_DIRECTORY)["kind"], scope(module.X_DIRECTORY)["directory"]), ("single", module.X_DIRECTORY))
            for cwd in ("cases/nested", "cases/nested/apps", "cases/nested/apps/m", "cases/nested/apps/m/src"):
                with self.subTest(cwd=cwd):
                    nested = scope(cwd)
                    self.assertEqual((nested["kind"], nested["via"], nested["base"]), ("multi", "nested", "cases/nested"))
            self.assertEqual(scope("cases/nested/apps/m")["workspace"], {"id": "m", "path": "apps/m"})
            self.assertEqual(scope("cases/nested")["workspace"], {"id": "nested", "path": "."})
            decision = lambda cwd, argv: module.reference_decision(repository, argv[0], cwd, argv)
            self.assertTrue(decision("cases/single", ["check", "--all-workspaces"])["argument_error"])
            self.assertFalse(decision("cases/nested/apps/m", ["check", "--all-workspaces"])["argument_error"])
            self.assertFalse(decision(".", ["check", "--all-workspaces"])["argument_error"])
            self.assertIsNone(decision(".", ["check", "--all-workspaces"])["cause"])
            # 除外がなければ、除外した範囲の中の4件の設定が未登録になる。
            self.assertEqual(len(module.outer_scope(repository, ".", scope(".")["config"], ".", None, [])["unregistered_git"]), 4)
            self.assertEqual(scope(".")["unregistered_git"], [])
            self.assertEqual(module.expected_workspaces(repository, scope(".")),
                             [("platform", ".", 1, 1), ("api", "services/api", 0, 0), ("web", "apps/web", 0, 0)])
            self.assertEqual(module.expected_workspaces(repository, scope("cases/nested")), [("nested", ".", 1, 1), ("m", "apps/m", 1, 1)])
        with tempfile.TemporaryDirectory() as temporary:
            # `cases`を除外から外すと、`cases/single`は未登録の最も近い設定になる。
            _, _, _, repository = self.exclude_repository(temporary, "MULTI-037-01")
            rewrite(repository, ".spec/bitz.yaml", "    - cases\n", "")
            self.assertEqual(module.reference_scope(repository, "cases/single")["via"], "outer")
            self.assertEqual(module.reference_decision(repository, "check", "cases/single", ["check"])["cause"], "unregistered-selected")
            self.assertEqual(module.reference_decision(repository, "check", ".", ["check", "--all-workspaces"])["cause"], "unregistered-git")
        with tempfile.TemporaryDirectory() as temporary:
            # 除外が不正なら除外を決めない。入れ子のルートの宣言も使わない。
            _, _, _, repository = self.exclude_repository(temporary, "MULTI-037-01")
            rewrite(repository, ".spec/bitz.yaml", "    - cases\n", "    - cases\n    - cases\n")
            self.assertEqual(module.reference_scope(repository, "cases/single")["via"], "outer")
            self.assertEqual(module.reference_decision(repository, "check", "cases/single", ["check"])["cause"], "exclude-duplicate")
            self.assertEqual(module.reference_decision(repository, "check", "cases/nested/apps/m", ["check", "--all-workspaces"])["cause"],
                             "exclude-duplicate")
        with tempfile.TemporaryDirectory() as temporary:
            # ルートの設定が読めないなら、複合ワークスペースと判定せず、最も近い設定を単一ワークスペースとして使う。
            _, _, _, repository = self.exclude_repository(temporary, "MULTI-037-21")
            for cwd, directory in (("cases/nested", "cases/nested"), ("cases/single", "cases/single"), ("apps/web", "apps/web")):
                with self.subTest(cwd=cwd):
                    scope = module.reference_scope(repository, cwd)
                    self.assertEqual((scope["kind"], scope["via"], scope["directory"]), ("single", "plain", directory))
            rewrite(repository, ".spec/bitz.yaml", "&label ", "")
            self.assertEqual(module.reference_scope(repository, "cases/nested")["via"], "nested")
        with tempfile.TemporaryDirectory() as temporary:
            # スキーマまたはEARS-AIのメジャーバージョンが非対応なら、除外を決めない。
            _, _, _, repository = self.exclude_repository(temporary, "MULTI-037-01")
            rewrite(repository, ".spec/bitz.yaml", 'earsAi: "1.0"', 'earsAi: "2.0"')
            scope = module.reference_scope(repository, "cases/single")
            self.assertEqual((scope["via"], scope["problem"], scope["excluded"]), ("outer", None, []))
        with tempfile.TemporaryDirectory() as temporary:
            # 入れ子のルートは、除外のディレクトリに最も近い`multiWorkspace`を宣言した設定である。
            _, _, _, repository = self.exclude_repository(temporary, "MULTI-037-06")
            (repository / "cases/.spec").mkdir()
            (repository / "cases/.spec/bitz.yaml").write_text(module.multi_reference.root_config([("n", "nested")], "outer-case"))
            self.assertEqual(module.reference_scope(repository, "cases/nested/apps/m")["base"], "cases")
            (repository / "cases/.spec/bitz.yaml").write_text(module.multi_reference.plain_config("plain-case"))
            self.assertEqual(module.reference_scope(repository, "cases/nested/apps/m")["base"], "cases/nested")
            # メンバー`m`が宣言しても、最寄りの設定ではなく、除外のディレクトリに最も近い宣言が入れ子のルートである。
            (repository / "cases/nested/apps/m/.spec/bitz.yaml").write_text(module.multi_reference.root_config([("q", "q")], "m"))
            self.assertEqual(module.reference_scope(repository, "cases/nested/apps/m")["base"], "cases/nested")
            # 入れ子のルートが宣言しなければ、開始位置に最も近い設定が単一ワークスペースになる。
            rewrite(repository, "cases/nested/.spec/bitz.yaml", "multiWorkspace:\n  members:\n    - id: m\n      path: apps/m\n", "")
            # 入れ子のルートの宣言がなければ、経路の上の次の宣言（メンバー`m`）が入れ子のルートになる。
            scope = module.reference_scope(repository, "cases/nested/apps/m")
            self.assertEqual((scope["kind"], scope["base"]), ("multi", "cases/nested/apps/m"))
            (repository / "cases/nested/apps/m/.spec/bitz.yaml").write_text(module.multi_reference.plain_config("m"))
            scope = module.reference_scope(repository, "cases/nested/apps/m")
            self.assertEqual((scope["kind"], scope["directory"]), ("single", "cases/nested/apps/m"))
            self.assertTrue(module.reference_decision(repository, "check", "cases/nested/apps/m", ["check", "--all-workspaces"])["argument_error"])
        with tempfile.TemporaryDirectory() as temporary:
            # 読めない設定は`multiWorkspace`を宣言しないものとみなす。
            _, _, _, repository = self.exclude_repository(temporary, "MULTI-037-06")
            rewrite(repository, "cases/nested/.spec/bitz.yaml", "language: ja\n", "language: &label ja\n")
            self.assertFalse(module.declares(repository, "cases/nested"))
            scope = module.reference_scope(repository, "cases/nested/apps/m")
            self.assertEqual((scope["kind"], scope["directory"]), ("single", "cases/nested/apps/m"))
        with tempfile.TemporaryDirectory() as temporary:
            # 外側のほかの不備（メンバーの設定の不在）は、除外の中の操作を止めない。ルートからの操作は止める。
            _, _, _, repository = self.exclude_repository(temporary, "MULTI-037-19")
            self.assertEqual(module.reference_decision(repository, "check", "cases/single", ["check", "--full"])["cause"], None)
            self.assertEqual(module.reference_decision(repository, "check", "apps/web", ["check", "--full"])["cause"], "member-missing")
            (repository / "services/api/.spec").mkdir()
            (repository / "services/api/.spec/bitz.yaml").write_text(module.multi_reference.plain_config("api"))
            self.assertEqual(module.reference_decision(repository, "check", "apps/web", ["check", "--full"])["cause"], None)
        for identifier, cause in (("MULTI-037-24", "members-required"), ("MULTI-037-25", "members-type"),
                                  ("MULTI-037-26", "members-required"), ("MULTI-037-27", "max-members")):
            with self.subTest(identifier=identifier), tempfile.TemporaryDirectory() as temporary:
                # `multiWorkspace`が設定不適合なら、妥当な`exclude: [cases]`も信用せず、外側の全体事前検査で停止する。
                _, _, _, repository = self.exclude_repository(temporary, identifier)
                scope = module.reference_scope(repository, "cases/single")
                self.assertEqual((scope["via"], scope["problem"], scope["excluded"]), ("outer", cause, []))
                self.assertEqual(module.reference_decision(repository, "check", "cases/single", ["check"])["cause"], cause)
                self.assertEqual(module.reference_decision(repository, "check", "cases/nested/apps/m", ["check", "--all-workspaces"])["cause"], cause)
                # 設定不適合を直すと、除外を信用し、`cases/single`は除外の中の単一ワークスペースになる。
                text = (repository / ".spec/bitz.yaml").read_text()
                for old_text in ("  members: web\n", "  members: []\n", "  maxMembers: 0\n"):
                    text = text.replace(old_text, "")
                if "members:" not in text:
                    text = text.replace("multiWorkspace:\n", "multiWorkspace:\n  members:\n    - id: web\n      path: apps/web\n", 1)
                (repository / ".spec/bitz.yaml").write_text(text)
                scope = module.reference_scope(repository, "cases/single")
                self.assertEqual((scope["kind"], scope["directory"]), ("single", "cases/single"))
        with tempfile.TemporaryDirectory() as temporary:
            # 入れ子のルートの外の変更は、変更集合に入らない。リポジトリのルートを基準にすると5件になる。
            _, _, _, repository = self.exclude_repository(temporary, "MULTI-037-23")
            self.assertEqual(len(module.changed_paths(repository)), 5)
            self.assertEqual(module.selection_counts(repository, "cases/nested"), (2, 1, 1))
            self.assertNotEqual(module.selection_counts(repository, "."), (2, 1, 1))
        with tempfile.TemporaryDirectory() as temporary:
            # 入れ子の中の未登録の設定だけが、入れ子のルート相対で報告される。登録すると止まらない。
            _, _, _, repository = self.exclude_repository(temporary, "MULTI-037-22")
            scope = module.reference_scope(repository, "cases/nested")
            self.assertEqual(scope["unregistered_git"], ["tools/z/.spec/bitz.yaml"])
            rewrite(repository, "cases/nested/.spec/bitz.yaml", "      path: apps/m\n", "      path: apps/m\n    - id: z\n      path: tools/z\n")
            self.assertEqual(module.reference_scope(repository, "cases/nested")["unregistered_git"], [])

    def test_multi_exclude_reference_rejects_inconsistent_expectations(self):
        """レビュー済みの期待値（`CASES`）を入力と食い違うように変えると、参照計算との照合が拒否する。"""
        module = multi_exclude_fixtures

        def with_expected(identifier, **changes):
            def mutate(cases):
                cases[identifier]["expected"].update(changes)
            return mutate

        def with_case(identifier, **changes):
            def mutate(cases):
                cases[identifier].update(changes)
            return mutate

        mutations = [
            ("MULTI-037-01", with_expected("MULTI-037-01", workspaces=[("platform", ".", 1, 1), ("api", "services/api", 0, 0)])),
            ("MULTI-037-01", with_expected("MULTI-037-01", workspaces=[("platform", ".", 1, 1), ("web", "apps/web", 0, 0), ("api", "services/api", 0, 0)])),
            ("MULTI-037-01", with_expected("MULTI-037-01", workspaces=[("platform", ".", 2, 1), ("api", "services/api", 0, 0), ("web", "apps/web", 0, 0)])),
            ("MULTI-037-01", with_expected("MULTI-037-01", workspaces=[("platform", ".", 1, 1), ("api", "services/api", 0, 0), ("web", "apps/web", 0, 0),
                                                                       ("single", "cases/single", 1, 1)])),
            ("MULTI-037-01", with_expected("MULTI-037-01", dirty=True)),
            ("MULTI-037-01", with_expected("MULTI-037-01", root="nested")),
            ("MULTI-037-02", with_expected("MULTI-037-02", workspace={"id": "web", "path": "apps/web"})),
            ("MULTI-037-03", with_expected("MULTI-037-03", workspace={"id": "root", "path": "."})),
            ("MULTI-037-03", with_expected("MULTI-037-03", workspace={"id": "single", "path": "cases/single"})),
            ("MULTI-037-03", with_expected("MULTI-037-03", counts=(2, 1))),
            ("MULTI-037-03", with_expected("MULTI-037-03", counts=(0, 0))),
            ("MULTI-037-05", with_expected("MULTI-037-05", workspace={"id": "platform", "path": "."})),
            ("MULTI-037-05", with_expected("MULTI-037-05", counts=(2, 1))),
            ("MULTI-037-06", with_expected("MULTI-037-06", workspaces=[("nested", ".", 1, 1)])),
            ("MULTI-037-06", with_expected("MULTI-037-06", workspaces=[("platform", ".", 1, 1), ("api", "services/api", 0, 0), ("web", "apps/web", 0, 0)],
                                           root="platform")),
            ("MULTI-037-06", with_expected("MULTI-037-06", workspaces=[("nested", ".", 1, 1), ("m", "cases/nested/apps/m", 1, 1)])),
            ("MULTI-037-06", with_expected("MULTI-037-06", root="platform")),
            ("MULTI-037-07", with_expected("MULTI-037-07", workspaces=[("m", "apps/m", 1, 1), ("nested", ".", 1, 1)])),
            ("MULTI-037-07", with_expected("MULTI-037-07", root="platform")),
            ("MULTI-037-08", with_expected("MULTI-037-08", workspace={"id": "x", "path": "."})),
            ("MULTI-037-08", with_expected("MULTI-037-08", dirty=True)),
            ("MULTI-037-09", with_case("MULTI-037-09", cause="exclude-spec")),
            ("MULTI-037-11", with_case("MULTI-037-11", cause="exclude-nested")),
            ("MULTI-037-12", with_case("MULTI-037-12", cause="exclude-duplicate")),
            ("MULTI-037-14", with_case("MULTI-037-14", cause="exclude-format")),
            ("MULTI-037-15", with_case("MULTI-037-15", cause="exclude-type")),
            ("MULTI-037-16", with_case("MULTI-037-16", cause="exclude-format")),
            ("MULTI-037-16", with_case("MULTI-037-16", status="blocked", exit=2)),
            ("MULTI-037-17", with_case("MULTI-037-17", cause=None, status="passed", exit=0)),
            ("MULTI-037-18", with_expected("MULTI-037-18", workspace={"id": "single", "path": "cases/single"})),
            ("MULTI-037-18", with_expected("MULTI-037-18", workspace={"id": None, "path": "."})),
            ("MULTI-037-18", with_case("MULTI-037-18", cause="exclude-nested")),
            ("MULTI-037-18", with_case("MULTI-037-18", cause=None, status="passed", exit=0)),
            ("MULTI-037-19", with_case("MULTI-037-19", cause="member-missing", status="failed", exit=1)),
            ("MULTI-037-19", with_expected("MULTI-037-19", workspace={"id": None, "path": "cases/single"})),
            ("MULTI-037-20", with_expected("MULTI-037-20", workspaces=[("platform", ".", 1, 1), ("api", "services/api", 0, 0)])),
            ("MULTI-037-21", with_expected("MULTI-037-21", workspace={"id": "root", "path": "."})),
            ("MULTI-037-21", with_case("MULTI-037-21", cause="exclude-format", status="failed", exit=1)),
            ("MULTI-037-22", with_expected("MULTI-037-22", unregistered=["cases/nested/tools/z/.spec/bitz.yaml"])),
            ("MULTI-037-22", with_expected("MULTI-037-22", unregistered=["tools/z/.spec/bitz.yaml", "apps/web/.spec/bitz.yaml"])),
            ("MULTI-037-22", with_case("MULTI-037-22", cause=None, status="passed", exit=0)),
            ("MULTI-037-24", with_case("MULTI-037-24", cause="members-type")),
            ("MULTI-037-24", with_expected("MULTI-037-24", workspace={"id": "single", "path": "."})),
            ("MULTI-037-24", with_case("MULTI-037-24", cause=None, status="passed", exit=0)),
            ("MULTI-037-25", with_case("MULTI-037-25", cause="members-required")),
            ("MULTI-037-26", with_case("MULTI-037-26", cause="exclude-format")),
            ("MULTI-037-27", with_case("MULTI-037-27", cause="members-required")),
            ("MULTI-037-27", with_expected("MULTI-037-27", workspace={"id": "platform", "path": "."})),
            ("MULTI-037-23", with_expected("MULTI-037-23", selection=(5, 2, 3))),
            ("MULTI-037-23", with_expected("MULTI-037-23", selection=(2, 1, 0))),
            ("MULTI-037-23", with_expected("MULTI-037-23", dirty=False)),
        ]
        for index, (identifier, mutate) in enumerate(mutations):
            with self.subTest(index=index, identifier=identifier), tempfile.TemporaryDirectory() as temporary:
                root = self.copy_multi_fixture(temporary, identifier)
                cases = copy.deepcopy(module.CASES)
                mutate(cases)
                self.assertNotEqual(cases[identifier], module.CASES[identifier])
                with patch.object(module, "CASES", cases):
                    # 入力は変えずに、期待値だけを変えた結果を書き、監査が参照計算で拒否することを確かめる。
                    fixture = root / "multi" / identifier
                    if module.has_result(identifier):
                        (fixture / module.RESULT_FILES[module.operation(identifier)]).write_text(
                            json.dumps(module.reviewed_result(identifier), ensure_ascii=False, indent=2) + "\n")
                    (fixture / "manifest.json").write_text(json.dumps(module.reviewed_manifest(identifier), ensure_ascii=False, indent=2) + "\n")
                    self.assertEqual(module.validate(root, {identifier})["status"], "Failed")

    def test_multi_exclude_audit_rejects_changed_files(self):
        """期待結果、起動条件、副作用の改変を拒否する。"""
        module = multi_exclude_fixtures
        results = {
            "status": lambda v: v.update(status="passed" if v["status"] != "passed" else "blocked"),
            "diagnostics-clear": lambda v: v["diagnostics"].clear(),
            "diagnostics-add": lambda v: v["diagnostics"].append({"code": "SPEC-MULTI-GIT-001"}),
            "summary": lambda v: v["diagnostics"][0].update(summary=v["diagnostics"][0]["summary"] + "。"),
            "source-key": lambda v: v["diagnostics"][0]["source"].update(key="multiWorkspace.members"),
            "source-workspace": lambda v: v["diagnostics"][0]["source"].update(workspaceId=None),
            "workspace": lambda v: v["workspace"].update(path="apps/web"),
            "multi": lambda v: v["multiWorkspace"].update(id="web"),
            "workspaces-reverse": lambda v: v["workspaces"].reverse(),
            "workspaces-count": lambda v: v["workspaces"][0].update(checkedDocumentCount=v["workspaces"][0].get("checkedDocumentCount", 0) + 1),
            "revision": lambda v: v.update(revision=None),
            "revision-dirty": lambda v: v["revision"].update(dirty=not v["revision"]["dirty"]),
            "selection": lambda v: v["selection"].update(changedPathCount=v["selection"]["changedPathCount"] + 1),
            "counts": lambda v: v.update(checkedStatementCount=v["checkedStatementCount"] + 1),
            "checks-pop": lambda v: v["checks"].pop(),
            "digest": lambda v: v["targetResults"][0].update(contextDigest="sha256:" + "0" * 64),
        }
        manifests = {
            "status": lambda v: v["expect"].update(status="passed" if v["expect"].get("status") != "passed" else "blocked"),
            "exit-code": lambda v: v["expect"].update(exitCode=3),
            "cwd": lambda v: v["invocation"].update(cwd="." if v["invocation"]["cwd"] != "." else "cases/single"),
            "argv-all": lambda v: v["invocation"]["argv"].insert(1, "--all-workspaces"),
            "argv-workspace": lambda v: v["invocation"]["argv"].insert(1, "--workspace") or v["invocation"]["argv"].insert(2, "web"),
            "env": lambda v: v["invocation"].update(env={"PATH": "/dev/null"}),
            "no-git": lambda v: v["setup"].update(git=False) or v["setup"].pop("baseCommit"),
            "operations": lambda v: v["setup"]["operations"].append({"op": "delete", "path": ".spec/bitz.yaml"}),
        }
        cli_outputs = {
            "exit": lambda v: v.update(exitCode=3),
            "stdout": lambda v: v.update(stdout="x"),
            "prefix": lambda v: v.update(stderrPrefix="bitz: verify: "),
            "lines": lambda v: v.update(stderrLineCount=2),
            "reason": lambda v: v.update(stderrReasonRequired=False),
        }
        mutations = []
        for identifier in module.CASES:
            case = module.CASES[identifier]
            relative = module.RESULT_FILES[case["op"]]
            if module.has_result(identifier):
                for name, change in results.items():
                    mutations.append((identifier, relative, name, change))
            for name, change in manifests.items():
                mutations.append((identifier, "manifest.json", name, change))
            mutations.append((identifier, "side-effects.json", "extra", lambda v: v["before"]["repository"].update(extra={"kind": "directory"})))
            mutations.append((identifier, "side-effects.json", "policy", lambda v: v.update(policy="read-write")))
            if not module.has_result(identifier):
                for name, change in cli_outputs.items():
                    mutations.append((identifier, "cli-output.json", name, change))
        applied = skipped = 0
        for index, (identifier, relative, name, mutate) in enumerate(mutations):
            with tempfile.TemporaryDirectory() as temporary:
                root = self.copy_multi_fixture(temporary, identifier)
                path = root / "multi" / identifier / relative
                value = json.loads(path.read_text())
                before = json.dumps(value, sort_keys=True)
                try:
                    mutate(value)
                except (KeyError, IndexError, TypeError, AttributeError):
                    skipped += 1
                    continue
                if json.dumps(value, sort_keys=True) == before:
                    skipped += 1
                    continue
                applied += 1
                path.write_text(json.dumps(value))
                with self.subTest(index=index, identifier=identifier, file=relative, mutation=name):
                    self.assertEqual(module.validate(root, {identifier})["status"], "Failed")
        # 改変の適用が空振りしていないこと: 結果を持つ22件のそれぞれに、状態と診断の改変が少なくとも1件は適用される。
        self.assertGreater(applied, 250)

    def test_multi_exclude_audit_rejects_changed_corpus(self):
        """入力の欠落と追加（バイト列の照合）と、原因を消す入力の書換え（参照計算と原因の構成の検査）を拒否する。"""
        module = multi_exclude_fixtures
        for identifier in module.CASES:
            repo, changes = module.reviewed_inputs(identifier)
            names = sorted(f"repo/{name}" for name in repo if name.endswith("/bitz.yaml") or name.endswith("bitz.yaml"))
            names += [f"changes/{name}" for name in changes]
            for name in [*names, "extra"]:
                with self.subTest(identifier=identifier, file=name), tempfile.TemporaryDirectory() as temporary:
                    root = self.copy_multi_fixture(temporary, identifier)
                    fixture = root / "multi" / identifier
                    if name == "extra":
                        (fixture / "repo/extra.txt").write_text("x")
                    else:
                        (fixture / name).unlink()
                    self.assertEqual(module.validate(root, {identifier})["status"], "Failed")
        # 原因を作る設定の書換え。入力のバイト列の照合を通した上で（`reviewed_inputs`を書換え後の内容にし、副作用の期待値を作り直す）、
        # 参照計算と原因の構成の検査が拒否することを確かめる（陰性対照。バイト列の照合で先に拒否される空振りを避ける）。
        valid_members = "multiWorkspace:\n  members:\n    - id: web\n      path: apps/web\n    - id: api\n      path: services/api\n"
        edits = {
            "MULTI-037-01": [(".spec/bitz.yaml", "    - cases\n", "")],
            "MULTI-037-05": [("cases/nested/.spec/bitz.yaml", "multiWorkspace:", "other:")],
            "MULTI-037-06": [("cases/nested/.spec/bitz.yaml", "multiWorkspace:", "other:")],
            "MULTI-037-09": [(".spec/bitz.yaml", "../x", "x")],
            "MULTI-037-13": [(".spec/bitz.yaml", "cases/x/.spec", "cases/x/spec")],
            "MULTI-037-15": [(".spec/bitz.yaml", "    - ex101\n", "")],
            "MULTI-037-16": [(".spec/bitz.yaml", "    - apps\n", "    - appz\n")],
            "MULTI-037-18": [(".spec/bitz.yaml", "    - cases\n    - cases\n", "    - cases\n")],
            "MULTI-037-21": [(".spec/bitz.yaml", "&label ", "")],
            "MULTI-037-22": [("cases/nested/.spec/bitz.yaml", "      path: apps/m\n", "      path: apps/m\n    - id: z\n      path: tools/z\n")],
            "MULTI-037-24": [(".spec/bitz.yaml", "multiWorkspace:\n", valid_members)],
            "MULTI-037-25": [(".spec/bitz.yaml", "  members: web\n", valid_members.split("\n", 1)[1])],
            "MULTI-037-26": [(".spec/bitz.yaml", "  members: []\n", valid_members.split("\n", 1)[1])],
            "MULTI-037-27": [(".spec/bitz.yaml", "  maxMembers: 0\n", "")],
        }
        byte_phrases = ("入力がレビュー済みのcorpusと異なります", "隔離した準備手順が固定したスナップショットと異なります")
        for identifier, changes in edits.items():
            for relative, old, new in changes:
                with self.subTest(identifier=identifier, file=relative), tempfile.TemporaryDirectory() as temporary:
                    root = self.copy_multi_fixture(temporary, identifier)
                    fixture = root / "multi" / identifier
                    path = fixture / "repo" / relative
                    self.assertIn(old, path.read_text())
                    path.write_text(path.read_text().replace(old, new))
                    edited = module.reviewed_inputs(identifier)
                    repo = {name: data for name, data in edited[0].items()}
                    repo[relative] = path.read_bytes()
                    manifest = json.loads((fixture / "manifest.json").read_text())
                    repository = fixture_setup(fixture, manifest, Path(temporary) / "regen" / "repo")
                    external = {key: Path(temporary) / "regen" / key for key in ("home", "cache", "temporary")}
                    for directory in external.values():
                        directory.mkdir()
                    state = module.observe_state(manifest, repository, external)
                    (fixture / "side-effects.json").write_text(json.dumps({"schemaVersion": "1.0", "policy": "read-only", "before": state, "after": state}))
                    with patch.object(module, "reviewed_inputs", lambda _identifier, repo=repo, changes=edited[1]: (repo, changes)):
                        outcome = module.validate(root, {identifier})
                    self.assertEqual(outcome["status"], "Failed")
                    self.assertEqual(len(outcome["errors"]), 1)
                    # 入力のバイト列とスナップショットは一致している。拒否したのは、参照計算または原因の構成の検査である。
                    self.assertFalse(any(phrase in outcome["errors"][0] for phrase in byte_phrases), outcome["errors"][0])
                    self.assertNotIn("KeyError", outcome["errors"][0])
                    self.assertNotRegex(outcome["errors"][0], r": '[A-Za-z_]+'$")

    def test_multi_closure_alias_fixtures(self):
        """`MULTI-038-01`〜`22`: 閉包の循環・別名の二重収録・`evidence`の修飾・`interpret`のADRを固定する（確認事項C18・C21・C19・D7）。"""
        module = multi_closure_alias_fixtures
        result = module.validate()
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["prepared"], [f"MULTI-038-{number:02d}" for number in range(1, 23)])
        self.assertEqual(result["references"], 2)
        self.assertEqual(result["core_execution"], "Not run")
        # 複製した状態でも通る（以降の拒否の試験が、複製の不備で空振りしていないことの陽性対照）。
        for identifier in module.CASES:
            with self.subTest(identifier=identifier), tempfile.TemporaryDirectory() as temporary:
                root = self.copy_multi_fixture(temporary, identifier)
                self.assertEqual(module.validate(root, {identifier})["errors"], [])

    def test_multi_closure_alias_reference_rules(self):
        """循環に参加するエッジ、閉包、別名の表記の参照計算（関係・トレースモデル §4・§6・§7）。"""
        module = multi_closure_alias_fixtures

        def document(workspace, identifier, kind="technical", status="approved", **relations):
            return {"workspaceId": workspace, "kind": kind, "body": "", "path": f"{identifier}.md",
                    "frontmatter": {"id": identifier, "title": "t", "status": status,
                                    "relations": {key: value for key, value in relations.items()}}}

        # 2文書の循環と、循環へ入るだけのエッジ。入るだけのエッジ（`a→b`の`a`）は循環に参加しない。
        documents = {"w::a": document("w", "a", requires=["b"]), "w::b": document("w", "b", requires=["c"]),
                     "w::c": document("w", "c", requires=["b"])}
        self.assertEqual(module.cyclic_edges(documents), {("w::b", "requires"), ("w::c", "requires")})
        # 自己参照は長さ1の循環。`related`は循環に数えない。
        self.assertEqual(module.cyclic_edges({"w::a": document("w", "a", requires=["a"])}), {("w::a", "requires")})
        self.assertEqual(module.cyclic_edges({"w::a": document("w", "a", related=["a"])}), set())
        # `requires`と`refines`を合わせた循環。
        mixed = {"w::a": document("w", "a", requires=["b"]), "w::b": document("w", "b", refines=["a"])}
        self.assertEqual(module.cyclic_edges(mixed), {("w::a", "requires"), ("w::b", "refines")})
        # 閉包は到達できる文書だけ。表記が違っても1件にまとめ、到達したエッジを両方保つ。
        documents = {"w::r": document("w", "r", requires=["t", "u"]), "w::t": document("w", "t"),
                     "w::u": document("w", "u", requires=["x::v"]), "x::v": document("x", "v", requires=["w::t"]),
                     "w::z": document("w", "z", requires=["z"])}
        order, edges, distance = module.interpret_closure(documents, "w::r")
        self.assertEqual(order, ["w::r", "w::t", "w::u", "x::v"])
        self.assertEqual(edges["w::t"], {("requires", "w::r"), ("requires", "x::v")})
        self.assertEqual(distance, {"w::r": 0, "w::t": 1, "w::u": 1, "x::v": 2})
        self.assertEqual(module.spellings(documents, "w::t"), {"t", "w::t"})
        # 診断は閉包の文書だけ。閉包の外の循環（`w::z`）は返さない。
        self.assertEqual(module.reference_diagnostics(documents, order), [])
        self.assertEqual([item["source"]["path"] for item in module.reference_diagnostics(documents, [*order, "w::z"])], [".spec/technical/z.md"])
        # 起点を（修飾した宣言で）`refines`する文書は具体化文書として含め、置換済みの起点は後継を距離1で含める。
        documents = {"w::r": document("w", "r", kind="requirement"), "x::t": document("x", "t", refines=["w::r"]),
                     "w::s": document("w", "s", kind="requirement", supersedes=["r"])}
        order, edges, distance = module.interpret_closure(documents, "w::r")
        self.assertEqual(order, ["w::r", "x::t", "w::s"])
        self.assertEqual((distance["x::t"], distance["w::s"]), (1, 1))
        self.assertEqual([module.role_of(documents, "w::r", name, edges) for name in order], ["advisory", "refinement", "replacement"])
        # 他のメンバーの文書が起点を置換するときも後継に数え、状態`draft`の具体化文書は役割`advisory`で含めてその`requires`を辿らない。
        documents = {"w::r": document("w", "r", kind="requirement"), "x::s": document("x", "s", kind="requirement", supersedes=["w::r"]),
                     "x::d": document("x", "d", status="draft", refines=["w::r"], requires=["x::e"]), "x::e": document("x", "e")}
        order, edges, _ = module.interpret_closure(documents, "w::r")
        self.assertEqual(module.successors_of(documents, "w::r"), ["x::s"])
        self.assertEqual(order, ["w::r", "x::d", "x::s"])
        self.assertEqual([module.role_of(documents, "w::r", name, edges) for name in order], ["advisory", "advisory", "replacement"])
        self.assertEqual(module.reference_state_diagnostics(documents, "w::r")[0]["code"], "CTX-STATE-SUPERSEDED-001")
        # 目的`implement`: 他のメンバーの状態`open`のTASKが起点の規範文を`addresses`すると、距離1で含める。
        documents = {"w::r": dict(document("w", "r", kind="requirement"), body="- [r:AC-01] [ACTOR:A] [ALWAYS] [MUST] [CONSTRAINT] x。\n"),
                     "x::t": document("x", "t", kind="task", status="open", addresses=["w::r:AC-01"])}
        order, edges, distance = module.interpret_closure(documents, "w::r", "implement")
        self.assertEqual((order, distance["x::t"], module.role_of(documents, "w::r", "x::t", edges)), (["w::r", "x::t"], 1, "work"))

    def test_multi_closure_alias_audit_rejects_changed_expectations(self):
        """期待結果・起動条件・副作用の改変を拒否する。"""
        module = multi_closure_alias_fixtures
        results = {
            "status": lambda v: v.update(status="passed" if v["status"] != "passed" else "failed"),
            "diagnostics-clear": lambda v: v["diagnostics"].clear(),
            "diagnostics-add": lambda v: v["diagnostics"].append({"code": "CTX-CYCLE-001"}),
            "summary": lambda v: v["diagnostics"][0].update(summary=v["diagnostics"][0]["summary"] + "。"),
            "evidence": lambda v: v["diagnostics"][0].update(evidence=v["diagnostics"][0]["evidence"].rpartition("::")[2]),
            "evidence-qualify": lambda v: v["diagnostics"][0].update(evidence="api::" + v["diagnostics"][0]["evidence"]),
            "source-workspace": lambda v: v["diagnostics"][0]["source"].update(workspaceId="platform"),
            "source-key": lambda v: v["diagnostics"][0]["source"].update(key="relations.refines"),
            "digest": lambda v: v.update(contextDigest="sha256:" + "0" * 64),
            "digest-null": lambda v: v.update(contextDigest=None),
            "unresolved": lambda v: v["resolution"].update(unresolvedStrongRelations=v["resolution"]["unresolvedStrongRelations"] + 1),
            "document-count": lambda v: v["resolution"].update(documentCount=v["resolution"]["documentCount"] + 1),
            "document-duplicate": lambda v: v["documents"].append(copy.deepcopy(v["documents"][-1])),
            "document-drop": lambda v: v["documents"].pop(),
            "document-reverse": lambda v: v["documents"].reverse(),
            "document-role": lambda v: v["documents"][-1].update(role="root"),
            "reached-by": lambda v: v["documents"][-1]["reachedBy"].append("requires:web::REQ-009"),
            "workspaces": lambda v: v["resolution"]["workspaces"].reverse(),
            "cross-edges": lambda v: v["resolution"]["crossWorkspaceEdges"].pop(),
            "coverage": lambda v: v["coverage"]["must"].update(addressed=[]),
            "ledger": lambda v: v["constraintLedger"]["statements"].clear(),
            "workspace": lambda v: v["workspace"].update(path="."),
            "revision": lambda v: v.update(revision=None if v["revision"] else {"commit": "0" * 40, "dirty": False}),
            "target-status": lambda v: v["targetResults"][0].update(status="passed"),
            "target-diagnostics": lambda v: v["targetResults"][0]["diagnostics"].pop(),
            "target-digest": lambda v: v["targetResults"][0].update(contextDigest="sha256:" + "0" * 64),
            "target-evidence": lambda v: v["targetResults"][0]["diagnostics"][0].update(evidence="ADR-001"),
            "commands": lambda v: v["commands"].append({}),
            "ws-order": lambda v: v["workspaces"].reverse(),
            "ws-status": lambda v: v["workspaces"][2].update(status="passed"),
        }
        manifests = {
            "status": lambda v: v["expect"].update(status="failed" if v["expect"]["status"] == "passed" else "passed"),
            "exit-code": lambda v: v["expect"].update(exitCode=3),
            "cwd": lambda v: v["invocation"].update(cwd="." if v["invocation"]["cwd"] != "." else "apps/web"),
            "purpose": lambda v: v["invocation"]["argv"].__setitem__(
                v["invocation"]["argv"].index("--purpose") + 1, "implement" if "interpret" in v["invocation"]["argv"] else "interpret"),
            "argv-extra": lambda v: v["invocation"]["argv"].insert(1, "--all-workspaces"),
            "env": lambda v: v["invocation"].update(env={"PATH": "/dev/null"}),
            "no-git": lambda v: v["setup"].update(git=False),
            "operations": lambda v: v["setup"]["operations"].append({"op": "delete", "path": ".spec/bitz.yaml"}),
        }
        mutations = []
        for identifier, case in module.CASES.items():
            relative = module.RESULT_FILES[case["op"]]
            mutations += [(identifier, relative, name, change) for name, change in results.items()]
            mutations += [(identifier, "manifest.json", name, change) for name, change in manifests.items()]
            mutations.append((identifier, "side-effects.json", "extra", lambda v: v["before"]["repository"].update(extra={"kind": "directory"})))
            mutations.append((identifier, "side-effects.json", "policy", lambda v: v.update(policy="read-write")))
        applied = 0
        for index, (identifier, relative, name, mutate) in enumerate(mutations):
            with tempfile.TemporaryDirectory() as temporary:
                root = self.copy_multi_fixture(temporary, identifier)
                path = root / "multi" / identifier / relative
                value = json.loads(path.read_text())
                before = json.dumps(value, sort_keys=True)
                try:
                    mutate(value)
                except (KeyError, IndexError, TypeError, AttributeError, ValueError):
                    continue
                if json.dumps(value, sort_keys=True) == before:
                    continue
                applied += 1
                path.write_text(json.dumps(value))
                with self.subTest(index=index, identifier=identifier, file=relative, mutation=name):
                    self.assertEqual(module.validate(root, {identifier})["status"], "Failed")
        # 改変の適用が空振りしていないこと。
        self.assertGreater(applied, 250)

    def test_multi_closure_alias_audit_rejects_changed_corpus(self):
        """入力の欠落と追加（バイト列の照合）と、原因を消す入力の書換え（参照計算と原因の構成の検査）を拒否する。"""
        module = multi_closure_alias_fixtures
        for identifier in module.CASES:
            names = sorted(f"repo/{name}" for name in module.reviewed_inputs(identifier) if name.endswith(".md") or name.endswith("bitz.yaml"))
            for name in [*names, "extra"]:
                with self.subTest(identifier=identifier, file=name), tempfile.TemporaryDirectory() as temporary:
                    root = self.copy_multi_fixture(temporary, identifier)
                    fixture = root / "multi" / identifier
                    if name == "extra":
                        (fixture / "repo/extra.txt").write_text("x")
                    else:
                        (fixture / name).unlink()
                    self.assertEqual(module.validate(root, {identifier})["status"], "Failed")
        # 原因を作る書換え。入力のバイト列の照合とスナップショットを通した上で（書換え後の内容を`reviewed_inputs`にし、副作用の期待値を作り直す）、
        # 参照計算と原因の構成の検査が拒否することを確かめる（バイト列の照合で先に拒否される空振りを避ける）。
        edits = {
            # 循環を閉包の中へ入れる（`MULTI-038-01`の陰性対照）、循環を壊す（`MULTI-038-02`）。
            "MULTI-038-01": [("apps/web/.spec/requirements/REQ-001.md", "status: approved\n", "status: approved\nrelations:\n  requires: [TECH-020]\n")],
            "MULTI-038-02": [("apps/web/.spec/technical/TECH-011.md", "requires: [TECH-010]", "requires: []")],
            "MULTI-038-05": [(".spec/requirements/REQ-001.md", "status: approved\n", "status: approved\nrelations:\n  requires: [TECH-020]\n")],
            # 別名だけで到達する参照切れを、非修飾の宣言へ変える（`MULTI-038-08`の条件を消す）。
            "MULTI-038-08": [("services/api/.spec/technical/TECH-020.md", "web::TECH-010", "api::TECH-021")],
            "MULTI-038-10": [("apps/web/.spec/technical/TECH-010.md", "TECH-999", "TECH-011")],
            # 二重収録の条件（非修飾と修飾の両方の表記）を消す。
            "MULTI-038-07": [("services/api/.spec/technical/TECH-020.md", "web::TECH-010", "api::TECH-020")],
            "MULTI-038-15": [("services/api/.spec/technical/TECH-030.md", "web::REQ-001", "web::REQ-009")],
            "MULTI-038-16": [("apps/web/.spec/technical/TECH-001.md", "refines: [REQ-001]", "refines: [REQ-009]")],
            "MULTI-038-17": [("apps/web/.spec/requirements/REQ-002.md", "supersedes: [REQ-001]", "supersedes: [REQ-009]")],
            "MULTI-038-18": [("apps/web/.spec/tasks/TASK-001.md", "status: open", "status: done")],
            # 他のメンバーの文書が起点を指す宣言を、起点を指さない宣言へ変える（置換・状態`draft`の具体化・`addresses`の条件を消す）。
            "MULTI-038-19": [("services/api/.spec/requirements/REQ-009.md", "supersedes: [web::REQ-001]", "supersedes: [web::REQ-009]")],
            "MULTI-038-20": [("services/api/.spec/requirements/REQ-009.md", "supersedes: [web::REQ-001]", "supersedes: [web::REQ-009]")],
            "MULTI-038-21": [("services/api/.spec/technical/TECH-040.md", "status: draft", "status: approved")],
            "MULTI-038-22": [("services/api/.spec/tasks/TASK-009.md", "status: open", "status: done")],
            # `evidence`の表記を、宣言どおりの原因を消す形へ変える。
            "MULTI-038-12": [("services/api/.spec/technical/TECH-020.md", "api::ADR-001", "ADR-001")],
            "MULTI-038-11": [("services/api/.spec/technical/TECH-020.md", "ADR-001", "api::ADR-001")],
            "MULTI-038-14": [(".spec/decisions/ADR-001.md", "status: proposed", "status: accepted")],
        }
        byte_phrases = ("入力がレビュー済みのcorpusと異なります", "隔離した準備手順が固定したスナップショットと異なります")
        for identifier, changes in edits.items():
            for relative, old, new in changes:
                with self.subTest(identifier=identifier, file=relative), tempfile.TemporaryDirectory() as temporary:
                    root = self.copy_multi_fixture(temporary, identifier)
                    fixture = root / "multi" / identifier
                    path = fixture / "repo" / relative
                    self.assertIn(old, path.read_text())
                    path.write_text(path.read_text().replace(old, new))
                    edited = dict(module.reviewed_inputs(identifier))
                    edited[relative] = path.read_bytes()
                    manifest = json.loads((fixture / "manifest.json").read_text())
                    repository = fixture_setup(fixture, manifest, Path(temporary) / "regen" / "repo")
                    external = {key: Path(temporary) / "regen" / key for key in ("home", "cache", "temporary")}
                    for directory in external.values():
                        directory.mkdir()
                    state = module.observe(repository, external)
                    (fixture / "side-effects.json").write_text(json.dumps({"schemaVersion": "1.0", "policy": "read-only", "before": state, "after": state}))
                    with patch.object(module, "reviewed_inputs", lambda _identifier, edited=edited: edited):
                        outcome = module.validate(root, {identifier})
                    self.assertEqual(outcome["status"], "Failed")
                    self.assertEqual(len(outcome["errors"]), 1)
                    self.assertFalse(any(phrase in outcome["errors"][0] for phrase in byte_phrases), outcome["errors"][0])
                    self.assertNotIn("KeyError", outcome["errors"][0])

    def test_multi_context_order_fixtures(self):
        """`MULTI-042-01`〜`03`: 複合ワークスペースのcontextの文書と規範文の並びを修飾IDの辞書順に固定する（確認事項C46）。"""
        module = multi_context_order_fixtures
        result = module.validate()
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["prepared"], [f"MULTI-042-{number:02d}" for number in range(1, 4)])
        self.assertEqual(result["references"], 2)
        self.assertEqual(result["core_execution"], "Not run")
        # 複製した状態でも通る（以降の拒否の試験が、複製の不備で空振りしていないことの陽性対照）。
        for identifier in module.CASES:
            with self.subTest(identifier=identifier), tempfile.TemporaryDirectory() as temporary:
                root = self.copy_multi_fixture(temporary, identifier)
                self.assertEqual(module.validate(root, {identifier})["errors"], [])

    def test_multi_context_order_reference_rules(self):
        """並びの参照計算（関係・トレースモデル §6.4・§7、複合ワークスペース仕様 §4）と、修正前の比較の再現。"""
        module = multi_context_order_fixtures

        def statements(identifier, count):
            return "".join(f"- [{identifier}:C-0{number}] [ACTOR:A] [ALWAYS] [MUST] [CONSTRAINT] x。\n" for number in range(1, count + 1))

        def document(workspace, identifier, kind, count=0, **relations):
            return {"workspaceId": workspace, "kind": kind, "body": statements(identifier, count), "path": f"{identifier}.md",
                    "frontmatter": {"id": identifier, "title": "t", "status": "approved",
                                    "relations": {key: value for key, value in relations.items()}}}

        documents = {
            "platform::REQ-001": document("platform", "REQ-001", "requirement", 1, requires=["web::REQ-003"]),
            "web::REQ-003": document("web", "REQ-003", "requirement", 1),
            "platform::TECH-005": document("platform", "TECH-005", "technical", 2, refines=["REQ-001:C-01"]),
            "api::TECH-010": document("api", "TECH-010", "technical", 1, refines=["platform::REQ-001:C-01"]),
            "web::TECH-010": document("web", "TECH-010", "technical", 1, refines=["platform::REQ-001:C-01"]),
            "platform::TECH-002": document("platform", "TECH-002", "technical", 1, refines=["TECH-005:C-02"]),
        }
        ordered, edges, distance = module.reference_order(documents, "platform::REQ-001", "interpret")
        # 距離が先、同じ距離では種別REQがTECHより先、同じ距離・種別では修飾IDの辞書順（`api::`が`platform::`より先）。
        self.assertEqual(ordered, ["platform::REQ-001", "web::REQ-003", "api::TECH-010", "platform::TECH-005", "web::TECH-010", "platform::TECH-002"])
        self.assertEqual([distance[name] for name in ordered], [0, 1, 1, 1, 1, 2])
        # 修正前の比較は、起点ワークスペースの文書だけを修飾しないIDで比べるので、`platform::TECH-005`が`api::TECH-010`より先になる。
        self.assertEqual(module.defective_order(documents, "platform::REQ-001", "interpret", "platform"),
                         ["platform::REQ-001", "web::REQ-003", "platform::TECH-005", "api::TECH-010", "web::TECH-010", "platform::TECH-002"])
        # 作業ワークスペースが違えば、内部のIDで比べる文書も変わる（`web`なら`web::TECH-010`が先頭になる）。`api`なら修飾IDの順と同じになる。
        self.assertEqual(module.defective_order(documents, "platform::REQ-001", "interpret", "web"),
                         ["platform::REQ-001", "web::REQ-003", "web::TECH-010", "api::TECH-010", "platform::TECH-005", "platform::TECH-002"])
        self.assertEqual(module.defective_order(documents, "platform::REQ-001", "interpret", "api"), ordered)
        # 対象規範文は、起点と具体化文書の規範文を、文書の順、行番号の順に並べる。`requires`で到達した`web::REQ-003`の規範文は含めない。
        wanted = ["platform::REQ-001:C-01", "api::TECH-010:C-01", "platform::TECH-005:C-01", "platform::TECH-005:C-02",
                  "web::TECH-010:C-01", "platform::TECH-002:C-01"]
        self.assertEqual(module.reference_targets(documents, ordered, edges, "platform::REQ-001"), wanted)
        # 対応済みは閉包のTASKが`addresses`する規範文、テスト済みは閉包の文書が`covers`する規範文。順は対象規範文の順のまま。
        documents["platform::TASK-001"] = dict(document("platform", "TASK-001", "task", addresses=["TECH-005:C-02", "platform::REQ-001:C-01"]),
                                               kind="task")
        documents["api::TECH-010"]["frontmatter"]["tests"] = [{"path": "t.py", "covers": ["api::TECH-010:C-01", "platform::REQ-001:C-01"]}]
        closure = [*ordered, "platform::TASK-001"]
        addressed, tested, unaddressed, untested = module.reference_coverage(documents, closure, wanted)
        self.assertEqual(addressed, ["platform::REQ-001:C-01", "platform::TECH-005:C-02"])
        self.assertEqual(tested, ["platform::REQ-001:C-01", "api::TECH-010:C-01"])
        self.assertEqual(unaddressed, ["api::TECH-010:C-01", "platform::TECH-005:C-01", "web::TECH-010:C-01", "platform::TECH-002:C-01"])
        self.assertEqual(untested, ["platform::TECH-005:C-01", "platform::TECH-005:C-02", "web::TECH-010:C-01", "platform::TECH-002:C-01"])

    def test_multi_context_order_expected_orders_distinguish_the_defect(self):
        """リテラルの期待する並びは、修正前の比較（内部のID）の並びと異なる（複合ワークスペース）。単一ワークスペースでは同じ（対照）。"""
        module = multi_context_order_fixtures
        for identifier in module.CASES:
            with self.subTest(identifier=identifier):
                single, root_id, _, documents = module.alias.load_tree(audit.FIXTURES / "multi" / identifier / "repo")
                root = f"{root_id}::{module.CASES[identifier]['root']}" if single else module.CASES[identifier]["root"]
                purpose = module.CASES[identifier]["purpose"]
                old = module.defective_order(documents, root, purpose, root_id if single else "platform")
                shown = [name.partition("::")[2] if single else name for name in old]
                if single:
                    self.assertEqual(shown, module.EXPECTED_DOCUMENTS[identifier])
                else:
                    self.assertNotEqual(shown, module.EXPECTED_DOCUMENTS[identifier])
                    self.assertEqual(sorted(shown), sorted(module.EXPECTED_DOCUMENTS[identifier]))
        # 距離の遠いplatform::TECH-002は、IDが小さくても距離1のTECHの後ろに並ぶ。
        ordered = module.EXPECTED_DOCUMENTS["MULTI-042-02"]
        self.assertGreater(ordered.index("platform::TECH-002"), ordered.index("web::TECH-010"))
        self.assertGreater(ordered.index("api::TASK-001"), ordered.index("web::TECH-010"))
        self.assertLess(ordered.index("api::TASK-001"), ordered.index("api::TECH-020"))

    def test_multi_context_order_audit_rejects_changed_expectations(self):
        """期待結果・起動条件・副作用の改変を拒否する。"""
        module = multi_context_order_fixtures

        def swap(values, first, second):
            values[first], values[second] = values[second], values[first]

        results = {
            "status": lambda v: v.update(status="failed"),
            "diagnostics-add": lambda v: v["diagnostics"].append({"code": "CTX-COVERAGE-TASK-001"}),
            "digest": lambda v: v.update(contextDigest="sha256:" + "0" * 64),
            "digest-null": lambda v: v.update(contextDigest=None),
            "documents-reverse": lambda v: v["documents"].reverse(),
            # 修正前の並び（起点ワークスペースの文書を内部のIDで比べる）への改変。
            "documents-defective-order": lambda v: swap(v["documents"], *[index for index, item in enumerate(v["documents"])
                                                                          if item["id"].endswith("TECH-005") or item["id"] == "api::TECH-010"]),
            "documents-swap-first": lambda v: swap(v["documents"], 1, 2),
            "documents-swap-distance": lambda v: swap(v["documents"], 4, 5),
            "documents-drop": lambda v: v["documents"].pop(),
            "documents-duplicate": lambda v: v["documents"].append(copy.deepcopy(v["documents"][-1])),
            "document-role": lambda v: v["documents"][-1].update(role="root"),
            "document-reached-by": lambda v: v["documents"][-1]["reachedBy"].append("requires:platform::REQ-001"),
            "document-projection": lambda v: v["documents"][-1].update(projection="full"),
            "document-count": lambda v: v["resolution"].update(documentCount=v["resolution"]["documentCount"] + 1),
            "unresolved": lambda v: v["resolution"].update(unresolvedStrongRelations=1),
            "workspaces": lambda v: v["resolution"]["workspaces"].reverse(),
            "cross-edges-drop": lambda v: v["resolution"]["crossWorkspaceEdges"].pop(),
            "cross-edges-reverse": lambda v: v["resolution"]["crossWorkspaceEdges"].reverse(),
            "ledger-swap-tie": lambda v: swap(v["constraintLedger"]["statements"], 1, 2),
            "ledger-defective-order": lambda v: v["constraintLedger"]["statements"].insert(
                1, v["constraintLedger"]["statements"].pop(2)),
            "ledger-clear": lambda v: v["constraintLedger"]["statements"].clear(),
            "ledger-role": lambda v: v["constraintLedger"]["statements"][1].update(documentRole="root"),
            "ledger-text": lambda v: v["constraintLedger"]["statements"][0]["operation"].update(text="x"),
            "coverage-total-swap": lambda v: swap(v["coverage"]["must"]["total"], 1, 2),
            "coverage-addressed-swap": lambda v: swap(v["coverage"]["must"]["addressed"], 1, 2),
            "coverage-tested-swap": lambda v: swap(v["coverage"]["must"]["tested"], 1, 2),
            "coverage-addressed-drop": lambda v: v["coverage"]["must"]["addressed"].pop(),
            "coverage-unaddressed": lambda v: v["coverage"]["must"]["unaddressed"].append(v["coverage"]["must"]["total"][0]),
            "coverage-untested": lambda v: v["coverage"]["must"]["untested"].append(v["coverage"]["must"]["total"][0]),
            "coverage-should": lambda v: v["coverage"]["should"]["total"].append("platform::REQ-001:AC-01"),
            "coverage-adjacent": lambda v: v["coverage"]["adjacent"].append("platform::REQ-001:AC-01"),
            "workspace": lambda v: v["workspace"].update(id="web"),
            "roots": lambda v: v["roots"].append("platform::REQ-002"),
            "revision": lambda v: v.update(revision=None),
            "detail": lambda v: v["projection"].update(detail="standard"),
        }
        manifests = {
            "status": lambda v: v["expect"].update(status="failed"),
            "exit-code": lambda v: v["expect"].update(exitCode=1),
            "cwd": lambda v: v["invocation"].update(cwd="apps/web"),
            "purpose": lambda v: v["invocation"]["argv"].__setitem__(
                v["invocation"]["argv"].index("--purpose") + 1, "implement" if "interpret" in v["invocation"]["argv"] else "interpret"),
            "detail": lambda v: v["invocation"]["argv"].__setitem__(v["invocation"]["argv"].index("--detail") + 1, "standard"),
            "root": lambda v: v["invocation"]["argv"].__setitem__(1, "web::REQ-003"),
            "argv-extra": lambda v: v["invocation"]["argv"].insert(1, "--all-workspaces"),
            "env": lambda v: v["invocation"].update(env={"PATH": "/dev/null"}),
            "no-git": lambda v: v["setup"].update(git=False),
            "operations": lambda v: v["setup"]["operations"].append({"op": "delete", "path": ".spec/bitz.yaml"}),
        }
        mutations = []
        for identifier in module.CASES:
            mutations += [(identifier, "expected/context.json", name, change) for name, change in results.items()]
            mutations += [(identifier, "manifest.json", name, change) for name, change in manifests.items()]
            mutations.append((identifier, "side-effects.json", "extra", lambda v: v["before"]["repository"].update(extra={"kind": "directory"})))
            mutations.append((identifier, "side-effects.json", "policy", lambda v: v.update(policy="read-write")))
        applied = 0
        for index, (identifier, relative, name, mutate) in enumerate(mutations):
            with tempfile.TemporaryDirectory() as temporary:
                root = self.copy_multi_fixture(temporary, identifier)
                path = root / "multi" / identifier / relative
                value = json.loads(path.read_text())
                before = json.dumps(value, sort_keys=True)
                try:
                    mutate(value)
                except (KeyError, IndexError, TypeError, AttributeError, ValueError):
                    continue
                if json.dumps(value, sort_keys=True) == before:
                    continue
                applied += 1
                path.write_text(json.dumps(value))
                with self.subTest(index=index, identifier=identifier, file=relative, mutation=name):
                    self.assertEqual(module.validate(root, {identifier})["status"], "Failed")
        # 改変の適用が空振りしていないこと。
        self.assertGreater(applied, 110)

    def test_multi_context_order_audit_rejects_changed_corpus(self):
        """入力の欠落と追加（バイト列の照合）と、欠陥を検出する構成を消す入力の書換え（参照計算と原因の構成の検査）を拒否する。"""
        module = multi_context_order_fixtures
        for identifier in module.CASES:
            names = sorted(f"repo/{name}" for name in module.reviewed_inputs(identifier) if name.endswith(".md") or name.endswith("bitz.yaml"))
            for name in [*names, "extra"]:
                with self.subTest(identifier=identifier, file=name), tempfile.TemporaryDirectory() as temporary:
                    root = self.copy_multi_fixture(temporary, identifier)
                    fixture = root / "multi" / identifier
                    if name == "extra":
                        (fixture / "repo/extra.txt").write_text("x")
                    else:
                        (fixture / name).unlink()
                    self.assertEqual(module.validate(root, {identifier})["status"], "Failed")
        # 原因を消す書換え。入力のバイト列の照合とスナップショットを通した上で（書換え後の内容を`reviewed_inputs`にし、副作用の期待値を作り直す）、
        # 参照計算と原因の構成の検査が拒否することを確かめる（バイト列の照合で先に拒否される空振りを避ける）。
        edits = {
            # 距離1のTECHの3つ組を崩す（apiのTECH-010を距離2へ移す）。
            "MULTI-042-01": [("services/api/.spec/technical/TECH-010.md", "refines: [platform::REQ-001:AC-01]", "refines: [platform::TECH-005:C-01]"),
                             # TASKを閉包に入れる（目的interpretはTASKを含めない）はずがない入力へ変える: 起点が別のワークスペースの文書を要求する。
                             (".spec/requirements/REQ-001.md", "requires: [web::REQ-003]", "requires: []")],
            "MULTI-042-02": [("services/api/.spec/tasks/TASK-001.md", "status: open", "status: done"),
                             ("apps/web/.spec/technical/TECH-010.md", "refines: [platform::REQ-001:AC-01]", "refines: [platform::TECH-005:C-01]"),
                             (".spec/technical/TECH-005.md", "    covers: [platform::TECH-005:C-01]\n", "    covers: [platform::TECH-002:C-01]\n")],
            # 対照の単一ワークスペースを、修飾しないIDでも並びが変わる形へ変える（TECH-010を距離2へ移す）。
            "MULTI-042-03": [(".spec/technical/TECH-010.md", "refines: [REQ-001:AC-01]", "refines: [TECH-005:C-01]")],
        }
        byte_phrases = ("入力がレビュー済みのcorpusと異なります", "隔離した準備手順が固定したスナップショットと異なります")
        for identifier, changes in edits.items():
            for relative, old, new in changes:
                with self.subTest(identifier=identifier, file=relative, old=old), tempfile.TemporaryDirectory() as temporary:
                    root = self.copy_multi_fixture(temporary, identifier)
                    fixture = root / "multi" / identifier
                    path = fixture / "repo" / relative
                    self.assertIn(old, path.read_text())
                    path.write_text(path.read_text().replace(old, new))
                    edited = dict(module.reviewed_inputs(identifier))
                    edited[relative] = path.read_bytes()
                    manifest = json.loads((fixture / "manifest.json").read_text())
                    repository = fixture_setup(fixture, manifest, Path(temporary) / "regen" / "repo")
                    external = {key: Path(temporary) / "regen" / key for key in ("home", "cache", "temporary")}
                    for directory in external.values():
                        directory.mkdir()
                    state = module.observe(repository, external)
                    (fixture / "side-effects.json").write_text(json.dumps({"schemaVersion": "1.0", "policy": "read-only", "before": state, "after": state}))
                    with patch.object(module, "reviewed_inputs", lambda _identifier, edited=edited: edited):
                        outcome = module.validate(root, {identifier})
                    self.assertEqual(outcome["status"], "Failed")
                    self.assertEqual(len(outcome["errors"]), 1)
                    self.assertFalse(any(phrase in outcome["errors"][0] for phrase in byte_phrases), outcome["errors"][0])
                    self.assertNotIn("KeyError", outcome["errors"][0])

    def test_multi_workspace_id_fixtures(self):
        """`MULTI-043-01`〜`18`: 複合ワークスペースのルートとメンバーの`workspace.id`の省略を既定値`root`で通さないことを固定する（確認事項C42）。"""
        module = multi_workspace_id_fixtures
        result = module.validate()
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["prepared"], [f"MULTI-043-{number:02d}" for number in range(1, 19)])
        self.assertEqual(result["references"], 1)
        self.assertEqual(result["core_execution"], "Not run")
        # 複製した状態でも通る（以降の拒否の試験が、複製の不備で空振りしていないことの陽性対照）。
        for identifier in module.CASES:
            with self.subTest(identifier=identifier), tempfile.TemporaryDirectory() as temporary:
                root = self.copy_multi_fixture(temporary, identifier)
                self.assertEqual(module.validate(root, {identifier})["errors"], [])

    def test_multi_workspace_id_reference_rules(self):
        """参照計算（複合ワークスペース仕様 §2・§4.1、結果・診断・終了コード §2）。ルートの省略は、ほかのカタログの不備より先に判定する。"""
        module = multi_workspace_id_fixtures

        def decide(identifier, cwd=None):
            with tempfile.TemporaryDirectory() as temporary:
                repository = Path(temporary)
                for name, data in module.reviewed_inputs(identifier).items():
                    (repository / name).parent.mkdir(parents=True, exist_ok=True)
                    (repository / name).write_bytes(data)
                return module.reference_decision(repository, cwd or module.CASES[identifier]["cwd"])

        # ルートの省略。ルートからは`null`、メンバーからはカタログのIDと一致する明示したIDがあればそのID。
        self.assertEqual(decide("MULTI-043-01"), {"cause": "root-id", "multiWorkspaceId": None, "workspace": {"id": None, "path": "."}})
        self.assertEqual(decide("MULTI-043-05")["workspace"], {"id": "web", "path": "apps/web"})
        # 同時の不備があっても、原因はルートの省略に定まる。
        self.assertEqual(decide("MULTI-043-08")["cause"], "root-id")
        self.assertEqual(decide("MULTI-043-09")["cause"], "root-id")
        # メンバーの省略。ルートのIDは明示した値。メンバーからは、カタログのIDと一致しないので`null`。
        self.assertEqual(decide("MULTI-043-10"), {"cause": "member-id", "multiWorkspaceId": "platform", "workspace": {"id": "platform", "path": "."}})
        self.assertEqual(decide("MULTI-043-11")["workspace"], {"id": None, "path": "apps/web"})
        # 版の非対応で止まっても、ルートが`workspace.id`を明示しなければ同一性は`null`。診断の種類は版の非対応が先。
        self.assertEqual(decide("MULTI-043-13"), {"cause": "ears-version", "multiWorkspaceId": None, "workspace": {"id": None, "path": "."}})
        self.assertEqual(decide("MULTI-043-14")["cause"], "schema-version")
        self.assertEqual(decide("MULTI-043-15")["cause"], "ears-version")
        self.assertEqual(decide("MULTI-043-16")["cause"], "schema-version")
        # 値のない`multiWorkspace`の宣言も、キーがあれば複合ワークスペースのルートの省略として扱う。
        self.assertEqual(decide("MULTI-043-17"), {"cause": "root-id", "multiWorkspaceId": None, "workspace": {"id": None, "path": "."}})
        self.assertEqual(decide("MULTI-043-18")["cause"], "root-id")
        # 対照: ルートが`root`を明示すれば原因はない。
        self.assertEqual(decide("MULTI-043-12"), {"cause": None, "multiWorkspaceId": "root", "workspace": {"id": "root", "path": "."}})
        # 既定値`root`は明示のIDではない。`workspace`が`id`を持たない形も省略として扱う。
        self.assertIsNone(module.explicit_id({"schemaVersion": "1.0"}))
        self.assertIsNone(module.explicit_id({"workspace": {}}))
        self.assertIsNone(module.explicit_id({"workspace": None}))
        self.assertEqual(module.explicit_id({"workspace": {"id": "root"}}), "root")

    def test_multi_workspace_id_audit_rejects_changed_expectations(self):
        """期待結果・起動条件・副作用の改変を拒否する。"""
        module = multi_workspace_id_fixtures

        results = {
            "status": lambda v: v.update(status="passed"),
            "status-blocked": lambda v: v.update(status="blocked"),
            "diagnostics-clear": lambda v: v["diagnostics"].clear(),
            "diagnostics-add": lambda v: v["diagnostics"].append(copy.deepcopy(v["diagnostics"][0])),
            "code": lambda v: v["diagnostics"][0].update(code="SPEC-MULTI-PATH-001"),
            "code-member": lambda v: v["diagnostics"][0].update(code="SPEC-MULTI-MEMBER-001"),
            "summary": lambda v: v["diagnostics"][0].update(summary="ルートワークスペースの設定キーworkspace.idが不正です"),
            "summary-version": lambda v: v["diagnostics"][0].update(summary="未対応のメジャーバージョンです"),
            "code-ears": lambda v: v["diagnostics"][0].update(code="SPEC-EARS-VERSION-001"),
            "code-doctor-ears": lambda v: v["diagnostics"][0].update(code="SPEC-DOCTOR-EARS-001"),
            "code-schema": lambda v: v["diagnostics"][0].update(code="SPEC-CONFIG-SCHEMA-001"),
            "result-status-failed": lambda v: v["diagnostics"][0].update(resultStatus="failed"),
            "source-key-ears": lambda v: v["diagnostics"][0]["source"].update(key="earsAi"),
            "source-key-schema": lambda v: v["diagnostics"][0]["source"].update(key="schemaVersion"),
            "suggested-action-drop": lambda v: v["diagnostics"][0].pop("suggestedAction"),
            "severity": lambda v: v["diagnostics"][0].update(severity="warning"),
            "result-status": lambda v: v["diagnostics"][0].update(resultStatus="blocked"),
            "source-workspace": lambda v: v["diagnostics"][0]["source"].update(workspaceId="platform"),
            "source-workspace-root": lambda v: v["diagnostics"][0]["source"].update(workspaceId="root"),
            "source-key": lambda v: v["diagnostics"][0]["source"].update(key="workspace"),
            "source-key-drop": lambda v: v["diagnostics"][0]["source"].pop("key"),
            "source-path": lambda v: v["diagnostics"][0]["source"].update(path="apps/web/.spec/bitz.yaml"),
            "suggested-action": lambda v: v["diagnostics"][0].update(suggestedAction="設定キーworkspace.idを指定してください"),
            "multi-id-root": lambda v: v["multiWorkspace"].update(id="root"),
            "multi-id-platform": lambda v: v["multiWorkspace"].update(id="platform"),
            "multi-id-null": lambda v: v["multiWorkspace"].update(id=None),
            "multi-path": lambda v: v["multiWorkspace"].update(path="apps/web"),
            "workspaces-fill": lambda v: v["workspaces"].append({"id": "root", "path": ".", "status": "passed", "durationMs": 0, "diagnostics": []}),
            "workspace-id-root": lambda v: v["workspace"].update(id="root"),
            "workspace-id-web": lambda v: v["workspace"].update(id="web"),
            "workspace-id-null": lambda v: v["workspace"].update(id=None),
            "workspace-path": lambda v: v["workspace"].update(path="."),
            "workspace-add": lambda v: v.update(workspace={"id": None, "path": "."}),
            "multi-add": lambda v: v.update(multiWorkspace={"id": None, "path": "."}),
            "checks-catalog": lambda v: v["checks"][2].update(status="passed"),
            "checks-catalog-blocked": lambda v: v["checks"][2].update(status="blocked"),
            "checks-drop": lambda v: v["checks"].pop(),
            "target-results": lambda v: v["targetResults"].append({}),
            "commands": lambda v: v["commands"].append({}),
            "scope": lambda v: v.update(scope="full"),
            "selection": lambda v: v["selection"].update(changedPathCount=1),
            "revision-null": lambda v: v.update(revision=None),
        }
        manifests = {
            "status": lambda v: v["expect"].update(status="blocked"),
            "exit-code": lambda v: v["expect"].update(exitCode=2),
            "cwd": lambda v: v["invocation"].update(cwd="services/api"),
            "argv-extra": lambda v: v["invocation"]["argv"].insert(1, "--full"),
            "argv-all": lambda v: v["invocation"]["argv"].insert(1, "--all-workspaces"),
            "env": lambda v: v["invocation"].update(env={"PATH": "/dev/null"}),
            "no-git": lambda v: v["setup"].update(git=False),
            "operations": lambda v: v["setup"]["operations"].append({"op": "delete", "path": ".spec/bitz.yaml"}),
        }
        mutations = []
        for identifier in module.CASES:
            result_file = module.RESULT_FILES[module.CASES[identifier]["op"]]
            mutations += [(identifier, result_file, name, change) for name, change in results.items()]
            mutations += [(identifier, "manifest.json", name, change) for name, change in manifests.items()]
            mutations.append((identifier, "side-effects.json", "extra", lambda v: v["before"]["repository"].update(extra={"kind": "directory"})))
            mutations.append((identifier, "side-effects.json", "policy", lambda v: v.update(policy="read-write")))
        applied = 0
        for index, (identifier, relative, name, mutate) in enumerate(mutations):
            with tempfile.TemporaryDirectory() as temporary:
                root = self.copy_multi_fixture(temporary, identifier)
                path = root / "multi" / identifier / relative
                value = json.loads(path.read_text())
                before = json.dumps(value, sort_keys=True)
                try:
                    mutate(value)
                except (KeyError, IndexError, TypeError, AttributeError, ValueError):
                    continue
                if json.dumps(value, sort_keys=True) == before:
                    continue
                applied += 1
                path.write_text(json.dumps(value))
                with self.subTest(index=index, identifier=identifier, file=relative, mutation=name):
                    self.assertEqual(module.validate(root, {identifier})["status"], "Failed")
        # 改変の適用が空振りしていないこと。
        self.assertGreater(applied, 400)

    def test_multi_workspace_id_audit_rejects_changed_corpus(self):
        """入力の欠落と追加（バイト列の照合）と、原因の構成を消す入力の書換え（参照計算と原因の構成の検査）を拒否する。"""
        module = multi_workspace_id_fixtures
        for identifier in module.CASES:
            for name in [*(f"repo/{name}" for name in sorted(module.reviewed_inputs(identifier))), "extra"]:
                with self.subTest(identifier=identifier, file=name), tempfile.TemporaryDirectory() as temporary:
                    root = self.copy_multi_fixture(temporary, identifier)
                    fixture = root / "multi" / identifier
                    if name == "extra":
                        (fixture / "repo/extra.txt").write_text("x")
                    else:
                        (fixture / name).unlink()
                    self.assertEqual(module.validate(root, {identifier})["status"], "Failed")
        # 原因を消す書換え。入力のバイト列の照合とスナップショットを通した上で（書換え後の内容を`reviewed_inputs`にし、副作用の期待値を作り直す）、
        # 参照計算と原因の構成の検査が拒否することを確かめる（バイト列の照合で先に拒否される空振りを避ける）。
        root_id = "workspace:\n  id: platform\n"
        edits = {
            # ルートが`workspace.id`を明示する（省略という原因を消す）。
            "MULTI-043-01": [(".spec/bitz.yaml", "multiWorkspace:", root_id + "multiWorkspace:"),
                             # 空のマッピングは、この群が固定する省略の形（`workspace`キーなし）ではない。
                             (".spec/bitz.yaml", "multiWorkspace:", "workspace: {}\nmultiWorkspace:"),
                             # メンバー`web`が省略する（原因をルートの省略だけにしない）。
                             ("apps/web/.spec/bitz.yaml", "workspace:\n  id: web\n", "")],
            "MULTI-043-05": [("apps/web/.spec/bitz.yaml", "id: web", "id: frontend")],
            # 未登録の設定をカタログへ登録する（ルートの省略に重ねる不備を1つ消す）。
            "MULTI-043-08": [(".spec/bitz.yaml", "      path: services/api\n", "      path: services/api\n    - id: x\n      path: tools/x\n")],
            "MULTI-043-09": [("apps/web/.spec/bitz.yaml", "id: frontend", "id: web")],
            # メンバーが明示する（省略という原因を消す）。
            "MULTI-043-10": [("apps/web/.spec/bitz.yaml", 'earsAi: "1.0"\n', 'earsAi: "1.0"\nworkspace:\n  id: root\n')],
            # 対照のルートが`root`を明示しない形へ変える。
            "MULTI-043-12": [(".spec/bitz.yaml", "id: root\n", "id: platform\n")],
            # 版の非対応という原因を消す（ルートの版を対応するメジャーバージョンへ戻す）。
            "MULTI-043-13": [(".spec/bitz.yaml", 'earsAi: "2.0"', 'earsAi: "1.0"')],
            "MULTI-043-14": [(".spec/bitz.yaml", 'schemaVersion: "2.0"', 'schemaVersion: "1.0"')],
            # 版の非対応にもう1つの版を足す、またはルートに`workspace.id`を明示する（省略という原因を消す）。
            "MULTI-043-15": [(".spec/bitz.yaml", 'schemaVersion: "1.0"', 'schemaVersion: "2.0"'),
                             (".spec/bitz.yaml", "multiWorkspace:", "workspace:\n  id: platform\nmultiWorkspace:")],
            "MULTI-043-16": [(".spec/bitz.yaml", "multiWorkspace:", "workspace:\n  id: platform\nmultiWorkspace:")],
            # 値のない宣言をメンバーの一覧のある宣言へ変える、または宣言を外す。
            "MULTI-043-17": [(".spec/bitz.yaml", "multiWorkspace:\n", "multiWorkspace:\n  members:\n    - id: web\n      path: apps/web\n"),
                             (".spec/bitz.yaml", "multiWorkspace:\n", "")],
            "MULTI-043-18": [(".spec/bitz.yaml", "multiWorkspace:\n", "workspace:\n  id: platform\nmultiWorkspace:\n")],
        }
        for identifier, changes in edits.items():
            for relative, old, new in changes:
                with self.subTest(identifier=identifier, file=relative, old=old), tempfile.TemporaryDirectory() as temporary:
                    root = self.copy_multi_fixture(temporary, identifier)
                    fixture = root / "multi" / identifier
                    path = fixture / "repo" / relative
                    self.assertIn(old, path.read_text())
                    path.write_text(path.read_text().replace(old, new, 1))
                    edited = dict(module.reviewed_inputs(identifier))
                    edited[relative] = path.read_bytes()
                    manifest = json.loads((fixture / "manifest.json").read_text())
                    repository = fixture_setup(fixture, manifest, Path(temporary) / "regen" / "repo")
                    external = {key: Path(temporary) / "regen" / key for key in ("home", "cache", "temporary")}
                    for directory in external.values():
                        directory.mkdir(parents=True)
                    state = module.observe_state(manifest, repository, external)
                    (fixture / "side-effects.json").write_text(json.dumps({"schemaVersion": "1.0", "policy": "read-only", "before": state, "after": state}))
                    with patch.object(module, "reviewed_inputs", lambda _identifier, edited=edited: edited):
                        outcome = module.validate(root, {identifier})
                    self.assertEqual(outcome["status"], "Failed")
                    self.assertEqual(len(outcome["errors"]), 1)
                    self.assertFalse(any(phrase in outcome["errors"][0] for phrase in (
                        "入力がレビュー済みのcorpusと異なります", "隔離した準備手順が固定したスナップショットと異なります")), outcome["errors"][0])
                    self.assertNotIn("KeyError", outcome["errors"][0])

    def test_multi_verify_order_fixtures(self):
        """`MULTI-044-01`〜`05`: verifyの規範文の並びとcontextのハッシュ値の材料の規範文の並びを固定する（確認事項C52・C60）。"""
        module = multi_verify_order_fixtures
        result = module.validate()
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["prepared"], [f"MULTI-044-{number:02d}" for number in range(1, 6)])
        self.assertEqual(result["references"], 2)
        self.assertEqual(result["core_execution"], "Not run")
        # 複製した状態でも通る（以降の拒否の試験が、複製の不備で空振りしていないことの陽性対照）。
        for identifier in module.CASES:
            with self.subTest(identifier=identifier), tempfile.TemporaryDirectory() as temporary:
                root = self.copy_multi_fixture(temporary, identifier)
                self.assertEqual(module.validate(root, {identifier})["errors"], [])

    def test_multi_verify_order_reference_rules(self):
        """対象規範文・テスト割当ての参照計算（関係・トレースモデル §6.4、verify §4・§8）と、修正前の並びの再現。"""
        module = multi_verify_order_fixtures

        def document(workspace, identifier, kind, labels, tests=(), **relations):
            body = "".join(f"- [{identifier}:{label}] [ACTOR:A] [ALWAYS] [MUST] [CONSTRAINT] x。\n" for label in labels)
            return {"workspaceId": workspace, "kind": kind, "body": body, "path": f"{identifier}.md",
                    "frontmatter": {"id": identifier, "title": "t", "status": "approved", "tests": list(tests),
                                    "relations": {key: value for key, value in relations.items()}}}

        documents = {
            "platform::REQ-001": document("platform", "REQ-001", "requirement", ["AC-10", "AC-02"],
                                          [{"path": "t.py", "covers": ["REQ-001:AC-02", "REQ-001:AC-10"], "command": "p"}]),
            "api::TECH-010": document("api", "TECH-010", "technical", ["C-01"],
                                      [{"path": "u.py", "covers": ["api::TECH-010:C-01"], "command": "b"}],
                                      refines=["platform::REQ-001:AC-02"]),
        }
        targets, ordered = module.reference_statements(documents, "platform::REQ-001")
        # 内部の並び: 起点の規範文を文書に書いた順、その後に具体化文書の規範文。出力する修飾IDの辞書順は別に求める。
        self.assertEqual(targets, ["platform::REQ-001:AC-10", "platform::REQ-001:AC-02", "api::TECH-010:C-01"])
        self.assertEqual(sorted(set(targets)), ["api::TECH-010:C-01", "platform::REQ-001:AC-02", "platform::REQ-001:AC-10"])
        # 2つ以上のワークスペースのテスト割当ては、`commands[]`の並びが規範から導けない（確認事項C62）ので止まる。
        with self.assertRaisesRegex(ValueError, "複数のワークスペース"):
            module.reference_bindings(documents, ordered, targets)
        # 1つのワークスペースのテスト割当ては、コマンド名の辞書順にまとめる（テストのパスと`covers`は辞書順）。
        documents["platform::REQ-001"]["frontmatter"]["tests"] = []
        documents["api::TECH-010"]["frontmatter"]["tests"] = [
            {"path": "u.py", "covers": ["api::TECH-010:C-01", "platform::REQ-001:AC-10", "platform::REQ-001:AC-02"], "command": "b"},
            {"path": "v.py", "covers": ["platform::REQ-001:AC-02"], "command": "a"}]
        self.assertEqual(module.reference_bindings(documents, ordered, targets),
                         [("api", "a", ["v.py"], ["platform::REQ-001:AC-02"]),
                          ("api", "b", ["u.py"], ["api::TECH-010:C-01", "platform::REQ-001:AC-02", "platform::REQ-001:AC-10"])])
        # 対象のMUSTにテスト対応がなければ拒否する。
        documents["api::TECH-010"]["frontmatter"]["tests"] = [{"path": "u.py", "covers": ["api::TECH-010:C-01"], "command": "b"}]
        with self.assertRaisesRegex(ValueError, "MUST"):
            module.reference_bindings(documents, ordered, targets)

    def test_multi_verify_order_expected_orders_distinguish_the_defect(self):
        """リテラルの期待する並びは、修正前の並び（内部の並び）と異なる。対照は同じ。ハッシュ値は材料の規範文の並びで変わる（C60）。"""
        module = multi_verify_order_fixtures
        for identifier in module.CASES:
            with self.subTest(identifier=identifier):
                expected, defective = module.EXPECTED_STATEMENTS[identifier], module.DEFECTIVE_STATEMENTS[identifier]
                self.assertEqual(sorted(defective), expected)
                self.assertEqual(sorted(set(expected)), expected)
                if identifier == "MULTI-044-04":
                    self.assertEqual(defective, expected)
                else:
                    self.assertNotEqual(defective, expected)
        # C60: 材料の規範文を文書に書いた順にすると、リテラルのハッシュ値と異なる値になる（規範は`id`の辞書順）。
        for identifier in ("MULTI-044-01", "MULTI-044-05"):
            material = module.reviewed_digest_input(identifier)
            self.assertEqual([item["id"] for item in material["documents"][0]["statements"]], ["REQ-001:AC-02", "REQ-001:AC-10"])
            wrong = copy.deepcopy(material)
            wrong["documents"][0]["statements"].reverse()
            self.assertNotEqual(module.digest_reference.digest(module.digest_reference.canonical_bytes(wrong)), module.expected_digest(identifier))
        # 目的`interpret`は、コマンドとタイムアウトを材料に含めない。`verify`は含める。
        self.assertEqual(module.reviewed_digest_input("MULTI-044-05")["settings"]["commands"], [])
        self.assertEqual(module.reviewed_digest_input("MULTI-044-05")["settings"]["verifyTimeouts"], [])
        self.assertEqual(len(module.reviewed_digest_input("MULTI-044-01")["settings"]["commands"]), 1)

    def test_multi_verify_order_audit_rejects_changed_expectations(self):
        """期待結果・起動条件・副作用の改変を拒否する。"""
        module = multi_verify_order_fixtures

        def swap(values, first, second):
            values[first], values[second] = values[second], values[first]

        results = {
            "status": lambda v: v.update(status="failed"),
            "diagnostics-add": lambda v: v["diagnostics"].append({"code": "SPEC-VERIFY-BLOCKED-001"}),
            "revision": lambda v: v.update(revision=None),
            "workspace": lambda v: v["workspace"].update(id="web"),
            "scope": lambda v: v.update(scope="all"),
            "digest": lambda v: (v["targetResults"][0] if "targetResults" in v else v).update(contextDigest="sha256:" + "0" * 64),
            "digest-null": lambda v: (v["targetResults"][0] if "targetResults" in v else v).update(contextDigest=None),
            "target-status": lambda v: v["targetResults"][0].update(status="blocked"),
            "target": lambda v: v["targetResults"][0].update(target="REQ-002"),
            "statements-swap": lambda v: swap(v["targetResults"][0]["statements"], 0, 1),
            "statements-defective-order": lambda v: v["targetResults"][0]["statements"].reverse(),
            "statements-drop": lambda v: v["targetResults"][0]["statements"].pop(),
            "statements-duplicate": lambda v: v["targetResults"][0]["statements"].append(v["targetResults"][0]["statements"][0]),
            "statements-clear": lambda v: v["targetResults"][0]["statements"].clear(),
            "binding-refs": lambda v: v["targetResults"][0]["bindingRefs"].append("root::other"),
            "binding-refs-clear": lambda v: v["targetResults"][0]["bindingRefs"].clear(),
            "target-diagnostics": lambda v: v["targetResults"][0]["diagnostics"].append({"code": "CTX-COVERAGE-TEST-001"}),
            "commands-clear": lambda v: v["commands"].clear(),
            "command-covers-swap": lambda v: swap(v["commands"][0]["covers"], 0, 1),
            "command-covers-drop": lambda v: v["commands"][0]["covers"].pop(),
            "command-tests": lambda v: v["commands"][0]["tests"].append("tests/extra.py"),
            "command-argv": lambda v: v["commands"][0]["argv"].__setitem__(0, "/bin/false"),
            "command-status": lambda v: v["commands"][0].update(status="failed"),
            "command-exit-code": lambda v: v["commands"][0].update(exitCode=1),
            "command-binding-id": lambda v: v["commands"][0].update(bindingId="root::other"),
            "documents-drop": lambda v: v["documents"].pop(),
            "documents-role": lambda v: v["documents"][0].update(role="refinement"),
            "documents-count": lambda v: v["resolution"].update(documentCount=2),
            "roots": lambda v: v["roots"].append("REQ-002"),
            "ledger-add": lambda v: v["constraintLedger"]["statements"].append({"id": "REQ-001:AC-02"}),
            "coverage-must": lambda v: v["coverage"]["must"]["total"].append("REQ-001:AC-02"),
            "purpose": lambda v: v.update(purpose="implement"),
            "detail": lambda v: v["projection"].update(detail="standard"),
        }
        manifests = {
            "status": lambda v: v["expect"].update(status="failed"),
            "exit-code": lambda v: v["expect"].update(exitCode=1),
            "cwd": lambda v: v["invocation"].update(cwd="services/api"),
            "root": lambda v: v["invocation"]["argv"].__setitem__(1, "REQ-002"),
            "argv-extra": lambda v: v["invocation"]["argv"].insert(1, "--all-workspaces"),
            "argv-purpose": lambda v: v["invocation"]["argv"].__setitem__(v["invocation"]["argv"].index("--purpose") + 1, "implement"),
            "env": lambda v: v["invocation"].update(env={"PATH": "/dev/null"}),
            "no-git": lambda v: v["setup"].update(git=False),
            "operations": lambda v: v["setup"]["operations"].append({"op": "delete", "path": ".spec/bitz.yaml"}),
            "report": lambda v: v["expect"].update(reportFileCount=1),
        }
        mutations = []
        for identifier in module.CASES:
            result_file = f"expected/{module.CASES[identifier]['operation']}.json"
            mutations += [(identifier, result_file, name, change) for name, change in results.items()]
            mutations += [(identifier, "manifest.json", name, change) for name, change in manifests.items()]
            mutations.append((identifier, "side-effects.json", "extra", lambda v: v["before"]["repository"].update(extra={"kind": "directory"})))
            mutations.append((identifier, "side-effects.json", "policy", lambda v: v.update(policy="read-write")))
        applied = 0
        for index, (identifier, relative, name, mutate) in enumerate(mutations):
            with tempfile.TemporaryDirectory() as temporary:
                root = self.copy_multi_fixture(temporary, identifier)
                path = root / "multi" / identifier / relative
                value = json.loads(path.read_text())
                before = json.dumps(value, sort_keys=True)
                try:
                    mutate(value)
                except (KeyError, IndexError, TypeError, AttributeError, ValueError):
                    continue
                if json.dumps(value, sort_keys=True) == before:
                    continue
                applied += 1
                path.write_text(json.dumps(value))
                with self.subTest(index=index, identifier=identifier, file=relative, mutation=name):
                    self.assertEqual(module.validate(root, {identifier})["status"], "Failed")
        # 改変の適用が空振りしていないこと。
        self.assertGreater(applied, 100)

    def test_multi_verify_order_audit_rejects_changed_corpus(self):
        """入力の欠落と追加（バイト列の照合）と、欠陥を検出する構成を消す入力の書換え（参照計算と原因の構成の検査）を拒否する。"""
        module = multi_verify_order_fixtures
        for identifier in module.CASES:
            names = sorted(f"repo/{name}" for name in module.reviewed_inputs(identifier) if name.endswith(".md") or name.endswith("bitz.yaml"))
            for name in [*names, "extra"]:
                with self.subTest(identifier=identifier, file=name), tempfile.TemporaryDirectory() as temporary:
                    root = self.copy_multi_fixture(temporary, identifier)
                    fixture = root / "multi" / identifier
                    if name == "extra":
                        (fixture / "repo/extra.txt").write_text("x")
                    else:
                        (fixture / name).unlink()
                    self.assertEqual(module.validate(root, {identifier})["status"], "Failed")
        # 原因を消す書換え。入力のバイト列の照合とスナップショットを通した上で（書換え後の内容を`reviewed_inputs`にし、副作用の期待値を作り直す）、
        # 参照計算と原因の構成の検査が拒否することを確かめる（バイト列の照合で先に拒否される空振りを避ける）。
        sorted_statements = (".spec/requirements/REQ-001.md", "- [REQ-001:AC-10] [ACTOR", "- [REQ-001:AC-01] [ACTOR")
        edits = {
            # 番号の大きい規範文を先に書く構成を、番号の順へ変える。
            "MULTI-044-01": [sorted_statements],
            # 起点を具体化する文書が、自分自身を具体化する（循環）。
            "MULTI-044-02": [(".spec/technical/TECH-003.md", "refines: [TECH-005:C-01]", "refines: [TECH-003:C-01]")],
            # 起点の規範文のテスト対応を消す（対象のMUSTにテスト対応がない）。
            "MULTI-044-03": [("services/api/.spec/technical/TECH-010.md", "covers: [api::TECH-010:C-01, platform::REQ-001:AC-01]",
                              "covers: [api::TECH-010:C-01]")],
            # 対照の入力を、修正前の並びが辞書順でない形へ変える。
            "MULTI-044-04": [(".spec/requirements/REQ-001.md", "- [REQ-001:AC-01] [ACTOR", "- [REQ-001:AC-03] [ACTOR")],
            "MULTI-044-05": [sorted_statements],
        }
        byte_phrases = ("入力がレビュー済みのcorpusと異なります", "隔離した準備手順が固定したスナップショットと異なります")
        for identifier, changes in edits.items():
            for relative, old, new in changes:
                with self.subTest(identifier=identifier, file=relative, old=old), tempfile.TemporaryDirectory() as temporary:
                    root = self.copy_multi_fixture(temporary, identifier)
                    fixture = root / "multi" / identifier
                    path = fixture / "repo" / relative
                    self.assertIn(old, path.read_text())
                    path.write_text(path.read_text().replace(old, new))
                    edited = dict(module.reviewed_inputs(identifier))
                    edited[relative] = path.read_bytes()
                    manifest = json.loads((fixture / "manifest.json").read_text())
                    repository = fixture_setup(fixture, manifest, Path(temporary) / "regen" / "repo")
                    external = {key: Path(temporary) / "regen" / key for key in ("home", "cache", "temporary")}
                    for directory in external.values():
                        directory.mkdir()
                    state = module.observe(repository, external)
                    (fixture / "side-effects.json").write_text(json.dumps({"schemaVersion": "1.0", "policy": "read-only", "before": state, "after": state}))
                    with patch.object(module, "reviewed_inputs", lambda _identifier, edited=edited: edited):
                        outcome = module.validate(root, {identifier})
                    self.assertEqual(outcome["status"], "Failed")
                    self.assertEqual(len(outcome["errors"]), 1)
                    self.assertFalse(any(phrase in outcome["errors"][0] for phrase in byte_phrases), outcome["errors"][0])
                    self.assertNotIn("KeyError", outcome["errors"][0])

    def test_multi_early_report_fixtures(self):
        """`MULTI-045-01`〜`14`: `--all-workspaces`の早期の結果が`--report`をルートワークスペースへ保存することを固定する（確認事項C53）。"""
        module = multi_early_report_fixtures
        result = module.validate()
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["prepared"], [f"MULTI-045-{number:02d}" for number in range(1, 15)])
        self.assertEqual(result["references"], 1)
        self.assertEqual(result["core_execution"], "Not run")
        # 複製した状態でも通る（以降の拒否の試験が、複製の不備で空振りしていないことの陽性対照）。
        for identifier in module.CASES:
            with self.subTest(identifier=identifier), tempfile.TemporaryDirectory() as temporary:
                root = self.copy_multi_fixture(temporary, identifier)
                self.assertEqual(module.validate(root, {identifier})["errors"], [])

    def test_multi_early_report_reference_rules(self):
        """保存の失敗の診断の並び（結果・診断・終了コード §7）、状態と終了コード（§3）、保存の件数（§8）の参照計算。"""
        module = multi_early_report_fixtures

        def diagnostic(workspace, path, code="SPEC-X-001"):
            return {"code": code, "source": {"kind": "file", "workspaceId": workspace, "path": path}}

        write = diagnostic("platform", ".spec/reports", "SPEC-REPORT-WRITE-001")
        # 同一性を構成できない発生元（`workspaceId: null`）が先、次に文字列のID、同じIDでは`path`、`code`の辞書順。
        ordered = [diagnostic(None, "z"), diagnostic("platform", ".spec/bitz.yaml"), write,
                   diagnostic("platform", "apps/web/.spec/bitz.yaml"), diagnostic("web", "a")]
        self.assertEqual(sorted(reversed(ordered), key=module.section7_key), ordered)
        # ワークスペースIDを持たない発生元（`environment`）は、`workspaceId: null`の`file`の後、文字列のIDの`file`の前に並ぶ。
        environment = {"code": "SPEC-MULTI-GIT-001", "source": {"kind": "environment", "component": "git"}}
        null_write = diagnostic(None, ".spec/reports", "SPEC-REPORT-WRITE-001")
        self.assertEqual(sorted([environment, null_write], key=module.section7_key), [null_write, environment])
        self.assertEqual(sorted([diagnostic("platform", ".spec/bitz.yaml"), environment, null_write], key=module.section7_key),
                         [null_write, environment, diagnostic("platform", ".spec/bitz.yaml")])
        # 保存の失敗は末尾に足さず、この順に入れる: `path`が後ろの診断があれば、保存の失敗はその前に並ぶ。
        appended = [diagnostic("platform", "apps/web/.spec/bitz.yaml"), write]
        self.assertEqual(sorted(appended, key=module.section7_key), [write, appended[0]])
        # `workspaceId: null`の保存の失敗は、文字列のIDの診断より前に並ぶ。
        self.assertEqual(sorted([diagnostic("platform", ".spec/bitz.yaml"), diagnostic(None, ".spec/reports")], key=module.section7_key)[0]["source"]["workspaceId"], None)
        self.assertEqual(module.worst_status([{"resultStatus": "failed"}, {"resultStatus": "error"}]), "error")
        self.assertEqual(module.worst_status([{"resultStatus": "blocked"}, {"resultStatus": "failed"}]), "failed")
        self.assertEqual({status: module.EXIT_CODES[status] for status in module.SEVERITY_ORDER},
                         {"passed": 0, "passed_with_warnings": 0, "blocked": 2, "failed": 1, "error": 3})
        # 原因、`--report`の有無、保存先の状態の全組合せの結果。
        expectations = {
            ("member-missing", True, "directory"): (["SPEC-MULTI-MEMBER-001"], ["platform"], "failed", 1, 1),
            ("member-missing", True, "file"): (["SPEC-MULTI-MEMBER-001", "SPEC-REPORT-WRITE-001"], ["platform", "platform"], "error", 3, 0),
            ("member-missing", False, "directory"): (["SPEC-MULTI-MEMBER-001"], ["platform"], "failed", 1, 0),
            ("member-missing", False, "file"): (["SPEC-MULTI-MEMBER-001"], ["platform"], "failed", 1, 0),
            ("root-id", True, "directory"): (["SPEC-MULTI-CONFIG-001"], [None], "failed", 1, 1),
            ("root-id", True, "file"): (["SPEC-MULTI-CONFIG-001", "SPEC-REPORT-WRITE-001"], [None, None], "error", 3, 0),
            ("root-id", True, "absent"): (["SPEC-MULTI-CONFIG-001", "SPEC-REPORT-WRITE-001"], [None, None], "error", 3, 0),
            # Gitの境界を確定できない停止（`environment`の発生元）。保存の失敗が先に並ぶ。保存できれば`blocked`／2。
            ("git", True, "file"): (["SPEC-REPORT-WRITE-001", "SPEC-MULTI-GIT-001"], [None, None], "error", 3, 0),
            ("git", True, "directory"): (["SPEC-MULTI-GIT-001"], [None], "blocked", 2, 1),
            ("git", False, "file"): (["SPEC-MULTI-GIT-001"], [None], "blocked", 2, 0),
        }
        for (cause, report, reports), (codes, workspaces, status, exit_code, saved) in expectations.items():
            with self.subTest(cause=cause, report=report, reports=reports):
                root_id = "platform" if cause == "member-missing" else None
                outcome = module.reference_outcome({"report": report}, {"cause": cause, "rootId": root_id, "reports": reports})
                self.assertEqual({key: value for key, value in outcome.items() if key != "kinds"},
                                 {"codes": codes, "workspaces": workspaces, "status": status, "exit": exit_code, "saved": saved})
                self.assertEqual(outcome["kinds"], ["environment" if code == "SPEC-MULTI-GIT-001" else "file" for code in codes])
        with self.assertRaises(ValueError):
            module.reference_outcome({"report": True}, {"cause": None, "rootId": "platform", "reports": "directory"})

    def test_multi_early_report_expected_results_distinguish_the_defect(self):
        """修正前のCore（`--report`を無視して保存せず、保存の失敗も返さない）の結果と異なる期待値を持つ。対照は修正の前後で同じ。"""
        module = multi_early_report_fixtures
        for identifier, case in module.CASES.items():
            with self.subTest(identifier=identifier):
                manifest = json.loads((audit.FIXTURES / "multi" / identifier / "manifest.json").read_text())
                result = json.loads((audit.FIXTURES / "multi" / identifier / module.RESULT_FILES[case["op"]]).read_text())
                # 修正前: 停止の診断1件だけの結果（`failed`／1）を返し、レポートは0件。
                stop = {"root-id": ("SPEC-MULTI-CONFIG-001", "failed", 1), "member-missing": ("SPEC-MULTI-MEMBER-001", "failed", 1),
                        "git": ("SPEC-MULTI-GIT-001", "blocked", 2)}[case["cause"]]
                defective = ([stop[0]], stop[1], stop[2], 0)
                actual = ([item["code"] for item in result["diagnostics"]], result["status"], manifest["expect"]["exitCode"],
                          manifest["expect"]["reportFileCount"])
                if not case["report"]:
                    self.assertEqual(actual, defective)
                else:
                    self.assertNotEqual(actual, defective)
                    self.assertEqual(("--report" in manifest["invocation"]["argv"]), True)
        # 保存できるケースはレポートがちょうど1件、保存できないケースは0件でSPEC-REPORT-WRITE-001が末尾に入り、状態は`error`／3。
        self.assertEqual([module.saved_count(identifier) for identifier in module.CASES], [1, 1, 0, 0, 1, 1, 0, 0, 0, 0, 0, 0, 1, 1])
        for identifier in ("MULTI-045-03", "MULTI-045-04", "MULTI-045-07", "MULTI-045-08"):
            result = module.reviewed_result(identifier)
            self.assertEqual((result["status"], [item["code"] for item in result["diagnostics"]][-1]), ("error", "SPEC-REPORT-WRITE-001"))
        # `11`・`12`は、保存の失敗が末尾ではなく先頭に並ぶ入力（末尾に足す実装と区別できる）。
        for identifier in ("MULTI-045-11", "MULTI-045-12"):
            result = module.reviewed_result(identifier)
            self.assertEqual([item["code"] for item in result["diagnostics"]], ["SPEC-REPORT-WRITE-001", "SPEC-MULTI-GIT-001"])
            self.assertEqual((result["status"], result["revision"]), ("error", None))
        # ルートの同一性を構成できない入力の保存の失敗は`workspaceId: null`、明示したルートでは`platform`。
        self.assertIsNone(module.reviewed_result("MULTI-045-07")["diagnostics"][-1]["source"]["workspaceId"])
        self.assertIsNone(module.reviewed_result("MULTI-045-11")["diagnostics"][0]["source"]["workspaceId"])
        self.assertEqual(module.reviewed_result("MULTI-045-03")["diagnostics"][-1]["source"]["workspaceId"], "platform")

    def test_multi_early_report_audit_rejects_changed_expectations(self):
        """期待結果・起動条件・副作用の改変を拒否する。"""
        module = multi_early_report_fixtures

        def last(values, **changes):
            values["diagnostics"][-1].update(changes)

        def source(values, **changes):
            values["diagnostics"][-1]["source"].update(changes)

        results = {
            "status": lambda v: v.update(status="passed"),
            "status-failed": lambda v: v.update(status="failed" if v["status"] == "error" else "error"),
            "operation": lambda v: v.update(operation="doctor"),
            "scope": lambda v: v.update(scope="full"),
            "diagnostics-drop": lambda v: v["diagnostics"].pop(),
            "diagnostics-clear": lambda v: v["diagnostics"].clear(),
            "diagnostics-add": lambda v: v["diagnostics"].append(copy.deepcopy(v["diagnostics"][0])),
            "diagnostics-reverse": lambda v: v["diagnostics"].reverse(),
            "code": lambda v: last(v, code="SPEC-MULTI-GIT-001"),
            "summary": lambda v: last(v, summary="x"),
            "severity": lambda v: last(v, severity="warning"),
            "effect": lambda v: last(v, resultStatus="blocked"),
            "source-workspace": lambda v: source(v, workspaceId="web"),
            "source-workspace-swap": lambda v: source(v, workspaceId="platform" if v["diagnostics"][-1]["source"]["workspaceId"] is None else None),
            "source-path": lambda v: source(v, path="apps/web/.spec/reports"),
            "source-key": lambda v: source(v, key="members"),
            "source-line": lambda v: source(v, line=1),
            "suggested-action": lambda v: last(v, suggestedAction="x"),
            "multi-id": lambda v: v["multiWorkspace"].update(id="root"),
            "multi-id-swap": lambda v: v["multiWorkspace"].update(id="platform" if v["multiWorkspace"]["id"] is None else None),
            "multi-path": lambda v: v["multiWorkspace"].update(path="apps/web"),
            "workspaces": lambda v: v["workspaces"].append({"id": "web", "path": "apps/web", "status": "passed", "diagnostics": []}),
            "workspace": lambda v: v.update(workspace={"id": "platform", "path": "."}),
            "revision-dirty": lambda v: v["revision"].update(dirty=True),
            "revision-null": lambda v: v.update(revision=None),
            "revision-object": lambda v: v.update(revision={"commit": "0" * 40, "dirty": False}) if v["revision"] is None else None,
            "revision-base": lambda v: v["revision"].update(base="1" * 40) if "base" in v["revision"] else v["revision"].update(base="0" * 40),
            "duration": lambda v: v.update(durationMs=1),
        }
        manifests = {
            "status": lambda v: v["expect"].update(status="passed"),
            "exit-code": lambda v: v["expect"].update(exitCode=0),
            "report-count": lambda v: v["expect"].update(reportFileCount=v["expect"]["reportFileCount"] + 1),
            "report-count-zero": lambda v: v["expect"].update(reportFileCount=0),
            "report-flag": lambda v: v["invocation"]["argv"].remove("--report") if "--report" in v["invocation"]["argv"]
            else v["invocation"]["argv"].append("--report"),
            "all-workspaces": lambda v: v["invocation"]["argv"].remove("--all-workspaces"),
            "operation": lambda v: v["invocation"]["argv"].__setitem__(0, "doctor"),
            "cwd": lambda v: v["invocation"].update(cwd="apps/web"),
            "env": lambda v: v["invocation"].update(env={"PATH": "/dev/null"}),
            "no-git": lambda v: v["setup"].update(git=False),
            "operations": lambda v: v["setup"]["operations"].append({"op": "delete", "path": ".spec/bitz.yaml"}),
            "result-file": lambda v: v["expect"].update(resultFile="expected/doctor.json"),
        }
        effects = {
            "policy-read-only": lambda v: v.update(policy="read-only"),
            "policy-report": lambda v: v.update(policy="explicit-report", report={
                "directory": ".spec/reports", "createdCount": 1, "namePattern": module.NAME_PATTERN, "temporaryFilesRemaining": 0}),
            "policy-read-write": lambda v: v.update(policy="read-write"),
            "report-drop": lambda v: v.pop("report"),
            "report-directory": lambda v: v["report"].update(directory="apps/web/.spec/reports"),
            "report-count": lambda v: v["report"].update(createdCount=2),
            "report-pattern-loose": lambda v: v["report"].update(namePattern=".*"),
            "report-pattern-bad": lambda v: v["report"].update(namePattern="^[0-9]{8}T[0-9]{6}Z-doctor\\.json$"),
            "report-temporary": lambda v: v["report"].update(temporaryFilesRemaining=1),
            "before-extra": lambda v: v["before"]["repository"].update(extra={"kind": "directory"}),
            "after-extra": lambda v: v["after"]["repository"].update(extra={"kind": "directory"}),
            "after-member-report": lambda v: v["after"]["repository"].update(
                {"apps/web/.spec/reports": {"kind": "directory"}, "apps/web/.spec/reports/x.json": {"kind": "file", "executable": False, "sha256": "0" * 64}}),
            "after-existing-report": lambda v: v["after"]["repository"].pop(module.EXISTING_REPORT),
        }
        mutations = []
        for identifier in module.CASES:
            result_file = f"expected/{module.CASES[identifier]['op']}.json"
            mutations += [(identifier, result_file, name, change) for name, change in results.items()]
            mutations += [(identifier, "manifest.json", name, change) for name, change in manifests.items()]
            mutations += [(identifier, "side-effects.json", name, change) for name, change in effects.items()]
        applied = 0
        for index, (identifier, relative, name, mutate) in enumerate(mutations):
            with tempfile.TemporaryDirectory() as temporary:
                root = self.copy_multi_fixture(temporary, identifier)
                path = root / "multi" / identifier / relative
                value = json.loads(path.read_text())
                before = json.dumps(value, sort_keys=True)
                try:
                    mutate(value)
                except (KeyError, IndexError, TypeError, AttributeError, ValueError):
                    continue
                if json.dumps(value, sort_keys=True) == before:
                    continue
                applied += 1
                path.write_text(json.dumps(value))
                with self.subTest(index=index, identifier=identifier, file=relative, mutation=name):
                    self.assertEqual(module.validate(root, {identifier})["status"], "Failed")
        # 改変の適用が空振りしていないこと。
        self.assertGreater(applied, 400)

    def test_multi_early_report_audit_rejects_changed_corpus(self):
        """入力の欠落と追加（バイト列の照合）と、欠陥を検出する構成を消す入力の書換え（参照計算と原因の構成の検査）を拒否する。"""
        module = multi_early_report_fixtures
        for identifier in module.CASES:
            names = sorted(f"repo/{name}" for name in module.reviewed_inputs(identifier) if name.endswith(".md") or name.endswith("bitz.yaml")
                           or name == ".spec/reports" or name.endswith("existing.json"))
            for name in [*names, "extra"]:
                with self.subTest(identifier=identifier, file=name), tempfile.TemporaryDirectory() as temporary:
                    root = self.copy_multi_fixture(temporary, identifier)
                    fixture = root / "multi" / identifier
                    if name == "extra":
                        (fixture / "repo/extra.txt").write_text("x")
                    else:
                        (fixture / name).unlink()
                    self.assertEqual(module.validate(root, {identifier})["status"], "Failed")
        # 原因を消す書換え。入力のバイト列の照合とスナップショットを通した上で（書換え後の内容を`reviewed_inputs`にし、副作用の期待値を作り直す）、
        # 参照計算と原因の構成の検査が拒否することを確かめる（バイト列の照合で先に拒否される空振りを避ける）。
        api_config = ("add", "services/api/.spec/bitz.yaml", 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\nworkspace:\n  id: api\n')
        declare_root = (".spec/bitz.yaml", "multiWorkspace:", "workspace:\n  id: platform\nmultiWorkspace:")
        edits = {
            # メンバー`api`が設定を持つ（メンバーの設定の不在という原因がなくなる）。
            "MULTI-045-01": [api_config],
            # `web`の明示したIDがカタログと一致しない。
            "MULTI-045-02": [("apps/web/.spec/bitz.yaml", "id: web", "id: frontend")],
            # 保存を妨げる通常ファイルが別の内容になる。
            "MULTI-045-03": [(".spec/reports", "this path occupies", "this path does not occupy")],
            # メンバーの`.spec/reports`が存在する。
            "MULTI-045-04": [("add", "apps/web/.spec/reports/x.json", "{}\n")],
            # ルートが`workspace.id`を明示する（ルートの省略という原因がなくなる）。
            "MULTI-045-05": [declare_root],
            "MULTI-045-06": [("apps/web/.spec/bitz.yaml", "id: web", "id: x")],
            "MULTI-045-07": [declare_root],
            # カタログにない設定がGitで追跡されている。
            "MULTI-045-08": [("add", "tools/x/.spec/bitz.yaml", 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\nworkspace:\n  id: x\n')],
            "MULTI-045-09": [api_config],
            "MULTI-045-10": [api_config],
            # 保存を妨げる通常ファイルが別の内容になる（Gitのメタデータは入力に置けない: harnessが拒否する）。
            "MULTI-045-11": [(".spec/reports", "this path occupies", "this path does not occupy")],
            "MULTI-045-12": [("add", "tools/x/.spec/bitz.yaml", 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\nworkspace:\n  id: x\n')],
            # ルートが`workspace.id`を明示する（`multiWorkspace.id`が`null`という期待と合わなくなる）。
            "MULTI-045-13": [declare_root],
            "MULTI-045-14": [("apps/web/.spec/bitz.yaml", "id: web", "id: x")],
        }
        byte_phrases = ("入力がレビュー済みのcorpusと異なります", "隔離した準備手順が固定したスナップショットと異なります")
        for identifier, changes in edits.items():
            for change in changes:
                with self.subTest(identifier=identifier, change=change[:2]), tempfile.TemporaryDirectory() as temporary:
                    root = self.copy_multi_fixture(temporary, identifier)
                    fixture = root / "multi" / identifier
                    edited = dict(module.reviewed_inputs(identifier))
                    if change[0] == "add":
                        _, relative, content = change
                        path = fixture / "repo" / relative
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_text(content)
                    else:
                        relative, old, new = change
                        path = fixture / "repo" / relative
                        self.assertIn(old, path.read_text())
                        path.write_text(path.read_text().replace(old, new, 1))
                    edited[relative] = path.read_bytes()
                    manifest = json.loads((fixture / "manifest.json").read_text())
                    repository = fixture_setup(fixture, manifest, Path(temporary) / "regen" / "repo")
                    external = {key: Path(temporary) / "regen" / key for key in ("home", "cache", "temporary")}
                    for directory in external.values():
                        directory.mkdir()
                    state = module.observe_state(manifest, repository, external)
                    (fixture / "side-effects.json").write_text(json.dumps(module.reviewed_effects(identifier, state)))
                    with patch.object(module, "reviewed_inputs", lambda _identifier, edited=edited: edited):
                        outcome = module.validate(root, {identifier})
                    self.assertEqual(outcome["status"], "Failed")
                    self.assertEqual(len(outcome["errors"]), 1)
                    self.assertFalse(any(phrase in outcome["errors"][0] for phrase in byte_phrases), outcome["errors"][0])
                    self.assertNotIn("KeyError", outcome["errors"][0])

    def test_multi_self_qualified_covers_fixtures(self):
        """`MULTI-046-01`〜`04`: 自ワークスペースを自身のIDで修飾したcoversをcheckが非修飾形式と同じに扱うことを固定する（確認事項C56）。"""
        module = multi_self_qualified_covers_fixtures
        result = module.validate()
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["prepared"], [f"MULTI-046-{number:02d}" for number in range(1, 5)])
        self.assertEqual(result["core_execution"], "Not run")
        # 複製した状態でも通る（以降の拒否の試験が、複製の不備で空振りしていないことの陽性対照）。
        for identifier in module.CASES:
            with self.subTest(identifier=identifier), tempfile.TemporaryDirectory() as temporary:
                root = self.copy_multi_fixture(temporary, identifier)
                self.assertEqual(module.validate(root, {identifier})["errors"], [])

    def test_multi_self_qualified_covers_reference_rules(self):
        """許可するcoversの集合（文書・フロントマター・状態仕様 §5の(a)(b)(c)）と、自ワークスペースの修飾を非修飾と同じに扱う参照計算。"""
        module = multi_self_qualified_covers_fixtures

        def statements(identifier, count):
            return "".join(f"- [{identifier}:C-0{number}] [ACTOR:A] [ALWAYS] [MUST] [CONSTRAINT] x。\n" for number in range(1, count + 1))

        def document(workspace, identifier, kind, count, refines=(), covers=()):
            relations = {"refines": list(refines)} if refines else {}
            frontmatter = {"id": identifier, "title": "t", "status": "approved", "relations": relations,
                           "tests": [{"path": "t.py", "covers": list(covers)}]}
            return {"workspaceId": workspace, "kind": kind, "body": statements(identifier, count), "frontmatter": frontmatter}

        documents = {
            "web::REQ-001": document("web", "REQ-001", "requirement", 1),
            "web::REQ-002": document("web", "REQ-002", "requirement", 2),
            # 規範文を持つ文書: 自身の規範文と、直接`refines`する規範文だけ。自身の文書IDは許可しない。
            "web::TECH-010": document("web", "TECH-010", "technical", 1, refines=["web::REQ-001:C-01"],
                                      covers=["web::TECH-010:C-01", "TECH-010:C-01", "web::REQ-001:C-01", "REQ-001:C-01",
                                              "web::TECH-010", "web::REQ-002:C-01", "REQ-099:C-01", "api::REQ-001:C-01"]),
            # 規範文を持たない文書: 自身の文書ID（修飾も非修飾も）。文書IDで`refines`すると、その文書の規範文すべて。
            "web::TECH-011": document("web", "TECH-011", "technical", 0, refines=["REQ-002"],
                                      covers=["web::TECH-011", "TECH-011", "web::REQ-002:C-01", "REQ-002:C-02", "web::REQ-001:C-01"]),
            # 存在しない参照先は何も許可しない。
            "web::TECH-012": document("web", "TECH-012", "technical", 0, refines=["web::REQ-099:C-01", "web::REQ-099"],
                                      covers=["web::REQ-099:C-01", "REQ-099:C-01"]),
            "api::REQ-001": document("api", "REQ-001", "requirement", 1),
            # 他のワークスペースの規範文は、その規範文または所有する文書を直接`refines`するときだけ許可する。
            "api::TECH-020": document("api", "TECH-020", "technical", 1, refines=["web::REQ-002"],
                                      covers=["web::REQ-002:C-01", "web::REQ-002:C-02", "web::REQ-001:C-01", "REQ-001:C-01"]),
        }
        self.assertEqual(module.allowed_covers(documents, "web::TECH-010"), {"web::TECH-010:C-01", "web::REQ-001:C-01"})
        self.assertEqual(module.allowed_covers(documents, "web::TECH-011"),
                         {"web::TECH-011", "web::REQ-002:C-01", "web::REQ-002:C-02"})
        self.assertEqual(module.allowed_covers(documents, "web::TECH-012"), {"web::TECH-012"})
        self.assertEqual(module.allowed_covers(documents, "api::TECH-020"),
                         {"api::TECH-020:C-01", "web::REQ-002:C-01", "web::REQ-002:C-02"})
        rejected = [(workspace, path, evidence) for workspace, path, _, evidence in module.reference_rejections(documents)]
        evidence = lambda name: [item[2] for item in rejected if item[1].endswith(name)]  # noqa: E731
        self.assertEqual(evidence("TECH-010.md"), ["web::TECH-010", "web::REQ-002:C-01", "REQ-099:C-01", "api::REQ-001:C-01"])
        self.assertEqual(evidence("TECH-011.md"), ["web::REQ-001:C-01"])
        self.assertEqual(evidence("TECH-012.md"), ["web::REQ-099:C-01", "REQ-099:C-01"])
        self.assertEqual(evidence("TECH-020.md"), ["web::REQ-001:C-01", "REQ-001:C-01"])
        self.assertEqual(evidence("REQ-001.md"), [])
        # 診断の順序は、ワークスペースのID、`path`の順（宣言した`evidence`は宣言の順を保つ）。
        self.assertEqual(rejected, sorted(rejected, key=lambda item: (item[0], item[1])))
        # 修飾の有無で拒否が変わらない: 自ワークスペースの修飾を外しても、拒否する要素は同じ。
        stripped = {}
        for name, value in documents.items():
            workspace = value["workspaceId"]
            copied = copy.deepcopy(value)
            copied["frontmatter"]["relations"] = {key: [module.plain(workspace, item) for item in items]
                                                  for key, items in value["frontmatter"]["relations"].items()}
            copied["frontmatter"]["tests"][0]["covers"] = [module.plain(workspace, item) for item in value["frontmatter"]["tests"][0]["covers"]]
            stripped[name] = copied
        self.assertEqual([(w, p, module.multi_crosscheck.qualify(w, e)) for w, p, _, e in module.reference_rejections(stripped)],
                         [(w, p, module.multi_crosscheck.qualify(w, e)) for w, p, _, e in module.reference_rejections(documents)])
        self.assertEqual(module.reference_counts(documents), {"web": (5, 4), "api": (2, 2)})

    def test_multi_self_qualified_covers_corpus_detects_the_defect(self):
        """入力が欠陥を検出できる形である: 修飾したcorpusは自ワークスペースの修飾のcoversを(a)(b)(c)で持ち、対照は修飾を持たない。"""
        module = multi_self_qualified_covers_fixtures
        qualified = module.documents_of("MULTI-046-01")
        self.assertIs(qualified, module.VALID_DOCUMENTS)
        self_qualified = [(local, text) for (workspace, local), spec in qualified.items() if workspace == "web"
                          for text in spec["covers"] if text.startswith("web::")]
        self.assertEqual(sorted(local for local, _ in self_qualified),
                         ["REQ-001", "REQ-002", "TECH-010", "TECH-010", "TECH-011", "TECH-012", "TECH-013"])
        plain = module.documents_of("MULTI-046-04")
        for (workspace, local), spec in plain.items():
            self.assertFalse([text for text in [*spec["covers"], *spec.get("refines", [])] if "::" in text], (workspace, local))
        # 対照は、修飾を外すだけで同じ文書であり、修飾した入力と同じ対象を指す。
        for key, spec in qualified.items():
            self.assertEqual([module.multi_crosscheck.qualify(key[0], text) for text in plain[key]["covers"]],
                             [module.multi_crosscheck.qualify(key[0], text) for text in spec["covers"]])
            self.assertEqual(plain[key]["statement"], spec["statement"])
        self.assertEqual(module.reviewed_result("MULTI-046-01"), module.reviewed_result("MULTI-046-04"))
        # 陰性対照は、存在しない規範文と`refines`していない規範文を1件ずつ持ち、修飾した通る`covers`と併記する。
        self.assertIs(module.documents_of("MULTI-046-03"), module.INVALID_DOCUMENTS)
        for identifier in ("MULTI-046-01", "MULTI-046-02", "MULTI-046-03", "MULTI-046-04"):
            with self.subTest(identifier=identifier), tempfile.TemporaryDirectory() as temporary:
                root = self.copy_multi_fixture(temporary, identifier)
                fixture = root / "multi" / identifier
                manifest = json.loads((fixture / "manifest.json").read_text())
                repository = fixture_setup(fixture, manifest, Path(temporary) / "work" / "repo")
                _, _, documents = multi_crosscheck.load_workspaces(repository)
                rejections = [(w, p, e) for w, p, _, e in module.reference_rejections(documents)]
                if identifier == "MULTI-046-03":
                    self.assertEqual(rejections, [("web", ".spec/requirements/REQ-001.md", "web::REQ-001:AC-99"),
                                                  ("web", ".spec/technical/TECH-010.md", "web::REQ-002:AC-01")])
                else:
                    self.assertEqual(rejections, [])
                # `MULTI-046-02`は、`web`の文書だけが対象で、他のワークスペースの文書を閉包に含めない。
                if identifier == "MULTI-046-02":
                    reference = multi_check_fixtures.reference_check(repository, "full", "web", "apps/web", None)
                    self.assertEqual(reference["inspected"], sorted(name for name in documents if name.startswith("web::")))
                    self.assertEqual(manifest["invocation"]["cwd"], "apps/web")

    def test_multi_self_qualified_covers_audit_rejects_changed_expectations(self):
        """期待結果・起動条件・副作用の改変を拒否する。"""
        module = multi_self_qualified_covers_fixtures
        pre_fix = module.rejection("web", ".spec/technical/TECH-010.md", "web::REQ-001:AC-01")

        def web(value):
            return value["workspaces"][2]

        all_passed = {
            "status": lambda v: v.update(status="failed"),
            "scope": lambda v: v.update(scope="full"),
            "top-level-diagnostic": lambda v: v["diagnostics"].append(copy.deepcopy(pre_fix)),
            "web-pre-fix-rejection": lambda v: (web(v)["diagnostics"].append(copy.deepcopy(pre_fix)), web(v).update(status="failed"),
                                                v.update(status="failed")),
            "platform-pre-fix-rejection": lambda v: v["workspaces"][0]["diagnostics"].append(
                module.rejection("platform", ".spec/requirements/REQ-001.md", "platform::REQ-001:AC-01")),
            "workspaces-reverse": lambda v: v["workspaces"].reverse(),
            "workspaces-drop": lambda v: v["workspaces"].pop(),
            "web-documents": lambda v: web(v).update(checkedDocumentCount=5),
            "web-statements": lambda v: web(v).update(checkedStatementCount=2),
            "platform-statements": lambda v: v["workspaces"][0].update(checkedStatementCount=0),
            "api-path": lambda v: v["workspaces"][1].update(path="apps/api"),
            "multi-workspace": lambda v: v["multiWorkspace"].update(id="web"),
            "revision": lambda v: v["revision"].update(dirty=True),
        }
        member_full = {
            "status": lambda v: v.update(status="failed"),
            "scope": lambda v: v.update(scope="selected"),
            "diagnostic": lambda v: v["diagnostics"].append(copy.deepcopy(pre_fix)),
            "documents": lambda v: v.update(checkedDocumentCount=5),
            "documents-closure": lambda v: v.update(checkedDocumentCount=7),
            "statements": lambda v: v.update(checkedStatementCount=2),
            "workspace-path": lambda v: v["workspace"].update(path="."),
            "workspace-id": lambda v: v["workspace"].update(id="platform", path="."),
            "revision": lambda v: v["revision"].update(dirty=True),
        }
        invalid = {
            "status": lambda v: v.update(status="passed"),
            "drop-first": lambda v: web(v)["diagnostics"].pop(0),
            "drop-second": lambda v: web(v)["diagnostics"].pop(1),
            "drop-all": lambda v: (web(v)["diagnostics"].clear(), web(v).update(status="passed"), v.update(status="passed")),
            "order": lambda v: web(v)["diagnostics"].reverse(),
            # `evidence`は宣言どおり（修飾したまま）。修飾を外した値や正規形式への置換は拒否する。
            "evidence-unqualified-first": lambda v: web(v)["diagnostics"][0].update(evidence="REQ-001:AC-99"),
            "evidence-unqualified-second": lambda v: web(v)["diagnostics"][1].update(evidence="REQ-002:AC-01"),
            "evidence-swap": lambda v: (web(v)["diagnostics"][0].update(evidence="web::REQ-002:AC-01"),
                                        web(v)["diagnostics"][1].update(evidence="web::REQ-001:AC-99")),
            # 修正前のCoreは、通る修飾のcoversも拒否する。
            "pre-fix-web": lambda v: web(v)["diagnostics"].append(module.rejection(
                "web", ".spec/requirements/REQ-001.md", "web::REQ-001:AC-01")),
            "pre-fix-platform": lambda v: v["workspaces"][0]["diagnostics"].append(
                module.rejection("platform", ".spec/requirements/REQ-001.md", "platform::REQ-001:AC-01")),
            "duplicate": lambda v: web(v)["diagnostics"].append(copy.deepcopy(web(v)["diagnostics"][0])),
            "key": lambda v: web(v)["diagnostics"][0]["source"].update(key="tests[1].covers"),
            "path": lambda v: web(v)["diagnostics"][0]["source"].update(path=".spec/technical/TECH-010.md"),
            "workspace-id": lambda v: web(v)["diagnostics"][1]["source"].update(workspaceId="platform"),
            "code": lambda v: web(v)["diagnostics"][0].update(code="SPEC-RELATION-MISSING-001"),
            "summary": lambda v: web(v)["diagnostics"][0].update(summary="x"),
            "severity": lambda v: web(v)["diagnostics"][0].update(severity="warning"),
            "top-level": lambda v: v["diagnostics"].append(copy.deepcopy(web(v)["diagnostics"][0])),
            "web-status": lambda v: web(v).update(status="passed"),
            "web-documents": lambda v: web(v).update(checkedDocumentCount=6),
        }
        manifests = {
            "status": lambda v: v["expect"].update(status="failed" if v["expect"]["status"] == "passed" else "passed"),
            "exit-code": lambda v: v["expect"].update(exitCode=2),
            "cwd": lambda v: v["invocation"].update(cwd="services/api"),
            "argv-extra": lambda v: v["invocation"]["argv"].insert(1, "--workspace"),
            "argv-drop": lambda v: v["invocation"]["argv"].pop(1),
            "env": lambda v: v["invocation"].update(env={"PATH": "/dev/null"}),
            "no-git": lambda v: v["setup"].update(git=False),
            "operations": lambda v: v["setup"]["operations"].append({"op": "delete", "path": ".spec/bitz.yaml"}),
        }
        mutations = []
        for identifier, table in (("MULTI-046-01", all_passed), ("MULTI-046-04", all_passed), ("MULTI-046-02", member_full),
                                  ("MULTI-046-03", invalid)):
            mutations += [(identifier, "expected/check.json", name, change) for name, change in table.items()]
        for identifier in module.CASES:
            mutations += [(identifier, "manifest.json", name, change) for name, change in manifests.items()]
            mutations.append((identifier, "side-effects.json", "extra", lambda v: v["before"]["repository"].update(extra={"kind": "directory"})))
            mutations.append((identifier, "side-effects.json", "policy", lambda v: v.update(policy="read-write")))
        applied = 0
        for index, (identifier, relative, name, mutate) in enumerate(mutations):
            with tempfile.TemporaryDirectory() as temporary:
                root = self.copy_multi_fixture(temporary, identifier)
                path = root / "multi" / identifier / relative
                value = json.loads(path.read_text())
                before = json.dumps(value, sort_keys=True)
                try:
                    mutate(value)
                except (KeyError, IndexError, TypeError, AttributeError, ValueError):
                    continue
                if json.dumps(value, sort_keys=True) == before:
                    continue
                applied += 1
                path.write_text(json.dumps(value))
                with self.subTest(index=index, identifier=identifier, file=relative, mutation=name):
                    self.assertEqual(module.validate(root, {identifier})["status"], "Failed")
        # 改変の適用が空振りしていないこと。
        self.assertGreater(applied, 80)

    def test_multi_self_qualified_covers_audit_rejects_changed_corpus(self):
        """入力の欠落と追加（バイト列の照合）と、原因の構成を消す入力の書換え（参照計算と原因の構成の検査）を拒否する。"""
        module = multi_self_qualified_covers_fixtures
        for identifier in module.CASES:
            names = sorted(f"repo/{name}" for name in module.reviewed_inputs(identifier) if name.endswith(".md") or name.endswith("bitz.yaml"))
            for name in [*names, "extra"]:
                with self.subTest(identifier=identifier, file=name), tempfile.TemporaryDirectory() as temporary:
                    root = self.copy_multi_fixture(temporary, identifier)
                    fixture = root / "multi" / identifier
                    if name == "extra":
                        (fixture / "repo/extra.txt").write_text("x")
                    else:
                        (fixture / name).unlink()
                    self.assertEqual(module.validate(root, {identifier})["status"], "Failed")
        # 原因を消す書換え。入力のバイト列の照合とスナップショットを通した上で（書換え後の内容を`reviewed_inputs`にし、副作用の期待値を作り直す）、
        # 参照計算と原因の構成の検査が拒否することを確かめる（バイト列の照合で先に拒否される空振りを避ける）。
        web = "apps/web/.spec/technical/"
        qualified_edits = [
            # (b)の文書IDの修飾を外す。
            (web + "TECH-011.md", "covers: [web::TECH-011]", "covers: [TECH-011]"),
            # (c)の文書IDで`refines`する分類を、規範文IDの`refines`へ変える。
            (web + "TECH-012.md", "refines: [web::REQ-002]", "refines: [web::REQ-002:AC-01]"),
            # `refines`していない規範文を`covers`へ足す（修飾した入力が拒否を含んではいけない）。
            (web + "TECH-010.md", "covers: [web::REQ-001:AC-01, web::TECH-010:C-01]", "covers: [web::REQ-001:AC-01, web::TECH-010:C-01, web::REQ-002:AC-01]"),
            # `refines`の先を変えて、(c)の`covers`が許可されない入力にする。
            (web + "TECH-013.md", "refines: [REQ-002:AC-01]", "refines: [REQ-001:AC-01]"),
            # 他のワークスペースの文書への参照を足す（`MULTI-046-02`の閉包を`web`に閉じる前提を崩す）。
            ("services/api/.spec/requirements/REQ-001.md", "status: approved\n", "status: approved\nrelations:\n  requires: [web::REQ-001]\n"),
        ]
        edits = {
            "MULTI-046-01": qualified_edits,
            "MULTI-046-02": qualified_edits,
            "MULTI-046-03": [
                # 存在しない規範文を存在する規範文へ変える（拒否が1件に減る）。
                ("apps/web/.spec/requirements/REQ-001.md", "web::REQ-001:AC-99", "web::REQ-001:AC-01"),
                # `refines`していない`covers`を、`refines`している規範文へ変える。
                (web + "TECH-010.md", "web::REQ-002:AC-01", "web::REQ-001:AC-01"),
                # `refines`の先を足して、2件目が許可される入力にする。
                (web + "TECH-010.md", "refines: [web::REQ-001:AC-01]", "refines: [web::REQ-001:AC-01, web::REQ-002:AC-01]"),
            ],
            "MULTI-046-04": [
                # 対照に修飾を持ち込む。
                (web + "TECH-011.md", "covers: [TECH-011]", "covers: [web::TECH-011]"),
                (web + "TECH-013.md", "refines: [REQ-002:AC-01]", "refines: [web::REQ-002:AC-01]"),
                # 対照に拒否する`covers`を持ち込む。
                (web + "TECH-010.md", "covers: [REQ-001:AC-01, TECH-010:C-01]", "covers: [REQ-001:AC-01, TECH-010:C-01, REQ-002:AC-01]"),
            ],
        }
        byte_phrases = ("入力がレビュー済みのcorpusと異なります", "隔離した準備手順が固定したスナップショットと異なります")
        for identifier, changes in edits.items():
            for relative, old, new in changes:
                with self.subTest(identifier=identifier, file=relative, old=old), tempfile.TemporaryDirectory() as temporary:
                    root = self.copy_multi_fixture(temporary, identifier)
                    fixture = root / "multi" / identifier
                    path = fixture / "repo" / relative
                    self.assertIn(old, path.read_text())
                    path.write_text(path.read_text().replace(old, new))
                    edited = dict(module.reviewed_inputs(identifier))
                    edited[relative] = path.read_bytes()
                    manifest = json.loads((fixture / "manifest.json").read_text())
                    repository = fixture_setup(fixture, manifest, Path(temporary) / "regen" / "repo")
                    external = {key: Path(temporary) / "regen" / key for key in ("home", "cache", "temporary")}
                    for directory in external.values():
                        directory.mkdir()
                    state = module.observe(repository, external)
                    (fixture / "side-effects.json").write_text(json.dumps({"schemaVersion": "1.0", "policy": "read-only", "before": state, "after": state}))
                    with patch.object(module, "reviewed_inputs", lambda _identifier, edited=edited: edited):
                        outcome = module.validate(root, {identifier})
                    self.assertEqual(outcome["status"], "Failed")
                    self.assertEqual(len(outcome["errors"]), 1)
                    self.assertFalse(any(phrase in outcome["errors"][0] for phrase in byte_phrases), outcome["errors"][0])
                    self.assertNotIn("KeyError", outcome["errors"][0])

    def test_multi_qualified_summary_fixtures(self):
        """`MULTI-047-01`〜`05`: 複合ワークスペースの診断のsummaryが作業ワークスペースのIDも修飾することを固定する（確認事項C47・C65）。"""
        module = multi_qualified_summary_fixtures
        result = module.validate()
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["prepared"], [f"MULTI-047-{number:02d}" for number in range(1, 6)])
        self.assertEqual(result["references"], 2)
        self.assertEqual(result["core_execution"], "Not run")
        # 複製した状態でも通る（以降の拒否の試験が、複製の不備で空振りしていないことの陽性対照）。
        for identifier in module.CASES:
            with self.subTest(identifier=identifier), tempfile.TemporaryDirectory() as temporary:
                root = self.copy_multi_fixture(temporary, identifier)
                self.assertEqual(module.validate(root, {identifier})["errors"], [])

    def test_multi_qualified_summary_reference_rules(self):
        """状態・先行TASK・カバレッジの診断の参照計算（関係・トレースモデル §6.2、結果・診断・終了コード §7）と、修正前の書き方の再現。"""
        module = multi_qualified_summary_fixtures

        def document(workspace, identifier, kind, status, body="", **relations):
            return {"workspaceId": workspace, "kind": kind, "body": body, "path": f".spec/{identifier}.md",
                    "frontmatter": {"id": identifier, "title": "t", "status": status, "relations": dict(relations)}}

        def statement(identifier):
            return f"- [{identifier}:AC-01] [ACTOR:A] [ALWAYS] [MUST] [CONSTRAINT] x。\n"

        documents = {
            "platform::TASK-002": document("platform", "TASK-002", "task", "open", requires=["TASK-001", "api::TASK-100", "api::TASK-101"]),
            "platform::TASK-001": document("platform", "TASK-001", "task", "cancelled"),
            "api::TASK-100": document("api", "TASK-100", "task", "done"),
            "api::TASK-101": document("api", "TASK-101", "task", "open"),
            "platform::REQ-001": document("platform", "REQ-001", "requirement", "approved", statement("REQ-001"), requires=["REQ-002", "api::REQ-003"]),
            "platform::REQ-002": document("platform", "REQ-002", "requirement", "approved", statement("REQ-002"), requires=["api::REQ-003"]),
            "api::REQ-003": document("api", "REQ-003", "requirement", "outdated", statement("REQ-003")),
        }
        # 先行TASKは、状態doneでないもの（cancelledとopen）だけを、宣言の順に返す。doneは返さない。
        found = module.reference_blocked(documents, "platform::TASK-002", "implement")
        self.assertEqual([item["summary"] for item in found], [
            "先行するplatform::TASK-001が状態cancelledで、状態doneではありません",
            "先行するapi::TASK-101が状態openで、状態doneではありません"])
        self.assertEqual([item["code"] for item in found], ["CTX-TASK-DEPENDENCY-001"] * 2)
        # 起点がTASKで状態openでなければ、先行TASKを検査せず、起点のCTX-STATE-001だけを返す（SINGLE-159と同じ）。
        documents["platform::TASK-002"]["frontmatter"]["status"] = "done"
        found = module.reference_blocked(documents, "platform::TASK-002", "implement")
        self.assertEqual([item["summary"] for item in found], ["platform::TASK-002は状態doneのため目的implementに適用できません"])
        # 起点がTASKでなければ、requiresで到達した文書のうち状態approvedでないもの（1回だけ）を、発生元のワークスペースIDの辞書順に返す。
        found = module.reference_blocked(documents, "platform::REQ-001", "implement")
        self.assertEqual([item["summary"] for item in found], ["api::REQ-003は状態outdatedのため目的implementに適用できません"])
        # 修正前の書き方は、作業ワークスペースの文書だけ修飾しない。
        documents["platform::REQ-002"]["frontmatter"]["status"] = "draft"
        wanted = ["api::REQ-003は状態outdatedのため目的implementに適用できません", "platform::REQ-002は状態draftのため目的implementに適用できません"]
        self.assertEqual([item["summary"] for item in module.reference_blocked(documents, "platform::REQ-001", "implement")], wanted)
        self.assertEqual([item["summary"] for item in module.reference_blocked(documents, "platform::REQ-001", "implement", qualify_active=False)],
                         [wanted[0], "REQ-002は状態draftのため目的implementに適用できません"])
        # カバレッジの診断: 未対応と未テストをそれぞれ返し、発生元のワークスペースID、path、codeの順に並べる。規範強度は規範文から読む。
        targets = ["platform::REQ-001:AC-01", "api::REQ-003:AC-01"]
        found = module.reference_coverage_diagnostics(documents, targets, ["api::REQ-003:AC-01"], ["platform::REQ-001:AC-01"])
        self.assertEqual([(item["source"]["workspaceId"], item["code"], item["summary"]) for item in found], [
            ("api", "CTX-COVERAGE-TEST-001", "対象規範文MUST api::REQ-003:AC-01にテスト対応がありません"),
            ("platform", "CTX-COVERAGE-TASK-001", "目的implementの対象規範文MUST platform::REQ-001:AC-01を実装するTASKがありません")])
        found = module.reference_coverage_diagnostics(documents, targets, [], [], qualify_active=False)
        self.assertEqual([item["summary"] for item in found], [
            "目的implementの対象規範文MUST api::REQ-003:AC-01を実装するTASKがありません", "対象規範文MUST api::REQ-003:AC-01にテスト対応がありません",
            "目的implementの対象規範文MUST REQ-001:AC-01を実装するTASKがありません", "対象規範文MUST REQ-001:AC-01にテスト対応がありません"])

    def test_multi_qualified_summary_expected_diagnostics_distinguish_the_defect(self):
        """リテラルの期待する診断は、修正前の書き方（作業ワークスペースのIDを修飾しない）の診断と異なり、作業ワークスペースと他のメンバーのIDが同じ出力に出る。"""
        module = multi_qualified_summary_fixtures
        for identifier, case in module.CASES.items():
            with self.subTest(identifier=identifier):
                single, _, _, documents = module.alias.load_tree(audit.FIXTURES / "multi" / identifier / "repo")
                self.assertFalse(single)
                active = case["workspace"]
                if case["outcome"] == "blocked":
                    defective = module.reference_blocked(documents, case["root"], "implement", qualify_active=False, active=active)
                else:
                    ordered, edges, _ = module.order.reference_order(documents, case["root"], "implement")
                    targets = module.order.reference_targets(documents, ordered, edges, case["root"])
                    addressed, tested, _, _ = module.order.reference_coverage(documents, ordered, targets)
                    defective = module.reference_coverage_diagnostics(documents, targets, addressed, tested, qualify_active=False, active=active)
                expected = module.EXPECTED_DIAGNOSTICS[identifier]
                self.assertEqual(len(defective), len(expected))
                self.assertNotEqual([item["summary"] for item in defective], [item["summary"] for item in expected])
                # 修正前の書き方では、作業ワークスペースのIDだけが修飾されない。他のメンバーのIDは変わらない。
                changed = [(old["summary"], new["summary"]) for old, new in zip(defective, expected) if old["summary"] != new["summary"]]
                for old, new in changed:
                    self.assertEqual(old, new.replace(f"{active}::", "", 1))
                unchanged = [new for old, new in zip(defective, expected) if old["summary"] == new["summary"]]
                self.assertEqual(bool(unchanged), identifier != "MULTI-047-01")
                # 期待するsummaryに現れるIDは、すべて修飾している（`<ワークスペース>::`のないREQ-/TECH-/TASK-のIDがない）。
                for item in expected:
                    for text in (item["summary"], item.get("suggestedAction", "")):
                        self.assertFalse(re.search(r"(?<![:A-Za-z0-9_-])(REQ|TECH|TASK)-[0-9]+", text), text)
        # 順序: 発生元のワークスペースID、path、codeの辞書順（01〜05の期待値の並びがこの規則に従う）。
        for identifier, expected in module.EXPECTED_DIAGNOSTICS.items():
            if identifier == "MULTI-047-02" or identifier == "MULTI-047-05":
                continue  # 同じ発生元・同じコードなので宣言の順
            with self.subTest(order=identifier):
                keys = [(item["source"]["workspaceId"], item["source"]["path"], item["code"]) for item in expected]
                self.assertEqual(keys, sorted(keys))

    def test_multi_qualified_summary_audit_rejects_changed_expectations(self):
        """期待結果・起動条件・副作用の改変を拒否する。"""
        module = multi_qualified_summary_fixtures

        def unqualify(value):
            active = value["workspace"]["id"]
            for item in value["diagnostics"]:
                for key in ("summary", "suggestedAction"):
                    if key in item:
                        item[key] = item[key].replace(f"{active}::", "", 1)

        def swap(values, first, second):
            values[first], values[second] = values[second], values[first]

        results = {
            "status": lambda v: v.update(status="failed"),
            "status-passed": lambda v: v.update(status="passed"),
            "unqualify-active": lambda v: unqualify(v),
            "summary-other-unqualified": lambda v: v["diagnostics"][-1].update(summary=v["diagnostics"][-1]["summary"].replace("api::", "").replace("platform::", "")),
            "summary-first": lambda v: v["diagnostics"][0].update(summary=v["diagnostics"][0]["summary"].replace("::", "-")),
            "action-unqualified": lambda v: v["diagnostics"][0].update(suggestedAction=v["diagnostics"][0]["suggestedAction"].replace("::", "")),
            "action-drop": lambda v: v["diagnostics"][0].pop("suggestedAction"),
            "action-add": lambda v: v["diagnostics"][0].update(suggestedAction="修正してください"),
            "diagnostics-drop": lambda v: v["diagnostics"].pop(),
            "diagnostics-clear": lambda v: v["diagnostics"].clear(),
            "diagnostics-reverse": lambda v: v["diagnostics"].reverse(),
            "diagnostics-duplicate": lambda v: v["diagnostics"].append(copy.deepcopy(v["diagnostics"][0])),
            "diagnostics-extra": lambda v: v["diagnostics"].append({"code": "CTX-STATE-001"}),
            "code": lambda v: v["diagnostics"][0].update(code="CTX-STATE-SUPERSEDED-001"),
            "severity": lambda v: v["diagnostics"][0].update(severity="warning"),
            "result-status": lambda v: v["diagnostics"][0].update(resultStatus="failed"),
            "source-workspace": lambda v: v["diagnostics"][0]["source"].update(workspaceId="web"),
            "source-null": lambda v: v["diagnostics"][0]["source"].update(workspaceId=None),
            "source-path": lambda v: v["diagnostics"][0]["source"].update(path=".spec/requirements/REQ-999.md"),
            "source-key": lambda v: v["diagnostics"][0]["source"].update(key="relations.refines"),
            "source-line": lambda v: v["diagnostics"][0]["source"].update(line=1),
            "evidence": lambda v: v["diagnostics"][0].update(evidence="TASK-001"),
            "digest": lambda v: v.update(contextDigest="sha256:" + "0" * 64),
            "digest-set": lambda v: v.update(contextDigest="sha256:" + "1" * 64) if v["contextDigest"] is None else v.update(contextDigest=None),
            "resolution-complete": lambda v: v["resolution"].update(complete=not v["resolution"]["complete"]),
            "resolution-unresolved": lambda v: v["resolution"].update(unresolvedStrongRelations=1),
            "resolution-workspaces": lambda v: v["resolution"]["workspaces"].append({"id": "web", "path": "apps/web"}),
            "resolution-edges": lambda v: v["resolution"]["crossWorkspaceEdges"].append(
                {"relation": "requires", "source": "api::REQ-001", "target": "platform::REQ-001"}),
            "documents-add": lambda v: v["documents"].append(copy.deepcopy(v["documents"][0])) if v["documents"] else v["documents"].append({}),
            "documents-reverse": lambda v: v["documents"].reverse(),
            "ledger-clear": lambda v: v["constraintLedger"]["statements"].clear() if v["constraintLedger"]["statements"] else v["constraintLedger"]["statements"].append({}),
            "coverage-total": lambda v: v["coverage"]["must"]["total"].append("platform::REQ-001:AC-01"),
            "coverage-unaddressed-drop": lambda v: v["coverage"]["must"]["unaddressed"].pop(),
            "coverage-untested-reverse": lambda v: v["coverage"]["must"]["untested"].reverse(),
            "coverage-should": lambda v: v["coverage"]["should"]["total"].append("platform::REQ-001:AC-01"),
            "coverage-adjacent": lambda v: v["coverage"]["adjacent"].append("platform::REQ-001:AC-01"),
            "workspace": lambda v: v["workspace"].update(id="web"),
            "workspace-path": lambda v: v["workspace"].update(path="apps/web"),
            "roots-unqualified": lambda v: v["roots"].__setitem__(0, v["roots"][0].partition("::")[2]),
            "roots-add": lambda v: v["roots"].append("platform::REQ-002"),
            "revision": lambda v: v.update(revision=None),
            "revision-dirty": lambda v: v["revision"].update(dirty=True),
            "detail": lambda v: v["projection"].update(detail="full"),
            "purpose": lambda v: v.update(purpose="verify"),
        }
        manifests = {
            "status": lambda v: v["expect"].update(status="failed"),
            "exit-code": lambda v: v["expect"].update(exitCode=1),
            "cwd": lambda v: v["invocation"].update(cwd="apps/web"),
            "purpose": lambda v: v["invocation"]["argv"].__setitem__(v["invocation"]["argv"].index("--purpose") + 1, "verify"),
            "root": lambda v: v["invocation"]["argv"].__setitem__(1, "REQ-002"),
            "root-qualified": lambda v: v["invocation"]["argv"].__setitem__(1, "platform::" + v["invocation"]["argv"][1]),
            "argv-extra": lambda v: v["invocation"]["argv"].insert(1, "--all-workspaces"),
            "argv-format": lambda v: v["invocation"]["argv"].__setitem__(-1, "markdown"),
            "env": lambda v: v["invocation"].update(env={"PATH": "/dev/null"}),
            "no-git": lambda v: v["setup"].update(git=False),
            "no-base-commit": lambda v: v["setup"].pop("baseCommit"),
            "operations": lambda v: v["setup"]["operations"].append({"op": "delete", "path": ".spec/bitz.yaml"}),
        }
        mutations = []
        for identifier in module.CASES:
            mutations += [(identifier, "expected/context.json", name, change) for name, change in results.items()]
            mutations += [(identifier, "manifest.json", name, change) for name, change in manifests.items()]
            mutations.append((identifier, "side-effects.json", "extra", lambda v: v["before"]["repository"].update(extra={"kind": "directory"})))
            mutations.append((identifier, "side-effects.json", "policy", lambda v: v.update(policy="read-write")))
        applied = 0
        for index, (identifier, relative, name, mutate) in enumerate(mutations):
            with tempfile.TemporaryDirectory() as temporary:
                root = self.copy_multi_fixture(temporary, identifier)
                path = root / "multi" / identifier / relative
                value = json.loads(path.read_text())
                before = json.dumps(value, sort_keys=True)
                try:
                    mutate(value)
                except (KeyError, IndexError, TypeError, AttributeError, ValueError):
                    continue
                if json.dumps(value, sort_keys=True) == before:
                    continue
                applied += 1
                path.write_text(json.dumps(value))
                with self.subTest(index=index, identifier=identifier, file=relative, mutation=name):
                    self.assertEqual(module.validate(root, {identifier})["status"], "Failed")
        # 改変の適用が空振りしていないこと。
        self.assertGreater(applied, 150)

    def test_multi_qualified_summary_audit_rejects_changed_corpus(self):
        """入力の欠落と追加（バイト列の照合）と、欠陥を検出する構成を消す入力の書換え（参照計算と原因の構成の検査）を拒否する。"""
        module = multi_qualified_summary_fixtures
        for identifier in module.CASES:
            names = sorted(f"repo/{name}" for name in module.reviewed_inputs(identifier) if name.endswith(".md") or name.endswith("bitz.yaml"))
            for name in [*names, "extra"]:
                with self.subTest(identifier=identifier, file=name), tempfile.TemporaryDirectory() as temporary:
                    root = self.copy_multi_fixture(temporary, identifier)
                    fixture = root / "multi" / identifier
                    if name == "extra":
                        (fixture / "repo/extra.txt").write_text("x")
                    else:
                        (fixture / name).unlink()
                    self.assertEqual(module.validate(root, {identifier})["status"], "Failed")
        # 原因を消す書換え。入力のバイト列の照合とスナップショットを通した上で（書換え後の内容を`reviewed_inputs`にし、副作用の期待値を作り直す）、
        # 参照計算と原因の構成の検査が拒否することを確かめる（バイト列の照合で先に拒否される空振りを避ける）。
        edits = {
            "MULTI-047-01": [(".spec/requirements/REQ-001.md", "status: draft", "status: approved")],
            # 作業ワークスペースの先行TASKを完了にする（診断が1件に減る）、他のメンバーの先行TASKを完了にする（作業ワークスペースだけが残る）。
            "MULTI-047-02": [(".spec/tasks/TASK-001.md", "status: open", "status: done"),
                             ("services/api/.spec/tasks/TASK-100.md", "status: open", "status: done"),
                             (".spec/tasks/TASK-002.md", "requires: [TASK-001, api::TASK-100]", "requires: [api::TASK-100, TASK-001]")],
            # 具体化文書を状態draftにする、具体化の関係をrelatedに替える（どちらも閉包から外れ、対象規範文が1件に減る）。
            "MULTI-047-03": [("services/api/.spec/technical/TECH-100.md", "status: approved", "status: draft"),
                             ("services/api/.spec/technical/TECH-100.md", "refines: [platform::REQ-050:AC-01]", "related: [platform::REQ-050]")],
            "MULTI-047-04": [(".spec/requirements/REQ-003.md", "status: draft", "status: approved"),
                             ("services/api/.spec/requirements/REQ-100.md", "status: draft", "status: approved")],
            "MULTI-047-05": [("services/api/.spec/tasks/TASK-100.md", "status: open", "status: done"),
                             (".spec/tasks/TASK-001.md", "status: open", "status: done")],
        }
        byte_phrases = ("入力がレビュー済みのcorpusと異なります", "隔離した準備手順が固定したスナップショットと異なります")
        for identifier, changes in edits.items():
            for relative, old, new in changes:
                with self.subTest(identifier=identifier, file=relative, old=old), tempfile.TemporaryDirectory() as temporary:
                    root = self.copy_multi_fixture(temporary, identifier)
                    fixture = root / "multi" / identifier
                    path = fixture / "repo" / relative
                    self.assertIn(old, path.read_text())
                    path.write_text(path.read_text().replace(old, new))
                    edited = dict(module.reviewed_inputs(identifier))
                    edited[relative] = path.read_bytes()
                    manifest = json.loads((fixture / "manifest.json").read_text())
                    repository = fixture_setup(fixture, manifest, Path(temporary) / "regen" / "repo")
                    external = {key: Path(temporary) / "regen" / key for key in ("home", "cache", "temporary")}
                    for directory in external.values():
                        directory.mkdir()
                    state = module.observe(repository, external)
                    (fixture / "side-effects.json").write_text(json.dumps({"schemaVersion": "1.0", "policy": "read-only", "before": state, "after": state}))
                    with patch.object(module, "reviewed_inputs", lambda _identifier, edited=edited: edited):
                        outcome = module.validate(root, {identifier})
                    self.assertEqual(outcome["status"], "Failed")
                    self.assertEqual(len(outcome["errors"]), 1)
                    self.assertFalse(any(phrase in outcome["errors"][0] for phrase in byte_phrases), outcome["errors"][0])
                    self.assertNotIn("KeyError", outcome["errors"][0])

    def test_multi_null_declaration_fixtures(self):
        """`MULTI-048-01`〜`05`: 値が空の`multiWorkspace:`の宣言を、ルートではメンバー0件の設定不適合、メンバーでは宣言の拒否として止めることを固定する（確認事項C58・C63）。"""
        module = multi_null_declaration_fixtures
        result = module.validate()
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["prepared"], [f"MULTI-048-{number:02d}" for number in range(1, 6)])
        self.assertEqual(result["references"], 1)
        self.assertEqual(result["core_execution"], "Not run")
        # 複製した状態でも通る（以降の拒否の試験が、複製の不備で空振りしていないことの陽性対照）。
        for identifier in module.CASES:
            with self.subTest(identifier=identifier), tempfile.TemporaryDirectory() as temporary:
                root = self.copy_multi_fixture(temporary, identifier)
                self.assertEqual(module.validate(root, {identifier})["errors"], [])

    def test_multi_null_declaration_reference_rules(self):
        """参照計算（複合ワークスペース仕様 §2・§2.1、結果・診断・終了コード §2）と、修正前の読み方の再現。宣言はキーの有無で判定する。"""
        module = multi_null_declaration_fixtures

        def decide(identifier, cwd=None, edits=(), function="reference_decision"):
            with tempfile.TemporaryDirectory() as temporary:
                repository = Path(temporary)
                for name, data in module.reviewed_inputs(identifier).items():
                    (repository / name).parent.mkdir(parents=True, exist_ok=True)
                    (repository / name).write_bytes(data)
                for relative, text in edits:
                    (repository / relative).parent.mkdir(parents=True, exist_ok=True)
                    (repository / relative).write_text(text)
                return getattr(module, function)(repository, cwd or module.CASES[identifier]["cwd"])

        # 値が空の宣言は、`members: []`と同じくメンバー0件。ルートのIDは明示した値なので`multiWorkspace.id`は`platform`。
        wanted = {"cause": "members-required", "multiWorkspaceId": "platform", "workspace": {"id": "platform", "path": "."}}
        self.assertEqual(decide("MULTI-048-01"), wanted)
        self.assertEqual(decide("MULTI-048-05"), wanted)
        # 未登録の設定が実在しても、原因はルートの設定不適合に定まる。単独の操作の`workspace.id`は、未登録なので`null`。
        self.assertEqual(decide("MULTI-048-03"), {"cause": "members-required", "multiWorkspaceId": "platform", "workspace": {"id": None, "path": "apps/web"}})
        # メンバーの値が空の宣言は、メンバーの宣言の拒否。
        self.assertEqual(decide("MULTI-048-04")["cause"], "member-nested")
        # メンバーの宣言が値を持っても、同じ原因（キーの有無で判定する）。宣言がなければ原因はない（対照）。
        web_config = module.multi_reference.plain_config("web")
        self.assertEqual(decide("MULTI-048-04", edits=[("apps/web/.spec/bitz.yaml", web_config + "multiWorkspace:\n  members: []\n")])["cause"], "member-nested")
        self.assertIsNone(decide("MULTI-048-04", edits=[("apps/web/.spec/bitz.yaml", web_config)])["cause"])
        # 宣言はキーの有無で判定する。キーがなければ複合ワークスペースのルートではない。
        with self.assertRaises(ValueError):
            decide("MULTI-048-01", edits=[(".spec/bitz.yaml", module.CONFIG_HEAD)])
        # 修正前の読み方は、値が空の宣言を不備なしとみなす。値のある宣言（`members: []`）は修正前も同じ原因を持つ。
        for identifier in ("MULTI-048-01", "MULTI-048-02", "MULTI-048-03", "MULTI-048-04"):
            self.assertIsNone(decide(identifier, function="defective_decision")["cause"], identifier)
        self.assertEqual(decide("MULTI-048-05", function="defective_decision")["cause"], "members-required")
        # 修正前の読み方でも、メンバーが値のある宣言をすれば拒否していた（値が空のときだけ通した）。
        self.assertEqual(decide("MULTI-048-04", function="defective_decision",
                                edits=[("apps/web/.spec/bitz.yaml", web_config + "multiWorkspace:\n  members: []\n")])["cause"], "member-nested")

    def test_multi_null_declaration_audit_rejects_changed_expectations(self):
        """期待結果・起動条件・副作用の改変を拒否する。"""
        module = multi_null_declaration_fixtures

        results = {
            "status": lambda v: v.update(status="passed"),
            "status-blocked": lambda v: v.update(status="blocked"),
            "diagnostics-clear": lambda v: v["diagnostics"].clear(),
            "diagnostics-add": lambda v: v["diagnostics"].append(copy.deepcopy(v["diagnostics"][0])),
            "code-config": lambda v: v["diagnostics"][0].update(code="SPEC-MULTI-CONFIG-001"),
            "code-member": lambda v: v["diagnostics"][0].update(code="SPEC-MULTI-MEMBER-001"),
            "code-unregistered": lambda v: v["diagnostics"][0].update(code="SPEC-MULTI-UNREGISTERED-001"),
            "code-path": lambda v: v["diagnostics"][0].update(code="SPEC-MULTI-PATH-001"),
            "summary": lambda v: v["diagnostics"][0].update(summary="設定キーmultiWorkspace.membersは配列で指定してください"),
            "summary-required": lambda v: v["diagnostics"][0].update(summary=module.MEMBERS_REQUIRED),
            "summary-nested": lambda v: v["diagnostics"][0].update(summary=module.MEMBER_NESTED),
            "severity": lambda v: v["diagnostics"][0].update(severity="warning"),
            "result-status": lambda v: v["diagnostics"][0].update(resultStatus="blocked"),
            "source-workspace": lambda v: v["diagnostics"][0]["source"].update(workspaceId=None),
            "source-workspace-web": lambda v: v["diagnostics"][0]["source"].update(workspaceId="web"),
            "source-key": lambda v: v["diagnostics"][0]["source"].update(key="multiWorkspace"),
            "source-key-drop": lambda v: v["diagnostics"][0]["source"].pop("key"),
            "source-path": lambda v: v["diagnostics"][0]["source"].update(path="apps/web/.spec/bitz.yaml"),
            "suggested-action": lambda v: v["diagnostics"][0].update(suggestedAction="設定キーmultiWorkspace.membersを指定してください"),
            "multi-id": lambda v: v["multiWorkspace"].update(id=None),
            "multi-id-root": lambda v: v["multiWorkspace"].update(id="root"),
            "multi-path": lambda v: v["multiWorkspace"].update(path="apps/web"),
            "workspaces-fill": lambda v: v["workspaces"].append({"id": "platform", "path": ".", "status": "passed", "durationMs": 0, "diagnostics": []}),
            "workspace-id": lambda v: v["workspace"].update(id="web"),
            "workspace-id-platform": lambda v: v["workspace"].update(id="platform"),
            "workspace-path": lambda v: v["workspace"].update(path="."),
            "workspace-add": lambda v: v.update(workspace={"id": "platform", "path": "."}),
            "multi-add": lambda v: v.update(multiWorkspace={"id": "platform", "path": "."}),
            "checks-catalog": lambda v: v["checks"][2].update(status="passed"),
            "checks-catalog-blocked": lambda v: v["checks"][2].update(status="blocked"),
            "checks-drop": lambda v: v["checks"].pop(),
            "scope": lambda v: v.update(scope="full"),
            "selection": lambda v: v["selection"].update(changedPathCount=1),
            "revision-null": lambda v: v.update(revision=None),
        }
        manifests = {
            "status": lambda v: v["expect"].update(status="passed"),
            "exit-code": lambda v: v["expect"].update(exitCode=0),
            "cwd": lambda v: v["invocation"].update(cwd="apps/web" if v["invocation"]["cwd"] == "." else "."),
            "argv-extra": lambda v: v["invocation"]["argv"].insert(1, "--full"),
            "argv-all": lambda v: v["invocation"]["argv"].insert(1, "--all-workspaces"),
            "env": lambda v: v["invocation"].update(env={"PATH": "/dev/null"}),
            "no-git": lambda v: v["setup"].update(git=False),
            "operations": lambda v: v["setup"]["operations"].append({"op": "delete", "path": ".spec/bitz.yaml"}),
        }
        mutations = []
        for identifier in module.CASES:
            result_file = module.RESULT_FILES[module.CASES[identifier]["op"]]
            mutations += [(identifier, result_file, name, change) for name, change in results.items()]
            mutations += [(identifier, "manifest.json", name, change) for name, change in manifests.items()]
            mutations.append((identifier, "side-effects.json", "extra", lambda v: v["before"]["repository"].update(extra={"kind": "directory"})))
            mutations.append((identifier, "side-effects.json", "policy", lambda v: v.update(policy="read-write")))
        applied = 0
        for index, (identifier, relative, name, mutate) in enumerate(mutations):
            with tempfile.TemporaryDirectory() as temporary:
                root = self.copy_multi_fixture(temporary, identifier)
                path = root / "multi" / identifier / relative
                value = json.loads(path.read_text())
                before = json.dumps(value, sort_keys=True)
                try:
                    mutate(value)
                except (KeyError, IndexError, TypeError, AttributeError, ValueError):
                    continue
                if json.dumps(value, sort_keys=True) == before:
                    continue
                applied += 1
                path.write_text(json.dumps(value))
                with self.subTest(index=index, identifier=identifier, file=relative, mutation=name):
                    self.assertEqual(module.validate(root, {identifier})["status"], "Failed")
        # 改変の適用が空振りしていないこと。
        self.assertGreater(applied, 100)

    def test_multi_null_declaration_audit_rejects_changed_corpus(self):
        """入力の欠落と追加（バイト列の照合）と、原因の構成を消す入力の書換え（参照計算と原因の構成の検査）を拒否する。"""
        module = multi_null_declaration_fixtures
        for identifier in module.CASES:
            for name in [*(f"repo/{name}" for name in sorted(module.reviewed_inputs(identifier))), "extra"]:
                with self.subTest(identifier=identifier, file=name), tempfile.TemporaryDirectory() as temporary:
                    root = self.copy_multi_fixture(temporary, identifier)
                    fixture = root / "multi" / identifier
                    if name == "extra":
                        (fixture / "repo/extra.txt").write_text("x")
                    else:
                        (fixture / name).unlink()
                    self.assertEqual(module.validate(root, {identifier})["status"], "Failed")
        # 原因を消す書換え。入力のバイト列の照合とスナップショットを通した上で（書換え後の内容を`reviewed_inputs`にし、副作用の期待値を作り直す）、
        # 参照計算と原因の構成の検査が拒否することを確かめる（バイト列の照合で先に拒否される空振りを避ける）。
        members = "multiWorkspace:\n  members:\n    - id: web\n      path: apps/web\n"
        edits = {
            # 値が空の宣言を、メンバーのある宣言、`{}`の形、宣言なしへ変える。ルートが`workspace.id`を省略する形も拒否する（この群はルートのIDを明示する）。
            "MULTI-048-01": [(".spec/bitz.yaml", "multiWorkspace:\n", members), (".spec/bitz.yaml", "multiWorkspace:\n", "multiWorkspace: {}\n"),
                             (".spec/bitz.yaml", "multiWorkspace:\n", ""), (".spec/bitz.yaml", "workspace:\n  id: platform\n", "")],
            "MULTI-048-02": [(".spec/bitz.yaml", "multiWorkspace:\n", members), (".spec/bitz.yaml", "multiWorkspace:\n", "multiWorkspace: {}\n")],
            # 未登録の設定をカタログへ登録する、未登録の設定のIDを変える、未登録の設定が宣言する。
            "MULTI-048-03": [(".spec/bitz.yaml", "multiWorkspace:\n", members), ("apps/web/.spec/bitz.yaml", "  id: web\n", "  id: frontend\n"),
                             ("apps/web/.spec/bitz.yaml", "  id: web\n", "  id: web\nmultiWorkspace:\n")],
            # メンバーの宣言を外す、`{}`の形にする、カタログのIDを不一致にする。
            "MULTI-048-04": [("apps/web/.spec/bitz.yaml", "multiWorkspace:\n", ""), ("apps/web/.spec/bitz.yaml", "multiWorkspace:\n", "multiWorkspace: {}\n"),
                             (".spec/bitz.yaml", "id: web", "id: frontend")],
            # 対照のメンバーの一覧を空でなくする、キーだけの宣言へ変える。
            "MULTI-048-05": [(".spec/bitz.yaml", "  members: []\n", "  members:\n    - id: web\n      path: apps/web\n"),
                             (".spec/bitz.yaml", "  members: []\n", "")],
        }
        for identifier, changes in edits.items():
            for relative, old, new in changes:
                with self.subTest(identifier=identifier, file=relative, old=old, new=new), tempfile.TemporaryDirectory() as temporary:
                    root = self.copy_multi_fixture(temporary, identifier)
                    fixture = root / "multi" / identifier
                    path = fixture / "repo" / relative
                    self.assertIn(old, path.read_text())
                    path.write_text(path.read_text().replace(old, new, 1))
                    edited = dict(module.reviewed_inputs(identifier))
                    edited[relative] = path.read_bytes()
                    manifest = json.loads((fixture / "manifest.json").read_text())
                    repository = fixture_setup(fixture, manifest, Path(temporary) / "regen" / "repo")
                    external = {key: Path(temporary) / "regen" / key for key in ("home", "cache", "temporary")}
                    for directory in external.values():
                        directory.mkdir(parents=True)
                    state = module.observe_state(manifest, repository, external)
                    (fixture / "side-effects.json").write_text(json.dumps({"schemaVersion": "1.0", "policy": "read-only", "before": state, "after": state}))
                    with patch.object(module, "reviewed_inputs", lambda _identifier, edited=edited: edited):
                        outcome = module.validate(root, {identifier})
                    self.assertEqual(outcome["status"], "Failed")
                    self.assertEqual(len(outcome["errors"]), 1)
                    self.assertFalse(any(phrase in outcome["errors"][0] for phrase in (
                        "入力がレビュー済みのcorpusと異なります", "隔離した準備手順が固定したスナップショットと異なります")), outcome["errors"][0])
                    self.assertNotIn("KeyError", outcome["errors"][0])

    def test_multi_null_base_fixtures(self):
        """`MULTI-048-06`〜`09`: 基準版のルートの値が空の`multiWorkspace:`の宣言を、`members: []`と同じルートだけのカタログとして扱うことを固定する（確認事項C58のM1）。"""
        module = multi_null_base_fixtures
        result = module.validate()
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["prepared"], [f"MULTI-048-{number:02d}" for number in range(6, 10)])
        self.assertEqual(result["references"], 1)
        self.assertEqual(result["core_execution"], "Not run")
        # 複製した状態でも通る（以降の拒否の試験が、複製の不備で空振りしていないことの陽性対照）。
        for identifier in module.CASES:
            with self.subTest(identifier=identifier), tempfile.TemporaryDirectory() as temporary:
                root = self.copy_multi_fixture(temporary, identifier)
                self.assertEqual(module.validate(root, {identifier})["errors"], [])

    def test_multi_null_base_reference_rules(self):
        """基準版の参照計算（複合ワークスペース仕様 §2.1・§4.1・§8）と、修正前の読み方の再現。値の空の宣言は`members: []`と同じ。"""
        module = multi_null_base_fixtures

        def decide(identifier, **options):
            with tempfile.TemporaryDirectory() as temporary:
                fixture = audit.FIXTURES / "multi" / identifier
                manifest = json.loads((fixture / "manifest.json").read_text())
                repository = fixture_setup(fixture, manifest, Path(temporary) / "repo")
                return module.reference_decision(repository, **options)

        unregistered = {"cause": "unregistered", "unregistered": ["apps/web/.spec/bitz.yaml"], "removed": {}}
        transition = {"cause": "transition", "unregistered": [], "removed": {"root": [".spec/requirements/REQ-001.md"]}}
        for identifier, wanted in (("MULTI-048-06", unregistered), ("MULTI-048-08", unregistered),
                                   ("MULTI-048-07", transition), ("MULTI-048-09", transition)):
            with self.subTest(identifier=identifier):
                found = decide(identifier)
                self.assertEqual({key: found[key] for key in wanted}, wanted)
                self.assertEqual(found["current"], {".": "platform", "apps/web": "web"})
        # 値の空の宣言と`members: []`は、同じ結果になる。
        self.assertEqual(decide("MULTI-048-06"), decide("MULTI-048-08"))
        self.assertEqual(decide("MULTI-048-07"), decide("MULTI-048-09"))
        # 修正前の読み方は、値の空の宣言の基準版を宣言なしとみなす。値のある`members: []`は修正前も同じ原因を持つ。
        for identifier in ("MULTI-048-06", "MULTI-048-07"):
            self.assertIsNone(decide(identifier, null_is_undeclared=True)["cause"], identifier)
        self.assertEqual(decide("MULTI-048-08", null_is_undeclared=True)["cause"], "unregistered")
        self.assertEqual(decide("MULTI-048-09", null_is_undeclared=True)["cause"], "transition")
        # 基準版が`multiWorkspace`を宣言しなければ、参照計算の対象外（`MULTI-043`の基準版の写像）。
        with self.assertRaises(ValueError):
            with tempfile.TemporaryDirectory() as temporary:
                fixture = audit.FIXTURES / "multi" / "MULTI-048-06"
                manifest = json.loads((fixture / "manifest.json").read_text())
                repository = fixture_setup(fixture, manifest, Path(temporary) / "repo")
                (repository / ".spec/bitz.yaml").write_text(module.CONFIG_HEAD)
                module.git(repository, "add", "-A", "--", ".")
                module.git(repository, "commit", "--amend", "-m", "base")
                module.reference_decision(repository)

    def test_multi_null_base_audit_rejects_changed_expectations(self):
        """期待結果・起動条件・副作用の改変を拒否する。"""
        module = multi_null_base_fixtures

        results = {
            "status": lambda v: v.update(status="passed"),
            "status-blocked": lambda v: v.update(status="blocked"),
            "status-failed": lambda v: v.update(status="failed"),
            "diagnostics-clear": lambda v: v["diagnostics"].clear(),
            "diagnostics-add": lambda v: v["diagnostics"].append(copy.deepcopy(v["diagnostics"][0])),
            "code-unregistered": lambda v: v["diagnostics"][0].update(code="SPEC-MULTI-UNREGISTERED-001"),
            "code-transition": lambda v: v["diagnostics"][0].update(code="SPEC-STATE-TRANSITION-001"),
            "code-config": lambda v: v["diagnostics"][0].update(code="SPEC-MULTI-CONFIG-001"),
            "summary": lambda v: v["diagnostics"][0].update(summary="設定キーmultiWorkspace.membersは1件以上指定してください"),
            "severity": lambda v: v["diagnostics"][0].update(severity="warning"),
            "result-status": lambda v: v["diagnostics"][0].update(resultStatus="blocked" if v["diagnostics"][0]["resultStatus"] == "failed" else "failed"),
            "source-workspace": lambda v: v["diagnostics"][0]["source"].update(workspaceId="platform"),
            "source-workspace-null": lambda v: v["diagnostics"][0]["source"].update(workspaceId=None),
            "source-workspace-root": lambda v: v["diagnostics"][0]["source"].update(workspaceId="root"),
            "source-path": lambda v: v["diagnostics"][0]["source"].update(path=".spec/bitz.yaml"),
            "source-key": lambda v: v["diagnostics"][0]["source"].update(key="multiWorkspace.members"),
            "suggested-action": lambda v: v["diagnostics"][0].update(suggestedAction="修正してください"),
            "multi-id": lambda v: v["multiWorkspace"].update(id="root"),
            "multi-id-null": lambda v: v["multiWorkspace"].update(id=None),
            "multi-path": lambda v: v["multiWorkspace"].update(path="apps/web"),
            "workspaces-clear": lambda v: v["workspaces"].clear(),
            "workspaces-fill": lambda v: v["workspaces"].append({"id": "platform", "path": ".", "status": "passed", "checkedDocumentCount": 1,
                                                                 "checkedStatementCount": 2, "durationMs": 0, "diagnostics": []}),
            "workspaces-reverse": lambda v: v["workspaces"].reverse(),
            "workspaces-count": lambda v: v["workspaces"][0].update(checkedDocumentCount=2),
            "workspaces-statements": lambda v: v["workspaces"][0].update(checkedStatementCount=0),
            "workspaces-status": lambda v: v["workspaces"][1].update(status="failed"),
            "workspaces-diagnostics": lambda v: v["workspaces"][1]["diagnostics"].append({}),
            "workspace-add": lambda v: v.update(workspace={"id": "platform", "path": "."}),
            "revision-clean": lambda v: v["revision"].update(dirty=False),
            "revision-null": lambda v: v.update(revision=None),
            "scope": lambda v: v.update(scope="full"),
        }
        manifests = {
            "status": lambda v: v["expect"].update(status="passed"),
            "exit-code": lambda v: v["expect"].update(exitCode=0),
            "cwd": lambda v: v["invocation"].update(cwd="apps/web"),
            "argv-base": lambda v: v["invocation"]["argv"].__setitem__(v["invocation"]["argv"].index("--base") + 1, "main"),
            "argv-no-base": lambda v: v["invocation"]["argv"].__delitem__(slice(v["invocation"]["argv"].index("--base"), v["invocation"]["argv"].index("--base") + 2)),
            "argv-no-all": lambda v: v["invocation"]["argv"].remove("--all-workspaces"),
            "env": lambda v: v["invocation"].update(env={"PATH": "/dev/null"}),
            "no-git": lambda v: v["setup"].update(git=False),
            "no-base-commit": lambda v: v["setup"].pop("baseCommit"),
            "operations-drop": lambda v: v["setup"]["operations"].pop(),
            "operations-add": lambda v: v["setup"]["operations"].append({"op": "delete", "path": ".spec/requirements/REQ-001.md"}),
        }
        mutations = []
        for identifier in module.CASES:
            mutations += [(identifier, "expected/check.json", name, change) for name, change in results.items()]
            mutations += [(identifier, "manifest.json", name, change) for name, change in manifests.items()]
            mutations.append((identifier, "side-effects.json", "extra", lambda v: v["before"]["repository"].update(extra={"kind": "directory"})))
            mutations.append((identifier, "side-effects.json", "policy", lambda v: v.update(policy="read-write")))
        applied = 0
        for index, (identifier, relative, name, mutate) in enumerate(mutations):
            with tempfile.TemporaryDirectory() as temporary:
                root = self.copy_multi_fixture(temporary, identifier)
                path = root / "multi" / identifier / relative
                value = json.loads(path.read_text())
                before = json.dumps(value, sort_keys=True)
                try:
                    mutate(value)
                except (KeyError, IndexError, TypeError, AttributeError, ValueError):
                    continue
                if json.dumps(value, sort_keys=True) == before:
                    continue
                applied += 1
                path.write_text(json.dumps(value))
                with self.subTest(index=index, identifier=identifier, file=relative, mutation=name):
                    self.assertEqual(module.validate(root, {identifier})["status"], "Failed")
        # 改変の適用が空振りしていないこと。
        self.assertGreater(applied, 100)

    def test_multi_null_base_audit_rejects_changed_corpus(self):
        """入力の欠落と追加（バイト列の照合）と、原因の構成を消す入力の書換え（参照計算と原因の構成の検査）を拒否する。"""
        module = multi_null_base_fixtures
        for identifier in module.CASES:
            reviewed = module.reviewed_inputs(identifier)
            names = [f"repo/{name}" for name in sorted(reviewed["files"])] + [f"changes/{name}" for name in sorted(reviewed["changes"])]
            for name in [*names, "repo/extra.txt", "changes/extra.txt"]:
                with self.subTest(identifier=identifier, file=name), tempfile.TemporaryDirectory() as temporary:
                    root = self.copy_multi_fixture(temporary, identifier)
                    fixture = root / "multi" / identifier
                    if name.endswith("extra.txt"):
                        (fixture / name).write_text("x")
                    else:
                        (fixture / name).unlink()
                    self.assertEqual(module.validate(root, {identifier})["status"], "Failed")
        # 原因を消す書換え。入力のバイト列の照合とスナップショットを通した上で（書換え後の内容を`reviewed_inputs`にし、副作用の期待値を作り直す）、
        # 参照計算と原因の構成の検査が拒否することを確かめる（バイト列の照合で先に拒否される空振りを避ける）。
        members = "multiWorkspace:\n  members:\n    - id: web\n      path: apps/web\n"
        edits = {
            # 基準版がメンバー`web`を登録する（未登録という原因を消す）、`{}`の形にする、基準版の`apps/web`の設定のIDを変える、現在版の`web`のIDを変える。
            "MULTI-048-06": [("repo", ".spec/bitz.yaml", "multiWorkspace:\n", members), ("repo", ".spec/bitz.yaml", "multiWorkspace:\n", "multiWorkspace: {}\n"),
                             ("repo", "apps/web/.spec/bitz.yaml", "  id: web\n", "  id: frontend\n"), ("changes", "bitz.yaml", "id: web", "id: frontend")],
            # 基準版がIDを明示する（写像しなくても同じIDになり、削除がなくなる）、基準版のREQを`draft`にする（管理済みの文書がなくなる）、現在版のIDを`root`にする。
            "MULTI-048-07": [("repo", ".spec/bitz.yaml", "multiWorkspace:\n", "workspace:\n  id: platform\nmultiWorkspace:\n"),
                             ("repo", ".spec/requirements/REQ-001.md", "status: approved", "status: draft"),
                             ("changes", "bitz.yaml", "id: platform", "id: root")],
            # 対照の`members: []`を、キーだけの宣言、メンバーのある宣言へ変える。
            "MULTI-048-08": [("repo", ".spec/bitz.yaml", "  members: []\n", ""), ("repo", ".spec/bitz.yaml", "  members: []\n", "  members:\n    - id: web\n      path: apps/web\n")],
            "MULTI-048-09": [("repo", ".spec/bitz.yaml", "  members: []\n", ""), ("repo", ".spec/bitz.yaml", "  members: []\n", "  members:\n    - id: web\n      path: apps/web\n")],
        }
        for identifier, changes in edits.items():
            for directory, relative, old, new in changes:
                with self.subTest(identifier=identifier, file=f"{directory}/{relative}", old=old, new=new), tempfile.TemporaryDirectory() as temporary:
                    root = self.copy_multi_fixture(temporary, identifier)
                    fixture = root / "multi" / identifier
                    path = fixture / directory / relative
                    self.assertIn(old, path.read_text())
                    path.write_text(path.read_text().replace(old, new, 1))
                    edited = copy.deepcopy(module.reviewed_inputs(identifier))
                    edited["files" if directory == "repo" else "changes"][relative] = path.read_bytes()
                    manifest = json.loads((fixture / "manifest.json").read_text())
                    repository = fixture_setup(fixture, manifest, Path(temporary) / "regen" / "repo")
                    external = {key: Path(temporary) / "regen" / key for key in ("home", "cache", "temporary")}
                    for item in external.values():
                        item.mkdir(parents=True)
                    state = module.observe_state(manifest, repository, external)
                    (fixture / "side-effects.json").write_text(json.dumps({"schemaVersion": "1.0", "policy": "read-only", "before": state, "after": state}))
                    with patch.object(module, "reviewed_inputs", lambda _identifier, edited=edited: edited):
                        outcome = module.validate(root, {identifier})
                    self.assertEqual(outcome["status"], "Failed")
                    self.assertEqual(len(outcome["errors"]), 1)
                    self.assertFalse(any(phrase in outcome["errors"][0] for phrase in (
                        "入力がレビュー済みのcorpusと異なります", "隔離した準備手順が固定したスナップショットと異なります")), outcome["errors"][0])
                    self.assertNotIn("KeyError", outcome["errors"][0])

    def test_multi_binding_missing_fixtures(self):
        """`MULTI-039-01`〜`04`: テスト割当ての欠落の診断を所有ワークスペースごとに返すことを固定する（確認事項C23）。"""
        module = multi_binding_missing_fixtures
        result = module.validate()
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["prepared"], [f"MULTI-039-{number:02d}" for number in range(1, 5)])
        self.assertEqual(result["references"], 2)
        self.assertEqual(result["core_execution"], "Not run")
        # 複製した状態でも通る（以降の拒否の試験が、複製の不備で空振りしていないことの陽性対照）。
        for identifier in module.CASES:
            with self.subTest(identifier=identifier), tempfile.TemporaryDirectory() as temporary:
                root = self.copy_multi_fixture(temporary, identifier)
                self.assertEqual(module.validate(root, {identifier})["errors"], [])

    def test_multi_binding_missing_reference_rules(self):
        """テスト割当ての欠落の元の原因の参照計算（診断レジストリ §2、関係・トレースモデル §6.4）。"""
        module = multi_binding_missing_fixtures
        statements = "".join(f"- [r:AC-0{number}] [ACTOR:A] [ALWAYS] [MUST] [CONSTRAINT] x。\n" for number in (1, 2))

        def document(workspace, identifier, kind, refines=(), tests=(), verify=None, body=""):
            frontmatter = {"id": identifier, "title": "t", "status": "approved", "relations": {"refines": list(refines)}, "tests": list(tests)}
            if verify:
                frontmatter["verify"] = verify
            return {"workspaceId": workspace, "kind": kind, "body": body, "path": f".spec/{kind}/{identifier}.md", "frontmatter": frontmatter}

        def entry(covers, command):
            return {"path": "tests/t.py", "covers": covers, "command": command}

        workspaces = {name: {"path": name, "config": {"verify": {"commands": {"ok": {"argv": ["/bin/true"]}}}}} for name in ("w", "x")}
        documents = {
            "w::r": document("w", "r", "requirement", body=statements),
            "w::t": document("w", "t", "technical", refines=["r:AC-01"], tests=[entry(["r:AC-01", "r:AC-02"], "bad")]),
            "x::t": document("x", "t", "technical", refines=["w::r"], tests=[entry(["w::r:AC-01"], "bad"), entry(["w::r:AC-02"], "ok")]),
        }
        # 同じ相対パスでも所有ワークスペースが異なれば別の原因（2件）。同じエントリを規範文2件が指しても1件（`w`の`tests[0]`）。
        found = module.reference_diagnostics(documents, workspaces, "w::r")
        self.assertEqual([(item["source"]["workspaceId"], item["source"]["key"]) for item in found],
                         [("w", "tests[0].command"), ("x", "tests[0].command")])
        self.assertEqual({item["source"]["path"] for item in found}, {".spec/technical/t.md"})
        self.assertEqual({item["summary"] for item in found}, {"コマンド名badが設定に定義されていません"})
        # コマンド名が定義されたエントリ（`x`の`tests[1]`）は原因にならない。文書の`verify`はコマンド名が省略されたときの既定。
        documents["x::t"]["frontmatter"]["tests"][0]["command"] = "ok"
        self.assertEqual([item["source"]["workspaceId"] for item in module.reference_diagnostics(documents, workspaces, "w::r")], ["w"])
        # 規範文のないTECHが起点なら、起点自身のテスト対応だけが対象（閉包の別の文書の欠落は返さない）。
        self.assertEqual(module.verify_closure(documents, "w::t")[0], ["w::t", "w::r"])
        self.assertEqual([item["source"]["workspaceId"] for item in module.reference_diagnostics(documents, workspaces, "w::t")], ["w"])
        # 起点を`refines`する文書は閉包へ含め（推移的）、起点の`refines`の参照先は含めるが、参照先を`refines`する別の文書は辿らない。
        order, refiners = module.verify_closure(documents, "w::r")
        self.assertEqual((order, refiners), (["w::r", "w::t", "x::t"], ["w::t", "x::t"]))
        self.assertEqual(module.verify_closure(documents, "x::t")[0], ["x::t", "w::r"])
        # コマンド名を持たないテスト対応は、このcorpusが扱わない形として拒否する。
        documents["w::t"]["frontmatter"]["tests"][0]["command"] = None
        with self.assertRaises(ValueError):
            module.reference_diagnostics(documents, workspaces, "w::r")

    def test_multi_binding_missing_audit_rejects_changed_expectations(self):
        """期待結果・起動条件・副作用の改変を拒否する。"""
        module = multi_binding_missing_fixtures

        def first(value):
            """検証対象`web::REQ-001`（`verify <ID>`は`targetResults[0]`、全体は`web`のワークスペースの先頭）。"""
            return value["targetResults"][0] if "targetResults" in value else value["workspaces"][2]["targetResults"][0]

        results = {
            "status": lambda v: v.update(status="failed"),
            "diagnostics-add": lambda v: v["diagnostics"].append({"code": "SPEC-VERIFY-BLOCKED-001"}),
            "target-status": lambda v: first(v).update(status="failed"),
            "target-digest": lambda v: first(v).update(contextDigest="sha256:" + "0" * 64),
            "target-digest-null": lambda v: first(v).update(contextDigest=None),
            "target-statements": lambda v: first(v)["statements"].pop(),
            "target-bindings": lambda v: first(v).update(bindingRefs=["web::frontend"]),
            "diag-drop": lambda v: first(v)["diagnostics"].pop(),
            "diag-drop-first": lambda v: first(v)["diagnostics"].pop(0),
            "diag-duplicate": lambda v: first(v)["diagnostics"].append(copy.deepcopy(first(v)["diagnostics"][0])),
            "diag-reverse": lambda v: first(v)["diagnostics"].reverse(),
            "diag-owner": lambda v: first(v)["diagnostics"][0]["source"].update(workspaceId="web"),
            "diag-owner-second": lambda v: first(v)["diagnostics"][1]["source"].update(workspaceId="api"),
            "diag-path": lambda v: first(v)["diagnostics"][0]["source"].update(path=".spec/technical/TECH-002.md"),
            "diag-key": lambda v: first(v)["diagnostics"][0]["source"].update(key="tests[1].command"),
            "diag-key-drop": lambda v: first(v)["diagnostics"][0]["source"].pop("key"),
            "diag-summary": lambda v: first(v)["diagnostics"][0].update(summary=first(v)["diagnostics"][0]["summary"] + "。"),
            "diag-summary-name": lambda v: first(v)["diagnostics"][0].update(summary="コマンド名missingが設定に定義されていません"),
            "diag-code": lambda v: first(v)["diagnostics"][0].update(code="SPEC-VERIFY-BLOCKED-002"),
            "diag-effect": lambda v: first(v)["diagnostics"][0].update(resultStatus="failed"),
            "diag-severity": lambda v: first(v)["diagnostics"][0].update(severity="warning"),
            "diag-evidence": lambda v: first(v)["diagnostics"][0].update(evidence="missing"),
            "commands": lambda v: (v["commands"] if "commands" in v else v["workspaces"][2]["commands"]).append({}),
            "workspace": lambda v: v["workspace"].update(path=".") if "workspace" in v else v["multiWorkspace"].update(path="apps/web"),
            "revision": lambda v: v.update(revision=None),
            "ws-order": lambda v: v["workspaces"].reverse(),
            "ws-status": lambda v: v["workspaces"][2].update(status="passed"),
            "ws-target-drop": lambda v: v["workspaces"][2]["targetResults"].pop(),
            "ws-target-add": lambda v: v["workspaces"][1]["targetResults"].append(copy.deepcopy(first(v))),
            "ws-api-diag": lambda v: v["workspaces"][1]["targetResults"][0]["diagnostics"].clear(),
            "ws-web-tech-diag": lambda v: v["workspaces"][2]["targetResults"][1]["diagnostics"].append(
                copy.deepcopy(v["workspaces"][2]["targetResults"][0]["diagnostics"][0])),
            "ws-platform-warning": lambda v: v["workspaces"][0]["diagnostics"].clear(),
        }
        manifests = {
            "status": lambda v: v["expect"].update(status="failed"),
            "exit-code": lambda v: v["expect"].update(exitCode=1),
            "cwd": lambda v: v["invocation"].update(cwd="apps/web"),
            "argv-target": lambda v: v["invocation"]["argv"].__setitem__(1, "web::TECH-001"),
            "argv-extra": lambda v: v["invocation"]["argv"].insert(1, "--all-workspaces"),
            "env": lambda v: v["invocation"].update(env={"PATH": "/dev/null"}),
            "no-git": lambda v: v["setup"].update(git=False),
            "operations": lambda v: v["setup"]["operations"].append({"op": "delete", "path": ".spec/bitz.yaml"}),
        }
        mutations = []
        for identifier in module.CASES:
            mutations += [(identifier, "expected/verify.json", name, change) for name, change in results.items()]
            mutations += [(identifier, "manifest.json", name, change) for name, change in manifests.items()]
            mutations.append((identifier, "side-effects.json", "extra", lambda v: v["before"]["repository"].update(extra={"kind": "directory"})))
            mutations.append((identifier, "side-effects.json", "policy", lambda v: v.update(policy="read-write")))
        applied = 0
        for index, (identifier, relative, name, mutate) in enumerate(mutations):
            with tempfile.TemporaryDirectory() as temporary:
                root = self.copy_multi_fixture(temporary, identifier)
                path = root / "multi" / identifier / relative
                value = json.loads(path.read_text())
                before = json.dumps(value, sort_keys=True)
                try:
                    mutate(value)
                except (KeyError, IndexError, TypeError, AttributeError, ValueError):
                    continue
                if json.dumps(value, sort_keys=True) == before:
                    continue
                applied += 1
                path.write_text(json.dumps(value))
                with self.subTest(index=index, identifier=identifier, file=relative, mutation=name):
                    self.assertEqual(module.validate(root, {identifier})["status"], "Failed")
        # 改変の適用が空振りしていないこと。
        self.assertGreater(applied, 130)

    def test_multi_binding_missing_audit_rejects_changed_corpus(self):
        """入力の欠落と追加（バイト列の照合）と、原因を消す入力の書換え（参照計算と原因の構成の検査）を拒否する。"""
        module = multi_binding_missing_fixtures
        for identifier in module.CASES:
            names = sorted(f"repo/{name}" for name in module.reviewed_inputs(identifier) if name.endswith(".md") or name.endswith("bitz.yaml"))
            for name in [*names, "extra"]:
                with self.subTest(identifier=identifier, file=name), tempfile.TemporaryDirectory() as temporary:
                    root = self.copy_multi_fixture(temporary, identifier)
                    fixture = root / "multi" / identifier
                    if name == "extra":
                        (fixture / "repo/extra.txt").write_text("x")
                    else:
                        (fixture / name).unlink()
                    self.assertEqual(module.validate(root, {identifier})["status"], "Failed")
        # 原因を消す書換え。入力のバイト列の照合とスナップショットを通した上で（書換え後の内容を`reviewed_inputs`にし、副作用の期待値を作り直す）、
        # 参照計算と原因の構成の検査が拒否することを確かめる（バイト列の照合で先に拒否される空振りを避ける）。
        edits = {
            # `api`のコマンド名を設定に定義された名前にする（`api`の欠落が消え、診断が1件になる）。
            "MULTI-039-01": [("services/api/.spec/technical/TECH-001.md", "command: absent", "command: backend"),
                             # `api`のTECH-001が起点を指さなくなる（閉包の外になる）。
                             ("services/api/.spec/technical/TECH-001.md", "refines: [web::REQ-001:AC-01]", "refines: [web::REQ-009:AC-01]"),
                             # `web`のコマンド名を設定に定義された名前にする。
                             ("apps/web/.spec/technical/TECH-001.md", "command: missing", "command: frontend")],
            "MULTI-039-02": [("apps/web/.spec/technical/TECH-001.md", "command: missing", "command: frontend")],
            # エントリが指す規範文を1件にする（同じエントリを複数の規範文が指す条件を消す）。
            "MULTI-039-03": [("apps/web/.spec/technical/TECH-001.md", "covers: [REQ-001:AC-01, REQ-001:AC-02]", "covers: [REQ-001:AC-01]"),
                             ("services/api/.spec/technical/TECH-001.md", "command: absent", "command: backend")],
            "MULTI-039-04": [(".spec/technical/TECH-001.md", "command: missing", "command: frontend"),
                             (".spec/technical/TECH-001.md", "covers: [REQ-001:AC-01, REQ-001:AC-02]", "covers: [REQ-001:AC-01]")],
        }
        byte_phrases = ("入力がレビュー済みのcorpusと異なります", "隔離した準備手順が固定したスナップショットと異なります")
        for identifier, changes in edits.items():
            for relative, old, new in changes:
                with self.subTest(identifier=identifier, file=relative, edit=old), tempfile.TemporaryDirectory() as temporary:
                    root = self.copy_multi_fixture(temporary, identifier)
                    fixture = root / "multi" / identifier
                    path = fixture / "repo" / relative
                    self.assertIn(old, path.read_text())
                    path.write_text(path.read_text().replace(old, new))
                    edited = dict(module.reviewed_inputs(identifier))
                    edited[relative] = path.read_bytes()
                    manifest = json.loads((fixture / "manifest.json").read_text())
                    repository = fixture_setup(fixture, manifest, Path(temporary) / "regen" / "repo")
                    external = {key: Path(temporary) / "regen" / key for key in ("home", "cache", "temporary")}
                    for directory in external.values():
                        directory.mkdir()
                    state = module.observe(repository, external)
                    (fixture / "side-effects.json").write_text(json.dumps({"schemaVersion": "1.0", "policy": "read-only", "before": state, "after": state}))
                    with patch.object(module, "reviewed_inputs", lambda _identifier, edited=edited: edited):
                        outcome = module.validate(root, {identifier})
                    self.assertEqual(outcome["status"], "Failed")
                    self.assertEqual(len(outcome["errors"]), 1)
                    self.assertFalse(any(phrase in outcome["errors"][0] for phrase in byte_phrases), outcome["errors"][0])
                    self.assertNotIn("KeyError", outcome["errors"][0])

    def test_multi_doctor_git_fixtures(self):
        """`MULTI-040-01`〜`10`: `doctor`のGit不在とルートの設定の停止が独立した原因として両方返ることを固定する（確認事項C33、ADR-065）。"""
        module = multi_doctor_git_fixtures
        result = module.validate()
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["prepared"], [f"MULTI-040-{number:02d}" for number in range(1, 11)])
        self.assertEqual(result["references"], 1)
        self.assertEqual(result["core_execution"], "Not run")
        # 複製した状態でも通る（以降の拒否の試験が、複製の不備で空振りしていないことの陽性対照）。
        for identifier in module.CASES:
            with self.subTest(identifier=identifier), tempfile.TemporaryDirectory() as temporary:
                root = self.copy_multi_fixture(temporary, identifier)
                self.assertEqual(module.validate(root, {identifier})["errors"], [])

    def test_multi_doctor_git_reference_rules(self):
        """参照計算（`doctor` §3、ADR-065、結果・診断・終了コード §7）。"""
        module = multi_doctor_git_fixtures
        base = module.stopped_root_config("ears").replace('earsAi: "2.0"', 'earsAi: "1.0"')
        # 停止の分類: 構文の不正、スキーマ、EARS-AIの順。止まらなければ`None`。
        self.assertIsNone(module.classify_root_config(base))
        self.assertEqual(module.classify_root_config(base.replace('earsAi: "1.0"', 'earsAi: "2.0"')), ("ears", "earsAi"))
        self.assertEqual(module.classify_root_config(base.replace('schemaVersion: "1.0"', 'schemaVersion: "2.0"')), ("schema", "schemaVersion"))
        both = base.replace('earsAi: "1.0"', 'earsAi: "2.0"').replace('schemaVersion: "1.0"', 'schemaVersion: "2.0"')
        self.assertEqual(module.classify_root_config(both), ("schema", "schemaVersion"))
        self.assertEqual(module.classify_root_config(both.replace("language: ja", "language: &x ja")), ("anchor", "language"))
        ears, schema, anchor = (module.stopped_root_config(name) for name in ("ears", "schema", "anchor"))
        # `doctor`はGitの不在を加える。Gitがあるとき、ほかの操作のときは設定の診断だけ。
        self.assertEqual(module.reference_expected(ears, False, "doctor", "all")["diagnostics"], ["git", "config"])
        self.assertEqual(module.reference_expected(ears, False, "doctor", "single")["diagnostics"], ["git", "config"])
        self.assertEqual(module.reference_expected(ears, True, "doctor", "all")["diagnostics"], ["config"])
        for operation in ("check", "verify", "context"):
            self.assertEqual(module.reference_expected(ears, False, operation, "single")["diagnostics"], ["config"])
        # 検査項目: `catalog`は版の非対応のときだけ。Gitがなければ`git`は`blocked`。
        expected = module.reference_expected(ears, False, "doctor", "all")
        self.assertEqual((expected["checks"], expected["status"], expected["exit"], expected["subjectId"]),
                         ([("core", "passed"), ("git", "blocked"), ("catalog", "blocked")], "blocked", 2, "platform"))
        expected = module.reference_expected(schema, True, "doctor", "single")
        self.assertEqual(expected["checks"], [("core", "passed"), ("git", "passed"), ("catalog", "blocked")])
        # 構文の不正は`error`／3で、有効なルートのIDを構成できず、`catalog`を置かない。
        expected = module.reference_expected(anchor, False, "doctor", "all")
        self.assertEqual((expected["checks"], expected["status"], expected["exit"], expected["subjectId"]),
                         ([("core", "passed"), ("git", "blocked")], "error", 3, None))
        # 並び: `null`のIDは文字列のIDより前、IDを持たない環境の発生元は文字列のIDより前（`workspaceId: null`のファイルの後。結果・診断・終了コード §7）。
        self.assertEqual(module.reference_expected(anchor, False, "doctor", "all")["diagnostics"], ["config", "git"])
        with patch.object(module, "ENVIRONMENT_AFTER_NULL_FILE", False):
            self.assertEqual(module.reference_expected(anchor, False, "doctor", "all")["diagnostics"], ["git", "config"])
            self.assertEqual(module.reference_expected(ears, False, "doctor", "all")["diagnostics"], ["git", "config"])
        with self.assertRaises(ValueError):
            module.reference_expected(base, False, "doctor", "all")

    def test_multi_doctor_git_audit_rejects_changed_expectations(self):
        """期待結果・起動条件・副作用の改変を拒否する。"""
        module = multi_doctor_git_fixtures

        def git_entry():
            return {"code": "SPEC-MULTI-GIT-001", "severity": "error", "resultStatus": "blocked", "summary": "Gitのリポジトリの境界を確定できません",
                    "source": {"kind": "environment", "component": "git"}}

        results = {
            "status": lambda v: v.update(status="failed"),
            "status-passed": lambda v: v.update(status="passed"),
            "diag-drop-first": lambda v: v["diagnostics"].pop(0),
            "diag-drop-last": lambda v: v["diagnostics"].pop(),
            "diag-reverse": lambda v: v["diagnostics"].reverse(),
            "diag-git-add": lambda v: v["diagnostics"].append(git_entry()),
            "diag-git-insert": lambda v: v["diagnostics"].insert(0, git_entry()),
            "diag-duplicate": lambda v: v["diagnostics"].append(copy.deepcopy(v["diagnostics"][0])),
            "diag-code": lambda v: v["diagnostics"][-1].update(code="SPEC-CONFIG-SCHEMA-001"),
            "diag-code-doctor": lambda v: v["diagnostics"][-1].update(code="SPEC-EARS-VERSION-001"),
            "diag-effect": lambda v: v["diagnostics"][0].update(resultStatus="failed"),
            "diag-severity": lambda v: v["diagnostics"][0].update(severity="warning"),
            "diag-summary": lambda v: v["diagnostics"][0].update(summary=v["diagnostics"][0]["summary"] + "。"),
            "diag-source": lambda v: v["diagnostics"][0]["source"].update(component="gitx"),
            "diag-source-id": lambda v: v["diagnostics"][-1]["source"].update(workspaceId="web"),
            "diag-source-key": lambda v: v["diagnostics"][-1]["source"].update(key="language"),
            "diag-action-drop": lambda v: v["diagnostics"][-1].pop("suggestedAction"),
            "diag-action-add": lambda v: v["diagnostics"][0].update(suggestedAction="直してください"),
            "checks-drop-git": lambda v: v["checks"].pop(1),
            "checks-git-passed": lambda v: v["checks"][1].update(status="passed"),
            "checks-git-blocked": lambda v: v["checks"][1].update(status="blocked"),
            "checks-catalog-add": lambda v: v["checks"].append({"name": "catalog", "status": "blocked"}),
            "checks-catalog-drop": lambda v: v["checks"].pop(),
            "checks-catalog-passed": lambda v: v["checks"][-1].update(status="passed"),
            "checks-config": lambda v: v["checks"].append({"name": "config", "status": "passed"}),
            "subject-id": lambda v: (v["multiWorkspace"] if "multiWorkspace" in v else v["workspace"]).update(id="web"),
            "subject-path": lambda v: (v["multiWorkspace"] if "multiWorkspace" in v else v["workspace"]).update(path="docs"),
            "workspaces-add": lambda v: v["workspaces"].append({"id": "web"}),
            "workspace-add": lambda v: v.update(workspace={"id": "platform", "path": "."}),
            "multi-add": lambda v: v.update(multiWorkspace={"id": "platform", "path": "."}),
            "revision": lambda v: v.update(revision={"base": "0" * 40, "commit": "0" * 40, "dirty": False}),
            "revision-set": lambda v: v.__setitem__("revision", None) if "revision" not in v else v.pop("revision"),
            "scope": lambda v: v.update(scope="changed"),
            "counts": lambda v: v.update(checkedDocumentCount=1),
            "targets": lambda v: v.update(targetResults=[{}]),
            "digest": lambda v: v.update(contextDigest="sha256:" + "0" * 64),
            "roots": lambda v: v.update(roots=["REQ-002"]),
        }
        manifests = {
            "status": lambda v: v["expect"].update(status="failed"),
            "exit-code": lambda v: v["expect"].update(exitCode=1),
            "cwd": lambda v: v["invocation"].update(cwd="apps/web"),
            "argv-all": lambda v: v["invocation"]["argv"].insert(1, "--all-workspaces"),
            "argv-drop": lambda v: v["invocation"]["argv"].pop(1),
            "env": lambda v: v["invocation"].update(env={} if v["invocation"]["env"] else {"PATH": "/dev/null"}),
            "git": lambda v: v["setup"].update(git=not v["setup"]["git"]),
            "operations": lambda v: v["setup"]["operations"].append({"op": "delete", "path": ".spec/bitz.yaml"}),
        }
        mutations = []
        for identifier in module.CASES:
            relative = module.RESULT_FILES[module.operation(identifier)]
            mutations += [(identifier, relative, name, change) for name, change in results.items()]
            mutations += [(identifier, "manifest.json", name, change) for name, change in manifests.items()]
            mutations.append((identifier, "side-effects.json", "extra", lambda v: v["before"]["repository"].update(extra={"kind": "directory"})))
            mutations.append((identifier, "side-effects.json", "policy", lambda v: v.update(policy="read-write")))
        applied = 0
        for index, (identifier, relative, name, mutate) in enumerate(mutations):
            with tempfile.TemporaryDirectory() as temporary:
                root = self.copy_multi_fixture(temporary, identifier)
                path = root / "multi" / identifier / relative
                value = json.loads(path.read_text())
                before = json.dumps(value, sort_keys=True)
                try:
                    mutate(value)
                except (KeyError, IndexError, TypeError, AttributeError, ValueError):
                    continue
                if json.dumps(value, sort_keys=True) == before:
                    continue
                applied += 1
                path.write_text(json.dumps(value))
                with self.subTest(index=index, identifier=identifier, file=relative, mutation=name):
                    self.assertEqual(module.validate(root, {identifier})["status"], "Failed")
        # 改変の適用が空振りしていないこと。
        self.assertGreater(applied, 380)

    def test_multi_doctor_git_audit_rejects_changed_corpus(self):
        """入力の欠落と追加（バイト列の照合）と、原因を消す入力の書換え（参照計算と原因の構成の検査）を拒否する。"""
        module = multi_doctor_git_fixtures
        for identifier in module.CASES:
            names = sorted(f"repo/{name}" for name in module.reviewed_inputs(identifier) if name.endswith(".md") or name.endswith("bitz.yaml"))
            for name in [*names, "extra"]:
                with self.subTest(identifier=identifier, file=name), tempfile.TemporaryDirectory() as temporary:
                    root = self.copy_multi_fixture(temporary, identifier)
                    fixture = root / "multi" / identifier
                    if name == "extra":
                        (fixture / "repo/extra.txt").write_text("x")
                    else:
                        (fixture / name).unlink()
                    self.assertEqual(module.validate(root, {identifier})["status"], "Failed")
        # 原因を消す・変える書換え。入力のバイト列の照合とスナップショットを通した上で（書換え後の内容を`reviewed_inputs`にし、副作用の期待値を作り直す）、
        # 参照計算と原因の構成の検査が拒否することを確かめる（バイト列の照合で先に拒否される空振りを避ける）。
        root_config = ".spec/bitz.yaml"
        edits = {
            # ルートの設定の原因を消す（停止しなくなる）。
            "MULTI-040-01": [(root_config, 'earsAi: "2.0"', 'earsAi: "1.0"'),
                             # 原因を別の種類に変える（スキーマの非対応が優先して分類される）。
                             (root_config, 'schemaVersion: "1.0"', 'schemaVersion: "2.0"'),
                             # メンバーの設定が非対応のメジャーバージョンになる（原因がルートだけでなくなる）。
                             ("apps/web/.spec/bitz.yaml", 'earsAi: "1.0"', 'earsAi: "2.0"')],
            "MULTI-040-02": [(root_config, 'schemaVersion: "2.0"', 'schemaVersion: "1.0"'),
                             ("services/api/.spec/bitz.yaml", 'schemaVersion: "1.0"', 'schemaVersion: "2.0"')],
            "MULTI-040-03": [(root_config, "language: &label ja", "language: ja"),
                             (root_config, "language: &label ja", "language: &label ja\nlanguage2: &other ja")],
            "MULTI-040-04": [(root_config, 'earsAi: "2.0"', 'earsAi: "1.0"')],
            "MULTI-040-05": [(root_config, 'schemaVersion: "2.0"', 'schemaVersion: "1.0"')],
            "MULTI-040-06": [(root_config, 'earsAi: "2.0"', 'earsAi: "1.0"')],
            "MULTI-040-07": [(root_config, 'schemaVersion: "2.0"', 'schemaVersion: "1.0"')],
            "MULTI-040-08": [(root_config, 'earsAi: "2.0"', 'earsAi: "1.0"')],
            "MULTI-040-09": [(root_config, 'schemaVersion: "2.0"', 'schemaVersion: "1.0"')],
            "MULTI-040-10": [(root_config, "language: &label ja", "language: ja")],
        }
        byte_phrases = ("入力がレビュー済みのcorpusと異なります", "隔離した準備手順が固定したスナップショットと異なります")
        for identifier, changes in edits.items():
            for relative, old, new in changes:
                with self.subTest(identifier=identifier, file=relative, edit=old), tempfile.TemporaryDirectory() as temporary:
                    root = self.copy_multi_fixture(temporary, identifier)
                    fixture = root / "multi" / identifier
                    path = fixture / "repo" / relative
                    self.assertIn(old, path.read_text())
                    path.write_text(path.read_text().replace(old, new))
                    edited = dict(module.reviewed_inputs(identifier))
                    edited[relative] = path.read_bytes()
                    manifest = json.loads((fixture / "manifest.json").read_text())
                    repository = fixture_setup(fixture, manifest, Path(temporary) / "regen" / "repo")
                    external = {key: Path(temporary) / "regen" / key for key in ("home", "cache", "temporary")}
                    for directory in external.values():
                        directory.mkdir()
                    state = module.observe_state(manifest, repository, external)
                    (fixture / "side-effects.json").write_text(json.dumps({"schemaVersion": "1.0", "policy": "read-only", "before": state, "after": state}))
                    with patch.object(module, "reviewed_inputs", lambda _identifier, edited=edited: edited):
                        outcome = module.validate(root, {identifier})
                    self.assertEqual(outcome["status"], "Failed")
                    self.assertEqual(len(outcome["errors"]), 1)
                    self.assertFalse(any(phrase in outcome["errors"][0] for phrase in byte_phrases), outcome["errors"][0])
                    self.assertNotIn("KeyError", outcome["errors"][0])

    def copy_single_fixture(self, temporary, identifier):
        root = Path(temporary)
        shutil.copytree(audit.FIXTURES / "single" / identifier, root / "single" / identifier, symlinks=True)
        for name in ("manifest", "result", "side-effects", "frontmatter"):
            shutil.copy2(schema_path(audit.FIXTURES, name), root)
        return root

    def test_verify_stop_revision_fixtures(self):
        """`SINGLE-165-01`〜`07`: `verify`の早期に返す結果の`revision`と`--report`を固定する（確認事項C41）。"""
        module = verify_stop_revision_fixtures
        result = module.validate()
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["prepared"], [f"SINGLE-165-{number:02d}" for number in range(1, 8)])
        self.assertEqual(result["references"], 1)
        self.assertEqual(result["core_execution"], "Not run")
        # 複製した状態でも通る（以降の拒否の試験が、複製の不備で空振りしていないことの陽性対照）。
        for identifier in module.CASES:
            with self.subTest(identifier=identifier), tempfile.TemporaryDirectory() as temporary:
                root = self.copy_single_fixture(temporary, identifier)
                self.assertEqual(module.validate(root, {identifier})["errors"], [])

    def test_verify_stop_revision_fixtures_cover_both_early_returns_and_every_revision_state(self):
        """早期に返す2つの原因、`revision`の状態、`--report`の有無を、少なくとも1件ずつ固定する。"""
        module = verify_stop_revision_fixtures
        cases = module.CASES.values()
        self.assertEqual({case["stop"] for case in cases}, {"schema", "anchor", None})
        self.assertEqual({case["git"] for case in cases}, {"committed", "staged", "absent"})
        self.assertEqual({case["report"] for case in cases}, {True, False})
        results = {identifier: json.loads((audit.FIXTURES / "single" / identifier / module.RESULT_FILE).read_text())
                   for identifier in module.CASES}
        revisions = [result["revision"] for result in results.values()]
        self.assertIn({"commit": "0" * 40, "dirty": False}, revisions)
        self.assertIn({"commit": "0" * 40, "dirty": True}, revisions)
        self.assertIn(None, revisions)
        # コミットありだけ`revision`を返し、`--report`のレポートは状態にかかわらず1件。
        for identifier, case in module.CASES.items():
            manifest = json.loads((audit.FIXTURES / "single" / identifier / "manifest.json").read_text())
            self.assertEqual(manifest["expect"]["reportFileCount"], 1 if case["report"] else 0, identifier)
            self.assertEqual("--report" in manifest["invocation"]["argv"], case["report"], identifier)
            self.assertEqual(results[identifier]["revision"] is None, case["git"] != "committed", identifier)
            self.assertNotEqual(results[identifier]["status"], "passed", identifier)

    def test_verify_stop_revision_reference_rules(self):
        """参照計算（結果・診断・終了コード §2・§3・§8、`verify` §3）。"""
        module = verify_stop_revision_fixtures
        schema, anchor, valid = (module.stopped_config(stop) for stop in ("schema", "anchor", None))
        draft = module.draft_requirement()
        approved = draft.replace("status: draft", "status: approved")
        self.assertEqual(module.default_targets([draft]), 0)
        self.assertEqual(module.default_targets([draft, approved]), 1)
        stopped = module.reference_expected(schema, [draft], (True, False), True)
        self.assertEqual((stopped["status"], stopped["exit"], stopped["code"], stopped["reports"], stopped["workspaceId"]),
                         ("blocked", 2, "SPEC-CONFIG-SCHEMA-001", 1, "root"))
        self.assertEqual(stopped["revision"], {"dirty": False})
        # `dirty`は作業ツリーの状態から導く。コミットなしとGit不在は`revision`なし。`--report`がなければレポートなし。
        self.assertEqual(module.reference_expected(schema, [draft], (True, True), True)["revision"], {"dirty": True})
        self.assertIsNone(module.reference_expected(schema, [draft], (False, False), True)["revision"])
        self.assertIsNone(module.reference_expected(schema, [draft], None, True)["revision"])
        self.assertEqual(module.reference_expected(schema, [draft], (True, False), False)["reports"], 0)
        # 構文の不正は`error`／3で、同一性を構成できないので`workspace.id`は`null`。
        broken = module.reference_expected(anchor, [draft], (True, False), True)
        self.assertEqual((broken["status"], broken["exit"], broken["workspaceId"]), ("error", 3, None))
        # 設定が止まらず対象が0件なら`SPEC-VERIFY-BLOCKED-002`。対象があるなら、この群の対象外。
        empty = module.reference_expected(valid, [draft], (True, False), True)
        self.assertEqual((empty["code"], empty["status"], empty["stop"]), ("SPEC-VERIFY-BLOCKED-002", "blocked", None))
        with self.assertRaises(ValueError):
            module.reference_expected(valid, [approved], (True, False), True)

    def test_verify_stop_revision_audit_rejects_changed_expectations(self):
        """期待結果・起動条件・副作用の期待値の改変を拒否する。"""
        module = verify_stop_revision_fixtures

        def entry(value):
            return value["diagnostics"][0]

        results = {
            "status": lambda v: v.update(status="failed"),
            "status-error": lambda v: v.update(status="error" if v["status"] != "error" else "blocked"),
            "diag-drop": lambda v: v["diagnostics"].pop(),
            "diag-duplicate": lambda v: v["diagnostics"].append(copy.deepcopy(entry(v))),
            "diag-code": lambda v: entry(v).update(code="SPEC-VERIFY-BLOCKED-001"),
            "diag-effect": lambda v: entry(v).update(resultStatus="failed"),
            "diag-summary": lambda v: entry(v).update(summary=entry(v)["summary"] + "。"),
            "diag-source": lambda v: entry(v).update(source={"kind": "invocation"}),
            "diag-source-id": lambda v: entry(v)["source"].update(workspaceId="web"),
            "diag-report-write": lambda v: v["diagnostics"].append(
                {"code": "SPEC-REPORT-WRITE-001", "severity": "error", "resultStatus": "error",
                 "summary": "レポートの保存先へ排他的に作成できません",
                 "source": {"kind": "file", "workspaceId": "root", "path": ".spec/reports"}}),
            "revision-null": lambda v: v.update(revision=None),
            "revision-dirty": lambda v: v.update(revision={"commit": "0" * 40, "dirty": not (v["revision"] or {"dirty": False})["dirty"]}),
            "revision-base": lambda v: v.update(revision={"base": "0" * 40, "commit": "0" * 40, "dirty": False}),
            "revision-missing": lambda v: v.pop("revision"),
            "workspace-id": lambda v: v["workspace"].update(id="web" if v["workspace"]["id"] != "web" else "root"),
            "workspace-path": lambda v: v["workspace"].update(path="docs"),
            "scope": lambda v: v.update(scope="selected"),
            "targets": lambda v: v.update(targetResults=[{"target": "REQ-001", "status": "blocked", "contextDigest": None,
                                                           "statements": [], "bindingRefs": [], "diagnostics": []}]),
            "commands": lambda v: v.update(commands=[{"bindingId": "root::default"}]),
        }
        manifests = {
            "status": lambda v: v["expect"].update(status="failed"),
            "exit-code": lambda v: v["expect"].update(exitCode=1),
            "report-count": lambda v: v["expect"].update(reportFileCount=1 - v["expect"]["reportFileCount"]),
            "report-flag": lambda v: (v["invocation"]["argv"].remove("--report") if "--report" in v["invocation"]["argv"]
                                      else v["invocation"]["argv"].append("--report")),
            "argv-target": lambda v: v["invocation"]["argv"].insert(1, "REQ-001"),
            "argv-operation": lambda v: v["invocation"]["argv"].__setitem__(0, "check"),
            "cwd": lambda v: v["invocation"].update(cwd="docs"),
            "env": lambda v: v["invocation"].update(env={} if v["invocation"]["env"] else {"PATH": "/dev/null"}),
            "git": lambda v: v["setup"].update(git=not v["setup"]["git"]),
            "base-commit": lambda v: (v["setup"].pop("baseCommit") if "baseCommit" in v["setup"]
                                      else v["setup"].update(baseCommit={"message": "base", "paths": ["."]})),
            "operations": lambda v: v["setup"]["operations"].append({"op": "delete", "path": ".spec/bitz.yaml"}),
        }
        effects = {
            "policy": lambda v: v.update(policy="read-only" if v["policy"] != "read-only" else "explicit-report"),
            "created-count": lambda v: v["report"].update(createdCount=2),
            "report-drop": lambda v: v.pop("report"),
            "name-pattern": lambda v: v["report"].update(namePattern="^.*$"),
            "temporary": lambda v: v["report"].update(temporaryFilesRemaining=1),
            "existing-report": lambda v: v["before"]["repository"].pop(module.EXISTING_REPORT),
            "extra": lambda v: v["before"]["repository"].update(extra={"kind": "directory"}),
            "after-changed": lambda v: v["after"]["repository"].pop(module.EXISTING_REPORT),
        }
        mutations = []
        for identifier in module.CASES:
            mutations += [(identifier, module.RESULT_FILE, name, change) for name, change in results.items()]
            mutations += [(identifier, "manifest.json", name, change) for name, change in manifests.items()]
            mutations += [(identifier, "side-effects.json", name, change) for name, change in effects.items()]
        applied = 0
        for index, (identifier, relative, name, mutate) in enumerate(mutations):
            with tempfile.TemporaryDirectory() as temporary:
                root = self.copy_single_fixture(temporary, identifier)
                path = root / "single" / identifier / relative
                value = json.loads(path.read_text())
                before = json.dumps(value, sort_keys=True)
                try:
                    mutate(value)
                except (KeyError, IndexError, TypeError, AttributeError, ValueError):
                    continue
                if json.dumps(value, sort_keys=True) == before:
                    continue
                applied += 1
                path.write_text(json.dumps(value))
                with self.subTest(index=index, identifier=identifier, file=relative, mutation=name):
                    self.assertEqual(module.validate(root, {identifier})["status"], "Failed")
        # 改変の適用が空振りしていないこと。
        self.assertGreater(applied, 190)

    def test_verify_stop_revision_audit_rejects_changed_corpus(self):
        """入力の欠落と追加（バイト列の照合）と、原因を消す・変える入力の書換え（参照計算と原因の構成の検査）を拒否する。"""
        module = verify_stop_revision_fixtures
        for identifier in module.CASES:
            for name in [*sorted(f"repo/{path}" for path in module.reviewed_inputs(identifier)), "extra"]:
                with self.subTest(identifier=identifier, file=name), tempfile.TemporaryDirectory() as temporary:
                    root = self.copy_single_fixture(temporary, identifier)
                    fixture = root / "single" / identifier
                    if name == "extra":
                        (fixture / "repo/extra.txt").write_text("x")
                    else:
                        (fixture / name).unlink()
                    self.assertEqual(module.validate(root, {identifier})["status"], "Failed")
        config, requirement = module.CONFIG_PATH, module.REQ_PATH
        edits = {
            # 設定の原因を消す（停止しなくなる）、別の種類に変える。
            "SINGLE-165-01": [(config, 'schemaVersion: "2.0"', 'schemaVersion: "1.0"'),
                              (config, 'schemaVersion: "2.0"', 'schemaVersion: "2.0"\nx: &a 1')],
            "SINGLE-165-02": [(config, "language: &label ja", "language: ja")],
            # 対象が0件でなくなる（`approved`のREQ）、設定が止まる。
            "SINGLE-165-03": [(requirement, "status: draft", "status: approved"),
                              (config, 'schemaVersion: "1.0"', 'schemaVersion: "2.0"')],
            "SINGLE-165-04": [(requirement, "status: draft", "status: approved")],
            "SINGLE-165-05": [(config, 'schemaVersion: "2.0"', 'schemaVersion: "1.0"')],
            "SINGLE-165-06": [(config, 'schemaVersion: "2.0"', 'schemaVersion: "1.0"')],
            "SINGLE-165-07": [(requirement, "status: draft", "status: approved")],
        }
        byte_phrases = ("入力がレビュー済みのcorpusと異なります", "隔離した準備手順が固定したスナップショットと異なります")
        for identifier, changes in edits.items():
            for relative, old, new in changes:
                with self.subTest(identifier=identifier, file=relative, edit=old), tempfile.TemporaryDirectory() as temporary:
                    root = self.copy_single_fixture(temporary, identifier)
                    fixture = root / "single" / identifier
                    path = fixture / "repo" / relative
                    self.assertIn(old, path.read_text())
                    path.write_text(path.read_text().replace(old, new))
                    edited = dict(module.reviewed_inputs(identifier))
                    edited[relative] = path.read_bytes()
                    manifest = json.loads((fixture / "manifest.json").read_text())
                    repository = fixture_setup(fixture, manifest, Path(temporary) / "regen" / "repo")
                    external = {key: Path(temporary) / "regen" / key for key in ("home", "cache", "temporary")}
                    for directory in external.values():
                        directory.mkdir()
                    state = module.observe_state(manifest, repository, external)
                    (fixture / "side-effects.json").write_text(json.dumps(module.reviewed_effects(identifier, state)))
                    with patch.object(module, "reviewed_inputs", lambda _identifier, edited=edited: edited):
                        outcome = module.validate(root, {identifier})
                    self.assertEqual(outcome["status"], "Failed")
                    self.assertEqual(len(outcome["errors"]), 1)
                    self.assertFalse(any(phrase in outcome["errors"][0] for phrase in byte_phrases), outcome["errors"][0])
                    self.assertNotIn("KeyError", outcome["errors"][0])

    def test_verify_stop_revision_audit_rejects_a_changed_git_state(self):
        """コミットの有無と作業ツリーの変更の有無は、準備手順の後のGitの状態から確かめる。準備手順だけを変えると拒否する。"""
        module = verify_stop_revision_fixtures

        def staged(manifest):
            manifest["setup"].pop("baseCommit")
            manifest["setup"]["operations"] = [{"op": "stage", "paths": ["."]}]

        changes = {
            # コミットなしの入力をコミットする、コミットありの入力をステージだけにする、未追跡のファイルの有無を変える。
            "SINGLE-165-06": lambda m: m["setup"].update(operations=[], baseCommit={"message": "base", "paths": ["."]}),
            "SINGLE-165-01": staged,
            "SINGLE-165-05": lambda m: m["setup"]["baseCommit"].update(paths=["."]),
            "SINGLE-165-04": lambda m: m["setup"]["baseCommit"].update(paths=[".spec/bitz.yaml"]),
        }
        for identifier, change in changes.items():
            with self.subTest(identifier=identifier), tempfile.TemporaryDirectory() as temporary:
                root = self.copy_single_fixture(temporary, identifier)
                fixture = root / "single" / identifier
                manifest = json.loads((fixture / "manifest.json").read_text())
                change(manifest)
                # 起動条件の照合で先に拒否される空振りを避け、準備手順の後のGitの状態の検査だけを直接確かめる。
                repository = fixture_setup(fixture, manifest, Path(temporary) / "regen" / "repo")
                with self.assertRaises(ValueError):
                    module.check_conditions(identifier, repository, manifest)

    def test_context_stop_revision_fixtures(self):
        """`SINGLE-166-01`〜`11`: `context`の早期に返す結果の`revision`を固定する（確認事項C45）。"""
        module = context_stop_revision_fixtures
        result = module.validate()
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["prepared"], [f"SINGLE-166-{number:02d}" for number in range(1, 12)])
        self.assertEqual(result["references"], 1)
        self.assertEqual(result["core_execution"], "Not run")
        # 複製した状態でも通る（以降の拒否の試験が、複製の不備で空振りしていないことの陽性対照）。
        for identifier in module.CASES:
            with self.subTest(identifier=identifier), tempfile.TemporaryDirectory() as temporary:
                root = self.copy_single_fixture(temporary, identifier)
                self.assertEqual(module.validate(root, {identifier})["errors"], [])

    def test_context_stop_revision_fixtures_cover_every_early_return_and_every_revision_state(self):
        """早期に返す結果の原因（8種類）と、`revision`の3つの状態（`dirty`の真偽とnull）を、少なくとも1件ずつ固定する。"""
        module = context_stop_revision_fixtures
        results = {identifier: json.loads((audit.FIXTURES / "single" / identifier / module.RESULT_FILE).read_text())
                   for identifier in module.CASES}
        codes = {identifier: [item["code"] for item in result["diagnostics"]] for identifier, result in results.items()}
        causes = {code for identifier, row in codes.items() for code in row}
        self.assertEqual(causes, {"SPEC-WORKSPACE-MISSING-001", "SPEC-CONFIG-SCHEMA-001", "CTX-ROOT-MISSING-001",
                                  "SPEC-RELATION-MISSING-001", "CTX-RELATION-TYPE-001", "CTX-STATE-001",
                                  "CTX-LIMIT-001", "CTX-PROJECTION-001", "CTX-STALE-001"})
        # 状態の診断と型制約の診断が重なる経路（対象展開の誤りを持つ経路）と、強い関係の検査だけが失敗する経路を両方持つ。
        self.assertIn(["SPEC-RELATION-MISSING-001"], codes.values())
        self.assertIn(["CTX-RELATION-TYPE-001", "CTX-STATE-001"], codes.values())
        revisions = [result["revision"] for result in results.values()]
        self.assertIn({"commit": "0" * 40, "dirty": False}, revisions)
        self.assertIn({"commit": "0" * 40, "dirty": True}, revisions)
        self.assertIn(None, revisions)
        self.assertEqual({case["git"] for case in module.CASES.values()}, {"committed", "staged", "absent"})
        # コミットありだけ`revision`を返す。成功した`context`ではなく、すべて非成功の結果である。
        for identifier, case in module.CASES.items():
            self.assertEqual(results[identifier]["revision"] is None, case["git"] != "committed", identifier)
            self.assertNotIn(results[identifier]["status"], ("passed", "passed_with_warnings"), identifier)
            self.assertEqual(results[identifier]["documents"], [], identifier)
        # 元のfixtureは、コミットのないリポジトリの対照として`revision: null`である（この群が変えるのはGitの状態だけ）。
        for base in {case["base"] for case in module.CASES.values() if case["base"]}:
            original = json.loads((audit.FIXTURES / "single" / base / module.RESULT_FILE).read_text())
            self.assertIsNone(original["revision"], base)

    def test_context_stop_revision_reference_rules(self):
        """参照計算（結果・診断・終了コード §2）。"""
        module = context_stop_revision_fixtures
        self.assertEqual(module.revision_for((True, False)), {"commit": "0" * 40, "dirty": False})
        self.assertEqual(module.revision_for((True, True)), {"commit": "0" * 40, "dirty": True})
        self.assertIsNone(module.revision_for((False, False)))
        self.assertIsNone(module.revision_for((False, True)))
        self.assertIsNone(module.revision_for(None))
        # 参照計算は、元のfixtureの`revision`以外を引き継ぎ、Gitの状態だけから`revision`を導く。
        expected = module.reference_expected("SINGLE-166-03", (True, False))
        original = json.loads((audit.FIXTURES / "single/SINGLE-050" / module.RESULT_FILE).read_text())
        self.assertEqual({**expected, "revision": None}, original)
        self.assertEqual(module.reference_expected("SINGLE-166-03", (True, True))["revision"]["dirty"], True)
        self.assertIsNone(module.reference_expected("SINGLE-166-03", None)["revision"])
        # 参照切れの診断は、同じ入力を`check`で検査した`SINGLE-020`のレビュー済みの診断と同じである。
        reviewed = json.loads((audit.FIXTURES / "single/SINGLE-020/expected/check.json").read_text())["diagnostics"]
        self.assertEqual(reviewed, [module.RELATION_MISSING])
        self.assertEqual(module.reference_expected("SINGLE-166-04", (True, False))["resolution"]["unresolvedStrongRelations"], 1)

    def test_context_stop_revision_audit_rejects_changed_expectations(self):
        """期待結果・起動条件・副作用の期待値の改変を拒否する。"""
        module = context_stop_revision_fixtures

        def entry(value):
            return value["diagnostics"][0]

        results = {
            "status": lambda v: v.update(status="passed" if v["status"] != "passed" else "failed"),
            "status-error": lambda v: v.update(status="error" if v["status"] != "error" else "blocked"),
            "diag-drop": lambda v: v["diagnostics"].pop(),
            "diag-duplicate": lambda v: v["diagnostics"].append(copy.deepcopy(entry(v))),
            "diag-code": lambda v: entry(v).update(code="CTX-LIMIT-002"),
            "diag-effect": lambda v: entry(v).update(resultStatus="error"),
            "diag-summary": lambda v: entry(v).update(summary=entry(v)["summary"] + "。"),
            "diag-source": lambda v: entry(v).update(source={"kind": "invocation"}),
            "revision-null": lambda v: v.update(revision=None),
            "revision-dirty": lambda v: v.update(revision={"commit": "0" * 40, "dirty": not (v["revision"] or {"dirty": False})["dirty"]}),
            "revision-base": lambda v: v.update(revision={"base": "0" * 40, "commit": "0" * 40, "dirty": False}),
            "revision-missing": lambda v: v.pop("revision"),
            "workspace-id": lambda v: v["workspace"].update(id="web" if v["workspace"]["id"] != "web" else "root"),
            "workspace-path": lambda v: v["workspace"].update(path="docs"),
            "digest": lambda v: v.update(contextDigest=None if v["contextDigest"] else "sha256:" + "0" * 64),
            "complete": lambda v: v["resolution"].update(complete=not v["resolution"]["complete"]),
            "unresolved": lambda v: v["resolution"].update(unresolvedStrongRelations=v["resolution"]["unresolvedStrongRelations"] + 1),
            "documents": lambda v: v.update(documents=[{"id": "REQ-001"}]),
            "roots": lambda v: v.update(roots=["REQ-999"]),
            "purpose": lambda v: v.update(purpose="implement" if v["purpose"] != "implement" else "verify"),
        }
        manifests = {
            "status": lambda v: v["expect"].update(status="passed"),
            "exit-code": lambda v: v["expect"].update(exitCode=v["expect"]["exitCode"] + 1),
            "report-count": lambda v: v["expect"].update(reportFileCount=1),
            "argv-operation": lambda v: v["invocation"]["argv"].__setitem__(0, "check"),
            "argv-root": lambda v: v["invocation"]["argv"].__setitem__(1, "REQ-404"),
            "argv-report": lambda v: v["invocation"]["argv"].append("--report"),
            "cwd": lambda v: v["invocation"].update(cwd="docs"),
            "env": lambda v: v["invocation"].update(env={} if v["invocation"]["env"] else {"PATH": "/dev/null"}),
            "git": lambda v: v["setup"].update(git=not v["setup"]["git"]),
            "base-commit": lambda v: (v["setup"].pop("baseCommit") if "baseCommit" in v["setup"]
                                      else v["setup"].update(baseCommit={"message": "base", "paths": ["."]})),
            "operations": lambda v: v["setup"]["operations"].append({"op": "delete", "path": ".spec/bitz.yaml"}),
        }
        effects = {
            "policy": lambda v: v.update(policy="explicit-report" if v["policy"] == "read-only" else "read-only"),
            "report-add": lambda v: v.update(report={"directory": ".spec/reports", "createdCount": 1,
                                                       "namePattern": "^.*$", "temporaryFilesRemaining": 0}),
            "extra": lambda v: v["before"]["repository"].update(extra={"kind": "directory"}),
            "after-changed": lambda v: v["after"]["repository"].update(extra={"kind": "directory"}),
        }
        mutations = []
        for identifier in module.CASES:
            mutations += [(identifier, module.RESULT_FILE, name, change) for name, change in results.items()]
            mutations += [(identifier, "manifest.json", name, change) for name, change in manifests.items()]
            mutations += [(identifier, "side-effects.json", name, change) for name, change in effects.items()]
        applied = 0
        for index, (identifier, relative, name, mutate) in enumerate(mutations):
            with tempfile.TemporaryDirectory() as temporary:
                root = self.copy_single_fixture(temporary, identifier)
                path = root / "single" / identifier / relative
                value = json.loads(path.read_text())
                before = json.dumps(value, sort_keys=True)
                try:
                    mutate(value)
                except (KeyError, IndexError, TypeError, AttributeError, ValueError):
                    continue
                if json.dumps(value, sort_keys=True) == before:
                    continue
                applied += 1
                path.write_text(json.dumps(value))
                with self.subTest(index=index, identifier=identifier, file=relative, mutation=name):
                    self.assertEqual(module.validate(root, {identifier})["status"], "Failed")
        # 改変の適用が空振りしていないこと。
        self.assertGreater(applied, 250)

    def test_context_stop_revision_audit_rejects_changed_corpus(self):
        """入力の欠落と追加（バイト列の照合）、入力の書換えを拒否する。"""
        module = context_stop_revision_fixtures
        for identifier in module.CASES:
            for name in [*sorted(f"repo/{path}" for path in module.reviewed_inputs(identifier)), "extra"]:
                with self.subTest(identifier=identifier, file=name), tempfile.TemporaryDirectory() as temporary:
                    root = self.copy_single_fixture(temporary, identifier)
                    fixture = root / "single" / identifier
                    if name == "extra":
                        (fixture / "repo/extra.txt").write_text("x")
                    else:
                        (fixture / name).unlink()
                    self.assertEqual(module.validate(root, {identifier})["status"], "Failed")
        # 原因を消す・変える書換え。副作用の期待値は準備手順の観測から作り直したうえで、入力のレビュー済みのcorpusとの照合で拒否されることを確かめる。
        edits = {
            "SINGLE-166-04": [(".spec/requirements/REQ-001.md", "requires: [REQ-999]", "requires: []")],
            "SINGLE-166-10": [(".spec/requirements/REQ-001.md", "requires: [REQ-999]", "requires: []")],
            "SINGLE-166-03": [(".spec/bitz.yaml", 'earsAi: "1.0"', 'earsAi: "1.0"\nx: 1')],
            "SINGLE-166-02": [(".spec/bitz.yaml", "language: 42", "language: ja")],
        }
        for identifier, changes in edits.items():
            for relative, old, new in changes:
                with self.subTest(identifier=identifier, file=relative, edit=old), tempfile.TemporaryDirectory() as temporary:
                    root = self.copy_single_fixture(temporary, identifier)
                    fixture = root / "single" / identifier
                    path = fixture / "repo" / relative
                    self.assertIn(old, path.read_text(), "改変の元の文字列が入力にありません")
                    path.write_text(path.read_text().replace(old, new))
                    manifest = json.loads((fixture / "manifest.json").read_text())
                    repository = fixture_setup(fixture, manifest, Path(temporary) / "regen" / "repo")
                    external = {key: Path(temporary) / "regen" / key for key in ("home", "cache", "temporary")}
                    for directory in external.values():
                        directory.mkdir()
                    state = module.observe_state(manifest, repository, external)
                    (fixture / "side-effects.json").write_text(json.dumps(module.reviewed_effects(identifier, state)))
                    outcome = module.validate(root, {identifier})
                    self.assertEqual(outcome["status"], "Failed")
                    self.assertIn("入力がレビュー済みのcorpusと異なります", outcome["errors"][0])

    def test_context_stop_revision_audit_rejects_a_changed_git_state(self):
        """コミットの有無と作業ツリーの変更の有無は、準備手順の後のGitの状態から確かめる。準備手順だけを変えると拒否する。"""
        module = context_stop_revision_fixtures

        def staged(manifest):
            manifest["setup"].pop("baseCommit")
            manifest["setup"]["operations"] = [{"op": "stage", "paths": ["."]}]

        changes = {
            # コミットなしの入力をコミットする、コミットありの入力をステージだけにする、未追跡のファイルの有無を変える。
            "SINGLE-166-10": lambda m: m["setup"].update(operations=[], baseCommit={"message": "base", "paths": ["."]}),
            "SINGLE-166-01": staged,
            "SINGLE-166-09": lambda m: m["setup"]["baseCommit"].update(paths=["."]),
            "SINGLE-166-03": lambda m: m["setup"]["baseCommit"].update(paths=[".spec/bitz.yaml"]),
        }
        for identifier, change in changes.items():
            with self.subTest(identifier=identifier), tempfile.TemporaryDirectory() as temporary:
                root = self.copy_single_fixture(temporary, identifier)
                fixture = root / "single" / identifier
                manifest = json.loads((fixture / "manifest.json").read_text())
                change(manifest)
                # 起動条件の照合で先に拒否される空振りを避け、準備手順の後のGitの状態の検査だけを直接確かめる。
                repository = fixture_setup(fixture, manifest, Path(temporary) / "regen" / "repo")
                with self.assertRaises(ValueError):
                    module.check_conditions(identifier, repository, manifest)

    def test_context_stop_revision_audit_rejects_a_drifted_source_fixture(self):
        """期待値は元のfixtureから引き継ぐ。元のfixtureの期待値や準備手順が変わると、この群は拒否する。"""
        module = context_stop_revision_fixtures
        sources = sorted({case["base"] for case in module.CASES.values() if case["base"]} | {module.RELATION_MISSING_SOURCE})
        changes = {
            "status": lambda v: v.update(status="blocked" if v["status"] != "blocked" else "failed"),
            "diagnostic": lambda v: v["diagnostics"][0].update(summary=v["diagnostics"][0]["summary"] + "。"),
            "revision": lambda v: v.update(revision={"commit": "0" * 40, "dirty": False}),
        }
        for source in sources:
            relative = "expected/check.json" if source == module.RELATION_MISSING_SOURCE else module.RESULT_FILE
            for name, change in changes.items():
                # `SINGLE-020`は診断だけを引き継ぐ（状態と`revision`は`check`の結果であり、この群の期待値に使わない）。
                if source == module.RELATION_MISSING_SOURCE and name != "diagnostic":
                    continue
                with self.subTest(source=source, change=name), tempfile.TemporaryDirectory() as temporary:
                    copied = Path(temporary) / "single"
                    copied.mkdir()
                    for other in sources:
                        shutil.copytree(audit.FIXTURES / "single" / other, copied / other, symlinks=True)
                    path = copied / source / relative
                    value = json.loads(path.read_text())
                    before = json.dumps(value, sort_keys=True)
                    change(value)
                    if json.dumps(value, sort_keys=True) == before:
                        continue
                    path.write_text(json.dumps(value))
                    users = [identifier for identifier in module.CASES if module.source_of(identifier) == source]
                    with patch.object(module, "SINGLE", copied):
                        outcome = module.validate(audit.FIXTURES, set(users))
                    self.assertEqual(outcome["status"], "Failed", (source, name))
                    self.assertEqual(len(outcome["errors"]), len(users), (source, name, outcome["errors"]))

    def copy_repo_root_fixture(self, temporary, identifier):
        root = Path(temporary)
        kind = repo_root_fixtures.CASES[identifier][0]
        shutil.copytree(audit.FIXTURES / kind / identifier, root / kind / identifier, symlinks=True)
        for name in ("manifest", "result", "side-effects", "frontmatter"):
            shutil.copy2(schema_path(audit.FIXTURES, name), root)
        return root

    def test_repo_root_fixtures(self):
        result = repo_root_fixtures.validate()
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["prepared"], ["SINGLE-158", "MULTI-030-01", "MULTI-030-02"])
        self.assertEqual(result["core_execution"], "Not run")
        # 複製した状態でも通る（以降の拒否の試験が、複製の不備で空振りしていないことの陽性対照）。
        for identifier in repo_root_fixtures.CASES:
            with self.subTest(identifier=identifier), tempfile.TemporaryDirectory() as temporary:
                root = self.copy_repo_root_fixture(temporary, identifier)
                self.assertEqual(repo_root_fixtures.validate(root, {identifier})["errors"], [])

    def test_repo_root_reference_follows_the_inputs(self):
        """参照計算は、基準版と作業ツリーの木構造から導き、実行するディレクトリによらない。リテラルの期待値の改変を拒否する。"""
        module = repo_root_fixtures
        for identifier in module.CASES:
            with self.subTest(identifier=identifier), tempfile.TemporaryDirectory() as temporary:
                root = self.copy_repo_root_fixture(temporary, identifier)
                fixture = root / module.CASES[identifier][0] / identifier
                manifest = json.loads((fixture / "manifest.json").read_text())
                repository = fixture_setup(fixture, manifest, Path(temporary) / "work" / "repo")
                result = json.loads((fixture / "expected/check.json").read_text())
                reference = module.reference_for(identifier, repository)
                module.check_result_against_reference(result, reference)
                module.check_invariance(identifier, repository)
                if identifier == "MULTI-030-02":
                    self.assertEqual(reference, {"unregistered": ["tools/x/.spec/bitz.yaml"]})
                    changes = [lambda v: v.update(status="passed"),
                               lambda v: v["diagnostics"].clear(),
                               lambda v: v["diagnostics"][0]["source"].update(path="apps/web/.spec/bitz.yaml"),
                               lambda v: v["diagnostics"][0]["source"].update(workspaceId="web"),
                               lambda v: v["diagnostics"].append(copy.deepcopy(v["diagnostics"][0])),
                               lambda v: v.update(workspaces=[{"id": "web", "path": "apps/web"}])]
                else:
                    expected_workspace = {"id": "root", "path": "."} if identifier == "SINGLE-158" else {"id": "web", "path": "apps/web"}
                    self.assertEqual(reference["workspace"], expected_workspace)
                    self.assertEqual([item["code"] for item in reference["diagnostics"]],
                                     ["SPEC-SAFETY-APPROVED-001", "SPEC-STATE-TRANSITION-001"])
                    # 現在版に残るREQ 1件（削除したREQは数えない）と、その規範文1件。
                    self.assertEqual((reference["documentCount"], reference["statementCount"]), (1, 1))
                    changes = [lambda v: v["workspace"].update(path="apps/web" if v["workspace"]["path"] == "." else "."),
                               lambda v: v["workspace"].update(id="platform", path="."),
                               lambda v: v.update(status="passed"),
                               lambda v: v["diagnostics"].clear(),
                               lambda v: v["diagnostics"].pop(0),
                               lambda v: v["diagnostics"].pop(1),
                               lambda v: v["diagnostics"].reverse(),
                               lambda v: v["diagnostics"][0].update(code="SPEC-STATE-TRANSITION-001"),
                               lambda v: v["diagnostics"][1].update(code="SPEC-SAFETY-APPROVED-001"),
                               lambda v: v["diagnostics"][0]["source"].update(key="status"),
                               lambda v: v["diagnostics"][0]["source"].update(workspaceId="platform"),
                               lambda v: v["diagnostics"][1]["source"].update(path="repo/" + v["diagnostics"][1]["source"]["path"]),
                               lambda v: v.update(checkedDocumentCount=0),
                               lambda v: v.update(checkedDocumentCount=2),
                               lambda v: v.update(checkedStatementCount=0),
                               lambda v: v.update(checkedStatementCount=2),
                               lambda v: v.update(scope="changed", selection={"changedPathCount": 2, "targetDocumentCount": 1,
                                                                              "excludedCodeTestPathCount": 0}),
                               lambda v: v.update(selection={"changedPathCount": 2, "targetDocumentCount": 1,
                                                             "excludedCodeTestPathCount": 0})]
                for index, change in enumerate(changes):
                    with self.subTest(identifier=identifier, change=index):
                        changed = copy.deepcopy(result)
                        change(changed)
                        self.assertNotEqual(changed, result)
                        with self.assertRaises(ValueError):
                            module.check_result_against_reference(changed, reference)
                if identifier == "MULTI-030-01":
                    # ルートのまま（作業ワークスペースが`platform`）では、`web`の変更は出発点にならず、期待と一致しない。
                    with self.assertRaises(ValueError):
                        module.check_result_against_reference(result, module.reference_check(repository, "multi", "full", ".", None))

    def test_repo_root_reference_uses_the_repository_root_for_git(self):
        """参照計算の基準版の一覧と変更集合は、現在のディレクトリではなくリポジトリのルートで求める。"""
        module = repo_root_fixtures
        for identifier in ("SINGLE-158", "MULTI-030-01"):
            with self.subTest(identifier=identifier), tempfile.TemporaryDirectory() as temporary:
                root = self.copy_repo_root_fixture(temporary, identifier)
                fixture = root / module.CASES[identifier][0] / identifier
                manifest = json.loads((fixture / "manifest.json").read_text())
                repository = fixture_setup(fixture, manifest, Path(temporary) / "work" / "repo")
                cwd = module.CASES[identifier][2]
                listing = module.base_listing(repository)
                # どのディレクトリから`--full-tree`で求めても、リポジトリ全体の一覧と同じである。
                self.assertEqual(
                    sorted(fixture_git(repository / cwd, "ls-tree", "-r", "--name-only", "-z", "--full-tree", "HEAD")
                           .decode().split("\0")[:-1]), sorted(listing))
                # 一覧は実行するディレクトリの外のパスも含み、変更集合はリポジトリのルート相対のパスで返る。
                self.assertTrue(any(not path.startswith(cwd + "/") for path in listing))
                self.assertEqual(len(module.changed_paths(repository)), 2)
                self.assertTrue(all(path.startswith(".spec/") or path.startswith("apps/web/.spec/")
                                    for path in module.changed_paths(repository)))

    def test_repo_root_audit_rejects_changed_expectations(self):
        """診断の欠落、状態の改変、実行するディレクトリの改変（ルートへ変えるなど）、準備手順の改変を拒否する。"""
        result_changes = {
            "SINGLE-158": [
                lambda v: v["diagnostics"].pop(0),
                lambda v: v["diagnostics"].pop(1),
                lambda v: v["diagnostics"].clear(),
                lambda v: v.update(status="passed", diagnostics=[]),
                lambda v: v.update(status="blocked"),
                lambda v: v["workspace"].update(path="docs"),
                lambda v: v.update(checkedDocumentCount=2),
                lambda v: v.update(checkedDocumentCount=0),
                lambda v: v.update(checkedStatementCount=0),
                lambda v: v["revision"].update(dirty=False),
                lambda v: v.update(scope="selected"),
                lambda v: v.update(scope="changed", selection={"changedPathCount": 2, "targetDocumentCount": 1,
                                                               "excludedCodeTestPathCount": 0}),
            ],
            "MULTI-030-01": [
                lambda v: v["diagnostics"].pop(0),
                lambda v: v["diagnostics"].pop(1),
                lambda v: v.update(status="passed", diagnostics=[]),
                lambda v: v["workspace"].update(id="platform", path="."),
                lambda v: v["workspace"].update(path="."),
                lambda v: v["diagnostics"][0]["source"].update(workspaceId="platform"),
                lambda v: v["diagnostics"][1]["source"].update(path="apps/web/.spec/requirements/REQ-011.md"),
                lambda v: v.update(checkedDocumentCount=2),
                lambda v: v.update(checkedStatementCount=2),
                lambda v: v["revision"].update(dirty=False),
                lambda v: v.update(scope="changed", selection={"changedPathCount": 2, "targetDocumentCount": 1,
                                                               "excludedCodeTestPathCount": 0}),
            ],
            "MULTI-030-02": [
                lambda v: v.update(status="passed", diagnostics=[]),
                lambda v: v["diagnostics"].clear(),
                lambda v: v.update(status="failed"),
                lambda v: v["diagnostics"][0]["source"].update(workspaceId="platform"),
                lambda v: v["diagnostics"][0]["source"].update(path="libs/native/.spec/bitz.yaml"),
                lambda v: v["revision"].update(dirty=False),
                lambda v: v.update(scope="changed"),
                lambda v: v["workspaces"].append({"id": "web", "path": "apps/web", "status": "passed",
                                                  "checkedDocumentCount": 1, "checkedStatementCount": 1,
                                                  "durationMs": 0, "diagnostics": []}),
            ],
        }
        manifest_changes = {
            "SINGLE-158": [
                lambda v: v["invocation"].update(cwd="."),
                lambda v: v["invocation"].update(cwd=".spec"),
                lambda v: v["invocation"]["argv"].remove("--full"),
                lambda v: v["setup"].update(operations=v["setup"]["operations"][:1]),
                lambda v: v["setup"].update(operations=v["setup"]["operations"][1:]),
                lambda v: v["setup"]["operations"].append({"op": "stage", "paths": ["."]}),
                lambda v: v["expect"].update(status="passed", exitCode=0),
            ],
            "MULTI-030-01": [
                lambda v: v["invocation"].update(cwd="."),
                lambda v: v["invocation"].update(cwd="services/api"),
                lambda v: v["invocation"]["argv"].remove("--full"),
                lambda v: v["setup"].update(operations=v["setup"]["operations"][:1]),
                lambda v: v["setup"].update(operations=v["setup"]["operations"][1:]),
                lambda v: v["expect"].update(status="passed", exitCode=0),
            ],
            "MULTI-030-02": [
                lambda v: v["invocation"].update(cwd="."),
                lambda v: v["invocation"].update(cwd="tools"),
                lambda v: v["invocation"]["argv"].remove("--all-workspaces"),
                lambda v: v["invocation"]["argv"].insert(1, "--full"),
                lambda v: v["setup"].update(operations=[]),
                lambda v: v["setup"]["operations"][0].update(path="apps/web/tools/.spec/bitz.yaml"),
                lambda v: v["expect"].update(status="passed", exitCode=0),
            ],
        }
        mutations = [(identifier, "expected/check.json", change)
                     for identifier, changes in result_changes.items() for change in changes]
        mutations += [(identifier, "manifest.json", change)
                      for identifier, changes in manifest_changes.items() for change in changes]
        mutations += [(identifier, "side-effects.json", lambda v: v["before"].update(git={"status": "", "index": ""}))
                      for identifier in repo_root_fixtures.CASES]
        for index, (identifier, relative, mutate) in enumerate(mutations):
            with self.subTest(index=index, identifier=identifier, file=relative), \
                    tempfile.TemporaryDirectory() as temporary:
                root = self.copy_repo_root_fixture(temporary, identifier)
                path = root / repo_root_fixtures.CASES[identifier][0] / identifier / relative
                value = json.loads(path.read_text())
                before = json.dumps(value, sort_keys=True)
                mutate(value)
                self.assertNotEqual(json.dumps(value, sort_keys=True), before)
                path.write_text(json.dumps(value))
                self.assertEqual(repo_root_fixtures.validate(root, {identifier})["status"], "Failed")

    def test_repo_root_audit_rejects_changed_corpus(self):
        """原因の構成は、基準版の`approved`のREQ 2件のうち、1件の`title`だけの変更と1件の削除、メンバーの外の未登録の設定1件である。入力を変えた写しは拒否する。"""
        module = repo_root_fixtures
        single_1, single_2 = "repo/.spec/requirements/REQ-001.md", "repo/.spec/requirements/REQ-002.md"
        web_10, web_11 = "repo/apps/web/.spec/requirements/REQ-010.md", "repo/apps/web/.spec/requirements/REQ-011.md"
        edits = [
            # 基準版の状態が`approved`でなければ、承認済み要求の保護の対象にならない。
            ("SINGLE-158", single_1, "status: approved", "status: draft"),
            ("SINGLE-158", single_2, "status: approved", "status: outdated"),
            # 変更後の状態を戻す（`draft`）と、保護の対象外になる。
            ("SINGLE-158", "changes/REQ-changed.md", "status: approved", "status: draft"),
            # `title`が変わらなければ、意味の変更がない。規範文を変えると2つ目の原因になる。
            ("SINGLE-158", "changes/REQ-changed.md", "変更後の文書検査", "文書の検査"),
            ("SINGLE-158", "changes/REQ-changed.md", "秘密情報を出力しない。", "ログを出力しない。"),
            # 強い関係を足すと、閉包や逆参照が加わる。
            ("SINGLE-158", single_2, "status: approved\n---", "status: approved\nrelations:\n  requires: [REQ-001]\n---"),
            ("SINGLE-158", single_2, "status: approved\n---", "status: approved\nrelations:\n  related: [REQ-001]\n---"),
            ("MULTI-030-01", web_10, "status: approved", "status: draft"),
            ("MULTI-030-01", web_11, "status: approved", "status: outdated"),
            ("MULTI-030-01", "changes/REQ-changed.md", "変更後の認証基準", "認証の基準"),
            ("MULTI-030-01", "changes/REQ-changed.md", "status: approved", "status: draft"),
            ("MULTI-030-01", "changes/REQ-changed.md", "秘密情報を出力しない。", "ログを出力しない。"),
            ("MULTI-030-01", web_11, "status: approved\n---", "status: approved\nrelations:\n  requires: [REQ-010]\n---"),
            # カタログに加えると未登録ではなくなる。メンバーの配下に置いても、メンバーの外の設定ではなくなる。
            ("MULTI-030-02", "repo/.spec/bitz.yaml", "      path: services/api\n", "      path: services/api\n    - id: x\n      path: tools/x\n"),
            ("MULTI-030-02", "repo/.spec/bitz.yaml", "path: services/api", "path: tools"),
            ("MULTI-030-02", "repo/.spec/bitz.yaml", "path: apps/web", "path: apps"),
        ]
        for index, (identifier, relative, old, new) in enumerate(edits):
            with self.subTest(index=index, identifier=identifier, file=relative), \
                    tempfile.TemporaryDirectory() as temporary:
                root = self.copy_repo_root_fixture(temporary, identifier)
                fixture = root / module.CASES[identifier][0] / identifier
                path = fixture / relative
                self.assertIn(old, path.read_text())
                path.write_text(path.read_text().replace(old, new))
                # 入力のバイト列の一致の検査が拒否する。
                self.assertEqual(module.validate(root, {identifier})["status"], "Failed")
                # 入力の一致の検査と別に、原因の構成の検査が、入力の木構造とGitの状態から拒否する。
                manifest = json.loads((fixture / "manifest.json").read_text())
                repository = fixture_setup(fixture, manifest, Path(temporary) / "work" / "repo")
                with self.assertRaises(ValueError):
                    module.check_conditions(identifier, repository)
        # 準備手順の結果（Gitの状態）の改変: 変更のステージ、実行するディレクトリの不在、余分な変更を拒否する。
        for identifier in ("SINGLE-158", "MULTI-030-01", "MULTI-030-02"):
            for variant in ("stage", "extra", "no-cwd"):
                with self.subTest(identifier=identifier, variant=variant), tempfile.TemporaryDirectory() as temporary:
                    root = self.copy_repo_root_fixture(temporary, identifier)
                    fixture = root / module.CASES[identifier][0] / identifier
                    manifest = json.loads((fixture / "manifest.json").read_text())
                    repository = fixture_setup(fixture, manifest, Path(temporary) / "work" / "repo")
                    module.check_conditions(identifier, repository)
                    if variant == "stage":
                        fixture_git(repository, "add", "-A")
                    elif variant == "extra":
                        (repository / "extra.txt").write_text("x")
                    else:
                        cwd = module.CASES[identifier][2]
                        fixture_git(repository, "rm", "-r", "-q", "--cached", "--", cwd)
                        fixture_git(repository, "commit", "-q", "-m", "drop")
                    with self.assertRaises(ValueError):
                        module.check_conditions(identifier, repository)
        # 入力の欠落と余分なファイルを拒否する。
        for identifier in module.CASES:
            for name in ("repo/.spec/bitz.yaml", "extra"):
                with self.subTest(identifier=identifier, file=name), tempfile.TemporaryDirectory() as temporary:
                    root = self.copy_repo_root_fixture(temporary, identifier)
                    fixture = root / module.CASES[identifier][0] / identifier
                    if name == "extra":
                        (fixture / "repo/extra.txt").write_text("x")
                    else:
                        (fixture / name).unlink()
                    self.assertEqual(module.validate(root, {identifier})["status"], "Failed")

    def test_multi_identity_audit_rejects_second_cause_in_the_corpus(self):
        """各種類は原因を1つだけ持つ。入力へ2つ目の原因を足した写しは受理しない。"""
        with tempfile.TemporaryDirectory() as temporary:
            root = self.copy_multi_fixture(temporary, "MULTI-003")
            path = root / "multi/MULTI-003/repo/apps/web/.spec/technical/TECH-010.md"
            path.write_bytes(path.read_bytes().replace(
                b"  refines: [REQ-001]\n",
                b"  refines: [REQ-001]\ntests:\n  - path: tests/missing.py\n    covers: [REQ-001:AC-01]\n"))
            result = multi_identity_fixtures.validate(root, {"MULTI-003"})
        self.assertEqual(result["status"], "Failed")

    def test_multi_catalog_fixtures(self):
        result = multi_catalog_fixtures.validate()
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["prepared"], list(multi_catalog_fixtures.CASES))
        self.assertEqual(result["core_execution"], "Not run")

    def test_multi_catalog_audit_rejects_partial_results_and_wrong_stops(self):
        mutations = [
            # 事前検査の非成功はメンバーの結果を作らない。
            ("MULTI-006", "expected/check.json",
             lambda v: v["workspaces"].append({"id": "web", "path": "apps/web", "status": "passed",
                                               "checkedDocumentCount": 1, "checkedStatementCount": 0,
                                               "durationMs": 0, "diagnostics": []})),
            ("MULTI-006", "expected/check.json", lambda v: v.update(status="failed")),
            ("MULTI-006", "expected/check.json",
             lambda v: v["diagnostics"][0]["source"].update(workspaceId="platform")),
            # Git不在は`warning`への縮退ではなく遮断とする。
            ("MULTI-019", "expected/doctor.json",
             lambda v: v["checks"][1].update(status="warning")),
            ("MULTI-019", "expected/doctor.json",
             lambda v: v["diagnostics"][0].update(code="SPEC-MULTI-PATH-001")),
            ("MULTI-007-01", "expected/doctor.json", lambda v: v.update(status="blocked")),
            ("MULTI-005", "manifest.json", lambda v: v["expect"].update(exitCode=1)),
            ("MULTI-005", "cli-output.json", lambda v: v.update(stderrLineCount=2)),
        ]
        for identifier, relative, mutate in mutations:
            with self.subTest(identifier=identifier, relative=relative), \
                    tempfile.TemporaryDirectory() as temporary:
                root = self.copy_multi_fixture(temporary, identifier)
                path = root / "multi" / identifier / relative
                value = json.loads(path.read_text())
                mutate(value)
                path.write_text(json.dumps(value))
                self.assertEqual(multi_catalog_fixtures.validate(root, {identifier})["status"], "Failed")

    def test_multi_catalog_audit_rejects_registered_or_flat_members(self):
        """入力が条件を満たさなくなった写しは、期待値が同じでも受理しない。"""
        with tempfile.TemporaryDirectory() as temporary:
            root = self.copy_multi_fixture(temporary, "MULTI-007-01")
            path = root / "multi/MULTI-007-01/repo/.spec/bitz.yaml"
            path.write_text(path.read_text().replace("apps/web/inner", "libs/inner"))
            (root / "multi/MULTI-007-01/repo/libs/inner/.spec").mkdir(parents=True)
            shutil.copy2(root / "multi/MULTI-007-01/repo/apps/web/inner/.spec/bitz.yaml",
                         root / "multi/MULTI-007-01/repo/libs/inner/.spec/bitz.yaml")
            shutil.rmtree(root / "multi/MULTI-007-01/repo/apps/web/inner")
            result = multi_catalog_fixtures.validate(root, {"MULTI-007-01"})
        self.assertEqual(result["status"], "Failed")

    def test_multi_doctor_fixtures(self):
        result = multi_doctor_fixtures.validate()
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["prepared"], list(multi_doctor_fixtures.CASES))
        self.assertEqual(result["core_execution"], "Not run")

    def test_multi_doctor_audit_rejects_member_omission_and_wrong_aggregation(self):
        mutations = [
            ("MULTI-026-01", "expected/doctor.json", lambda v: v["workspaces"].pop()),
            ("MULTI-026-01", "expected/doctor.json",
             lambda v: v["workspaces"][1].update(path="apps/api")),
            ("MULTI-026-02", "expected/doctor.json", lambda v: v.update(status="passed")),
            ("MULTI-026-02", "expected/doctor.json",
             lambda v: v["workspaces"][1]["diagnostics"][0].pop("suggestedAction")),
            ("MULTI-026-02", "expected/doctor.json",
             lambda v: v["workspaces"][1]["diagnostics"][0]["source"].update(workspaceId="platform")),
        ]
        for identifier, relative, mutate in mutations:
            with self.subTest(identifier=identifier, relative=relative), \
                    tempfile.TemporaryDirectory() as temporary:
                root = self.copy_multi_fixture(temporary, identifier)
                path = root / "multi" / identifier / relative
                value = json.loads(path.read_text())
                mutate(value)
                path.write_text(json.dumps(value))
                self.assertEqual(multi_doctor_fixtures.validate(root, {identifier})["status"], "Failed")
        with tempfile.TemporaryDirectory() as temporary:
            root = self.copy_multi_fixture(temporary, "MULTI-026-02")
            path = root / "multi/MULTI-026-02/expected/doctor.txt"
            path.write_text(path.read_text().replace("diagnostics=1", "diagnostics=0"))
            self.assertEqual(multi_doctor_fixtures.validate(root, {"MULTI-026-02"})["status"], "Failed")
        # テキストの`suggestedAction`の継続行（`  -> `）が欠けても拒否する。
        with tempfile.TemporaryDirectory() as temporary:
            root = self.copy_multi_fixture(temporary, "MULTI-026-02")
            path = root / "multi/MULTI-026-02/expected/doctor.txt"
            path.write_text("".join(line for line in path.read_text().splitlines(keepends=True)
                                    if not line.startswith("  -> ")))
            self.assertEqual(multi_doctor_fixtures.validate(root, {"MULTI-026-02"})["status"], "Failed")

    def test_multi_doctor_precheck_stop_audit_rejects_wrong_code_and_member_diagnostics(self):
        """`MULTI-033`: ルートのEARS-AIの非互換は`doctor`のコードで返し、メンバーの診断を開始しない（実装の確認事項C31）。"""
        mutations = [
            ("expected/doctor.json", lambda v: v["diagnostics"][0].update(code="SPEC-EARS-VERSION-001")),
            ("expected/doctor.json", lambda v: v["diagnostics"][0].pop("suggestedAction")),
            ("expected/doctor.json", lambda v: v["diagnostics"][0].update(suggestedAction="")),
            ("expected/doctor.json", lambda v: v["diagnostics"][0].update(summary="未対応のEARS-AI majorです")),
            ("expected/doctor.json", lambda v: v["diagnostics"][0]["source"].pop("key")),
            ("expected/doctor.json", lambda v: v["diagnostics"][0]["source"].update(workspaceId="web")),
            ("expected/doctor.json", lambda v: v["diagnostics"].append(dict(v["diagnostics"][0], code="SPEC-EARS-VERSION-001"))),
            ("expected/doctor.json", lambda v: v.update(diagnostics=[])),
            ("expected/doctor.json", lambda v: v["workspaces"].append(multi_doctor_fixtures.workspace("platform", "."))),
            ("expected/doctor.json", lambda v: v["workspaces"].extend([
                multi_doctor_fixtures.workspace("platform", "."), multi_doctor_fixtures.workspace("web", "apps/web")])),
            ("expected/doctor.json", lambda v: v["checks"][2].update(status="passed")),
            ("expected/doctor.json", lambda v: v["checks"].pop()),
            ("expected/doctor.json", lambda v: v["checks"][1].update(status="blocked")),
            ("expected/doctor.json", lambda v: v.update(status="passed")),
            ("expected/doctor.json", lambda v: v.update(status="failed")),
            ("manifest.json", lambda v: v["expect"].update(exitCode=1)),
            ("manifest.json", lambda v: v["expect"].update(exitCode=0, status="passed")),
            ("manifest.json", lambda v: v["invocation"].update(cwd="apps/web")),
            ("manifest.json", lambda v: v["invocation"]["argv"].remove("--all-workspaces")),
        ]
        for index, (relative, mutate) in enumerate(mutations):
            with self.subTest(relative=relative, index=index), \
                    tempfile.TemporaryDirectory() as temporary:
                root = self.copy_multi_fixture(temporary, "MULTI-033")
                path = root / "multi/MULTI-033" / relative
                value = json.loads(path.read_text())
                mutate(value)
                path.write_text(json.dumps(value))
                self.assertEqual(multi_doctor_fixtures.validate(root, {"MULTI-033"})["status"], "Failed")
        # 入力：`earsAi`が互換なら、診断を持つ期待値を受理しない。メンバー側が非互換になっても受理しない。
        for relative, old, new in ((".spec/bitz.yaml", 'earsAi: "2.0"', 'earsAi: "1.0"'),
                                   ("apps/web/.spec/bitz.yaml", 'earsAi: "1.0"', 'earsAi: "2.0"')):
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as temporary:
                root = self.copy_multi_fixture(temporary, "MULTI-033")
                path = root / "multi/MULTI-033/repo" / relative
                path.write_text(path.read_text().replace(old, new))
                self.assertEqual(multi_doctor_fixtures.validate(root, {"MULTI-033"})["status"], "Failed")

    def test_multi_doctor_reference_ears_precheck(self):
        """参照計算：ルートの設定の`earsAi`のメジャーバージョンだけから、`doctor`の診断を導く。互換なら診断なし（陰性対照）。"""
        root = (audit.FIXTURES / "multi/MULTI-033/repo/.spec/bitz.yaml").read_text()
        diagnostics = multi_doctor_fixtures.reference_ears_precheck(root)
        self.assertEqual([d["code"] for d in diagnostics], ["SPEC-DOCTOR-EARS-001"])
        for compatible in ("1.0", "1.9"):
            self.assertEqual(multi_doctor_fixtures.reference_ears_precheck(
                root.replace('earsAi: "2.0"', f'earsAi: "{compatible}"')), [])
        for incompatible in ("2.1", "3.0"):
            self.assertEqual(len(multi_doctor_fixtures.reference_ears_precheck(
                root.replace('earsAi: "2.0"', f'earsAi: "{incompatible}"'))), 1)

    def copy_doctor_plugin_fixture(self, temporary, identifier):
        multi = identifier in doctor_plugin_fixtures.MULTI
        return self.copy_multi_fixture(temporary, identifier) if multi else self.copy_fixture(temporary, identifier)

    def test_doctor_plugin_fixtures(self):
        result = doctor_plugin_fixtures.validate()
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["prepared"], doctor_plugin_fixtures.all_identifiers())
        self.assertEqual(result["core_execution"], "Not run")
        self.assertEqual(result["prepared"], [
            "SINGLE-160", "SINGLE-161", "SINGLE-162", "SINGLE-163",
            *[f"SINGLE-164-0{index}" for index in range(1, 9)], "MULTI-032"])

    def test_doctor_plugin_reference_lexicon_follows_adr_061(self):
        """字句の参照計算は、ADR-061 Decision 1の許可と拒否の両方の例を固定する（Coreの実装は使わない）。"""
        def errors(**options):
            argv = []
            for name, value in options.items():
                argv += ["--" + name.replace("_", "-"), value]
            return doctor_plugin_fixtures.reference_lexical_errors(argv)
        for value in ("bitz-sdd", "a", "a1", "a-b-c1", "a" * 64):
            self.assertEqual(errors(plugin=value), [], value)
        for value in ("Bitz", "1a", "-a", "a-", "a--b", "a_b", "a.b", "", "a" * 65, "a\n"):
            self.assertEqual(errors(plugin=value), ["--plugin"], repr(value))
        for value in ("0.0.0", "1.2.0", "10.20.30", "1.2.0-rc.1", "1.2.0+build.5", "1.2.0-rc.1+build.5", "1.0.0-0A.is.legal"):
            self.assertEqual(errors(plugin_version=value), [], value)
        for value in ("1.0", "v1.2.0", "01.2.0", "1.2.0-", "1.2.0+", "1.2.0-01", "1.2", "1.2.0.0", "", " 1.2.0", "1.2.0\n"):
            self.assertEqual(errors(plugin_version=value), ["--plugin-version"], repr(value))
        for value in ("^1.0", "1.0", "=1.0", ">=1.0", ">1.0", "<=1.0", "<2.0", ">=1.0 <2.0", "^0.0", ">=10.20 <=30.40"):
            self.assertEqual(errors(require_core_api=value), [], value)
        for value in ("~1.0", "1.x", "*", "^1.0.0", "1.0.0", ">= 1.0", ">=1.0  <2.0", " ^1.0", "^1.0 ", ">=1.0 || ^2.0",
                      "1.0 - 2.0", "^01.0", "=>1.0", "", "^1", ">=1.0\n"):
            self.assertEqual(errors(require_core_api=value), ["--require-core-api"], repr(value))
        for value in ("context.v1", "Context.v12", "a.v1"):
            self.assertEqual(errors(require_capability=value), [], value)
        for value in ("context.v0", "context", "context.v01", "1a.v1", "con-text.v1", "context.v1.v2", "", "context.V1", "context.v1\n"):
            self.assertEqual(errors(require_capability=value), ["--require-capability"], repr(value))

    def test_doctor_plugin_reference_range_semantics(self):
        satisfies, parse = doctor_plugin_fixtures.satisfies, doctor_plugin_fixtures.parse_range
        for text, expected in (("^1.0", True), ("^0.9", False), ("^2.0", False), ("=1.0", True), ("1.0", True), (">=1.0", True),
                               (">=1.1", False), (">1.0", False), ("<=1.0", True), ("<1.0", False), ("<2.0", True),
                               (">=1.0 <2.0", True), (">=1.0 <1.0", False), ("^1.0 >=1.1", False), ("<1.1", True)):
            self.assertEqual(satisfies((1, 0), parse(text)), expected, text)
        # 範囲のすべての比較子を満たすときだけ満たす。マイナーバージョンの差も範囲で判定する。
        self.assertTrue(satisfies((1, 3), parse("^1.0")))
        self.assertFalse(satisfies((1, 3), parse("^1.0 <1.3")))
        # 4300桁を超える値も、`int`へ変換せずに数値の大小で比べる。
        huge = "1" * 4301
        self.assertTrue(satisfies((1, 0), parse(f"<{huge}.0")))
        self.assertFalse(satisfies((1, 0), parse(f">={huge}.0")))
        self.assertFalse(satisfies((1, 0), parse(f"^1.{huge}")))
        self.assertTrue(satisfies((1, 10), parse(">1.9")))

    def test_doctor_plugin_reference_outcome_follows_adr_061(self):
        outcome = doctor_plugin_fixtures.reference_plugin_outcome
        self.assertEqual(outcome(["--format", "json"]), ([], []))
        self.assertEqual(outcome(["--all-workspaces", "--format", "json"]), ([], []))
        # 通過するときは診断を持たず、要求した対応機能が0件でも`capability`を置く。
        checks, diagnostics = outcome(doctor_plugin_fixtures.request(capabilities=()))
        self.assertEqual((checks, diagnostics), ([{"name": "plugin", "status": "passed"}, {"name": "capability", "status": "passed"}], []))
        # 検査2と検査3は独立で、両方不適合なら診断は`code`の辞書順に並ぶ。
        checks, diagnostics = outcome(doctor_plugin_fixtures.request(
            api="^2.0", capabilities=("verify.v2", "context.v9", "verify.v2", "check.v1")))
        self.assertEqual([c["status"] for c in checks], ["blocked", "blocked"])
        self.assertEqual([d["code"] for d in doctor_plugin_fixtures.sort_diagnostics(diagnostics[::-1])],
                         ["SPEC-DOCTOR-API-001", "SPEC-DOCTOR-CAPABILITY-001"])
        self.assertEqual(diagnostics[1]["evidence"], {"missing": ["context.v9", "verify.v2"]})
        # 組合せが不完全なら検査2と検査3を行わず、欠けたオプションを辞書順で示す。
        for kwargs, missing in (({"plugin": None}, ["--plugin"]),
                                ({"version": None}, ["--plugin-version"]),
                                ({"api": None}, ["--require-core-api"]),
                                ({"plugin": None, "version": None, "api": None},
                                 ["--plugin", "--plugin-version", "--require-core-api"])):
            checks, diagnostics = outcome(doctor_plugin_fixtures.request(**kwargs))
            self.assertEqual(checks, [{"name": "plugin", "status": "failed"}], kwargs)
            self.assertEqual(diagnostics[0]["evidence"], {"missing": missing}, kwargs)
            self.assertEqual(diagnostics[0]["source"].get("identifier"), None if "plugin" in kwargs else "bitz-sdd")
        # `--require-capability`だけを指定しても、要求の1つとして不完全になる。
        checks, _ = outcome(["--require-capability", "context.v1"])
        self.assertEqual(checks, [{"name": "plugin", "status": "failed"}])

    def test_doctor_plugin_lexical_fixtures_have_one_cause_and_no_result(self):
        for identifier, (option, argv, _) in doctor_plugin_fixtures.LEXICAL.items():
            fixture = audit.FIXTURES / "single" / identifier
            manifest = json.loads((fixture / "manifest.json").read_text())
            self.assertEqual(manifest["expect"], {"exitCode": 4, "stdout": "none", "reportFileCount": 0}, identifier)
            self.assertFalse((fixture / "expected").exists(), identifier)
            self.assertEqual(doctor_plugin_fixtures.reference_lexical_errors(manifest["invocation"]["argv"][1:]), [option], identifier)
            output = json.loads((fixture / "cli-output.json").read_text())
            self.assertEqual(output["stderrPrefix"], "bitz: doctor: ", identifier)
            self.assertEqual(output["stderrLineCount"], 1, identifier)
            self.assertFalse(output["stderrTerminalControls"], identifier)
        # 字句が正しい4件は、結果を返す。
        for identifier in doctor_plugin_fixtures.SINGLE:
            manifest = json.loads((audit.FIXTURES / "single" / identifier / "manifest.json").read_text())
            self.assertEqual(doctor_plugin_fixtures.reference_lexical_errors(manifest["invocation"]["argv"][1:]), [], identifier)
            self.assertNotEqual(manifest["expect"]["exitCode"], 4, identifier)

    def test_doctor_plugin_audit_rejects_tampered_fixtures(self):
        diag = lambda v: v["diagnostics"][0]
        mutations = [
            # 起動条件：オプションの削除、値の変更、操作の変更
            ("SINGLE-160", "manifest.json", lambda v: v["invocation"]["argv"].__delitem__(slice(1, 3))),
            ("SINGLE-160", "manifest.json", lambda v: v["invocation"]["argv"].remove("--require-core-api") or None),
            ("SINGLE-160", "manifest.json", lambda v: v["invocation"]["argv"].__setitem__(6, ">=1.1")),
            ("SINGLE-160", "manifest.json", lambda v: v["invocation"]["argv"].__setitem__(8, "context.v2")),
            ("SINGLE-160", "manifest.json", lambda v: v["invocation"]["argv"].__setitem__(2, "other-plugin")),
            ("SINGLE-160", "manifest.json", lambda v: v["expect"].update(status="blocked", exitCode=2)),
            ("SINGLE-161", "manifest.json", lambda v: v["invocation"]["argv"].__setitem__(6, "^1.0")),
            ("SINGLE-161", "manifest.json", lambda v: v["invocation"]["argv"].__setitem__(6, "^2.0")),
            ("SINGLE-161", "manifest.json", lambda v: v["expect"].update(status="failed", exitCode=1)),
            ("SINGLE-161", "manifest.json", lambda v: v["expect"].update(exitCode=3)),
            ("SINGLE-162", "manifest.json", lambda v: v["invocation"]["argv"].__setitem__(8, "context.v1")),
            ("SINGLE-162", "manifest.json", lambda v: v["invocation"].update(cwd="src")),
            ("SINGLE-163", "manifest.json", lambda v: v["invocation"]["argv"].__setitem__(1, "--plugin-version")),
            ("SINGLE-163", "manifest.json", lambda v: v["invocation"]["argv"].extend(["--require-core-api", "^1.0"])),
            ("SINGLE-163", "manifest.json", lambda v: v["expect"].update(status="blocked", exitCode=2)),
            # 期待結果：検査項目の欠落、順序、状態
            ("SINGLE-160", "expected/doctor.json", lambda v: v["checks"].pop(1)),
            ("SINGLE-160", "expected/doctor.json", lambda v: v["checks"].pop(2)),
            ("SINGLE-160", "expected/doctor.json", lambda v: v["checks"].insert(1, v["checks"].pop(2))),
            ("SINGLE-160", "expected/doctor.json", lambda v: v["checks"].append(v["checks"].pop(1))),
            ("SINGLE-160", "expected/doctor.json", lambda v: v["checks"][1].update(status="blocked")),
            ("SINGLE-160", "expected/doctor.json", lambda v: v["checks"].__setitem__(slice(1, 3), [])),
            ("SINGLE-160", "expected/doctor.json", lambda v: v.update(diagnostics=v["diagnostics"] + [{"code": "SPEC-DOCTOR-API-001"}])),
            ("SINGLE-160", "expected/doctor.json", lambda v: v.update(status="passed_with_warnings")),
            ("SINGLE-161", "expected/doctor.json", lambda v: v.update(diagnostics=[])),
            ("SINGLE-161", "expected/doctor.json", lambda v: v.update(status="passed")),
            ("SINGLE-161", "expected/doctor.json", lambda v: v.update(status="failed")),
            ("SINGLE-161", "expected/doctor.json", lambda v: v["checks"][1].update(status="passed")),
            ("SINGLE-161", "expected/doctor.json", lambda v: v["checks"][2].update(status="blocked")),
            ("SINGLE-161", "expected/doctor.json", lambda v: v["checks"].pop(2)),
            ("SINGLE-161", "expected/doctor.json", lambda v: diag(v).update(code="SPEC-DOCTOR-CAPABILITY-001")),
            ("SINGLE-161", "expected/doctor.json", lambda v: diag(v).update(resultStatus="failed")),
            ("SINGLE-161", "expected/doctor.json", lambda v: diag(v).update(severity="warning")),
            ("SINGLE-161", "expected/doctor.json", lambda v: diag(v)["evidence"].update(coreApi="1.1")),
            ("SINGLE-161", "expected/doctor.json", lambda v: diag(v).pop("suggestedAction")),
            ("SINGLE-161", "expected/doctor.json", lambda v: diag(v).update(
                suggestedAction="範囲^1.0を満たすCoreへ更新するか、Core APIのバージョン1.0に対応するプラグインを使ってください")),
            ("SINGLE-161", "expected/doctor.json", lambda v: diag(v)["evidence"].update(required="^1.0")),
            ("SINGLE-161", "expected/doctor.json", lambda v: diag(v).update(evidence=">=1.1")),
            ("SINGLE-161", "expected/doctor.json", lambda v: diag(v)["source"].update(identifier="other-plugin")),
            ("SINGLE-161", "expected/doctor.json", lambda v: diag(v)["source"].pop("identifier")),
            ("SINGLE-161", "expected/doctor.json", lambda v: diag(v)["source"].update(component="core")),
            ("SINGLE-161", "expected/doctor.json", lambda v: diag(v).update(
                source={"kind": "invocation", "argument": "--require-core-api"})),
            ("SINGLE-161", "expected/doctor.json", lambda v: v["diagnostics"].append(dict(diag(v)))),
            ("SINGLE-162", "expected/doctor.json", lambda v: v.update(diagnostics=[])),
            ("SINGLE-162", "expected/doctor.json", lambda v: v["checks"][1].update(status="blocked")),
            ("SINGLE-162", "expected/doctor.json", lambda v: v["checks"][2].update(status="passed")),
            ("SINGLE-162", "expected/doctor.json", lambda v: diag(v)["evidence"].update(missing=["context.v2", "check.v1"])),
            ("SINGLE-162", "expected/doctor.json", lambda v: diag(v)["evidence"].update(missing=[])),
            ("SINGLE-162", "expected/doctor.json", lambda v: diag(v).pop("suggestedAction")),
            ("SINGLE-162", "expected/doctor.json", lambda v: diag(v).update(code="SPEC-DOCTOR-API-001")),
            ("SINGLE-162", "expected/doctor.json", lambda v: diag(v).update(resultStatus="failed")),
            ("SINGLE-162", "expected/doctor.json", lambda v: v.update(status="failed")),
            ("SINGLE-162", "expected/doctor.json", lambda v: v["core"]["capabilities"].append("context.v2")),
            ("SINGLE-163", "expected/doctor.json", lambda v: v["checks"].insert(2, {"name": "capability", "status": "passed"})),
            ("SINGLE-163", "expected/doctor.json", lambda v: v["checks"][1].update(status="blocked")),
            ("SINGLE-163", "expected/doctor.json", lambda v: diag(v).update(code="SPEC-DOCTOR-API-001", resultStatus="blocked")),
            ("SINGLE-163", "expected/doctor.json", lambda v: diag(v)["evidence"].update(
                missing=["--require-core-api", "--plugin-version"])),
            ("SINGLE-163", "expected/doctor.json", lambda v: diag(v)["evidence"].update(missing=["--plugin-version"])),
            ("SINGLE-163", "expected/doctor.json", lambda v: diag(v).pop("suggestedAction")),
            ("SINGLE-163", "expected/doctor.json", lambda v: diag(v).update(
                summary="プラグインの要求が不完全です。--plugin、--plugin-version、--require-core-apiを同時に指定してください")),
            ("SINGLE-163", "expected/doctor.json", lambda v: diag(v)["source"].pop("identifier")),
            ("SINGLE-163", "expected/doctor.json", lambda v: v.update(status="blocked")),
            ("SINGLE-163", "expected/doctor.json", lambda v: v.update(diagnostics=[])),
            # 字句の不一致：結果の混入、引数の修復、終了コードの変更、標準エラー出力の契約
            *[(identifier, "manifest.json", lambda v: v["expect"].update(exitCode=1)) for identifier in doctor_plugin_fixtures.LEXICAL],
            *[(identifier, "manifest.json", lambda v: v["expect"].update(status="blocked", exitCode=2, stdout="json",
                                                                          resultFile="expected/doctor.json"))
              for identifier in doctor_plugin_fixtures.LEXICAL],
            *[(identifier, "cli-output.json", lambda v: v.update(stderrLineCount=2)) for identifier in doctor_plugin_fixtures.LEXICAL],
            *[(identifier, "cli-output.json", lambda v: v.update(stdout="{}")) for identifier in doctor_plugin_fixtures.LEXICAL],
            ("SINGLE-164-01", "manifest.json", lambda v: v["invocation"]["argv"].__setitem__(6, "^1.0")),
            ("SINGLE-164-02", "manifest.json", lambda v: v["invocation"]["argv"].__setitem__(2, "bitz-sdd")),
            ("SINGLE-164-03", "manifest.json", lambda v: v["invocation"]["argv"].__setitem__(8, "context.v1")),
            ("SINGLE-164-04", "manifest.json", lambda v: v["invocation"]["argv"].__setitem__(4, "1.0.0")),
            ("SINGLE-164-05", "manifest.json", lambda v: v["invocation"]["argv"].__setitem__(6, "^1.0")),
            ("SINGLE-164-06", "manifest.json", lambda v: v["invocation"]["argv"].__setitem__(6, ">=1.0 <2.0")),
            ("SINGLE-164-07", "manifest.json", lambda v: v["invocation"]["argv"].__setitem__(4, "1.2.0")),
            ("SINGLE-164-08", "manifest.json", lambda v: v["invocation"]["argv"].__setitem__(2, "a" * 64)),
            # 複合ワークスペース：複製、位置、状態
            ("MULTI-032", "manifest.json", lambda v: v["invocation"]["argv"].remove("--all-workspaces") or None),
            ("MULTI-032", "manifest.json", lambda v: v["invocation"]["argv"].__setitem__(7, "^1.0")),
            ("MULTI-032", "manifest.json", lambda v: v["invocation"].update(cwd=".")),
            ("MULTI-032", "manifest.json", lambda v: v["expect"].update(status="passed", exitCode=0)),
            ("MULTI-032", "manifest.json", lambda v: v["expect"].update(exitCode=1)),
            ("MULTI-032", "expected/doctor.json", lambda v: v["checks"].pop(1)),
            ("MULTI-032", "expected/doctor.json", lambda v: v["checks"].pop(2)),
            ("MULTI-032", "expected/doctor.json", lambda v: v["checks"].insert(1, v["checks"].pop(3))),
            ("MULTI-032", "expected/doctor.json", lambda v: v["checks"][1].update(status="passed")),
            ("MULTI-032", "expected/doctor.json", lambda v: v["checks"].append(dict(v["checks"][1]))),
            ("MULTI-032", "expected/doctor.json", lambda v: v.update(diagnostics=[])),
            ("MULTI-032", "expected/doctor.json", lambda v: v.update(status="passed")),
            ("MULTI-032", "expected/doctor.json", lambda v: v["diagnostics"].append(dict(v["diagnostics"][0]))),
            ("MULTI-032", "expected/doctor.json", lambda v: diag(v)["evidence"].update(required="^1.0")),
            ("MULTI-032", "expected/doctor.json", lambda v: diag(v).pop("suggestedAction")),
            ("MULTI-032", "expected/doctor.json", lambda v: diag(v)["source"].pop("identifier")),
            # メンバーへの複製：診断
            ("MULTI-032", "expected/doctor.json", lambda v: v["workspaces"][1]["diagnostics"].append(dict(diag(v)))),
            ("MULTI-032", "expected/doctor.json", lambda v: v["workspaces"][1].update(status="blocked")),
            # メンバーへの複製：検査項目
            ("MULTI-032", "expected/doctor.json", lambda v: v["workspaces"][0]["checks"].insert(0, dict(v["checks"][1]))),
            ("MULTI-032", "expected/doctor.json", lambda v: v["workspaces"][2]["checks"].insert(0, dict(v["checks"][2]))),
            ("MULTI-032", "expected/doctor.json", lambda v: v["workspaces"].pop()),
        ]
        # 陽性対照：コピーを改変しなければ受理する。改変した場合の拒否が、コピーの不備によるものではないことを示す。
        for identifier in doctor_plugin_fixtures.all_identifiers():
            with self.subTest(identifier=identifier, control="pristine"), tempfile.TemporaryDirectory() as temporary:
                root = self.copy_doctor_plugin_fixture(temporary, identifier)
                self.assertEqual(doctor_plugin_fixtures.validate(root, {identifier}),
                                 {"prepared": [identifier], "setups_per_fixture": 2, "core_execution": "Not run",
                                  "status": "Passed", "errors": []})
        for identifier, relative, mutate in mutations:
            with self.subTest(identifier=identifier, relative=relative), \
                    tempfile.TemporaryDirectory() as temporary:
                root = self.copy_doctor_plugin_fixture(temporary, identifier)
                path = root / ("multi" if identifier in doctor_plugin_fixtures.MULTI else "single") / identifier / relative
                value = json.loads(path.read_text())
                mutate(value)
                path.write_text(json.dumps(value))
                self.assertEqual(doctor_plugin_fixtures.validate(root, {identifier})["status"], "Failed")

    def test_doctor_plugin_reference_check_rejects_consistent_but_wrong_pairs(self):
        """期待結果をリテラルと同時に書き換えても、引数列からの参照計算とずれれば拒否する（リテラルへの依存を避ける）。"""
        base = {identifier: json.loads((audit.FIXTURES / ("multi" if identifier in doctor_plugin_fixtures.MULTI else "single")
                                        / identifier / "manifest.json").read_text())
                for identifier in doctor_plugin_fixtures.all_identifiers()}
        results = {identifier: json.loads((audit.FIXTURES / ("multi" if identifier in doctor_plugin_fixtures.MULTI else "single")
                                           / identifier / "expected/doctor.json").read_text())
                   for identifier in [*doctor_plugin_fixtures.SINGLE, *doctor_plugin_fixtures.MULTI]}
        for identifier in results:
            doctor_plugin_fixtures.check_reference(identifier, copy.deepcopy(base[identifier]), copy.deepcopy(results[identifier]))
        # 引数列だけを変えると、検査項目と診断がずれる。
        for identifier, index, value in (("SINGLE-160", 6, ">=1.1"), ("SINGLE-161", 6, "^1.0"), ("SINGLE-162", 8, "context.v1"),
                                         ("SINGLE-160", 8, "nope.v1"), ("MULTI-032", 7, "^1.0")):
            manifest = copy.deepcopy(base[identifier])
            manifest["invocation"]["argv"][index] = value
            with self.subTest(identifier=identifier, value=value), self.assertRaises(ValueError):
                doctor_plugin_fixtures.check_reference(identifier, manifest, copy.deepcopy(results[identifier]))
        # 結果だけを変えると、操作の状態が診断の最悪値とずれる。
        for identifier, mutate in (
                ("SINGLE-161", lambda v: v.update(status="failed")),
                ("SINGLE-163", lambda v: v.update(status="blocked")),
                ("MULTI-032", lambda v: v["workspaces"][0]["checks"].append({"name": "plugin", "status": "passed"}))):
            result = copy.deepcopy(results[identifier])
            mutate(result)
            with self.subTest(identifier=identifier), self.assertRaises(ValueError):
                doctor_plugin_fixtures.check_reference(identifier, copy.deepcopy(base[identifier]), result)
        # 字句の不一致のfixtureで、別のオプションも不一致にする、または不一致を直すと拒否する。
        manifest = copy.deepcopy(base["SINGLE-164-01"])
        manifest["invocation"]["argv"][2] = "Bad"
        with self.assertRaises(ValueError):
            doctor_plugin_fixtures.check_reference("SINGLE-164-01", manifest, None)
        manifest = copy.deepcopy(base["SINGLE-164-01"])
        manifest["invocation"]["argv"][6] = "^1.0"
        with self.assertRaises(ValueError):
            doctor_plugin_fixtures.check_reference("SINGLE-164-01", manifest, None)

    def test_multi_ownership_fixtures(self):
        result = multi_ownership_fixtures.validate()
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["prepared"], list(multi_ownership_fixtures.CASES))
        self.assertEqual(result["core_execution"], "Not run")

    def test_multi_ownership_audit_rejects_wrong_codes_and_relaxed_links(self):
        mutations = [
            # 所有境界の違反をTASK境界の診断コードへ置き換えない。
            ("MULTI-008", "expected/check.json",
             lambda v: v["workspaces"][2]["diagnostics"][0].update(code="SPEC-TASK-BOUNDARY-001")),
            ("MULTI-008", "expected/check.json",
             lambda v: v["workspaces"][2].update(status="passed")),
            ("MULTI-009", "expected/check.json",
             lambda v: v["diagnostics"][0]["source"].update(path="src/inside.py")),
            ("MULTI-009", "manifest.json", lambda v: v["setup"].update(operations=[])),
            ("MULTI-010", "expected/check.json",
             lambda v: v["diagnostics"][0].update(code="SPEC-TASK-BOUNDARY-001")),
        ]
        for identifier, relative, mutate in mutations:
            with self.subTest(identifier=identifier, relative=relative), \
                    tempfile.TemporaryDirectory() as temporary:
                root = self.copy_multi_fixture(temporary, identifier)
                path = root / "multi" / identifier / relative
                value = json.loads(path.read_text())
                mutate(value)
                path.write_text(json.dumps(value))
                self.assertEqual(multi_ownership_fixtures.validate(root, {identifier})["status"], "Failed")

    def test_multi_ownership_audit_rejects_inward_symlink(self):
        """所有境界のケースは、別のメンバーへ出るシンボリックリンクでなければ証拠にならない。"""
        with tempfile.TemporaryDirectory() as temporary:
            root = self.copy_multi_fixture(temporary, "MULTI-008")
            link = root / "multi/MULTI-008/repo/apps/web/src/shared.py"
            link.unlink()
            link.symlink_to("inside.py")
            result = multi_ownership_fixtures.validate(root, {"MULTI-008"})
        self.assertEqual(result["status"], "Failed")

    def test_multi_member_fixtures(self):
        result = multi_member_fixtures.validate()
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["prepared"], list(multi_member_fixtures.CASES))
        self.assertEqual(result["core_execution"], "Not run")

    def test_multi_member_audit_rejects_dropped_members_and_wrong_counts(self):
        mutations = [
            # 非成功のメンバーの後ろにあるメンバーの件数を落とさない。
            ("MULTI-011", "expected/check.json", lambda v: v["workspaces"][2].update(checkedDocumentCount=0)),
            ("MULTI-011", "expected/check.json", lambda v: v["workspaces"].pop()),
            ("MULTI-011", "expected/check.json", lambda v: v["workspaces"][1].update(status="blocked")),
            # パスの移動はIDの変更ではない。
            ("MULTI-017", "expected/check.json", lambda v: v["workspaces"][2].update(id="webui")),
            ("MULTI-017", "expected/check.json", lambda v: v.update(status="failed")),
            ("MULTI-018-01", "expected/check.json", lambda v: v.update(diagnostics=[])),
            ("MULTI-018-02", "expected/check.json",
             lambda v: v["diagnostics"][0]["source"].update(workspaceId="platform")),
        ]
        for identifier, relative, mutate in mutations:
            with self.subTest(identifier=identifier, relative=relative), \
                    tempfile.TemporaryDirectory() as temporary:
                root = self.copy_multi_fixture(temporary, identifier)
                path = root / "multi" / identifier / relative
                value = json.loads(path.read_text())
                mutate(value)
                path.write_text(json.dumps(value))
                self.assertEqual(multi_member_fixtures.validate(root, {identifier})["status"], "Failed")

    def test_multi_member_audit_rejects_unchanged_catalog(self):
        """IDの変更のケースは、パスを保ったままIDを変えた入力でなければ証拠にならない。"""
        with tempfile.TemporaryDirectory() as temporary:
            root = self.copy_multi_fixture(temporary, "MULTI-018-01")
            path = root / "multi/MULTI-018-01/changes/bitz.yaml"
            path.write_text(path.read_text().replace("webui", "web"))
            result = multi_member_fixtures.validate(root, {"MULTI-018-01"})
        self.assertEqual(result["status"], "Failed")

    def test_multi_verify_fixtures(self):
        result = multi_verify_fixtures.validate()
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["prepared"], list(multi_verify_fixtures.DESCRIPTIONS))
        self.assertEqual(result["references"], 2)
        self.assertEqual(result["core_execution"], "Not run")

    def test_multi_verify_shares_one_binding_between_two_contexts(self):
        result = multi_verify_fixtures.reviewed_result("MULTI-013")
        digests = {entry["contextDigest"] for workspace in result["workspaces"]
                   for entry in workspace["targetResults"]}
        commands = [command for workspace in result["workspaces"] for command in workspace["commands"]]
        self.assertEqual(len(digests), 2)
        self.assertEqual(len(commands), 1)
        self.assertEqual(commands[0]["bindingId"], "web::frontend")

    def test_multi_verify_audit_rejects_wrong_aggregation_and_bindings(self):
        mutations = [
            # 遮断された検証対象はハッシュ値もテスト割当ても持たない。
            ("MULTI-012", "expected/verify.json",
             lambda v: v["workspaces"][2]["targetResults"][0].update(bindingRefs=["web::frontend"])),
            ("MULTI-012", "expected/verify.json", lambda v: v.update(status="blocked")),
            ("MULTI-012", "expected/verify.json",
             lambda v: v["workspaces"][1]["targetResults"][0].update(status="blocked")),
            # 共有するテスト割当てを2回実行しない。
            ("MULTI-013", "expected/verify.json",
             lambda v: v["workspaces"][0].update(commands=v["workspaces"][1]["commands"])),
            ("MULTI-013", "expected/verify.json",
             lambda v: v["workspaces"][1]["targetResults"][0].update(
                 contextDigest=v["workspaces"][0]["targetResults"][0]["contextDigest"])),
            # 失敗したコマンドの後も独立したテスト割当てを実行する。
            ("MULTI-014", "expected/verify.json", lambda v: v["workspaces"][1].update(commands=[])),
            ("MULTI-015", "expected/verify.json", lambda v: v.update(status="passed")),
            ("MULTI-016", "expected/verify.json", lambda v: v.update(status="passed_with_warnings")),
            ("MULTI-016", "expected/verify.json", lambda v: v.update(diagnostics=[])),
        ]
        for identifier, relative, mutate in mutations:
            with self.subTest(identifier=identifier, relative=relative), \
                    tempfile.TemporaryDirectory() as temporary:
                root = self.copy_multi_fixture(temporary, identifier)
                path = root / "multi" / identifier / relative
                value = json.loads(path.read_text())
                mutate(value)
                path.write_text(json.dumps(value))
                self.assertEqual(multi_verify_fixtures.validate(root, {identifier})["status"], "Failed")

    def test_multi_verify_audit_rejects_resolvable_dependency(self):
        """依存遮断のケースは、依存先が`invalid`でなければ証拠にならない。"""
        with tempfile.TemporaryDirectory() as temporary:
            root = self.copy_multi_fixture(temporary, "MULTI-012")
            path = root / "multi/MULTI-012/repo/services/api/.spec/technical/TECH-020.md"
            path.write_text(path.read_text().replace("TECH-020:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 監査logを保持する",
                                                     "TECH-020:AC-02] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 監査logを保持する"))
            result = multi_verify_fixtures.validate(root, {"MULTI-012"})
        self.assertEqual(result["status"], "Failed")

    def test_multi_report_fixtures(self):
        result = multi_report_fixtures.validate()
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["prepared"], list(multi_report_fixtures.CASES))
        self.assertEqual(result["core_execution"], "Not run")

    def test_multi_report_audit_rejects_wrong_policy_and_changed_body(self):
        mutations = [
            # 既定の全体操作はファイルを作らない。
            ("MULTI-022-01", "side-effects.json",
             lambda v: v.update(policy="explicit-report", report={
                 "directory": ".spec/reports", "createdCount": 1,
                 "namePattern": multi_report_fixtures.NAME_PATTERN, "temporaryFilesRemaining": 0})),
            ("MULTI-022-02", "side-effects.json", lambda v: v["report"].update(createdCount=2)),
            ("MULTI-022-02", "side-effects.json", lambda v: v["report"].update(temporaryFilesRemaining=1)),
            ("MULTI-022-02", "side-effects.json", lambda v: v["report"].update(namePattern="^.*$")),
            ("MULTI-022-02", "manifest.json", lambda v: v["expect"].update(reportFileCount=0)),
            # レポートの有無で結果の本体は変わらない。
            ("MULTI-022-04", "expected/verify.json", lambda v: v["workspaces"][1].update(commands=[])),
        ]
        for identifier, relative, mutate in mutations:
            with self.subTest(identifier=identifier, relative=relative), \
                    tempfile.TemporaryDirectory() as temporary:
                root = self.copy_multi_fixture(temporary, identifier)
                path = root / "multi" / identifier / relative
                value = json.loads(path.read_text())
                mutate(value)
                path.write_text(json.dumps(value))
                self.assertEqual(multi_report_fixtures.validate(root, {identifier})["status"], "Failed")

    def test_multi_compat_fixtures(self):
        result = multi_compat_fixtures.validate()
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["prepared"], list(multi_compat_fixtures.CASES))
        self.assertEqual(result["core_execution"], "Not run")

    def test_multi_compat_audit_rejects_wrong_outcomes(self):
        mutations = [
            ("MULTI-023-01", "expected/consumer.json", lambda v: v.update(outcome="rejected")),
            ("MULTI-023-03", "manifest.json", lambda v: v["expect"].update(exitCode=0)),
            ("MULTI-024-01", "expected/migration.json", lambda v: v.update(outcome="accepted")),
            ("MULTI-024-03", "expected/migration.json", lambda v: v.update(outcome="passed")),
            ("MULTI-024-02", "manifest.json", lambda v: v["setup"].update(operations=[])),
        ]
        for identifier, relative, mutate in mutations:
            with self.subTest(identifier=identifier, relative=relative), \
                    tempfile.TemporaryDirectory() as temporary:
                root = self.copy_multi_fixture(temporary, identifier)
                path = root / "multi" / identifier / relative
                value = json.loads(path.read_text())
                mutate(value)
                path.write_text(json.dumps(value))
                self.assertEqual(multi_compat_fixtures.validate(root, {identifier})["status"], "Failed")

    def test_multi_compat_audit_rejects_complete_rollback_as_partial(self):
        """部分的なロールバックのケースは、修飾参照が残っていなければ証拠にならない。"""
        with tempfile.TemporaryDirectory() as temporary:
            root = self.copy_multi_fixture(temporary, "MULTI-024-03")
            path = root / "multi/MULTI-024-03/changes/tech.md"
            path.write_bytes(path.read_bytes().replace(b"platform::REQ-001:AC-01", b"REQ-001:AC-01"))
            result = multi_compat_fixtures.validate(root, {"MULTI-024-03"})
        self.assertEqual(result["status"], "Failed")

    def test_multi_limit_fixtures(self):
        result = multi_limit_fixtures.validate()
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["prepared"], list(multi_limit_fixtures.CASES))
        self.assertEqual(result["generated_profiles"], "reduced")
        self.assertEqual(result["core_execution"], "Not run")

    def test_multi_limit_matrix_covers_every_dimension(self):
        """8次元×（上限-1、上限、上限+1）を1件ずつ持つ。"""
        cases = multi_limit_fixtures.CASES
        self.assertEqual(len(cases), 24)
        for dimension, limit in multi_generator.LIMITS.items():
            values = sorted(value for name, (kind, value, _) in cases.items() if kind == dimension)
            self.assertEqual(values, [limit - 1, limit, limit + 1], dimension)

    def test_multi_generator_counts_only_the_targeted_dimension(self):
        """生成器の計数は生成計画を読まない。狙った以外の次元は上限内に収まる。"""
        for dimension in multi_generator.DIMENSIONS:
            value = max(5, multi_generator.LIMITS[dimension] // 1000)
            totals = multi_generator.count(multi_generator.emit(multi_generator.plan(dimension, value)))
            self.assertEqual(totals[dimension], value, dimension)
            for name, observed in totals.items():
                self.assertLessEqual(observed, multi_generator.LIMITS[name], (dimension, name))

    def test_multi_limit_audit_rejects_changed_datasets_and_digests(self):
        mutations = [
            ("MULTI-020-01", "dataset.json", lambda v: v.update(value=v["value"] - 1)),
            ("MULTI-020-01", "dataset.json", lambda v: v.update(crosses=True)),
            ("MULTI-021-01", "dataset.json", lambda v: v.update(crosses=False)),
            ("MULTI-021-01", "manifest.json",
             lambda v: v["expect"].update(resultDigest="sha256:" + "0" * 64)),
            ("MULTI-021-01", "manifest.json", lambda v: v["expect"].update(status="failed", exitCode=1)),
            ("MULTI-020-03", "manifest.json",
             lambda v: v["setup"]["generate"].update(dataset="missing.json")),
            ("MULTI-020-03", "side-effects.json", lambda v: v.update(policy="explicit-report")),
        ]
        for identifier, relative, mutate in mutations:
            with self.subTest(identifier=identifier, relative=relative), \
                    tempfile.TemporaryDirectory() as temporary:
                root = self.copy_multi_fixture(temporary, identifier)
                path = root / "multi" / identifier / relative
                value = json.loads(path.read_text())
                mutate(value)
                path.write_text(json.dumps(value))
                self.assertEqual(multi_limit_fixtures.validate(root, {identifier})["status"], "Failed")

    def test_multi_limit_audit_rejects_committed_input_tree(self):
        """生成fixtureは`repo/`と期待結果のファイルを持たない。"""
        with tempfile.TemporaryDirectory() as temporary:
            root = self.copy_multi_fixture(temporary, "MULTI-020-01")
            (root / "multi/MULTI-020-01/repo/.spec").mkdir(parents=True)
            (root / "multi/MULTI-020-01/repo/.spec/bitz.yaml").write_text("schemaVersion: \"1.0\"\n")
            result = multi_limit_fixtures.validate(root, {"MULTI-020-01"})
        self.assertEqual(result["status"], "Failed")

    def test_multi_single_verify_limit_fixtures(self):
        """`MULTI-041-01`〜`04`: 単独の`verify`が上限を実行計画の確定後に判定し、`verifyBindingCount`を優先することを固定する（確認事項C40、ADR-066）。"""
        module = multi_single_verify_limit_fixtures
        result = module.validate()
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["prepared"], [f"MULTI-041-{number:02d}" for number in range(1, 5)])
        self.assertEqual(result["prepared"], list(module.CASES))
        self.assertEqual(result["generated_profiles"], "reduced")
        self.assertEqual(result["core_execution"], "Not run")
        # 複製した状態でも通る（以降の拒否の試験が、複製の不備で空振りしていないことの陽性対照）。
        for identifier in module.CASES:
            with self.subTest(identifier=identifier), tempfile.TemporaryDirectory() as temporary:
                root = self.copy_multi_fixture(temporary, identifier)
                self.assertEqual(module.validate(root, {identifier})["errors"], [])

    def test_multi_single_verify_limit_audit_rejects_changed_fixtures(self):
        mutations = [
            # 優先の対象と同時に超える次元の宣言を、入力と期待結果からそらさない。
            ("MULTI-041-01", "dataset.json", lambda v: v.update(dimension="commandDefinitionCount")),
            ("MULTI-041-01", "dataset.json", lambda v: v.pop("companionDimensions")),
            ("MULTI-041-01", "dataset.json", lambda v: v["profile"].update(commands=10000)),
            ("MULTI-041-01", "manifest.json",
             lambda v: v["expect"].update(resultDigest="sha256:" + "0" * 64)),
            ("MULTI-041-01", "manifest.json", lambda v: v["invocation"]["argv"].pop(1)),
            ("MULTI-041-02", "dataset.json", lambda v: v["profile"].update(bindings=10001)),
            ("MULTI-041-02", "dataset.json", lambda v: v.update(crosses=False)),
            ("MULTI-041-02", "manifest.json", lambda v: v["expect"].update(status="passed", exitCode=0)),
            ("MULTI-041-03", "dataset.json", lambda v: v["profile"].update(commands=10001)),
            ("MULTI-041-03", "dataset.json", lambda v: v.update(value=10001, crosses=True)),
            ("MULTI-041-03", "manifest.json", lambda v: v["expect"].update(status="blocked", exitCode=2)),
            ("MULTI-041-04", "manifest.json", lambda v: v["expect"].update(exitCode=2)),
            ("MULTI-041-04", "manifest.json", lambda v: v["invocation"]["argv"].__setitem__(2, "web")),
            ("MULTI-041-04", "cli-output.json", lambda v: v.update(exitCode=2)),
            ("MULTI-041-04", "dataset.json", lambda v: v["profile"].update(commands=10000)),
            ("MULTI-041-03", "side-effects.json", lambda v: v.update(policy="explicit-report")),
        ]
        for identifier, relative, mutate in mutations:
            with self.subTest(identifier=identifier, relative=relative), \
                    tempfile.TemporaryDirectory() as temporary:
                root = self.copy_multi_fixture(temporary, identifier)
                path = root / "multi" / identifier / relative
                value = json.loads(path.read_text())
                mutate(value)
                path.write_text(json.dumps(value))
                self.assertEqual(multi_single_verify_limit_fixtures.validate(root, {identifier})["status"], "Failed")
        # 結果を返すfixtureが`repo/`や`cli-output.json`を持つことを拒否する。
        with tempfile.TemporaryDirectory() as temporary:
            root = self.copy_multi_fixture(temporary, "MULTI-041-01")
            (root / "multi/MULTI-041-01/repo").mkdir()
            self.assertEqual(multi_single_verify_limit_fixtures.validate(root, {"MULTI-041-01"})["status"], "Failed")
        with tempfile.TemporaryDirectory() as temporary:
            root = self.copy_multi_fixture(temporary, "MULTI-041-02")
            (root / "multi/MULTI-041-02/cli-output.json").write_text("{}")
            self.assertEqual(multi_single_verify_limit_fixtures.validate(root, {"MULTI-041-02"})["status"], "Failed")

    def test_multi_single_verify_limit_expected_results_follow_the_norm(self):
        """期待結果の根拠（複合ワークスペース仕様 §10、ADR-066）: 両方が超過なら`verifyBindingCount`、`commandDefinitionCount`だけならそれを報告する。"""
        module = multi_single_verify_limit_fixtures
        first = module.blocked_result("MULTI-041-01")
        second = module.blocked_result("MULTI-041-02")
        for body, dimension, summary in (
                (first, "verifyBindingCount", "テスト割当て数が上限10,000を超過しました"),
                (second, "commandDefinitionCount", "コマンド定義数が上限10,000を超過しました")):
            self.assertEqual(body["status"], "blocked")
            self.assertEqual(body["scope"], "selected")
            self.assertEqual(body["workspace"], {"id": "platform", "path": "."})
            # 上限の超過は部分的な結果へ進まない。
            self.assertEqual((body["targetResults"], body["commands"]), ([], []))
            self.assertEqual(len(body["diagnostics"]), 1)
            diagnostic = body["diagnostics"][0]
            self.assertEqual(diagnostic["code"], "SPEC-MULTI-LIMIT-001")
            self.assertEqual(diagnostic["resultStatus"], "blocked")
            self.assertEqual(diagnostic["summary"], summary)
            self.assertEqual(diagnostic["evidence"], {"dimension": dimension, "limit": 10000, "observedAtLeast": 10001})
        # 01は両方の次元が超過し、02は`commandDefinitionCount`だけが超過する（入力の側の前提）。
        datasets = {identifier: module.reviewed_dataset(identifier)["dimensions"] for identifier in module.CASES}
        self.assertEqual((datasets["MULTI-041-01"]["verifyBindingCount"], datasets["MULTI-041-01"]["commandDefinitionCount"]),
                         (10001, 10001))
        self.assertEqual((datasets["MULTI-041-02"]["verifyBindingCount"], datasets["MULTI-041-02"]["commandDefinitionCount"]),
                         (10000, 10001))
        self.assertEqual((datasets["MULTI-041-03"]["verifyBindingCount"], datasets["MULTI-041-03"]["commandDefinitionCount"]),
                         (10000, 10000))
        # 04は結果を返さず、引数不正（終了コード4）である。
        manifest = json.loads((audit.FIXTURES / "multi/MULTI-041-04/manifest.json").read_text())
        self.assertEqual(manifest["expect"], {"exitCode": 4, "stdout": "none", "reportFileCount": 0})
        self.assertNotIn("resultDigest", manifest["expect"])

    def test_multi_single_verify_limit_inputs_fit_the_ceilings_and_reach_the_limit_from_the_root(self):
        """入力は、入力の上限（設定64 KiB、フロントマター32 KiB）とコンテキストの閉包の既定の上限（20文書、128 KiB）に収まり、
        ルートの検証対象だけで実行計画が上限に届く（既存の`plan`は、ルートの分にしか届かない）。実寸で照合する。"""
        for identifier, case in multi_single_verify_limit_fixtures.CASES.items():
            profile = multi_single_verify_limit_fixtures.profile(identifier)
            entries = dict(multi_generator.emit(profile))
            targets = multi_generator.single_verify_targets(profile)
            reached = set()
            for target in targets:
                requirement = target.split("::")[1]
                size = len(entries[f".spec/requirements/{requirement}.md"])
                documents = 1
                for path, content in entries.items():
                    if "/.spec/technical/" in path and f"refines: [platform::{requirement}]" in content.decode():
                        documents += 1
                        size += len(content)
                        head = content.decode().partition("\n---\n")[0]
                        self.assertLessEqual(len(head.encode()), 32 * 1024, (identifier, path))
                        workspace = path.split("/.spec/", 1)[0].rsplit("/", 1)[-1]
                        reached.update((workspace, line[len("    command: "):])
                                       for line in head.split("\n") if line.startswith("    command: "))
                self.assertLessEqual(documents, 20, (identifier, target))
                self.assertLessEqual(size, 128 * 1024, (identifier, target))
            self.assertEqual(len(reached), case["bindings"], identifier)
            for path, content in entries.items():
                if path.endswith("bitz.yaml"):
                    self.assertLessEqual(len(content), 64 * 1024, (identifier, path))
            # 検証対象は、ルートの文書と同数で、位置引数に重複なく並ぶ。
            self.assertEqual(len(set(targets)), len(targets))
            self.assertEqual(targets, sorted(targets))
        # 対照: 既存の`plan`は割当てを全ワークスペースへ散らすので、ルートのTECHが持つ割当ては800件以下である。
        scattered = multi_generator.emit(multi_generator.plan("verifyBindingCount", 10001))
        root_bindings = {line for path, content in scattered if path.startswith(".spec/technical/")
                         for line in content.decode().split("\n") if line.startswith("    command: ")}
        self.assertLessEqual(len(root_bindings), multi_generator.COMMANDS_PER_WORKSPACE)

    def test_multi_single_verify_limit_generation_is_deterministic_across_hash_seeds(self):
        """生成と期待結果は、集合や辞書の反復順に依存しない（`PYTHONHASHSEED`を変えて2回）。"""
        script = (
            "import sys, tempfile\n"
            "from pathlib import Path\n"
            "sys.dont_write_bytecode = True\n"
            f"sys.path.insert(0, {str(audit.FIXTURES.parent)!r})\n"
            "from conformance import multi_generator, multi_single_verify_limit_fixtures as m\n"
            "from conformance.harness import tree_digest_bytes, write_generated\n"
            "from conformance.multi_limit_fixtures import canonical_digest\n"
            "entries = multi_generator.emit(multi_generator.single_verify_plan(400, 450, 'verifyBindingCount'))\n"
            "with tempfile.TemporaryDirectory() as t:\n"
            "    write_generated(entries, Path(t))\n"
            "    body = m.passed_result(entries, m.context_digests(entries, Path(t)))\n"
            "print(tree_digest_bytes(entries), canonical_digest(body))\n"
        )
        outputs = []
        for seed in ("1", "2"):
            outputs.append(subprocess.run([sys.executable, "-B", "-c", script], capture_output=True, text=True, check=True,
                                          env={**os.environ, "PYTHONHASHSEED": seed}).stdout)
        self.assertEqual(outputs[0], outputs[1])
        self.assertRegex(outputs[0], r"^sha256:[0-9a-f]{64} sha256:[0-9a-f]{64}\n$")

    def test_multi_single_verify_limit_harness_reproduces_result_digests(self):
        """超過側の`resultDigest`を、Coreを実行せずにharnessの手順（`normalize_result`の`durationMs`固定と正規JSON）で再現する。"""
        from conformance.runner import normalize_result

        for identifier in ("MULTI-041-01", "MULTI-041-02"):
            manifest = json.loads((audit.FIXTURES / "multi" / identifier / "manifest.json").read_text())
            body = multi_single_verify_limit_fixtures.blocked_result(identifier)
            normalized, warnings = normalize_result(body, zero_duration=True)
            self.assertEqual(warnings, [], identifier)
            digest = digest_reference.digest(digest_reference.canonical_bytes(normalized))
            self.assertEqual(digest, manifest["expect"]["resultDigest"], identifier)

    def test_harness_reproduces_generate_fixture_result_digest_for_crosses_cases(self):
        """`runner.py`の`resultDigest`の比較手順(`normalize_result(..., zero_duration=True)`を
        `digest_reference`で正規JSON化してSHA-256を取る)が、生成fixtureのレビュー済みの
        `resultDigest`を、Coreを実行せずに再現することを確かめる(適合fixture仕様3.4・3.5)。

        `crosses`側は`blocked_result(identifier)`だけから決まり実寸の生成を要らないため、
        8次元の全件を軽量に照合できる(実寸の生成の照合は`validate_scale.py`が行う)。
        """
        from conformance.runner import normalize_result

        for identifier, (dimension, value, crosses) in multi_limit_fixtures.CASES.items():
            if not crosses:
                continue
            manifest = json.loads((audit.FIXTURES / "multi" / identifier / "manifest.json").read_text())
            body = multi_limit_fixtures.blocked_result(identifier)
            normalized, warnings = normalize_result(body, zero_duration=True)
            self.assertEqual(warnings, [], identifier)
            digest = digest_reference.digest(digest_reference.canonical_bytes(normalized))
            self.assertEqual(digest, manifest["expect"]["resultDigest"], identifier)

    def test_harness_reproduces_generate_fixture_result_digest_for_member_boundary(self):
        """境界内(`passed`)の側も`memberCount`の次元(実寸の生成が軽い)で同じ手順を照合する。"""
        from conformance.runner import normalize_result

        for identifier in ("MULTI-020-01", "MULTI-020-02"):
            manifest = json.loads((audit.FIXTURES / "multi" / identifier / "manifest.json").read_text())
            dataset = json.loads((audit.FIXTURES / "multi" / identifier / "dataset.json").read_text())
            entries = multi_generator.generate(dataset)
            body = multi_limit_fixtures.passed_check_result(multi_generator.workspace_counts(entries))
            normalized, warnings = normalize_result(body, zero_duration=True)
            self.assertEqual(warnings, [], identifier)
            digest = digest_reference.digest(digest_reference.canonical_bytes(normalized))
            self.assertEqual(digest, manifest["expect"]["resultDigest"], identifier)

    def test_harness_reproduces_generate_fixture_state_digest(self):
        """`runner.py`の`stateDigest`の比較手順(観測した状態の正規JSONのSHA-256)が、
        生成fixtureのレビュー済みの`stateDigest`を、Coreを実行せずに再現することを確かめる(適合fixture仕様5)。
        """
        from conformance.runner import _state_digest
        from conformance.harness import setup as fixture_setup, tree_digest_bytes
        from conformance.initial_fixtures import observe

        for identifier in ("MULTI-020-01", "MULTI-021-01"):
            fixture = audit.FIXTURES / "multi" / identifier
            manifest = json.loads((fixture / "manifest.json").read_text())
            dataset = json.loads((fixture / "dataset.json").read_text())
            effects = json.loads((fixture / "side-effects.json").read_text())
            entries = multi_generator.generate(dataset)
            self.assertEqual(tree_digest_bytes(entries), manifest["setup"]["generate"]["treeDigest"], identifier)
            with tempfile.TemporaryDirectory() as temporary:
                sandbox = Path(temporary)
                repository = fixture_setup(fixture, manifest, sandbox / "repo", generated=entries)
                external = {name: sandbox / name for name in ("home", "cache", "temporary")}
                for path in external.values():
                    path.mkdir()
                state = observe(repository, external)
            self.assertEqual(_state_digest(state), effects["stateDigest"], identifier)

    def test_frontmatter_boundary_evidence(self):
        from conformance import frontmatter_boundary_fixtures as boundaries
        report = boundaries.validate()
        self.assertEqual(report["errors"], [])
        self.assertEqual(len(report["prepared"]), 24)
        self.assertEqual(report["core_execution"], "Not run")
        mutations = [
            ("SINGLE-116-01", "expected/check.json", lambda v: v.update(status="failed")),
            ("SINGLE-116-02", "expected/check.json", lambda v: v.update(checkedDocumentCount=1)),
            ("SINGLE-115-04", "expected/check.json", lambda v: v.update(checkedStatementCount=1)),
            ("SINGLE-117-01", "expected/check.json", lambda v: v["diagnostics"][0].update(code="SPEC-FM-SCHEMA-001")),
            ("SINGLE-120-04", "expected/check.json", lambda v: v["diagnostics"].append(v["diagnostics"][0])),
            ("SINGLE-119-03", "expected/check.json", lambda v: v["diagnostics"].clear()),
            ("SINGLE-119-04", "side-effects.json", lambda v: v["after"].update(cache={"index": {"kind": "directory"}})),
            # キーのタプルによる重複を受理へ戻す改変と、別のテスト対応を重複扱いにする改変を拒否する。
            ("SINGLE-118-02", "expected/check.json", lambda v: v.update(status="passed", diagnostics=[])),
            ("SINGLE-118-03", "expected/check.json", lambda v: v.update(checkedStatementCount=1)),
            # 空の`changes`を変更許可と取り違える改変、境界違反を文書のスキップとして数える改変を拒否する。
            ("SINGLE-120-01", "manifest.json", lambda v: v["invocation"]["argv"].__setitem__(1, "--full")),
            ("SINGLE-120-02", "expected/check.json", lambda v: v.update(checkedDocumentCount=0)),
            ("SINGLE-120-02", "expected/check.json", lambda v: v["diagnostics"][0]["source"].update(key="changes")),
            ("SINGLE-120-02", "side-effects.json", lambda v: v["after"]["git"].update(status="")),
        ]
        for identifier, relative, mutate in mutations:
            with self.subTest(identifier=identifier), tempfile.TemporaryDirectory() as temporary:
                root = self.copy_fixture(temporary, identifier)
                shutil.copy2(schema_path(audit.FIXTURES, "frontmatter"), root)
                path = root / "single" / identifier / relative
                value = json.loads(path.read_text()); mutate(value); path.write_text(json.dumps(value))
                self.assertTrue(boundaries.validate(root, [identifier])["errors"])
        with tempfile.TemporaryDirectory() as temporary:
            identifier = "SINGLE-116-02"
            root = self.copy_fixture(temporary, identifier)
            shutil.copy2(schema_path(audit.FIXTURES, "frontmatter"), root)
            path = root / "single" / identifier / "repo" / boundaries.spec_path(identifier)
            path.write_text(path.read_text().replace("界" * 121, "界" * 120))
            self.assertTrue(boundaries.validate(root, [identifier])["errors"])
        # `covers`の順序の入替えを同じ順序へ修復すると単一原因でなくなるため拒否する。
        with tempfile.TemporaryDirectory() as temporary:
            identifier = "SINGLE-118-02"
            root = self.copy_fixture(temporary, identifier)
            shutil.copy2(schema_path(audit.FIXTURES, "frontmatter"), root)
            path = root / "single" / identifier / "repo" / boundaries.spec_path(identifier)
            path.write_text(path.read_text().replace('["REQ-001:AC-02", "REQ-001:AC-01"]', '["REQ-001:AC-01", "REQ-001:AC-02"]'))
            self.assertTrue(boundaries.validate(root, [identifier])["errors"])
        # 変更の差分をインデックスへステージした状態は、未ステージの差分の期待と一致しないため拒否する。
        with tempfile.TemporaryDirectory() as temporary:
            identifier = "SINGLE-120-02"
            root = self.copy_fixture(temporary, identifier)
            shutil.copy2(schema_path(audit.FIXTURES, "frontmatter"), root)
            path = root / "single" / identifier / "manifest.json"
            value = json.loads(path.read_text())
            value["setup"]["operations"].append({"op": "stage", "paths": ["src/app.py"]})
            path.write_text(json.dumps(value))
            self.assertTrue(boundaries.validate(root, [identifier])["errors"])

    def test_side_effect_evidence(self):
        from conformance import side_effect_fixtures as effects
        report = effects.validate()
        self.assertEqual(report["errors"], [])
        self.assertEqual(len(report["prepared"]), 6)
        self.assertEqual(report["core_execution"], "Not run")

        def fixture_root(temporary, identifier):
            # 元のfixtureとの一致を検査するため、元のfixtureも一緒にコピーする。
            root = self.copy_fixture(temporary, identifier)
            source = effects.CASES[identifier][0]
            shutil.copytree(audit.FIXTURES / "single" / source, root / "single" / source, symlinks=True)
            return root

        mutations = [
            # 書込みの許容、外部の木構造の事前汚染、レポート要求の追加、件数の改変を拒否する。
            ("SINGLE-125-01", "side-effects.json", lambda v: v["after"]["cache"].update(index={"kind": "directory"})),
            ("SINGLE-125-02", "side-effects.json", lambda v: [v[k]["home"].update(lock={"kind": "directory"}) for k in ("before", "after")]),
            ("SINGLE-125-03", "manifest.json", lambda v: v["invocation"]["argv"].append("--report")),
            ("SINGLE-125-03", "manifest.json", lambda v: v["expect"].update(reportFileCount=1)),
            ("SINGLE-125-04", "manifest.json", lambda v: v["invocation"]["env"].update(HOME="/tmp")),
            ("SINGLE-125-04", "expected/verify.json", lambda v: v.update(status="failed")),
            ("SINGLE-125-05", "side-effects.json", lambda v: v["report"].update(temporaryFilesRemaining=1)),
            ("SINGLE-125-05", "side-effects.json", lambda v: v["report"].update(createdCount=2)),
            ("SINGLE-125-05", "side-effects.json", lambda v: v.update(policy="read-only")),
            # シンボリックリンクを辿って書く期待、シンボリックリンクを通常のディレクトリとする期待、レポート作成の許容を拒否する。
            ("SINGLE-125-06", "side-effects.json", lambda v: v["after"]["repository"].update({"report-store/new.json": v["after"]["repository"]["report-store/existing.json"]})),
            ("SINGLE-125-06", "side-effects.json", lambda v: [v[k]["repository"].update({".spec/reports": {"kind": "directory"}}) for k in ("before", "after")]),
            ("SINGLE-125-06", "manifest.json", lambda v: v["expect"].update(reportFileCount=1)),
            ("SINGLE-125-06", "expected/check.json", lambda v: v.update(status="failed")),
        ]
        for identifier, relative, mutate in mutations:
            with self.subTest(identifier=identifier, relative=relative), tempfile.TemporaryDirectory() as temporary:
                root = fixture_root(temporary, identifier)
                path = root / "single" / identifier / relative
                value = json.loads(path.read_text()); mutate(value); path.write_text(json.dumps(value))
                self.assertTrue(effects.validate(root, [identifier])["errors"])
        # 方針が`read-only`のケースへレポートのディレクトリを置く改変、`verify`のコマンドを書込みのコマンドへ替える改変を拒否する。
        for identifier, name, content in [
                ("SINGLE-125-03", ".spec/reports/existing.json", b"{}\n"),
                ("SINGLE-125-04", ".spec/bitz.yaml", None)]:
            with self.subTest(identifier=identifier, name=name), tempfile.TemporaryDirectory() as temporary:
                root = fixture_root(temporary, identifier)
                for base in (root / "single" / identifier / "repo", root / "single" / effects.CASES[identifier][0] / "repo"):
                    path = base / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    if content is None:
                        path.write_bytes(path.read_bytes().replace(b'"/bin/true"', b'"/usr/bin/touch"'))
                    else:
                        path.write_bytes(content)
                self.assertTrue(effects.validate(root, [identifier])["errors"])

    def test_verify_argv_evidence(self):
        from conformance import verify_argv_fixtures as argv
        report = argv.validate()
        self.assertEqual(report["errors"], [])
        self.assertEqual(len(report["prepared"]), 9)
        self.assertEqual(report["core_execution"], "Not run")
        mutations = [
            # 設定違反のキー・診断コード・停止の形の改変、実行ケースの環境・引数列・状態の改変を拒否する。
            ("SINGLE-126-01", "expected/verify.json", lambda v: v["diagnostics"][0]["source"].update(key="verify.commands.default.argv")),
            ("SINGLE-126-02", "expected/verify.json", lambda v: v["workspace"].update(id="root")),
            ("SINGLE-126-03", "expected/verify.json", lambda v: v["diagnostics"][0].update(code="SPEC-VERIFY-BLOCKED-001")),
            ("SINGLE-126-04", "expected/verify.json", lambda v: v["diagnostics"].append(v["diagnostics"][0])),
            ("SINGLE-126-05", "manifest.json", lambda v: v["expect"].update(exitCode=2)),
            ("SINGLE-126-07", "expected/verify.json", lambda v: v["commands"][0]["argv"].remove("")),
            ("SINGLE-126-09", "expected/verify.json", lambda v: v["targetResults"][0].update(bindingRefs=["root::default"])),
            ("SINGLE-126-09", "expected/verify.json", lambda v: v["targetResults"][0].update(diagnostics=v["diagnostics"])),
            ("SINGLE-126-10", "expected/verify.json", lambda v: v.update(status="error")),
            ("SINGLE-126-11", "manifest.json", lambda v: v["invocation"]["env"].pop("PWD")),
            ("SINGLE-126-11", "expected/verify.json", lambda v: v["commands"][0].update(argv=["./probe.awk", *v["commands"][0]["tests"]])),
        ]
        for identifier, relative, mutate in mutations:
            with self.subTest(identifier=identifier, relative=relative), tempfile.TemporaryDirectory() as temporary:
                root = self.copy_fixture(temporary, identifier)
                path = root / "single" / identifier / relative
                value = json.loads(path.read_text()); mutate(value); path.write_text(json.dumps(value))
                self.assertTrue(argv.validate(root, [identifier])["errors"])
        # 2つ目の違反を混ぜた設定は単一原因でなくなるため拒否する。
        self.assertEqual(argv.template_violations(["/bin/true", 42, "a\0b"]),
                         [argv.ARGV_KEY + "[1]", argv.ARGV_KEY + "[2]"])
        self.assertEqual(argv.template_violations(["x"] * 256), [])
        self.assertEqual(argv.template_violations(["a" * (32 * 1024)]), [])
        # 直接観測は、期待と異なる挙動のスクリプトを拒否する。
        broken = {
            "SINGLE-126-07": "#!/bin/sh\nexit 0\n",
            "SINGLE-126-10": "#!/bin/sh\nexit 0\n",
            "SINGLE-126-11": "#!/usr/bin/awk -f\nBEGIN { exit 0 }\n",
        }
        for identifier, script in broken.items():
            with self.subTest(identifier=identifier, script="broken"), tempfile.TemporaryDirectory() as temporary:
                repository = Path(temporary) / "repo"
                shutil.copytree(audit.FIXTURES / "single" / identifier / "repo", repository)
                (repository / argv.SCRIPTS[identifier][0]).write_text(script)
                with self.assertRaises(ValueError):
                    argv.observe_command(identifier, repository)

    def test_verify_stream_evidence(self):
        from conformance import verify_stream_fixtures as stream
        report = stream.validate()
        self.assertEqual(report["errors"], [])
        self.assertEqual(len(report["prepared"]), 5)
        mutations = [
            ("SINGLE-126-12", "expected/verify.json", lambda v: v["commands"][0].update(termination="signal")),
            ("SINGLE-126-13", "expected/verify.json", lambda v: v["commands"].pop()),
            ("SINGLE-126-13", "expected/verify.json", lambda v: v["targetResults"][0].update(bindingRefs=["root::alpha"])),
            ("SINGLE-126-14", "expected/verify.json", lambda v: v["commands"][0].update(stderrExcerpt="err\r\n")),
            ("SINGLE-126-15", "expected/verify.json", lambda v: v["commands"][0].update(stdoutExcerpt=v["commands"][0]["stdoutExcerpt"].replace("password=[REDACTED]", "password=hunter2"))),
            ("SINGLE-126-15", "manifest.json", lambda v: v["invocation"].update(env={})),
            ("SINGLE-126-16", "expected/verify.json", lambda v: v["commands"][0].update(stdoutTruncated=True)),
        ]
        for identifier, relative, mutate in mutations:
            with self.subTest(identifier=identifier, relative=relative), tempfile.TemporaryDirectory() as temporary:
                root = self.copy_fixture(temporary, identifier)
                path = root / "single" / identifier / relative
                value = json.loads(path.read_text()); mutate(value); path.write_text(json.dumps(value))
                self.assertTrue(stream.validate(root, [identifier])["errors"])
        # 参照変換の読みを固定する。
        self.assertEqual(stream.convert_controls(b"a\r\nb\rc\x1b\x7f\t"), "a\nb\nc\\u001b\\u007f\t")
        self.assertEqual(stream.redact("x password=abc\nAuthorization:q\n", {}), "x password=[REDACTED]\nAuthorization:[REDACTED]\n")
        self.assertEqual(stream.excerpt("\u3042" + "a" * (stream.LIMIT - 1)), "a" * (stream.LIMIT - 1))
        # `setsid`で子孫を逃がさないスクリプトはパイプがすぐ閉じるため拒否する。
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "repo"
            shutil.copytree(audit.FIXTURES / "single" / "SINGLE-126-12" / "repo", repository)
            path = repository / "bin/orphan.sh"
            path.write_text(path.read_text().replace("setsid sh -c 'trap \"\" TERM; ", "sh -c '"))
            with self.assertRaises(ValueError):
                stream.observe_command("SINGLE-126-12", repository)
        # 出力を変えたスクリプトは独立した変換の結果が期待と一致しないため拒否する。
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "repo"
            shutil.copytree(audit.FIXTURES / "single" / "SINGLE-126-14" / "repo", repository)
            path = repository / "bin/controls.sh"
            path.write_text(path.read_text().replace("\\033", "E"))
            with self.assertRaises(ValueError):
                stream.observe_command("SINGLE-126-14", repository)
        # 観測は実行環境を継承しない。値`1`の伏せ字化の対象となる名前の変数があっても期待する抜粋は変わらない。
        with patch.dict(stream.os.environ, {"HOST_AUTH_FLAG": "1", "HOST_TOKEN": "err"}):
            self.assertEqual(stream.validate(identifiers=["SINGLE-126-14"])["errors"], [])
            self.assertEqual(stream.observation_env({"A": "b"}), {"PATH": stream.os.environ.get("PATH", ""), "A": "b"})

    def test_verify_argv_limit_evidence(self):
        from conformance import verify_argv_limit_fixtures as limit
        report = limit.validate()
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["prepared"], ["SINGLE-126-08"])
        mutations = [
            # プロセスを生成した扱い、検証対象への診断の複製、テスト割当ての参照、発生元の種別の改変を拒否する。
            ("expected/verify.json", lambda v: v.update(commands=[{"bindingId": "root::default"}])),
            ("expected/verify.json", lambda v: v["targetResults"][0].update(diagnostics=v["diagnostics"])),
            ("expected/verify.json", lambda v: v["targetResults"][3].update(bindingRefs=["root::default"])),
            ("expected/verify.json", lambda v: v["diagnostics"][0].update(source={"kind": "environment", "component": "command", "identifier": "root::default"})),
            ("expected/verify.json", lambda v: v["targetResults"][5].update(contextDigest=v["targetResults"][6]["contextDigest"])),
            ("manifest.json", lambda v: v["invocation"]["argv"].insert(1, "TECH-001")),
        ]
        for relative, mutate in mutations:
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as temporary:
                root = self.copy_fixture(temporary, "SINGLE-126-08")
                path = root / "single" / "SINGLE-126-08" / relative
                value = json.loads(path.read_text()); mutate(value); path.write_text(json.dumps(value))
                self.assertTrue(limit.validate(root, ["SINGLE-126-08"])["errors"])
        # 1文書分のパスを削ると上限内へ戻るため、超過条件を満たさない入力として拒否する。
        inputs = limit.reviewed_inputs()
        limit.check_single_limit(inputs)
        inputs[".spec/technical/TECH-001.md"] = b"---\nid: TECH-001\n---\n"
        with self.assertRaisesRegex(ValueError, "バイト上限を超えていません"):
            limit.check_single_limit(inputs)

    def test_frontmatter_fixtures(self):
        result = frontmatter_fixtures.validate()
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["prepared"], ["SINGLE-081", "SINGLE-082", "SINGLE-084", "SINGLE-085", "SINGLE-086",
                                              "SINGLE-087-01", "SINGLE-087-02", "SINGLE-087-03", "SINGLE-087-04", "SINGLE-087-05", "SINGLE-088"])
        self.assertEqual(result["core_execution"], "Not run")

    def test_frontmatter_audit_rejects_changed_status_counts_and_input(self):
        mutations = [
            ("SINGLE-081", "expected/check.json", lambda v: v.update(checkedDocumentCount=0)),
            ("SINGLE-082", "expected/check.json", lambda v: v["diagnostics"].clear()),
            ("SINGLE-084", "expected/check.json", lambda v: v["diagnostics"][0].update(code="SPEC-FM-UNKNOWN-001")),
            ("SINGLE-085", "expected/check.json", lambda v: v.update(status="failed")),
            ("SINGLE-086", "expected/check.json", lambda v: v.update(checkedDocumentCount=1, checkedStatementCount=1)),
            ("SINGLE-087-05", "expected/check.json", lambda v: v["diagnostics"].append(copy.deepcopy(v["diagnostics"][0]))),
            ("SINGLE-088", "side-effects.json", lambda v: v["after"].update(cache={"index": {"kind": "directory"}})),
        ]
        for identifier, relative, mutate in mutations:
            with self.subTest(identifier=identifier), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                fixture = root / "single" / identifier
                shutil.copytree(audit.FIXTURES / "single" / identifier, fixture)
                for name in ("manifest", "result", "side-effects"):
                    shutil.copy2(schema_path(audit.FIXTURES, name), root)
                path = fixture / relative
                value = json.loads(path.read_text()); mutate(value); path.write_text(json.dumps(value))
                self.assertTrue(frontmatter_fixtures.validate(root, [identifier])["errors"])
        for identifier in frontmatter_fixtures.CASES:
            with self.subTest(repaired_input=identifier), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                fixture = root / "single" / identifier
                shutil.copytree(audit.FIXTURES / "single" / identifier, fixture)
                for name in ("manifest", "result", "side-effects"):
                    shutil.copy2(schema_path(audit.FIXTURES, name), root)
                # 唯一の入力条件を修復する。期待する診断を古いままにしても通過してはいけない。
                if identifier == "SINGLE-081":
                    path = fixture / "repo/.spec/bitz.yaml"
                    path.write_bytes(path.read_bytes()[3:])
                else:
                    (fixture / "repo" / frontmatter_fixtures.REQ_PATH).write_text(frontmatter_fixtures.DOCUMENT)
                self.assertTrue(frontmatter_fixtures.validate(root, [identifier])["errors"])

    def test_text_fixtures_and_json_parity(self):
        result = text_fixtures.validate()
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["prepared"], ["SINGLE-075-01", "SINGLE-075-02", "SINGLE-076", "SINGLE-077"])
        self.assertEqual(result["core_execution"], "Not run")
        for identifier, original in text_fixtures.CASES.items():
            counterpart = text_fixtures.reviewed_result(identifier)
            lines = text_fixtures.TEXT[identifier].splitlines()
            self.assertEqual(lines[0], f"check {counterpart['status']} scope={counterpart['scope']} "
                             f"targets={counterpart['checkedDocumentCount']} "
                             f"diagnostics={len(counterpart['diagnostics'])} (0ms)")
            self.assertEqual(len(lines), 1 + len(counterpart["diagnostics"]))

    def test_text_normalization_preserves_everything_except_duration(self):
        expected = text_fixtures.TEXT["SINGLE-075-02"].encode()
        normalize = text_fixtures.normalize_text
        self.assertEqual(normalize(expected), normalize(expected.replace(b"(0ms)", b"(123ms)")))
        for changed in (expected.replace(b"targets=3", b"targets=2"),
                        expected.replace(b"failed", b"passed"),
                        expected.replace(b"md:::", b"md:"), expected.rstrip(b"\n"),
                        expected.replace(b"(0ms)", b"(1.5ms)"),
                        expected.replace(b"(0ms)", "(１２ms)".encode())):
            self.assertNotEqual(normalize(expected), normalize(changed))

    def test_diagnostic_field_escaping_covers_control_boundaries(self):
        escape = text_fixtures.escape_field
        self.assertEqual(escape("\n\t\r\x1b\x7f\x85"), r"\u000a\u0009\u000d\u001b\u007f\u0085")
        for point in list(range(32)) + list(range(127, 160)):
            self.assertEqual(escape(chr(point)), "\\u" + format(point, "04x"))
        visible = " 空白\\u001b[31m日本語~\u00a0"
        self.assertEqual(escape(visible), visible)
        result = text_fixtures.reviewed_result("SINGLE-076")
        diagnostic = result["diagnostics"][0]
        self.assertIn("\x1b", diagnostic["source"]["path"])
        self.assertIn("\x1b", diagnostic["summary"])
        output = text_fixtures.TEXT["SINGLE-076"]
        self.assertIn(escape(diagnostic["source"]["path"]), output)
        self.assertIn(escape(diagnostic["summary"]), output)
        self.assertEqual(len(output.splitlines()), 2)
        self.assertFalse(any(ord(c) < 32 or 127 <= ord(c) <= 159 for c in output.replace("\n", "")))

    def test_text_audit_rejects_tampered_evidence(self):
        mutations = [("SINGLE-075-01", "manifest.json", lambda v: v["expect"].update(reportFileCount=1)),
                     ("SINGLE-077", "expected/check.json", lambda v: v["diagnostics"].reverse()),
                     ("SINGLE-077", "expected/check.json", lambda v: v["diagnostics"].pop()),
                     ("SINGLE-077", "expected/check.json", lambda v: v.update(checkedDocumentCount=3)),
                     ("SINGLE-075-02", "expected/check.json", lambda v: v.update(status="passed")),
                     ("SINGLE-075-01", "side-effects.json", lambda v: v["after"].update(cache={"new": {"kind": "directory"}}))]
        for identifier, relative, mutate in mutations:
            with self.subTest(identifier=identifier, relative=relative), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                fixture = root / "single" / identifier
                shutil.copytree(audit.FIXTURES / "single" / identifier, fixture)
                for name in ("manifest", "result", "side-effects"):
                    shutil.copy2(schema_path(audit.FIXTURES, name), root)
                path = fixture / relative
                value = json.loads(path.read_text())
                mutate(value)
                path.write_text(json.dumps(value))
                self.assertTrue(text_fixtures.validate(root, [identifier])["errors"])
        for replacement in ("targets=2", "diagnostics=0"):
            with self.subTest(replacement=replacement), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                fixture = root / "single/SINGLE-075-02"
                shutil.copytree(audit.FIXTURES / "single/SINGLE-075-02", fixture)
                for name in ("manifest", "result", "side-effects"):
                    shutil.copy2(schema_path(audit.FIXTURES, name), root)
                path = fixture / "expected/check.txt"
                path.write_text(path.read_text().replace("targets=3" if replacement.startswith("targets") else "diagnostics=1", replacement))
                self.assertTrue(text_fixtures.validate(root, ["SINGLE-075-02"])["errors"])

    def test_report_write_fixtures(self):
        result = validate_report_write()
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["prepared"], ["SINGLE-071-01", "SINGLE-071-02", "SINGLE-071-03",
                                              "SINGLE-071-04", "SINGLE-072", "SINGLE-127-12"])
        self.assertEqual(result["core_execution"], "Not run")

    def test_explicit_report_creates_exactly_one_file(self):
        for identifier in ("SINGLE-071-01", "SINGLE-071-02", "SINGLE-071-03", "SINGLE-071-04", "SINGLE-127-12"):
            fixture = audit.FIXTURES / "single" / identifier
            manifest = json.loads((fixture / "manifest.json").read_text())
            effects = json.loads((fixture / "side-effects.json").read_text())
            self.assertIn("--report", manifest["invocation"]["argv"], identifier)
            self.assertEqual(manifest["expect"]["reportFileCount"], 1, identifier)
            self.assertEqual(effects["policy"], "explicit-report", identifier)
            self.assertEqual(effects["report"]["createdCount"], 1, identifier)
            self.assertEqual(effects["report"]["temporaryFilesRemaining"], 0, identifier)
            # 既存のレポートは、置換ではなく排他的な作成であることを示す。
            self.assertIn(report_write_fixtures.EXISTING_REPORT,
                          effects["before"]["repository"], identifier)
            self.assertEqual(effects["before"], effects["after"], identifier)

    def test_report_name_pattern_matches_the_specified_grammar(self):
        pattern = report_write_fixtures.NAME_PATTERN
        for name in ("20000101T000000Z-check.json", "20260914T112233Z-verify-2.json"):
            self.assertRegex(name, pattern)
        for name in ("check.json", "20000101T000000Z-check-0.json", "20000101T000000Z-context.json",
                     "20000101T000000Z-check.json.tmp", "20000101T00000Z-check.json"):
            self.assertNotRegex(name, pattern)

    def test_blocked_report_keeps_the_original_result(self):
        result = json.loads((audit.FIXTURES / "single/SINGLE-072/expected/check.json").read_text())
        source = json.loads((audit.FIXTURES / "single/SINGLE-070-02/expected/check.json").read_text())
        self.assertEqual(result["status"], "error")
        self.assertEqual(source["status"], "failed")
        for key in ("scope", "revision", "checkedDocumentCount", "checkedStatementCount"):
            self.assertEqual(result[key], source[key], key)
        # 保存の失敗は末尾ではなく、結果・診断・終了コード §7の順序（発生元のpathの辞書順）に入る（C51）。
        self.assertEqual([d["code"] for d in result["diagnostics"]],
                         ["SPEC-REPORT-WRITE-001"] + [d["code"] for d in source["diagnostics"]])
        self.assertEqual([d["source"]["path"] for d in result["diagnostics"]],
                         sorted(d["source"]["path"] for d in result["diagnostics"]))
        effects = json.loads((audit.FIXTURES / "single/SINGLE-072/side-effects.json").read_text())
        self.assertEqual(effects["policy"], "read-only")
        self.assertNotIn("report", effects)

    def test_side_effects_schema_pairs_policy_with_report(self):
        schema = json.loads((audit.FIXTURES / "side-effects.schema.json").read_text())
        validator = Draft202012Validator(schema)
        base = json.loads((audit.FIXTURES / "single/SINGLE-071-01/side-effects.json").read_text())
        validator.validate(base)
        missing = copy.deepcopy(base)
        missing.pop("report")
        with self.assertRaises(ValidationError):
            validator.validate(missing)
        surplus = copy.deepcopy(base)
        surplus["policy"] = "read-only"
        with self.assertRaises(ValidationError):
            validator.validate(surplus)
        zero = copy.deepcopy(base)
        zero["report"]["createdCount"] = 0
        with self.assertRaises(ValidationError):
            validator.validate(zero)
        leftover = copy.deepcopy(base)
        leftover["report"]["temporaryFilesRemaining"] = 1
        with self.assertRaises(ValidationError):
            validator.validate(leftover)

    def test_report_write_audit_rejects_tampered_expectations(self):
        mutations = [
            ("SINGLE-071-01", "manifest.json", lambda v: v["expect"].update(reportFileCount=0)),
            ("SINGLE-071-01", "manifest.json",
             lambda v: v["invocation"].update(argv=["check", "--full", "--base", "HEAD",
                                                    "--format", "json"])),
            ("SINGLE-071-02", "side-effects.json", lambda v: v["report"].update(createdCount=2)),
            ("SINGLE-071-03", "side-effects.json",
             lambda v: v["report"].update(namePattern="^.*$")),
            ("SINGLE-071-04", "side-effects.json",
             lambda v: v["before"]["repository"].pop(report_write_fixtures.EXISTING_REPORT)),
            ("SINGLE-072", "expected/check.json", lambda v: v.update(status="failed")),
            ("SINGLE-072", "expected/check.json", lambda v: v.update(diagnostics=v["diagnostics"][1:])),
            # 診断を逆順にした期待値は、レビュー済みの期待値との完全一致の比較で拒否される（§7の検査には届かない。下の専用の試験を参照）。
            ("SINGLE-072", "expected/check.json", lambda v: v.update(diagnostics=v["diagnostics"][::-1])),
            ("SINGLE-072", "expected/check.json", lambda v: v.update(checkedDocumentCount=0)),
        ]
        for identifier, relative, mutate in mutations:
            with self.subTest(identifier=identifier, relative=relative), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                fixture = root / "single" / identifier
                shutil.copytree(audit.FIXTURES / "single" / identifier, fixture)
                for name in ("manifest", "result", "side-effects", "frontmatter"):
                    shutil.copy2(schema_path(audit.FIXTURES, name), root)
                path = fixture / relative
                value = json.loads(path.read_text())
                mutate(value)
                path.write_text(json.dumps(value))
                self.assertTrue(validate_report_write(root, [identifier])["errors"])

    def test_report_write_audit_requires_section7_order_independently_of_the_reviewed_result(self):
        """生成器と期待値がそろって旧い並び（保存の失敗が末尾）でも、§7の検査が文言つきで拒否する（C51）。

        完全一致の比較（`result != reviewed_result`）は、期待値が生成器と一致すれば通る。
        その先の`check_report_contract`の§7の検査に届くよう、`reviewed_result`を差し替える。
        """
        original = report_write_fixtures.reviewed_result
        section7_message = "診断は結果・診断・終了コード §7の順序で並べる必要があります"

        def old_order(identifier):
            result = original(identifier)
            if identifier == "SINGLE-072":
                result["diagnostics"] = result["diagnostics"][::-1]
            return result

        for identifier in ("SINGLE-072",):
            with self.subTest(identifier=identifier), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                fixture = root / "single" / identifier
                shutil.copytree(audit.FIXTURES / "single" / identifier, fixture)
                for name in ("manifest", "result", "side-effects", "frontmatter"):
                    shutil.copy2(schema_path(audit.FIXTURES, name), root)
                path = fixture / "expected/check.json"
                value = json.loads(path.read_text())
                value["diagnostics"].reverse()
                path.write_text(json.dumps(value))
                # 陰性対照: 期待値だけが旧い並びなら、完全一致の比較が先に拒否する。
                errors = validate_report_write(root, [identifier])["errors"]
                self.assertEqual(len(errors), 1)
                self.assertIn("起動条件または完全結果がレビュー済みの期待値と異なります", errors[0])
                # 生成器も旧い並びにそろえると、完全一致は通り、§7の検査が拒否する。
                with patch.object(report_write_fixtures, "reviewed_result", old_order):
                    errors = validate_report_write(root, [identifier])["errors"]
                self.assertEqual(len(errors), 1)
                self.assertEqual(errors[0], f"{identifier}: {section7_message}")
        # 陽性対照: 現在の期待値と生成器では、§7の検査を通る。
        self.assertEqual(validate_report_write(audit.FIXTURES, ["SINGLE-072"])["errors"], [])

    def test_report_absent_and_cli_error_fixtures(self):
        absent = validate_report_absent()
        self.assertEqual(absent["errors"], [])
        self.assertEqual(absent["prepared"], ["SINGLE-070-01", "SINGLE-070-02",
                                              "SINGLE-070-03", "SINGLE-070-04"])
        errors = validate_cli_errors()
        self.assertEqual(errors["errors"], [])
        self.assertEqual(errors["prepared"], ["SINGLE-073-01", "SINGLE-073-02", "SINGLE-074-01",
                                              "SINGLE-074-02", "SINGLE-074-03",
                                              "SINGLE-112-02", "SINGLE-112-04",
                                              "SINGLE-127-01", "SINGLE-127-02", "SINGLE-127-05",
                                              "SINGLE-127-06", "SINGLE-127-07", "SINGLE-127-08",
                                              "SINGLE-127-09", "SINGLE-127-10", "SINGLE-127-11", "SINGLE-127-14"])
        for result in (absent, errors):
            self.assertEqual(result["core_execution"], "Not run")

    def test_no_report_run_leaves_the_existing_report_untouched(self):
        for identifier in report_absent_fixtures.CASES:
            fixture = audit.FIXTURES / "single" / identifier
            manifest = json.loads((fixture / "manifest.json").read_text())
            effects = json.loads((fixture / "side-effects.json").read_text())
            report_absent_fixtures.check_report_expectation(manifest, effects)
            self.assertNotIn("--report", manifest["invocation"]["argv"], identifier)
            self.assertEqual(manifest["expect"]["reportFileCount"], 0, identifier)
            self.assertIn(report_absent_fixtures.EXISTING_REPORT,
                          effects["before"]["repository"], identifier)

    def test_argument_errors_carry_no_result_and_no_report(self):
        for identifier, (operation, _, _) in cli_error_fixtures.CASES.items():
            fixture = audit.FIXTURES / "single" / identifier
            manifest = json.loads((fixture / "manifest.json").read_text())
            self.assertEqual(manifest["expect"],
                             {"exitCode": 4, "stdout": "none", "reportFileCount": 0}, identifier)
            self.assertFalse((fixture / "expected").exists(), identifier)
            output = json.loads((fixture / "cli-output.json").read_text())
            self.assertEqual(output["stderrPrefix"], "bitz: " + operation + ": ", identifier)
            self.assertEqual(output["stderrLineCount"], 1, identifier)
            self.assertFalse(output["stderrTerminalControls"], identifier)

    def test_shared_stderr_contract_is_operation_aware(self):
        for operation in ("context", "doctor", "check", "verify"):
            check_cli_error_output(4, b"", ("bitz: " + operation + ": reason" + chr(10)).encode(), operation)
            with self.assertRaises(ValueError):
                check_cli_error_output(4, b"", ("bitz: other: reason" + chr(10)).encode(), operation)
            with self.assertRaises(ValueError):
                check_cli_error_output(4, b"", ("bitz: " + operation + ": " + chr(10)).encode(), operation)
            with self.assertRaises(ValueError):
                check_cli_error_output(0, b"", ("bitz: " + operation + ": reason" + chr(10)).encode(), operation)

    def test_report_group_audit_rejects_tampered_expectations(self):
        mutations = [
            (validate_report_absent, "SINGLE-070-01", "manifest.json",
             lambda v: v["expect"].update(reportFileCount=1)),
            (validate_report_absent, "SINGLE-070-01", "manifest.json",
             lambda v: v["invocation"]["argv"].append("--report")),
            (validate_report_absent, "SINGLE-070-02", "expected/check.json",
             lambda v: v.update(status="passed", diagnostics=[])),
            (validate_report_absent, "SINGLE-070-02", "expected/check.json",
             lambda v: v.update(checkedDocumentCount=1)),
            (validate_report_absent, "SINGLE-070-03", "expected/verify.json",
             lambda v: v.update(status="failed")),
            (validate_report_absent, "SINGLE-070-04", "side-effects.json",
             lambda v: v["after"]["repository"].pop(report_absent_fixtures.EXISTING_REPORT)),
            (validate_cli_errors, "SINGLE-073-01", "manifest.json",
             lambda v: v["expect"].update(status="failed")),
            (validate_cli_errors, "SINGLE-073-02", "cli-output.json",
             lambda v: v.update(stderrPrefix="bitz: check: ")),
            (validate_cli_errors, "SINGLE-074-01", "cli-output.json",
             lambda v: v.update(stderrLineCount=2)),
            (validate_cli_errors, "SINGLE-074-02", "manifest.json",
             lambda v: v["invocation"].update(argv=["verify", "REQ-001", "--format", "json"])),
            # ADRの起点を`interpret`へ戻すと妥当な起点になり、引数不正ではなくなる。
            (validate_cli_errors, "SINGLE-112-02", "manifest.json",
             lambda v: v["invocation"]["argv"].__setitem__(3, "interpret")),
            (validate_cli_errors, "SINGLE-112-04", "manifest.json",
             lambda v: v["invocation"]["argv"].__setitem__(1, "REQ-001")),
            (validate_cli_errors, "SINGLE-127-01", "manifest.json",
             lambda v: v["invocation"].update(argv=["check", "--format", "json"])),
            (validate_cli_errors, "SINGLE-127-02", "manifest.json",
             lambda v: v["invocation"]["argv"].remove("--full")),
            (validate_cli_errors, "SINGLE-127-05", "manifest.json",
             lambda v: v["invocation"]["argv"].remove("")),
            (validate_cli_errors, "SINGLE-127-06", "manifest.json",
             lambda v: v["invocation"]["argv"].append("REQ-001")),
            (validate_cli_errors, "SINGLE-127-07", "manifest.json",
             lambda v: v["invocation"]["argv"].__setitem__(2, "root")),
            (validate_cli_errors, "SINGLE-127-08", "manifest.json",
             lambda v: v["invocation"]["argv"].__setitem__(3, "1")),
            (validate_cli_errors, "SINGLE-127-09", "manifest.json",
             lambda v: v["invocation"]["argv"].__setitem__(3, "3600")),
            (validate_cli_errors, "SINGLE-127-10", "manifest.json",
             lambda v: v["invocation"]["argv"].__setitem__(3, "1")),
            (validate_cli_errors, "SINGLE-127-11", "side-effects.json",
             lambda v: v["after"]["repository"].update({"out.json": {"kind": "directory"}})),
            (validate_cli_errors, "SINGLE-127-14", "manifest.json",
             lambda v: v["invocation"]["argv"].__setitem__(2, "root")),
            (validate_cli_errors, "SINGLE-127-14", "manifest.json",
             lambda v: v["expect"].update(status="failed", exitCode=1)),
        ]
        for validator, identifier, relative, mutate in mutations:
            with self.subTest(identifier=identifier, relative=relative), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                fixture = root / "single" / identifier
                shutil.copytree(audit.FIXTURES / "single" / identifier, fixture)
                for name in ("manifest", "result", "side-effects", "frontmatter"):
                    shutil.copy2(schema_path(audit.FIXTURES, name), root)
                path = fixture / relative
                value = json.loads(path.read_text())
                mutate(value)
                path.write_text(json.dumps(value))
                self.assertTrue(validator(root, [identifier])["errors"])

    def test_verify_task_root_fixture(self):
        result = validate_verify_task_root()
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["prepared"], ["SINGLE-068", "SINGLE-137", "SINGLE-138", "SINGLE-146", "SINGLE-149"])
        self.assertEqual(result["core_execution"], "Not run")

    def test_done_task_root_is_reverifiable_and_cancelled_is_not(self):
        done = json.loads((audit.FIXTURES / "single/SINGLE-068/expected/verify.json").read_text())
        cancelled = json.loads((audit.FIXTURES / "single/SINGLE-067/expected/verify.json").read_text())
        verify_task_root_fixtures.check_done_root(done)
        self.assertEqual((done["status"], cancelled["status"]), ("passed", "blocked"))
        self.assertEqual(done["targetResults"][0]["bindingRefs"], ["root::default"])
        self.assertEqual(cancelled["targetResults"][0]["bindingRefs"], [])
        # `cancelled`の起点は`addresses`する規範文に到達せず、`done`の起点は到達する。
        self.assertEqual(cancelled["targetResults"][0]["statements"], [])
        self.assertEqual(done["targetResults"][0]["statements"], ["REQ-001:AC-01"])

    def test_task_root_context_holds_the_addressed_owner(self):
        """関係・トレースモデル §6.3: TASKの起点は、`addresses`の対象を所有する文書を
        コンテキストに加えるので、ハッシュ値は3文書すべてを含む。"""
        canonical = digest_reference.canonical_bytes(
            verify_task_root_fixtures.reviewed_digest_input())
        payload = json.loads(canonical.decode())
        self.assertEqual([d["id"] for d in payload["documents"]],
                         ["REQ-001", "TASK-001", "TECH-001"])
        self.assertEqual(payload["roots"], ["TASK-001"])
        golden = (audit.FIXTURES / "single/SINGLE-042/expected/context.canonical.json").read_bytes()
        self.assertNotEqual(canonical, golden)

    def test_task_root_audit_rejects_tampered_expectations(self):
        mutations = [
            ("expected/verify.json", lambda v: v["targetResults"][0].update(statements=[])),
            ("expected/verify.json",
             lambda v: v["targetResults"][0].update(statements=["REQ-001:AC-01", "REQ-001:AC-02"])),
            ("expected/verify.json",
             lambda v: v["commands"][0].update(tests=["tests/test_auth.py", "tests/test_session.py"])),
            ("expected/verify.json", lambda v: v["targetResults"][0].update(bindingRefs=[])),
            ("expected/verify.json", lambda v: v.update(status="blocked")),
        ]
        for relative, mutate in mutations:
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                fixture = root / "single/SINGLE-068"
                shutil.copytree(audit.FIXTURES / "single/SINGLE-068", fixture)
                for name in ("manifest", "result", "side-effects", "frontmatter"):
                    shutil.copy2(schema_path(audit.FIXTURES, name), root)
                path = fixture / relative
                value = json.loads(path.read_text())
                mutate(value)
                path.write_text(json.dumps(value))
                self.assertTrue(validate_verify_task_root(root, ["SINGLE-068"])["errors"])

    def test_task_root_audit_rejects_a_status_change(self):
        for status in ("open", "cancelled"):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                fixture = root / "single/SINGLE-068"
                shutil.copytree(audit.FIXTURES / "single/SINGLE-068", fixture)
                for name in ("manifest", "result", "side-effects", "frontmatter"):
                    shutil.copy2(schema_path(audit.FIXTURES, name), root)
                path = fixture / "repo" / verify_task_root_fixtures.TASK_PATH
                path.write_text(path.read_text().replace("status: done", "status: " + status))
                self.assertTrue(validate_verify_task_root(root, ["SINGLE-068"])["errors"])

    def test_prerequisite_state_decides_verify_of_a_task_root(self):
        """関係・トレースモデル §6.3、ADR-029: 目的`verify`でも、起点のTASKの`requires`の参照先のTASKが
        すべて`done`でなければ`CTX-TASK-DEPENDENCY-001`の`blocked`とする（実装の確認事項C11）。"""
        blocked = json.loads((audit.FIXTURES / "single/SINGLE-137/expected/verify.json").read_text())
        passed = json.loads((audit.FIXTURES / "single/SINGLE-138/expected/verify.json").read_text())
        verify_task_root_fixtures.check_prerequisite("SINGLE-137", blocked)
        verify_task_root_fixtures.check_prerequisite("SINGLE-138", passed)
        target = blocked["targetResults"][0]
        self.assertEqual((blocked["status"], target["contextDigest"], target["statements"], target["bindingRefs"],
                          blocked["commands"]), ("blocked", None, [], [], []))
        self.assertEqual([d["code"] for d in target["diagnostics"]], ["CTX-TASK-DEPENDENCY-001"])
        self.assertEqual(target["diagnostics"][0]["source"]["key"], "relations.requires")
        self.assertEqual(passed["status"], "passed")
        self.assertEqual(passed["targetResults"][0]["diagnostics"], [])
        self.assertEqual(passed["targetResults"][0]["statements"], ["REQ-001:AC-01"])
        # 起点のTASKの`requires`の閉包は含めないので、先行TASK-002はコンテキストへ入らない。
        payload = json.loads(digest_reference.canonical_bytes(
            verify_task_root_fixtures.reviewed_digest_input("SINGLE-138")).decode())
        self.assertEqual([d["id"] for d in payload["documents"]], ["REQ-001", "TASK-001", "TECH-001"])
        task = payload["documents"][1]
        self.assertEqual(task["strongRelations"], [{"relation": "addresses", "target": "REQ-001:AC-01"},
                                                   {"relation": "requires", "target": "TASK-002"}])

    def test_prerequisite_audit_rejects_tampered_expectations(self):
        # 先行TASKが未完了の起点（SINGLE-137）を`passed`や診断なしにすること、先行TASKが`done`の起点
        # （SINGLE-138）を`blocked`にしたり診断を足したりすることを、監査は拒否する。
        def blocked_target(**changes):
            return lambda v: v["targetResults"][0].update(**changes)

        def drop_diagnostic(v):
            v["targetResults"][0]["diagnostics"] = []

        def wrong_code(v):
            v["targetResults"][0]["diagnostics"][0].update(code="CTX-STATE-001")

        def add_diagnostic(code):
            def mutate(v):
                diagnostic = json.loads((audit.FIXTURES / "single/SINGLE-137/expected/verify.json").read_text()
                                        )["targetResults"][0]["diagnostics"][0]
                v["targetResults"][0]["diagnostics"].append(dict(diagnostic, code=code))
            return mutate

        mutations = [
            ("SINGLE-137", "expected/verify.json", drop_diagnostic),
            ("SINGLE-137", "expected/verify.json", wrong_code),
            ("SINGLE-137", "expected/verify.json", lambda v: v.update(status="passed")),
            ("SINGLE-137", "expected/verify.json", blocked_target(status="passed")),
            ("SINGLE-137", "expected/verify.json",
             blocked_target(contextDigest="sha256:" + "0" * 64)),
            ("SINGLE-137", "expected/verify.json", blocked_target(statements=["REQ-001:AC-01"])),
            ("SINGLE-137", "expected/verify.json", blocked_target(bindingRefs=["root::default"])),
            ("SINGLE-137", "expected/verify.json",
             lambda v: v["commands"].append(json.loads(
                 (audit.FIXTURES / "single/SINGLE-138/expected/verify.json").read_text())["commands"][0])),
            ("SINGLE-137", "manifest.json", lambda v: v["expect"].update(status="passed", exitCode=0)),
            ("SINGLE-138", "expected/verify.json", lambda v: v.update(status="blocked")),
            ("SINGLE-138", "expected/verify.json", add_diagnostic("CTX-TASK-DEPENDENCY-001")),
            ("SINGLE-138", "expected/verify.json", add_diagnostic("CTX-STATE-001")),
            ("SINGLE-138", "expected/verify.json", blocked_target(statements=[])),
            ("SINGLE-138", "expected/verify.json",
             blocked_target(statements=["REQ-001:AC-01", "REQ-001:AC-02"])),
            ("SINGLE-138", "expected/verify.json", blocked_target(contextDigest=None)),
            ("SINGLE-138", "expected/verify.json", blocked_target(bindingRefs=[])),
            ("SINGLE-138", "expected/verify.json",
             lambda v: v["commands"][0].update(tests=["tests/test_auth.py", "tests/test_session.py"])),
            ("SINGLE-138", "expected/verify.json",
             lambda v: v["commands"][0].update(covers=["REQ-001:AC-01", "REQ-001:AC-02"])),
            ("SINGLE-138", "expected/verify.json",
             lambda v: v["commands"][0].update(argv=["/bin/true", "tests/test_auth.py", "tests/test_session.py"])),
            ("SINGLE-138", "manifest.json", lambda v: v["expect"].update(status="blocked", exitCode=2)),
        ]
        for identifier, relative, mutate in mutations:
            with self.subTest(identifier=identifier, relative=relative), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                fixture = root / "single" / identifier
                shutil.copytree(audit.FIXTURES / "single" / identifier, fixture)
                for name in ("manifest", "result", "side-effects", "frontmatter"):
                    shutil.copy2(schema_path(audit.FIXTURES, name), root)
                path = fixture / relative
                value = json.loads(path.read_text())
                mutate(value)
                path.write_text(json.dumps(value))
                self.assertTrue(validate_verify_task_root(root, [identifier])["errors"])

    def test_inapplicable_requires_closure_blocks_verify_of_a_task_root(self):
        """関係・トレースモデル §6.3、ADR-034の`Decision`の5番目の項目: 目的`verify`でも、コンテキストへ含めない
        起点の`requires`の閉包の文書（TASKを除く）の適用可能性を検査する。状態`draft`のREQ-002を`requires`する
        状態`done`のTASKは、`CTX-STATE-001`の`blocked`になる（実装の確認事項C15）。"""
        blocked = json.loads((audit.FIXTURES / "single/SINGLE-146/expected/verify.json").read_text())
        verify_task_root_fixtures.check_inapplicable_closure(blocked)
        target = blocked["targetResults"][0]
        self.assertEqual((blocked["status"], target["contextDigest"], target["statements"], target["bindingRefs"],
                          blocked["commands"], blocked["diagnostics"]), ("blocked", None, [], [], [], []))
        self.assertEqual([(d["code"], d["source"]["path"]) for d in target["diagnostics"]],
                         [("CTX-STATE-001", ".spec/requirements/REQ-002.md")])
        inputs = verify_task_root_fixtures.reviewed_inputs("SINGLE-146")
        task, _ = digest_crosscheck.split_document(inputs[verify_task_root_fixtures.TASK_PATH].decode())
        inapplicable, _ = digest_crosscheck.split_document(inputs[verify_task_root_fixtures.INAPPLICABLE_PATH].decode())
        self.assertEqual((task["status"], task["relations"]["requires"], inapplicable["status"]),
                         ("done", ["REQ-002"], "draft"))
        # `addresses`の参照先（REQ-001）は`approved`でテスト対応を持つので、`blocked`の原因はREQ-002だけである。
        self.assertEqual(task["relations"]["addresses"], ["REQ-001:AC-01"])

    def test_inapplicable_closure_audit_rejects_tampered_expectations(self):
        # 起点の`requires`の閉包の文書が適用できない起点を、`passed`にする、診断を消す、診断を重ねる、別の診断へ置換する、
        # テストを開始したことにする改変を、監査は拒否する。
        def target(**changes):
            return lambda v: v["targetResults"][0].update(**changes)

        def add_diagnostic(**changes):
            def mutate(v):
                diagnostic = v["targetResults"][0]["diagnostics"][0]
                v["targetResults"][0]["diagnostics"].append(dict(diagnostic, **changes))
            return mutate

        passed = json.loads((audit.FIXTURES / "single/SINGLE-138/expected/verify.json").read_text())
        mutations = [
            ("expected/verify.json", lambda v: v.update(status="passed")),
            ("expected/verify.json", lambda v: v.update(status="failed")),
            ("expected/verify.json", target(status="passed")),
            ("expected/verify.json", target(diagnostics=[])),
            ("expected/verify.json", lambda v: v["targetResults"][0]["diagnostics"][0].update(code="CTX-TASK-DEPENDENCY-001")),
            ("expected/verify.json", lambda v: v["targetResults"][0]["diagnostics"][0].update(code="CTX-STATE-SUPERSEDED-001")),
            ("expected/verify.json", add_diagnostic(code="CTX-STATE-001")),
            ("expected/verify.json", add_diagnostic(code="CTX-TASK-DEPENDENCY-001")),
            ("expected/verify.json", lambda v: v["targetResults"][0]["diagnostics"][0]["source"].update(
                path=".spec/tasks/TASK-001.md")),
            ("expected/verify.json", lambda v: v["targetResults"][0]["diagnostics"][0]["source"].update(
                key="relations.requires")),
            ("expected/verify.json", lambda v: v.update(diagnostics=[v["targetResults"][0]["diagnostics"][0]])),
            ("expected/verify.json", target(contextDigest="sha256:" + "0" * 64)),
            ("expected/verify.json", target(statements=["REQ-001:AC-01"])),
            ("expected/verify.json", target(bindingRefs=["root::default"])),
            ("expected/verify.json", lambda v: v["commands"].append(passed["commands"][0])),
            ("manifest.json", lambda v: v["expect"].update(status="passed", exitCode=0)),
            ("manifest.json", lambda v: v["expect"].update(exitCode=0)),
        ]
        for relative, mutate in mutations:
            with self.subTest(relative=relative, mutation=mutations.index((relative, mutate))), \
                    tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                fixture = root / "single/SINGLE-146"
                shutil.copytree(audit.FIXTURES / "single/SINGLE-146", fixture)
                for name in ("manifest", "result", "side-effects", "frontmatter"):
                    shutil.copy2(schema_path(audit.FIXTURES, name), root)
                path = fixture / relative
                value = json.loads(path.read_text())
                mutate(value)
                path.write_text(json.dumps(value))
                self.assertTrue(validate_verify_task_root(root, ["SINGLE-146"])["errors"])

    def test_inapplicable_closure_audit_rejects_repaired_causes(self):
        # 原因を入力側で直す（REQ-002を`approved`へ、`requires`を消す、TASKを`open`へ、`addresses`の参照先を`draft`へ）と、
        # 期待値との組が成り立たなくなる。
        mutations = [
            (verify_task_root_fixtures.INAPPLICABLE_PATH, "status: draft", "status: approved"),
            (verify_task_root_fixtures.INAPPLICABLE_PATH, "status: draft", "status: outdated"),
            (verify_task_root_fixtures.TASK_PATH, "requires: [REQ-002]", "related: [REQ-002]"),
            (verify_task_root_fixtures.TASK_PATH, "status: done", "status: open"),
            (verify_task_root_fixtures.TASK_PATH, "status: done", "status: cancelled"),
            (verify_task_root_fixtures.ADDRESSED_PATH, "status: approved", "status: draft"),
        ]
        for relative, before, after in mutations:
            with self.subTest(relative=relative, after=after), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                fixture = root / "single/SINGLE-146"
                shutil.copytree(audit.FIXTURES / "single/SINGLE-146", fixture)
                for name in ("manifest", "result", "side-effects", "frontmatter"):
                    shutil.copy2(schema_path(audit.FIXTURES, name), root)
                path = fixture / "repo" / relative
                self.assertIn(before, path.read_text())
                path.write_text(path.read_text().replace(before, after))
                self.assertTrue(validate_verify_task_root(root, ["SINGLE-146"])["errors"])

    def test_proposed_adr_in_requires_closure_fails_verify_of_a_task_root(self):
        """関係・トレースモデル §4・§6.3、診断レジストリ`RELATION-TYPE`: 目的`verify`でも、コンテキストへ含めない起点の
        `requires`の閉包の文書（REQ-002）の強い関係が`proposed`のADRを指せば、型制約の`CTX-RELATION-TYPE-001`（`failed`）にする
        （実装の確認事項C17）。状態の診断（`CTX-STATE-001`、`blocked`）にしない。"""
        failed = json.loads((audit.FIXTURES / "single/SINGLE-149/expected/verify.json").read_text())
        verify_task_root_fixtures.check_type_closure(failed)
        target = failed["targetResults"][0]
        self.assertEqual((failed["status"], target["status"], target["contextDigest"], target["statements"],
                          target["bindingRefs"], failed["commands"], failed["diagnostics"]),
                         ("failed", "failed", None, [], [], [], []))
        self.assertEqual([(d["code"], d["source"]["path"], d["source"]["key"], d["evidence"]) for d in target["diagnostics"]],
                         [("CTX-RELATION-TYPE-001", ".spec/requirements/REQ-002.md", "relations.requires", "ADR-001")])
        inputs = verify_task_root_fixtures.reviewed_inputs("SINGLE-149")
        task, _ = digest_crosscheck.split_document(inputs[verify_task_root_fixtures.TASK_PATH].decode())
        closure, _ = digest_crosscheck.split_document(inputs[verify_task_root_fixtures.INAPPLICABLE_PATH].decode())
        adr, _ = digest_crosscheck.split_document(inputs[".spec/decisions/ADR-001.md"].decode())
        # TASK-001はADR-001を直接`requires`しない。REQ-002（`approved`）を経由して推移的に到達する。
        self.assertEqual((task["status"], task["relations"]["requires"], closure["status"], closure["relations"]["requires"],
                          adr["status"]), ("done", ["REQ-002"], "approved", ["ADR-001"], "proposed"))
        self.assertEqual(task["relations"]["addresses"], ["REQ-001:AC-01"])

    def test_type_closure_audit_rejects_tampered_expectations(self):
        # `proposed`のADRへの`requires`を、`passed`にする、診断を消す、状態の診断へ置換する、診断を重ねる、
        # テストを開始したことにする改変を、監査は拒否する。
        def target(**changes):
            return lambda v: v["targetResults"][0].update(**changes)

        def first(**changes):
            return lambda v: v["targetResults"][0]["diagnostics"][0].update(**changes)

        def add_diagnostic(**changes):
            def mutate(v):
                diagnostic = v["targetResults"][0]["diagnostics"][0]
                v["targetResults"][0]["diagnostics"].append(dict(diagnostic, **changes))
            return mutate

        passed = json.loads((audit.FIXTURES / "single/SINGLE-138/expected/verify.json").read_text())
        mutations = [
            ("expected/verify.json", lambda v: v.update(status="passed")),
            ("expected/verify.json", lambda v: v.update(status="blocked")),
            ("expected/verify.json", target(status="passed")),
            ("expected/verify.json", target(status="blocked")),
            ("expected/verify.json", target(diagnostics=[])),
            ("expected/verify.json", first(code="CTX-STATE-001", resultStatus="blocked")),
            ("expected/verify.json", lambda v: (v.update(status="blocked"), v["targetResults"][0].update(status="blocked"),
                                                v["targetResults"][0]["diagnostics"][0].update(
                                                    code="CTX-STATE-001", resultStatus="blocked"))),
            ("expected/verify.json", first(code="CTX-TASK-DEPENDENCY-001")),
            ("expected/verify.json", add_diagnostic(code="CTX-STATE-001", resultStatus="blocked")),
            ("expected/verify.json", add_diagnostic()),
            ("expected/verify.json", lambda v: v["targetResults"][0]["diagnostics"][0].pop("evidence")),
            ("expected/verify.json", first(evidence="REQ-002")),
            ("expected/verify.json", lambda v: v["targetResults"][0]["diagnostics"][0]["source"].pop("key")),
            ("expected/verify.json", lambda v: v["targetResults"][0]["diagnostics"][0]["source"].update(
                path=".spec/tasks/TASK-001.md")),
            ("expected/verify.json", lambda v: v["targetResults"][0]["diagnostics"][0]["source"].update(
                path=".spec/decisions/ADR-001.md")),
            ("expected/verify.json", lambda v: v.update(diagnostics=[v["targetResults"][0]["diagnostics"][0]])),
            ("expected/verify.json", target(contextDigest="sha256:" + "0" * 64)),
            ("expected/verify.json", target(statements=["REQ-001:AC-01"])),
            ("expected/verify.json", target(bindingRefs=["root::default"])),
            ("expected/verify.json", lambda v: v["commands"].append(passed["commands"][0])),
            ("manifest.json", lambda v: v["expect"].update(status="passed", exitCode=0)),
            ("manifest.json", lambda v: v["expect"].update(status="blocked", exitCode=2)),
            ("manifest.json", lambda v: v["expect"].update(exitCode=2)),
        ]
        for index, (relative, mutate) in enumerate(mutations):
            with self.subTest(relative=relative, mutation=index), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                fixture = root / "single/SINGLE-149"
                shutil.copytree(audit.FIXTURES / "single/SINGLE-149", fixture)
                for name in ("manifest", "result", "side-effects", "frontmatter"):
                    shutil.copy2(schema_path(audit.FIXTURES, name), root)
                path = fixture / relative
                value = json.loads(path.read_text())
                mutate(value)
                path.write_text(json.dumps(value))
                self.assertTrue(validate_verify_task_root(root, ["SINGLE-149"])["errors"])

    def test_type_closure_contract_rejects_state_replacement(self):
        """完全比較とは別に、`check_type_closure`だけが、型制約の診断の状態の診断への置換や、`blocked`への変更を拒否する。"""
        value = json.loads((audit.FIXTURES / "single/SINGLE-149/expected/verify.json").read_text())
        verify_task_root_fixtures.check_type_closure(value)
        state = verify_task_root_fixtures.inapplicable_diagnostic()
        for index, mutate in enumerate([
            lambda v: v["targetResults"][0].update(diagnostics=[state]),
            lambda v: v["targetResults"][0]["diagnostics"].append(state),
            lambda v: v["targetResults"][0].update(diagnostics=[]),
            lambda v: (v.update(status="blocked"), v["targetResults"][0].update(status="blocked")),
            lambda v: v["targetResults"][0]["diagnostics"][0]["source"].update(path=".spec/tasks/TASK-001.md"),
            lambda v: v["targetResults"][0]["diagnostics"][0].update(evidence="REQ-002"),
        ]):
            with self.subTest(index=index):
                changed = copy.deepcopy(value)
                mutate(changed)
                with self.assertRaises(ValueError):
                    verify_task_root_fixtures.check_type_closure(changed)

    def test_type_closure_audit_rejects_repaired_causes(self):
        # 原因を入力側で直す（ADR-001を`accepted`へ、REQ-002の`requires`を消す、TASKからREQ-002への`requires`を消す、
        # ADR-001への`requires`をTASK-001へ移す、TASKを`open`へ、`addresses`の参照先を`draft`へ）と、期待値との組が成り立たなくなる。
        mutations = [
            (".spec/decisions/ADR-001.md", "status: proposed", "status: accepted"),
            (".spec/decisions/ADR-001.md", "status: proposed", "status: rejected"),
            (verify_task_root_fixtures.INAPPLICABLE_PATH, "requires: [ADR-001]", "related: [ADR-001]"),
            (verify_task_root_fixtures.INAPPLICABLE_PATH, "status: approved", "status: draft"),
            (verify_task_root_fixtures.TASK_PATH, "requires: [REQ-002]", "requires: [ADR-001]"),
            (verify_task_root_fixtures.TASK_PATH, "requires: [REQ-002]", "related: [REQ-002]"),
            (verify_task_root_fixtures.TASK_PATH, "status: done", "status: open"),
            (verify_task_root_fixtures.ADDRESSED_PATH, "status: approved", "status: draft"),
        ]
        for relative, before, after in mutations:
            with self.subTest(relative=relative, after=after), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                fixture = root / "single/SINGLE-149"
                shutil.copytree(audit.FIXTURES / "single/SINGLE-149", fixture)
                for name in ("manifest", "result", "side-effects", "frontmatter"):
                    shutil.copy2(schema_path(audit.FIXTURES, name), root)
                path = fixture / "repo" / relative
                self.assertIn(before, path.read_text())
                path.write_text(path.read_text().replace(before, after))
                self.assertTrue(validate_verify_task_root(root, ["SINGLE-149"])["errors"])

    def test_prerequisite_addresses_stays_out_of_the_obligation(self):
        """`verify` §3、関係・トレースモデル §6.4の4.: `requires`先のTASKの`addresses`の参照先は、起点の義務へ加えない。
        SINGLE-138の先行TASK-002は、起点が`addresses`しないREQ-001:AC-02を`addresses`する。"""
        inputs = verify_task_root_fixtures.reviewed_inputs("SINGLE-138")
        prerequisite, _ = digest_crosscheck.split_document(
            inputs[verify_task_root_fixtures.PREREQUISITE_PATH].decode())
        self.assertEqual((prerequisite["status"], prerequisite["relations"]["addresses"]),
                         ("done", ["REQ-001:AC-02"]))
        result = json.loads((audit.FIXTURES / "single/SINGLE-138/expected/verify.json").read_text())
        self.assertEqual(result["targetResults"][0]["statements"], ["REQ-001:AC-01"])
        self.assertEqual(result["commands"][0]["covers"], ["REQ-001:AC-01"])
        self.assertEqual(result["commands"][0]["tests"], ["tests/test_auth.py"])
        # 参照計算Bは、閉包の外のTASK-002が閉包の文書REQ-001を`addresses`しても、材料へ入れない。
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            for name, data in inputs.items():
                (repository / name).parent.mkdir(parents=True, exist_ok=True)
                (repository / name).write_bytes(data)
            built = digest_crosscheck.build(repository, root="TASK-001")
            self.assertEqual([d["id"] for d in built["documents"]], ["REQ-001", "TASK-001", "TECH-001"])
            self.assertEqual(digest_crosscheck.canonical_bytes(built), digest_reference.canonical_bytes(
                verify_task_root_fixtures.reviewed_digest_input("SINGLE-138")))
        # 入力側で先行TASKの`addresses`を消す、または起点と同じ規範文へ変えると、監査は拒否する。
        for replacement in ("", "relations:\n  addresses: [REQ-001:AC-01]\n"):
            with self.subTest(replacement=replacement), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                fixture = root / "single/SINGLE-138"
                shutil.copytree(audit.FIXTURES / "single/SINGLE-138", fixture)
                for name in ("manifest", "result", "side-effects", "frontmatter"):
                    shutil.copy2(schema_path(audit.FIXTURES, name), root)
                path = fixture / "repo" / verify_task_root_fixtures.PREREQUISITE_PATH
                path.write_text(path.read_text().replace("relations:\n  addresses: [REQ-001:AC-02]\n", replacement))
                self.assertTrue(validate_verify_task_root(root, ["SINGLE-138"])["errors"])

    def test_closure_accepts_only_the_verify_task_root_prerequisite_addresses(self):
        """参照計算Bの`closure`は、閉包の外のTASKの`addresses`を一律には受理しない。受理するのは、目的`verify`で
        TASKを起点にしたときの、起点が`requires`する先行TASKの`addresses`だけである（関係・トレースモデル §6.3、§6.4の4.）。"""
        requirement = (audit.FIXTURES / "single/SINGLE-138/repo/.spec/requirements/REQ-001.md").read_text()
        body = digest_crosscheck.normalize_body(requirement.split("---\n", 2)[2])

        def corpus(*tasks):
            documents = {"REQ-001": {"kind": "requirement", "path": "r",
                                     "frontmatter": {"id": "REQ-001", "title": "t", "status": "approved"}, "body": body}}
            for identifier, status, relations in tasks:
                documents[identifier] = {"kind": "task", "path": "t", "body": "",
                                         "frontmatter": {"id": identifier, "title": "t", "status": status,
                                                         "relations": relations}}
            return documents

        root = ("TASK-001", "open", {"requires": ["TASK-002"], "addresses": ["REQ-001:AC-01"]})
        done = ("TASK-002", "done", {"addresses": ["REQ-001:AC-02"]})
        outside = lambda status: ("TASK-009", status, {"addresses": ["REQ-001:AC-01"]})
        # 受理: verifyでTASKを起点にし、先行TASKが閉包の規範文を`addresses`する。先行TASKは閉包へ入らない。
        ordered, _ = digest_crosscheck.closure(corpus(root, done), "TASK-001", "verify")
        self.assertEqual(ordered, ["TASK-001", "REQ-001"])
        # 受理（従来どおり）: implementで、閉包の規範文を`addresses`する`open`のTASKは閉包へ加える。
        ordered, _ = digest_crosscheck.closure(corpus(outside("open")), "REQ-001", "implement")
        self.assertEqual(ordered, ["REQ-001", "TASK-009"])
        rejected = {
            "implementでTASKを起点にし、先行TASKが`addresses`する": (corpus(root, done), "TASK-001", "implement"),
            "interpretでTASKを起点にし、先行TASKが`addresses`する": (corpus(root, done), "TASK-001", "interpret"),
            "verifyでREQを起点にし、閉包の外のTASKが`addresses`する": (corpus(outside("open")), "REQ-001", "verify"),
            "interpretでREQを起点にし、閉包の外のTASKが`addresses`する": (corpus(outside("open")), "REQ-001", "interpret"),
            "implementでREQを起点にし、`done`のTASKが`addresses`する": (corpus(outside("done")), "REQ-001", "implement"),
            "閉包の外のTASKが`requires`で閉包の文書を指す": (
                corpus(("TASK-009", "open", {"requires": ["REQ-001"]})), "REQ-001", "verify"),
            "後続のTASKが起点を`requires`する": (
                corpus(root, done, ("TASK-003", "open", {"requires": ["TASK-001"]})), "TASK-001", "verify"),
        }
        for name, (documents, start, purpose) in rejected.items():
            with self.subTest(name), self.assertRaises(ValueError):
                digest_crosscheck.closure(documents, start, purpose)

    def test_prerequisite_audit_rejects_a_changed_prerequisite_state(self):
        # 先行TASKの状態を入力側で変えると、期待値との組が成り立たなくなる。
        for identifier, status in (("SINGLE-137", "done"), ("SINGLE-137", "cancelled"),
                                   ("SINGLE-138", "open"), ("SINGLE-138", "cancelled")):
            with self.subTest(identifier=identifier, status=status), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                fixture = root / "single" / identifier
                shutil.copytree(audit.FIXTURES / "single" / identifier, fixture)
                for name in ("manifest", "result", "side-effects", "frontmatter"):
                    shutil.copy2(schema_path(audit.FIXTURES, name), root)
                path = fixture / "repo" / verify_task_root_fixtures.PREREQUISITE_PATH
                text = path.read_text()
                self.assertIn("status: " + verify_task_root_fixtures.PREREQUISITE_STATUS[identifier], text)
                path.write_text(text.replace("status: " + verify_task_root_fixtures.PREREQUISITE_STATUS[identifier],
                                             "status: " + status))
                self.assertTrue(validate_verify_task_root(root, [identifier])["errors"])

    def test_verify_document_fixture(self):
        result = validate_verify_document()
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["prepared"], ["SINGLE-066"])
        self.assertEqual(result["core_execution"], "Not run")

    def test_document_level_binding_has_no_statements(self):
        result = json.loads((audit.FIXTURES / "single/SINGLE-066/expected/verify.json").read_text())
        verify_document_fixtures.check_document_binding(result)
        target = result["targetResults"][0]
        self.assertEqual(target["statements"], [])
        self.assertEqual(target["bindingRefs"], ["root::default"])
        self.assertEqual(result["commands"][0]["covers"], ["TECH-001"])
        self.assertEqual(result["status"], "passed")

    def test_document_audit_rejects_a_statement_bearing_or_unbound_target(self):
        statement = ("- [TECH-001:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] "
                     "[CONSTRAINT] 秘密情報を出力しない。")
        mutations = [
            ("expected/verify.json", lambda v: v["targetResults"][0].update(statements=["TECH-001:AC-01"])),
            ("expected/verify.json", lambda v: v["targetResults"][0].update(bindingRefs=[])),
            ("expected/verify.json", lambda v: v["commands"][0].update(covers=["TECH-001:AC-01"])),
        ]
        for relative, mutate in mutations:
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                fixture = root / "single/SINGLE-066"
                shutil.copytree(audit.FIXTURES / "single/SINGLE-066", fixture)
                for name in ("manifest", "result", "side-effects", "frontmatter"):
                    shutil.copy2(schema_path(audit.FIXTURES, name), root)
                path = fixture / relative
                value = json.loads(path.read_text())
                mutate(value)
                path.write_text(json.dumps(value))
                self.assertTrue(validate_verify_document(root, ["SINGLE-066"])["errors"])
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = root / "single/SINGLE-066"
            shutil.copytree(audit.FIXTURES / "single/SINGLE-066", fixture)
            for name in ("manifest", "result", "side-effects", "frontmatter"):
                shutil.copy2(schema_path(audit.FIXTURES, name), root)
            path = fixture / "repo" / verify_document_fixtures.TECH_PATH
            path.write_text(path.read_text().rstrip(chr(10)) + chr(10) * 2 + statement + chr(10))
            self.assertTrue(validate_verify_document(root, ["SINGLE-066"])["errors"])

    def test_verify_output_fixtures(self):
        result = validate_verify_output()
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["prepared"], ["SINGLE-069-01", "SINGLE-069-02"])
        self.assertEqual(result["core_execution"], "Not run")
        self.assertTrue(result["observed_output"])

    def test_excerpt_is_the_tail_not_the_head(self):
        verify_output_fixtures.check_excerpt_shape()
        for identifier in verify_output_fixtures.CASES:
            result = json.loads((audit.FIXTURES / "single" / identifier / "expected/verify.json").read_text())
            command = result["commands"][0]
            for excerpt in (command["stdoutExcerpt"], command["stderrExcerpt"]):
                self.assertEqual(len(excerpt.encode()), verify_output_fixtures.LIMIT, identifier)
                self.assertIn(verify_output_fixtures.TAIL, excerpt, identifier)
                self.assertNotIn(verify_output_fixtures.HEAD, excerpt, identifier)
            self.assertTrue(command["stdoutTruncated"], identifier)
            self.assertTrue(command["stderrTruncated"], identifier)

    def test_output_fixtures_share_one_context_but_differ_in_outcome(self):
        first = json.loads((audit.FIXTURES / "single/SINGLE-069-01/expected/verify.json").read_text())
        second = json.loads((audit.FIXTURES / "single/SINGLE-069-02/expected/verify.json").read_text())
        # スクリプトの本文はハッシュ値の材料ではないので、コンテキストは同じである。
        self.assertEqual(first["targetResults"][0]["contextDigest"],
                         second["targetResults"][0]["contextDigest"])
        self.assertEqual((first["status"], second["status"]), ("passed", "failed"))
        self.assertEqual((first["commands"][0]["exitCode"], second["commands"][0]["exitCode"]), (0, 1))

    def test_output_audit_rejects_tampered_expectations(self):
        head_excerpt = verify_output_fixtures.HEAD + chr(10) + verify_output_fixtures.EXCERPT[
            :verify_output_fixtures.LIMIT - verify_output_fixtures.LINE_BYTES]
        mutations = [
            ("SINGLE-069-01", "expected/verify.json",
             lambda v: v["commands"][0].update(stdoutTruncated=False)),
            ("SINGLE-069-01", "expected/verify.json",
             lambda v: v["commands"][0].update(stdoutExcerpt=head_excerpt)),
            ("SINGLE-069-01", "expected/verify.json",
             lambda v: v["commands"][0].update(stderrExcerpt="")),
            ("SINGLE-069-02", "expected/verify.json", lambda v: v.update(status="passed")),
            ("SINGLE-069-02", "expected/verify.json",
             lambda v: v["commands"][0].update(exitCode=0, status="passed")),
        ]
        for identifier, relative, mutate in mutations:
            with self.subTest(identifier=identifier, relative=relative), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                fixture = root / "single" / identifier
                shutil.copytree(audit.FIXTURES / "single" / identifier, fixture)
                for name in ("manifest", "result", "side-effects", "frontmatter"):
                    shutil.copy2(schema_path(audit.FIXTURES, name), root)
                path = fixture / relative
                value = json.loads(path.read_text())
                mutate(value)
                path.write_text(json.dumps(value))
                self.assertTrue(validate_verify_output(root, [identifier])["errors"])

    def test_output_audit_rejects_a_command_that_stays_under_the_limit(self):
        short = "#!/bin/sh" + chr(10) + 'echo "short"' + chr(10) + "exit 0" + chr(10)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = root / "single/SINGLE-069-01"
            shutil.copytree(audit.FIXTURES / "single/SINGLE-069-01", fixture)
            for name in ("manifest", "result", "side-effects", "frontmatter"):
                shutil.copy2(schema_path(audit.FIXTURES, name), root)
            path = fixture / "repo" / verify_output_fixtures.COMMAND_PATH
            mode = path.stat().st_mode
            path.write_text(short)
            path.chmod(mode)
            self.assertTrue(validate_verify_output(root, ["SINGLE-069-01"])["errors"])

    def test_verify_process_fixtures(self):
        result = validate_verify_process()
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["prepared"], ["SINGLE-057", "SINGLE-058", "SINGLE-059"])
        self.assertEqual(result["core_execution"], "Not run")
        self.assertTrue(result["observed_terminations"])

    def test_non_exit_terminations_report_no_exit_code(self):
        expected = {"SINGLE-057": "spawn_error", "SINGLE-058": "signal", "SINGLE-059": "timeout"}
        for identifier, termination in expected.items():
            result = json.loads((audit.FIXTURES / "single" / identifier / "expected/verify.json").read_text())
            command = result["commands"][0]
            self.assertEqual(command["termination"], termination, identifier)
            self.assertIsNone(command["exitCode"], identifier)
            self.assertEqual(command["status"], "error", identifier)
            self.assertEqual(result["status"], "error", identifier)
            # テスト割当てに到達したので、検証対象は引き続きそれを参照する。
            self.assertEqual(result["targetResults"][0]["bindingRefs"], ["root::default"], identifier)
            self.assertEqual(len(result["diagnostics"]), 1, identifier)
            self.assertEqual(result["diagnostics"][0]["source"]["kind"], "environment", identifier)

    def test_spawn_error_keeps_both_excerpts_empty(self):
        result = json.loads((audit.FIXTURES / "single/SINGLE-057/expected/verify.json").read_text())
        command = result["commands"][0]
        self.assertEqual(command["stdoutExcerpt"], "")
        self.assertEqual(command["stderrExcerpt"], "")
        self.assertFalse(command["stdoutTruncated"])
        self.assertFalse(command["stderrTruncated"])

    def test_timeout_fixture_keeps_the_drained_readiness_line(self):
        result = json.loads((audit.FIXTURES / "single/SINGLE-059/expected/verify.json").read_text())
        command = result["commands"][0]
        self.assertEqual(command["stdoutExcerpt"], verify_process_fixtures.READY + chr(10))
        self.assertEqual(command["timeoutSeconds"], 1)
        self.assertFalse(command["stdoutTruncated"])

    def test_process_audit_rejects_tampered_expectations(self):
        mutations = [
            ("SINGLE-057", "expected/verify.json", lambda v: v["commands"][0].update(exitCode=0)),
            ("SINGLE-057", "expected/verify.json", lambda v: v["commands"][0].update(termination="exit", exitCode=1)),
            ("SINGLE-058", "expected/verify.json", lambda v: v["diagnostics"][0].update(code="SPEC-VERIFY-TIMEOUT-001")),
            ("SINGLE-058", "expected/verify.json", lambda v: v.update(status="failed")),
            ("SINGLE-059", "expected/verify.json", lambda v: v["commands"][0].update(timeoutSeconds=300)),
            ("SINGLE-059", "expected/verify.json", lambda v: v["commands"][0].update(stdoutExcerpt="")),
            ("SINGLE-059", "expected/verify.json", lambda v: v["targetResults"][0].update(bindingRefs=[])),
        ]
        for identifier, relative, mutate in mutations:
            with self.subTest(identifier=identifier, relative=relative), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                fixture = root / "single" / identifier
                shutil.copytree(audit.FIXTURES / "single" / identifier, fixture)
                for name in ("manifest", "result", "side-effects", "frontmatter"):
                    shutil.copy2(schema_path(audit.FIXTURES, name), root)
                path = fixture / relative
                value = json.loads(path.read_text())
                mutate(value)
                path.write_text(json.dumps(value))
                self.assertTrue(validate_verify_process(root, [identifier])["errors"])

    def test_process_audit_rejects_inputs_that_no_longer_cause_the_failure(self):
        """監査はコマンドのファイルを自分で実行するので、扱いにくい挙動をしなくなった
        corpusは、古い期待値を黙って保たずに失敗しなければならない。"""
        mutations = [
            # OSが受理するファイルはプロセスの生成に成功するので、プロセス生成のエラーにはならない。
            ("SINGLE-057", "repo/bin/badformat", lambda t: "#!/bin/sh\nexit 0\n"),
            # `TERM`に従うコマンドは強制終了を必要としない。
            ("SINGLE-059", "repo/bin/hang.sh", lambda t: "#!/bin/sh\nsleep 60\n"),
        ]
        for identifier, relative, mutate in mutations:
            with self.subTest(identifier=identifier), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                fixture = root / "single" / identifier
                shutil.copytree(audit.FIXTURES / "single" / identifier, fixture)
                for name in ("manifest", "result", "side-effects", "frontmatter"):
                    shutil.copy2(schema_path(audit.FIXTURES, name), root)
                path = fixture / relative
                mode = path.stat().st_mode
                path.write_text(mutate(path.read_text()))
                path.chmod(mode)
                self.assertTrue(validate_verify_process(root, [identifier])["errors"])

    def test_process_audit_rejects_a_lost_executable_bit(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = root / "single/SINGLE-058"
            shutil.copytree(audit.FIXTURES / "single/SINGLE-058", fixture)
            for name in ("manifest", "result", "side-effects", "frontmatter"):
                shutil.copy2(schema_path(audit.FIXTURES, name), root)
            (fixture / "repo/bin/signal.sh").chmod(0o644)
            self.assertTrue(validate_verify_process(root, ["SINGLE-058"])["errors"])

    def test_verify_binding_fixtures(self):
        result = validate_verify_bindings()
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["prepared"], ["SINGLE-063", "SINGLE-064", "SINGLE-065"])
        self.assertEqual(result["core_execution"], "Not run")

    def test_shared_binding_runs_once_with_distinct_target_digests(self):
        for identifier in ("SINGLE-063", "SINGLE-064"):
            result = json.loads((audit.FIXTURES / "single" / identifier / "expected/verify.json").read_text())
            verify_binding_fixtures.check_sharing(identifier, result)
            self.assertEqual(len(result["commands"]), 1, identifier)
            self.assertEqual(result["commands"][0]["tests"],
                             [verify_binding_fixtures.SHARED_TEST], identifier)
            digests = [target["contextDigest"] for target in result["targetResults"]]
            self.assertEqual(len(set(digests)), 2, identifier)

    def test_mixed_targets_execute_only_the_passing_half(self):
        result = json.loads((audit.FIXTURES / "single/SINGLE-064/expected/verify.json").read_text())
        blocked = [t for t in result["targetResults"] if t["status"] == "blocked"]
        passing = [t for t in result["targetResults"] if t["status"] == "passed"]
        self.assertEqual(len(blocked), 1)
        self.assertEqual(len(passing), 1)
        self.assertEqual(blocked[0]["bindingRefs"], [])
        self.assertEqual(passing[0]["bindingRefs"], ["root::default"])
        # 実行したコマンドは、通過した検証対象の規範文だけを対象として主張しなければならない。
        self.assertEqual(result["commands"][0]["covers"], ["REQ-002:AC-01"])
        self.assertEqual(result["status"], "blocked")

    def test_command_without_placeholder_is_not_expanded(self):
        result = json.loads((audit.FIXTURES / "single/SINGLE-065/expected/verify.json").read_text())
        command = result["commands"][0]
        self.assertEqual(command["argv"], ["/bin/true"])
        self.assertEqual(len(command["tests"]), 2)
        for path in command["tests"]:
            self.assertNotIn(path, command["argv"])

    def test_binding_audit_rejects_tampered_expectations(self):
        shared = verify_binding_fixtures.SHARED_TEST
        mutations = [
            ("SINGLE-063", "expected/verify.json",
             lambda v: v["commands"].append(copy.deepcopy(v["commands"][0]))),
            ("SINGLE-063", "expected/verify.json",
             lambda v: v["commands"][0].update(argv=["/bin/true", shared, shared],
                                               tests=[shared, shared])),
            ("SINGLE-063", "expected/verify.json",
             lambda v: v["targetResults"][1].update(contextDigest=v["targetResults"][0]["contextDigest"])),
            ("SINGLE-064", "expected/verify.json",
             lambda v: v["targetResults"][0].update(bindingRefs=["root::default"])),
            ("SINGLE-064", "expected/verify.json", lambda v: v.update(status="passed")),
            ("SINGLE-064", "expected/verify.json",
             lambda v: v["commands"][0].update(covers=["REQ-001:AC-01", "REQ-002:AC-01"])),
            ("SINGLE-065", "expected/verify.json",
             lambda v: v["commands"][0].update(argv=["/bin/true", "tests/test_auth.py",
                                                     "tests/test_session.py"])),
        ]
        for identifier, relative, mutate in mutations:
            with self.subTest(identifier=identifier, relative=relative), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                fixture = root / "single" / identifier
                shutil.copytree(audit.FIXTURES / "single" / identifier, fixture)
                for name in ("manifest", "result", "side-effects", "frontmatter"):
                    shutil.copy2(schema_path(audit.FIXTURES, name), root)
                path = fixture / relative
                value = json.loads(path.read_text())
                mutate(value)
                path.write_text(json.dumps(value))
                self.assertTrue(validate_verify_bindings(root, [identifier])["errors"])

    def test_binding_audit_rejects_a_repaired_or_shifted_corpus(self):
        mutations = [
            ("SINGLE-064", "repo/.spec/technical/TECH-001.md",
             lambda t: t.replace("implements: [src/auth.py]\n", "implements: [src/auth.py]\ntests:\n  - path: tests/test_shared.py\n    covers: [REQ-001:AC-01]\n    command: default\n")),
            ("SINGLE-063", "repo/.spec/technical/TECH-002.md",
             lambda t: t.replace("tests/test_shared.py", "tests/test_other.py")),
            ("SINGLE-065", "repo/.spec/bitz.yaml",
             lambda t: t.replace('["/bin/true"]', '["/bin/true", "{tests}"]')),
        ]
        for identifier, relative, mutate in mutations:
            with self.subTest(identifier=identifier), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                fixture = root / "single" / identifier
                shutil.copytree(audit.FIXTURES / "single" / identifier, fixture)
                for name in ("manifest", "result", "side-effects", "frontmatter"):
                    shutil.copy2(schema_path(audit.FIXTURES, name), root)
                path = fixture / relative
                path.write_text(mutate(path.read_text()))
                self.assertTrue(validate_verify_bindings(root, [identifier])["errors"])

    def test_verify_fixtures(self):
        result = validate_verify()
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["prepared"], ["SINGLE-055", "SINGLE-056", "SINGLE-060",
                                              "SINGLE-061", "SINGLE-062", "SINGLE-067"])
        self.assertEqual(result["core_execution"], "Not run")

    def test_verify_success_reuses_the_committed_golden_digest(self):
        golden = digest_reference.digest(
            (audit.FIXTURES / "single/SINGLE-042/expected/context.canonical.json").read_bytes())
        result = json.loads((audit.FIXTURES / "single/SINGLE-055/expected/verify.json").read_text())
        self.assertEqual(result["targetResults"][0]["contextDigest"], golden)
        # 変えたコマンドの引数列はハッシュ値の材料なので、056はこれを再利用してはいけない。
        failing = json.loads((audit.FIXTURES / "single/SINGLE-056/expected/verify.json").read_text())
        self.assertNotEqual(failing["targetResults"][0]["contextDigest"], golden)

    def test_verify_fixtures_stage_their_configuration(self):
        """`verify`は未追跡の設定で停止するので、どのfixtureも
        `.spec/bitz.yaml`をインデックスから外してはいけない。"""
        for identifier in verify_fixtures.CASES:
            manifest = json.loads((audit.FIXTURES / "single" / identifier / "manifest.json").read_text())
            self.assertEqual(manifest["setup"]["operations"], [{"op": "stage", "paths": ["."]}], identifier)
            with tempfile.TemporaryDirectory() as temporary:
                repository = fixture_setup(audit.FIXTURES / "single" / identifier, manifest,
                                           Path(temporary) / "repo")
                staged = fixture_git(repository, "ls-files", "--", ".spec/bitz.yaml").decode().strip()
            self.assertEqual(staged, ".spec/bitz.yaml", identifier)

    def test_blocked_verify_starts_no_command(self):
        for identifier in ("SINGLE-060", "SINGLE-061", "SINGLE-062", "SINGLE-067"):
            result = json.loads((audit.FIXTURES / "single" / identifier / "expected/verify.json").read_text())
            self.assertEqual(result["commands"], [], identifier)
            self.assertEqual(result["status"], "blocked", identifier)
            for target in result["targetResults"]:
                self.assertEqual(target["bindingRefs"], [], identifier)

    def test_digest_is_absent_exactly_where_the_context_cannot_resolve(self):
        # SINGLE-061はコマンド名を解決できないだけで、コンテキスト自体は完全に構成できる（`verify`仕様 §8）。
        # `contextDigest`が`null`なのはコンテキストを構成できないSINGLE-067だけである（2026-09-26訂正）。
        expected = {"SINGLE-055": True, "SINGLE-056": True, "SINGLE-060": True,
                    "SINGLE-061": True, "SINGLE-067": False}
        for identifier, resolves in expected.items():
            result = json.loads((audit.FIXTURES / "single" / identifier / "expected/verify.json").read_text())
            digest = result["targetResults"][0]["contextDigest"]
            self.assertEqual(digest is not None, resolves, identifier)

    def test_verify_audit_rejects_tampered_expectations(self):
        mutations = [
            ("SINGLE-055", "expected/verify.json", lambda v: v["commands"][0].update(exitCode=1)),
            ("SINGLE-055", "expected/verify.json", lambda v: v["commands"][0].update(bindingId="default")),
            ("SINGLE-055", "expected/verify.json", lambda v: v["targetResults"][0].update(bindingRefs=[])),
            ("SINGLE-055", "expected/verify.json",
             lambda v: v["commands"][0].update(argv=["/bin/true"], tests=["tests/test_auth.py"])),
            ("SINGLE-056", "expected/verify.json", lambda v: v.update(status="passed")),
            ("SINGLE-056", "expected/verify.json",
             lambda v: v["targetResults"][0].update(contextDigest=verify_fixtures.GOLDEN)),
            ("SINGLE-060", "expected/verify.json",
             lambda v: v["commands"].append(verify_fixtures.executed_command("SINGLE-060"))),
            ("SINGLE-060", "expected/verify.json", lambda v: v["targetResults"][0]["diagnostics"].clear()),
            ("SINGLE-061", "expected/verify.json",
             lambda v: v["targetResults"][0].update(contextDigest=verify_fixtures.GOLDEN)),
            ("SINGLE-062", "expected/verify.json", lambda v: v.update(scope="selected")),
            ("SINGLE-067", "expected/verify.json", lambda v: v["targetResults"][0].update(status="passed")),
            ("SINGLE-067", "manifest.json", lambda v: v["setup"].update(operations=[])),
        ]
        for identifier, relative, mutate in mutations:
            with self.subTest(identifier=identifier, relative=relative), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                fixture = root / "single" / identifier
                shutil.copytree(audit.FIXTURES / "single" / identifier, fixture)
                for name in ("manifest", "result", "side-effects", "frontmatter"):
                    shutil.copy2(schema_path(audit.FIXTURES, name), root)
                path = fixture / relative
                value = json.loads(path.read_text())
                mutate(value)
                path.write_text(json.dumps(value))
                self.assertTrue(validate_verify(root, [identifier])["errors"])

    def test_verify_audit_rejects_a_repaired_cause(self):
        mutations = [
            ("SINGLE-060", "repo/.spec/technical/TECH-001.md",
             lambda t: t.replace(verify_fixtures.ONE_TEST, verify_fixtures.BOTH_TESTS)),
            ("SINGLE-061", "repo/.spec/technical/TECH-001.md",
             lambda t: t.replace("command: missing", "command: default")),
            ("SINGLE-062", "repo/.spec/requirements/REQ-001.md",
             lambda t: t.replace("status: draft", "status: approved")),
            ("SINGLE-067", "repo/.spec/tasks/TASK-001.md",
             lambda t: t.replace("status: cancelled", "status: open")),
        ]
        for identifier, relative, mutate in mutations:
            with self.subTest(identifier=identifier), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                fixture = root / "single" / identifier
                shutil.copytree(audit.FIXTURES / "single" / identifier, fixture)
                for name in ("manifest", "result", "side-effects", "frontmatter"):
                    shutil.copy2(schema_path(audit.FIXTURES, name), root)
                path = fixture / relative
                path.write_text(mutate(path.read_text()))
                self.assertTrue(validate_verify(root, [identifier])["errors"])

    def test_context_coverage_and_projection_limit_fixtures(self):
        coverage = validate_context_coverage()
        self.assertEqual(coverage["errors"], [])
        self.assertEqual(coverage["prepared"], ["SINGLE-054"])
        projection = validate_projection_limit()
        self.assertEqual(projection["errors"], [])
        self.assertEqual(projection["prepared"], ["SINGLE-049"])
        for result in (coverage, projection):
            self.assertEqual(result["core_execution"], "Not run")
            self.assertEqual(result["references"], 2)

    def test_implement_digest_differs_from_the_verify_golden(self):
        """目的はハッシュ値の材料であり、`implement`はテスト割当てを記録しないので、2つの
        正規JSONは衝突してはいけない。"""
        golden = (audit.FIXTURES / "single/SINGLE-042/expected/context.canonical.json").read_bytes()
        implement = (audit.FIXTURES / "single/SINGLE-054/expected/context.canonical.json").read_bytes()
        self.assertNotEqual(golden, implement)
        payload = json.loads(implement.decode())
        self.assertEqual(payload["purpose"], "implement")
        self.assertEqual(payload["settings"]["commands"], [])
        self.assertEqual(payload["settings"]["verifyTimeouts"], [])
        self.assertEqual([d["id"] for d in payload["documents"]], ["REQ-001", "TASK-001", "TECH-001"])

    def test_coverage_buckets_partition_their_totals(self):
        result = json.loads((audit.FIXTURES / "single/SINGLE-054/expected/context.json").read_text())
        context_coverage_fixtures.check_coverage(result)
        broken = copy.deepcopy(result)
        broken["coverage"]["must"]["addressed"] = ["REQ-001:AC-01"]
        with self.assertRaises(ValueError):
            context_coverage_fixtures.check_coverage(broken)
        no_cause = copy.deepcopy(result)
        no_cause["coverage"]["must"]["addressed"] = ["REQ-001:AC-01"]
        no_cause["coverage"]["must"]["unaddressed"] = []
        with self.assertRaises(ValueError):
            context_coverage_fixtures.check_coverage(no_cause)

    def test_projection_limit_corpus_actually_crosses_only_the_full_limit(self):
        projection_limit_fixtures.check_limits(projection_limit_fixtures.reviewed_inputs())
        # 文書は同じで、本文は絶対上限を越えるには小さい。
        small = {path: (value[0], value[1], value[2], f"# {value[0]} {value[1]}\n")
                 for path, value in projection_limit_fixtures.DOCUMENTS.items()}
        with patch.object(projection_limit_fixtures, "DOCUMENTS", small):
            with self.assertRaises(ValueError):
                projection_limit_fixtures.check_limits(projection_limit_fixtures.reviewed_inputs())
        # 標準の提示が既に上限を越えていると、詳細度の効果を分離できない。
        huge = {path: (value[0], value[1], value[2],
                       value[3] if value[0] != "TECH-001" else "x" * (2 * projection_limit_fixtures.HARD_LIMIT_BYTES))
                for path, value in projection_limit_fixtures.DOCUMENTS.items()}
        with patch.object(projection_limit_fixtures, "DOCUMENTS", huge):
            with self.assertRaises(ValueError):
                projection_limit_fixtures.check_limits(projection_limit_fixtures.reviewed_inputs())

    def test_coverage_and_projection_audits_reject_tampered_expectations(self):
        mutations = [
            (validate_context_coverage, "SINGLE-054", "expected/context.json",
             lambda v: v.update(status="passed")),
            (validate_context_coverage, "SINGLE-054", "expected/context.json",
             lambda v: v["coverage"]["must"].update(addressed=["REQ-001:AC-01"], unaddressed=[])),
            (validate_context_coverage, "SINGLE-054", "expected/context.json",
             lambda v: v["resolution"].update(documentCount=2)),
            (validate_context_coverage, "SINGLE-054", "manifest.json",
             lambda v: v["invocation"]["argv"].__setitem__(3, "verify")),
            (validate_projection_limit, "SINGLE-049", "expected/context.json",
             lambda v: v["projection"].update(detail="standard")),
            (validate_projection_limit, "SINGLE-049", "expected/context.json",
             lambda v: v.update(contextDigest=None)),
            (validate_projection_limit, "SINGLE-049", "expected/context.json",
             lambda v: v["diagnostics"][0].update(code="CTX-LIMIT-001")),
        ]
        for validator, identifier, relative, mutate in mutations:
            with self.subTest(identifier=identifier, relative=relative), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                fixture = root / "single" / identifier
                shutil.copytree(audit.FIXTURES / "single" / identifier, fixture)
                shutil.copytree(audit.FIXTURES / "single/SINGLE-042", root / "single/SINGLE-042")
                for name in ("manifest", "result", "side-effects", "frontmatter"):
                    shutil.copy2(schema_path(audit.FIXTURES, name), root)
                path = fixture / relative
                value = json.loads(path.read_text())
                mutate(value)
                path.write_text(json.dumps(value))
                self.assertTrue(validator(root, [identifier])["errors"])

    def test_context_limit_fixtures(self):
        result = validate_context_limits()
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["prepared"], ["SINGLE-046", "SINGLE-047", "SINGLE-048-01", "SINGLE-048-02"])
        self.assertEqual(result["core_execution"], "Not run")

    def test_stale_and_projection_report_the_committed_golden_digest(self):
        """046と047は完全に解決するので、別に作った定数ではなく、
        goldenのfixtureがコミットしたのと同じハッシュ値を持たなければならない。"""
        golden = (audit.FIXTURES / "single/SINGLE-042/expected/context.canonical.json").read_bytes()
        expected = digest_reference.digest(golden)
        for identifier in ("SINGLE-046", "SINGLE-047"):
            result = json.loads((audit.FIXTURES / "single" / identifier / "expected/context.json").read_text())
            self.assertEqual(result["contextDigest"], expected, identifier)
            self.assertTrue(result["resolution"]["complete"], identifier)
        for identifier in ("SINGLE-048-01", "SINGLE-048-02"):
            result = json.loads((audit.FIXTURES / "single" / identifier / "expected/context.json").read_text())
            self.assertIsNone(result["contextDigest"], identifier)
            self.assertFalse(result["resolution"]["complete"], identifier)

    def test_non_success_context_delivers_no_bundle(self):
        for identifier in context_limit_fixtures.CASES:
            result = json.loads((audit.FIXTURES / "single" / identifier / "expected/context.json").read_text())
            self.assertEqual(result["documents"], [], identifier)
            self.assertEqual(result["constraintLedger"]["statements"], [], identifier)
            self.assertEqual(result["projection"]["expanded"], [], identifier)
            self.assertEqual(len(result["diagnostics"]), 1, identifier)

    def test_context_limit_audit_rejects_tampered_expectations(self):
        mutations = [
            ("SINGLE-046", "expected/context.json", lambda v: v.update(status="failed")),
            ("SINGLE-046", "expected/context.json", lambda v: v.update(contextDigest=None)),
            ("SINGLE-046", "expected/context.json", lambda v: v["documents"].append({"id": "REQ-001"})),
            ("SINGLE-046", "manifest.json", lambda v: v["expect"].update(exitCode=1)),
            ("SINGLE-047", "expected/context.json", lambda v: v["projection"].update(expanded=["ADR-001"])),
            ("SINGLE-047", "expected/context.json", lambda v: v["diagnostics"][0].update(code="CTX-STALE-001")),
            ("SINGLE-048-01", "expected/context.json", lambda v: v["resolution"].update(complete=True)),
            ("SINGLE-048-01", "expected/context.json", lambda v: v.update(contextDigest="sha256:" + "0" * 64)),
            ("SINGLE-048-02", "expected/context.json", lambda v: v["diagnostics"][0].update(severity="warning")),
            ("SINGLE-048-02", "side-effects.json", lambda v: v["after"].update(home={"x": {"kind": "directory"}})),
        ]
        for identifier, relative, mutate in mutations:
            with self.subTest(identifier=identifier, relative=relative), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                fixture = root / "single" / identifier
                shutil.copytree(audit.FIXTURES / "single" / identifier, fixture)
                for name in ("manifest", "result", "side-effects", "frontmatter"):
                    shutil.copy2(schema_path(audit.FIXTURES, name), root)
                path = fixture / relative
                value = json.loads(path.read_text())
                mutate(value)
                path.write_text(json.dumps(value))
                self.assertTrue(validate_context_limits(root, [identifier])["errors"])

    def test_limit_cases_must_actually_cross_their_configured_limit(self):
        mutations = [
            ("SINGLE-048-02", "repo/.spec/requirements/REQ-001.md",
             lambda t: t.replace(context_limit_fixtures.PADDING, "")),
            ("SINGLE-048-01", "repo/.spec/bitz.yaml",
             lambda t: t.replace("maxDocuments: 1", "maxDocuments: 20")),
            ("SINGLE-046", "repo/.spec/bitz.yaml",
             lambda t: t + "context:\n  maxDocuments: 1\n"),
        ]
        for identifier, relative, mutate in mutations:
            with self.subTest(identifier=identifier), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                fixture = root / "single" / identifier
                shutil.copytree(audit.FIXTURES / "single" / identifier, fixture)
                for name in ("manifest", "result", "side-effects", "frontmatter"):
                    shutil.copy2(schema_path(audit.FIXTURES, name), root)
                path = fixture / relative
                path.write_text(mutate(path.read_text()))
                self.assertTrue(validate_context_limits(root, [identifier])["errors"])

    def test_parser_checks_reject_missing_unsafe_and_duplicate_references(self):
        from conformance.parser_expectations import files
        identifier = "SINGLE-097-01"
        fixture = audit.FIXTURES / "single" / identifier
        manifest = json.loads((fixture / "manifest.json").read_text())
        self.assertEqual(len(list(files(fixture, manifest))), 1)
        for field, value in (("path", "../outside.md"), ("path", "/tmp/outside.md"),
                             ("resultFile", "expected/missing.json"),
                             ("resultFile", "expected/../manifest.json")):
            changed = copy.deepcopy(manifest)
            changed["parserChecks"][0][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                list(files(fixture, changed))
        duplicate = copy.deepcopy(manifest)
        duplicate["parserChecks"].append(copy.deepcopy(duplicate["parserChecks"][0]))
        with self.assertRaises(ValueError):
            list(files(fixture, duplicate))

    def test_code_span_reference_uses_maximal_equal_runs(self):
        decode = digest_crosscheck.unescape_text
        self.assertEqual(decode(digest_reference.CODE_TEXT), digest_reference.CODE_VALUE)
        self.assertEqual(decode("`[MUST]`"), "[MUST]")
        self.assertEqual(decode("``a`b```c``"), "a`b```c")
        for text in ("`a", "``a`", "`a``", "``a```"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                decode(text)

    def test_digest_fixtures(self):
        result = validate_digest()
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["prepared"], ["SINGLE-042", "SINGLE-043-01", "SINGLE-043-02",
                                              "SINGLE-044-01", "SINGLE-044-02", "SINGLE-045",
                                              "SINGLE-127-03", "SINGLE-127-04", "SINGLE-097-01", "SINGLE-098-01", "SINGLE-096-01",
                                              "SINGLE-101-01", "SINGLE-106-01", "SINGLE-121", "SINGLE-106-02"])
        self.assertEqual(result["core_execution"], "Not run")
        self.assertEqual(result["references"], 2)

    def test_two_references_agree_and_separate_the_family(self):
        """Aはハッシュ値の材料を記述し、Bは木構造から組み立て直す。両者は一致しなければならず、
        matrixの一致・不一致の組はハッシュ値だけでなくバイト列で成り立たなければならない。"""
        canonical = {}
        for identifier in digest_reference.CASES:
            fixture = audit.FIXTURES / "single" / identifier
            manifest = json.loads((fixture / "manifest.json").read_text())
            with tempfile.TemporaryDirectory() as temporary:
                repository = fixture_setup(fixture, manifest, Path(temporary) / "repo")
                derived = digest_crosscheck.canonical_bytes(digest_crosscheck.build(repository))
            literal = digest_reference.canonical_bytes(digest_reference.reviewed_digest_input(identifier))
            self.assertEqual(literal, derived)
            self.assertEqual(digest_reference.digest(literal), digest_crosscheck.digest(derived))
            self.assertEqual(literal, (fixture / "expected/context.canonical.json").read_bytes())
            canonical[identifier] = literal
        golden = canonical["SINGLE-042"]
        for identifier, value in canonical.items():
            if identifier in digest_reference.SAME_AS_GOLDEN:
                self.assertEqual(value, golden, identifier)
            else:
                self.assertNotEqual(value, golden, identifier)
        self.assertNotEqual(canonical["SINGLE-044-01"], canonical["SINGLE-044-02"])

    def test_canonical_json_is_rfc8785_shaped(self):
        golden = (audit.FIXTURES / "single/SINGLE-042/expected/context.canonical.json").read_bytes()
        self.assertFalse(golden.startswith(b"\xef\xbb\xbf"))
        self.assertFalse(golden.endswith(b"\n"))
        self.assertNotIn(b'": ', golden)
        self.assertNotIn(b", ", golden.replace(", ".encode(), b", "))
        payload = json.loads(golden.decode("utf-8"))
        self.assertEqual(list(payload), sorted(payload))
        self.assertEqual(digest_reference.canonical_bytes(payload), golden)

    def test_digest_audit_rejects_tampered_expectations(self):
        mutations = [
            ("SINGLE-096-01", "expected/parser-ir.json", lambda v: v[0]["operation"].update(text=digest_reference.CODE_TEXT)),
            ("SINGLE-096-01", "expected/parser-ir.json", lambda v: v[0]["operation"].update(text=digest_reference.CODE_VALUE.replace("`", ""))),
            ("SINGLE-096-01", "expected/context.json", lambda v: v["constraintLedger"]["statements"][0]["operation"].update(text="lost span content")),
            ("SINGLE-098-01", "expected/parser-ir.json", lambda v: v[0].update(unknownExtensions=[])),
            ("SINGLE-098-01", "expected/parser-ir.json", lambda v: v[0]["extensions"][0].update(value="lost quote")),
            ("SINGLE-098-01", "expected/context.json", lambda v: v.update(status="passed", diagnostics=[])),
            ("SINGLE-098-01", "expected/context.json", lambda v: v["diagnostics"][0]["source"].update(column=20)),
            ("SINGLE-097-01", "expected/parser-ir.json", lambda v: v[0]["source"].update(column=2)),
            ("SINGLE-097-01", "expected/parser-ir.json", lambda v: v[0]["source"].update(line=1)),
            ("SINGLE-097-01", "expected/parser-ir.json", lambda v: v[0].update(raw="normalized raw")),
            ("SINGLE-097-01", "expected/parser-ir.json", lambda v: v[0]["operation"].update(text="lost escapes")),
            ("SINGLE-101-01", "expected/parser-ir.json", lambda v: v[1].update(reason=None)),
            ("SINGLE-106-02", "expected/context.json", lambda v: v["documents"][2].update(bodyText="forbidden body")),
            ("SINGLE-106-02", "expected/context.json", lambda v: v["documents"][2].pop("statementRefs")),
            ("SINGLE-101-01", "expected/context.json", lambda v: v["constraintLedger"]["statements"][1].update(reason=None)),
            ("SINGLE-106-01", "expected/context.json", lambda v: v["documents"][0].update(expandable=True)),
            ("SINGLE-106-01", "expected/context.json", lambda v: v["documents"][0].pop("bodyText")),
            ("SINGLE-121", "expected/context.canonical.json", lambda v: v.update(resolverVersion="1.1")),
            ("SINGLE-121", "expected/context.canonical.json", lambda v: v.update(digestVersion="1.1")),
            ("SINGLE-042", "expected/context.json", lambda v: v.update(contextDigest="sha256:" + "0" * 64)),
            ("SINGLE-042", "expected/context.json", lambda v: v.update(status="passed_with_warnings")),
            ("SINGLE-042", "expected/context.json", lambda v: v["resolution"].update(documentCount=3)),
            ("SINGLE-042", "expected/context.json", lambda v: v["coverage"]["must"].update(untested=["REQ-001:AC-01"])),
            ("SINGLE-042", "expected/context.json", lambda v: v["documents"][1].update(projection="normative")),
            ("SINGLE-042", "manifest.json", lambda v: v["invocation"]["argv"].__setitem__(3, "implement")),
            ("SINGLE-042", "manifest.json", lambda v: v["expect"].update(reportFileCount=1)),
            ("SINGLE-043-01", "expected/context.json", lambda v: v["projection"].update(detail="standard")),
            ("SINGLE-043-02", "expected/context.json", lambda v: v["projection"].update(expanded=[])),
            ("SINGLE-127-03", "expected/context.json", lambda v: v["projection"].update(expanded=["TECH-001", "REQ-001"])),
            ("SINGLE-127-04", "expected/context.json", lambda v: v["projection"].update(expanded=["TECH-001", "TECH-001"])),
            ("SINGLE-127-03", "manifest.json", lambda v: v["invocation"].update(argv=["context", "REQ-001", "--purpose", "verify", "--expand", "TECH-001", "--format", "json"])),
            ("SINGLE-045", "side-effects.json", lambda v: v["after"].update(cache={"index": {"kind": "directory"}})),
        ]
        for identifier, relative, mutate in mutations:
            with self.subTest(identifier=identifier, relative=relative), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                fixture = root / "single" / identifier
                shutil.copytree(audit.FIXTURES / "single" / identifier, fixture)
                for name in ("manifest", "result", "side-effects", "frontmatter"):
                    shutil.copy2(schema_path(audit.FIXTURES, name), root)
                path = fixture / relative
                value = json.loads(path.read_text())
                mutate(value)
                path.write_text(json.dumps(value))
                self.assertTrue(validate_digest(root, [identifier])["errors"])

    def test_digest_audit_rejects_changed_inputs_and_canonical_bytes(self):
        """変えた入力はコミットした正規JSONを無効にしなければならず、
        `x-`だけの変更をハッシュ値に現れる差として受理してはいけない。"""
        mutations = [
            ("SINGLE-042", "repo/.spec/requirements/REQ-001.md", lambda t: t.replace("秘密情報を出力しない", "秘密情報を記録しない")),
            ("SINGLE-042", "repo/.spec/technical/TECH-001.md", lambda t: t.replace("command: default", "command: other")),
            ("SINGLE-042", "repo/.spec/bitz.yaml", lambda t: t.replace('"{tests}"', '"tests"')),
            ("SINGLE-045", "repo/.spec/technical/TECH-001.md", lambda t: t.replace("x-owners: [team-platform]", "x-owners: [team-auth]\nchanges: [src/auth.py]")),
            ("SINGLE-044-01", "repo/.spec/requirements/REQ-001.md", lambda t: t.replace("\n\n\n## Acceptance Criteria", "\n\n## Acceptance Criteria")),
        ]
        for identifier, relative, mutate in mutations:
            with self.subTest(identifier=identifier, relative=relative), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                fixture = root / "single" / identifier
                shutil.copytree(audit.FIXTURES / "single" / identifier, fixture)
                for name in ("manifest", "result", "side-effects", "frontmatter"):
                    shutil.copy2(schema_path(audit.FIXTURES, name), root)
                path = fixture / relative
                path.write_text(mutate(path.read_text()))
                self.assertTrue(validate_digest(root, [identifier])["errors"])

    def test_digest_audit_rejects_a_replaced_canonical_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = root / "single/SINGLE-042"
            shutil.copytree(audit.FIXTURES / "single/SINGLE-042", fixture)
            for name in ("manifest", "result", "side-effects", "frontmatter"):
                shutil.copy2(schema_path(audit.FIXTURES, name), root)
            canonical = fixture / "expected/context.canonical.json"
            canonical.write_bytes(canonical.read_bytes() + b"\n")
            self.assertTrue(validate_digest(root, ["SINGLE-042"])["errors"])

    def test_crosscheck_rejects_a_corpus_it_cannot_account_for(self):
        """参照計算Bは、別のハッシュ値の材料を黙って作らず、
        レビュー済みの閉包の外の入力を拒否しなければならない。"""
        fixture = audit.FIXTURES / "single/SINGLE-042"
        manifest = json.loads((fixture / "manifest.json").read_text())
        with tempfile.TemporaryDirectory() as temporary:
            repository = fixture_setup(fixture, manifest, Path(temporary) / "repo")
            extra = repository / ".spec/technical/TECH-002.md"
            extra.write_text("---\nid: TECH-002\ntitle: 別方針\nstatus: approved\n"
                             "relations:\n  requires: [TECH-001]\n---\n\n# TECH-002 別方針\n\n## Context\n\n別。\n")
            with self.assertRaises(ValueError):
                digest_crosscheck.build(repository)

    def test_crosscheck_rejects_a_non_canonical_statement(self):
        fixture = audit.FIXTURES / "single/SINGLE-042"
        manifest = json.loads((fixture / "manifest.json").read_text())
        with tempfile.TemporaryDirectory() as temporary:
            repository = fixture_setup(fixture, manifest, Path(temporary) / "repo")
            path = repository / ".spec/requirements/REQ-001.md"
            path.write_text(path.read_text().replace("[MUST] [CONSTRAINT]", "[MUST] [REASON] 理由 [CONSTRAINT]"))
            with self.assertRaises(ValueError):
                digest_crosscheck.build(repository)

    def test_context_failure_fixtures(self):
        result = validate_context_failures()
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["prepared"], ["SINGLE-050", "SINGLE-051", "SINGLE-144", "SINGLE-159", "SINGLE-147", "SINGLE-148", "SINGLE-052-01", "SINGLE-052-02", "SINGLE-053", "SINGLE-127-13"])
        self.assertEqual(result["core_execution"], "Not run")

    def test_proposed_adr_requires_is_a_type_constraint_not_a_state_check(self):
        """関係・トレースモデル §4・§5.1、`context` §3、診断レジストリ: 状態が`accepted`でないADRへの`requires`は、状態の診断
        （`CTX-STATE-001`、`blocked`）ではなく型制約の`CTX-RELATION-TYPE-001`（`failed`）で返す（実装の確認事項C17）。
        `SINGLE-148`は、独立した別の原因の状態の診断も併記し、状態は最悪値の`failed`とする。"""
        for identifier, codes in (("SINGLE-147", ["CTX-RELATION-TYPE-001"]),
                                  ("SINGLE-148", ["CTX-RELATION-TYPE-001", "CTX-STATE-001"])):
            with self.subTest(identifier=identifier):
                result = json.loads((audit.FIXTURES / f"single/{identifier}/expected/context.json").read_text())
                context_failure_fixtures.check_type_constraint(identifier, result)
                self.assertEqual([d["code"] for d in result["diagnostics"]], codes)
                self.assertEqual((result["status"], result["resolution"]["unresolvedStrongRelations"]), ("failed", 1))
                self.assertEqual(result["diagnostics"][0]["evidence"], "ADR-001")
        inputs = context_failure_fixtures.reviewed_documents("SINGLE-148")
        self.assertEqual([inputs[path][1]["status"] for path in (
            ".spec/requirements/REQ-002.md", ".spec/decisions/ADR-001.md")], ["draft", "proposed"])

    def test_type_constraint_contract_rejects_state_replacement_and_lost_diagnostics(self):
        """完全比較とは別に、`check_type_constraint`だけが、型制約の診断の状態の診断への置換、片方の診断の消去、重複、
        状態や未解決の件数の改変を拒否する（`SINGLE-147`、`SINGLE-148`）。"""
        def state(path=".spec/requirements/REQ-002.md"):
            return {"code": "CTX-STATE-001", "severity": "error", "resultStatus": "blocked",
                    "summary": "ADR-001は状態proposedのため目的implementに適用できません",
                    "source": {"kind": "file", "workspaceId": "root", "path": path}}

        def replace_first(v):
            v.update(status="blocked")
            v["diagnostics"][0] = state(".spec/decisions/ADR-001.md")

        changes = {
            "SINGLE-147": [
                replace_first,
                lambda v: v["diagnostics"].append(state(".spec/decisions/ADR-001.md")),
                lambda v: v["diagnostics"].insert(0, state(".spec/decisions/ADR-001.md")),
                lambda v: v.update(diagnostics=[]),
                lambda v: v.update(status="blocked"),
                lambda v: v["diagnostics"][0].update(resultStatus="blocked"),
                lambda v: v["diagnostics"][0].pop("evidence"),
                lambda v: v["diagnostics"][0].update(evidence="REQ-001"),
                lambda v: v["diagnostics"][0]["source"].pop("key"),
                lambda v: v["diagnostics"][0]["source"].update(path=".spec/decisions/ADR-001.md"),
                lambda v: v["resolution"].update(unresolvedStrongRelations=0),
                lambda v: v["resolution"].update(unresolvedStrongRelations=2),
                lambda v: v["resolution"].update(complete=True),
            ],
            "SINGLE-148": [
                replace_first,
                lambda v: v["diagnostics"].pop(),
                lambda v: v["diagnostics"].pop(0),
                lambda v: v["diagnostics"].reverse(),
                lambda v: v["diagnostics"].append(state(".spec/decisions/ADR-001.md")),
                lambda v: v["diagnostics"].append(copy.deepcopy(v["diagnostics"][0])),
                lambda v: v["diagnostics"][1].update(resultStatus="failed"),
                lambda v: v["diagnostics"][1]["source"].update(path=".spec/decisions/ADR-001.md"),
                lambda v: v.update(status="blocked"),
                lambda v: v["resolution"].update(unresolvedStrongRelations=2),
                lambda v: v["resolution"].update(unresolvedStrongRelations=0),
            ],
        }
        for identifier, mutations in changes.items():
            for index, mutate in enumerate(mutations):
                with self.subTest(identifier=identifier, index=index):
                    value = json.loads((audit.FIXTURES / f"single/{identifier}/expected/context.json").read_text())
                    context_failure_fixtures.check_type_constraint(identifier, value)
                    mutate(value)
                    with self.assertRaises(ValueError):
                        context_failure_fixtures.check_type_constraint(identifier, value)

    def test_context_failures_reject_partial_success_or_replacement(self):
        mutations = [
            ("SINGLE-050", "expected/context.json", lambda v: v["diagnostics"][0].update(source={"kind": "file", "path": ".spec/technical/TECH-001.md"})),
            ("SINGLE-050", "expected/context.json", lambda v: v.update(roots=["TECH-001"])),
            ("SINGLE-051", "expected/context.json", lambda v: v.update(status="passed")),
            ("SINGLE-051", "expected/context.json", lambda v: v["diagnostics"][0].update(code="CTX-STATE-001")),
            # 先行TASKが`cancelled`の起点は、`CTX-TASK-DEPENDENCY-001`だけを返す。同じ原因の`CTX-STATE-001`を重ねない
            # （診断レジストリの主診断の規則）。診断の置換、追加、状態の改変、`blocked`の取消しを拒否する。
            ("SINGLE-144", "expected/context.json", lambda v: v["diagnostics"][0].update(code="CTX-STATE-001")),
            ("SINGLE-144", "expected/context.json", lambda v: v["diagnostics"].append(dict(
                v["diagnostics"][0], code="CTX-STATE-001", summary="TASK-002は状態cancelledのため目的implementに適用できません",
                source={"kind": "file", "workspaceId": "root", "path": ".spec/tasks/TASK-002.md"}))),
            ("SINGLE-144", "expected/context.json", lambda v: v["diagnostics"].insert(0, dict(
                v["diagnostics"][0], code="CTX-STATE-001", summary="TASK-002は状態cancelledのため目的implementに適用できません",
                source={"kind": "file", "workspaceId": "root", "path": ".spec/tasks/TASK-002.md"}))),
            ("SINGLE-144", "expected/context.json", lambda v: v.update(status="passed_with_warnings")),
            ("SINGLE-144", "expected/context.json", lambda v: v.update(status="failed")),
            ("SINGLE-144", "expected/context.json", lambda v: v.update(diagnostics=[])),
            ("SINGLE-144", "expected/context.json", lambda v: v["diagnostics"][0]["source"].pop("key")),
            ("SINGLE-144", "expected/context.json", lambda v: v["resolution"].update(complete=True)),
            ("SINGLE-144", "manifest.json", lambda v: v["expect"].update(status="passed", exitCode=0)),
            ("SINGLE-144", "manifest.json", lambda v: v["expect"].update(exitCode=1)),
            # 状態`done`のTASKを目的`implement`の起点にすると、`CTX-STATE-001`（`blocked`）の1件だけを返す（実装の確認事項C13）。
            # 先行TASKの診断への置換と混入、置換済みの診断への置換、状態・終了コードの改変、診断の消去、発生元の取り違え、
            # 起点・目的・ハッシュ値・解決の状態の改変を拒否する。
            ("SINGLE-159", "expected/context.json", lambda v: v["diagnostics"][0].update(code="CTX-TASK-DEPENDENCY-001")),
            ("SINGLE-159", "expected/context.json", lambda v: v["diagnostics"][0].update(code="CTX-STATE-SUPERSEDED-001")),
            ("SINGLE-159", "expected/context.json", lambda v: v["diagnostics"].append(dict(
                v["diagnostics"][0], code="CTX-TASK-DEPENDENCY-001", summary="先行するTASK-002が状態openで、状態doneではありません",
                source={"kind": "file", "workspaceId": "root", "path": ".spec/tasks/TASK-001.md", "key": "relations.requires"}))),
            ("SINGLE-159", "expected/context.json", lambda v: v["diagnostics"].insert(0, dict(
                v["diagnostics"][0], code="CTX-TASK-DEPENDENCY-001", summary="先行するTASK-002が状態openで、状態doneではありません",
                source={"kind": "file", "workspaceId": "root", "path": ".spec/tasks/TASK-001.md", "key": "relations.requires"}))),
            ("SINGLE-159", "expected/context.json", lambda v: v["diagnostics"].append(copy.deepcopy(v["diagnostics"][0]))),
            ("SINGLE-159", "expected/context.json", lambda v: v.update(diagnostics=[])),
            ("SINGLE-159", "expected/context.json", lambda v: v.update(status="passed")),
            ("SINGLE-159", "expected/context.json", lambda v: v.update(status="failed")),
            ("SINGLE-159", "expected/context.json", lambda v: v.update(status="passed_with_warnings")),
            ("SINGLE-159", "expected/context.json", lambda v: v["diagnostics"][0].update(resultStatus="failed")),
            ("SINGLE-159", "expected/context.json", lambda v: v["diagnostics"][0]["source"].update(key="relations.requires")),
            ("SINGLE-159", "expected/context.json", lambda v: v["diagnostics"][0]["source"].update(path=".spec/requirements/REQ-001.md")),
            ("SINGLE-159", "expected/context.json", lambda v: v["diagnostics"][0]["source"].update(kind="invocation", argument="TASK-001")),
            ("SINGLE-159", "expected/context.json", lambda v: v.update(roots=["REQ-001"])),
            ("SINGLE-159", "expected/context.json", lambda v: v.update(purpose="verify")),
            ("SINGLE-159", "expected/context.json", lambda v: v.update(contextDigest="sha256:" + "0" * 64)),
            ("SINGLE-159", "expected/context.json", lambda v: v["resolution"].update(complete=True)),
            ("SINGLE-159", "expected/context.json", lambda v: v["resolution"].update(unresolvedStrongRelations=1)),
            ("SINGLE-159", "expected/context.json", lambda v: v["resolution"].update(documentCount=1)),
            ("SINGLE-159", "manifest.json", lambda v: v["expect"].update(status="passed", exitCode=0)),
            ("SINGLE-159", "manifest.json", lambda v: v["expect"].update(status="failed", exitCode=1)),
            ("SINGLE-159", "manifest.json", lambda v: v["expect"].update(exitCode=1)),
            ("SINGLE-159", "manifest.json", lambda v: v["invocation"]["argv"].__setitem__(3, "verify")),
            ("SINGLE-159", "manifest.json", lambda v: v["invocation"]["argv"].__setitem__(3, "interpret")),
            ("SINGLE-159", "manifest.json", lambda v: v["invocation"]["argv"].__setitem__(1, "REQ-001")),
            # 状態が`accepted`でないADRへの`requires`は、型制約の`CTX-RELATION-TYPE-001`（`failed`）で返す。状態の診断
            # （`CTX-STATE-001`、`blocked`）への置換、診断の消去、独立した原因の診断の消去、状態の改変を拒否する。
            ("SINGLE-147", "expected/context.json", lambda v: v["diagnostics"][0].update(
                code="CTX-STATE-001", resultStatus="blocked", summary="ADR-001は状態proposedのため目的implementに適用できません")),
            ("SINGLE-147", "expected/context.json", lambda v: v["diagnostics"][0].update(
                code="CTX-STATE-001", resultStatus="blocked", summary="ADR-001は状態proposedのため目的implementに適用できません",
                source={"kind": "file", "workspaceId": "root", "path": ".spec/decisions/ADR-001.md"})),
            ("SINGLE-147", "expected/context.json", lambda v: v.update(status="blocked")),
            ("SINGLE-147", "expected/context.json", lambda v: v.update(status="passed")),
            ("SINGLE-147", "expected/context.json", lambda v: v.update(diagnostics=[])),
            ("SINGLE-147", "expected/context.json", lambda v: v["diagnostics"][0].pop("evidence")),
            ("SINGLE-147", "expected/context.json", lambda v: v["diagnostics"][0]["source"].pop("key")),
            ("SINGLE-147", "expected/context.json", lambda v: v["resolution"].update(unresolvedStrongRelations=0)),
            ("SINGLE-147", "manifest.json", lambda v: v["expect"].update(status="blocked", exitCode=2)),
            ("SINGLE-147", "manifest.json", lambda v: v["expect"].update(exitCode=2)),
            ("SINGLE-148", "expected/context.json", lambda v: v["diagnostics"].pop()),
            ("SINGLE-148", "expected/context.json", lambda v: v["diagnostics"].pop(0)),
            ("SINGLE-148", "expected/context.json", lambda v: v["diagnostics"].reverse()),
            ("SINGLE-148", "expected/context.json", lambda v: v["diagnostics"].append(dict(
                v["diagnostics"][1], summary="ADR-001は状態proposedのため目的implementに適用できません",
                source={"kind": "file", "workspaceId": "root", "path": ".spec/decisions/ADR-001.md"}))),
            ("SINGLE-148", "expected/context.json", lambda v: v.update(status="blocked")),
            ("SINGLE-148", "expected/context.json", lambda v: v["resolution"].update(unresolvedStrongRelations=2)),
            ("SINGLE-148", "manifest.json", lambda v: v["expect"].update(status="blocked", exitCode=2)),
            ("SINGLE-148", "manifest.json", lambda v: v["expect"].update(exitCode=2)),
            ("SINGLE-052-01", "expected/context.json", lambda v: v.update(roots=["TECH-002"])),
            ("SINGLE-052-01", "expected/context.json", lambda v: v.update(contextDigest="sha256:" + "0" * 64)),
            ("SINGLE-052-02", "expected/context.json", lambda v: v["resolution"].update(complete=True)),
            ("SINGLE-052-02", "expected/context.json", lambda v: v["resolution"].update(documentCount=1)),
            ("SINGLE-052-02", "expected/context.json", lambda v: v["coverage"]["must"].update(total=["REQ-001:AC-01"])),
            ("SINGLE-053", "expected/context.json", lambda v: v["diagnostics"][0].update(code="CTX-STATE-SUPERSEDED-001")),
            ("SINGLE-053", "expected/context.json", lambda v: v["diagnostics"].append(copy.deepcopy(v["diagnostics"][0]))),
            ("SINGLE-053", "manifest.json", lambda v: v["invocation"]["argv"].__setitem__(3, "interpret")),
            ("SINGLE-053", "side-effects.json", lambda v: v["after"].update(git=None)),
            ("SINGLE-127-13", "manifest.json", lambda v: v["expect"].update(exitCode=4)),
            ("SINGLE-127-13", "expected/context.json", lambda v: v["diagnostics"][0]["source"].update(argument="TECH-001")),
            ("SINGLE-127-13", "expected/context.json", lambda v: v["resolution"].update(complete=True)),
        ]
        for identifier, relative, mutate in mutations:
            with self.subTest(identifier=identifier, relative=relative), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                fixture = root / "single" / identifier
                shutil.copytree(audit.FIXTURES / "single" / identifier, fixture)
                for name in ("manifest", "result", "side-effects", "frontmatter"):
                    shutil.copy2(schema_path(audit.FIXTURES, name), root)
                path = fixture / relative
                value = json.loads(path.read_text())
                mutate(value)
                path.write_text(json.dumps(value))
                self.assertTrue(validate_context_failures(root, [identifier])["errors"])

    def test_done_root_contract_is_a_state_check_not_a_dependency_check(self):
        """文書・フロントマター・状態仕様 §7、関係・トレースモデル §11: 状態`done`のTASKを目的`implement`の起点にすると`CTX-STATE-001`（`blocked`）。
        先行TASKがないので`CTX-TASK-DEPENDENCY-001`は返さない。`check_done_root`だけが、診断の置換と混入、発生元の取り違え、解決の状態の改変を拒否する。"""
        result = json.loads((audit.FIXTURES / "single/SINGLE-159/expected/context.json").read_text())
        context_failure_fixtures.check_done_root(result)
        self.assertEqual([d["code"] for d in result["diagnostics"]], ["CTX-STATE-001"])
        self.assertEqual((result["status"], result["purpose"], result["contextDigest"]), ("blocked", "implement", None))
        documents = context_failure_fixtures.reviewed_documents("SINGLE-159")
        context_failure_fixtures.check_done_root_inputs(documents)
        self.assertEqual(documents[".spec/tasks/TASK-001.md"][1]["status"], "done")
        self.assertNotIn("requires", documents[".spec/tasks/TASK-001.md"][1]["relations"])
        dependency = dict(result["diagnostics"][0], code="CTX-TASK-DEPENDENCY-001", summary="先行するTASK-002が状態openで、状態doneではありません")
        changes = [
            lambda v: v["diagnostics"][0].update(code="CTX-TASK-DEPENDENCY-001"),
            lambda v: v["diagnostics"].append(copy.deepcopy(dependency)),
            lambda v: v["diagnostics"].insert(0, copy.deepcopy(dependency)),
            lambda v: v["diagnostics"].append(copy.deepcopy(v["diagnostics"][0])),
            lambda v: v.update(diagnostics=[]),
            lambda v: v.update(status="failed"),
            lambda v: v["diagnostics"][0].update(resultStatus="failed"),
            lambda v: v["diagnostics"][0]["source"].update(key="relations.requires"),
            lambda v: v["diagnostics"][0]["source"].update(path=".spec/requirements/REQ-001.md"),
            lambda v: v.update(roots=["REQ-001"]),
            lambda v: v.update(purpose="verify"),
            lambda v: v.update(contextDigest="sha256:" + "0" * 64),
            lambda v: v["resolution"].update(complete=True),
            lambda v: v["resolution"].update(unresolvedStrongRelations=1),
            lambda v: v.update(documents=[{"id": "TASK-001"}]),
        ]
        for index, mutate in enumerate(changes):
            with self.subTest(index=index):
                value = copy.deepcopy(result)
                mutate(value)
                with self.assertRaises(ValueError):
                    context_failure_fixtures.check_done_root(value)
        for index, mutate in enumerate([
            lambda d: d[".spec/tasks/TASK-001.md"][1].update(status="open"),
            lambda d: d[".spec/tasks/TASK-001.md"][1]["relations"].update(requires=["TASK-002"]),
            lambda d: d[".spec/requirements/REQ-001.md"][1].update(status="draft"),
            lambda d: d.update({".spec/tasks/TASK-002.md": d[".spec/tasks/TASK-001.md"]}),
        ]):
            with self.subTest(input_index=index):
                value = copy.deepcopy(context_failure_fixtures.reviewed_documents("SINGLE-159"))
                mutate(value)
                with self.assertRaises(ValueError):
                    context_failure_fixtures.check_done_root_inputs(value)

    def test_context_failure_inputs_reject_repaired_or_changed_causes(self):
        mutations = [
            ("SINGLE-050", ".spec/technical/TECH-001.md", "TECH-001", "TECH-999"),
            ("SINGLE-051", ".spec/tasks/TASK-002.md", "status: open", "status: done"),
            # 先行TASKの状態を`done`や`open`へ直す、先行TASKへの`requires`を消す、起点の`addresses`を消す入力は、期待値と組にならない。
            ("SINGLE-144", ".spec/tasks/TASK-002.md", "status: cancelled", "status: done"),
            ("SINGLE-144", ".spec/tasks/TASK-002.md", "status: cancelled", "status: open"),
            ("SINGLE-144", ".spec/tasks/TASK-001.md", "requires: [TASK-002]", "related: [TASK-002]"),
            ("SINGLE-144", ".spec/tasks/TASK-001.md", "  addresses: [REQ-001:AC-01]\n", ""),
            # ADR-001を`accepted`へ直す、`requires`を消す、起点やREQ-002の状態を変える入力は、期待値と組にならない。
            ("SINGLE-147", ".spec/decisions/ADR-001.md", "status: proposed", "status: accepted"),
            ("SINGLE-147", ".spec/decisions/ADR-001.md", "status: proposed", "status: rejected"),
            ("SINGLE-147", ".spec/tasks/TASK-001.md", "requires: [ADR-001]", "related: [ADR-001]"),
            ("SINGLE-147", ".spec/tasks/TASK-001.md", "status: open", "status: done"),
            ("SINGLE-147", ".spec/requirements/REQ-001.md", "status: approved", "status: draft"),
            ("SINGLE-148", ".spec/decisions/ADR-001.md", "status: proposed", "status: accepted"),
            ("SINGLE-148", ".spec/requirements/REQ-002.md", "status: draft", "status: approved"),
            ("SINGLE-148", ".spec/requirements/REQ-001.md", "requires: [REQ-002, ADR-001]", "requires: [ADR-001]"),
            ("SINGLE-148", ".spec/requirements/REQ-001.md", "requires: [REQ-002, ADR-001]", "requires: [REQ-002]"),
            # TASK-001を`open`や`cancelled`へ直す、先行TASKへの`requires`を足す、`addresses`を消す、`addresses`の先を`draft`にする入力は、期待値と組にならない。
            ("SINGLE-159", ".spec/tasks/TASK-001.md", "status: done", "status: open"),
            ("SINGLE-159", ".spec/tasks/TASK-001.md", "status: done", "status: cancelled"),
            ("SINGLE-159", ".spec/tasks/TASK-001.md", "  addresses: [REQ-001:AC-01]\n", "  requires: [TASK-002]\n  addresses: [REQ-001:AC-01]\n"),
            ("SINGLE-159", ".spec/tasks/TASK-001.md", "  addresses: [REQ-001:AC-01]\n", ""),
            ("SINGLE-159", ".spec/requirements/REQ-001.md", "status: approved", "status: draft"),
            ("SINGLE-052-01", ".spec/technical/TECH-002.md", "supersedes:", "related:"),
            ("SINGLE-052-02", ".spec/technical/TECH-003.md", "requires:", "related:"),
            ("SINGLE-053", ".spec/technical/TECH-003.md", "status: approved", "status: draft"),
        ]
        for identifier, relative, before, after in mutations:
            with self.subTest(identifier=identifier), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                fixture = root / "single" / identifier
                shutil.copytree(audit.FIXTURES / "single" / identifier, fixture)
                for name in ("manifest", "result", "side-effects", "frontmatter"):
                    shutil.copy2(schema_path(audit.FIXTURES, name), root)
                path = fixture / "repo" / relative
                path.write_text(path.read_text().replace(before, after))
                self.assertTrue(validate_context_failures(root, [identifier])["errors"])

    def test_context_failure_git_state_rejects_staging_or_commit(self):
        for identifier in ("SINGLE-050", "SINGLE-051", "SINGLE-144", "SINGLE-159", "SINGLE-147", "SINGLE-148", "SINGLE-052-01", "SINGLE-052-02", "SINGLE-053"):
            with self.subTest(identifier=identifier), tempfile.TemporaryDirectory() as temporary:
                repo = fixture_setup(audit.FIXTURES / "single" / identifier, context_failure_manifest(identifier), Path(temporary) / "repo")
                check_context_unborn(repo, identifier)
                fixture_git(repo, "add", "-A")
                with self.assertRaises(ValueError):
                    check_context_unborn(repo, identifier)
                fixture_git(repo, "commit", "-m", "unexpected initial commit")
                with self.assertRaises(ValueError):
                    check_context_unborn(repo, identifier)

    def test_git_environment_fixtures(self):
        result = validate_git_environment()
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["prepared"], ["SINGLE-036", "SINGLE-037", "SINGLE-038"])
        self.assertEqual(result["core_execution"], "Not run")

    def test_cli_error_stream_contract(self):
        for reason in ("unknown revision", "基準版を解決できません"):
            check_cli_error_output(4, b"", ("bitz: check: " + reason + "\n").encode())
        for exit_code, stdout, stderr in (
            (1, b"", b"bitz: check: missing base\n"),
            (4, b"{}", b"bitz: check: missing base\n"),
            (4, b"\n", b"bitz: check: missing base\n"),
            (4, b"", b"bitz: check: \n"),
            (4, b"", b"bitz: check:    \n"),
            (4, b"", b"bitz: check: reason\nusage\n"),
            (4, b"", b"bitz: check: \x1b[31mreason\n"),
            (4, b"", b"bitz: check: reason\xff\n"),
            (4, b"", b"wrong prefix: reason\n"),
        ):
            with self.subTest(exit_code=exit_code, stdout=stdout, stderr=stderr), self.assertRaises(ValueError):
                check_cli_error_output(exit_code, stdout, stderr)

    def test_git_environment_rejects_corrupted_evidence(self):
        mutations = [
            ("SINGLE-036", "manifest.json", lambda v: v["expect"].update(status="error")),
            ("SINGLE-036", "cli-output.json", lambda v: v.update(stdout="{}")),
            ("SINGLE-036", "cli-output.json", lambda v: v.update(stderrLineCount=2)),
            ("SINGLE-036", "side-effects.json", lambda v: v["after"]["repository"].pop(".spec/reports/existing.json")),
            ("SINGLE-037", "manifest.json", lambda v: v["invocation"].update(env={})),
            ("SINGLE-037", "expected/check.json", lambda v: v.update(status="passed")),
            ("SINGLE-037", "side-effects.json", lambda v: v.update(before={**v["before"], "git": {"status": "", "index": ""}},
                after={**v["after"], "git": {"status": "", "index": ""}})),
            ("SINGLE-038", "expected/check.json", lambda v: v["diagnostics"][0].update(code="SPEC-GIT-DEGRADED-001")),
            ("SINGLE-038", "expected/check.json", lambda v: v["diagnostics"].append(copy.deepcopy(v["diagnostics"][0]))),
        ]
        for identifier, relative, mutate in mutations:
            with self.subTest(identifier=identifier, relative=relative), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                fixture = root / "single" / identifier
                shutil.copytree(audit.FIXTURES / "single" / identifier, fixture)
                for name in ("manifest", "result", "side-effects", "frontmatter"):
                    shutil.copy2(schema_path(audit.FIXTURES, name), root)
                path = fixture / relative
                value = json.loads(path.read_text())
                mutate(value)
                path.write_text(json.dumps(value))
                self.assertTrue(validate_git_environment(root, [identifier])["errors"])

    def test_git_environment_setup_rejects_resolvable_base_or_git_presence(self):
        for identifier in ("SINGLE-036", "SINGLE-037", "SINGLE-038"):
            with self.subTest(identifier=identifier), tempfile.TemporaryDirectory() as temporary:
                manifest = environment_manifest(identifier)
                repo = fixture_setup(audit.FIXTURES / "single" / identifier, manifest, Path(temporary) / "repo")
                check_environment(repo, identifier, manifest)
                if identifier == "SINGLE-036":
                    fixture_git(repo, "branch", "fixture-missing-base")
                else:
                    manifest["invocation"]["env"] = {"PATH": "/usr/bin"}
                    with self.assertRaises(ValueError):
                        check_environment(repo, identifier, manifest)
                    manifest = environment_manifest(identifier)
                    fixture_git(repo, "init", "--initial-branch=fixture")
                with self.assertRaises(ValueError):
                    check_environment(repo, identifier, manifest)

    def test_matrix_enforces_explicit_base_contract(self):
        for identifier, kind in (("SINGLE-040", "required"), ("SINGLE-037", "forbidden")):
            with self.subTest(identifier=identifier), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                fixture = root / "single" / identifier
                shutil.copytree(audit.FIXTURES / "single" / identifier, fixture)
                for name in ("manifest", "result"):
                    shutil.copy2(schema_path(audit.FIXTURES, name), root)
                path = fixture / "manifest.json"
                value = json.loads(path.read_text())
                argv = value["invocation"]["argv"]
                if kind == "required":
                    index = argv.index("--base")
                    del argv[index:index + 2]
                else:
                    argv.extend(["--base", "HEAD"])
                path.write_text(json.dumps(value))
                with patch.object(audit, "FIXTURES", root):
                    errors = audit.matrix()["errors"]
                self.assertTrue(any("明示の`--base`が必要です" in e or "`--base`を使えません" in e for e in errors), errors)

    def test_git_selection_fixtures(self):
        result = validate_selection()
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["prepared"], ["SINGLE-033", "SINGLE-039", "SINGLE-040", "SINGLE-041"])
        self.assertEqual(result["core_execution"], "Not run")

    def test_git_selection_rejects_corrupted_evidence(self):
        mutations = [
            ("SINGLE-033", "expected/check.json", lambda v: v.update(status="failed")),
            ("SINGLE-033", "expected/check.json", lambda v: v["diagnostics"].clear()),
            ("SINGLE-033", "expected/check.json", lambda v: v["diagnostics"][0]["source"].update(path=".spec/technical/TECH-003.md")),
            ("SINGLE-033", "expected/check.json", lambda v: v["diagnostics"].append({**copy.deepcopy(v["diagnostics"][0]),
                "source": {"kind": "file", "workspaceId": "root", "path": ".spec/technical/TECH-004.md"}})),
            ("SINGLE-039", "expected/check.json", lambda v: v.update(revision={"base": "0" * 40, "commit": "0" * 40, "dirty": True})),
            ("SINGLE-039", "expected/check.json", lambda v: v["diagnostics"].append({"code": "SPEC-GIT-DEGRADED-001",
                "severity": "warning", "resultStatus": "passed_with_warnings", "summary": "Git不在",
                "source": {"kind": "environment", "component": "git", "identifier": "git"}})),
            ("SINGLE-039", "manifest.json", lambda v: v["invocation"]["argv"].extend(["--base", "HEAD"])),
            ("SINGLE-040", "expected/check.json", lambda v: v["selection"].update(targetDocumentCount=1)),
            ("SINGLE-040", "expected/check.json", lambda v: v["revision"].update(dirty=True)),
            ("SINGLE-041", "expected/check.json", lambda v: v["selection"].update(changedPathCount=1)),
            ("SINGLE-041", "expected/check.json", lambda v: v["selection"].update(excludedCodeTestPathCount=0)),
            ("SINGLE-041", "manifest.json", lambda v: v["setup"]["operations"].pop(1)),
            ("SINGLE-041", "side-effects.json", lambda v: v["after"]["git"].update(status="")),
        ]
        for identifier, relative, mutate in mutations:
            with self.subTest(identifier=identifier, relative=relative), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                fixture = root / "single" / identifier
                shutil.copytree(audit.FIXTURES / "single" / identifier, fixture)
                for name in ("manifest", "result", "side-effects", "frontmatter"):
                    shutil.copy2(schema_path(audit.FIXTURES, name), root)
                path = fixture / relative
                value = json.loads(path.read_text())
                mutate(value)
                path.write_text(json.dumps(value))
                self.assertTrue(validate_selection(root, [identifier])["errors"])

    def test_selection_inputs_reject_changed_causes(self):
        mutations = [
            ("SINGLE-033", "repo/.spec/technical/TECH-002.md", "requires:", "related:"),
            ("SINGLE-033", "repo/.spec/technical/TECH-003.md", "related:", "requires:"),
            ("SINGLE-033", "changes/tech.md", "改訂した前提技術", "前提技術"),
            ("SINGLE-041", "repo/.spec/technical/TECH-001.md", "status: approved", "status: approved\nimplements: [src/unowned.py]"),
        ]
        for identifier, relative, before, after in mutations:
            with self.subTest(identifier=identifier, relative=relative), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                fixture = root / "single" / identifier
                shutil.copytree(audit.FIXTURES / "single" / identifier, fixture)
                for name in ("manifest", "result", "side-effects", "frontmatter"):
                    shutil.copy2(schema_path(audit.FIXTURES, name), root)
                path = fixture / relative
                path.write_text(path.read_text().replace(before, after))
                self.assertTrue(validate_selection(root, [identifier])["errors"])

    def test_selection_git_state_rejects_unborn_commit_or_index_changes(self):
        for identifier in ("SINGLE-033", "SINGLE-039", "SINGLE-040", "SINGLE-041"):
            with self.subTest(identifier=identifier), tempfile.TemporaryDirectory() as temporary:
                repository = fixture_setup(audit.FIXTURES / "single" / identifier, selection_manifest(identifier), Path(temporary) / "repo")
                check_selection_git_states(repository, identifier)
                if identifier == "SINGLE-040":
                    (repository / "unexpected.py").write_text("# new change\n")
                fixture_git(repository, "add", "-A")
                if identifier == "SINGLE-039":
                    with self.assertRaises(ValueError):
                        check_selection_git_states(repository, identifier)
                    fixture_git(repository, "commit", "-m", "incorrect initial commit")
                with self.assertRaises(ValueError):
                    check_selection_git_states(repository, identifier)

    def test_task_scope_fixtures(self):
        result = validate_tasks()
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["prepared"], ["SINGLE-034", "SINGLE-035-01", "SINGLE-035-02"])
        self.assertEqual(result["core_execution"], "Not run")

    def test_task_scope_rejects_corrupted_evidence(self):
        mutations = [
            ("SINGLE-034", "expected/check.json", lambda v: v.update(status="passed")),
            ("SINGLE-034", "expected/check.json", lambda v: v["diagnostics"][0]["source"].update(path="src/inside.py")),
            ("SINGLE-034", "manifest.json", lambda v: v["invocation"]["argv"].remove("TASK-001")),
            ("SINGLE-035-01", "expected/check.json", lambda v: v["selection"].update(targetDocumentCount=0)),
            ("SINGLE-035-01", "expected/check.json", lambda v: v["selection"].update(excludedCodeTestPathCount=0)),
            ("SINGLE-035-02", "expected/check.json", lambda v: v.update(checkedStatementCount=1)),
            ("SINGLE-035-02", "expected/check.json", lambda v: v["diagnostics"].append({
                "code": "SPEC-TASK-BOUNDARY-001", "severity": "warning", "resultStatus": "passed_with_warnings",
                "summary": "境界未実施", "source": {"kind": "file", "workspaceId": "root", "path": "src2/outside.py"}})),
            ("SINGLE-035-02", "side-effects.json", lambda v: v["after"]["git"].update(status="")),
        ]
        for identifier, relative, mutate in mutations:
            with self.subTest(identifier=identifier, relative=relative), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                fixture = root / "single" / identifier
                shutil.copytree(audit.FIXTURES / "single" / identifier, fixture)
                for name in ("manifest", "result", "side-effects", "frontmatter"):
                    shutil.copy2(schema_path(audit.FIXTURES, name), root)
                path = fixture / relative
                value = json.loads(path.read_text())
                mutate(value)
                path.write_text(json.dumps(value))
                self.assertTrue(validate_tasks(root, [identifier])["errors"])

    def test_task_inputs_reject_widened_permission_and_missing_selection(self):
        for relative, before, after in [
            ("repo/.spec/tasks/TASK-001.md", "changes: [src/]", "changes: [src/, src2/]"),
            ("changes/task.md", "説明を補足する。", ""),
        ]:
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                fixture = root / "single/SINGLE-035-01"
                shutil.copytree(audit.FIXTURES / "single/SINGLE-035-01", fixture)
                for name in ("manifest", "result", "side-effects", "frontmatter"):
                    shutil.copy2(schema_path(audit.FIXTURES, name), root)
                path = fixture / relative
                path.write_text(path.read_text().replace(before, after))
                self.assertTrue(validate_tasks(root, ["SINGLE-035-01"])["errors"])

    def test_task_git_state_rejects_staged_or_committed_changes(self):
        for action in ("stage", "commit"):
            with self.subTest(action=action), tempfile.TemporaryDirectory() as temporary:
                repository = fixture_setup(audit.FIXTURES / "single/SINGLE-034", task_manifest("SINGLE-034"), Path(temporary) / "repo")
                check_task_git_states(repository)
                fixture_git(repository, "add", "-A")
                if action == "commit":
                    fixture_git(repository, "commit", "-m", "incorrect base")
                with self.assertRaises(ValueError):
                    check_task_git_states(repository)

    def test_git_transition_fixtures(self):
        result = validate_git_fixtures()
        self.assertEqual(result["errors"], [])
        self.assertEqual(len(result["prepared"]), 10)
        self.assertEqual(result["core_execution"], "Not run")

    def test_git_fixtures_reject_corrupted_evidence(self):
        mutations = [
            ("SINGLE-027", "expected/check.json", lambda v: v.update(status="passed")),
            ("SINGLE-028", "expected/check.json", lambda v: v["revision"].update(dirty=False)),
            ("SINGLE-029", "expected/check.json", lambda v: v.update(checkedDocumentCount=1)),
            ("SINGLE-030", "manifest.json", lambda v: v["setup"]["operations"].pop()),
            ("SINGLE-031", "expected/check.json", lambda v: v["diagnostics"][0].update(code="SPEC-STYLE-H1-001")),
            ("SINGLE-031", "side-effects.json", lambda v: v["after"]["git"].update(status="")),
            ("SINGLE-032-01", "expected/check.json", lambda v: v.update(status="failed")),
            ("SINGLE-032-02", "expected/check.json", lambda v: v.update(checkedStatementCount=0)),
            ("SINGLE-032-03", "expected/check.json", lambda v: v.update(checkedDocumentCount=1)),
            ("SINGLE-032-04", "expected/check.json", lambda v: v["diagnostics"].append({"code": "SPEC-FM-UNKNOWN-001",
                "severity": "warning", "resultStatus": "passed_with_warnings", "summary": "unexpected warning",
                "source": {"kind": "file", "workspaceId": "root", "path": ".spec/requirements/REQ-001.md"}})),
            ("SINGLE-032-05", "expected/check.json", lambda v: v["revision"].update(dirty=False)),
        ]
        for identifier, relative, mutate in mutations:
            with self.subTest(identifier=identifier), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                fixture = root / "single" / identifier
                shutil.copytree(audit.FIXTURES / "single" / identifier, fixture)
                for name in ("manifest", "result", "side-effects", "frontmatter"):
                    shutil.copy2(schema_path(audit.FIXTURES, name), root)
                path = fixture / relative
                value = json.loads(path.read_text())
                mutate(value)
                path.write_text(json.dumps(value))
                self.assertTrue(validate_git_fixtures(root, [identifier])["errors"])

    def test_git_state_audit_rejects_staging_or_committing_changes(self):
        for identifier in ("SINGLE-027", "SINGLE-028", "SINGLE-029", "SINGLE-030", "SINGLE-031",
                           "SINGLE-032-01", "SINGLE-032-02", "SINGLE-032-03", "SINGLE-032-04", "SINGLE-032-05"):
            with self.subTest(identifier=identifier), tempfile.TemporaryDirectory() as temporary:
                repo = fixture_setup(audit.FIXTURES / "single" / identifier, git_manifest(identifier), Path(temporary) / "repo")
                check_git_states(repo, identifier)
                fixture_git(repo, "add", "-A")
                if identifier == "SINGLE-030":
                    fixture_git(repo, "commit", "-m", "incorrect new base")
                with self.assertRaises(ValueError):
                    check_git_states(repo, identifier)

    def test_exempt_changes_reject_additional_causes(self):
        for identifier, mutation in [("SINGLE-032-01", "missing-implementation"), ("SINGLE-032-02", "bad-covers"),
                ("SINGLE-032-03", "strong-relation"), ("SINGLE-032-04", "unknown-key"), ("SINGLE-032-05", "meaning-change")]:
            with self.subTest(identifier=identifier), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                fixture = root / "single" / identifier
                shutil.copytree(audit.FIXTURES / "single" / identifier, fixture)
                for name in ("manifest", "result", "side-effects", "frontmatter"):
                    shutil.copy2(schema_path(audit.FIXTURES, name), root)
                path = fixture / "changes/document.md"
                if mutation == "missing-implementation":
                    (fixture / "repo/src/contract.py").unlink()
                else:
                    before, after = {"bad-covers": ("covers: [REQ-001:AC-01]", "covers: [REQ-001:AC-99]"),
                        "strong-relation": ("related:", "requires:"), "unknown-key": ("x-risk:", "risk:"),
                        "meaning-change": ("秘密情報を出力しない", "秘密情報を出力する")}[mutation]
                    path.write_text(path.read_text().replace(before, after))
                self.assertTrue(validate_git_fixtures(root, [identifier])["errors"])

    def test_graph_fixtures(self):
        result = validate_graph()
        self.assertEqual(result["errors"], [])
        self.assertEqual(len(result["prepared"]), 4)
        self.assertEqual(result["core_execution"], "Not run")

    def test_graph_rejects_corrupted_evidence(self):
        mutations = [
            ("SINGLE-015", lambda v: v.update(checkedDocumentCount=1)),
            ("SINGLE-015", lambda v: v["diagnostics"].append(copy.deepcopy(v["diagnostics"][0]))),
            ("SINGLE-015", lambda v: v["diagnostics"][0].update(suggestedAction="TECH-002へ改番")),
            ("SINGLE-022-01", lambda v: v["diagnostics"][0].update(code="SPEC-RELATION-MISSING-001")),
            ("SINGLE-022-02", lambda v: v["diagnostics"][0]["source"].update(key="relations.requires")),
            ("SINGLE-022-03", lambda v: v.update(status="failed")),
            ("SINGLE-022-03", lambda v: v.update(checkedDocumentCount=0)),
        ]
        for identifier, mutate in mutations:
            with self.subTest(identifier=identifier), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                fixture = root / "single" / identifier
                shutil.copytree(audit.FIXTURES / "single" / identifier, fixture)
                for name in ("manifest", "result", "side-effects", "frontmatter"):
                    shutil.copy2(schema_path(audit.FIXTURES, name), root)
                path = fixture / "expected/check.json"
                value = json.loads(path.read_text())
                mutate(value)
                path.write_text(json.dumps(value))
                self.assertTrue(validate_graph(root, [identifier])["errors"])

    def test_graph_rejects_changed_cause_and_side_effects(self):
        for identifier, mutation in [("SINGLE-015", "remove-duplicate"), ("SINGLE-022-01", "missing-target"),
                ("SINGLE-022-02", "weak-edge"), ("SINGLE-022-03", "cache-write")]:
            with self.subTest(identifier=identifier), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                fixture = root / "single" / identifier
                shutil.copytree(audit.FIXTURES / "single" / identifier, fixture)
                for name in ("manifest", "result", "side-effects", "frontmatter"):
                    shutil.copy2(schema_path(audit.FIXTURES, name), root)
                path = fixture / "repo/.spec/technical/TECH-001.md"
                if mutation == "remove-duplicate":
                    (fixture / "repo/.spec/technical/TECH-001-b.md").unlink()
                elif mutation == "missing-target":
                    path.write_text(path.read_text().replace("requires: [TECH-001]", "requires: [TECH-999]"))
                elif mutation == "weak-edge":
                    path.write_text(path.read_text().replace("refines:", "related:"))
                else:
                    path = fixture / "side-effects.json"
                    value = json.loads(path.read_text())
                    value["after"]["cache"]["unexpected"] = {"kind": "directory"}
                    path.write_text(json.dumps(value))
                self.assertTrue(validate_graph(root, [identifier])["errors"])

    def test_trace_fixtures(self):
        result = validate_trace()
        self.assertEqual(result["errors"], [])
        self.assertEqual(len(result["prepared"]), 7)
        self.assertEqual(result["core_execution"], "Not run")

    def test_trace_rejects_corrupted_evidence(self):
        mutations = [
            ("SINGLE-020", "expected/check.json", lambda v: v["diagnostics"].append(copy.deepcopy(v["diagnostics"][0]))),
            ("SINGLE-021", "expected/check.json", lambda v: v["diagnostics"][0].update(code="SPEC-RELATION-MISSING-001")),
            ("SINGLE-023", "expected/check.json", lambda v: v.update(checkedDocumentCount=1)),
            ("SINGLE-024", "expected/check.json", lambda v: v["diagnostics"][0].update(severity="warning")),
            ("SINGLE-025", "expected/check.json", lambda v: v.update(status="failed")),
            ("SINGLE-026", "expected/check.json", lambda v: v["diagnostics"][0]["source"].update(key="tests[0].path")),
            ("SINGLE-026", "manifest.json", lambda v: v["invocation"]["argv"].append("--report")),
            ("SINGLE-024", "side-effects.json", lambda v: v["after"]["cache"].update(unexpected={"kind": "directory"})),
        ]
        for identifier, relative, mutate in mutations:
            with self.subTest(identifier=identifier, relative=relative), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                shutil.copytree(audit.FIXTURES / "single" / identifier, root / "single" / identifier)
                for name in ("manifest", "result", "side-effects", "frontmatter"):
                    shutil.copy2(schema_path(audit.FIXTURES, name), root)
                path = root / "single" / identifier / relative
                value = json.loads(path.read_text())
                mutate(value)
                path.write_text(json.dumps(value))
                self.assertTrue(validate_trace(root, [identifier])["errors"])

    def test_trace_rejects_missing_or_additional_causes(self):
        cases = [("SINGLE-020", "resolve"), ("SINGLE-021", "remove-target"), ("SINGLE-023", "convert-refs"),
                 ("SINGLE-024", "create-path"), ("SINGLE-025", "approve"), ("SINGLE-026", "remove-test"),
                 ("SINGLE-026", "repair-covers"), ("SINGLE-026", "remove-command")]
        for identifier, mutation in cases:
            with self.subTest(identifier=identifier, mutation=mutation), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                fixture = root / "single" / identifier
                shutil.copytree(audit.FIXTURES / "single" / identifier, fixture)
                for name in ("manifest", "result", "side-effects", "frontmatter"):
                    shutil.copy2(schema_path(audit.FIXTURES, name), root)
                repo = fixture / "repo"
                req = repo / ".spec/requirements/REQ-001.md"
                if mutation == "resolve":
                    req.with_name("REQ-999.md").write_text(req.read_text().replace("REQ-001", "REQ-999"))
                elif mutation == "remove-target":
                    (repo / ".spec/technical/TECH-001.md").unlink()
                elif mutation == "convert-refs":
                    req.write_text(req.read_text().replace("refs: [TECH-001]", "relations:\n  requires: [TECH-001]"))
                elif mutation == "create-path":
                    (repo / "src").mkdir()
                    (repo / "src/missing.py").write_text("pass\n")
                elif mutation == "approve":
                    req.write_text(req.read_text().replace("status: draft", "status: approved"))
                elif mutation == "remove-test":
                    (repo / "tests/test_contract.py").unlink()
                elif mutation == "repair-covers":
                    req.write_text(req.read_text().replace("AC-99", "AC-01"))
                else:
                    config = repo / ".spec/bitz.yaml"
                    config.write_text(config.read_text().split("verify:")[0])
                self.assertTrue(validate_trace(root, [identifier])["errors"])

    def test_document_fixtures(self):
        result = validate_documents()
        self.assertEqual(result["errors"], [])
        self.assertEqual(len(result["prepared"]), 9)
        self.assertEqual(result["core_execution"], "Not run")

    def test_documents_reject_corrupted_evidence(self):
        mutations = [
            ("SINGLE-014", "expected/check.json", lambda v: v["diagnostics"][0]["source"].update(path=".spec/requirements/REQ-001.md")),
            ("SINGLE-016", "expected/check.json", lambda v: v.update(checkedDocumentCount=1)),
            ("SINGLE-017-01", "expected/check.json", lambda v: v.update(checkedDocumentCount=0)),
            ("SINGLE-017-02", "expected/check.json", lambda v: v["diagnostics"][0].update(code="SPEC-REQ-STATEMENT-001")),
            ("SINGLE-017-03", "expected/check.json", lambda v: v.update(checkedStatementCount=1)),
            ("SINGLE-018-01", "expected/check.json", lambda v: v.update(status="passed_with_warnings")),
            ("SINGLE-018-02", "manifest.json", lambda v: v["invocation"]["argv"].append("--report")),
            ("SINGLE-018-03", "side-effects.json", lambda v: v["after"]["home"].update(unexpected={"kind": "directory"})),
            ("SINGLE-019", "expected/check.json", lambda v: v.update(status="error")),
        ]
        for identifier, relative, mutate in mutations:
            with self.subTest(identifier=identifier), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                shutil.copytree(audit.FIXTURES / "single" / identifier, root / "single" / identifier)
                for name in ("manifest", "result", "side-effects", "frontmatter"):
                    shutil.copy2(schema_path(audit.FIXTURES, name), root)
                path = root / "single" / identifier / relative
                value = json.loads(path.read_text())
                mutate(value)
                path.write_text(json.dumps(value))
                self.assertTrue(validate_documents(root, [identifier])["errors"])

    def test_documents_reject_repaired_input_and_extra_cause(self):
        for mutation in ("repair-utf8", "extra-document", "config"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                identifier = "SINGLE-019"
                fixture = root / "single" / identifier
                shutil.copytree(audit.FIXTURES / "single" / identifier, fixture)
                for name in ("manifest", "result", "side-effects", "frontmatter"):
                    shutil.copy2(schema_path(audit.FIXTURES, name), root)
                path = fixture / "repo/.spec/requirements/REQ-001.md"
                if mutation == "repair-utf8":
                    path.write_bytes(path.read_bytes().replace(b"\xff", "�".encode()))
                elif mutation == "extra-document":
                    path.with_name("REQ-002.md").write_text("another cause")
                else:
                    (fixture / "repo/.spec/bitz.yaml").write_text("schemaVersion: 2\n")
                self.assertTrue(validate_documents(root, [identifier])["errors"])

    def test_ears_fixtures(self):
        result = validate_ears()
        self.assertEqual(result["errors"], [])
        self.assertEqual(len(result["prepared"]), 17)
        self.assertEqual(result["core_execution"], "Not run")

    def test_ears_rejects_corrupted_expectations(self):
        mutations = [
            ("SINGLE-007", lambda value: value["diagnostics"][0]["source"].update(column=71)),
            ("SINGLE-008", lambda value: value["diagnostics"][0].update(severity="error")),
            ("SINGLE-009-01", lambda value: value.update(diagnostics=[])),
            ("SINGLE-009-02", lambda value: value.update(checkedDocumentCount=1)),
            ("SINGLE-009-03", lambda value: value["diagnostics"][0]["source"].update(line=15)),
            ("SINGLE-010-01", lambda value: value.update(checkedStatementCount=2)),
            ("SINGLE-010-02", lambda value: value.update(status="failed")),
            ("SINGLE-011", lambda value: value["diagnostics"][0].update(severity="warning")),
            ("SINGLE-012-01", lambda value: value["diagnostics"][0].update(code="EAI-CORE-SYNTAX-002")),
            ("SINGLE-012-02", lambda value: value["diagnostics"][0]["source"].update(column=3)),
            ("SINGLE-012-03", lambda value: value["diagnostics"][0]["source"].update(column=78)),
            ("SINGLE-013", lambda value: value.update(checkedStatementCount=1)),
            ("SINGLE-128", lambda value: value["diagnostics"][0].update(summary="規範文IDの形式が不正です")),
            ("SINGLE-130", lambda value: value.update(diagnostics=[])),
            ("SINGLE-132", lambda value: value.update(checkedStatementCount=1)),
        ]
        for identifier, mutate in mutations:
            with self.subTest(identifier=identifier), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                shutil.copytree(audit.FIXTURES / "single" / identifier, root / "single" / identifier)
                for name in ("manifest", "result", "side-effects", "frontmatter"):
                    shutil.copy2(schema_path(audit.FIXTURES, name), root)
                path = root / "single" / identifier / "expected/check.json"
                value = json.loads(path.read_text())
                mutate(value)
                path.write_text(json.dumps(value))
                self.assertTrue(validate_ears(root, [identifier])["errors"])

    def test_ears_rejects_removed_valid_statement(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            identifier = "SINGLE-007"
            shutil.copytree(audit.FIXTURES / "single" / identifier, root / "single" / identifier)
            for name in ("manifest", "result", "side-effects", "frontmatter"):
                shutil.copy2(schema_path(audit.FIXTURES, name), root)
            path = root / "single" / identifier / "repo/.spec/requirements/REQ-001.md"
            path.write_text("\n".join(line for line in path.read_text().splitlines() if not line.startswith("- [REQ-001:AC-01]")) + "\n")
            self.assertTrue(validate_ears(root, [identifier])["errors"])

    def test_initial_fixtures(self):
        result = validate_initial()
        self.assertEqual(result["errors"], [])
        self.assertEqual(len(result["prepared"]), 9)
        self.assertEqual(result["core_execution"], "Not run")

    def test_initial_fixture_rejects_corrupted_evidence(self):
        mutations = [
            ("SINGLE-004-01/expected/check.json", lambda value: value.update(status="passed")),
            ("SINGLE-004-02/expected/check.json", lambda value: value["diagnostics"][0]["source"].update(key="language")),
            ("SINGLE-003/manifest.json", lambda value: value["invocation"]["argv"].remove("--full")),
            ("SINGLE-001/side-effects.json", lambda value: value["after"]["cache"].update(lock={"kind": "directory"})),
            ("SINGLE-001/side-effects.json", lambda value: value["before"]["repository"][".spec/bitz.yaml"].update(sha256="0" * 64)),
            ("SINGLE-002/expected/doctor.json", lambda value: value["diagnostics"][0].pop("suggestedAction")),
            ("SINGLE-005-01/expected/check.json", lambda value: value["diagnostics"][0].update(severity="error")),
            ("SINGLE-005-02/expected/check.json", lambda value: value["diagnostics"].append(copy.deepcopy(value["diagnostics"][0]))),
            ("SINGLE-006-01/expected/doctor.json", lambda value: value["diagnostics"][0]["source"].update(key="verify.commands.default.cwd")),
            ("SINGLE-006-01/expected/doctor.json", lambda value: value["diagnostics"][0].pop("suggestedAction")),
            ("SINGLE-006-02/expected/doctor.json", lambda value: value["diagnostics"][0].pop("suggestedAction")),
            # 修復手順の文字列は、承認済みの文言の差し替え（条件の取り違え）も拒否する。
            ("SINGLE-006-01/expected/doctor.json", lambda value: value["diagnostics"][0].update(
                suggestedAction="設定キーverify.commands.default.cwdのディレクトリを作成するか、正しいパスを指定してください")),
            ("SINGLE-006-02/expected/doctor.json", lambda value: value["checks"][6].update(status="passed")),
        ]
        for relative, mutate in mutations:
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                shutil.copytree(audit.FIXTURES / "single", root / "single")
                for name in ("manifest", "result", "side-effects"):
                    shutil.copy2(schema_path(audit.FIXTURES, name), root)
                path = root / "single" / relative
                value = json.loads(path.read_text())
                mutate(value)
                path.write_text(json.dumps(value))
                self.assertTrue(validate_initial(root)["errors"])

    def test_command_cases_reject_additional_or_missing_causes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            check_command_preconditions("SINGLE-006-01", root)
            check_command_preconditions("SINGLE-006-02", root)
            with self.assertRaises(ValueError):
                check_command_preconditions("SINGLE-006-02", root, root / "absent-executable")
            with patch("conformance.initial_fixtures.os.access", return_value=False):
                with self.assertRaises(ValueError):
                    check_command_preconditions("SINGLE-006-02", root)
            (root / "missing-command").write_text("unexpected")
            with self.assertRaises(ValueError):
                check_command_preconditions("SINGLE-006-01", root)
            (root / "missing-directory").mkdir()
            with self.assertRaises(ValueError):
                check_command_preconditions("SINGLE-006-02", root)

    def test_side_effect_comparison_rejects_each_changed_boundary(self):
        state = json.loads((audit.FIXTURES / "single/SINGLE-001/side-effects.json").read_text())["after"]
        for name in ("repository", "home", "cache", "temporary"):
            changed = copy.deepcopy(state)
            changed[name]["unexpected"] = {"kind": "directory"}
            self.assertEqual(compare_state(state, changed), [name])
        changed = copy.deepcopy(state)
        changed["git"]["index"] = "changed index"
        self.assertEqual(compare_state(state, changed), ["git"])

    def test_target_vectors(self):
        data = json.loads((TARGET_HERE / "targets/cases.json").read_text())
        self.assertEqual(validate_targets(data)["errors"], [])
        missing = copy.deepcopy(data)
        missing["cases"] = [c for c in missing["cases"] if c["id"] != "BASIC-ADR-verify"]
        self.assertTrue(validate_targets(missing)["errors"])
        leaked = copy.deepcopy(data)
        case = next(c for c in leaked["cases"] if c["id"] == "REFINEMENT-TRANSITIVE")
        case["expected"]["targetStatements"].append("REQ-009:AC-01")
        self.assertTrue(validate_targets(leaked)["errors"])
        wrong_order = copy.deepcopy(data)
        case = next(c for c in wrong_order["cases"] if c["id"] == "SOURCE-LINE-ORDER")
        case["expected"]["targetStatements"].reverse()
        self.assertTrue(validate_targets(wrong_order)["errors"])
        bad_id = copy.deepcopy(data)
        bad_id["cases"][0]["graph"][0]["requires"] = ["REQ-999"]
        self.assertTrue(validate_targets(bad_id)["errors"])
        stale = copy.deepcopy(data)
        stale["contractSha256"] = "0" * 64
        self.assertTrue(validate_targets(stale)["errors"])
        wrong_kind = copy.deepcopy(data)
        wrong_kind["cases"][0]["rootKind"] = "TASK"
        self.assertTrue(validate_targets(wrong_kind)["errors"])

    def test_diagnostic_ledger_rejects_missing_unknown_and_stale(self):
        original = json.loads(LEDGER.read_text())
        self.assertEqual(validate(original)["errors"], [])
        self.assertEqual(validate(original)["semantic_coverage"], "Passed")
        missing = copy.deepcopy(original)
        missing["groups"][0]["conditionIds"].pop()
        self.assertTrue(validate(missing)["errors"])
        unknown = copy.deepcopy(original)
        unknown["groups"][0]["conditionIds"].append("UNKNOWN-CONDITION")
        self.assertTrue(validate(unknown)["errors"])
        stale = copy.deepcopy(original)
        stale["sources"][next(iter(stale["sources"]))] = "0" * 64
        self.assertTrue(validate(stale)["errors"])
        false_pass = copy.deepcopy(original)
        false_pass["reviewStatus"] = "Passed"
        false_pass["openIssues"] = ["UNRESOLVED-CONDITION"]
        self.assertTrue(validate(false_pass)["errors"])
        pending = copy.deepcopy(false_pass)
        pending["reviewStatus"] = "Pending"
        self.assertEqual(validate(pending)["semantic_coverage"], "Pending")

    def test_invalid_public_result_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "result.md").write_text('```json\n{"operation":"check"}\n```\n')
            with patch.object(audit, "DETAIL", root), patch.object(audit, "ROOT", root):
                result = audit.public_json()
            self.assertEqual(len(result["errors"]), 1)

    def test_ir_operation_is_not_a_core_result(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "ir.md").write_text('```json\n{"operation":{"kind":"THEN","text":"example"}}\n```\n')
            with patch.object(audit, "DETAIL", root), patch.object(audit, "ROOT", root):
                result = audit.public_json()
            self.assertEqual(result["errors"], [])
            self.assertEqual(len(result["non_public_result_examples"]), 1)

    def test_unknown_nonterminal_detected(self):
        with patch.object(audit, "blocks", return_value=['statement = missing, "literal" ;']):
            result = audit.grammar()
        self.assertEqual(result["errors"], ["missing"])

    def test_missing_fixture_detected(self):
        result = audit.matrix()
        self.assertGreater(result["matrix_ids"], 0)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            # 実際のスキーマは残し、受入fixtureのディレクトリは置かない。
            for name in ("manifest", "result"):
                (root / f"{name}.schema.json").write_text(schema_path(audit.FIXTURES, name).read_text())
            with patch.object(audit, "FIXTURES", root):
                missing = audit.matrix()
        self.assertEqual(len(missing["missing_fixtures"]), missing["matrix_ids"])

    def test_fixture_coverage_requires_a_verified_family_for_every_matrix_id(self):
        ids = [identifier for identifier, _ in audit.matrix_rows()]
        complete = {"a_fixtures": {"prepared": ids[:10]}, "b_fixtures": {"prepared": ids[10:]}, "links": {"errors": []}}
        self.assertEqual(audit.fixture_coverage(complete)["status"], "Passed")
        # 検証に失敗したfixtureは`prepared`へ入らない。ディレクトリが存在しても網羅とは数えない。
        dropped = audit.fixture_coverage({"a_fixtures": {"prepared": ids[:10]}, "b_fixtures": {"prepared": ids[11:]}})
        self.assertEqual(dropped["status"], "Failed")
        self.assertEqual(len(dropped["errors"]), 1)
        self.assertTrue(dropped["errors"][0].startswith(f"{ids[10]}: "))
        unknown = audit.fixture_coverage({"a_fixtures": {"prepared": ids + ["SINGLE-999"]}})
        self.assertEqual(unknown["status"], "Failed")
        with patch.object(audit, "matrix_rows", return_value=[]):
            self.assertEqual(audit.fixture_coverage({})["status"], "Failed")

    def test_step_assignment_matches_the_plan(self):
        result = step_assignment.validate()
        self.assertEqual(result["errors"], [])
        ids = step_assignment.matrix_ids()
        # 枝番だけの終端は同じファミリーの枝番の範囲、3桁どうしはファミリーの範囲として読む。
        text = "## 4. Step 1\n\n完了条件は、`SINGLE-127-05`〜`07`、`070`〜`071`が通過する。\n"
        for heading in ("## 5. Step 2", "## 6. Step 3", "## 7. Step 4", "## 8. Step 5"):
            text += f"\n{heading}\n\n完了条件は、`MULTI-001`が通過する。\n"
        steps = step_assignment.plan_steps(text, ids)
        self.assertEqual(steps[1], {"SINGLE-127-05", "SINGLE-127-06", "SINGLE-127-07", "SINGLE-070-01", "SINGLE-070-02",
                                    "SINGLE-070-03", "SINGLE-070-04", "SINGLE-071-01", "SINGLE-071-02", "SINGLE-071-03",
                                    "SINGLE-071-04"})

    def test_step_assignment_rejects_drift_from_the_plan(self):
        original = json.loads((audit.FIXTURES / "steps.json").read_text())
        plan = step_assignment.PLAN.read_text()

        def run(document, plan_text=plan):
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                (root / "single").symlink_to(audit.FIXTURES / "single")
                (root / "steps.json").write_text(json.dumps(document))
                return step_assignment.validate(root, plan_text)

        self.assertEqual(run(original)["errors"], [])
        dropped = copy.deepcopy(original)
        dropped["steps"][0]["fixtures"].pop()
        self.assertTrue(run(dropped)["errors"])
        misplaced = copy.deepcopy(original)
        misplaced["steps"][1]["parserChecks"].append(misplaced["steps"][1]["fixtures"].pop(0))
        self.assertTrue(run(misplaced)["errors"])
        self.assertTrue(run(original, plan.replace("`SINGLE-001`〜`006`、", "`SINGLE-002`〜`006`、", 1))["errors"])

    @staticmethod
    def certification_runs(pending=None, errors=None, conformance_exit=1, scale_status="Passed"):
        report = {"gateA": "Blocked", "pending": [certify.CERTIFIED] if pending is None else pending,
                  "checks": {"links": {"errors": errors or []}, "fixture_coverage": {"status": "Passed", "errors": []}}}
        conformance = {"exitCode": conformance_exit, "stdout": json.dumps(report).encode()}
        scale = {"exitCode": 0 if scale_status == "Passed" else 1,
                 "stdout": json.dumps({"status": scale_status, "durationSeconds": 37.0, "results": [], "errors": []}).encode()}
        return [conformance, dict(conformance)], [scale, dict(scale)]

    def test_gate_a_certification_accepts_identical_fresh_checkouts(self):
        conformance, scale = self.certification_runs()
        self.assertEqual(certify.judge(conformance, scale), [])
        # 所要時間だけが異なる規模の検証は一致として扱う。
        scale[1] = {"exitCode": 0, "stdout": scale[1]["stdout"].replace(b"37.0", b"41.5")}
        self.assertEqual(certify.judge(conformance, scale), [])

    def test_gate_a_certification_rejects_incomplete_or_unrepeatable_evidence(self):
        cases = {
            "他の未完了の証拠": self.certification_runs(pending=["conformance inputs and expectations", certify.CERTIFIED]),
            "認定対象の項目の欠落": self.certification_runs(pending=[]),
            "errorのある検査": self.certification_runs(errors=["broken link"]),
            "統合検証の終了コード": self.certification_runs(conformance_exit=0),
            "scale検証の失敗": self.certification_runs(scale_status="Failed"),
        }
        conformance, scale = self.certification_runs()
        cases["checkout数"] = (conformance[:1], scale[:1])
        cases["reportのbyte不一致"] = (
            [conformance[0], {"exitCode": 1, "stdout": conformance[1]["stdout"] + b"\n"}], scale)
        cases["scale結果の不一致"] = (
            conformance, [scale[0], {"exitCode": 0, "stdout": scale[1]["stdout"].replace(b'"results": []', b'"results": [1]')}])
        cases["JSONでないreport"] = ([{"exitCode": 1, "stdout": b"not json"}] * 2, scale)
        for name, (runs, scales) in cases.items():
            with self.subTest(name):
                self.assertTrue(certify.judge(runs, scales))

    def test_gate_a_certification_names_the_scale_failure(self):
        # 規模の検証が理由を返したときは、認定の理由にその先頭を示す（原因を「形式が不正」に埋もれさせない）。
        conformance, scale = self.certification_runs()
        failed = {"exitCode": 1, "stdout": json.dumps({"status": "Failed", "durationSeconds": 1.0, "results": [],
                                                      "errors": ["MULTI-020-01: 照合を完了できません（TimeoutExpired: git）"]}).encode()}
        reasons = certify.judge(conformance, [failed, dict(failed)])
        self.assertIn("規模の検証1: 成功していません（MULTI-020-01: 照合を完了できません（TimeoutExpired: git））", reasons)

    def test_scale_validation_reports_setup_failures_as_json(self):
        # 準備手順のGit操作がタイムアウトしても、規模の検証はJSONのレポートを出し、失敗として数える（C14）。
        import contextlib
        import io
        import subprocess
        import validate_scale
        first = next(iter(validate_scale.multi_limit_fixtures.CASES))

        def fake(identifier):
            if identifier == first:
                raise subprocess.TimeoutExpired(["git", "add"], 120)
            return {"fixtureId": identifier, "errors": []}

        output = io.StringIO()

        def fake_single_verify(identifier):
            return {"fixtureId": identifier, "errors": []}

        with patch.object(validate_scale, "validate_fixture", fake), \
                patch.object(validate_scale, "validate_single_verify_fixture", fake_single_verify), \
                contextlib.redirect_stdout(output):
            exit_code = validate_scale.main()
        report = json.loads(output.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertEqual(report["status"], "Failed")
        self.assertEqual(report["fixtures"], len(validate_scale.multi_limit_fixtures.CASES)
                         + len(validate_scale.single_verify.CASES))
        self.assertEqual(len(report["errors"]), 1)
        self.assertTrue(report["errors"][0].startswith(f"{first}: 照合を完了できません（TimeoutExpired: "))
        conformance, _scale = self.certification_runs()
        reasons = certify.judge(conformance, [{"exitCode": exit_code, "stdout": output.getvalue().encode()}] * 2)
        self.assertEqual([reason for reason in reasons if reason.startswith("規模の検証1")],
                         [f"規模の検証1: 成功していません（{report['errors'][0]}）"])
        self.assertFalse(any("形式が不正" in reason for reason in reasons), reasons)

    def test_scale_validation_does_not_swallow_other_exceptions(self):
        # 捕まえる範囲は準備手順・ファイル操作・照合の不一致に限り、それ以外の例外（実装の欠陥など）は伝える。
        import validate_scale

        def broken(identifier):
            raise KeyError(identifier)

        with patch.object(validate_scale, "validate_fixture", broken):
            with self.assertRaises(KeyError):
                validate_scale.main()

    def test_gate_a_certification_shows_the_stderr_of_an_unreadable_report(self):
        conformance, _scale = self.certification_runs()
        crashed = {"exitCode": 1, "stdout": b"", "stderr": b"Traceback (most recent call last):\n  ...\nKeyError: 'x'\n"}
        reasons = certify.judge(conformance, [crashed, dict(crashed)])
        self.assertIn("規模の検証1: レポートの形式が不正です（KeyError: 'x'）", reasons)
        self.assertIn("規模の検証2: レポートの形式が不正です（KeyError: 'x'）", reasons)
        _conformance, scale = self.certification_runs()
        reasons = certify.judge([crashed, dict(crashed)], scale)
        self.assertIn("監査1: レポートの形式が不正です（KeyError: 'x'）", reasons)
        # 実行の結果は標準エラー出力を保持する（`judge`へ渡す材料）。
        completed = certify.subprocess.CompletedProcess(["uv"], 1, stdout=b"", stderr=b"KeyError: 'y'\n")
        with patch.object(certify.subprocess, "run", return_value=completed):
            result = certify.run("uv", ["fixtures/validate_scale.py"], Path("."), 900)
        self.assertEqual(result, {"exitCode": 1, "stdout": b"", "stderr": b"KeyError: 'y'\n"})

    def test_fixture_git_uses_the_shared_timeout(self):
        from conformance import harness
        self.assertEqual(harness.GIT_TIMEOUT_SECONDS, 120)
        with patch.object(harness.subprocess, "check_output", return_value=b"") as check_output:
            harness.git(Path("."), "status")
        self.assertEqual(check_output.call_args.kwargs["timeout"], harness.GIT_TIMEOUT_SECONDS)

    def test_gate_a_certification_requires_a_committed_worktree(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for args in (("init", "--quiet"), ("config", "user.email", "audit@example.invalid"),
                         ("config", "user.name", "audit")):
                certify.git(*args, cwd=root)
            (root / "tracked.txt").write_text("a\n")
            certify.git("add", "tracked.txt", cwd=root)
            certify.git("commit", "--quiet", "-m", "init", cwd=root)
            with patch.object(certify, "ROOT", root):
                self.assertEqual(certify.worktree_errors(), [])
                (root / "untracked.txt").write_text("b\n")
                self.assertTrue(certify.worktree_errors())
                (root / "untracked.txt").unlink()
                (root / "tracked.txt").write_text("changed\n")
                self.assertTrue(certify.worktree_errors())


if __name__ == "__main__":
    unittest.main()
