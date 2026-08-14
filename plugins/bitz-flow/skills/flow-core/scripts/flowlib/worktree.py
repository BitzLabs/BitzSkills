"""M2 worktree create/resume/audit の観測状態機械（FLW-FR-006 / 007）。"""

from __future__ import annotations

import dataclasses


WORK_UNIT_STATES = (
    "PLANNED", "ISOLATED", "ACTIVE", "VERIFIED", "PR_DRAFT", "REVIEW_READY",
    "MERGE_READY", "MERGED", "AUDITED", "CLEANED", "FAILED_RETAINED", "DISCARDED",
)
WORKTREE_STATES = ("ABSENT", "CLEAN", "DIRTY", "MISMATCH")
BRANCH_AUDIT_STATES = (
    "ACTIVE", "MERGED_EXACT", "REMOTE_ADVANCED", "WORKTREE_IN_USE", "ORPHAN",
)

CREATE_STEPS = (
    "verify-path-scope", "create-local-ref", "create-worktree-dir", "set-head",
    "publish-instance-nonce", "publish-registry-entry",
)
RESUME_STEPS = (
    "verify-registry-binding", "verify-instance-nonce", "verify-head-oid",
    "acquire-worktree-guard", "publish-resume-receipt",
)


@dataclasses.dataclass(frozen=True)
class OperationDecision:
    code: str
    action: str | None = None
    worktree_state: str | None = None
    branch_audit_state: str | None = None
    completed_steps: tuple[str, ...] = ()
    remaining_steps: tuple[str, ...] = ()
    reason: str = ""


@dataclasses.dataclass(frozen=True)
class AuditObservation:
    evidence_complete: bool
    directory_exists: bool
    registry_exists: bool
    binding_valid: bool
    branch_matches: bool
    head_matches: bool
    dirty: bool = False
    branch_in_other_worktree: bool = False
    local_branch_exists: bool = True
    remote_branch_exists: bool = False
    merged_exact: bool = False
    remote_advanced: bool = False


def audit_worktree(observation: AuditObservation) -> OperationDecision:
    """worktree/branch の直交状態を外部観測だけから再構成する。"""
    if not observation.evidence_complete:
        return OperationDecision("INDETERMINATE", reason="監査証跡が不完全なため分類しない")

    if not observation.directory_exists and not observation.registry_exists:
        worktree_state = "ABSENT"
    elif not (
        observation.directory_exists
        and observation.registry_exists
        and observation.binding_valid
        and observation.branch_matches
        and observation.head_matches
    ):
        return OperationDecision(
            "BLOCKED", worktree_state="MISMATCH", branch_audit_state="ORPHAN",
            reason="directory / registry / branch / HEAD の照合不一致",
        )
    else:
        worktree_state = "DIRTY" if observation.dirty else "CLEAN"

    if observation.branch_in_other_worktree:
        branch_state = "WORKTREE_IN_USE"
    elif observation.merged_exact:
        branch_state = "MERGED_EXACT"
    elif observation.remote_advanced:
        branch_state = "REMOTE_ADVANCED"
    elif observation.local_branch_exists or observation.remote_branch_exists:
        branch_state = "ACTIVE"
    else:
        branch_state = "ORPHAN"
    return OperationDecision(
        "DONE", worktree_state=worktree_state, branch_audit_state=branch_state
    )


def plan_create(observation: AuditObservation) -> OperationDecision:
    """create要求を create / resume / BLOCKED へ決定的に分岐する。"""
    audit = audit_worktree(observation)
    if audit.code == "INDETERMINATE":
        return audit
    if observation.branch_in_other_worktree:
        return dataclasses.replace(audit, code="BLOCKED", reason="WORKTREE_IN_USE")
    if audit.worktree_state in {"CLEAN", "DIRTY"} and audit.branch_audit_state != "ORPHAN":
        return dataclasses.replace(audit, action="worktree.resume", reason="既存instanceと完全一致")
    if audit.worktree_state == "ABSENT":
        return dataclasses.replace(
            audit, action="worktree.create", completed_steps=(), remaining_steps=CREATE_STEPS
        )
    return dataclasses.replace(audit, code="BLOCKED", reason="既存worktreeが部分一致")


def reconcile_create(
    completed_steps: tuple[str, ...], observation: AuditObservation
) -> OperationDecision:
    """crash後の create を receipt prefix と双方向照合から一意化する。"""
    if completed_steps != CREATE_STEPS[: len(completed_steps)]:
        return OperationDecision("INDETERMINATE", reason="create receiptがstep列のprefixでない")
    if completed_steps == CREATE_STEPS and audit_worktree(observation).code == "DONE":
        return OperationDecision("DONE", completed_steps=completed_steps)
    published = "publish-registry-entry" in completed_steps
    return OperationDecision(
        "PARTIAL" if published else "STALE",
        completed_steps=completed_steps,
        remaining_steps=CREATE_STEPS[len(completed_steps) :],
        reason="registry公開後の不一致" if published else "registry公開前の中断",
    )


def plan_resume(
    *, expected_instance_digest: str, observed_instance_digest: str, audit: OperationDecision
) -> OperationDecision:
    if audit.code != "DONE" or audit.worktree_state not in {"CLEAN", "DIRTY"}:
        return OperationDecision("BLOCKED", reason="resume可能なbindingでない")
    if expected_instance_digest != observed_instance_digest:
        return OperationDecision("STALE", reason="instance identityが承認時から変化した")
    return OperationDecision("DONE", action="worktree.resume", remaining_steps=RESUME_STEPS)


@dataclasses.dataclass(frozen=True)
class RootCapabilities:
    advisory_lock: bool
    atomic_replace_dir_fsync: bool
    stable_identity: bool
    mtime_granularity: bool

    @property
    def supports_lifecycle(self) -> bool:
        return all(dataclasses.astuple(self))


def operation_support(operation: str, capabilities: RootCapabilities) -> OperationDecision:
    """finish/discard不能rootではcreate/resumeも対称に公開しない。"""
    if operation == "worktree.audit":
        return OperationDecision("DONE", action=operation)
    if operation in {"worktree.create", "worktree.resume"} and not capabilities.supports_lifecycle:
        return OperationDecision("UNSUPPORTED", reason="finish/discardに必要なfilesystem capability不足")
    return OperationDecision("DONE", action=operation)
