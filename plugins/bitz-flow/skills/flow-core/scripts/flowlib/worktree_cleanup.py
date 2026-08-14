"""M2 worktree finish/discard・retention・quarantine安全核。"""

from __future__ import annotations

import dataclasses
from datetime import datetime
from typing import Iterable


FINISH_STEPS = (
    "verify-pr-merge", "verify-target-oid", "verify-reachability", "create-retention-ref",
    "remove-registry-entry", "remove-worktree-dir", "delete-local-branch",
)
DISCARD_STEPS = (
    "freeze-manifest", "verify-manifest-scope", "create-retention-ref",
    "remove-registry-entry", "remove-worktree-dir", "delete-local-branch",
)
MUTATING_STEPS = frozenset(
    {"create-retention-ref", "remove-registry-entry", "remove-worktree-dir", "delete-local-branch"}
)


@dataclasses.dataclass(frozen=True)
class CleanupDecision:
    code: str
    completed_steps: tuple[str, ...] = ()
    remaining_steps: tuple[str, ...] = ()
    recovery_class: str = "human-stop"
    reason: str = ""


def reconcile_steps(operation: str, completed: tuple[str, ...]) -> CleanupDecision:
    steps = FINISH_STEPS if operation == "worktree.finish" else DISCARD_STEPS
    if completed != steps[: len(completed)]:
        return CleanupDecision("INDETERMINATE", reason="receipt chainがstep列のprefixでない")
    if completed == steps:
        return CleanupDecision("DONE", completed)
    return CleanupDecision(
        "PARTIAL", completed, steps[len(completed) :], "reconcile-only",
        "残stepは新plan・新承認・新operation IDまで自動実行しない",
    )


def finish_precondition(
    *, work_unit_state: str, worktree_state: str, branch_audit_state: str,
    backup_receipt: bool, merge_proof: bool, target_oid_matches: bool, reachable: bool,
) -> CleanupDecision:
    if work_unit_state != "AUDITED" or branch_audit_state != "MERGED_EXACT":
        return CleanupDecision("BLOCKED", reason="finishはAUDITEDかつMERGED_EXACTだけ許可")
    if worktree_state == "MISMATCH":
        return CleanupDecision("BLOCKED", reason="MISMATCH worktreeは削除しない")
    if worktree_state == "DIRTY" and not backup_receipt:
        return CleanupDecision("BLOCKED", reason="dirty worktreeの退避receiptが無い")
    if not (merge_proof and target_oid_matches and reachable):
        return CleanupDecision("BLOCKED", reason="merge・target OID・到達性証跡が不足")
    return CleanupDecision("DONE")


@dataclasses.dataclass(frozen=True)
class ManifestTarget:
    path: str
    kind: str
    identity: str


@dataclasses.dataclass(frozen=True)
class DiscardManifest:
    digest: str
    instance_digest: str
    targets: tuple[ManifestTarget, ...]
    root: str


def validate_discard(
    manifest: DiscardManifest, *, expected_digest: str, observed_instance_digest: str,
    backup_receipt: bool, dirty: bool, stable_identity_supported: bool,
) -> CleanupDecision:
    if manifest.digest != expected_digest:
        return CleanupDecision("STALE", recovery_class="replan-human", reason="manifest digest不一致")
    if manifest.instance_digest != observed_instance_digest:
        return CleanupDecision("STALE", recovery_class="replan-human", reason="instance identity不一致")
    if dirty and not backup_receipt:
        return CleanupDecision("BLOCKED", reason="dirty/untracked内容の退避が無い")
    if not stable_identity_supported:
        return CleanupDecision("UNSUPPORTED", reason="stable identity/dirfd相対削除を確保できない")
    root = manifest.root.rstrip("/") + "/"
    for target in manifest.targets:
        normalized = target.path.replace("\\", "/")
        if not normalized.startswith(root) or "/../" in normalized or not target.identity:
            return CleanupDecision("BLOCKED", reason="manifestにroot外またはidentity不明targetがある")
    return CleanupDecision("DONE")


def validate_next_graph(*, result_code: str, nodes: Iterable[str], human_approval: bool) -> bool:
    nodes = tuple(nodes)
    if "git.delete-remote-branch.apply" in nodes:
        return False
    if result_code in {"PARTIAL", "STALE", "INDETERMINATE"}:
        if any(node.endswith(".apply") for node in nodes) and not human_approval:
            return False
    return True


@dataclasses.dataclass(frozen=True)
class QuarantineEvidence:
    chain_valid: bool
    completed_steps: tuple[str, ...]
    instance_nonce_matches: bool
    mutation_receipts: int
    all_postconditions_match: bool


def classify_quarantine(evidence: QuarantineEvidence, *, total_mutating_steps: int) -> str:
    if not evidence.chain_valid or not evidence.instance_nonce_matches:
        return "worktree-unresolved"
    if evidence.mutation_receipts == 0:
        return "worktree-not-started"
    if evidence.mutation_receipts == total_mutating_steps and evidence.all_postconditions_match:
        return "worktree-confirmed-done"
    if evidence.completed_steps and evidence.all_postconditions_match:
        return "worktree-resumable"
    return "worktree-unresolved"


def may_reissue_guard(*, lease_expired: bool, owner_stopped: bool, children_stopped: bool,
                      os_lock_released: bool, postcondition_reconciled: bool) -> bool:
    return all((lease_expired, owner_stopped, children_stopped, os_lock_released, postcondition_reconciled))


def recovery_for(code: str, cause: str) -> CleanupDecision:
    known = {
        ("PARTIAL", "step-interrupted"): "reconcile-only",
        ("STALE", "snapshot-mismatch"): "replan-human",
        ("BLOCKED", "quarantined"): "human-stop",
    }
    recovery = known.get((code, cause))
    return CleanupDecision(
        code if recovery else "INDETERMINATE", recovery_class=recovery or "human-stop",
        reason="" if recovery else "未登録または矛盾するrecovery tuple",
    )


@dataclasses.dataclass(frozen=True)
class RetentionRef:
    name: str
    tip_oid: str
    created_at: datetime
    expires_at: datetime | None
    quarantine_resolved: bool


def create_retention_ref(work_id: str, timestamp: str, tip_oid: str,
                         existing_oid: str | None) -> CleanupDecision:
    if existing_oid is not None and existing_oid != tip_oid:
        return CleanupDecision("BLOCKED", reason="同名retention refが別OIDを指す")
    return CleanupDecision("DONE")


def may_prune_retention(ref: RetentionRef, *, now: datetime, explicit_approval: bool) -> bool:
    return bool(
        explicit_approval and ref.expires_at is not None and now >= ref.expires_at
        and ref.quarantine_resolved
    )
