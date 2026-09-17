"""複合workspaceの全体操作とreportを固定するreview済みvector（Core操作は実行しない）。

`--report`がなければ全体操作はstatusにかかわらずfileを作らず、指定した場合だけroot workspaceの
`.spec/reports/`へ1件を排他的に作成する（[結果・Diagnostic・終了コード §8](../../docs/03.詳細設計/00_共通契約/01_結果・Diagnostic・終了コード.md)）。
`MULTI-022-01..04`は、checkとverifyのそれぞれで既定と明示指定を対にし、結果本体が変わらないことも固定する。
"""
import json
from pathlib import Path
import re
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from . import multi_verify_fixtures
from .harness import setup
from .initial_fixtures import observe, compare_state

HERE = Path(__file__).resolve().parent
COMMIT = "0" * 40
CORPUS = "MULTI-013"
REPORT_DIRECTORY = ".spec/reports"
EXISTING_REPORT = f"{REPORT_DIRECTORY}/existing.json"
NAME_PATTERN = r"^[0-9]{8}T[0-9]{6}Z-(?:check|verify)(?:-[1-9][0-9]*)?\.json$"
# id: (操作, --reportの有無, 説明)
CASES = {
    "MULTI-022-01": ("check", False, "既定の全体checkはreportを作らない"),
    "MULTI-022-02": ("check", True, "明示--report付きの全体checkがroot workspaceへ1件を作る"),
    "MULTI-022-03": ("verify", False, "既定の全体verifyはreportを作らない"),
    "MULTI-022-04": ("verify", True, "明示--report付きの全体verifyがroot workspaceへ1件を作る"),
}


def reviewed_inputs():
    """全workspaceが対象を持つcorpusへ、既存のreport fileを1件加える。"""
    return {**multi_verify_fixtures.reviewed_inputs(CORPUS), EXISTING_REPORT: b"{}\n"}


def reviewed_manifest(identifier):
    operation, report, description = CASES[identifier]
    argv = [operation, "--all-workspaces"]
    if operation == "check":
        argv += ["--base", "HEAD"]
    argv += ["--format", "json"]
    if report:
        argv.append("--report")
    return {
        "fixtureId": identifier,
        "description": description,
        "setup": {"git": True, "baseCommit": {"message": "base", "paths": ["."]}, "operations": []},
        "invocation": {"runner": "bitz", "cwd": ".", "argv": argv, "env": {}},
        "expect": {"status": "passed", "exitCode": 0, "stdout": "json",
                   "resultFile": f"expected/{operation}.json",
                   "reportFileCount": 1 if report else 0},
    }


def reviewed_result(identifier):
    operation = CASES[identifier][0]
    if operation == "verify":
        # reportを保存しても、計算済みの結果は変わらない。同じcorpusの結果をそのまま使う。
        return json.loads(json.dumps(multi_verify_fixtures.reviewed_result(CORPUS)))
    return {
        "schemaVersion": "1.0", "operation": "check", "scope": "all-workspaces", "status": "passed",
        "multiWorkspace": {"id": "platform", "path": "."},
        "workspaces": [
            {"id": "platform", "path": ".", "status": "passed", "checkedDocumentCount": 1,
             "checkedStatementCount": 1, "durationMs": 0, "diagnostics": []},
            {"id": "web", "path": "apps/web", "status": "passed", "checkedDocumentCount": 1,
             "checkedStatementCount": 0, "durationMs": 0, "diagnostics": []},
        ],
        "revision": {"base": COMMIT, "commit": COMMIT, "dirty": False},
        "durationMs": 0,
        "diagnostics": [],
    }


def reviewed_effects(identifier, state):
    effects = {"schemaVersion": "1.0", "policy": "read-only", "before": state, "after": state}
    if CASES[identifier][1]:
        effects["policy"] = "explicit-report"
        effects["report"] = {"directory": REPORT_DIRECTORY, "createdCount": 1,
                             "namePattern": NAME_PATTERN, "temporaryFilesRemaining": 0}
    return effects


def check_report_contract(identifier, manifest, effects, result):
    operation, report, _ = CASES[identifier]
    if ("--report" in manifest["invocation"]["argv"]) != report:
        raise ValueError("manifestの--reportが審査済みcaseと異なります")
    if manifest["expect"]["reportFileCount"] != (1 if report else 0):
        raise ValueError("report件数がmanifestと異なります")
    if not report:
        if effects["policy"] != "read-only" or "report" in effects:
            raise ValueError("既定の全体操作はfileを作ってはいけません")
        return
    if effects["policy"] != "explicit-report" or effects["report"]["createdCount"] != 1:
        raise ValueError("明示reportはちょうど1件を作る必要があります")
    if effects["report"]["directory"] != REPORT_DIRECTORY:
        raise ValueError("全体reportはroot workspaceの規定先へ保存する必要があります")
    if effects["report"]["temporaryFilesRemaining"] != 0:
        raise ValueError("原子的な作成は一時fileを残してはいけません")
    pattern = effects["report"]["namePattern"]
    if not re.fullmatch(pattern, f"20000101T000000Z-{operation}.json"):
        raise ValueError("review済みの名前のpatternが妥当なreport名を拒否しています")
    for bad in (f"{operation}.json", f"20000101T000000Z-{operation}-0.json",
                "20000101T000000Z-doctor.json", f"20000101T000000Z-{operation}.json.tmp"):
        if re.fullmatch(pattern, bad):
            raise ValueError("review済みの名前のpatternが不正なreport名を受理しています")
    if EXISTING_REPORT not in effects["before"]["repository"]:
        raise ValueError("既存のreportがないと排他的な作成を検査できません")
    # 既定の対と結果本体が一致することを確かめる。reportの有無は結果を変えない。
    default = "MULTI-022-01" if operation == "check" else "MULTI-022-03"
    if result != reviewed_result(default):
        raise ValueError("reportの有無で結果本体が変わっています")


def validate(root=HERE, identifiers=None):
    errors, prepared = [], []
    validators = {name: Draft202012Validator(json.loads((root / f"{name}.schema.json").read_text()))
                  for name in ("manifest", "result", "side-effects")}
    inputs = reviewed_inputs()
    for identifier in CASES:
        if identifiers is not None and identifier not in identifiers:
            continue
        fixture = root / "multi" / identifier
        try:
            manifest = json.loads((fixture / "manifest.json").read_text())
            operation = CASES[identifier][0]
            result = json.loads((fixture / f"expected/{operation}.json").read_text())
            effects = json.loads((fixture / "side-effects.json").read_text())
            for name, value in (("manifest", manifest), ("result", result), ("side-effects", effects)):
                validators[name].validate(value)
            if manifest != reviewed_manifest(identifier):
                raise ValueError("起動条件が審査済み期待値と異なります")
            if result != reviewed_result(identifier):
                raise ValueError("完全結果が審査済み期待値と異なります")
            files = {p.relative_to(fixture / "repo").as_posix(): p
                     for p in (fixture / "repo").rglob("*") if p.is_file() or p.is_symlink()}
            if set(files) != set(inputs) or any(p.is_symlink() or p.read_bytes() != inputs[key]
                                                for key, p in files.items()):
                raise ValueError("入力が審査済みcorpusと異なります")
            if effects["before"] != effects["after"]:
                raise ValueError("実行前後で既存のpathは不変でなければなりません")
            check_report_contract(identifier, manifest, effects, result)
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-multi-report-") as temporary:
                for run in range(2):
                    sandbox = Path(temporary) / str(run)
                    sandbox.mkdir()
                    repository = setup(fixture, manifest, sandbox / "repo")
                    external = {name: sandbox / name for name in ("home", "cache", "temporary")}
                    for path in external.values():
                        path.mkdir()
                    actual = observe(repository, external)
                    if compare_state(effects["before"], actual) or (previous is not None and previous != actual):
                        raise ValueError("隔離setupが固定snapshotと異なります")
                    previous = actual
                    if not (repository / REPORT_DIRECTORY).is_dir():
                        raise ValueError("report directoryは実在するdirectoryである必要があります")
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, IndexError, ValidationError,
                subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "status": "Passed" if not errors else "Failed", "errors": errors}
