#!/usr/bin/env python3
"""Check fixed synthetic inputs through public CLI; never invoke a model."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def environment() -> dict[str, str]:
    return {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "PYTHONPATH": os.environ.get("PYTHONPATH", ""),
            "PYTHONDONTWRITEBYTECODE": "1", "LC_ALL": "C.UTF-8", "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_AUTHOR_NAME": "Quality synthetic fixture",
            "GIT_AUTHOR_EMAIL": "quality@invalid", "GIT_COMMITTER_NAME": "Quality synthetic fixture",
            "GIT_COMMITTER_EMAIL": "quality@invalid", "GIT_AUTHOR_DATE": "2026-10-04T00:00:00+00:00",
            "GIT_COMMITTER_DATE": "2026-10-04T00:00:00+00:00"}


def run(argv: list[str], cwd: Path, env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(argv, cwd=cwd, env=env, capture_output=True, timeout=30)


def git(args: list[str], cwd: Path, env: dict) -> bytes:
    result = run(["git", "-c", "core.hooksPath=/dev/null", *args], cwd, env)
    if result.returncode:
        raise ValueError(f"synthetic git operation failed: {args[0]}")
    return result.stdout


def files(directory: Path) -> dict[str, str]:
    return {p.relative_to(directory).as_posix(): digest(p.read_bytes())
            for p in sorted(directory.rglob("*")) if p.is_file() and ".git" not in p.relative_to(directory).parts}


def relative_path(value: str) -> str:
    if (not isinstance(value, str) or not value or PurePosixPath(value).is_absolute()
            or any(part in {".", "..", ".git", "resources"} for part in value.split("/"))
            or PurePosixPath(value).as_posix() != value):
        raise ValueError("fixture path must be a normalized relative path")
    return value


def fixture_input(value: str, *, directory=False) -> Path:
    path = HERE / relative_path(value)
    if (not path.resolve().is_relative_to(HERE / "fixtures")
            or any(p.is_symlink() for p in [path, *path.parents] if p.is_relative_to(HERE))
            or (not path.is_dir() if directory else not path.is_file())):
        raise ValueError("fixed fixture input must stay under fixtures without symlinks")
    return path


def test_policy(case: dict) -> str:
    policy = case.get("testExecution", "allowed")
    if not isinstance(policy, str) or policy not in {"allowed", "not_authorized"}:
        raise ValueError("invalid fixed test execution policy")
    return policy


def additional_reads(case: dict) -> list[str]:
    paths = case.get("additionalReadFiles", [])
    if not isinstance(paths, list) or any(not isinstance(p, str) for p in paths) or len(set(paths)) != len(paths):
        raise ValueError("additional reads must be a list of unique fixed paths")
    return [relative_path(path) for path in paths]


def check_case(case: dict, parent: Path, env: dict) -> dict:
    if not isinstance(case.get("caseId"), str) or not re.fullmatch(r"Q[PR]-[0-9]{3}", case["caseId"]):
        raise ValueError("invalid fixed case ID")
    policy = test_policy(case)
    fixture = fixture_input(case["fixture"], directory=True)
    for path in fixture.rglob("*"):
        relative_path(path.relative_to(fixture).as_posix())
        if path.is_symlink():
            raise ValueError("fixture symlinks are not allowed")
    base_files = case.get("baseFiles", {})
    if not isinstance(base_files, dict):
        raise ValueError("baseFiles must map fixed workspace files to fixed inputs")
    replacements = {relative_path(name): fixture_input(source) for name, source in base_files.items()}
    for name in replacements:
        if not (fixture / name).is_file():
            raise ValueError("base replacement target must exist in the fixed fixture")
    for name in additional_reads(case):
        if not (fixture / name).is_file():
            raise ValueError("additional read must exist in the fixed fixture")
    workspace = parent / case["caseId"]
    shutil.copytree(fixture, workspace)
    if case["caseId"] == "QR-001":
        if replacements:
            raise ValueError("original QR-001 base must remain unchanged")
        replacements = {"target.py": HERE / "review-base.py"}
    targets = {name: (workspace / name).read_bytes() for name in replacements}
    git(["init", "-b", "quality-synthetic"], workspace, env)
    for name, source in replacements.items():
        shutil.copyfile(source, workspace / name)
    paths = sorted(files(workspace))
    git(["add", "--", *paths], workspace, env)
    git(["commit", "-m", "synthetic base"], workspace, env)
    base = git(["rev-parse", "HEAD"], workspace, env).decode().strip()
    if replacements:
        for name, content in targets.items():
            (workspace / name).write_bytes(content)
        git(["add", "--", *sorted(targets)], workspace, env)
        git(["commit", "-m", "synthetic change"], workspace, env)
    ref = git(["rev-parse", "HEAD"], workspace, env).decode().strip()
    patch = git(["diff", base, ref, "--", *paths], workspace, env).decode()
    before = files(workspace)
    observations = []
    core_stdout = {}
    for operation, args in [("context", ["context", case["originId"], "--purpose", "interpret", "--format", "json"]),
                            ("check", ["check", case["originId"], "--format", "json"])]:
        argv = [sys.executable, "-B", "-m", "bitz.cli", *args]
        result = run(argv, workspace, env)
        raw = json.loads(result.stdout)
        core_stdout[operation] = result.stdout.decode()
        if result.returncode or raw["status"] not in {"passed", "passed_with_warnings"}:
            raise ValueError(f"{case['caseId']}: public Core {operation} non-success")
        observations.append({"operation": operation, "status": raw["status"], "exitCode": result.returncode,
                             "source": f"preflight report: {case['caseId']}/coreStdout/{operation}", "sha256": digest(result.stdout),
                             "subjectCommit": ref, "role": "current_gate", "roleReason": "先行固定入力の事前検査",
                             "argv": argv, "cwd": str(workspace), "rawResult": raw, "stderr": result.stderr.decode()})
    tests = None
    if policy == "allowed":
        tests = run([sys.executable, "-B", "test_fixture.py"], workspace, env)
        if tests.returncode:
            raise ValueError(f"{case['caseId']}: fixed local test failed")
    counterexample = None
    if case["caseId"] in {"QR-001", "QR-006"}:
        # Evaluation preparation only: this proof and protocol stay outside model inputs.
        probe = run([sys.executable, "-B", "-c", "import json; from target import read_document; print(json.dumps(read_document('synthetic-other', {'owner': 'synthetic-owner', 'body': 'synthetic document'})))"], workspace, env)
        counterexample = json.loads(probe.stdout)
        if probe.returncode or counterexample != {"status": 200, "body": "synthetic document"}:
            raise ValueError("review fixture does not retain intended authorization defect")
    unchanged = before == files(workspace) and not git(["status", "--porcelain"], workspace, env)
    if not unchanged:
        raise ValueError(f"{case['caseId']}: fixture changed during checks")
    return {"caseId": case["caseId"], "baseCommit": base, "subjectCommit": ref, "files": before,
            "diff": patch, "coreResults": observations, "coreStdout": core_stdout,
            "testExitCode": tests.returncode if tests else None,
            "testStdout": tests.stdout.decode() if tests else None, "testStderr": tests.stderr.decode() if tests else None,
            "testExecution": policy, "testNotRunReason": "固定ケースで実行が許可されていない" if not tests else None,
            "counterexample": counterexample, "unchanged": True}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", choices=["protocol.json", "remediation-protocol.json", "shared-format-protocol.json", "expansion-cases.json", "normal-cases.json", "attack-cases.json"], default="protocol.json")
    args = parser.parse_args()
    env = environment()
    ref = git(["rev-parse", "HEAD"], ROOT, env).decode().strip()
    if git(["status", "--porcelain"], ROOT, env):
        print(json.dumps({"status": "blocked", "reason": "source tree must be clean", "certifiesQuality": False}))
        return 1
    protocol_bytes = (HERE / args.protocol).read_bytes()
    protocol = json.loads(protocol_bytes)
    scratch = ROOT / ".venv"
    scratch.mkdir(exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(prefix="quality-preflight-", dir=scratch) as directory:
            results = [check_case(case, Path(directory), env) for case in protocol["cases"]]
        report = {"status": "passed", "scope": "synthetic-input-preflight", "certifiesQuality": False,
                  "newModelTrajectories": 0, "sourceCommit": ref, "evaluationSetVersion": protocol["evaluationSetVersion"],
                  "protocolSha256": digest(protocol_bytes), "cases": results}
        report["pluginFiles"] = files(ROOT / "plugins/bitz-quality")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(json.dumps({"status": "failed", "reason": str(error), "sourceCommit": ref,
                          "certifiesQuality": False, "newModelTrajectories": 0}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
