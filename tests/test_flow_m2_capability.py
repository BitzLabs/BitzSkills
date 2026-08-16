"""M2-2 承認 capability fault fixtures（FLW-NFR-007 / FLW-CON-005 / 006）。"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / "plugins" / "bitz-flow" / "skills" / "flow-core"
sys.path.insert(0, str(SKILL / "scripts"))

from flowlib import worktree_capability as C  # noqa: E402


NOW = datetime(2026, 8, 14, tzinfo=timezone.utc)


def _context(**overrides):
    values = {
        "worktree_dir_guard_key": "worktree-dir:abc",
        "worktree_registry_guard_key": "worktree-registry:def",
        "parent_dir_identity": "dev:1:ino:2",
        "nonexistence_digest": "sha256:" + "1" * 64,
        "instance_identity_digest": None,
        "worktree_root_canonical": "/approved/root",
        "case_sensitivity": True,
        "operation_id": "worktree.create",
    }
    values.update(overrides)
    return C.WorktreeApprovalContext(**values)


def _capability(**overrides):
    ctx = _context()
    values = {
        **ctx.__dict__,
        "expires_at": NOW + timedelta(minutes=10),
        "nonce": "nonce-1",
        "algorithm": "Ed25519",
        "key_id": "owner-key-1",
        "signature": "signed",
    }
    values.update(overrides)
    return C.WorktreeApprovalCapability(**values)


def _authorize(capability=None, context=None, **overrides):
    values = {
        "context": context or _context(),
        "now": NOW,
        "trusted_key_ids": ("owner-key-1",),
        "nonce_state": C.NONCE_UNUSED,
        "verify_signature": lambda payload, signature, key_id: bool(payload and signature and key_id),
    }
    values.update(overrides)
    return C.authorize_worktree_write(capability or _capability(), **values)


def test_M2_FLT_010_nonce_reuse_target_transfer_and_expiry_are_rejected():
    assert _authorize(nonce_state=C.NONCE_USED_DONE).code == C.CODE_BLOCKED
    assert _authorize(context=_context(worktree_dir_guard_key="worktree-dir:other")).code == C.CODE_BLOCKED
    assert _authorize(now=NOW + timedelta(hours=1)).code == C.CODE_BLOCKED


def test_M2_FLT_010_nonce_consumption_is_linearizable():
    ledger = C.NonceLedger()
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: ledger.begin("nonce-1"), range(32)))
    assert results.count(True) == 1
    assert ledger.state("nonce-1") == C.NONCE_USED_PENDING
    assert ledger.finish("nonce-1")
    assert ledger.state("nonce-1") == C.NONCE_USED_DONE
    assert not ledger.begin("nonce-1")


def test_M2_FLT_011_parent_symlink_replacement_is_stale():
    failure = _authorize(context=_context(parent_dir_identity="dev:1:ino:999"))
    assert (failure.code, "parent directory" in failure.reason) == (C.CODE_STALE, True)


def test_M2_FLT_012_prior_path_occupation_is_stale():
    failure = _authorize(context=_context(nonexistence_digest="sha256:" + "2" * 64))
    assert (failure.code, "nonexistence" in failure.reason) == (C.CODE_STALE, True)


def test_M2_FLT_013_external_directory_removal_is_orphaned_and_quarantined():
    """外部削除を検出し quarantine へ接続すること。

    `worktree_state` は `FLW-DSN-016` §2 の閉集合から選ぶ。実体が消えたのだから
    `ABSENT` である。従来は `ORPHAN` を返していたが、`ORPHAN` は
    `branch_audit_state` の値であり `worktree_state` の閉集合には無い
    （`FLW-REV-018:SYN-005`）。§7 が使う「ORPHAN」は起因の呼称であって field 値ではない。
    """
    from flowlib import worktree as W

    finding = C.audit_external_binding_change(
        C.WorktreeBindingObservation(False, True, False)
    )
    assert (finding.worktree_state, finding.result_code, finding.quarantine_required) == (
        "ABSENT",
        C.CODE_BLOCKED,
        True,
    )
    assert finding.worktree_state in W.WORKTREE_STATES, "閉集合の外の値を作らないこと"


def test_M2_FLT_014_external_registry_tampering_is_orphaned_and_quarantined():
    finding = C.audit_external_binding_change(
        C.WorktreeBindingObservation(True, True, False)
    )
    assert finding is not None and finding.quarantine_required
    assert C.audit_external_binding_change(C.WorktreeBindingObservation(True, True, True)) is None


def test_M2_FLT_015_missing_or_invalid_capability_blocks_before_write():
    missing = C.authorize_worktree_write(
        None,
        context=_context(),
        now=NOW,
        trusted_key_ids=("owner-key-1",),
        nonce_state=C.NONCE_UNUSED,
        verify_signature=lambda payload, signature, key_id: True,
    )
    invalid = _authorize(verify_signature=lambda payload, signature, key_id: False)
    assert missing.code == invalid.code == C.CODE_BLOCKED


def test_instance_operations_require_instance_digest_not_nonexistence_digest():
    context = _context(
        operation_id="worktree.finish",
        nonexistence_digest=None,
        instance_identity_digest="sha256:" + "3" * 64,
    )
    capability = _capability(
        operation_id="worktree.finish",
        nonexistence_digest=None,
        instance_identity_digest="sha256:" + "3" * 64,
    )
    assert _authorize(capability, context=context) is None
