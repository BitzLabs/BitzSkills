"""`repo.doctor` — v2 の環境診断（FLW-FR-011）。

対象 project へ**書き込まない**。Git ref も GitHub の状態も変えない。

診断は「使えるか / 使えないか」を返すだけでなく、**operation ごとに何が足りないか**を返す。
「なんとなく動きそう」ではなく、どの operation がどの capability を欠いて `UNSUPPORTED` に
なるのかを呼出側が判断できるようにするためである。

診断結果に絶対 path・token・URL userinfo を載せない（sanitizer を通す）。
"""

from __future__ import annotations

import dataclasses
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Sequence

from . import git_read
from . import sanitize as S

SEVERITY_OK = "ok"
SEVERITY_WARNING = "warning"
SEVERITY_MISSING = "missing"

#: operation ごとに必要な capability。ここに無い operation は診断対象外。
OPERATION_CAPABILITIES: dict[str, tuple[str, ...]] = {
    "repo.inspect": ("git",),
    "git.status": ("git",),
    "git.diff-summary": ("git",),
    "git.diff-detail": ("git",),
    "git.log": ("git",),
    "git.branches": ("git",),
    "git.conflicts": ("git",),
    "worktree.list": ("git",),
    "git.fetch": ("git", "remote"),
    "git.stage": ("git", "atomic-rename", "native-index-lock", "owner-only-area", "fsync"),
    "git.commit": ("git", "atomic-rename", "owner-only-area", "fsync"),
    "git.sync": ("git", "remote", "atomic-rename", "owner-only-area", "fsync"),
    "git.publish-branch": ("git", "remote", "remote-cas"),
    "git.delete-remote-branch": ("git", "remote", "remote-cas"),
    "repo.doctor": ("git",),
}

MIN_GIT_VERSION = (2, 30)


@dataclasses.dataclass(frozen=True)
class Finding:
    name: str
    severity: str
    detail: str
    stage: str | None = None
    cause: str | None = None
    next_action: str | None = None


@dataclasses.dataclass(frozen=True)
class Diagnosis:
    findings: tuple[Finding, ...]
    capabilities: dict[str, bool]
    operations: dict[str, dict[str, object]]

    @property
    def blocking(self) -> tuple[Finding, ...]:
        return tuple(f for f in self.findings if f.severity == SEVERITY_MISSING)

    @property
    def warnings(self) -> tuple[Finding, ...]:
        return tuple(f for f in self.findings if f.severity == SEVERITY_WARNING)


def _run(root: Path, args: Sequence[str]) -> subprocess.CompletedProcess:
    environ = dict(os.environ)
    environ.update(git_read.GIT_ENV)
    return subprocess.run(
        ["git", *git_read.GIT_COMMON_FLAGS, *args],
        cwd=str(root), capture_output=True, env=environ,
    )


def _git_version() -> tuple[int, ...] | None:
    if shutil.which("git") is None:
        return None
    proc = subprocess.run(["git", "--version"], capture_output=True, text=True)
    parts = proc.stdout.strip().split()
    for token in parts:
        if token[0].isdigit():
            return tuple(int(p) for p in token.split(".")[:3] if p.isdigit())
    return None


def _filesystem_capabilities(common_dir: Path) -> dict[str, bool]:
    """owner-only 領域・atomic rename・fsync・native index lock の可否。"""
    result = {
        "owner-only-area": False,
        "atomic-rename": hasattr(os, "replace"),
        "fsync": hasattr(os, "fsync"),
        "native-index-lock": False,
    }
    if not common_dir.is_dir():
        return result
    probe = common_dir / ".bitz-flow-doctor-probe"
    try:
        fd = os.open(probe, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(fd)
        result["owner-only-area"] = True
        result["native-index-lock"] = True
        os.unlink(probe)
    except OSError:
        pass
    try:
        dir_fd = os.open(common_dir, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except OSError:
        result["fsync"] = False
    return result


def diagnose(
    root: Path, *, uses_github: bool = True, gh_available: bool | None = None,
    remote_cas: bool = True,
) -> Diagnosis:
    """読み取り専用の診断。対象 project を変更しない。"""
    findings: list[Finding] = []
    capabilities: dict[str, bool] = {}

    # Python
    capabilities["python"] = sys.version_info >= (3, 10)
    if not capabilities["python"]:
        findings.append(Finding(
            "python", SEVERITY_MISSING, "Python 3.10 以上が必要",
            stage="validate", cause="command-unavailable",
            next_action="Python 3.10 以上を導入する",
        ))

    # Git
    version = _git_version()
    capabilities["git"] = version is not None and version[:2] >= MIN_GIT_VERSION
    if version is None:
        findings.append(Finding(
            "git", SEVERITY_MISSING, "git が見つからない",
            stage="inspect", cause="command-unavailable", next_action="git を導入する",
        ))
    elif version[:2] < MIN_GIT_VERSION:
        findings.append(Finding(
            "git", SEVERITY_MISSING,
            f"git {'.'.join(map(str, MIN_GIT_VERSION))} 以上が必要",
            stage="validate", cause="command-unavailable", next_action="git を更新する",
        ))

    # repository
    inside = _run(root, ["rev-parse", "--is-inside-work-tree"])
    capabilities["repository"] = inside.returncode == 0
    if not capabilities["repository"]:
        findings.append(Finding(
            "repository", SEVERITY_MISSING, "対象が Git work tree ではない",
            stage="inspect", cause="not-repository", next_action="git リポジトリ内で実行する",
        ))

    common_dir = root / ".git"
    if capabilities["repository"]:
        proc = _run(root, ["rev-parse", "--path-format=absolute", "--git-common-dir"])
        if proc.returncode == 0:
            common_dir = Path(proc.stdout.decode().strip())

    # remote / default branch
    remotes = _run(root, ["remote"]).stdout.decode().split() if capabilities["repository"] else []
    capabilities["remote"] = bool(remotes)
    if capabilities["repository"] and not remotes:
        findings.append(Finding(
            "remote", SEVERITY_WARNING, "remote が登録されていない",
            stage="inspect", cause="remote-unavailable",
            next_action="git remote add で remote を登録する",
        ))

    head = _run(root, ["symbolic-ref", "--quiet", "HEAD"]) if capabilities["repository"] else None
    capabilities["default-branch"] = bool(head and head.returncode == 0)
    if head is not None and head.returncode != 0:
        findings.append(Finding(
            "default-branch", SEVERITY_WARNING, "detached HEAD",
            stage="inspect", cause="detached-head",
            next_action="branch を checkout する",
        ))

    # gh（GitHub を使わないなら warning）
    if gh_available is None:
        gh_available = shutil.which("gh") is not None
    capabilities["gh"] = gh_available
    if not gh_available:
        findings.append(Finding(
            "gh", SEVERITY_MISSING if uses_github else SEVERITY_WARNING,
            "gh が見つからない",
            stage="inspect", cause="command-unavailable",
            next_action="gh を導入して認証する",
        ))

    # filesystem / locking
    capabilities.update(_filesystem_capabilities(common_dir))
    for name in ("owner-only-area", "atomic-rename", "fsync", "native-index-lock"):
        if not capabilities[name]:
            findings.append(Finding(
                name, SEVERITY_MISSING, f"{name} を提供できない",
                stage="validate", cause="permission-denied",
                next_action="write operation を使わないか、対応する filesystem を使う",
            ))

    # process tree 収束（この platform で子孫まで終了させられるか）
    capabilities["process-tree-convergence"] = hasattr(os, "killpg") or os.name == "nt"
    capabilities["remote-cas"] = remote_cas and capabilities["remote"]

    operations: dict[str, dict[str, object]] = {}
    for operation, required in OPERATION_CAPABILITIES.items():
        missing = [name for name in required if not capabilities.get(name, False)]
        operations[operation] = {
            "required": list(required),
            "missing": missing,
            "supported": not missing,
        }

    return Diagnosis(tuple(findings), capabilities, operations)


def render_findings(diagnosis: Diagnosis, *, repo_root: Path | None = None) -> list[str]:
    """診断を安全な表現へ落とす。絶対 path・秘密値を載せない。"""
    lines: list[str] = []
    for finding in diagnosis.findings:
        fields = {"name": finding.name, "detail": finding.detail}
        if finding.next_action:
            fields["next_action"] = finding.next_action
        safe = S.sanitize_diagnostic(fields, repo_root=repo_root)
        rendered = " ".join(f"{k}={v}" for k, v in safe.values.items())
        lines.append(f"{finding.severity.upper()} {rendered}")
        lines.extend(r.as_line() for r in safe.redactions)
    return lines
