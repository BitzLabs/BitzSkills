"""明示reportを固定するreview済みvector（Core操作は実行しない）。

`SINGLE-071-01..04`は、`check`と`verify`で、成功・失敗のどちらでも`--report`が
`.spec/reports/`にちょうど1件のfileを作ることを固定する。`SINGLE-072`は、使えないreportの保存先が
errorになり、それでも元の結果を端末へ返すことを固定する。
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
# report directoryの位置に置く通常file。directoryの権限と異なりversion管理できる。
# Gitはdirectoryの権限を記録せず、fresh checkoutでは復元されない。
BLOCKING_FILE = b"this path occupies the report directory\n"
# id: (操作, status, 終了コード, review済みの結果の元fixture)
CASES = {
    "SINGLE-071-01": ("check", "passed", 0, "SINGLE-070-01"),
    "SINGLE-071-02": ("check", "failed", 1, "SINGLE-070-02"),
    "SINGLE-071-03": ("verify", "passed", 0, "SINGLE-070-03"),
    "SINGLE-071-04": ("verify", "failed", 1, "SINGLE-070-04"),
    # 「元の結果が残る」が空疎にならないよう、失敗するcheckに基づく。
    "SINGLE-072": ("check", "error", 3, "SINGLE-070-02"),
    "SINGLE-127-12": ("check", "passed", 0, "SINGLE-070-01"),
}
DESCRIPTIONS = {
    "SINGLE-071-01": "明示--report付きの成功checkが規定先へ1件を排他的作成する",
    "SINGLE-071-02": "明示--report付きの失敗checkが規定先へ1件を排他的作成する",
    "SINGLE-071-03": "明示--report付きの成功verifyが規定先へ1件を排他的作成する",
    "SINGLE-071-04": "明示--report付きの失敗verifyが規定先へ1件を排他的作成する",
    "SINGLE-072": "report保存先が書込み不能でも元結果を端末へ保持する",
    "SINGLE-127-12": "--format jsonと--reportを併用し標準出力JSONと規定reportを生成する",
}


def reviewed_inputs(identifier):
    inputs = dict(report_absent_fixtures.reviewed_inputs(CASES[identifier][3]))
    if identifier == "SINGLE-072":
        # 通常fileがpathを占めるので、report directoryは存在できない。
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
        # reportを保存しても、計算済みの結果は変わらない。
        return result
    # 元の結果とそのDiagnosticは端末に残り、statusと
    # 保存の失敗だけが加わる。
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
        raise ValueError("この群は--reportを渡す必要があります")
    expected = manifest["expect"]["reportFileCount"]
    if identifier == "SINGLE-072":
        if effects["policy"] != "read-only" or "report" in effects or expected != 0:
            raise ValueError("保存に失敗した場合はtreeを変えてはいけません")
        source = report_absent_fixtures.reviewed_result(CASES[identifier][3])
        keys = ("status", "diagnostics")
        if {k: v for k, v in result.items() if k not in keys} != {
                k: v for k, v in source.items() if k not in keys}:
            raise ValueError("元の結果は端末に残る必要があります")
        if ([d["code"] for d in result["diagnostics"]]
                != [d["code"] for d in source["diagnostics"]] + ["SPEC-REPORT-WRITE-001"]):
            raise ValueError("保存の失敗は元のDiagnosticに追加する必要があります")
        if not source["diagnostics"]:
            raise ValueError("このcaseは既にDiagnosticを持つ結果から始める必要があります")
        return
    if effects["policy"] != "explicit-report" or effects["report"]["createdCount"] != expected:
        raise ValueError("作成したreportの件数がmanifestと異なります")
    if effects["report"]["temporaryFilesRemaining"] != 0:
        raise ValueError("原子的な作成は一時fileを残してはいけません")
    operation = manifest["invocation"]["argv"][0]
    sample = f"20000101T000000Z-{operation}.json"
    if not re.fullmatch(effects["report"]["namePattern"], sample):
        raise ValueError("review済みの名前のpatternが妥当なreport名を拒否しています")
    for bad in (f"{operation}.json", f"20000101T000000Z-{operation}-0.json",
                f"20000101T000000Z-context.json", f"20000101T000000Z-{operation}.json.tmp"):
        if re.fullmatch(effects["report"]["namePattern"], bad):
            raise ValueError("review済みの名前のpatternが不正なreport名を受理しています")
    if EXISTING_REPORT not in effects["before"]["repository"]:
        raise ValueError("既存のreportがないと排他的な作成を検査できません")


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
                raise ValueError("起動条件または完全結果が審査済み期待値と異なります")
            if effects != reviewed_effects(identifier, effects["before"]):
                raise ValueError("副作用の期待値が審査済みのpolicyと異なります")
            check_report_contract(identifier, manifest, effects, result)
            inputs = reviewed_inputs(identifier)
            files = {p.relative_to(fixture / "repo").as_posix(): p
                     for p in (fixture / "repo").rglob("*") if p.is_file() or p.is_symlink()}
            if set(files) != set(inputs) or any(p.is_symlink() or p.read_bytes() != inputs[name]
                                                for name, p in files.items()):
                raise ValueError("入力が審査済みcorpusと異なります")
            if effects["before"] != effects["after"]:
                raise ValueError("既に存在したpathはすべて不変である必要があります")
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-report-write-") as temporary:
                for run in range(2):
                    sandbox = Path(temporary) / str(run)
                    sandbox.mkdir()
                    repository = setup(fixture, manifest, sandbox / "repo")
                    reports = repository / REPORT_DIRECTORY
                    if identifier == "SINGLE-072":
                        if not reports.is_file():
                            raise ValueError("blockedのcaseにはreport pathにfileが必要です")
                    elif not reports.is_dir():
                        raise ValueError("report directoryは実行前に存在する必要があります")
                    external = {name: sandbox / name for name in ("home", "cache", "temporary")}
                    for path in external.values():
                        path.mkdir()
                    actual = observe(repository, external)
                    if compare_state(effects["before"], actual) or (previous is not None and previous != actual):
                        raise ValueError("隔離setupが固定snapshotと異なります")
                    previous = actual
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, ValidationError,
                subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "status": "Passed" if not errors else "Failed", "errors": errors}
