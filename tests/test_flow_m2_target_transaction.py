"""FLW-NFR-014 / FLW-TSK-108 TargetTransaction authority tests."""

from __future__ import annotations

import ast
import json
import multiprocessing
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "plugins" / "bitz-flow" / "skills" / "flow-core"
SCHEMAS = SKILL / "schemas" / "worktree-v2"
sys.path.insert(0, str(SKILL / "scripts"))

from flowlib import worktree_contract as C  # noqa: E402
from flowlib import worktree_transaction as T  # noqa: E402

DIGEST = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64


def _hold_process_lock(root, ready, release):
    tx = T.TargetTransaction(root, target_collision_key="target-1")
    lease = tx.acquire(operation_id=DIGEST, nonce="child")
    ready.set()
    release.wait(5)
    tx.release(lease)


def transaction(tmp_path, **kwargs):
    return T.TargetTransaction(tmp_path / "authority", target_collision_key="target-1", **kwargs)


def begin(tx, operation_id=DIGEST, nonce="nonce-1"):
    lease = tx.acquire(operation_id=operation_id, nonce=nonce)
    emergency = tx.prepare_intent(
        lease, planned_effects_digest=DIGEST, precondition_digest=DIGEST_B
    )
    return lease, emergency


def test_schemas_are_closed_and_use_decimal_string_fencing_tokens():
    for name in (
        "target-transaction-v2.schema.json", "operation-event-v2.schema.json",
        "target-lease-v2.schema.json", "mutation-receipt-v2.schema.json",
    ):
        schema = json.loads((SCHEMAS / name).read_text(encoding="utf-8"))
        assert schema["additionalProperties"] is False
        assert set(schema["required"]) == set(schema["properties"])
    lease = json.loads((SCHEMAS / "target-lease-v2.schema.json").read_text())
    assert lease["properties"]["fencing_token"]["type"] == "string"


@pytest.mark.parametrize("terminal", ["DONE", "QUARANTINED"])
def test_intent_and_emergency_precede_mutation_and_terminal_supersedes_once(tmp_path, terminal):
    tx = transaction(tmp_path)
    lease, emergency = begin(tx)
    assert tx.inspect(DIGEST).state == "INTENT_DURABLE"
    tx.mark_mutating(lease)
    receipt = tx.publish_result(
        lease, terminal_state=terminal, postcondition_digest=DIGEST
    )
    report = tx.inspect(DIGEST)
    assert report.healthy and report.state == terminal
    assert [item["event"]["state"] for item in report.events] == [
        "LOCKED", "INTENT_DURABLE", "MUTATING", "RESULT_DURABLE", terminal,
    ]
    terminal_receipt = [r for r in report.receipts if r["receipt_state"] == "TERMINAL"][0]
    assert terminal_receipt["supersedes_receipt_digest"] == emergency
    assert receipt == C.sha256_digest(C.canonical_json_bytes(terminal_receipt))
    tx.release(lease)


def test_lock_contention_allows_at_most_one_writer(tmp_path):
    first = transaction(tmp_path)
    lease = first.acquire(operation_id=DIGEST, nonce="one")
    second = transaction(tmp_path)
    with pytest.raises(T.TransactionError) as caught:
        second.acquire(operation_id=DIGEST_B, nonce="two", timeout_seconds=0.02)
    assert caught.value.code == "BLOCKED_LOCK_BUSY"
    first.release(lease)
    next_lease = second.acquire(operation_id=DIGEST_B, nonce="two")
    assert int(next_lease.fencing_token) > int(lease.fencing_token)
    second.release(next_lease)


@pytest.mark.skipif(sys.platform == "win32", reason="Windows runner fixtureで別途実行")
def test_separate_process_cannot_enter_same_target_authority(tmp_path):
    context = multiprocessing.get_context("spawn")
    ready, release = context.Event(), context.Event()
    root = tmp_path / "authority"
    child = context.Process(target=_hold_process_lock, args=(root, ready, release))
    child.start()
    assert ready.wait(5)
    contender = T.TargetTransaction(root, target_collision_key="target-1")
    with pytest.raises(T.TransactionError) as caught:
        contender.acquire(operation_id=DIGEST_B, nonce="parent", timeout_seconds=0.05)
    assert caught.value.code == "BLOCKED_LOCK_BUSY"
    release.set()
    child.join(5)
    assert child.exitcode == 0


def test_nonce_is_consumed_by_durable_intent_and_cannot_be_reused(tmp_path):
    tx = transaction(tmp_path)
    lease, _ = begin(tx, nonce="same")
    tx.release(lease)
    other = transaction(tmp_path)
    lease2 = other.acquire(operation_id=DIGEST_B, nonce="same")
    with pytest.raises(T.TransactionError) as caught:
        other.prepare_intent(
            lease2, planned_effects_digest=DIGEST, precondition_digest=DIGEST_B
        )
    assert caught.value.code == "STALE"
    other.release(lease2)


def test_counter_rollback_and_overflow_stop_indeterminate(tmp_path):
    tx = transaction(tmp_path)
    lease = tx.acquire(operation_id=DIGEST, nonce="one")
    tx.release(lease)
    counter = tx.root / "fencing-counter.json"
    counter.write_text('{"value":"0"}\n', encoding="utf-8")
    with pytest.raises(T.TransactionError, match="rolled back"):
        transaction(tmp_path).acquire(operation_id=DIGEST_B, nonce="two")
    counter.write_text(json.dumps({"value": str(C.MAX_UINT64)}) + "\n", encoding="utf-8")
    with pytest.raises(T.TransactionError, match="overflow"):
        transaction(tmp_path).acquire(operation_id=DIGEST_B, nonce="two")


def test_gap_branch_and_tamper_are_reported_without_repair(tmp_path):
    tx = transaction(tmp_path)
    lease, _ = begin(tx)
    event_dir = tx.root / "events" / DIGEST[7:]
    first = sorted(event_dir.glob("*.json"))[0]
    record = json.loads(first.read_text())
    branch = event_dir / ("9" * 20 + "-branch.json")
    branch.write_text(json.dumps(record), encoding="utf-8")
    report = tx.inspect(DIGEST)
    assert not report.healthy and report.state == "INDETERMINATE"
    with pytest.raises(T.TransactionError) as caught:
        tx.mark_mutating(lease)
    assert caught.value.code == "INDETERMINATE"
    tx.release(lease)


@pytest.mark.parametrize("crash_step", T.PUBLISH_STEPS)
def test_crash_during_intent_never_grants_mutation_without_emergency_receipt(tmp_path, crash_step):
    tx = transaction(tmp_path)
    lease = tx.acquire(operation_id=DIGEST, nonce="one")

    def crash(step, _path):
        if step == crash_step:
            raise RuntimeError("crash")

    tx._hook = crash
    with pytest.raises(RuntimeError, match="crash"):
        tx.prepare_intent(
            lease, planned_effects_digest=DIGEST, precondition_digest=DIGEST_B
        )
    tx._hook = None
    # `SI-FLW-087` 以降、intent と緊急 receipt は 1 回の atomic publish で確定する。
    # したがって不変条件は「INTENT_DURABLE へ到達しない」ではなく、
    # **「intent が確定したなら必ず有効な緊急 receipt が付いている」** である。
    report = tx.inspect(DIGEST)
    assert not report.problems, report.problems
    if report.state == "INTENT_DURABLE":
        emergency = [r for r in report.receipts if r["receipt_state"] == "INDETERMINATE"]
        assert len(emergency) == 1, "intent 確定なのに緊急 receipt が無い（回収不能状態）"
        tx.mark_mutating(lease)          # 緊急 receipt があるので前進できる
    else:
        assert report.state == "LOCKED"
        with pytest.raises(T.TransactionError):
            tx.mark_mutating(lease)
    tx.release(lease)


def test_reconcile_is_idempotent_and_conflicting_decision_is_rejected(tmp_path):
    tx = transaction(tmp_path)
    lease, _ = begin(tx)
    report = tx.inspect(DIGEST)
    token = lease.fencing_token
    tx.release(lease)
    recovery = transaction(tmp_path)
    lease = recovery.acquire_reconcile(
        operation_id=DIGEST,
        expected_fencing_token=token,
        expected_head_digest=report.head_digest,
    )
    first = recovery.reconcile(lease, decision_digest=DIGEST)
    assert recovery.reconcile(lease, decision_digest=DIGEST) == first
    with pytest.raises(T.TransactionError) as caught:
        recovery.reconcile(lease, decision_digest=DIGEST_B)
    assert caught.value.code == "INDETERMINATE"
    recovery.release(lease)


def test_operation_id_cannot_escape_authority_root_and_module_has_no_git_launcher(tmp_path):
    tx = transaction(tmp_path)
    with pytest.raises(C.ContractError):
        tx.acquire(operation_id="../../escape", nonce="one")
    source = (SKILL / "scripts" / "flowlib" / "worktree_transaction.py").read_text()
    tree = ast.parse(source)
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert "subprocess" not in imported
    assert not any(name.startswith("git") for name in imported)
