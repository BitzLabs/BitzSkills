"""M2-3 create/resume/audit fixtures（FLW-FR-006 / FLW-FR-007）。"""

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / "plugins" / "bitz-flow" / "skills" / "flow-core"
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


def _design_enums():
    text = (REPO_ROOT / "plugins/bitz-flow/.spec/design/FLW-DSN-016.md").read_text(encoding="utf-8")
    rows = {}
    for field in ("work_unit_state", "worktree_state", "branch_audit_state"):
        match = re.search(rf"\|[^\n]*`{field}`[^\n]*\|\s*`([^\n]+)`\s*\|", text)
        assert match
        rows[field] = tuple(part.strip(" `") for part in match.group(1).split(","))
    return rows


def test_M2_FLT_023_design_schema_and_implementation_enums_match_both_ways():
    schema = json.loads((SKILL / "schemas/worktree-state-v1.schema.json").read_text(encoding="utf-8"))
    implementation = {
        "work_unit_state": W.WORK_UNIT_STATES,
        "worktree_state": W.WORKTREE_STATES,
        "branch_audit_state": W.BRANCH_AUDIT_STATES,
    }
    for field, design_values in _design_enums().items():
        schema_values = tuple(schema["$defs"][field]["enum"])
        assert set(design_values) == set(schema_values) == set(implementation[field])


def test_M2_FLT_053_capability_symmetry_blocks_create_but_allows_audit():
    missing = W.RootCapabilities(True, True, False, True)
    assert W.operation_support("worktree.create", missing).code == "UNSUPPORTED"
    assert W.operation_support("worktree.resume", missing).code == "UNSUPPORTED"
    assert W.operation_support("worktree.audit", missing).code == "DONE"


def test_resume_rejects_recreated_instance():
    audit = W.audit_worktree(_observation())
    assert W.plan_resume(expected_instance_digest="old", observed_instance_digest="new", audit=audit).code == "STALE"
