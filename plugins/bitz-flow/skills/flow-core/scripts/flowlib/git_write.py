"""Git write adapter — `git.stage` の plan / apply（FLW-DSN-015 / FLW-FR-005）。

read adapter（`git_read.py`）に write を混ぜない。read と write の境界が boundary 宣言の単位であり、
「読むだけのつもりが書いていた」経路を構造的に作らないためである。

index の更新は **Git native `index.lock` 規約**に従う。

1. plan 時に、予定 index の bytes を**副作用なしで**一時領域に作る
2. target guard 取得後に `index.lock` を exclusive create する
3. lock 保持下で現 index digest を再読し、plan snapshot と一致したときだけ書く
4. file fsync → atomic rename → directory fsync で公開する

**lock 内から通常の `git add` を起動しない**。起動すると Git 自身が `index.lock` を取りにいって
失敗するか、こちらの排他を迂回した書き込みになる。

native index lock / atomic rename / 同一 filesystem を提供できない platform では stage を
`UNSUPPORTED` とする。
"""

from __future__ import annotations

import dataclasses
import os
import subprocess
from pathlib import Path
from typing import Sequence

from . import git_read
from . import result as R

CODE_BLOCKED = "BLOCKED"
CODE_STALE = "STALE"
CODE_UNSUPPORTED = "UNSUPPORTED"
CODE_INVALID_INPUT = "INVALID_INPUT"

INDEX_LOCK_NAME = "index.lock"
INDEX_NAME = "index"


@dataclasses.dataclass(frozen=True)
class WriteFailure:
    code: str
    reason: str
    cause: str | None = None
    stage: str = "apply"


@dataclasses.dataclass(frozen=True)
class StagePlan:
    """副作用なしで作った plan。`effects` が apply の上限である。"""

    paths: tuple[str, ...]
    index_digest: str
    planned_index_bytes: bytes
    effects: tuple[str, ...]

    @property
    def target_summary(self) -> str:
        return f"index({len(self.paths)} paths)"


def _git(root: Path, args: Sequence[str], *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    environ = dict(os.environ)
    environ.update(git_read.GIT_ENV)
    if env:
        environ.update(env)
    return subprocess.run(
        ["git", *git_read.GIT_COMMON_FLAGS, *args],
        cwd=str(root),
        capture_output=True,
        env=environ,
    )


def index_path(common_dir: Path) -> Path:
    return Path(common_dir) / INDEX_NAME


def index_digest(common_dir: Path) -> str:
    """現在の index の内容 digest。存在しなければ空の digest。"""
    path = index_path(common_dir)
    if not path.exists():
        return R.sha256_of(b"")
    return R.sha256_of(path.read_bytes())


def capability(common_dir: Path) -> list[str]:
    """stage に必要な capability のうち提供できないものを返す。"""
    missing: list[str] = []
    common = Path(common_dir)
    if not common.is_dir():
        missing.append("Git common-dir")
        return missing
    if not hasattr(os, "replace"):
        missing.append("atomic rename")
    try:
        probe = common / ".bitz-flow-capability-probe"
        fd = os.open(probe, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(fd)
        os.unlink(probe)
    except OSError:
        missing.append("owner-only 領域への排他作成")
    return missing


def plan_stage(
    repo_root: Path, common_dir: Path, paths: Sequence[str]
) -> tuple[StagePlan | None, WriteFailure | None]:
    """`git add -- <paths>` 相当の予定 index を副作用なしで作る。

    実際の index は触らず、`GIT_INDEX_FILE` で一時 index に対して読み書きする。
    """
    if not paths:
        return None, WriteFailure(CODE_INVALID_INPUT, "stage する path を明示すること（`git add .` 相当は提供しない）")
    for path in paths:
        if path in (".", "-A", "--all", "*"):
            return None, WriteFailure(
                CODE_INVALID_INPUT, f"一括指定は受け付けない: {path}"
            )

    missing = capability(common_dir)
    if missing:
        return None, WriteFailure(
            CODE_UNSUPPORTED, "index の原子的更新を提供できない: " + ", ".join(missing), stage="validate"
        )

    current = index_path(Path(common_dir))
    temp_index = Path(common_dir) / f".bitz-flow-plan-index-{os.getpid()}"
    try:
        if current.exists():
            temp_index.write_bytes(current.read_bytes())
        proc = _git(
            repo_root, ["add", "--", *paths], env={"GIT_INDEX_FILE": str(temp_index)}
        )
        if proc.returncode != 0:
            return None, WriteFailure(
                CODE_BLOCKED,
                "予定 index を作成できない",
                cause=git_read._classify(proc.stderr),
                stage="plan",
            )
        planned = temp_index.read_bytes()
    except OSError as exc:
        return None, WriteFailure(CODE_BLOCKED, f"予定 index を作成できない: {exc.strerror}", stage="plan")
    finally:
        if temp_index.exists():
            temp_index.unlink()

    return (
        StagePlan(
            paths=tuple(paths),
            index_digest=index_digest(Path(common_dir)),
            planned_index_bytes=planned,
            effects=tuple(f"stage {p}" for p in paths),
        ),
        None,
    )


def apply_stage(
    common_dir: Path, plan: StagePlan, *, on_locked=None
) -> tuple[str | None, WriteFailure | None]:
    """plan の index bytes を native lock 規約で公開する。

    `on_locked` は fault 注入用のフックで、lock 保持中・公開前に呼ばれる。
    """
    common = Path(common_dir)
    lock = common / INDEX_LOCK_NAME
    target = index_path(common)

    try:
        fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return None, WriteFailure(
            CODE_BLOCKED,
            "index.lock を他の writer が保持している",
            cause="permission-denied",
        )
    except OSError as exc:
        return None, WriteFailure(CODE_BLOCKED, f"index.lock を作成できない: {exc.strerror}")

    try:
        # lock 保持下で現 index を再読し、plan 時点から動いていないことを確かめる。
        if index_digest(common) != plan.index_digest:
            return None, WriteFailure(
                CODE_STALE,
                "index が plan 時点から変化している",
                cause="snapshot-mismatch",
            )

        if on_locked is not None:
            on_locked(common)
            if index_digest(common) != plan.index_digest:
                # 管理外 process が native lock を無視して書いた。
                return None, WriteFailure(
                    CODE_BLOCKED,
                    "lock を無視した writer が index を変更した（quarantine 対象）",
                    cause="snapshot-mismatch",
                )

        os.write(fd, plan.planned_index_bytes)
        os.fsync(fd)
        os.close(fd)
        fd = None
        os.replace(lock, target)

        dir_fd = os.open(common, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except OSError as exc:
        return None, WriteFailure(CODE_BLOCKED, f"index を更新できない: {exc.strerror}")
    finally:
        if fd is not None:
            os.close(fd)
        if lock.exists():
            lock.unlink()

    return index_digest(common), None


def verify_postcondition(common_dir: Path, expected_digest: str) -> WriteFailure | None:
    """apply 後の index が予定値と一致するか。"""
    actual = index_digest(Path(common_dir))
    if actual != expected_digest:
        return WriteFailure(
            CODE_BLOCKED,
            "apply 後の index が予定値と一致しない（quarantine 対象）",
            cause="snapshot-mismatch",
            stage="post-check",
        )
    return None
