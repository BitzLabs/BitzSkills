"""Audit the five introduction/config fixtures; never invokes or emulates Core."""
import json
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from .harness import git, safe_path, setup, snapshot

HERE = Path(__file__).resolve().parent
CASES = {
    "SINGLE-001": ("doctor", "passed", 0),
    "SINGLE-002": ("doctor", "blocked", 2),
    "SINGLE-003": ("check", "blocked", 2),
    "SINGLE-004-01": ("check", "error", 3),
    "SINGLE-004-02": ("check", "error", 3),
}
# Independent, deliberately limited review of the single cause in each input.
# This is not a YAML parser or a production configuration validator.
CONFIGS = {
    "SINGLE-001": 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\n',
    "SINGLE-003": 'schemaVersion: "2.0"\nlanguage: ja\nearsAi: "1.0"\n',
    "SINGLE-004-01": 'schemaVersion: "1.0"\nlanguage: 42\nearsAi: "1.0"\n',
    "SINGLE-004-02": 'schemaVersion: "1.0"\nlanguage: ja\n',
}


def observe(repository, external):
    return {
        "repository": snapshot(repository),
        "git": {
            "status": git(repository, "status", "--porcelain=v1", "--untracked-files=all").decode(),
            "index": git(repository, "ls-files", "--stage").decode(),
        },
        **{name: snapshot(path) for name, path in external.items()},
    }


def compare_state(expected, observed):
    """Do not normalize away new files, changed Git index, or external caches."""
    return [name for name in sorted(expected.keys() | observed.keys()) if expected.get(name) != observed.get(name)]


def validate(root=HERE):
    errors, prepared = [], []
    validators = {name: Draft202012Validator(json.loads((root / f"{name}.schema.json").read_text()))
                  for name in ("manifest", "result", "side-effects")}
    for identifier, (operation, status, exit_code) in CASES.items():
        fixture = root / "single" / identifier
        try:
            manifest = json.loads((fixture / "manifest.json").read_text())
            validators["manifest"].validate(manifest)
            expect = manifest["expect"]
            expected_argv = ["doctor", "--format", "json"] if operation == "doctor" else ["check", "--full", "--base", "HEAD", "--format", "json"]
            expected_setup = {"git": True, "operations": []}
            if operation == "check":
                expected_setup["baseCommit"] = {"message": "base", "paths": ["."]}
            elif identifier == "SINGLE-002":
                expected_setup["operations"] = [{"op": "delete", "path": ".gitkeep"}]
            if (manifest["fixtureId"] != identifier or manifest["setup"] != expected_setup
                    or manifest["invocation"] != {"runner": "bitz", "cwd": ".", "argv": expected_argv, "env": {}}
                    or expect != {"status": status, "exitCode": exit_code, "stdout": "json",
                                  "resultFile": f"expected/{operation}.json", "reportFileCount": 0}):
                raise ValueError("manifest differs from reviewed single-cause invocation")
            expected_path = safe_path(fixture, expect["resultFile"])
            result = json.loads(expected_path.read_text())
            validators["result"].validate(result)
            if result["operation"] != operation or result["status"] != status:
                raise ValueError("manifest/result operation or status mismatch")
            diagnostics = result["diagnostics"]
            if len(diagnostics) != (0 if identifier == "SINGLE-001" else 1):
                raise ValueError("unexpected number of independent causes")
            identity = "root" if identifier in {"SINGLE-001", "SINGLE-003"} else None
            if result["workspace"] != {"id": identity, "path": "."}:
                raise ValueError("incorrect workspace identity")
            if operation == "check":
                key = {"SINGLE-003": "schemaVersion", "SINGLE-004-01": "language", "SINGLE-004-02": "earsAi"}[identifier]
                if (result["scope"] != "full" or result["checkedDocumentCount"] != 0 or result["checkedStatementCount"] != 0
                        or result["revision"] is None or result["revision"]["dirty"]):
                    raise ValueError("config rejection must precede indexing with clean committed revision")
                diagnostic = diagnostics[0]
                if (diagnostic["code"] != "SPEC-CONFIG-SCHEMA-001" or diagnostic["severity"] != "error"
                        or diagnostic["resultStatus"] != status
                        or diagnostic["source"] != {"kind": "file", "workspaceId": identity, "path": ".spec/bitz.yaml", "key": key}):
                    raise ValueError("incorrect configuration Diagnostic")
            else:
                checks = ([{"name": name, "status": "info" if name == "impact" else "passed"}
                           for name in ("core", "workspace", "config", "schema", "ears", "git", "command", "impact")]
                          if identifier == "SINGLE-001" else [
                              {"name": "core", "status": "passed"}, {"name": "workspace", "status": "blocked"},
                              {"name": "git", "status": "passed"}])
                if result["checks"] != checks or result["core"] != {
                    "version": "1.0.0", "apiVersion": "1.0",
                    "capabilities": ["context.v1", "check.v1", "verify.v1", "doctor.v1", "monorepo.v1"],
                }:
                    raise ValueError("incorrect doctor checks or Core 1.0 expectation")
                if diagnostics:
                    diagnostic = diagnostics[0]
                    if (diagnostic["code"] != "SPEC-DOCTOR-WORKSPACE-001" or diagnostic["severity"] != "error"
                            or diagnostic["resultStatus"] != "blocked" or diagnostic["source"] != {
                                "kind": "environment", "component": "workspace", "identifier": "."}):
                        raise ValueError("incorrect missing-workspace Diagnostic")
                    action = diagnostic.get("suggestedAction", "")
                    if any(text not in action for text in (".spec/bitz.yaml", CONFIGS["SINGLE-001"], ".gitignore", ".spec/reports/", "bitz check --full")):
                        raise ValueError("missing pasteable recovery instructions")
            effects = json.loads((fixture / "side-effects.json").read_text())
            validators["side-effects"].validate(effects)
            if effects["before"] != effects["after"]:
                raise ValueError("read-only fixture permits side effects")
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-initial-fixtures-") as temporary:
                for run in range(2):
                    sandbox = Path(temporary) / str(run)
                    sandbox.mkdir()
                    repository = setup(fixture, manifest, sandbox / "repo")
                    external = {name: sandbox / name for name in ("home", "cache", "temporary")}
                    for directory in external.values():
                        directory.mkdir()
                    actual = observe(repository, external)
                    if compare_state(effects["before"], actual):
                        raise ValueError("setup differs from fixed before snapshot")
                    if previous is not None and actual != previous:
                        raise ValueError("two isolated setups differ")
                    previous = actual
                    config = repository / ".spec/bitz.yaml"
                    if identifier in CONFIGS and config.read_bytes() != CONFIGS[identifier].encode():
                        raise ValueError("input differs from reviewed cause")
                    if identifier == "SINGLE-002" and (repository / ".spec").exists():
                        raise ValueError("missing-workspace fixture must have no .spec directory")
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, ValidationError, subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "status": "Passed" if not errors else "Failed", "errors": errors}
