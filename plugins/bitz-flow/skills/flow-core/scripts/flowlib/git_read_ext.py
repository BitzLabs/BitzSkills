"""M1 で追加する Git read adapter（FLW-FR-004 / FLW-DSN-005）。

M0 の `git_read.py`（`repo inspect` / `status` / `diff-summary`）に対して、
`diff-detail` / `log` / `branches` / `conflicts` / `worktree list` を足す。

共通規律は M0 と同じ:

- path は NUL 区切りで取得し、改行・空白・非 ASCII を含む filename を損なわない
- pager・color・external diff を無効化する（`git_read` の共通 flags を共有）
- 失敗は許可語彙 cause へ正規化し、生の stderr を公開しない
- 副作用を持たない（暗黙の fetch や ref 更新をしない）

`diff-detail` だけは**上限**を持つ。変更行の全文は容易に巨大化するため、最大 bytes と
最大 hunks を受け取り、**超過したことを必ず明示する**（黙って切らない）。
"""

from __future__ import annotations

import dataclasses
import os
import subprocess
from pathlib import Path
from typing import Sequence

from . import git_read
from . import result as R

DEFAULT_MAX_BYTES = 64 * 1024
DEFAULT_MAX_HUNKS = 50
DEFAULT_LOG_LIMIT = 20

#: レコード区切りは `-z` の NUL、field 区切りは Unit Separator。
#: どちらも NUL にすると区切りが混ざって parse できない。
_FIELD_SEPARATOR = "\x1f"
_LOG_FORMAT = "%H%x1f%h%x1f%s%x1f%aI%x1f%P"


@dataclasses.dataclass(frozen=True)
class ReadFailure:
    cause: str
    stage: str = "inspect"


def _run(root: Path, args: Sequence[str]) -> tuple[bytes | None, ReadFailure | None]:
    environ = dict(os.environ)
    environ.update(git_read.GIT_ENV)
    proc = subprocess.run(
        ["git", *git_read.GIT_COMMON_FLAGS, *args],
        cwd=str(root),
        capture_output=True,
        env=environ,
    )
    if proc.returncode != 0:
        return None, ReadFailure(git_read._classify(proc.stderr))
    return proc.stdout, None


def _decode(raw: bytes) -> str:
    return raw.decode("utf-8", "surrogateescape")


def _split_nul(raw: bytes) -> list[str]:
    return [_decode(part) for part in raw.split(b"\x00") if part]


# --- git.diff-detail ----------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class DiffDetail:
    paths: tuple[str, ...]
    hunks: tuple[dict[str, object], ...]
    truncated: bool
    shown_bytes: int
    total_bytes: int
    shown_hunks: int
    total_hunks: int
    snapshot: str


def diff_detail(
    root: Path,
    paths: Sequence[str],
    *,
    base: str = "HEAD",
    max_bytes: int = DEFAULT_MAX_BYTES,
    max_hunks: int = DEFAULT_MAX_HUNKS,
) -> tuple[DiffDetail | None, ReadFailure | None]:
    """指定 path の変更行を返す。上限超過は必ず可視化する。"""
    if not paths:
        return None, ReadFailure("invalid-path", stage="validate")

    raw, failure = _run(
        root, ["diff", "--no-ext-diff", "--unified=1", base, "--", *paths]
    )
    if failure is not None:
        return None, failure

    text = _decode(raw)
    all_hunks: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    for line in text.splitlines():
        if line.startswith("@@"):
            current = {"header": line, "lines": []}
            all_hunks.append(current)
        elif current is not None:
            current["lines"].append(line)

    total_bytes = len(raw)
    total_hunks = len(all_hunks)

    kept: list[dict[str, object]] = []
    used = 0
    for hunk in all_hunks:
        size = len(hunk["header"].encode("utf-8")) + sum(
            len(line.encode("utf-8")) + 1 for line in hunk["lines"]
        )
        if len(kept) >= max_hunks or used + size > max_bytes:
            break
        kept.append(hunk)
        used += size

    return (
        DiffDetail(
            paths=tuple(paths),
            hunks=tuple(kept),
            # truncated は「hunk を落としたか」で判定する。raw には diff ヘッダも含むため、
            # hunk の合計 byte と raw 総 byte の比較では常に truncated になってしまう。
            truncated=len(kept) < total_hunks,
            shown_bytes=used,
            total_bytes=total_bytes,
            shown_hunks=len(kept),
            total_hunks=total_hunks,
            snapshot=R.snapshot_of([base, sorted(paths), total_bytes, total_hunks]),
        ),
        None,
    )


# --- git.log ------------------------------------------------------------------


def log(
    root: Path, *, limit: int = DEFAULT_LOG_LIMIT, ref: str = "HEAD"
) -> tuple[list[dict[str, object]] | None, ReadFailure | None]:
    raw, failure = _run(
        root, ["log", f"--max-count={limit}", f"--format={_LOG_FORMAT}", "-z", ref]
    )
    if failure is not None:
        return None, failure

    entries: list[dict[str, object]] = []
    for record in raw.split(b"\x00"):
        fields = _decode(record).strip("\n").split(_FIELD_SEPARATOR)
        if len(fields) < 4 or not fields[0]:
            continue
        parents = fields[4].split() if len(fields) > 4 and fields[4] else []
        entries.append(
            {
                "sha": fields[0],
                "short_sha": fields[1],
                "subject": fields[2],
                "author_date": fields[3],
                "parents": parents,
            }
        )
    return entries[:limit], None


# --- git.branches -------------------------------------------------------------


def branches(root: Path) -> tuple[list[dict[str, object]] | None, ReadFailure | None]:
    fmt = "%(refname)%00%(objectname:short)%00%(upstream:short)%00%(upstream:track)"
    raw, failure = _run(root, ["for-each-ref", f"--format={fmt}", "refs/heads", "refs/remotes"])
    if failure is not None:
        return None, failure

    result: list[dict[str, object]] = []
    for line in _decode(raw).splitlines():
        if not line.strip():
            continue
        fields = line.split("\x00")
        refname = fields[0]
        track = fields[3] if len(fields) > 3 else ""
        ahead = behind = 0
        if "ahead " in track:
            ahead = int(track.split("ahead ")[1].split("]")[0].split(",")[0])
        if "behind " in track:
            behind = int(track.split("behind ")[1].split("]")[0].split(",")[0])
        result.append(
            {
                "ref": refname,
                "scope": "remote" if refname.startswith("refs/remotes/") else "local",
                "sha": fields[1] if len(fields) > 1 else "",
                "upstream": fields[2] if len(fields) > 2 and fields[2] else None,
                "ahead": ahead,
                "behind": behind,
            }
        )
    return result, None


# --- git.conflicts ------------------------------------------------------------


def conflicts(root: Path) -> tuple[list[str] | None, ReadFailure | None]:
    raw, failure = _run(root, ["diff", "--name-only", "--diff-filter=U", "-z"])
    if failure is not None:
        return None, failure
    return _split_nul(raw), None


# --- worktree.list ------------------------------------------------------------


def worktree_list(root: Path) -> tuple[list[dict[str, object]] | None, ReadFailure | None]:
    raw, failure = _run(root, ["worktree", "list", "--porcelain"])
    if failure is not None:
        return None, failure

    entries: list[dict[str, object]] = []
    current: dict[str, object] = {}
    for line in _decode(raw).splitlines():
        if not line:
            if current:
                entries.append(current)
                current = {}
            continue
        key, _, value = line.partition(" ")
        if key == "worktree":
            current = {"path": value, "head": None, "branch": None,
                       "locked": False, "prunable": False}
        elif key == "HEAD":
            current["head"] = value
        elif key == "branch":
            current["branch"] = value
        elif key == "locked":
            current["locked"] = True
        elif key == "prunable":
            current["prunable"] = True
        elif key == "detached":
            current["branch"] = None
    if current:
        entries.append(current)
    return entries, None
