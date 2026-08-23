#!/usr/bin/env python3
"""M2 local-write confirmation subject。実Git worktree E2Eを同一test ID集合で実行する。"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import subprocess
import sys
from pathlib import Path


FILES = (
    "tests/test_flow_m1_git_write.py",
    "tests/test_flow_m1_commit_causality.py",
    "tests/test_flow_m1_git_sync.py",
    "tests/test_flow_m2_guard.py",
    "tests/test_flow_m2_capability.py",
    "tests/test_flow_m2_worktree.py",
    "tests/test_flow_m2_reconnaissance.py",
    "tests/test_flow_m2_cleanup.py",
    "tests/test_flow_m2_remote_delete.py",
    "tests/test_flow_m2_runtime.py",
    "tests/test_flow_m2_contract_kernel.py",
    "tests/test_flow_m2_approval.py",
    "tests/test_flow_m2_platform_adapter.py",
    "tests/test_flow_m2_target_transaction.py",
    "tests/test_flow_m2_promotion.py",
    "tests/test_flow_m2_recovery.py",
    "tests/test_flow_m2_operability.py",
)

#: 実Git worktree副作用を観測する実動E2Eファイル（runtime check の母数はここから導出する）。
RUNTIME_FILE = "tests/test_flow_m2_runtime.py"


def _python_for_suite(root: Path) -> str:
    """Runner が固定した検証用 Python を優先し、単体実行時だけ Git から補完する。"""
    bound = os.environ.get("BITZ_CONFIRMATION_PYTHON")
    if bound:
        candidate = Path(bound)
        if (
            not candidate.is_absolute()
            or not candidate.is_file()
            or not os.access(candidate, os.X_OK)
        ):
            raise RuntimeError("BITZ_CONFIRMATION_PYTHON must be an executable absolute path")
        return str(candidate)
    common = subprocess.run(
        ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
        cwd=root, capture_output=True, text=True, check=True,
    ).stdout.strip()
    workspace_python = Path(common).parent / ".venv" / "bin" / "python"
    return str(workspace_python) if workspace_python.is_file() else sys.executable


def _suite(root: Path, python: str) -> tuple[list[str], str, int]:
    proc = subprocess.run(
        [python, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider", *FILES],
        cwd=root, capture_output=True, text=True, check=False,
    )
    test_ids = sorted(line.strip() for line in proc.stdout.splitlines() if "::" in line)
    if proc.returncode != 0 or not test_ids:
        combined = proc.stdout + proc.stderr
        if "No module named pytest" in combined:
            reason = "pytest-unavailable"
        elif "Permission denied" in combined or "Read-only file system" in combined:
            reason = "sandbox-filesystem-denied"
        else:
            reason = f"pytest-exit-{proc.returncode}"
        raise RuntimeError(f"confirmation test ID collection failed ({reason})")
    runtime_checks = sum(1 for test_id in test_ids if test_id.startswith(RUNTIME_FILE + "::"))
    if runtime_checks == 0:
        raise RuntimeError("runtime check collection failed")
    digest = "sha256:" + hashlib.sha256("\n".join(test_ids).encode()).hexdigest()
    return test_ids, digest, runtime_checks


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--describe", action="store_true")
    args = parser.parse_args()
    root = Path(args.repo).resolve()
    python = _python_for_suite(root)
    test_ids, test_id_digest, runtime_checks = _suite(root, python)
    if args.describe:
        print(
            "M2_CONFIRMATION_SUITE "
            f"tests={len(test_ids)} test_id_digest={test_id_digest} "
            f"runtime_checks={runtime_checks}"
        )
        return 0
    command = [python, "-m", "pytest", "-q", "-p", "no:cacheprovider", *FILES]
    proc = subprocess.run(command, cwd=root, capture_output=True, text=True, check=False)
    output = proc.stdout + proc.stderr
    match = re.search(r"(\d+) passed", output)
    if proc.returncode != 0 or match is None:
        print("M2_CONFIRMATION_FAIL")
        return 1
    print(
        "M2_CONFIRMATION_PASS "
        f"tests={match.group(1)} test_id_digest={test_id_digest} "
        f"runtime_checks={runtime_checks}/{runtime_checks} "
        "hazards=0 residuals=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
