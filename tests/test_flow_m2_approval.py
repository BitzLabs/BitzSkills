"""FLW-NFR-014 / FLW-TSK-107 plan-digest承認。"""

from __future__ import annotations

import inspect
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "plugins" / "bitz-flow" / "skills" / "flow-core"
sys.path.insert(0, str(SKILL / "scripts"))

from flowlib import worktree_approval as A  # noqa: E402
from flowlib.worktree_contract import ContractError  # noqa: E402

NOW = datetime(2026, 8, 22, 3, 0, tzinfo=timezone.utc)
DIGEST = "sha256:" + "a" * 64


def _mapping(**changes):
    value = {
        "contract_version": 2,
        "operation": "worktree.create",
        "repository_identity": DIGEST,
        "target_collision_key": "linux:directory:target",
        "head_oid": "b" * 40,
        "index_digest": DIGEST,
        "worktree_digest": "sha256:" + "c" * 64,
        "planned_effects": ["create-branch", "create-worktree"],
        "expires_at": (NOW + timedelta(minutes=5)).isoformat(),
        "nonce": "nonce-from-secure-source",
    }
    value.update(changes)
    return value


def test_approval_context_is_closed_and_mapping_order_does_not_change_operation_id():
    first = A.approval_context_from_mapping(_mapping())
    second = A.approval_context_from_mapping(dict(reversed(list(_mapping().items()))))
    assert first.operation_id == second.operation_id
    with pytest.raises(ContractError, match="unknown"):
        A.approval_context_from_mapping({**_mapping(), "unknown": True})


@pytest.mark.parametrize("field,replacement", [
    ("operation", "worktree.resume"), ("repository_identity", "sha256:" + "d" * 64),
    ("target_collision_key", "other"), ("head_oid", "e" * 40),
    ("index_digest", "sha256:" + "e" * 64), ("worktree_digest", "sha256:" + "f" * 64),
    ("planned_effects", ["create-worktree", "create-branch"]),
    ("expires_at", (NOW + timedelta(minutes=6)).isoformat()), ("nonce", "other"),
])
def test_every_approval_field_is_bound_to_operation_id(field, replacement):
    baseline = A.approval_context_from_mapping(_mapping())
    changed = A.approval_context_from_mapping(_mapping(**{field: replacement}))
    assert changed.operation_id != baseline.operation_id


@pytest.mark.parametrize("changes", [
    {"expires_at": "2026-08-22T03:05:00"}, {"nonce": ""},
    {"planned_effects": ["same", "same"]}, {"head_oid": "ABC"},
])
def test_invalid_expiry_nonce_effects_and_oid_are_rejected(changes):
    with pytest.raises(ContractError):
        A.approval_context_from_mapping(_mapping(**changes))


def test_matching_confirmation_unused_nonce_and_fresh_context_is_allowed():
    context = A.approval_context_from_mapping(_mapping())
    decision = A.authorize_plan_digest(context, confirm=context.operation_id, now=NOW, nonce_unused=True, rederived_context=context)
    assert (decision.allowed, decision.reason_code) == (True, None)


@pytest.mark.parametrize("kwargs,reason", [
    ({"confirm": "sha256:" + "0" * 64}, "CONFIRMATION_MISMATCH"),
    ({"now": NOW + timedelta(minutes=5)}, "APPROVAL_EXPIRED"),
    ({"nonce_unused": False}, "NONCE_REUSED"),
    ({"unsupported_approval_input": True}, A.UNSUPPORTED_APPROVAL_MODE),
])
def test_rejection_reasons_are_closed_and_do_not_mutate(kwargs, reason):
    context = A.approval_context_from_mapping(_mapping())
    arguments = {"confirm": context.operation_id, "now": NOW, "nonce_unused": True, "rederived_context": context}
    arguments.update(kwargs)
    decision = A.authorize_plan_digest(context, **arguments)
    assert (decision.allowed, decision.reason_code) == (False, reason)


def test_rederived_context_change_is_stale():
    context = A.approval_context_from_mapping(_mapping())
    changed = A.approval_context_from_mapping(_mapping(head_oid="e" * 40))
    decision = A.authorize_plan_digest(context, confirm=context.operation_id, now=NOW, nonce_unused=True, rederived_context=changed)
    assert (decision.allowed, decision.reason_code) == (False, "CONTEXT_STALE")


@pytest.mark.parametrize("kwargs", [
    {"declaration_present": True}, {"declaration_observable": False},
    {"capability_file_present": True}, {"trusted_registry_configured": True},
])
def test_signed_capability_inputs_are_unsupported_without_fallback(kwargs):
    assert A.has_unsupported_approval_input(**kwargs)


def test_approval_module_is_pure_and_has_no_mutation_callback_surface():
    source = inspect.getsource(A)
    assert "subprocess" not in source
    assert "import os" not in source
    assert "callback" not in inspect.signature(A.authorize_plan_digest).parameters
