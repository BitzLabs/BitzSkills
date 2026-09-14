"""Reviewed explicit-report vectors; runs no Core operation.

`SINGLE-071-01..04` pin that `--report` creates exactly one file in `.spec/reports/`
for `check` and `verify`, on success and on failure alike, and `SINGLE-072` pins
that an unusable report destination is an error which still returns the original
result to the terminal.
"""
import json
from pathlib import Path
import re
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from . import digest_reference, report_absent_fixtures, verify_fixtures
from .harness import setup
from .initial_fixtures import observe, compare_state

HERE = Path(__file__).resolve().parent
REPORT_DIRECTORY = ".spec/reports"
EXISTING_REPORT = report_absent_fixtures.EXISTING_REPORT
# 結果・Diagnostic・終了コード §8: <YYYYMMDDTHHMMSSZ>-<operation>[-<sequence>].json
NAME_PATTERN = r"^[0-9]{8}T[0-9]{6}Z-(?:check|verify)(?:-[1-9][0-9]*)?\.json$"
# A regular file where the report directory belongs: version-controllable, unlike a
# directory mode, which Git does not record and a fresh checkout would not restore.
BLOCKING_FILE = b"this path occupies the report directory\n"
# id: (operation, status, exit code, source fixture for the reviewed result)
CASES = {
    "SINGLE-071-01": ("check", "passed", 0, "SINGLE-070-01"),
    "SINGLE-071-02": ("check", "failed", 1, "SINGLE-070-02"),
    "SINGLE-071-03": ("verify", "passed", 0, "SINGLE-070-03"),
    "SINGLE-071-04": ("verify", "failed", 1, "SINGLE-070-04"),
    # Based on the failing check, so "the original result survives" is not vacuous.
    "SINGLE-072": ("check", "error", 3, "SINGLE-070-02"),
}
DESCRIPTIONS = {
    "SINGLE-071-01": "明示--report付きの成功checkが規定先へ1件を排他的作成する",
    "SINGLE-071-02": "明示--report付きの失敗checkが規定先へ1件を排他的作成する",
    "SINGLE-071-03": "明示--report付きの成功verifyが規定先へ1件を排他的作成する",
    "SINGLE-071-04": "明示--report付きの失敗verifyが規定先へ1件を排他的作成する",
    "SINGLE-072": "report保存先が書込み不能でも元結果を端末へ保持する",
}


def reviewed_inputs(identifier):
    inputs = dict(report_absent_fixtures.reviewed_inputs(CASES[identifier][3]))
    if identifier == "SINGLE-072":
        # The report directory cannot exist, because a regular file occupies its path.
        del inputs[EXISTING_REPORT]
        inputs[REPORT_DIRECTORY] = BLOCKING_FILE
    return inputs


def reviewed_manifest(identifier):
    operation, status, exit_code, source = CASES[identifier]
    manifest = report_absent_fixtures.reviewed_manifest(source)
    argv = list(manifest["invocation"]["argv"]) + ["--report"]
    return {
        "fixtureId": identifier,
        "description": DESCRIPTIONS[identifier],
        "setup": manifest["setup"],
        "invocation": {"runner": "bitz", "cwd": ".", "argv": argv, "env": {}},
        "expect": {"status": status, "exitCode": exit_code, "stdout": "json",
                   "resultFile": f"expected/{operation}.json",
                   "reportFileCount": 0 if identifier == "SINGLE-072" else 1},
    }


def reviewed_result(identifier):
    operation, status, _, source = CASES[identifier]
    result = json.loads(json.dumps(report_absent_fixtures.reviewed_result(source)))
    if identifier != "SINGLE-072":
        # Saving a report does not change the result that was already computed.
        return result
    # The original result and its Diagnostics stay on the terminal; only the status
    # and the save failure are added.
    result["status"] = "error"
    result["diagnostics"] = result["diagnostics"] + [{
        "code": "SPEC-REPORT-WRITE-001", "severity": "error", "resultStatus": "error",
        "summary": "report保存先へ排他的に作成できません",
        "source": {"kind": "file", "workspaceId": "root", "path": REPORT_DIRECTORY}}]
    return result


def reviewed_effects(identifier, state):
    effects = {"schemaVersion": "1.0", "policy": "read-only", "before": state, "after": state}
    if identifier != "SINGLE-072":
        effects["policy"] = "explicit-report"
        effects["report"] = {"directory": REPORT_DIRECTORY, "createdCount": 1,
                             "namePattern": NAME_PATTERN, "temporaryFilesRemaining": 0}
    return effects


def check_report_contract(identifier, manifest, effects, result):
    if "--report" not in manifest["invocation"]["argv"]:
        raise ValueError("this group must pass --report")
    expected = manifest["expect"]["reportFileCount"]
    if identifier == "SINGLE-072":
        if effects["policy"] != "read-only" or "report" in effects or expected != 0:
            raise ValueError("a failed save must leave the tree untouched")
        source = report_absent_fixtures.reviewed_result(CASES[identifier][3])
        keys = ("status", "diagnostics")
        if {k: v for k, v in result.items() if k not in keys} != {
                k: v for k, v in source.items() if k not in keys}:
            raise ValueError("the original result must survive on the terminal")
        if ([d["code"] for d in result["diagnostics"]]
                != [d["code"] for d in source["diagnostics"]] + ["SPEC-REPORT-WRITE-001"]):
            raise ValueError("the save failure must be appended to the original Diagnostics")
        if not source["diagnostics"]:
            raise ValueError("this case must start from a result that already has Diagnostics")
        return
    if effects["policy"] != "explicit-report" or effects["report"]["createdCount"] != expected:
        raise ValueError("the created report count differs from the manifest")
    if effects["report"]["temporaryFilesRemaining"] != 0:
        raise ValueError("atomic creation must leave no temporary file")
    operation = manifest["invocation"]["argv"][0]
    sample = f"20000101T000000Z-{operation}.json"
    if not re.fullmatch(effects["report"]["namePattern"], sample):
        raise ValueError("the reviewed name pattern rejects a valid report name")
    for bad in (f"{operation}.json", f"20000101T000000Z-{operation}-0.json",
                f"20000101T000000Z-context.json", f"20000101T000000Z-{operation}.json.tmp"):
        if re.fullmatch(effects["report"]["namePattern"], bad):
            raise ValueError("the reviewed name pattern accepts an invalid report name")
    if EXISTING_REPORT not in effects["before"]["repository"]:
        raise ValueError("exclusive creation is untested without a pre-existing report")


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
            if effects != reviewed_effects(identifier, effects["before"]):
                raise ValueError("side-effect expectation differs from reviewed policy")
            check_report_contract(identifier, manifest, effects, result)
            inputs = reviewed_inputs(identifier)
            files = {p.relative_to(fixture / "repo").as_posix(): p
                     for p in (fixture / "repo").rglob("*") if p.is_file() or p.is_symlink()}
            if set(files) != set(inputs) or any(p.is_symlink() or p.read_bytes() != inputs[name]
                                                for name, p in files.items()):
                raise ValueError("input differs from the reviewed corpus")
            if effects["before"] != effects["after"]:
                raise ValueError("every path that already existed must be unchanged")
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-report-write-") as temporary:
                for run in range(2):
                    sandbox = Path(temporary) / str(run)
                    sandbox.mkdir()
                    repository = setup(fixture, manifest, sandbox / "repo")
                    reports = repository / REPORT_DIRECTORY
                    if identifier == "SINGLE-072":
                        if not reports.is_file():
                            raise ValueError("the blocked case requires a file at the report path")
                    elif not reports.is_dir():
                        raise ValueError("the report directory must exist before the run")
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
