"""FLW-NFR-014 / FLW-TSK-110 recovery audit and reconcile tests."""

from __future__ import annotations

import ast
import dataclasses
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "plugins" / "bitz-flow" / "skills" / "flow-core"
sys.path.insert(0, str(SKILL / "scripts"))

from flowlib import worktree_contract as C  # noqa: E402
from flowlib import worktree_promotion as P  # noqa: E402
from flowlib import worktree_recovery as RC  # noqa: E402
from flowlib import worktree_runtime as R  # noqa: E402
from flowlib import worktree_transaction as T  # noqa: E402

DIGEST = "sha256:" + "a" * 64
BUNDLE = "sha256:" + "b" * 64
REPOSITORY = "sha256:" + "c" * 64


def snapshot(suffix="0"):
    return R.RepositorySnapshot(
        suffix * 40,
        "sha256:" + suffix * 64,
        "sha256:" + suffix * 64,
        "sha256:" + suffix * 64,
    )


def authority(tmp_path):
    return T.TargetTransaction(tmp_path / "authority", target_collision_key="target-1")


def interrupted(tmp_path, observed, *, mutating=False):
    tx = authority(tmp_path)
    lease = tx.acquire(operation_id=DIGEST, nonce="mutation-nonce")
    tx.prepare_intent(
        lease,
        planned_effects_digest=BUNDLE,
        precondition_digest=observed.digest,
    )
    if mutating:
        tx.mark_mutating(lease)
    tx.release(lease)
    P.register_active_operation(
        tmp_path / "common", operation_id=DIGEST, bundle_digest=BUNDLE
    )
    return tx


def plan_for(report, *, decision=None, nonce="reconcile-nonce"):
    return RC.build_reconcile_plan(
        audit_report=report,
        decision=decision or report.classification,
        repository_identity=REPOSITORY,
        expires_at=(datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
        nonce=nonce,
        bundle_digest=BUNDLE,
    )


def run_reconcile(tmp_path, tx, plan, observed):
    return RC.reconcile(
        transaction=tx,
        plan=plan,
        confirm=plan.operation_id,
        now=datetime.now(timezone.utc),
        nonce_unused=True,
        observe=lambda: observed,
        common_dir=str(tmp_path / "common"),
    )


def test_audit_proves_pre_mutation_incomplete_without_writes(tmp_path):
    observed = snapshot()
    tx = interrupted(tmp_path, observed)
    before = sorted(str(path.relative_to(tmp_path)) for path in tmp_path.rglob("*"))
    report = RC.audit(tx, operation_id=DIGEST, observed_snapshot=observed)
    after = sorted(str(path.relative_to(tmp_path)) for path in tmp_path.rglob("*"))
    assert report.classification == RC.CONFIRMED_INCOMPLETE
    assert report.transaction_state == "INTENT_DURABLE"
    assert before == after


def test_mutating_state_is_never_inferred_complete(tmp_path):
    observed = snapshot()
    tx = interrupted(tmp_path, observed, mutating=True)
    report = RC.audit(tx, operation_id=DIGEST, observed_snapshot=observed)
    assert report.classification == RC.INDETERMINATE


def test_terminal_receipt_and_matching_snapshot_are_confirmed_complete(tmp_path):
    observed = snapshot()
    tx = authority(tmp_path)
    lease = tx.acquire(operation_id=DIGEST, nonce="one")
    tx.prepare_intent(lease, planned_effects_digest=BUNDLE,
                      precondition_digest=snapshot("1").digest)
    tx.mark_mutating(lease)
    tx.publish_result(
        lease, terminal_state="DONE", postcondition_digest=observed.digest
    )
    tx.release(lease)
    report = RC.audit(tx, operation_id=DIGEST, observed_snapshot=observed)
    assert report.classification == RC.CONFIRMED_COMPLETE
    assert report.terminal_receipt_digest


def test_terminal_snapshot_mismatch_is_indeterminate(tmp_path):
    observed = snapshot()
    tx = authority(tmp_path)
    lease = tx.acquire(operation_id=DIGEST, nonce="one")
    tx.prepare_intent(lease, planned_effects_digest=BUNDLE,
                      precondition_digest=observed.digest)
    tx.mark_mutating(lease)
    tx.publish_result(
        lease, terminal_state="DONE", postcondition_digest=snapshot("1").digest
    )
    tx.release(lease)
    assert RC.audit(
        tx, operation_id=DIGEST, observed_snapshot=observed
    ).classification == RC.INDETERMINATE


def test_corrupt_journal_preserves_longest_prefix_and_is_indeterminate(tmp_path):
    observed = snapshot()
    tx = interrupted(tmp_path, observed)
    event_dir = tx.root / "events" / DIGEST[7:]
    record = json.loads(sorted(event_dir.glob("*.json"))[0].read_text())
    (event_dir / ("9" * 20 + "-branch.json")).write_text(json.dumps(record))
    report = RC.audit(tx, operation_id=DIGEST, observed_snapshot=observed)
    assert report.classification == RC.INDETERMINATE
    assert report.valid_event_count >= 1
    assert report.problems


def test_reconcile_requires_exact_new_plan_confirmation(tmp_path):
    observed = snapshot()
    tx = interrupted(tmp_path, observed)
    plan = plan_for(RC.audit(tx, operation_id=DIGEST, observed_snapshot=observed))
    with pytest.raises(RC.RecoveryError) as caught:
        RC.reconcile(
            transaction=tx, plan=plan, confirm=DIGEST,
            now=datetime.now(timezone.utc), nonce_unused=True,
            observe=lambda: observed, common_dir=str(tmp_path / "common"),
        )
    assert caught.value.code == "STALE"
    assert not tx.inspect(DIGEST).closures


def test_reconcile_appends_only_closure_then_releases_marker(tmp_path):
    observed = snapshot()
    tx = interrupted(tmp_path, observed)
    report = RC.audit(tx, operation_id=DIGEST, observed_snapshot=observed)
    plan = plan_for(report)
    event_count = len(tx.inspect(DIGEST).events)
    result = run_reconcile(tmp_path, tx, plan, observed)
    chain = tx.inspect(DIGEST)
    assert result.marker_released
    assert len(chain.events) == event_count
    assert len(chain.closures) == 1
    assert not (tmp_path / "common" / P.PROMOTION_RELATIVE_PATH /
                "active" / f"{DIGEST[7:]}.json").exists()


def test_same_decision_retry_is_idempotent(tmp_path):
    observed = snapshot()
    tx = interrupted(tmp_path, observed)
    plan = plan_for(RC.audit(tx, operation_id=DIGEST, observed_snapshot=observed))
    first = run_reconcile(tmp_path, tx, plan, observed)
    second = run_reconcile(tmp_path, tx, plan, observed)
    assert second.closure_digest == first.closure_digest
    assert len(tx.inspect(DIGEST).closures) == 1


def test_crash_after_closure_before_marker_release_converges_on_retry(tmp_path, monkeypatch):
    observed = snapshot()
    tx = interrupted(tmp_path, observed)
    plan = plan_for(RC.audit(tx, operation_id=DIGEST, observed_snapshot=observed))
    actual_release = P.release_reconciled_operation
    calls = 0

    def crash_once(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise P.PromotionError("INDETERMINATE", "injected crash")
        return actual_release(*args, **kwargs)

    monkeypatch.setattr(P, "release_reconciled_operation", crash_once)
    with pytest.raises(RC.RecoveryError):
        run_reconcile(tmp_path, tx, plan, observed)
    assert len(tx.inspect(DIGEST).closures) == 1
    assert run_reconcile(tmp_path, tx, plan, observed).marker_released
    assert len(tx.inspect(DIGEST).closures) == 1


def test_retry_finishes_marker_unlink_after_closed_record_was_durable(tmp_path):
    observed = snapshot()
    tx = interrupted(tmp_path, observed)
    plan = plan_for(RC.audit(tx, operation_id=DIGEST, observed_snapshot=observed))
    lease = tx.acquire_reconcile(
        operation_id=DIGEST,
        expected_fencing_token=plan.audit.fencing_token,
        expected_head_digest=plan.audit.journal_head_digest,
    )
    closure = tx.reconcile(lease, decision_digest=plan.decision_digest)
    tx.release(lease)
    namespace = tmp_path / "common" / P.PROMOTION_RELATIVE_PATH
    P._atomic_json(namespace / "closed" / f"{DIGEST[7:]}.json", {
        "contract_version": C.CONTRACT_VERSION,
        "operation_id": DIGEST,
        "bundle_digest": BUNDLE,
        "closure_digest": closure,
    })
    assert run_reconcile(tmp_path, tx, plan, observed).marker_released
    assert not (namespace / "active" / f"{DIGEST[7:]}.json").exists()


def test_target_lock_is_released_before_marker_operation(tmp_path, monkeypatch):
    observed = snapshot()
    tx = interrupted(tmp_path, observed)
    plan = plan_for(RC.audit(tx, operation_id=DIGEST, observed_snapshot=observed))
    actual_release = P.release_reconciled_operation
    observed_unlocked = False

    def assert_unlocked(*args, **kwargs):
        nonlocal observed_unlocked
        contender = authority(tmp_path)
        lease = contender.acquire_reconcile(
            operation_id=DIGEST,
            expected_fencing_token=plan.audit.fencing_token,
            expected_head_digest=plan.audit.journal_head_digest,
        )
        contender.release(lease)
        observed_unlocked = True
        return actual_release(*args, **kwargs)

    monkeypatch.setattr(P, "release_reconciled_operation", assert_unlocked)
    run_reconcile(tmp_path, tx, plan, observed)
    assert observed_unlocked


def test_different_decision_cannot_replace_closure(tmp_path):
    observed = snapshot()
    tx = interrupted(tmp_path, observed, mutating=True)
    report = RC.audit(tx, operation_id=DIGEST, observed_snapshot=observed)
    first = plan_for(report, decision=RC.QUARANTINE)
    run_reconcile(tmp_path, tx, first, observed)
    second = plan_for(report, decision=RC.QUARANTINE, nonce="another")
    with pytest.raises(RC.RecoveryError) as caught:
        run_reconcile(tmp_path, tx, second, observed)
    assert caught.value.code == "STALE"
    assert len(tx.inspect(DIGEST).closures) == 1


def test_repository_state_swap_after_plan_is_stale(tmp_path):
    observed = snapshot()
    tx = interrupted(tmp_path, observed)
    plan = plan_for(RC.audit(tx, operation_id=DIGEST, observed_snapshot=observed))
    with pytest.raises(RC.RecoveryError) as caught:
        run_reconcile(tmp_path, tx, plan, snapshot("1"))
    assert caught.value.code == "STALE"
    assert not tx.inspect(DIGEST).closures


def test_approval_expiry_is_rechecked_after_target_lock(tmp_path):
    observed = snapshot()
    tx = interrupted(tmp_path, observed)
    plan = plan_for(RC.audit(tx, operation_id=DIGEST, observed_snapshot=observed))
    with pytest.raises(RC.RecoveryError) as caught:
        RC.reconcile(
            transaction=tx, plan=plan, confirm=plan.operation_id,
            now=datetime.now(timezone.utc), nonce_unused=True,
            observe=lambda: observed, common_dir=str(tmp_path / "common"),
            clock=lambda: datetime.now(timezone.utc) + timedelta(days=1),
        )
    assert caught.value.code == "STALE"
    assert not tx.inspect(DIGEST).closures


def test_newer_fencing_token_blocks_old_operation_reconcile(tmp_path):
    observed = snapshot()
    tx = interrupted(tmp_path, observed)
    report = RC.audit(tx, operation_id=DIGEST, observed_snapshot=observed)
    newer = authority(tmp_path)
    newer_id = "sha256:" + "d" * 64
    newer_lease = newer.acquire(operation_id=newer_id, nonce="newer")
    newer.release(newer_lease)
    plan = plan_for(report)
    with pytest.raises(RC.RecoveryError) as caught:
        run_reconcile(tmp_path, tx, plan, observed)
    assert caught.value.code == "STALE"
    assert not tx.inspect(DIGEST).closures


def test_journal_head_or_token_swap_is_stale_or_indeterminate(tmp_path):
    observed = snapshot()
    tx = interrupted(tmp_path, observed)
    report = RC.audit(tx, operation_id=DIGEST, observed_snapshot=observed)
    bad = dataclasses.replace(report, fencing_token="999")
    plan = plan_for(bad)
    with pytest.raises(RC.RecoveryError) as caught:
        run_reconcile(tmp_path, tx, plan, observed)
    assert caught.value.code == "STALE"


def test_indeterminate_audit_only_accepts_quarantine_plan(tmp_path):
    observed = snapshot()
    tx = interrupted(tmp_path, observed, mutating=True)
    report = RC.audit(tx, operation_id=DIGEST, observed_snapshot=observed)
    with pytest.raises(C.ContractError):
        plan_for(report, decision=RC.CONFIRMED_COMPLETE)
    assert plan_for(report, decision=RC.QUARANTINE)


def test_recovery_module_has_no_git_or_subprocess_capability():
    source = (SKILL / "scripts" / "flowlib" / "worktree_recovery.py").read_text()
    tree = ast.parse(source)
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert "subprocess" not in imported
    assert not any(name.startswith("git") for name in imported)
