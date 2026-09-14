"""Regression checks that malformed evidence is not silently accepted."""
import json
import copy
from pathlib import Path
import tempfile
import shutil
import unittest
from unittest.mock import patch

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
from conformance.git_environment_fixtures import (validate as validate_git_environment, check_cli_error_output,
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


class AuditTests(unittest.TestCase):
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

    def test_digest_fixtures(self):
        result = validate_digest()
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["prepared"], ["SINGLE-042", "SINGLE-043-01", "SINGLE-043-02",
                                              "SINGLE-044-01", "SINGLE-044-02", "SINGLE-045"])
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
            ("SINGLE-042", "expected/context.json", lambda v: v.update(contextDigest="sha256:" + "0" * 64)),
            ("SINGLE-042", "expected/context.json", lambda v: v.update(status="passed_with_warnings")),
            ("SINGLE-042", "expected/context.json", lambda v: v["resolution"].update(documentCount=3)),
            ("SINGLE-042", "expected/context.json", lambda v: v["coverage"]["must"].update(untested=["REQ-001:AC-01"])),
            ("SINGLE-042", "expected/context.json", lambda v: v["documents"][1].update(projection="normative")),
            ("SINGLE-042", "manifest.json", lambda v: v["invocation"]["argv"].__setitem__(3, "implement")),
            ("SINGLE-042", "manifest.json", lambda v: v["expect"].update(reportFileCount=1)),
            ("SINGLE-043-01", "expected/context.json", lambda v: v["projection"].update(detail="standard")),
            ("SINGLE-043-02", "expected/context.json", lambda v: v["projection"].update(expanded=[])),
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
        self.assertEqual(result["prepared"], ["SINGLE-050", "SINGLE-051", "SINGLE-052-01", "SINGLE-052-02", "SINGLE-053"])
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
