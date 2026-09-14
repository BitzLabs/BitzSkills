"""Reviewed `--report`-absent vectors; runs no Core operation.

`SINGLE-070-01/02/03/04` pin that neither `check` nor `verify` writes anything
without `--report`, on success and on failure alike. Each corpus already holds a
report file, so "既存report不変" is a property the snapshot can actually fail.
"""
import json
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from . import digest_reference, verify_fixtures
from .harness import setup
from .initial_fixtures import observe, compare_state

HERE = Path(__file__).resolve().parent
EXISTING_REPORT = ".spec/reports/existing.json"
EXISTING_REPORT_BODY = b'{"schemaVersion": "1.0", "note": "pre-existing report"}\n'
MISSING_REQUIRE = "relations:\n  requires: [TECH-999]\n  refines: [REQ-001]\n  related: [ADR-001]\n"
CHECK_DOCUMENTS = 3
CHECK_STATEMENTS = 2
# id: (operation, status, exit code)
CASES = {
    "SINGLE-070-01": ("check", "passed", 0),
    "SINGLE-070-02": ("check", "failed", 1),
    "SINGLE-070-03": ("verify", "passed", 0),
    "SINGLE-070-04": ("verify", "failed", 1),
}
DESCRIPTIONS = {
    "SINGLE-070-01": "--reportなしの成功checkがfileを作らず既存reportを変えない",
    "SINGLE-070-02": "--reportなしの失敗checkがfileを作らず既存reportを変えない",
    "SINGLE-070-03": "--reportなしの成功verifyがfileを作らず既存reportを変えない",
    "SINGLE-070-04": "--reportなしの失敗verifyがfileを作らず既存reportを変えない",
}


def reviewed_inputs(identifier):
    source = "SINGLE-056" if identifier == "SINGLE-070-04" else "SINGLE-042"
    inputs = dict(digest_reference.reviewed_inputs("SINGLE-042"))
    if identifier == "SINGLE-070-04":
        inputs[digest_reference.CONFIG_PATH] = verify_fixtures.FAILING_CONFIG.encode()
    if identifier == "SINGLE-070-02":
        inputs[digest_reference.TECH_PATH] = ("---\n" + digest_reference.TECH_HEAD_FIELDS.replace(
            "relations:\n  refines: [REQ-001]\n  related: [ADR-001]\n", MISSING_REQUIRE, 1)
            + "x-owners: [team-auth]\n---\n\n" + digest_reference.TECH_BODY).encode()
    inputs[EXISTING_REPORT] = EXISTING_REPORT_BODY
    return inputs


def reviewed_manifest(identifier):
    operation, status, exit_code = CASES[identifier]
    if operation == "check":
        plan = {"git": True, "baseCommit": {"message": "base", "paths": ["."]}, "operations": []}
        argv = ["check", "--full", "--base", "HEAD", "--format", "json"]
    else:
        # verify blocks on an untracked configuration and takes no --base.
        plan = {"git": True, "operations": [{"op": "stage", "paths": ["."]}]}
        argv = ["verify", "REQ-001", "--format", "json"]
    return {
        "fixtureId": identifier,
        "description": DESCRIPTIONS[identifier],
        "setup": plan,
        "invocation": {"runner": "bitz", "cwd": ".", "argv": argv, "env": {}},
        "expect": {"status": status, "exitCode": exit_code, "stdout": "json",
                   "resultFile": f"expected/{operation}.json", "reportFileCount": 0},
    }


def reviewed_result(identifier):
    operation, status, _ = CASES[identifier]
    if operation == "verify":
        # The extra report file is not SPEC material, so the Context is unchanged.
        return verify_fixtures.reviewed_result(
            "SINGLE-055" if identifier == "SINGLE-070-03" else "SINGLE-056")
    diagnostics = [] if status == "passed" else [{
        "code": "SPEC-RELATION-MISSING-001", "severity": "error", "resultStatus": "failed",
        "summary": "strong relationの参照先が存在しません",
        "source": {"kind": "file", "workspaceId": "root",
                   "path": digest_reference.TECH_PATH, "key": "relations.requires"}}]
    return {
        "schemaVersion": "1.0", "operation": "check", "status": status, "scope": "full",
        "workspace": {"id": "root", "path": "."},
        "revision": {"base": "0" * 40, "commit": "0" * 40, "dirty": False},
        "checkedDocumentCount": CHECK_DOCUMENTS, "checkedStatementCount": CHECK_STATEMENTS,
        "durationMs": 0, "diagnostics": diagnostics,
    }


def check_report_expectation(manifest, effects):
    if manifest["expect"]["reportFileCount"] != 0:
        raise ValueError("this group runs without --report, so no file may be created")
    if "--report" in manifest["invocation"]["argv"]:
        raise ValueError("the reviewed invocation must not pass --report")
    before = effects["before"]["repository"]
    if EXISTING_REPORT not in before:
        raise ValueError("the corpus must already hold a report, or immutability is untested")
    if before != effects["after"]["repository"]:
        raise ValueError("an existing report must survive the run byte for byte")


def validate(root=HERE, identifiers=None):
    errors, prepared = [], []
    validators = {name: Draft202012Validator(json.loads((root / f"{name}.schema.json").read_text()))
                  for name in ("manifest", "result", "side-effects")}
    for identifier in CASES:
        if identifiers is not None and identifier not in identifiers:
            continue
        operation = CASES[identifier][0]
        fixture = root / "single" / identifier
        try:
            manifest = json.loads((fixture / "manifest.json").read_text())
            result = json.loads((fixture / f"expected/{operation}.json").read_text())
            effects = json.loads((fixture / "side-effects.json").read_text())
            for name, value in (("manifest", manifest), ("result", result), ("side-effects", effects)):
                validators[name].validate(value)
            if manifest != reviewed_manifest(identifier) or result != reviewed_result(identifier):
                raise ValueError("invocation or complete result differs from reviewed expectation")
            check_report_expectation(manifest, effects)
            inputs = reviewed_inputs(identifier)
            files = {p.relative_to(fixture / "repo").as_posix(): p
                     for p in (fixture / "repo").rglob("*") if p.is_file() or p.is_symlink()}
            if set(files) != set(inputs) or any(p.is_symlink() or p.read_bytes() != inputs[name]
                                                for name, p in files.items()):
                raise ValueError("input differs from the reviewed corpus")
            if effects["before"] != effects["after"]:
                raise ValueError("read-only expectation permits writes")
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-report-absent-") as temporary:
                for run in range(2):
                    sandbox = Path(temporary) / str(run)
                    sandbox.mkdir()
                    repository = setup(fixture, manifest, sandbox / "repo")
                    external = {name: sandbox / name for name in ("home", "cache", "temporary")}
                    for path in external.values():
                        path.mkdir()
                    actual = observe(repository, external)
                    if compare_state(effects["before"], actual) or (previous is not None and previous != actual):
                        raise ValueError("isolated setup differs from fixed snapshot")
                    previous = actual
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, ValidationError,
                subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "status": "Passed" if not errors else "Failed", "errors": errors}
