"""Reviewed process-termination verify vectors; runs no Core operation.

`SINGLE-057`, `SINGLE-058` and `SINGLE-059` each fail after the pre-checks pass,
so every one records a `commands[]` entry rather than a pre-spawn block. The audit
runs each fixture's own command file directly — never through Core — to confirm the
input really produces the reviewed termination, so the expectation is not merely
asserted.
"""
import copy
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import tempfile
import time

from jsonschema import Draft202012Validator, ValidationError

from . import digest_crosscheck, digest_reference
from .harness import setup
from .initial_fixtures import observe, compare_state

HERE = Path(__file__).resolve().parent
TEST_PATHS = ["tests/test_auth.py", "tests/test_session.py"]
STATEMENTS = ["REQ-001:AC-01", "REQ-001:AC-02"]
# A regular file carrying the executable bit whose format the kernel refuses:
# no ELF magic and no shebang, so execve fails with ENOEXEC after the pre-checks pass.
BAD_FORMAT = "this file is executable but is not a program\n"
SIGNAL_SCRIPT = "#!/bin/sh\nkill -TERM $$\n"
# Ignores SIGTERM and leaves a child holding the inherited stdout/stderr pipes, so
# neither graceful termination nor EOF can end the binding on their own. The readiness
# line is printed only after the trap is installed, and the surviving child keeps the
# pipe open afterwards, so a reader that waits for EOF never finishes.
READY = "hang-ready"
HANG_SCRIPT = (
    "#!/bin/sh\n"
    "trap '' TERM\n"
    # The child ignores TERM too, so it keeps the inherited pipes open after a
    # group-wide graceful termination.
    "sh -c \"trap '' TERM; sleep 60\" &\n"
    "echo " + READY + "\n"
    # A killed foreground sleep must not end the script, or a group TERM would be
    # enough and the fixture would never require a force kill.
    "i=0\n"
    "while [ \"$i\" -lt 60 ]; do\n"
    "    sleep 1\n"
    "    i=$((i + 1))\n"
    "done\n"
)
COMMANDS = {
    "SINGLE-057": ("bin/badformat", BAD_FORMAT, "spawn_error", "SPEC-VERIFY-COMMAND-001", 300),
    "SINGLE-058": ("bin/signal.sh", SIGNAL_SCRIPT, "signal", "SPEC-VERIFY-COMMAND-001", 300),
    "SINGLE-059": ("bin/hang.sh", HANG_SCRIPT, "timeout", "SPEC-VERIFY-TIMEOUT-001", 1),
}
SUMMARIES = {
    "SINGLE-057": "commandの実行形式をOSが拒否しprocessを生成できません",
    "SINGLE-058": "commandがsignalで終了しました",
    "SINGLE-059": "commandが実効timeout 1秒で終了しませんでした",
}
DESCRIPTIONS = {
    "SINGLE-057": "事前検査通過後のprocess生成失敗をspawn_errorで記録する",
    "SINGLE-058": "commandのsignal終了をterminationへ記録する",
    "SINGLE-059": "timeout後も終了しない直接processを有限時間で確定する",
}
CASES = tuple(COMMANDS)


def config(identifier):
    path, _, _, _, timeout = COMMANDS[identifier]
    body = digest_reference.CONFIG.replace('"/bin/true", "{tests}"', f'"{path}", "{{tests}}"')
    if timeout != 300:
        body = body.replace("verify:\n", f"verify:\n  timeoutSeconds: {timeout}\n", 1)
    return body


def reviewed_inputs(identifier):
    path, content, _, _, _ = COMMANDS[identifier]
    inputs = dict(digest_reference.reviewed_inputs("SINGLE-042"))
    inputs[digest_reference.CONFIG_PATH] = config(identifier).encode()
    inputs[path] = content.encode()
    return inputs


def executables(identifier):
    return {COMMANDS[identifier][0]}


def reviewed_digest_input(identifier):
    path, _, _, _, timeout = COMMANDS[identifier]
    payload = copy.deepcopy(digest_reference.reviewed_digest_input("SINGLE-042"))
    payload["settings"]["commands"][0]["argv"] = [path, "{tests}"]
    payload["settings"]["verifyTimeouts"][0]["timeoutSeconds"] = timeout
    return payload


def context_digest(identifier):
    return digest_reference.digest(
        digest_reference.canonical_bytes(reviewed_digest_input(identifier)))


def expected_stdout(identifier):
    """Only the timeout fixture writes, and it writes exactly one readiness line
    before its descendant holds the pipe open."""
    return READY + "\n" if identifier == "SINGLE-059" else ""


def reviewed_manifest(identifier):
    return {
        "fixtureId": identifier,
        "description": DESCRIPTIONS[identifier],
        "setup": {"git": True, "operations": [{"op": "stage", "paths": ["."]}]},
        "invocation": {"runner": "bitz", "cwd": ".",
                       "argv": ["verify", "REQ-001", "--format", "json"], "env": {}},
        "expect": {"status": "error", "exitCode": 3, "stdout": "json",
                   "resultFile": "expected/verify.json", "reportFileCount": 0},
    }


def reviewed_result(identifier):
    path, _, termination, code, timeout = COMMANDS[identifier]
    return {
        "schemaVersion": "1.0", "operation": "verify", "status": "error", "scope": "selected",
        "workspace": {"id": "root", "path": "."},
        "targetResults": [{
            "target": "REQ-001", "status": "error",
            "contextDigest": context_digest(identifier),
            "statements": list(STATEMENTS),
            "bindingRefs": ["root::default"], "diagnostics": []}],
        "revision": None,
        "commands": [{
            "bindingId": "root::default", "workspaceId": "root", "name": "default",
            "status": "error", "termination": termination, "cwd": ".",
            "argv": [path, *TEST_PATHS], "tests": list(TEST_PATHS), "covers": list(STATEMENTS),
            "exitCode": None, "timeoutSeconds": timeout,
            "stdoutExcerpt": expected_stdout(identifier), "stderrExcerpt": "",
            "stdoutTruncated": False, "stderrTruncated": False, "durationMs": 0}],
        "durationMs": 0,
        "diagnostics": [{
            "code": code, "severity": "error", "resultStatus": "error",
            "summary": SUMMARIES[identifier],
            "source": {"kind": "environment", "component": "command", "identifier": "root::default"}}],
    }


def observe_termination(identifier, repository):
    """Run the fixture's own command file directly to confirm the reviewed cause.
    This is a fixture-side observation of the input, not a Core verify run."""
    path, _, termination, _, _ = COMMANDS[identifier]
    executable = repository / path
    if not (executable.is_file() and os.access(executable, os.X_OK)):
        raise ValueError("the command file must be a regular executable before spawn")
    if termination == "spawn_error":
        try:
            subprocess.run([str(executable)], cwd=repository, capture_output=True, timeout=10)
        except OSError:
            return
        raise ValueError("the command file was accepted by the OS, so no spawn error occurs")
    if termination == "signal":
        completed = subprocess.run([str(executable)], cwd=repository, capture_output=True, timeout=10)
        if completed.returncode != -signal.SIGTERM:
            raise ValueError("the command did not terminate by signal")
        return
    # timeout: graceful termination must be insufficient and a force kill must end it.
    process = subprocess.Popen([str(executable)], cwd=repository, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, start_new_session=True, text=True)
    try:
        deadline = time.monotonic() + 5
        # Wait for the readiness line, so the trap is already installed. Signalling
        # before it would only prove that an unprotected startup can be killed.
        if not select.select([process.stdout], [], [], 5)[0]:
            raise ValueError("the command produced no readiness line")
        if process.stdout.readline().strip() != READY:
            raise ValueError("the command did not announce readiness")
        os.killpg(process.pid, signal.SIGTERM)
        time.sleep(0.5)
        if process.poll() is not None:
            raise ValueError("the command stopped on graceful termination, so no force kill is needed")
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=max(0.1, deadline - time.monotonic()))
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)
        for stream in (process.stdout, process.stderr):
            if stream is not None:
                stream.close()


def validate(root=HERE, identifiers=None):
    errors, prepared = [], []
    validators = {name: Draft202012Validator(json.loads((root / f"{name}.schema.json").read_text()))
                  for name in ("manifest", "result", "side-effects")}
    for identifier in CASES:
        if identifiers is not None and identifier not in identifiers:
            continue
        fixture = root / "single" / identifier
        try:
            manifest = json.loads((fixture / "manifest.json").read_text())
            result = json.loads((fixture / "expected/verify.json").read_text())
            effects = json.loads((fixture / "side-effects.json").read_text())
            for name, value in (("manifest", manifest), ("result", result), ("side-effects", effects)):
                validators[name].validate(value)
            if manifest != reviewed_manifest(identifier) or result != reviewed_result(identifier):
                raise ValueError("invocation or complete result differs from reviewed expectation")
            command = result["commands"][0]
            if command["exitCode"] is not None or command["status"] != "error":
                raise ValueError("a non-exit termination must report no exit code and error status")
            if command["stdoutExcerpt"] != expected_stdout(identifier) or command["stderrExcerpt"]:
                raise ValueError("command excerpts differ from the reviewed output")
            inputs = reviewed_inputs(identifier)
            expected_executables = executables(identifier)
            files = {p.relative_to(fixture / "repo").as_posix(): p
                     for p in (fixture / "repo").rglob("*") if p.is_file() or p.is_symlink()}
            if set(files) != set(inputs):
                raise ValueError("input differs from the reviewed corpus")
            for name, path in files.items():
                if path.is_symlink() or path.read_bytes() != inputs[name]:
                    raise ValueError("input differs from the reviewed corpus")
                if bool(path.stat().st_mode & 0o111) != (name in expected_executables):
                    raise ValueError(f"executable bit of {name} differs from the reviewed input")
            if effects["before"] != effects["after"]:
                raise ValueError("read-only expectation permits writes")
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-verify-process-") as temporary:
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
                        observe_termination(identifier, repository)
                    if compare_state(effects["after"], observe(repository, external)):
                        raise ValueError("observing the command changed the fixture state")
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, ValidationError,
                subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "references": 2, "observed_terminations": True,
            "status": "Passed" if not errors else "Failed", "errors": errors}
