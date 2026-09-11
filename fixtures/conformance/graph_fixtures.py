"""Reviewed duplicate-ID and self-cycle evidence; not a Core graph implementation."""
import json
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from .harness import setup
from .initial_fixtures import CONFIGS, observe, compare_state
from .trace_fixtures import TECH, TECH_PATH

HERE = Path(__file__).resolve().parent
CASES = {"SINGLE-015": None, "SINGLE-022-01": "requires", "SINGLE-022-02": "refines", "SINGLE-022-03": "related"}
DUPLICATE_PATHS = [".spec/technical/TECH-001-a.md", ".spec/technical/TECH-001-b.md"]


def reviewed_inputs(identifier):
    inputs = {".spec/bitz.yaml": CONFIGS["SINGLE-001"].encode()}
    relation = CASES[identifier]
    if relation is None:
        inputs.update({path: TECH.encode() for path in DUPLICATE_PATHS})
    else:
        inputs[TECH_PATH] = TECH.replace("status: approved\n---", f"status: approved\nrelations:\n  {relation}: [TECH-001]\n---", 1).encode()
    return inputs


def reviewed_manifest(identifier):
    status = "passed" if identifier == "SINGLE-022-03" else "failed"
    return {"fixtureId": identifier, "description": "文書ID重複" if identifier == "SINGLE-015" else f"{CASES[identifier]}の自己循環",
        "setup": {"git": True, "baseCommit": {"message": "base", "paths": ["."]}, "operations": []},
        "invocation": {"runner": "bitz", "cwd": ".", "argv": ["check", "--full", "--base", "HEAD", "--format", "json"], "env": {}},
        "expect": {"status": status, "exitCode": 0 if status == "passed" else 1,
            "stdout": "json", "resultFile": "expected/check.json", "reportFileCount": 0}}


def reviewed_result(identifier):
    duplicate = identifier == "SINGLE-015"
    passed = identifier == "SINGLE-022-03"
    diagnostics = [] if passed else [{
        "code": "SPEC-ID-DUPLICATE-001" if duplicate else "CTX-CYCLE-001", "severity": "error", "resultStatus": "failed",
        "summary": "文書ID TECH-001が重複しています" if duplicate else f"{CASES[identifier]}に禁止循環があります",
        "source": {"kind": "file", "workspaceId": "root", "path": DUPLICATE_PATHS[0] if duplicate else TECH_PATH,
                   "key": "id" if duplicate else f"relations.{CASES[identifier]}"}}]
    return {"schemaVersion": "1.0", "operation": "check", "status": "passed" if passed else "failed", "scope": "full",
        "workspace": {"id": "root", "path": "."}, "revision": {"base": "0" * 40, "commit": "0" * 40, "dirty": False},
        "checkedDocumentCount": 0 if duplicate else 1, "checkedStatementCount": 0, "durationMs": 0, "diagnostics": diagnostics}


def validate(root=HERE, identifiers=None):
    errors, prepared = [], []
    validators = {name: Draft202012Validator(json.loads((root / f"{name}.schema.json").read_text()))
                  for name in ("manifest", "result", "side-effects")}
    schema = json.loads((root / "frontmatter.schema.json").read_text())
    frontmatter = Draft202012Validator({"$ref": "#/$defs/techFrontmatter", "$defs": schema["$defs"]})
    for identifier, relation in CASES.items():
        if identifiers is not None and identifier not in identifiers:
            continue
        fixture = root / "single" / identifier
        try:
            manifest = json.loads((fixture / "manifest.json").read_text())
            result = json.loads((fixture / "expected/check.json").read_text())
            effects = json.loads((fixture / "side-effects.json").read_text())
            for name, value in (("manifest", manifest), ("result", result), ("side-effects", effects)):
                validators[name].validate(value)
            if manifest != reviewed_manifest(identifier) or result != reviewed_result(identifier):
                raise ValueError("invocation or complete result differs from reviewed expectation")
            inputs = reviewed_inputs(identifier)
            files = {p.relative_to(fixture / "repo").as_posix(): p for p in (fixture / "repo").rglob("*") if p.is_file() or p.is_symlink()}
            if set(files) != set(inputs) or any(p.is_symlink() or p.read_bytes() != inputs[name] for name, p in files.items()):
                raise ValueError("input differs from reviewed single cause")
            # Fixed YAML/value pair only; graph constraints intentionally lie outside JSON Schema.
            fm = {"id": "TECH-001", "title": "前提技術", "status": "approved"}
            if relation:
                fm["relations"] = {relation: ["TECH-001"]}
            frontmatter.validate(fm)
            if effects["before"] != effects["after"]:
                raise ValueError("read-only expectation permits writes")
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-graph-fixtures-") as temporary:
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
