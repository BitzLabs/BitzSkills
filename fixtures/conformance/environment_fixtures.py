"""実行環境・配布物のfixture（Core操作とharness実行部は動かさない）。

SINGLE-127-15／16はGit shimの版を下限未満と下限にしたdoctor、127-19はCPython下限でのdoctor、
127-17／18は`runner: package`によるpackage metadataとlock fileの検査である。
下限値はテストへ直書きせず、[Core実行環境・CLI基盤契約 §2・§4]の本文から読み取る。
shim生成、`uv`環境構築、package検査の実行はADR-046に従うharness実装の責務で、Gate Bで確認する。
"""
import json
from pathlib import Path
import re
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from .schemas import schema_path
from .harness import git, setup
from .initial_fixtures import CONFIGS, observe, compare_state
from .registry_closure_fixtures import CORE, LOST_GUARANTEES, doctor_checks

HERE = Path(__file__).resolve().parent
CONTRACT = HERE.parents[1] / "docs/03.詳細設計/00_共通契約/06_Core実行環境・CLI基盤契約.md"
FIXTURE_SPEC = HERE.parents[1] / "docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md"
CASES = {
    "SINGLE-127-15": "下限未満のGitをGit不在へ縮退する",
    "SINGLE-127-16": "下限と同じGitを利用可能として扱う",
    "SINGLE-127-17": "package metadataの名前とrequires-pythonを検査する",
    "SINGLE-127-18": "runtime依存とlock fileを検査する",
    "SINGLE-127-19": "下限CPythonでdoctorを起動する",
}
PACKAGE_CASES = {"SINGLE-127-17": "metadata", "SINGLE-127-18": "dependencies"}


def minimums():
    """規範本文の下限値を返す。表記が変われば検証をerrorにする。"""
    text = CONTRACT.read_text()
    python = re.findall(r"Core 1\.0はCPython (\d+)\.(\d+)以上を対象とする", text)
    git_floor = re.findall(r"Gitは(\d+)\.(\d+)以上を対象とし", text)
    if len(python) != 1 or len(git_floor) != 1:
        raise ValueError("実行環境契約から下限versionを一意に読み取れません")
    if "`git --version`" not in text:
        raise ValueError("実行環境契約にGit版の取得方法がありません")
    return tuple(map(int, python[0])), tuple(map(int, git_floor[0]))


def reviewed_manifest(identifier):
    (py_major, py_minor), (git_major, git_minor) = minimums()
    manifest = {"fixtureId": identifier, "description": CASES[identifier]}
    if identifier in PACKAGE_CASES:
        manifest.update(
            setup={"git": True, "operations": []},
            invocation={"runner": "package", "cwd": ".", "argv": [PACKAGE_CASES[identifier]], "env": {}},
            expect={"outcome": "accepted", "exitCode": 0, "stdout": "json",
                    "resultFile": "expected/package.json", "reportFileCount": 0})
        return manifest
    invocation = {"runner": "bitz", "cwd": ".", "argv": ["doctor", "--format", "json"], "env": {}}
    if identifier == "SINGLE-127-15":
        invocation["gitVersion"] = f"{git_major}.{git_minor - 1}.0"
    elif identifier == "SINGLE-127-16":
        invocation["gitVersion"] = f"{git_major}.{git_minor}.0"
    else:
        invocation["python"] = f"{py_major}.{py_minor}"
    degraded = identifier == "SINGLE-127-15"
    manifest.update(
        setup={"git": True, "operations": []}, invocation=invocation,
        expect={"status": "passed_with_warnings" if degraded else "passed", "exitCode": 0, "stdout": "json",
                "resultFile": "expected/doctor.json", "reportFileCount": 0})
    return manifest


def reviewed_result(identifier):
    if identifier in PACKAGE_CASES:
        return {"outcome": "accepted"}
    result = {"schemaVersion": "1.0", "operation": "doctor", "status": "passed",
              "workspace": {"id": "root", "path": "."}, "durationMs": 0, "diagnostics": [],
              "core": dict(CORE), "checks": doctor_checks()}
    if identifier == "SINGLE-127-15":
        # Git自体は起動できるが下限未満のため、SINGLE-093のGit不在と同じ縮退結果になる。
        result.update(status="passed_with_warnings", checks=doctor_checks(
            {"git": {"status": "warning", "lostGuarantees": LOST_GUARANTEES}}))
        result["diagnostics"] = [{
            "code": "SPEC-DOCTOR-GIT-001", "severity": "warning", "resultStatus": "passed_with_warnings",
            "summary": "Git不在のため差分に依存する保証を提供できません",
            "source": {"kind": "environment", "component": "git", "identifier": "git"}}]
    return result


def reviewed_inputs():
    return {".spec/bitz.yaml": CONFIGS["SINGLE-001"].encode()}


def check_contract(identifier, manifest):
    (_, _), (git_major, git_minor) = minimums()
    invocation = manifest["invocation"]
    if identifier in {"SINGLE-127-15", "SINGLE-127-16"}:
        major, minor, _ = map(int, invocation["gitVersion"].split("."))
        below = (major, minor) < (git_major, git_minor)
        if below != (identifier == "SINGLE-127-15") or (major, minor) < (git_major, git_minor - 1):
            raise ValueError("Git shimの版は下限の直前と下限でなければなりません")
        if "PATH" in invocation["env"] or "python" in invocation:
            raise ValueError("Git版fixtureはPATHやPythonを同時に変えてはいけません")
    if identifier == "SINGLE-127-19" and ("gitVersion" in invocation or invocation["env"]):
        raise ValueError("CPython下限fixtureはGitや環境を同時に変えてはいけません")
    if identifier in PACKAGE_CASES:
        spec = FIXTURE_SPEC.read_text()
        if f"| `package` | `{PACKAGE_CASES[identifier]}` |" not in spec:
            raise ValueError("package caseが適合fixture仕様のrunner表にありません")
        if not re.search(rf"^\| `{identifier}` \| [^|]+ \| package test \| accepted／0 \|", spec, re.M):
            raise ValueError("matrix行がpackage testではありません")


def validate(root=HERE, identifiers=None):
    errors, prepared = [], []
    validators = {name: Draft202012Validator(json.loads(schema_path(root, name).read_text()))
                  for name in ("manifest", "result", "side-effects")}
    for identifier in CASES:
        if identifiers is not None and identifier not in identifiers:
            continue
        fixture = root / "single" / identifier
        try:
            manifest = json.loads((fixture / "manifest.json").read_text())
            result = json.loads((fixture / manifest["expect"]["resultFile"]).read_text())
            effects = json.loads((fixture / "side-effects.json").read_text())
            validators["manifest"].validate(manifest)
            validators["side-effects"].validate(effects)
            if identifier not in PACKAGE_CASES:
                validators["result"].validate(result)
            if manifest != reviewed_manifest(identifier) or result != reviewed_result(identifier):
                raise ValueError("起動条件または完全結果が審査済み期待値と異なります")
            check_contract(identifier, manifest)
            files = {p.relative_to(fixture / "repo").as_posix(): p
                     for p in (fixture / "repo").rglob("*") if p.is_file() or p.is_symlink()}
            if set(files) != set(reviewed_inputs()) or any(
                    p.is_symlink() or p.read_bytes() != reviewed_inputs()[name] for name, p in files.items()):
                raise ValueError("入力が審査済みcorpusと異なります")
            if effects["before"] != effects["after"]:
                raise ValueError("read-only期待値が書込みを許しています")
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-environment-") as temporary:
                for run in range(2):
                    sandbox = Path(temporary) / str(run)
                    sandbox.mkdir()
                    repository = setup(fixture, manifest, sandbox / "repo")
                    if git(repository, "ls-files", "-z") or git(repository, "for-each-ref"):
                        raise ValueError("fixtureはunbornで空のindexである必要があります")
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
