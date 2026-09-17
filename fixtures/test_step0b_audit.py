"""Regression checks that malformed evidence is not silently accepted."""
import json
import copy
from pathlib import Path
import tempfile
import shutil
import unittest
from unittest.mock import patch

from jsonschema import Draft202012Validator, ValidationError

import validate_step0b as audit
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
from conformance import scanner_fixtures
from conformance import presentation_fixtures


class AuditTests(unittest.TestCase):
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
        # A body holding a longer backtick run must widen the fence.
        document = copy.deepcopy(result["documents"][0])
        document["bodyText"] = "````\ncode\n````\n"
        self.assertEqual(markdown_reference.fence(document["bodyText"]), "`" * 5)
        self.assertIn("`````markdown", markdown_reference.document_block(document))
        # compact keeps the heading and drops the body.
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
            # The shared raw cause must keep the reviewed primary, not the lower-priority condition.
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
        # Repairing the sole cause, or adding the workspace the case denies, must not pass.
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
        # Each replacement moves the fixture to the other side of its reviewed dimension.
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

    def copy_fixture(self, temporary, identifier):
        root = Path(temporary)
        shutil.copytree(audit.FIXTURES / "single" / identifier, root / "single" / identifier)
        for name in ("manifest", "result", "side-effects"):
            shutil.copy2(audit.FIXTURES / f"{name}.schema.json", root)
        return root

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
            # key tupleによる重複を受理へ戻す改変と、別test対応を重複扱いにする改変を拒否する。
            ("SINGLE-118-02", "expected/check.json", lambda v: v.update(status="passed", diagnostics=[])),
            ("SINGLE-118-03", "expected/check.json", lambda v: v.update(checkedStatementCount=1)),
            # 空changesを変更許可と取り違える改変、境界違反を文書skipとして数える改変を拒否する。
            ("SINGLE-120-01", "manifest.json", lambda v: v["invocation"]["argv"].__setitem__(1, "--full")),
            ("SINGLE-120-02", "expected/check.json", lambda v: v.update(checkedDocumentCount=0)),
            ("SINGLE-120-02", "expected/check.json", lambda v: v["diagnostics"][0]["source"].update(key="changes")),
            ("SINGLE-120-02", "side-effects.json", lambda v: v["after"]["git"].update(status="")),
        ]
        for identifier, relative, mutate in mutations:
            with self.subTest(identifier=identifier), tempfile.TemporaryDirectory() as temporary:
                root = self.copy_fixture(temporary, identifier)
                shutil.copy2(audit.FIXTURES / "frontmatter.schema.json", root)
                path = root / "single" / identifier / relative
                value = json.loads(path.read_text()); mutate(value); path.write_text(json.dumps(value))
                self.assertTrue(boundaries.validate(root, [identifier])["errors"])
        with tempfile.TemporaryDirectory() as temporary:
            identifier = "SINGLE-116-02"
            root = self.copy_fixture(temporary, identifier)
            shutil.copy2(audit.FIXTURES / "frontmatter.schema.json", root)
            path = root / "single" / identifier / "repo" / boundaries.spec_path(identifier)
            path.write_text(path.read_text().replace("界" * 121, "界" * 120))
            self.assertTrue(boundaries.validate(root, [identifier])["errors"])
        # covers順の入替えを同順へ修復すると単一原因でなくなるため拒否する。
        with tempfile.TemporaryDirectory() as temporary:
            identifier = "SINGLE-118-02"
            root = self.copy_fixture(temporary, identifier)
            shutil.copy2(audit.FIXTURES / "frontmatter.schema.json", root)
            path = root / "single" / identifier / "repo" / boundaries.spec_path(identifier)
            path.write_text(path.read_text().replace('["REQ-001:AC-02", "REQ-001:AC-01"]', '["REQ-001:AC-01", "REQ-001:AC-02"]'))
            self.assertTrue(boundaries.validate(root, [identifier])["errors"])
        # 変更差分をindexへstageした状態は、未stage差分の期待と一致しないため拒否する。
        with tempfile.TemporaryDirectory() as temporary:
            identifier = "SINGLE-120-02"
            root = self.copy_fixture(temporary, identifier)
            shutil.copy2(audit.FIXTURES / "frontmatter.schema.json", root)
            path = root / "single" / identifier / "manifest.json"
            value = json.loads(path.read_text())
            value["setup"]["operations"].append({"op": "stage", "paths": ["src/app.py"]})
            path.write_text(json.dumps(value))
            self.assertTrue(boundaries.validate(root, [identifier])["errors"])

    def test_side_effect_evidence(self):
        from conformance import side_effect_fixtures as effects
        report = effects.validate()
        self.assertEqual(report["errors"], [])
        self.assertEqual(len(report["prepared"]), 5)
        self.assertEqual(report["core_execution"], "Not run")

        def fixture_root(temporary, identifier):
            # source fixtureとの一致を検査するため、sourceも一緒にcopyする。
            root = self.copy_fixture(temporary, identifier)
            source = effects.CASES[identifier][0]
            shutil.copytree(audit.FIXTURES / "single" / source, root / "single" / source)
            return root

        mutations = [
            # 書込みの許容、外部treeの事前汚染、report要求の追加、件数改変を拒否する。
            ("SINGLE-125-01", "side-effects.json", lambda v: v["after"]["cache"].update(index={"kind": "directory"})),
            ("SINGLE-125-02", "side-effects.json", lambda v: [v[k]["home"].update(lock={"kind": "directory"}) for k in ("before", "after")]),
            ("SINGLE-125-03", "manifest.json", lambda v: v["invocation"]["argv"].append("--report")),
            ("SINGLE-125-03", "manifest.json", lambda v: v["expect"].update(reportFileCount=1)),
            ("SINGLE-125-04", "manifest.json", lambda v: v["invocation"]["env"].update(HOME="/tmp")),
            ("SINGLE-125-04", "expected/verify.json", lambda v: v.update(status="failed")),
            ("SINGLE-125-05", "side-effects.json", lambda v: v["report"].update(temporaryFilesRemaining=1)),
            ("SINGLE-125-05", "side-effects.json", lambda v: v["report"].update(createdCount=2)),
            ("SINGLE-125-05", "side-effects.json", lambda v: v.update(policy="read-only")),
        ]
        for identifier, relative, mutate in mutations:
            with self.subTest(identifier=identifier, relative=relative), tempfile.TemporaryDirectory() as temporary:
                root = fixture_root(temporary, identifier)
                path = root / "single" / identifier / relative
                value = json.loads(path.read_text()); mutate(value); path.write_text(json.dumps(value))
                self.assertTrue(effects.validate(root, [identifier])["errors"])
        # read-only caseへreport directoryを置く改変、verify commandを書込みcommandへ替える改変を拒否する。
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
                    shutil.copy2(audit.FIXTURES / f"{name}.schema.json", root)
                path = fixture / relative
                value = json.loads(path.read_text()); mutate(value); path.write_text(json.dumps(value))
                self.assertTrue(frontmatter_fixtures.validate(root, [identifier])["errors"])
        for identifier in frontmatter_fixtures.CASES:
            with self.subTest(repaired_input=identifier), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                fixture = root / "single" / identifier
                shutil.copytree(audit.FIXTURES / "single" / identifier, fixture)
                for name in ("manifest", "result", "side-effects"):
                    shutil.copy2(audit.FIXTURES / f"{name}.schema.json", root)
                # Repair the sole input condition; the old expected Diagnostic must no longer pass.
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
                    shutil.copy2(audit.FIXTURES / f"{name}.schema.json", root)
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
                    shutil.copy2(audit.FIXTURES / f"{name}.schema.json", root)
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
            # The pre-existing report proves exclusive creation rather than replacement.
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
        self.assertEqual([d["code"] for d in result["diagnostics"]],
                         [d["code"] for d in source["diagnostics"]] + ["SPEC-REPORT-WRITE-001"])
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
            ("SINGLE-072", "expected/check.json", lambda v: v.update(checkedDocumentCount=0)),
        ]
        for identifier, relative, mutate in mutations:
            with self.subTest(identifier=identifier, relative=relative), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                fixture = root / "single" / identifier
                shutil.copytree(audit.FIXTURES / "single" / identifier, fixture)
                for name in ("manifest", "result", "side-effects", "frontmatter"):
                    shutil.copy2(audit.FIXTURES / f"{name}.schema.json", root)
                path = fixture / relative
                value = json.loads(path.read_text())
                mutate(value)
                path.write_text(json.dumps(value))
                self.assertTrue(validate_report_write(root, [identifier])["errors"])

    def test_report_absent_and_cli_error_fixtures(self):
        absent = validate_report_absent()
        self.assertEqual(absent["errors"], [])
        self.assertEqual(absent["prepared"], ["SINGLE-070-01", "SINGLE-070-02",
                                              "SINGLE-070-03", "SINGLE-070-04"])
        errors = validate_cli_errors()
        self.assertEqual(errors["errors"], [])
        self.assertEqual(errors["prepared"], ["SINGLE-073-01", "SINGLE-073-02", "SINGLE-074-01",
                                              "SINGLE-074-02", "SINGLE-074-03",
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
                    shutil.copy2(audit.FIXTURES / f"{name}.schema.json", root)
                path = fixture / relative
                value = json.loads(path.read_text())
                mutate(value)
                path.write_text(json.dumps(value))
                self.assertTrue(validator(root, [identifier])["errors"])

    def test_verify_task_root_fixture(self):
        result = validate_verify_task_root()
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["prepared"], ["SINGLE-068"])
        self.assertEqual(result["core_execution"], "Not run")

    def test_done_task_root_is_reverifiable_and_cancelled_is_not(self):
        done = json.loads((audit.FIXTURES / "single/SINGLE-068/expected/verify.json").read_text())
        cancelled = json.loads((audit.FIXTURES / "single/SINGLE-067/expected/verify.json").read_text())
        verify_task_root_fixtures.check_done_root(done)
        self.assertEqual((done["status"], cancelled["status"]), ("passed", "blocked"))
        self.assertEqual(done["targetResults"][0]["bindingRefs"], ["root::default"])
        self.assertEqual(cancelled["targetResults"][0]["bindingRefs"], [])
        # A cancelled root never reaches its addressed statements; a done root does.
        self.assertEqual(cancelled["targetResults"][0]["statements"], [])
        self.assertEqual(done["targetResults"][0]["statements"], ["REQ-001:AC-01"])

    def test_task_root_context_holds_the_addressed_owner(self):
        """関係・トレースモデル §6.3: a TASK root brings the documents owning its
        addresses targets into the Context, so the Digest covers all three."""
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
                    shutil.copy2(audit.FIXTURES / f"{name}.schema.json", root)
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
                    shutil.copy2(audit.FIXTURES / f"{name}.schema.json", root)
                path = fixture / "repo" / verify_task_root_fixtures.TASK_PATH
                path.write_text(path.read_text().replace("status: done", "status: " + status))
                self.assertTrue(validate_verify_task_root(root, ["SINGLE-068"])["errors"])

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
                    shutil.copy2(audit.FIXTURES / f"{name}.schema.json", root)
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
                shutil.copy2(audit.FIXTURES / f"{name}.schema.json", root)
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
        # The script body is not Digest material, so the Context is the same.
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
                    shutil.copy2(audit.FIXTURES / f"{name}.schema.json", root)
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
                shutil.copy2(audit.FIXTURES / f"{name}.schema.json", root)
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
            # The binding was reached, so the target still references it.
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
                    shutil.copy2(audit.FIXTURES / f"{name}.schema.json", root)
                path = fixture / relative
                value = json.loads(path.read_text())
                mutate(value)
                path.write_text(json.dumps(value))
                self.assertTrue(validate_verify_process(root, [identifier])["errors"])

    def test_process_audit_rejects_inputs_that_no_longer_cause_the_failure(self):
        """The audit runs each command file itself, so a corpus that stopped being
        hostile must fail rather than quietly keep the old expectation."""
        mutations = [
            # A file the OS accepts spawns successfully, so there is no spawn error.
            ("SINGLE-057", "repo/bin/badformat", lambda t: "#!/bin/sh\nexit 0\n"),
            # A command that honours TERM never needs a force kill.
            ("SINGLE-059", "repo/bin/hang.sh", lambda t: "#!/bin/sh\nsleep 60\n"),
        ]
        for identifier, relative, mutate in mutations:
            with self.subTest(identifier=identifier), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                fixture = root / "single" / identifier
                shutil.copytree(audit.FIXTURES / "single" / identifier, fixture)
                for name in ("manifest", "result", "side-effects", "frontmatter"):
                    shutil.copy2(audit.FIXTURES / f"{name}.schema.json", root)
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
                shutil.copy2(audit.FIXTURES / f"{name}.schema.json", root)
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
        # The executed command must only claim the passing target's statements.
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
                    shutil.copy2(audit.FIXTURES / f"{name}.schema.json", root)
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
                    shutil.copy2(audit.FIXTURES / f"{name}.schema.json", root)
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
        # A changed command argv is Digest material, so 056 must not reuse it.
        failing = json.loads((audit.FIXTURES / "single/SINGLE-056/expected/verify.json").read_text())
        self.assertNotEqual(failing["targetResults"][0]["contextDigest"], golden)

    def test_verify_fixtures_stage_their_configuration(self):
        """verify blocks on an untracked configuration, so no fixture may leave
        .spec/bitz.yaml out of the index."""
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
        expected = {"SINGLE-055": True, "SINGLE-056": True, "SINGLE-060": True,
                    "SINGLE-061": False, "SINGLE-067": False}
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
                    shutil.copy2(audit.FIXTURES / f"{name}.schema.json", root)
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
                    shutil.copy2(audit.FIXTURES / f"{name}.schema.json", root)
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
        """purpose is digest material, and implement records no binding, so the two
        canonical forms must not collide."""
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
        # Same documents, bodies too small to cross the hard limit.
        small = {path: (value[0], value[1], value[2], f"# {value[0]} {value[1]}\n")
                 for path, value in projection_limit_fixtures.DOCUMENTS.items()}
        with patch.object(projection_limit_fixtures, "DOCUMENTS", small):
            with self.assertRaises(ValueError):
                projection_limit_fixtures.check_limits(projection_limit_fixtures.reviewed_inputs())
        # A standard presentation that already crosses the limit would not isolate detail.
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
                    shutil.copy2(audit.FIXTURES / f"{name}.schema.json", root)
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
        """046 and 047 resolve completely, so they must carry the same Digest the
        golden fixture committed, not a separately invented constant."""
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
                    shutil.copy2(audit.FIXTURES / f"{name}.schema.json", root)
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
                    shutil.copy2(audit.FIXTURES / f"{name}.schema.json", root)
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
        """A states the digest input; B rebuilds it from the tree. Both must agree,
        and the matrix's equal/unequal pairs must hold as bytes, not only as hashes."""
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
                    shutil.copy2(audit.FIXTURES / f"{name}.schema.json", root)
                path = fixture / relative
                value = json.loads(path.read_text())
                mutate(value)
                path.write_text(json.dumps(value))
                self.assertTrue(validate_digest(root, [identifier])["errors"])

    def test_digest_audit_rejects_changed_inputs_and_canonical_bytes(self):
        """A changed input must invalidate the committed Canonical JSON, and an
        x-only change must not be accepted as a Digest-visible difference."""
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
                    shutil.copy2(audit.FIXTURES / f"{name}.schema.json", root)
                path = fixture / relative
                path.write_text(mutate(path.read_text()))
                self.assertTrue(validate_digest(root, [identifier])["errors"])

    def test_digest_audit_rejects_a_replaced_canonical_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = root / "single/SINGLE-042"
            shutil.copytree(audit.FIXTURES / "single/SINGLE-042", fixture)
            for name in ("manifest", "result", "side-effects", "frontmatter"):
                shutil.copy2(audit.FIXTURES / f"{name}.schema.json", root)
            canonical = fixture / "expected/context.canonical.json"
            canonical.write_bytes(canonical.read_bytes() + b"\n")
            self.assertTrue(validate_digest(root, ["SINGLE-042"])["errors"])

    def test_crosscheck_rejects_a_corpus_it_cannot_account_for(self):
        """Reference B must refuse inputs outside the reviewed closure instead of
        silently producing some other digest input."""
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
        self.assertEqual(result["prepared"], ["SINGLE-050", "SINGLE-051", "SINGLE-052-01", "SINGLE-052-02", "SINGLE-053", "SINGLE-127-13"])
        self.assertEqual(result["core_execution"], "Not run")

    def test_context_failures_reject_partial_success_or_replacement(self):
        mutations = [
            ("SINGLE-050", "expected/context.json", lambda v: v["diagnostics"][0].update(source={"kind": "file", "path": ".spec/technical/TECH-001.md"})),
            ("SINGLE-050", "expected/context.json", lambda v: v.update(roots=["TECH-001"])),
            ("SINGLE-051", "expected/context.json", lambda v: v.update(status="passed")),
            ("SINGLE-051", "expected/context.json", lambda v: v["diagnostics"][0].update(code="CTX-STATE-001")),
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
                    shutil.copy2(audit.FIXTURES / f"{name}.schema.json", root)
                path = fixture / relative
                value = json.loads(path.read_text())
                mutate(value)
                path.write_text(json.dumps(value))
                self.assertTrue(validate_context_failures(root, [identifier])["errors"])

    def test_context_failure_inputs_reject_repaired_or_changed_causes(self):
        mutations = [
            ("SINGLE-050", ".spec/technical/TECH-001.md", "TECH-001", "TECH-999"),
            ("SINGLE-051", ".spec/tasks/TASK-002.md", "status: open", "status: done"),
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
                    shutil.copy2(audit.FIXTURES / f"{name}.schema.json", root)
                path = fixture / "repo" / relative
                path.write_text(path.read_text().replace(before, after))
                self.assertTrue(validate_context_failures(root, [identifier])["errors"])

    def test_context_failure_git_state_rejects_staging_or_commit(self):
        for identifier in ("SINGLE-050", "SINGLE-051", "SINGLE-052-01", "SINGLE-052-02", "SINGLE-053"):
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
                    shutil.copy2(audit.FIXTURES / f"{name}.schema.json", root)
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
                    shutil.copy2(audit.FIXTURES / f"{name}.schema.json", root)
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
                self.assertTrue(any("requires explicit --base" in e or "forbids --base" in e for e in errors), errors)

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
                    shutil.copy2(audit.FIXTURES / f"{name}.schema.json", root)
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
                    shutil.copy2(audit.FIXTURES / f"{name}.schema.json", root)
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
                    shutil.copy2(audit.FIXTURES / f"{name}.schema.json", root)
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
                    shutil.copy2(audit.FIXTURES / f"{name}.schema.json", root)
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
                    shutil.copy2(audit.FIXTURES / f"{name}.schema.json", root)
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
                    shutil.copy2(audit.FIXTURES / f"{name}.schema.json", root)
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
                    shutil.copy2(audit.FIXTURES / f"{name}.schema.json", root)
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
                    shutil.copy2(audit.FIXTURES / f"{name}.schema.json", root)
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
        self.assertEqual(len(result["prepared"]), 6)
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
                    shutil.copy2(audit.FIXTURES / f"{name}.schema.json", root)
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
                    shutil.copy2(audit.FIXTURES / f"{name}.schema.json", root)
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
                    shutil.copy2(audit.FIXTURES / f"{name}.schema.json", root)
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
                    shutil.copy2(audit.FIXTURES / f"{name}.schema.json", root)
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
        self.assertEqual(len(result["prepared"]), 12)
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
        ]
        for identifier, mutate in mutations:
            with self.subTest(identifier=identifier), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                shutil.copytree(audit.FIXTURES / "single" / identifier, root / "single" / identifier)
                for name in ("manifest", "result", "side-effects", "frontmatter"):
                    shutil.copy2(audit.FIXTURES / f"{name}.schema.json", root)
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
                shutil.copy2(audit.FIXTURES / f"{name}.schema.json", root)
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
            ("SINGLE-006-02/expected/doctor.json", lambda value: value["checks"][6].update(status="passed")),
        ]
        for relative, mutate in mutations:
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                shutil.copytree(audit.FIXTURES / "single", root / "single")
                for name in ("manifest", "result", "side-effects"):
                    shutil.copy2(audit.FIXTURES / f"{name}.schema.json", root)
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
            # Preserve real schemas but provide no acceptance fixture directories.
            for name in ("manifest.schema.json", "result.schema.json"):
                (root / name).write_text((audit.FIXTURES / name).read_text())
            with patch.object(audit, "FIXTURES", root):
                missing = audit.matrix()
        self.assertEqual(len(missing["missing_fixtures"]), missing["matrix_ids"])


if __name__ == "__main__":
    unittest.main()
