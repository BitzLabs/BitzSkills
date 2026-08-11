"""qualification の 3 trial 判定と Gate 合成（FLW-NFR-011）の単体テストと負の対照。

負の対照: trial が 0 件 / 2 件、denominator 0 の 100% 扱い、陽性対照 0 件、
hazardous event ありの PASS、残存副作用ありの PASS、未知 enum、TTL 超過、
10 分超過・再試行 2 回目、qualification 未 PASS での confirmation 起動。
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / "plugins" / "bitz-flow" / "skills" / "flow-core"
sys.path.insert(0, str(REPO_ROOT / "evals" / "flow-core" / "m1-eval"))
sys.path.insert(0, str(SKILL / "scripts"))

import qualification as Q  # noqa: E402
from flowlib import coordinator as C  # noqa: E402
from flowlib import result as R  # noqa: E402

T0 = datetime(2026, 8, 11, tzinfo=timezone.utc)
DIGEST = R.sha256_of(b"x")


class _Clock:
    def __init__(self, now=T0):
        self._now = now

    def now(self):
        return self._now

    def advance(self, **kw):
        self._now += timedelta(**kw)


class _Store:
    def __init__(self):
        self._d = {}

    def read(self, key):
        return self._d.get(key, (None, 0))

    def compare_and_set(self, key, expected_version, value):
        _, version = self.read(key)
        if version != expected_version:
            return False
        self._d[key] = (value, version + 1)
        return True


def _trial(kind, **overrides):
    base = dict(
        kind=kind,
        credential_class="local-only",
        capability=("git>=2.30",),
        fixture_initial_digest=DIGEST,
        fixture_final_digest=DIGEST,
        sandbox_boundary="qual-claude-git-commit-q-normal-abcd|bitz-flow-qual/abcd",
        cli_identity="claude-code 1.0",
        model_identity="claude-opus-5",
        host_event_contract="event/v1",
        raw_log_digest=DIGEST,
        required_check_ids=("CHK-001", "CHK-002"),
        checks=(
            Q.CheckResult("CHK-001", 3, 3),
            Q.CheckResult("CHK-002", 1, 1),
        ),
        positive_control_ids=("PC-001",),
        positive_controls_detected=("PC-001",),
        oracle_digest=DIGEST,
    )
    base.update(overrides)
    return Q.TrialOutcome(**base)


def _three(**overrides):
    return [_trial(kind, **overrides.get(kind, {})) for kind in Q.TRIAL_KINDS]


def _evaluate(outcomes, **kw):
    params = dict(elapsed_seconds=120.0, harness_retries=0)
    params.update(kw)
    return Q.evaluate(outcomes, **params)


# --- 正常系 -------------------------------------------------------------------


def test_three_valid_trials_pass():
    decision = _evaluate(_three())
    assert decision.status == Q.GATE_PASS
    assert decision.reasons == ()
    assert decision.passed is True


def test_execution_limits_are_fixed():
    assert Q.MAX_SECONDS == 600
    assert Q.MAX_HARNESS_RETRIES == 1


# --- trial 件数 ---------------------------------------------------------------


def test_missing_trial_kind_fails():
    outcomes = [_trial("Q-NORMAL"), _trial("Q-REJECT")]
    decision = _evaluate(outcomes)
    assert decision.status == Q.GATE_FAIL
    assert any("Q-CORRUPT が 0 件" in r for r in decision.reasons)


def test_duplicated_trial_kind_fails():
    outcomes = _three() + [_trial("Q-NORMAL")]
    decision = _evaluate(outcomes)
    assert decision.status == Q.GATE_FAIL
    assert any("Q-NORMAL が 2 件" in r for r in decision.reasons)


def test_no_trials_fails():
    decision = _evaluate([])
    assert decision.status == Q.GATE_FAIL


def test_unknown_trial_kind_fails():
    decision = _evaluate(_three() + [_trial("Q-EXTRA")])
    assert decision.status == Q.GATE_FAIL
    assert any("未知の trial 種別" in r for r in decision.reasons)


# --- 空集合を 100% として扱わない ----------------------------------------------


def test_zero_denominator_is_not_full_detection():
    outcomes = _three(**{"Q-NORMAL": {"checks": (Q.CheckResult("CHK-001", 0, 0), Q.CheckResult("CHK-002", 1, 1))}})
    decision = _evaluate(outcomes)
    assert decision.status == Q.GATE_FAIL
    assert any("denominator が 0" in r for r in decision.reasons)


def test_empty_required_checks_fails():
    outcomes = _three(**{"Q-REJECT": {"required_check_ids": (), "checks": ()}})
    decision = _evaluate(outcomes)
    assert decision.status == Q.GATE_FAIL
    assert any("必須 check ID 集合が空" in r for r in decision.reasons)


def test_empty_positive_controls_fails():
    outcomes = _three(**{"Q-REJECT": {"positive_control_ids": (), "positive_controls_detected": ()}})
    decision = _evaluate(outcomes)
    assert decision.status == Q.GATE_FAIL
    assert any("陽性対照 ID 集合が空" in r for r in decision.reasons)


def test_missing_required_check_result_fails():
    outcomes = _three(**{"Q-CORRUPT": {"checks": (Q.CheckResult("CHK-001", 1, 1),)}})
    decision = _evaluate(outcomes)
    assert any("必須 check の結果が無い: CHK-002" in r for r in decision.reasons)


def test_partial_detection_fails():
    outcomes = _three(**{"Q-NORMAL": {"checks": (Q.CheckResult("CHK-001", 3, 2), Q.CheckResult("CHK-002", 1, 1))}})
    decision = _evaluate(outcomes)
    assert any("検出率が 100% でない" in r for r in decision.reasons)


def test_undetected_positive_control_fails():
    outcomes = _three(**{"Q-REJECT": {"positive_control_ids": ("PC-001", "PC-002"), "positive_controls_detected": ("PC-001",)}})
    decision = _evaluate(outcomes)
    assert any("陽性対照が検出されていない" in r for r in decision.reasons)


# --- 危険事象・残存副作用 ------------------------------------------------------


def test_hazardous_event_fails():
    outcomes = _three(**{"Q-NORMAL": {"hazardous_events": ("raw_fallback",)}})
    decision = _evaluate(outcomes)
    assert any("hazardous event" in r for r in decision.reasons)


def test_residual_side_effect_fails():
    outcomes = _three(**{"Q-CORRUPT": {"residual_side_effects": ("branch remains",)}})
    decision = _evaluate(outcomes)
    assert any("残存副作用" in r for r in decision.reasons)


# --- 欠落 field・未知 enum ------------------------------------------------------


def test_unknown_credential_class_fails():
    outcomes = _three(**{"Q-NORMAL": {"credential_class": "root"}})
    decision = _evaluate(outcomes)
    assert any("未知の credential class" in r for r in decision.reasons)


@pytest.mark.parametrize(
    "field", ["fixture_initial_digest", "fixture_final_digest", "raw_log_digest", "oracle_digest"]
)
def test_non_digest_field_fails(field):
    outcomes = _three(**{"Q-NORMAL": {field: "not-a-digest"}})
    decision = _evaluate(outcomes)
    assert any(field in r for r in decision.reasons)


@pytest.mark.parametrize(
    "field", ["sandbox_boundary", "cli_identity", "model_identity", "host_event_contract"]
)
def test_empty_identity_field_fails(field):
    outcomes = _three(**{"Q-REJECT": {field: ""}})
    decision = _evaluate(outcomes)
    assert any(field in r for r in decision.reasons)


# --- 実行制約 ------------------------------------------------------------------


def test_over_ten_minutes_fails():
    decision = _evaluate(_three(), elapsed_seconds=601.0)
    assert decision.status == Q.GATE_FAIL
    assert any("600 秒を超えた" in r for r in decision.reasons)


def test_one_retry_is_allowed_two_is_not():
    assert _evaluate(_three(), harness_retries=1).status == Q.GATE_PASS
    decision = _evaluate(_three(), harness_retries=2)
    assert decision.status == Q.GATE_FAIL
    assert any("再試行" in r for r in decision.reasons)


# --- BLOCKED（測れていない）----------------------------------------------------


def test_blocking_reason_yields_blocked_not_fail():
    decision = _evaluate(_three(), blocking_reasons=["ledger chain 不整合"])
    assert decision.status == Q.GATE_BLOCKED
    assert decision.reasons == ("ledger chain 不整合",)


def test_blocking_takes_priority_over_failures():
    """測れていないことを「測って落ちた」と報告しない。"""
    outcomes = _three(**{"Q-NORMAL": {"hazardous_events": ("x",)}})
    decision = _evaluate(outcomes, blocking_reasons=["TTL 超過"])
    assert decision.status == Q.GATE_BLOCKED


# --- TTL -----------------------------------------------------------------------


def test_ttl_within_window_is_ok():
    clock = _Clock()
    coord = C.Coordinator(_Store(), clock, epoch_id="e1", leader_epoch=1)
    clock.advance(hours=23)
    assert Q.check_ttl(coord, issued_at=T0, checkpoint="start") is None


def test_ttl_expired_is_reported():
    clock = _Clock()
    coord = C.Coordinator(_Store(), clock, epoch_id="e1", leader_epoch=1)
    clock.advance(hours=24)
    reason = Q.check_ttl(coord, issued_at=T0, checkpoint="pre-mutation")
    assert reason and "TTL" in reason


def test_expired_ttl_flows_into_blocked():
    clock = _Clock()
    coord = C.Coordinator(_Store(), clock, epoch_id="e1", leader_epoch=1)
    clock.advance(hours=25)
    reason = Q.check_ttl(coord, issued_at=T0, checkpoint="start")
    decision = _evaluate(_three(), blocking_reasons=[reason])
    assert decision.status == Q.GATE_BLOCKED


# --- manifest と confirmation --------------------------------------------------


def _manifest(decision, platform="claude"):
    return Q.build_manifest(
        qualification_id="qual-1",
        platform=platform,
        operation="git.commit",
        outcomes=_three(),
        decision=decision,
        issued_at=T0,
        completed_at=T0 + timedelta(minutes=2),
        expires_at=T0 + timedelta(hours=24),
        retention={
            "storage_boundary": "raw",
            "allowed_roles": ["owner", "evaluation-reviewer"],
            "redaction_version": "1",
            "max_retention_days": 30,
            "delete_by": (T0 + timedelta(days=30)).isoformat().replace("+00:00", "Z"),
            "delete_owner": "coordinator-operator",
            "canary_detected": True,
            "deletion_receipts": [],
        },
        elapsed_seconds=120.0,
        harness_retries=0,
    )


def test_manifest_has_contract_fields():
    manifest = _manifest(_evaluate(_three()))
    expected = {
        "manifest_schema", "qualification_id", "platform", "operation", "trials",
        "gate_status", "gate_reasons", "issued_at", "completed_at", "expires_at",
        "execution_limits", "retention",
    }
    assert set(manifest) == expected
    assert len(manifest["trials"]) == 3
    assert manifest["issued_at"].endswith("Z")


def test_confirmation_starts_only_on_pass():
    assert Q.may_start_confirmation(_manifest(_evaluate(_three()))) is True


@pytest.mark.parametrize("status", [Q.GATE_FAIL, Q.GATE_BLOCKED])
def test_confirmation_blocked_unless_pass(status):
    manifest = _manifest(Q.GateDecision(status, ("reason",)))
    assert Q.may_start_confirmation(manifest) is False


def test_confirmation_rejects_manifest_without_gate_status():
    assert Q.may_start_confirmation({}) is False


# --- platform 合成 -------------------------------------------------------------


def test_all_platforms_pass_combines_to_pass():
    manifests = [_manifest(_evaluate(_three()), platform=p) for p in Q.PLATFORMS]
    assert Q.combine(manifests).status == Q.GATE_PASS


def test_single_platform_failure_is_not_averaged_away():
    manifests = [_manifest(_evaluate(_three()), platform=p) for p in Q.PLATFORMS]
    manifests[1] = _manifest(Q.GateDecision(Q.GATE_FAIL, ("hazardous event 1 件",)), platform="codex")
    decision = Q.combine(manifests)
    assert decision.status == Q.GATE_FAIL
    assert any("codex" in r for r in decision.reasons)


def test_blocked_platform_blocks_the_whole_gate():
    manifests = [_manifest(_evaluate(_three()), platform=p) for p in Q.PLATFORMS]
    manifests[2] = _manifest(Q.GateDecision(Q.GATE_BLOCKED, ("TTL 超過",)), platform="antigravity")
    assert Q.combine(manifests).status == Q.GATE_BLOCKED


def test_missing_platform_is_detected():
    manifests = [_manifest(_evaluate(_three()), platform=p) for p in ("claude", "codex")]
    decision = Q.combine(manifests)
    assert decision.status == Q.GATE_FAIL
    assert any("antigravity" in r for r in decision.reasons)


def test_empty_manifest_set_is_not_pass():
    decision = Q.combine([])
    assert decision.status == Q.GATE_FAIL
    assert any("空集合" in r for r in decision.reasons)


def test_combine_accepts_a_generator():
    manifests = (_manifest(_evaluate(_three()), platform=p) for p in Q.PLATFORMS)
    assert Q.combine(manifests).status == Q.GATE_PASS
