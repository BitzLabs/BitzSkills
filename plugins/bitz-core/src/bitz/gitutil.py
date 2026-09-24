"""Git検出とrevision解決。

`Core実行環境・CLI基盤契約 §4` に従い、Git CLIをargvで直接起動する。shellを使わない。
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass

MIN_GIT_MAJOR = 2
MIN_GIT_MINOR = 30


@dataclass
class GitInfo:
    available: bool
    executable: str | None = None
    version: tuple[int, int] | None = None


def _run(argv: list[str], cwd: str, env: dict[str, str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        argv,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


def detect_git(cwd: str, env: dict[str, str]) -> GitInfo:
    path_value = env.get("PATH", "")
    executable = shutil.which("git", path=path_value)
    if not executable:
        return GitInfo(available=False)
    try:
        proc = _run([executable, "--version"], cwd, env)
    except (OSError, subprocess.SubprocessError):
        return GitInfo(available=False)
    if proc.returncode != 0:
        return GitInfo(available=False)
    first_line = (proc.stdout or "").splitlines()[0] if proc.stdout else ""
    version = _parse_git_version(first_line)
    if version is None:
        return GitInfo(available=False)
    major, minor = version
    if (major, minor) < (MIN_GIT_MAJOR, MIN_GIT_MINOR):
        return GitInfo(available=False, executable=executable, version=version)
    return GitInfo(available=True, executable=executable, version=version)


def _parse_git_version(line: str) -> tuple[int, int] | None:
    prefix = "git version "
    if not line.startswith(prefix):
        return None
    rest = line[len(prefix) :].strip()
    parts = rest.split(".")
    if len(parts) < 2:
        return None
    major_s, minor_s = parts[0], parts[1]
    if not major_s.isdigit() or not minor_s.isdigit():
        return None
    return int(major_s), int(minor_s)


def show_toplevel(executable: str, cwd: str, env: dict[str, str]) -> str | None:
    try:
        proc = _run(
            [executable, "--no-optional-locks", "rev-parse", "--show-toplevel"], cwd, env
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def resolve_commit(executable: str, cwd: str, env: dict[str, str], rev: str) -> str | None:
    try:
        proc = _run(
            [executable, "--no-optional-locks", "rev-parse", "--verify", f"{rev}^{{commit}}"],
            cwd,
            env,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    out = proc.stdout.strip()
    if len(out) != 40:
        return None
    return out


def is_dirty(executable: str, cwd: str, env: dict[str, str]) -> bool:
    try:
        proc = _run(
            [executable, "--no-optional-locks", "status", "--porcelain"], cwd, env
        )
    except (OSError, subprocess.SubprocessError):
        return False
    if proc.returncode != 0:
        return False
    return bool(proc.stdout.strip())


def is_config_tracked(executable: str, cwd: str, env: dict[str, str], path: str) -> bool:
    try:
        proc = _run(
            [executable, "--no-optional-locks", "ls-files", "--error-unmatch", path], cwd, env
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return proc.returncode == 0
