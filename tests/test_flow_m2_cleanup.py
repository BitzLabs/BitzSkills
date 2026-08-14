"""M2-5 finish/discard/retention/quarantine fixtures。"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / "plugins" / "bitz-flow" / "skills" / "flow-core"
sys.path.insert(0, str(SKILL / "scripts"))
from flowlib import worktree_cleanup as C  # noqa: E402


def _manifest(**overrides):
    values = {
        "digest": "manifest-1", "instance_digest": "instance-1", "root": "/root",
        "targets": (C.ManifestTarget("/root/wt/file", "file", "dev:1:ino:2"),),
    }
    values.update(overrides)
    return C.DiscardManifest(**values)


def _validate(manifest=None, **overrides):
    values = {"expected_digest": "manifest-1", "observed_instance_digest": "instance-1",
              "backup_receipt": True, "dirty": False, "stable_identity_supported": True}
    values.update(overrides)
    return C.validate_discard(manifest or _manifest(), **values)


def test_M2_FLT_024_finish_crash_boundaries_have_unique_prefix_and_remaining():
    for i in range(len(C.FINISH_STEPS)):
        d = C.reconcile_steps("worktree.finish", C.FINISH_STEPS[:i])
        assert d.code == "PARTIAL" and d.remaining_steps == C.FINISH_STEPS[i:]


def test_M2_FLT_025_finish_next_cannot_auto_apply_remote_delete():
    assert not C.validate_next_graph(result_code="DONE", nodes=("git.delete-remote-branch.apply",), human_approval=True)


def test_M2_FLT_026_insufficient_merge_evidence_blocks_finish():
    d = C.finish_precondition(work_unit_state="AUDITED", worktree_state="CLEAN",
        branch_audit_state="MERGED_EXACT", backup_receipt=False, merge_proof=False,
        target_oid_matches=True, reachable=True)
    assert d.code == "BLOCKED"


def test_M2_FLT_027_recreated_instance_is_stale():
    assert _validate(observed_instance_digest="instance-2").code == "STALE"


def test_M2_FLT_028_changed_manifest_is_stale():
    assert _validate(expected_digest="manifest-2").code == "STALE"


def test_M2_FLT_029_root_escape_and_symlink_alias_are_blocked():
    target = C.ManifestTarget("/other/wt", "symlink", "dev:1:ino:3")
    assert _validate(_manifest(targets=(target,))).code == "BLOCKED"


def test_M2_FLT_030_discard_interruptions_are_reconcile_only():
    d = C.reconcile_steps("worktree.discard", C.DISCARD_STEPS[:4])
    assert (d.code, d.recovery_class, d.remaining_steps) == ("PARTIAL", "reconcile-only", C.DISCARD_STEPS[4:])
    assert not C.validate_next_graph(result_code="PARTIAL", nodes=("worktree.discard.apply",), human_approval=False)


def test_M2_FLT_031_dirty_discard_needs_backup_receipt():
    assert _validate(dirty=True, backup_receipt=False).code == "BLOCKED"


def test_M2_FLT_050_dirty_merged_exact_finish_needs_backup_receipt():
    base = dict(work_unit_state="AUDITED", worktree_state="DIRTY", branch_audit_state="MERGED_EXACT",
                merge_proof=True, target_oid_matches=True, reachable=True)
    assert C.finish_precondition(**base, backup_receipt=False).code == "BLOCKED"
    assert C.finish_precondition(**base, backup_receipt=True).code == "DONE"


def test_M2_FLT_032_special_targets_are_all_manifested_not_implicitly_skipped():
    targets = tuple(C.ManifestTarget(f"/root/wt/{kind}", kind, f"id:{i}")
                    for i, kind in enumerate(("submodule", "ignored", "symlink")))
    assert _validate(_manifest(targets=targets)).code == "DONE"


def test_M2_FLT_033_missing_stable_identity_makes_discard_unsupported():
    assert _validate(stable_identity_supported=False).code == "UNSUPPORTED"


def test_M2_FLT_034_quarantine_evidence_maps_to_exactly_one_class():
    assert C.classify_quarantine(C.QuarantineEvidence(True, (), True, 0, True), total_mutating_steps=4) == "worktree-not-started"
    assert C.classify_quarantine(C.QuarantineEvidence(True, ("a",), True, 1, True), total_mutating_steps=4) == "worktree-resumable"
    assert C.classify_quarantine(C.QuarantineEvidence(True, ("a",), True, 4, True), total_mutating_steps=4) == "worktree-confirmed-done"
    assert C.classify_quarantine(C.QuarantineEvidence(False, (), True, 0, True), total_mutating_steps=4) == "worktree-unresolved"


def test_M2_FLT_035_lease_expiry_alone_never_reissues_guard():
    assert not C.may_reissue_guard(lease_expired=True, owner_stopped=False, children_stopped=False,
                                   os_lock_released=False, postcondition_reconciled=False)
    assert C.may_reissue_guard(lease_expired=True, owner_stopped=True, children_stopped=True,
                               os_lock_released=True, postcondition_reconciled=True)


def test_M2_FLT_036_unknown_recovery_tuple_is_human_stop():
    d = C.recovery_for("DONE", "unknown")
    assert (d.code, d.recovery_class) == ("INDETERMINATE", "human-stop")


def test_M2_FLT_056_tip_is_retained_and_cannot_be_pruned_early_or_unresolved():
    now = datetime(2026, 8, 14, tzinfo=timezone.utc)
    assert C.create_retention_ref("w1", "t", "abc", None).code == "DONE"
    assert C.create_retention_ref("w1", "t", "abc", "def").code == "BLOCKED"
    early = C.RetentionRef("r", "abc", now, now + timedelta(days=1), True)
    unresolved = C.RetentionRef("r", "abc", now, now - timedelta(days=1), False)
    assert not C.may_prune_retention(early, now=now, explicit_approval=True)
    assert not C.may_prune_retention(unresolved, now=now, explicit_approval=True)
