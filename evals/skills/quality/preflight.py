#!/usr/bin/env python3
"""Check fixed synthetic inputs through public CLI; never invoke a model."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
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


def check_case(case: dict, parent: Path, env: dict) -> dict:
    workspace = parent / case["caseId"]
    shutil.copytree(HERE / case["fixture"], workspace)
    target = (workspace / "target.py").read_bytes()
    git(["init", "-b", "quality-synthetic"], workspace, env)
    if case["caseId"] == "QR-001":
        shutil.copyfile(HERE / "review-base.py", workspace / "target.py")
    paths = [".spec/bitz.yaml", f".spec/requirements/{case['originId'].split(':')[0]}.md", "target.py", "test_fixture.py"]
    git(["add", "--", *paths], workspace, env)
    git(["commit", "-m", "synthetic base"], workspace, env)
    base = git(["rev-parse", "HEAD"], workspace, env).decode().strip()
    if case["caseId"] == "QR-001":
        (workspace / "target.py").write_bytes(target)
        git(["add", "--", "target.py"], workspace, env)
        git(["commit", "-m", "synthetic change"], workspace, env)
    ref = git(["rev-parse", "HEAD"], workspace, env).decode().strip()
    patch = git(["diff", base, ref, "--", "target.py"], workspace, env).decode()
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
    tests = run([sys.executable, "-B", "test_fixture.py"], workspace, env)
    if tests.returncode:
        raise ValueError(f"{case['caseId']}: fixed local test failed")
    counterexample = None
    if case["caseId"] == "QR-001":
        # Evaluation preparation only: this proof and protocol stay outside model inputs.
        probe = run([sys.executable, "-B", "-c", "import json; from target import read_document; print(json.dumps(read_document('synthetic-other', {'owner': 'synthetic-owner', 'body': 'synthetic document'})))"], workspace, env)
        counterexample = json.loads(probe.stdout)
        if probe.returncode or counterexample != {"status": 200, "body": "synthetic document"}:
            raise ValueError("review fixture does not retain intended authorization defect")
    unchanged = before == files(workspace) and not git(["status", "--porcelain"], workspace, env)
    if not unchanged:
        raise ValueError(f"{case['caseId']}: fixture changed during checks")
    return {"caseId": case["caseId"], "baseCommit": base, "subjectCommit": ref, "files": before,
            "diff": patch, "coreResults": observations, "coreStdout": core_stdout, "testExitCode": tests.returncode,
            "testStdout": tests.stdout.decode(), "testStderr": tests.stderr.decode(),
            "counterexample": counterexample, "unchanged": True}


def main() -> int:
    env = environment()
    ref = git(["rev-parse", "HEAD"], ROOT, env).decode().strip()
    if git(["status", "--porcelain"], ROOT, env):
        print(json.dumps({"status": "blocked", "reason": "source tree must be clean", "certifiesQuality": False}))
        return 1
    protocol_bytes = (HERE / "protocol.json").read_bytes()
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
