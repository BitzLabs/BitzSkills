"""remote-write の plan / apply / reconcile（FLW-FR-005 / FLW-CON-005 / FLW-CON-006）。

remote への書き込みは、失敗しても手元から取り消せない。したがって次を守る。

- **expected HEAD / expected remote SHA を apply 直前に再照会**し、一致した場合だけ実行する。
  plan 時点の値をそのまま信じない（TOCTOU）。
- **force を提供しない**。実装にも診断にも `next_actions` にも現れない。
- **応答喪失時は成否を推定しない**。remote の CAS 結果を確認できなければ `INDETERMINATE` とし、
  「たぶん成功した」も「たぶん失敗した」も言わない。
- `delete-remote-branch` は**独立 operation**とし、finish / merge へ自動連結しない。
  `approval` は `explicit-human`。

remote CAS（server-side の expected OID 検証）を提供できない platform では publish を
`UNSUPPORTED` とする。ここでは Git の `--force-with-lease=<ref>:<expected>` 相当の
明示 expected 指定を CAS の実体として使う。
"""

from __future__ import annotations

import dataclasses
import os
import subprocess
from pathlib import Path
from typing import Sequence

from . import git_read
from . import git_sync
from . import guard as GD

CODE_DONE = "DONE"
CODE_BLOCKED = "BLOCKED"
CODE_STALE = "STALE"
CODE_INDETERMINATE = "INDETERMINATE"
CODE_INVALID_INPUT = "INVALID_INPUT"
CODE_UNSUPPORTED = "UNSUPPORTED"
CODE_APPROVAL_REQUIRED = "APPROVAL_REQUIRED"

REC_PUSH = "REC-PUSH"

APPROVAL_EXPLICIT_HUMAN = "explicit-human"

#: 提供しない操作。実装にも next_actions にも現れてはならない（FLW-CON-006）。
FORBIDDEN_OPERATIONS = (
    "force-push", "reset --hard", "clean -f", "rebase", "stash", "git config",
)


@dataclasses.dataclass(frozen=True)
class PublishFailure:
    code: str
    reason: str
    cause: str | None = None
    stage: str = "apply"


@dataclasses.dataclass(frozen=True)
class PublishPlan:
    remote: str
    branch: str
    expected_head: str
    local_head: str
    upstream: str | None
    approval: str
    effects: tuple[str, ...]


@dataclasses.dataclass(frozen=True)
class DeletePlan:
    remote: str
    ref: str
    expected_remote_sha: str
    merged_evidence: tuple[str, ...]
    approval: str
    effects: tuple[str, ...]


@dataclasses.dataclass(frozen=True)
class PublishOutcome:
    code: str
    recovery: str
    remote_ref: str
    before_sha: str | None
    after_sha: str | None


def _run(root: Path, args: Sequence[str]) -> subprocess.CompletedProcess:
    environ = dict(os.environ)
    environ.update(git_read.GIT_ENV)
    return subprocess.run(
        ["git", *git_read.GIT_COMMON_FLAGS, *args],
        cwd=str(root),
        capture_output=True,
        env=environ,
    )


def remote_ref_sha(root: Path, remote: str, ref: str) -> tuple[str | None, PublishFailure | None]:
    """remote ref を**再照会**する。plan 時点の値を信じない。"""
    proc = _run(root, ["ls-remote", "--exit-code", remote, ref])
    if proc.returncode == 2:
        return None, None  # ref が存在しない（新規 branch）
    if proc.returncode != 0:
        return None, PublishFailure(
            CODE_BLOCKED, "remote ref を再照会できない",
            cause=git_sync.classify_remote(proc.stderr), stage="validate",
        )
    line = proc.stdout.decode("utf-8", "replace").split("\n")[0]
    return (line.split("\t")[0] if line else None), None


def capability(*, remote_cas: bool = True) -> list[str]:
    return [] if remote_cas else ["remote の server-side CAS"]


# --- git.publish-branch --------------------------------------------------------


def plan_publish(
    root: Path, *, remote: str, branch: str, remote_cas: bool = True
) -> tuple[PublishPlan | None, PublishFailure | None]:
    missing = capability(remote_cas=remote_cas)
    if missing:
        return None, PublishFailure(
            CODE_UNSUPPORTED, "remote CAS を提供できない platform では publish しない: " + ", ".join(missing),
            stage="validate",
        )

    local = _run(root, ["rev-parse", branch])
    if local.returncode != 0:
        return None, PublishFailure(
            CODE_INVALID_INPUT, "対象 branch を解決できない",
            cause=git_read._classify(local.stderr), stage="plan",
        )
    local_head = local.stdout.decode().strip()

    ref = f"refs/heads/{branch}"
    expected, failure = remote_ref_sha(root, remote, ref)
    if failure is not None:
        return None, failure

    upstream_proc = _run(root, ["rev-parse", "--abbrev-ref", f"{branch}@{{upstream}}"])
    upstream = upstream_proc.stdout.decode().strip() if upstream_proc.returncode == 0 else None

    return (
        PublishPlan(
            remote=remote,
            branch=branch,
            expected_head=expected or "",
            local_head=local_head,
            upstream=upstream,
            approval=APPROVAL_EXPLICIT_HUMAN,
            effects=(f"update {remote}:{ref} to {local_head[:12]}",),
        ),
        None,
    )


def guard_targets_for_publish(host: str, repository_id: str, branch: str) -> list[GD.Target]:
    """canonical mutation target: repository ID + remote branch ref（local identity を混ぜない）。"""
    return [GD.canonical_remote_ref_target(host, repository_id, f"refs/heads/{branch}")]


def apply_publish(
    root: Path, plan: PublishPlan, *, approved: bool, response_lost: bool = False
) -> tuple[PublishOutcome | None, PublishFailure | None]:
    """force なし push。expected HEAD を再照会してから実行する。"""
    if not approved:
        return None, PublishFailure(
            CODE_APPROVAL_REQUIRED, "remote-write には明示的な人間承認が要る", stage="validate"
        )

    ref = f"refs/heads/{plan.branch}"
    current, failure = remote_ref_sha(root, plan.remote, ref)
    if failure is not None:
        return None, failure
    if (current or "") != plan.expected_head:
        return None, PublishFailure(
            CODE_STALE, "remote ref が plan 時点から変化している",
            cause="snapshot-mismatch", stage="validate",
        )

    if response_lost:
        # 応答が返らなかった。成否を推定しない。
        return (
            PublishOutcome(
                code=CODE_INDETERMINATE, recovery=REC_PUSH, remote_ref=ref,
                before_sha=current, after_sha=None,
            ),
            None,
        )

    args = ["push", plan.remote, f"{plan.local_head}:{ref}"]
    if plan.expected_head:
        args.insert(1, f"--force-with-lease={ref}:{plan.expected_head}")
    proc = _run(root, args)
    if proc.returncode != 0:
        return None, PublishFailure(
            CODE_BLOCKED, "push を完了できない", cause=git_sync.classify_remote(proc.stderr)
        )

    after, failure = remote_ref_sha(root, plan.remote, ref)
    if failure is not None:
        return None, failure
    return (
        PublishOutcome(
            code=CODE_DONE if after == plan.local_head else CODE_INDETERMINATE,
            recovery=REC_PUSH, remote_ref=ref, before_sha=current, after_sha=after,
        ),
        None,
    )


# --- git.delete-remote-branch --------------------------------------------------


def plan_delete_remote_branch(
    root: Path, *, remote: str, branch: str, merged_evidence: Sequence[str] = ()
) -> tuple[DeletePlan | None, PublishFailure | None]:
    ref = f"refs/heads/{branch}"
    expected, failure = remote_ref_sha(root, remote, ref)
    if failure is not None:
        return None, failure
    if expected is None:
        return None, PublishFailure(
            CODE_BLOCKED, "削除対象の remote ref が存在しない", cause="invalid-ref", stage="plan"
        )

    return (
        DeletePlan(
            remote=remote, ref=ref, expected_remote_sha=expected,
            merged_evidence=tuple(merged_evidence),
            approval=APPROVAL_EXPLICIT_HUMAN,
            effects=(f"delete {remote}:{ref}",),
        ),
        None,
    )


def apply_delete_remote_branch(
    root: Path, plan: DeletePlan, *, approved: bool, response_lost: bool = False
) -> tuple[PublishOutcome | None, PublishFailure | None]:
    """exact ref だけを削除する。expected remote SHA を再照会して一致した場合のみ。"""
    if not approved:
        return None, PublishFailure(
            CODE_APPROVAL_REQUIRED, "破壊操作には独立した人間承認が要る", stage="validate"
        )

    current, failure = remote_ref_sha(root, plan.remote, plan.ref)
    if failure is not None:
        return None, failure
    if current != plan.expected_remote_sha:
        return None, PublishFailure(
            CODE_STALE, "remote ref が plan 時点から変化しているため削除しない",
            cause="snapshot-mismatch", stage="validate",
        )

    if response_lost:
        return (
            PublishOutcome(
                code=CODE_INDETERMINATE, recovery=REC_PUSH, remote_ref=plan.ref,
                before_sha=current, after_sha=None,
            ),
            None,
        )

    proc = _run(root, ["push", plan.remote, "--delete", plan.ref])
    if proc.returncode != 0:
        return None, PublishFailure(
            CODE_BLOCKED, "remote branch を削除できない", cause=git_sync.classify_remote(proc.stderr)
        )

    after, failure = remote_ref_sha(root, plan.remote, plan.ref)
    if failure is not None:
        return None, failure
    return (
        PublishOutcome(
            code=CODE_DONE if after is None else CODE_INDETERMINATE,
            recovery=REC_PUSH, remote_ref=plan.ref, before_sha=current, after_sha=after,
        ),
        None,
    )


# --- REC-PUSH ------------------------------------------------------------------


def next_actions_for(outcome: PublishOutcome | PublishFailure) -> tuple[str, ...]:
    """STALE は remote ref の全件再照会と新 plan へ。force / update の再実行は出さない。"""
    code = outcome.code
    if code == CODE_STALE:
        return ("git.branches",)
    if code == CODE_INDETERMINATE:
        return ()  # 成否不明では自動で次へ進まない
    return ()


def required_human_input(outcome: PublishOutcome) -> tuple[str, ...]:
    if outcome.code != CODE_INDETERMINATE:
        return ()
    return (
        "remote ref の現在値の確認",
        "push が適用されたかどうかの裁定",
        "続行または中止の判断",
    )
