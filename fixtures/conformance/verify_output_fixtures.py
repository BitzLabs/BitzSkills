"""Reviewed output-truncation verify vectors; runs no Core operation.

`SINGLE-069-01/02` fix a command whose stdout and stderr both exceed the 64 KiB
excerpt limit. The expected excerpt is the tail of the stream, so the corpus marks
the first and last lines differently: an excerpt that kept the head instead of the
tail, or that kept everything, cannot satisfy it.
"""
import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from . import digest_crosscheck, digest_reference
from .harness import setup
from .initial_fixtures import observe, compare_state

HERE = Path(__file__).resolve().parent
COMMAND_PATH = "bin/output.sh"
TEST_PATHS = ["tests/test_auth.py", "tests/test_session.py"]
STATEMENTS = ["REQ-001:AC-01", "REQ-001:AC-02"]
LIMIT = 65536
# Fixed 64-byte lines, so the 64 KiB tail lands exactly on a line boundary and the
# expected excerpt needs no assumption about partial lines.
LINE_BYTES = 64
HEAD = "verify-output-head" + "-" * 45
FILLER = "verify-output-filler" + "-" * 43
TAIL = "verify-output-tail" + "-" * 45
FILLER_COUNT = 1098
TOTAL_LINES = FILLER_COUNT + 2
EXCERPT_LINES = LIMIT // LINE_BYTES
EXCERPT = (FILLER + "\n") * (EXCERPT_LINES - 1) + TAIL + "\n"
SCRIPT = (
    "#!/bin/sh\n"
    f'head="{HEAD}"\n'
    f'filler="{FILLER}"\n'
    f'tail="{TAIL}"\n'
    'echo "$head"\n'
    'echo "$head" >&2\n'
    "i=1\n"
    f'while [ "$i" -le {FILLER_COUNT} ]; do\n'
    '    echo "$filler"\n'
    '    echo "$filler" >&2\n'
    "    i=$((i + 1))\n"
    "done\n"
    'echo "$tail"\n'
    'echo "$tail" >&2\n'
)
CASES = {
    "SINGLE-069-01": (0, "passed", 0),
    "SINGLE-069-02": (1, "failed", 1),
}
DESCRIPTIONS = {
    "SINGLE-069-01": "成功commandの64 KiB超の出力を末尾抜粋とtruncated flagで保持する",
    "SINGLE-069-02": "非0終了commandの64 KiB超の出力を末尾抜粋とtruncated flagで保持する",
}


def script(identifier):
    exit_code, _, _ = CASES[identifier]
    return SCRIPT + f"exit {exit_code}\n"


def reviewed_inputs(identifier):
    inputs = dict(digest_reference.reviewed_inputs("SINGLE-042"))
    inputs[digest_reference.CONFIG_PATH] = digest_reference.CONFIG.replace(
        '"/bin/true", "{tests}"', f'"{COMMAND_PATH}", "{{tests}}"').encode()
    inputs[COMMAND_PATH] = script(identifier).encode()
    return inputs


def executables(identifier):
    return {COMMAND_PATH}


def reviewed_digest_input(identifier):
    """The script body is not Digest material, so both fixtures share one Context."""
    payload = copy.deepcopy(digest_reference.reviewed_digest_input("SINGLE-042"))
    payload["settings"]["commands"][0]["argv"] = [COMMAND_PATH, "{tests}"]
    return payload


def context_digest(identifier):
    return digest_reference.digest(
        digest_reference.canonical_bytes(reviewed_digest_input(identifier)))


def reviewed_manifest(identifier):
    _, status, exit_code = CASES[identifier]
    return {
        "fixtureId": identifier,
        "description": DESCRIPTIONS[identifier],
        "setup": {"git": True, "operations": [{"op": "stage", "paths": ["."]}]},
        "invocation": {"runner": "bitz", "cwd": ".",
                       "argv": ["verify", "REQ-001", "--format", "json"], "env": {}},
        "expect": {"status": status, "exitCode": exit_code, "stdout": "json",
                   "resultFile": "expected/verify.json", "reportFileCount": 0},
    }


def reviewed_result(identifier):
    command_exit, status, _ = CASES[identifier]
    return {
        "schemaVersion": "1.0", "operation": "verify", "status": status, "scope": "selected",
        "workspace": {"id": "root", "path": "."},
        "targetResults": [{
            "target": "REQ-001", "status": status,
            "contextDigest": context_digest(identifier),
            "statements": list(STATEMENTS),
            "bindingRefs": ["root::default"], "diagnostics": []}],
        "revision": None,
        "commands": [{
            "bindingId": "root::default", "workspaceId": "root", "name": "default",
            "status": status, "termination": "exit", "cwd": ".",
            "argv": [COMMAND_PATH, *TEST_PATHS], "tests": list(TEST_PATHS),
            "covers": list(STATEMENTS),
            "exitCode": command_exit, "timeoutSeconds": 300,
            "stdoutExcerpt": EXCERPT, "stderrExcerpt": EXCERPT,
            "stdoutTruncated": True, "stderrTruncated": True, "durationMs": 0}],
        "durationMs": 0,
        "diagnostics": [],
    }


def check_excerpt_shape():
    """The reviewed excerpt must be the tail of an over-limit stream, on a line
    boundary, holding the tail marker and not the head marker."""
    if len(HEAD) + 1 != LINE_BYTES or len(FILLER) + 1 != LINE_BYTES or len(TAIL) + 1 != LINE_BYTES:
        raise ValueError("every line must be exactly the fixed width")
    if TOTAL_LINES * LINE_BYTES <= LIMIT:
        raise ValueError("the stream must exceed the excerpt limit")
    if len(EXCERPT.encode()) != LIMIT:
        raise ValueError("the excerpt must be exactly the 64 KiB tail")
    if HEAD in EXCERPT or TAIL not in EXCERPT:
        raise ValueError("the excerpt must drop the head marker and keep the tail marker")
    for keyword in ("token", "secret", "password", "passwd", "api_key", "private_key",
                    "credential", "auth"):
        if keyword in EXCERPT.lower():
            raise ValueError("the fixed output must not collide with a redaction pattern")


def observe_output(identifier, repository):
    """Run the fixture's own command file to confirm the reviewed excerpt is what it
    really produces. This is a fixture-side observation, not a Core verify run."""
    executable = repository / COMMAND_PATH
    if not (executable.is_file() and os.access(executable, os.X_OK)):
        raise ValueError("the command file must be a regular executable")
    completed = subprocess.run([str(executable)], cwd=repository, capture_output=True, timeout=60)
    command_exit = CASES[identifier][0]
    if completed.returncode != command_exit:
        raise ValueError("the command exit code differs from the reviewed expectation")
    for stream in (completed.stdout, completed.stderr):
        if len(stream) <= LIMIT:
            raise ValueError("the command did not exceed the excerpt limit")
        if stream[-LIMIT:].decode("utf-8") != EXCERPT:
            raise ValueError("the produced tail differs from the reviewed excerpt")


def validate(root=HERE, identifiers=None):
    errors, prepared = [], []
    validators = {name: Draft202012Validator(json.loads((root / f"{name}.schema.json").read_text()))
                  for name in ("manifest", "result", "side-effects")}
    for identifier in CASES:
        if identifiers is not None and identifier not in identifiers:
            continue
        fixture = root / "single" / identifier
        try:
            check_excerpt_shape()
            manifest = json.loads((fixture / "manifest.json").read_text())
            result = json.loads((fixture / "expected/verify.json").read_text())
            effects = json.loads((fixture / "side-effects.json").read_text())
            for name, value in (("manifest", manifest), ("result", result), ("side-effects", effects)):
                validators[name].validate(value)
            if manifest != reviewed_manifest(identifier) or result != reviewed_result(identifier):
                raise ValueError("invocation or complete result differs from reviewed expectation")
            command = result["commands"][0]
            if not (command["stdoutTruncated"] and command["stderrTruncated"]):
                raise ValueError("an over-limit stream must set its truncated flag")
            inputs = reviewed_inputs(identifier)
            files = {p.relative_to(fixture / "repo").as_posix(): p
                     for p in (fixture / "repo").rglob("*") if p.is_file() or p.is_symlink()}
            if set(files) != set(inputs):
                raise ValueError("input differs from the reviewed corpus")
            for name, path in files.items():
                if path.is_symlink() or path.read_bytes() != inputs[name]:
                    raise ValueError("input differs from the reviewed corpus")
                if bool(path.stat().st_mode & 0o111) != (name in executables(identifier)):
                    raise ValueError(f"executable bit of {name} differs from the reviewed input")
            if effects["before"] != effects["after"]:
                raise ValueError("read-only expectation permits writes")
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-verify-output-") as temporary:
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
                    derived = digest_crosscheck.canonical_bytes(digest_crosscheck.build(repository))
                    if digest_crosscheck.digest(derived) != context_digest(identifier):
                        raise ValueError("references disagree on the target Digest")
                    if run == 0:
                        observe_output(identifier, repository)
                    if compare_state(effects["after"], observe(repository, external)):
                        raise ValueError("observing the command changed the fixture state")
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, ValidationError,
                subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "references": 2, "observed_output": True,
            "status": "Passed" if not errors else "Failed", "errors": errors}
