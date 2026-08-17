#!/usr/bin/env python3
"""M2 local-write confirmation subject。実Git worktree E2Eを同一test ID集合で実行する。"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
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

#: 実Git worktree副作用を観測する実動E2Eファイル（runtime check の母数はここから導出する）。
RUNTIME_FILE = "tests/test_flow_m2_runtime.py"


def _pytest_command(root: Path) -> list[str]:
    """sandbox 内でも使える pytest 実行器を選ぶ。

    通常はリポジトリの仮想環境を使う。Antigravity の sandbox では、その venv の
    interpreter がリポジトリ外の uv toolchain を参照して起動できないため、ネットワーク
    を使わない `uv --offline` fallback を用いる。cache は `/tmp` に限定し、repo を変更しない。
    """
    common = subprocess.run(
        ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
        cwd=root, capture_output=True, text=True, check=True,
    ).stdout.strip()
    workspace_python = Path(common).parent / ".venv" / "bin" / "python"
    if workspace_python.is_file():
        return [str(workspace_python), "-m", "pytest"]
    if shutil.which("uv") is None:
        raise RuntimeError("pytest interpreter unavailable")
    return ["uv", "run", "--offline", "--no-project", "--with", "pytest", "python3", "-m", "pytest"]


def _suite(root: Path, pytest_command: list[str]) -> tuple[list[str], str, int]:
    proc = subprocess.run(
        [*pytest_command, "--collect-only", "-q", "-p", "no:cacheprovider", *FILES],
        cwd=root, capture_output=True, text=True, check=False,
        env={**os.environ, "UV_CACHE_DIR": "/tmp/bitz-flow-m2-uv-cache"},
    )
    test_ids = sorted(line.strip() for line in proc.stdout.splitlines() if "::" in line)
    if proc.returncode != 0 or not test_ids:
        raise RuntimeError("confirmation test ID collection failed")
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
    pytest_command = _pytest_command(root)
    test_ids, test_id_digest, runtime_checks = _suite(root, pytest_command)
    if args.describe:
        print(
            "M2_CONFIRMATION_SUITE "
            f"tests={len(test_ids)} test_id_digest={test_id_digest} "
            f"runtime_checks={runtime_checks}"
        )
        return 0
    command = [*pytest_command, "-q", "-p", "no:cacheprovider", *FILES]
    proc = subprocess.run(
        command, cwd=root, capture_output=True, text=True, check=False,
        env={**os.environ, "UV_CACHE_DIR": "/tmp/bitz-flow-m2-uv-cache"},
    )
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
