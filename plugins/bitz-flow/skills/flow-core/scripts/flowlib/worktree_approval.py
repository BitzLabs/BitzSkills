"""M2 plan-digest ApprovalContextのpure判定（FLW-NFR-014）。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Mapping, Sequence

from .worktree_contract import (
    CONTRACT_VERSION,
    ContractError,
    canonical_json_bytes,
    sha256_digest,
    validate_digest,
)

UNSUPPORTED_APPROVAL_MODE = "UNSUPPORTED_APPROVAL_MODE"


def _parse_expiry(value: object) -> datetime:
    if not isinstance(value, str) or not value.endswith(("Z", "+00:00")):
        raise ContractError("expires_at must be an RFC3339 UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractError("expires_at must be an RFC3339 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ContractError("expires_at must include a timezone")
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class ApprovalContext:
    contract_version: int
    operation: str
    repository_identity: str
    target_collision_key: str
    head_oid: str
    index_digest: str
    worktree_digest: str
    planned_effects: tuple[str, ...]
    expires_at: str
    nonce: str

    def as_mapping(self) -> dict[str, object]:
        return {
            "contract_version": self.contract_version,
            "operation": self.operation,
            "repository_identity": self.repository_identity,
            "target_collision_key": self.target_collision_key,
            "head_oid": self.head_oid,
            "index_digest": self.index_digest,
            "worktree_digest": self.worktree_digest,
            "planned_effects": list(self.planned_effects),
            "expires_at": self.expires_at,
            "nonce": self.nonce,
        }

    @property
    def operation_id(self) -> str:
        return sha256_digest(canonical_json_bytes(self.as_mapping()))


def approval_context_from_mapping(value: Mapping[str, object]) -> ApprovalContext:
    fields = {
        "contract_version", "operation", "repository_identity", "target_collision_key", "head_oid",
        "index_digest", "worktree_digest", "planned_effects", "expires_at", "nonce",
    }
    if not isinstance(value, Mapping) or set(value) != fields:
        actual = set(value) if isinstance(value, Mapping) else set()
        raise ContractError(f"approval context fields mismatch: missing={sorted(fields-actual)}, unknown={sorted(actual-fields)}")
    if value["contract_version"] != CONTRACT_VERSION:
        raise ContractError("unsupported contract version")
    for field in ("operation", "target_collision_key", "nonce"):
        if not isinstance(value[field], str) or not value[field]:
            raise ContractError(f"{field} must be a non-empty string")
    for field in ("repository_identity", "index_digest", "worktree_digest"):
        validate_digest(value[field])
    head = value["head_oid"]
    if not isinstance(head, str) or len(head) not in {40, 64} or any(char not in "0123456789abcdef" for char in head):
        raise ContractError("head_oid must be 40 or 64 lowercase hex")
    effects = value["planned_effects"]
    if not isinstance(effects, list) or not effects or any(not isinstance(item, str) or not item for item in effects):
        raise ContractError("planned_effects must be a non-empty string array")
    if len(effects) != len(set(effects)):
        raise ContractError("planned_effects must not contain duplicates")
    _parse_expiry(value["expires_at"])
    return ApprovalContext(
        CONTRACT_VERSION,
        str(value["operation"]),
        str(value["repository_identity"]),
        str(value["target_collision_key"]),
        head,
        str(value["index_digest"]),
        str(value["worktree_digest"]),
        tuple(effects),
        str(value["expires_at"]),
        str(value["nonce"]),
    )


def has_unsupported_approval_input(
    *,
    declaration_present: bool = False,
    declaration_observable: bool = True,
    capability_file_present: bool = False,
    trusted_registry_configured: bool = False,
) -> bool:
    """旧署名入力の存在または存在確認不能を安全側へ分類する。"""
    return declaration_present or not declaration_observable or capability_file_present or trusted_registry_configured


@dataclass(frozen=True)
class ApprovalDecision:
    allowed: bool
    reason_code: str | None
    operation_id: str


def authorize_plan_digest(
    context: ApprovalContext,
    *,
    confirm: str,
    now: datetime,
    nonce_unused: bool,
    rederived_context: ApprovalContext,
    unsupported_approval_input: bool = False,
) -> ApprovalDecision:
    operation_id = context.operation_id
    if unsupported_approval_input:
        return ApprovalDecision(False, UNSUPPORTED_APPROVAL_MODE, operation_id)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ContractError("now must include a timezone")
    if confirm != operation_id:
        return ApprovalDecision(False, "CONFIRMATION_MISMATCH", operation_id)
    if now.astimezone(timezone.utc) >= _parse_expiry(context.expires_at):
        return ApprovalDecision(False, "APPROVAL_EXPIRED", operation_id)
    if not nonce_unused:
        return ApprovalDecision(False, "NONCE_REUSED", operation_id)
    if rederived_context.operation_id != operation_id:
        return ApprovalDecision(False, "CONTEXT_STALE", operation_id)
    return ApprovalDecision(True, None, operation_id)
