"""Reviewed argument-error vectors; runs no Core operation.

`SINGLE-073-01/02` reject `--report` on the operations that never write one, and
`SINGLE-074-01/02/03` reject an exclusive option pair, a code path target and a
lexically invalid ID. All five return no common result: exit code 4, no JSON body,
one stderr line, and no report.
"""
import json
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from . import digest_reference
from .git_environment_fixtures import check_cli_error_output
from .harness import setup
from .initial_fixtures import observe, compare_state

HERE = Path(__file__).resolve().parent
# id: (operation, argv tail, description)
CASES = {
    "SINGLE-073-01": ("context", ["REQ-001", "--report"],
                      "contextは--reportを未知optionとして拒否する"),
    "SINGLE-073-02": ("doctor", ["--report"],
                      "doctorは--reportを未知optionとして拒否する"),
    "SINGLE-074-01": ("check", ["REQ-001", "--full", "--format", "json"],
                      "明示対象と--fullの排他違反を拒否する"),
    "SINGLE-074-02": ("verify", ["src/auth.py", "--format", "json"],
                      "verify targetへのcode path指定を拒否する"),
    "SINGLE-074-03": ("check", ["REQ-1", "--format", "json"],
                      "構文不正な文書IDを拒否する"),
}


def cli_output(identifier):
    operation = CASES[identifier][0]
    return {"exitCode": 4, "stdout": "", "stderrPrefix": f"bitz: {operation}: ",
            "stderrLineCount": 1, "stderrReasonRequired": True, "stderrTerminalControls": False}


def reviewed_inputs(identifier):
    return dict(digest_reference.reviewed_inputs("SINGLE-042"))


def reviewed_manifest(identifier):
    operation, tail, description = CASES[identifier]
    return {
        "fixtureId": identifier,
        "description": description,
        "setup": {"git": True, "operations": []},
        "invocation": {"runner": "bitz", "cwd": ".", "argv": [operation, *tail], "env": {}},
        # No status: argv is rejected before any common result exists.
        "expect": {"exitCode": 4, "stdout": "none", "reportFileCount": 0},
    }


def check_contract(identifier, manifest):
    if "status" in manifest["expect"] or "resultFile" in manifest["expect"]:
        raise ValueError("an argument error produces no common result")
    if manifest["expect"]["reportFileCount"] != 0:
        raise ValueError("an argument error must not write a report")
    operation = CASES[identifier][0]
    if manifest["invocation"]["argv"][0] != operation:
        raise ValueError("manifest operation differs from the reviewed case")
    if identifier.startswith("SINGLE-073") and "--report" not in manifest["invocation"]["argv"]:
        raise ValueError("the report-flag cases must pass --report")
    # The shared helper owns the stderr contract; exercise it for this operation so a
    # prefix or reason that stopped matching cannot pass unnoticed.
    check_cli_error_output(4, b"", f"bitz: {operation}: reason\n".encode(), operation)
    for bad in (f"bitz: {operation}: \n", f"bitz: other: reason\n",
                f"bitz: {operation}: reason\nextra\n"):
        try:
            check_cli_error_output(4, b"", bad.encode(), operation)
        except ValueError:
            continue
        raise ValueError("the stderr contract accepts output it should reject")


def validate(root=HERE, identifiers=None):
    errors, prepared = [], []
    validators = {name: Draft202012Validator(json.loads((root / f"{name}.schema.json").read_text()))
                  for name in ("manifest", "side-effects")}
    for identifier in CASES:
        if identifiers is not None and identifier not in identifiers:
            continue
        fixture = root / "single" / identifier
        try:
            manifest = json.loads((fixture / "manifest.json").read_text())
            effects = json.loads((fixture / "side-effects.json").read_text())
            validators["manifest"].validate(manifest)
            validators["side-effects"].validate(effects)
            if manifest != reviewed_manifest(identifier):
                raise ValueError("invocation differs from reviewed expectation")
            if json.loads((fixture / "cli-output.json").read_text()) != cli_output(identifier):
                raise ValueError("CLI output expectation differs from the reviewed contract")
            check_contract(identifier, manifest)
            if (fixture / "expected").exists():
                raise ValueError("an argument error fixture has no expected result file")
            inputs = reviewed_inputs(identifier)
            files = {p.relative_to(fixture / "repo").as_posix(): p
                     for p in (fixture / "repo").rglob("*") if p.is_file() or p.is_symlink()}
            if set(files) != set(inputs) or any(p.is_symlink() or p.read_bytes() != inputs[name]
                                                for name, p in files.items()):
                raise ValueError("input differs from the reviewed corpus")
            if effects["before"] != effects["after"]:
                raise ValueError("read-only expectation permits writes")
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-cli-error-") as temporary:
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
