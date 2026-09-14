"""Reviewed text/JSON parity fixtures; no production renderer or Core execution."""
import json
from pathlib import Path
import re
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from . import report_absent_fixtures as source
from .harness import setup
from .initial_fixtures import observe, compare_state

HERE = Path(__file__).resolve().parent
CASES = {"SINGLE-075-01": "SINGLE-070-01", "SINGLE-075-02": "SINGLE-070-02"}
TEXT = {
    "SINGLE-075-01": "check passed scope=full targets=3 diagnostics=0 (0ms)\n",
    "SINGLE-075-02": "check failed scope=full targets=3 diagnostics=1 (0ms)\n"
                     "root:.spec/technical/TECH-001.md::: error: SPEC-RELATION-MISSING-001: "
                     "strong relationの参照先が存在しません\n",
}


def reviewed_manifest(identifier):
    manifest = source.reviewed_manifest(CASES[identifier])
    manifest["fixtureId"] = identifier
    manifest["description"] = "text出力のstatus・件数・DiagnosticがJSON結果と一致する"
    manifest["invocation"]["argv"][-1] = "text"
    manifest["expect"].update(stdout="text", textFile="expected/check.txt")
    return manifest


def normalize_text(value):
    """Only the byte-level duration token may vary (fixture contract section 4)."""
    return re.sub(rb"\([0-9]+ms\)", b"(<duration>ms)", value)


def validate(root=HERE, identifiers=None):
    errors, prepared = [], []
    validators = {name: Draft202012Validator(json.loads((root / f"{name}.schema.json").read_text()))
                  for name in ("manifest", "result", "side-effects")}
    for identifier, original in CASES.items():
        if identifiers is not None and identifier not in identifiers:
            continue
        fixture = root / "single" / identifier
        try:
            manifest = json.loads((fixture / "manifest.json").read_text())
            result = json.loads((fixture / "expected/check.json").read_text())
            effects = json.loads((fixture / "side-effects.json").read_text())
            for name, value in (("manifest", manifest), ("result", result), ("side-effects", effects)):
                validators[name].validate(value)
            if manifest != reviewed_manifest(identifier) or result != source.reviewed_result(original):
                raise ValueError("manifest or JSON counterpart differs from the reviewed case")
            # Committed text uses a fixed duration; only actual output is variable at Gate B.
            if (fixture / "expected/check.txt").read_bytes() != TEXT[identifier].encode():
                raise ValueError("text differs from the reviewed complete output")
            inputs = source.reviewed_inputs(original)
            files = {p.relative_to(fixture / "repo").as_posix(): p
                     for p in (fixture / "repo").rglob("*") if p.is_file() or p.is_symlink()}
            if set(files) != set(inputs) or any(p.is_symlink() or p.read_bytes() != inputs[name]
                                                for name, p in files.items()):
                raise ValueError("input differs from the JSON counterpart")
            source.check_report_expectation(manifest, effects)
            if effects["policy"] != "read-only" or effects["before"] != effects["after"]:
                raise ValueError("text formatting must not permit writes")
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-text-") as temporary:
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
        except (OSError, ValueError, KeyError, TypeError, ValidationError, subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "status": "Passed" if not errors else "Failed", "errors": errors}
