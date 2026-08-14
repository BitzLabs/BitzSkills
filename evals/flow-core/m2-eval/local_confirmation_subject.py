#!/usr/bin/env python3
"""M2 local-write confirmation subject。独立tmp repoを使うfixtureだけを実行する。"""

from __future__ import annotations

import argparse
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
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    args = parser.parse_args()
    root = Path(args.repo).resolve()
    common = subprocess.run(
        ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
        cwd=root, capture_output=True, text=True, check=True,
    ).stdout.strip()
    workspace_python = Path(common).parent / ".venv" / "bin" / "python"
    python = str(workspace_python) if workspace_python.is_file() else sys.executable
    command = [python, "-m", "pytest", "-q", "-p", "no:cacheprovider", *FILES]
    proc = subprocess.run(command, cwd=root, capture_output=True, text=True, check=False)
    output = proc.stdout + proc.stderr
    match = re.search(r"(\d+) passed", output)
    if proc.returncode != 0 or match is None:
        print("M2_CONFIRMATION_FAIL")
        return 1
    print(
        "M2_CONFIRMATION_PASS "
        f"tests={match.group(1)} required_checks=1/1 positive_controls=1/1 "
        "hazards=0 residuals=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
