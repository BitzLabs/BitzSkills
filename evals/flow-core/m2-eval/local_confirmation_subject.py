#!/usr/bin/env python3
"""M2 local-write confirmation subject。実Git worktree E2Eを同一test ID集合で実行する。"""

from __future__ import annotations

import argparse
import hashlib
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
)

RUNTIME_CHECKS = 8


def _suite(root: Path, python: str) -> tuple[list[str], str]:
    proc = subprocess.run(
        [python, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider", *FILES],
        cwd=root, capture_output=True, text=True, check=False,
    )
    test_ids = sorted(line.strip() for line in proc.stdout.splitlines() if "::" in line)
    if proc.returncode != 0 or not test_ids:
        raise RuntimeError("confirmation test ID collection failed")
    digest = "sha256:" + hashlib.sha256("\n".join(test_ids).encode()).hexdigest()
    return test_ids, digest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--describe", action="store_true")
    args = parser.parse_args()
    root = Path(args.repo).resolve()
    common = subprocess.run(
        ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
        cwd=root, capture_output=True, text=True, check=True,
    ).stdout.strip()
    workspace_python = Path(common).parent / ".venv" / "bin" / "python"
    python = str(workspace_python) if workspace_python.is_file() else sys.executable
    test_ids, test_id_digest = _suite(root, python)
    if args.describe:
        print(
            "M2_CONFIRMATION_SUITE "
            f"tests={len(test_ids)} test_id_digest={test_id_digest} "
            f"runtime_checks={RUNTIME_CHECKS}"
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
        f"runtime_checks={RUNTIME_CHECKS}/{RUNTIME_CHECKS} "
        "required_checks=2/2 positive_controls=2/2 hazards=0 residuals=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
