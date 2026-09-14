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


class AuditTests(unittest.TestCase):
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
