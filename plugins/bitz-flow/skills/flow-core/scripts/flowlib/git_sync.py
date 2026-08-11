"""`git.fetch` と `git.sync` の plan / apply / reconcile（FLW-FR-005 / FLW-NFR-003）。

REC-FETCH と REC-SYNC の要点は「**部分完了を自動で埋めない**」ことである。

- fetch が ref 集合の一部だけを更新して終わったら、completed / remaining を確定して返す。
  fetch を再実行して埋めない（何が起きたか分からないまま状態が進むため）。
- sync が fetch まで終えて branch を更新できなかったら、`completed=fetch` /
  `remaining=branch-update` を提示する。自動で branch を更新しない。
- fast-forward できない場合は `non-fast-forward` で停止し、**merge や rebase を代替提示しない**。

外部ネットワークへは接続しない。remote はローカル bare リポジトリでも成立する契約にしてある。
"""

from __future__ import annotations

import dataclasses
import os
import subprocess
from pathlib import Path
from typing import Sequence

from . import git_read
from . import guard as GD

CODE_DONE = "DONE"
CODE_PARTIAL = "PARTIAL"
CODE_BLOCKED = "BLOCKED"
CODE_STALE = "STALE"
CODE_INVALID_INPUT = "INVALID_INPUT"

REC_FETCH = "REC-FETCH"
REC_SYNC = "REC-SYNC"


@dataclasses.dataclass(frozen=True)
class SyncFailure:
    code: str
    reason: str
    cause: str | None = None
    stage: str = "apply"


@dataclasses.dataclass(frozen=True)
class FetchPlan:
    remote: str
    refspecs: tuple[str, ...]
    prune: bool
    tracking_before: dict[str, str]
    fetch_head_before: str | None
    effects: tuple[str, ...]


@dataclasses.dataclass(frozen=True)
class FetchOutcome:
    code: str
    updated_refs: tuple[str, ...]
    completed_steps: tuple[str, ...]
    remaining_steps: tuple[str, ...]
    recovery: str
    freshness: dict[str, str]


@dataclasses.dataclass(frozen=True)
class SyncOutcome:
    code: str
    completed_steps: tuple[str, ...]
    remaining_steps: tuple[str, ...]
    recovery: str
    cause: str | None = None


#: remote 到達不能を表す stderr の断片。M0 の `_classify` は read 用で remote 系を持たず、
#: 分類できないものを `result-indeterminate`（成否不明）へ落としてしまう。fetch / push の失敗を
#: 「成否不明」と報告すると、呼出側は reconcile へ進めず不必要に人間を呼ぶことになる。
_REMOTE_UNAVAILABLE_HINTS = (
    "could not read from remote",
    "repository not found",
    "does not appear to be a git repository",
    "unable to access",
    "connection",
    "could not resolve host",
    "no such remote",
)


def classify_remote(stderr: bytes) -> str:
    """remote 操作の失敗を許可語彙 cause へ正規化する。"""
    text = stderr.decode("utf-8", "replace").lower()
    if any(hint in text for hint in _REMOTE_UNAVAILABLE_HINTS):
        return "remote-unavailable"
    classified = git_read._classify(stderr)
    if classified == "result-indeterminate":
        # remote 操作で分類できない失敗は、成否不明ではなく到達不能として扱う。
        return "remote-unavailable"
    return classified


def _run(root: Path, args: Sequence[str]) -> subprocess.CompletedProcess:
    environ = dict(os.environ)
    environ.update(git_read.GIT_ENV)
    return subprocess.run(
        ["git", *git_read.GIT_COMMON_FLAGS, *args],
        cwd=str(root),
        capture_output=True,
        env=environ,
    )


def tracking_refs(root: Path, remote: str) -> dict[str, str]:
    """remote-tracking ref 集合の現在値。"""
    proc = _run(root, ["for-each-ref", "--format=%(refname)%09%(objectname)", f"refs/remotes/{remote}"])
    result: dict[str, str] = {}
    for line in proc.stdout.decode("utf-8", "surrogateescape").splitlines():
        if "\t" in line:
            ref, oid = line.split("\t", 1)
            result[ref] = oid
    return result


def fetch_head(root: Path, common_dir: Path) -> str | None:
    path = Path(common_dir) / "FETCH_HEAD"
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8", errors="replace").strip() or None


# --- git.fetch ----------------------------------------------------------------


def plan_fetch(
    root: Path, common_dir: Path, *, remote: str, refspecs: Sequence[str] = (), prune: bool = False
) -> tuple[FetchPlan | None, SyncFailure | None]:
    """明示した remote だけを対象にする plan（副作用なし）。"""
    if not remote:
        return None, SyncFailure(CODE_INVALID_INPUT, "remote を明示すること", stage="validate")

    known = _run(root, ["remote"]).stdout.decode().split()
    if remote not in known:
        return None, SyncFailure(
            CODE_BLOCKED, "未登録の remote は対象にしない", cause="remote-unavailable", stage="plan"
        )

    return (
        FetchPlan(
            remote=remote,
            refspecs=tuple(refspecs),
            prune=prune,
            tracking_before=tracking_refs(root, remote),
            fetch_head_before=fetch_head(root, common_dir),
            effects=(f"update remote-tracking refs of {remote}", "update FETCH_HEAD"),
        ),
        None,
    )


def guard_targets_for_fetch(common_dir: Path, remote: str, plan: FetchPlan) -> list[GD.Target]:
    """canonical mutation target: remote-tracking ref 集合と FETCH_HEAD。"""
    targets = [GD.canonical_fetch_head_target(common_dir)]
    for ref in plan.tracking_before:
        targets.append(GD.canonical_remote_tracking_target(common_dir, ref))
    if not plan.tracking_before:
        targets.append(GD.canonical_remote_tracking_target(common_dir, f"refs/remotes/{remote}/*"))
    return GD.order(targets)


def apply_fetch(
    root: Path, common_dir: Path, plan: FetchPlan, *, expected_refs: Sequence[str] = ()
) -> tuple[FetchOutcome | None, SyncFailure | None]:
    """fetch を実行し、更新できた ref 集合から完了段階を確定する。"""
    args = ["fetch", plan.remote, *plan.refspecs]
    if plan.prune:
        args.insert(1, "--prune")
    proc = _run(root, args)
    if proc.returncode != 0:
        return None, SyncFailure(
            CODE_BLOCKED, "fetch を完了できない", cause=classify_remote(proc.stderr)
        )

    after = tracking_refs(root, plan.remote)
    updated = tuple(
        sorted(ref for ref, oid in after.items() if plan.tracking_before.get(ref) != oid)
    )

    expected = list(expected_refs)
    if expected:
        remaining = tuple(sorted(set(expected) - set(updated)))
        if remaining:
            # 一部だけ更新された。fetch を再実行して埋めない。
            return (
                FetchOutcome(
                    code=CODE_PARTIAL,
                    updated_refs=updated,
                    completed_steps=tuple(f"update {ref}" for ref in updated),
                    remaining_steps=tuple(f"update {ref}" for ref in remaining),
                    recovery=REC_FETCH,
                    freshness={"remote": plan.remote, "fetch_head": fetch_head(root, common_dir) or ""},
                ),
                None,
            )

    return (
        FetchOutcome(
            code=CODE_DONE,
            updated_refs=updated,
            completed_steps=tuple(f"update {ref}" for ref in updated),
            remaining_steps=(),
            recovery=REC_FETCH,
            freshness={"remote": plan.remote, "fetch_head": fetch_head(root, common_dir) or ""},
        ),
        None,
    )


# --- git.sync -----------------------------------------------------------------


def guard_targets_for_sync(common_dir: Path, remote: str, branch: str, plan: FetchPlan) -> list[GD.Target]:
    """canonical mutation target: branch ref・index・remote-tracking ref 集合。"""
    targets = [
        GD.canonical_local_ref_target(common_dir, branch),
        GD.canonical_index_target(common_dir, "main"),
        *guard_targets_for_fetch(common_dir, remote, plan),
    ]
    return GD.order(targets)


def apply_sync(
    root: Path, common_dir: Path, plan: FetchPlan, *, branch: str, upstream: str
) -> tuple[SyncOutcome | None, SyncFailure | None]:
    """fetch 後に `merge --ff-only`。ff できなければ停止し、代替を提示しない。"""
    outcome, failure = apply_fetch(root, common_dir, plan)
    if failure is not None:
        return None, failure

    before = _run(root, ["rev-parse", branch]).stdout.decode().strip()
    merged = _run(root, ["merge", "--ff-only", upstream])
    after = _run(root, ["rev-parse", branch]).stdout.decode().strip()

    if merged.returncode != 0:
        cause = git_read._classify(merged.stderr) or "non-fast-forward"
        if cause not in ("non-fast-forward", "dirty", "conflict"):
            cause = "non-fast-forward"
        # fetch は終わっているので、その事実を completed として残す。
        return (
            SyncOutcome(
                code=CODE_PARTIAL,
                completed_steps=("fetch",),
                remaining_steps=("branch-update",),
                recovery=REC_SYNC,
                cause=cause,
            ),
            None,
        )

    if before == after:
        return (
            SyncOutcome(
                code=CODE_PARTIAL if outcome.updated_refs else CODE_DONE,
                completed_steps=("fetch",),
                remaining_steps=("branch-update",) if outcome.updated_refs else (),
                recovery=REC_SYNC,
            ),
            None,
        )

    return (
        SyncOutcome(
            code=CODE_DONE,
            completed_steps=("fetch", "branch-update"),
            remaining_steps=(),
            recovery=REC_SYNC,
        ),
        None,
    )


def next_actions_for(outcome: SyncOutcome | FetchOutcome) -> tuple[str, ...]:
    """PARTIAL からの次の一手は read-only の reconcile だけ。"""
    if outcome.code != CODE_PARTIAL:
        return ()
    return ("git.status", "git.branches")
