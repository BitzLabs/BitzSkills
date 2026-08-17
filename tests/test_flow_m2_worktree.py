"""M2-3 create/resume/audit fixtures（FLW-FR-006 / FLW-FR-007）。"""

import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1] / "plugins" / "bitz-flow" / "skills" / "flow-core"
sys.path.insert(0, str(SKILL / "scripts"))

from flowlib import worktree as W  # noqa: E402


def _observation(**overrides):
    values = {
        "evidence_complete": True,
        "directory_exists": True,
        "registry_exists": True,
        "binding_valid": True,
        "branch_matches": True,
        "head_matches": True,
    }
    values.update(overrides)
    return W.AuditObservation(**values)


def test_M2_FLT_016_create_crash_boundaries_converge_uniquely():
    before = W.reconcile_create(W.CREATE_STEPS[:4], _observation())
    after = W.reconcile_create(W.CREATE_STEPS, _observation(binding_valid=False))
    done = W.reconcile_create(W.CREATE_STEPS, _observation())
    assert (before.code, after.code, done.code) == ("STALE", "PARTIAL", "DONE")


def test_M2_FLT_017_exact_existing_worktree_routes_to_resume():
    decision = W.plan_create(_observation())
    assert (decision.code, decision.action) == ("DONE", "worktree.resume")


def test_M2_FLT_018_partial_match_is_mismatch_and_blocked():
    decision = W.plan_create(_observation(head_matches=False))
    assert (decision.code, decision.worktree_state) == ("BLOCKED", "MISMATCH")


def test_M2_FLT_019_same_branch_in_another_worktree_is_blocked():
    decision = W.plan_create(_observation(branch_in_other_worktree=True))
    assert (decision.code, decision.reason) == ("BLOCKED", "WORKTREE_IN_USE")


def test_M2_FLT_020_dirty_audit_keeps_read_only_work_available():
    decision = W.audit_worktree(_observation(dirty=True))
    assert (decision.code, decision.worktree_state, decision.branch_audit_state) == (
        "DONE", "DIRTY", "ACTIVE"
    )


def test_M2_FLT_021_legacy_branch_only_and_remote_only_are_classified():
    branch_only = W.audit_worktree(
        _observation(directory_exists=False, registry_exists=False, remote_branch_exists=False)
    )
    remote_only = W.audit_worktree(
        _observation(directory_exists=False, registry_exists=False, local_branch_exists=False, remote_branch_exists=True)
    )
    assert branch_only.branch_audit_state == remote_only.branch_audit_state == "ACTIVE"


def test_M2_FLT_022_incomplete_evidence_is_indeterminate_without_guessing():
    decision = W.audit_worktree(_observation(evidence_complete=False))
    assert decision.code == "INDETERMINATE"
    assert decision.worktree_state is decision.branch_audit_state is None


# `M2-FLT-023`（design/schema/実装の三者照合）は `test_flow_contract_vocabulary.py` へ
# 移設・拡張した（`FLW-TSK-097`）。旧実装は `work_unit_state` / `worktree_state` /
# `branch_audit_state` の3 namespace だけをハードコードしており、`FLW-DSN-016` §2 の
# 閉集合表が宣言する他の namespace（`cause` を含む）を走査していなかった
# （`SI-FLW-072`）。新実装は閉集合表をパースして得た**全 namespace**を回す。


def test_M2_FLT_053_capability_symmetry_blocks_create_but_allows_audit():
    missing = W.RootCapabilities(True, True, False, True)
    assert W.operation_support("worktree.create", missing).code == "UNSUPPORTED"
    assert W.operation_support("worktree.resume", missing).code == "UNSUPPORTED"
    assert W.operation_support("worktree.audit", missing).code == "DONE"


def test_resume_rejects_recreated_instance():
    audit = W.audit_worktree(_observation())
    assert W.plan_resume(expected_instance_digest="old", observed_instance_digest="new", audit=audit).code == "STALE"
