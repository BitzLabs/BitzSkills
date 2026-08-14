"""M2 remote branch delete のCAS・ABA安全核（公開はM3までUNSUPPORTED）。"""

from __future__ import annotations

import dataclasses
from datetime import datetime
from typing import Iterable


@dataclasses.dataclass(frozen=True)
class DeleteDecision:
    code: str
    approval_required: bool = False
    aba_detection: str = ""
    reason: str = ""


@dataclasses.dataclass(frozen=True)
class DeletePlan:
    ref: str
    expected_oid: str
    observed_at: datetime
    reachable_from_default: bool
    branch_audit_state: str


def plan_delete(*, ref: str, expected_oid: str | None, observed_at: datetime,
                reachable_from_default: bool, branch_audit_state: str) -> tuple[DeletePlan | None, DeleteDecision]:
    if not expected_oid:
        return None, DeleteDecision("BLOCKED", reason="remote refが存在しない")
    if branch_audit_state == "REMOTE_ADVANCED":
        return None, DeleteDecision("BLOCKED", reason="REMOTE_ADVANCEDはplan生成禁止")
    if not reachable_from_default:
        return None, DeleteDecision("BLOCKED", reason="default branchから到達不能")
    return DeletePlan(ref, expected_oid, observed_at, True, branch_audit_state), DeleteDecision("DONE")


def validate_cas(*, plan: DeletePlan, current_oid: str | None,
                 protocol_supports_expected_oid: bool, conditional_request: bool) -> DeleteDecision:
    if not conditional_request:
        return DeleteDecision("BLOCKED", reason="条件なし削除は禁止")
    if not protocol_supports_expected_oid:
        return DeleteDecision("UNSUPPORTED", reason="server-side expected-OID CAS非対応")
    if current_oid != plan.expected_oid:
        return DeleteDecision("STALE", reason="remote refがplan後に変化した")
    return DeleteDecision("DONE")


def evaluate_activity(*, capability: str, updates: Iterable[dict], complete_pagination: bool,
                      response_consistent: bool) -> DeleteDecision:
    """Activity APIの肯定証拠だけを使い、更新不在を証明扱いしない。"""
    if capability == "UNAVAILABLE":
        return DeleteDecision("UNAVAILABLE", True, "unavailable", "一時障害でactivityを観測できない")
    if capability == "UNSUPPORTED":
        return DeleteDecision("UNSUPPORTED", True, "not-detected", "ABA不検出。API非提供または恒久scope不足")
    if capability != "AVAILABLE" or not complete_pagination or not response_consistent:
        return DeleteDecision("INDETERMINATE", True, "indeterminate", "部分page/cursor欠落/応答矛盾")
    updates = tuple(updates)
    if updates:
        return DeleteDecision("BLOCKED", False, "detected", f"plan後の更新を{len(updates)}件検出")
    return DeleteDecision("BLOCKED", True, "observed-none", "観測範囲では更新なし。不在証明ではない")


def qualification_allows_confirmation(*, stored_key: str, current_key: str,
                                      gate_status: str, expires_at: datetime, now: datetime) -> bool:
    return gate_status == "PASS" and stored_key == current_key and now < expires_at


def confirmation_scope(write_target: str) -> DeleteDecision:
    if write_target == "remote":
        return DeleteDecision("UNSUPPORTED", reason="remote-write confirmationはM3へ移送済み")
    if write_target == "local":
        return DeleteDecision("DONE")
    return DeleteDecision("INVALID_INPUT", reason="未知のwrite_target")
