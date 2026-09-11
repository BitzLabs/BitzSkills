"""Fixed relation/path/coverage evidence audit, not a Core resolver."""
import json
import os
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from .document_fixtures import DOCUMENT, REQ_PATH
from .harness import setup
from .initial_fixtures import CONFIGS, observe, compare_state

HERE = Path(__file__).resolve().parent
TECH_PATH = ".spec/technical/TECH-001.md"
TECH = "---\nid: TECH-001\ntitle: 前提技術\nstatus: approved\n---\n\n# TECH-001 前提技術\n\n## Context\n\n規範文を持たない前提技術。\n"
# Literal YAML and its independently reviewed value; no general YAML parser here.
# id: (YAML fields, decoded fields, code, source key, summary, status, document count)
CASES = {
    "SINGLE-020": ("relations:\n  requires: [REQ-999]\n", {"relations": {"requires": ["REQ-999"]}},
        "SPEC-RELATION-MISSING-001", "relations.requires", "strong relationの参照先が存在しません", "failed", 1),
    "SINGLE-021": ("relations:\n  refines: [TECH-001]\n", {"relations": {"refines": ["TECH-001"]}},
        "CTX-RELATION-TYPE-001", "relations.refines", "REQからTECHへのrefinesは許可されません", "failed", 2),
    "SINGLE-023": ("refs: [TECH-001]\n", {"refs": ["TECH-001"]},
        "SPEC-RELATION-LEGACY-001", "refs", "旧refs fieldは使用できません", "failed", 2),
    "SINGLE-024": ("implements: [src/missing.py]\n", {"implements": ["src/missing.py"]},
        "SPEC-PATH-INVALID-001", "implements", "実装pathが存在しません", "failed", 1),
    "SINGLE-025": ("implements: [src/missing.py]\n", {"implements": ["src/missing.py"]},
        "SPEC-PATH-INVALID-001", "implements", "draftの実装pathは未作成です", "passed_with_warnings", 1),
    "SINGLE-026": ("tests:\n  - path: tests/test_contract.py\n    covers: [REQ-001:AC-99]\n    command: default\n",
        {"tests": [{"path": "tests/test_contract.py", "covers": ["REQ-001:AC-99"], "command": "default"}]},
        "SPEC-TEST-COVERAGE-001", "tests[0].covers", "coversが存在しない規範文を参照しています", "failed", 1),
}


def reviewed_inputs(identifier):
    fields = CASES[identifier][0]
    document = DOCUMENT.replace("status: approved\n---", "status: approved\n" + fields + "---", 1)
    if identifier == "SINGLE-025":
        document = document.replace("status: approved", "status: draft", 1)
    inputs = {REQ_PATH: document.encode(), ".spec/bitz.yaml": CONFIGS["SINGLE-001"].encode()}
    if identifier in {"SINGLE-021", "SINGLE-023"}:
        inputs[TECH_PATH] = TECH.encode()
    if identifier == "SINGLE-026":
        inputs[".spec/bitz.yaml"] += b'verify:\n  commands:\n    default:\n      argv: ["/bin/true"]\n      cwd: .\n'
        inputs["tests/test_contract.py"] = b'raise RuntimeError("check must not execute this file")\n'
    return inputs


def reviewed_manifest(identifier):
    status = CASES[identifier][5]
    return {
        "fixtureId": identifier, "description": CASES[identifier][4],
        "setup": {"git": True, "baseCommit": {"message": "base", "paths": ["."]}, "operations": []},
        "invocation": {"runner": "bitz", "cwd": ".", "argv": ["check", "--full", "--base", "HEAD", "--format", "json"], "env": {}},
        "expect": {"status": status, "exitCode": 0 if status == "passed_with_warnings" else 1,
            "stdout": "json", "resultFile": "expected/check.json", "reportFileCount": 0},
    }


def reviewed_result(identifier):
    _, _, code, key, summary, status, documents = CASES[identifier]
    return {
        "schemaVersion": "1.0", "operation": "check", "status": status, "scope": "full",
        "workspace": {"id": "root", "path": "."},
        "revision": {"base": "0" * 40, "commit": "0" * 40, "dirty": False},
        "checkedDocumentCount": documents, "checkedStatementCount": 1, "durationMs": 0,
        "diagnostics": [{"code": code, "severity": "warning" if status == "passed_with_warnings" else "error",
            "resultStatus": status, "summary": summary,
            "source": {"kind": "file", "workspaceId": "root", "path": REQ_PATH, "key": key}}],
    }


def validate(root=HERE, identifiers=None):
    errors, prepared = [], []
    validators = {name: Draft202012Validator(json.loads((root / f"{name}.schema.json").read_text()))
                  for name in ("manifest", "result", "side-effects")}
    fm_schema = json.loads((root / "frontmatter.schema.json").read_text())
    for identifier in CASES:
        if identifiers is not None and identifier not in identifiers:
            continue
        fixture = root / "single" / identifier
        try:
            manifest = json.loads((fixture / "manifest.json").read_text())
            validators["manifest"].validate(manifest)
            if manifest != reviewed_manifest(identifier):
                raise ValueError("manifest differs from reviewed invocation")
            result = json.loads((fixture / "expected/check.json").read_text())
            validators["result"].validate(result)
            if result != reviewed_result(identifier):
                raise ValueError("result differs from reviewed complete expectation")
            inputs = reviewed_inputs(identifier)
            actual_files = {p.relative_to(fixture / "repo").as_posix(): p for p in (fixture / "repo").rglob("*")
                            if p.is_file() or p.is_symlink()}
            if set(actual_files) != set(inputs) or any(p.is_symlink() or p.read_bytes() != inputs[name]
                                                      for name, p in actual_files.items()):
                raise ValueError("input differs from reviewed single cause")
            fm = {"id": "REQ-001", "title": "文書の検査", "status": "draft" if identifier == "SINGLE-025" else "approved",
                  **CASES[identifier][1]}
            Draft202012Validator({"$ref": "#/$defs/reqFrontmatter", "$defs": fm_schema["$defs"]}).validate(fm)
            if TECH_PATH in inputs:
                Draft202012Validator({"$ref": "#/$defs/techFrontmatter", "$defs": fm_schema["$defs"]}).validate(
                    {"id": "TECH-001", "title": "前提技術", "status": "approved"})
            if identifier == "SINGLE-026" and (not Path("/bin/true").is_file() or not os.access("/bin/true", os.X_OK)):
                raise ValueError("coverage case requires executable /bin/true on the Linux fixture host")
            effects = json.loads((fixture / "side-effects.json").read_text())
            validators["side-effects"].validate(effects)
            if effects["before"] != effects["after"]:
                raise ValueError("read-only expectation permits writes")
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-trace-fixtures-") as temporary:
                for run in range(2):
                    sandbox = Path(temporary) / str(run)
                    sandbox.mkdir()
                    repository = setup(fixture, manifest, sandbox / "repo")
                    external = {name: sandbox / name for name in ("home", "cache", "temporary")}
                    for directory in external.values():
                        directory.mkdir()
                    actual = observe(repository, external)
                    if compare_state(effects["before"], actual) or (previous is not None and previous != actual):
                        raise ValueError("isolated setup differs from fixed snapshot")
                    previous = actual
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, ValidationError, subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "status": "Passed" if not errors else "Failed", "errors": errors}
