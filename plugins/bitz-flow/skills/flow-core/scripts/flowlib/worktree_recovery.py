"""Read-only audit and explicitly confirmed M2 reconciliation (FLW-TSK-110).

This module never launches Git.  Callers supply RepositoryObserver snapshots; the
only durable changes are a TargetTransaction closure and, after its lock is
released, an idempotent promotion-marker closure.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from . import worktree_approval as A
from . import worktree_promotion as P
from . import worktree_transaction as T
from .worktree_contract import (
    CONTRACT_VERSION,
    ContractError,
    canonical_json_bytes,
    sha256_digest,
    validate_digest,
)
from .worktree_runtime import RepositorySnapshot

CONFIRMED_COMPLETE = "confirmed-complete"
CONFIRMED_INCOMPLETE = "confirmed-incomplete"
INDETERMINATE = "indeterminate"
QUARANTINE = "quarantine"


@dataclass(frozen=True)
class RecoveryAudit:
    operation_id: str
    target_collision_key: str
    classification: str
    transaction_state: str
    observed_snapshot: RepositorySnapshot
    journal_head_digest: str | None
    fencing_token: str | None
    valid_event_count: int
    terminal_receipt_digest: str | None
    closure_digest: str | None
    problems: tuple[str, ...]

    @property
    def digest(self) -> str:
        value = dataclasses.asdict(self)
        value["problems"] = list(self.problems)
        return sha256_digest(canonical_json_bytes(value))


@dataclass(frozen=True)
class ReconcilePlan:
    original_operation_id: str
    decision: str
    audit: RecoveryAudit
    context: A.ApprovalContext
    bundle_digest: str

    @property
    def operation_id(self) -> str:
        return self.context.operation_id

    @property
    def decision_digest(self) -> str:
        return sha256_digest(canonical_json_bytes({
            "contract_version": CONTRACT_VERSION,
            "reconcile_operation_id": self.operation_id,
            "original_operation_id": self.original_operation_id,
            "audit_digest": self.audit.digest,
            "decision": self.decision,
            "bundle_digest": self.bundle_digest,
        }))


@dataclass(frozen=True)
class ReconcileResult:
    operation_id: str
    closure_digest: str
    audit_digest: str
    marker_released: bool


class RecoveryError(RuntimeError):
    def __init__(self, code: str, cause: str):
        super().__init__(cause)
        self.code = code
        self.cause = cause


def audit(transaction: T.TargetTransaction, *, operation_id: str,
          observed_snapshot: RepositorySnapshot) -> RecoveryAudit:
    """Classify one operation without acquiring locks or writing durable state."""
    validate_digest(operation_id)
    report = transaction.inspect(operation_id)
    token = (
        str(report.events[0]["event"]["fencing_token"])
        if report.events else None
    )
    terminal = [item for item in report.receipts if item["receipt_state"] == "TERMINAL"]
    terminal_digest = (
        sha256_digest(canonical_json_bytes(terminal[0])) if len(terminal) == 1 else None
    )
    closure_digest = (
        sha256_digest(canonical_json_bytes(report.closures[0]))
        if len(report.closures) == 1 else None
    )
    classification = INDETERMINATE
    if report.healthy and report.events:
        if report.state == "LOCKED":
            classification = CONFIRMED_INCOMPLETE
        elif report.state == "INTENT_DURABLE":
            precondition = report.events[-1]["intent"]["precondition_digest"]
            if precondition == observed_snapshot.digest:
                classification = CONFIRMED_INCOMPLETE
        elif report.state in {"RESULT_DURABLE", "DONE", "QUARANTINED"} and terminal_digest:
            result_events = [
                item for item in report.events
                if item["event"]["state"] == "RESULT_DURABLE"
            ]
            if (
                len(result_events) == 1
                and result_events[0]["result"]["postcondition_digest"]
                == observed_snapshot.digest
            ):
                classification = CONFIRMED_COMPLETE
    return RecoveryAudit(
        operation_id,
        transaction.target_collision_key,
        classification,
        report.state,
        observed_snapshot,
        report.head_digest,
        token,
        len(report.events),
        terminal_digest,
        closure_digest,
        report.problems,
    )


def build_reconcile_plan(*, audit_report: RecoveryAudit, decision: str,
                         repository_identity: str, expires_at: str, nonce: str,
                         bundle_digest: str) -> ReconcilePlan:
    """Bind a fresh plan-digest approval to an immutable audit result."""
    validate_digest(repository_identity)
    validate_digest(bundle_digest)
    if decision not in {CONFIRMED_COMPLETE, CONFIRMED_INCOMPLETE, QUARANTINE}:
        raise ContractError("unknown recovery decision")
    if audit_report.classification == INDETERMINATE:
        if decision != QUARANTINE:
            raise ContractError("indeterminate audit may only be quarantined")
    elif decision != audit_report.classification:
        raise ContractError("decision contradicts the recovery audit")
    snapshot = audit_report.observed_snapshot
    effects = (
        f"close-operation:{audit_report.operation_id}",
        f"audit:{audit_report.digest}",
        f"decision:{decision}",
        f"worktree-list:{snapshot.worktree_list_digest}",
        f"bundle:{bundle_digest}",
    )
    context = A.ApprovalContext(
        CONTRACT_VERSION,
        "reconcile",
        repository_identity,
        audit_report.target_collision_key,
        snapshot.head_oid,
        snapshot.index_digest,
        snapshot.worktree_digest,
        effects,
        expires_at,
        nonce,
    )
    # Apply the same closed validation used for externally supplied mappings.
    A.approval_context_from_mapping(context.as_mapping())
    return ReconcilePlan(
        audit_report.operation_id, decision, audit_report, context, bundle_digest
    )


def reconcile(*, transaction: T.TargetTransaction, plan: ReconcilePlan,
              confirm: str, now: datetime, nonce_unused: bool,
              observe: Callable[[], RepositorySnapshot], common_dir: str,
              timeout_seconds: float = 0.0,
              clock: Callable[[], datetime] | None = None) -> ReconcileResult:
    """Append a closure under the target lock, then release its active marker."""
    authorization = A.authorize_plan_digest(
        plan.context,
        confirm=confirm,
        now=now,
        nonce_unused=nonce_unused,
        rederived_context=plan.context,
    )
    if not authorization.allowed:
        raise RecoveryError("STALE", authorization.reason_code or "approval rejected")
    expected = plan.audit
    if expected.journal_head_digest is None or expected.fencing_token is None:
        raise RecoveryError("INDETERMINATE", "audit has no recoverable journal head")
    try:
        lease = transaction.acquire_reconcile(
            operation_id=plan.original_operation_id,
            expected_fencing_token=expected.fencing_token,
            expected_head_digest=expected.journal_head_digest,
            timeout_seconds=timeout_seconds,
        )
    except T.TransactionError as exc:
        raise RecoveryError(exc.code, exc.cause) from exc
    try:
        recheck = A.authorize_plan_digest(
            plan.context,
            confirm=confirm,
            now=clock() if clock else datetime.now(timezone.utc),
            nonce_unused=nonce_unused,
            rederived_context=plan.context,
        )
        if not recheck.allowed:
            raise RecoveryError("STALE", recheck.reason_code or "approval changed")
        current = audit(
            transaction,
            operation_id=plan.original_operation_id,
            observed_snapshot=observe(),
        )
        comparable = dataclasses.replace(
            current, closure_digest=expected.closure_digest
        )
        if comparable.digest != expected.digest:
            raise RecoveryError("STALE", "repository, journal, receipt, or token changed")
        try:
            closure_digest = transaction.reconcile(
                lease, decision_digest=plan.decision_digest
            )
        except T.TransactionError as exc:
            if exc.cause == "conflicting closure decision":
                raise RecoveryError("STALE", exc.cause) from exc
            raise RecoveryError(exc.code, exc.cause) from exc
    finally:
        transaction.release(lease)

    # Promotion lock is deliberately acquired only after the target lock is released.
    try:
        P.release_reconciled_operation(
            common_dir,
            operation_id=plan.original_operation_id,
            bundle_digest=plan.bundle_digest,
            closure_digest=closure_digest,
        )
    except P.PromotionError as exc:
        raise RecoveryError(exc.code, exc.cause) from exc
    return ReconcileResult(
        plan.operation_id, closure_digest, expected.digest, True
    )
