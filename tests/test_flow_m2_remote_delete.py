"""M2-6 remote-delete/confirmation fixtures。"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / "plugins" / "bitz-flow" / "skills" / "flow-core"
sys.path.insert(0, str(SKILL / "scripts"))
from flowlib import remote_delete as D  # noqa: E402

NOW = datetime(2026, 8, 14, tzinfo=timezone.utc)


def _plan(**overrides):
    values = dict(ref="refs/heads/x", expected_oid="abc", observed_at=NOW,
                  reachable_from_default=True, branch_audit_state="MERGED_EXACT")
    values.update(overrides)
    plan, decision = D.plan_delete(**values)
    return plan, decision


def test_M2_FLT_037_ref_advanced_after_plan_fails_expected_oid_cas():
    plan, _ = _plan()
    assert D.validate_cas(plan=plan, current_oid="def", protocol_supports_expected_oid=True,
                          conditional_request=True).code == "STALE"


def test_M2_FLT_038_aba_with_activity_update_is_blocked():
    d = D.evaluate_activity(capability="AVAILABLE", updates=({"type": "force_push"},),
                            complete_pagination=True, response_consistent=True)
    assert (d.code, d.aba_detection, d.approval_required) == ("BLOCKED", "detected", False)


def test_M2_FLT_048_empty_activity_still_requires_approval():
    d = D.evaluate_activity(capability="AVAILABLE", updates=(), complete_pagination=True,
                            response_consistent=True)
    assert (d.code, d.aba_detection, d.approval_required) == ("BLOCKED", "observed-none", True)
    assert "不在証明ではない" in d.reason


def test_M2_FLT_049_missing_api_is_unsupported_and_requires_approval():
    d = D.evaluate_activity(capability="UNSUPPORTED", updates=(), complete_pagination=False,
                            response_consistent=False)
    assert (d.code, d.aba_detection, d.approval_required) == ("UNSUPPORTED", "not-detected", True)


def test_M2_FLT_039_unconditional_or_non_cas_delete_is_rejected():
    plan, _ = _plan()
    assert D.validate_cas(plan=plan, current_oid="abc", protocol_supports_expected_oid=True,
                          conditional_request=False).code == "BLOCKED"
    assert D.validate_cas(plan=plan, current_oid="abc", protocol_supports_expected_oid=False,
                          conditional_request=True).code == "UNSUPPORTED"


def test_M2_FLT_040_remote_advanced_cannot_create_plan():
    plan, d = _plan(branch_audit_state="REMOTE_ADVANCED")
    assert plan is None and d.code == "BLOCKED"


def test_M2_FLT_041_unreachable_ref_cannot_create_plan():
    plan, d = _plan(reachable_from_default=False)
    assert plan is None and d.code == "BLOCKED"


def test_M2_FLT_042_stale_or_incompatible_qualification_cannot_be_gate_evidence():
    assert not D.qualification_allows_confirmation(stored_key="old", current_key="new",
        gate_status="PASS", expires_at=NOW + timedelta(hours=1), now=NOW)
    assert not D.qualification_allows_confirmation(stored_key="same", current_key="same",
        gate_status="PASS", expires_at=NOW, now=NOW)


def test_M2_FLT_043_confirmation_cannot_start_without_qualification_pass():
    assert not D.qualification_allows_confirmation(stored_key="same", current_key="same",
        gate_status="BLOCKED", expires_at=NOW + timedelta(hours=1), now=NOW)


def test_M2_FLT_044_remote_write_confirmation_is_deferred_to_m3():
    assert D.confirmation_scope("remote").code == "UNSUPPORTED"
    assert D.confirmation_scope("local").code == "DONE"


def test_M2_FLT_054_activity_failures_never_become_no_updates():
    assert D.evaluate_activity(capability="UNAVAILABLE", updates=(), complete_pagination=False,
                               response_consistent=False).code == "UNAVAILABLE"
    assert D.evaluate_activity(capability="AVAILABLE", updates=(), complete_pagination=False,
                               response_consistent=True).code == "INDETERMINATE"
    assert D.evaluate_activity(capability="AVAILABLE", updates=(), complete_pagination=True,
                               response_consistent=False).code == "INDETERMINATE"
