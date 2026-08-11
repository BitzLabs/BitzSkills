"""M1-2 の出口判定（FLW-NFR-011）— 3 platform fixture と統合 fault・変異試験。

M1-2 は M1 最初の blocking Go/No-Go である。ここが PASS しない限り M1-3 以降へ進まない。
実 platform CLI での qualification 実走は M1-6 confirmation が扱う。
"""

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / "plugins" / "bitz-flow" / "skills" / "flow-core"
M1_EVAL = REPO_ROOT / "evals" / "flow-core" / "m1-eval"
sys.path.insert(0, str(M1_EVAL))
sys.path.insert(0, str(M1_EVAL / "fixtures"))
sys.path.insert(0, str(SKILL / "scripts"))

import isolation as I  # noqa: E402
import qualification as Q  # noqa: E402
import qualification_fixtures as F  # noqa: E402
import raw_log_guard as G  # noqa: E402
from flowlib import coordinator as C  # noqa: E402

MANIFEST_SCHEMA = json.loads(
    (SKILL / "schemas" / "qualification-manifest-v1.schema.json").read_text(encoding="utf-8")
)

T0 = datetime(2026, 8, 11, tzinfo=timezone.utc)
CANARY = "CANARY-m1-2-fixture"


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


def _retention(tmp_path, name="trial.log"):
    guard = G.RawLogGuard(tmp_path / f"raw-{name}", owner="owner-1")
    log, failure = guard.store(
        name, f"begin {CANARY}\nrun ok\n", canaries=[CANARY], now=T0
    )
    assert failure is None
    return guard.retention_block(log)


def _manifest(platform, outcomes, tmp_path, *, elapsed=120.0, retries=0, blocking=()):
    decision = Q.evaluate(
        outcomes, elapsed_seconds=elapsed, harness_retries=retries, blocking_reasons=blocking
    )
    return Q.build_manifest(
        qualification_id=f"qual-{platform}",
        platform=platform,
        operation="git.commit",
        outcomes=outcomes,
        decision=decision,
        issued_at=T0,
        completed_at=T0 + timedelta(minutes=2),
        expires_at=T0 + timedelta(hours=24),
        retention=_retention(tmp_path, f"{platform}.log"),
        elapsed_seconds=elapsed,
        harness_retries=retries,
    )


def _check_manifest(manifest: dict) -> None:
    """schema の必須 field と enum を検査する（既存 test の流儀に合わせた最小検査）。"""
    required = set(MANIFEST_SCHEMA["required"])
    allowed = set(MANIFEST_SCHEMA["properties"])
    assert required <= set(manifest), f"必須 key 不足: {sorted(required - set(manifest))}"
    assert set(manifest) <= allowed, f"契約外 key: {sorted(set(manifest) - allowed)}"

    defs = MANIFEST_SCHEMA["$defs"]
    assert manifest["platform"] in MANIFEST_SCHEMA["properties"]["platform"]["enum"]
    assert manifest["gate_status"] in defs["gate_status"]["enum"]

    trials_schema = MANIFEST_SCHEMA["properties"]["trials"]
    assert trials_schema["minItems"] == trials_schema["maxItems"] == 3
    assert len(manifest["trials"]) == 3

    trial_required = set(defs["trial"]["required"])
    for trial in manifest["trials"]:
        assert trial_required <= set(trial), f"trial 必須 key 不足: {sorted(trial_required - set(trial))}"
        assert trial["kind"] in defs["trial_kind"]["enum"]
        assert trial["credential_class"] in defs["credential_class"]["enum"]
        assert defs["trial"]["properties"]["positive_control_ids"]["minItems"] == 1
        assert trial["positive_control_ids"], "陽性対照の空集合を許さない"
        for check in trial["checks"]:
            assert set(check) == set(defs["check_result"]["required"])

    retention_required = set(defs["retention"]["required"])
    assert retention_required <= set(manifest["retention"])
    assert manifest["retention"]["max_retention_days"] <= defs["retention"]["properties"]["max_retention_days"]["maximum"]

    limits = manifest["execution_limits"]
    assert limits["max_seconds"] == MANIFEST_SCHEMA["properties"]["execution_limits"]["properties"]["max_seconds"]["const"]
    assert limits["max_harness_retries"] == 1


# === 3 platform fixture が PASS する ==========================================


@pytest.mark.parametrize("platform", Q.PLATFORMS)
def test_each_platform_fixture_passes(platform, tmp_path):
    manifest = _manifest(platform, F.trials(platform), tmp_path)
    assert manifest["gate_status"] == Q.GATE_PASS, manifest["gate_reasons"]
    _check_manifest(manifest)


def test_all_platforms_combine_to_pass(tmp_path):
    manifests = [_manifest(p, F.trials(p), tmp_path) for p in Q.PLATFORMS]
    assert Q.combine(manifests).status == Q.GATE_PASS


@pytest.mark.parametrize("platform", Q.PLATFORMS)
def test_confirmation_may_start_after_pass(platform, tmp_path):
    assert Q.may_start_confirmation(_manifest(platform, F.trials(platform), tmp_path)) is True


def test_platform_identities_are_distinct():
    identities = {
        (v["cli_identity"], v["model_identity"], v["host_event_contract"])
        for v in F.PLATFORM_IDENTITY.values()
    }
    assert len(identities) == 3


def test_required_checks_are_bound_per_trial_kind():
    """必須 check と陽性対照は trial 種別ごとに事前拘束された閉集合である。"""
    for kind in Q.TRIAL_KINDS:
        spec = F.TRIAL_CHECKS[kind]
        assert spec["required"] and spec["controls"]


# === fixture が甘くないこと ====================================================


@pytest.mark.parametrize("platform", Q.PLATFORMS)
def test_zero_denominator_variant_does_not_pass(platform, tmp_path):
    manifest = _manifest(platform, F.corrupt_variant(platform), tmp_path)
    assert manifest["gate_status"] == Q.GATE_FAIL
    assert any("denominator が 0" in r for r in manifest["gate_reasons"])


@pytest.mark.parametrize("platform", Q.PLATFORMS)
def test_residual_side_effect_variant_does_not_pass(platform, tmp_path):
    manifest = _manifest(platform, F.residual_variant(platform), tmp_path)
    assert manifest["gate_status"] == Q.GATE_FAIL
    assert any("残存副作用" in r for r in manifest["gate_reasons"])


@pytest.mark.parametrize("platform", Q.PLATFORMS)
def test_undetected_control_variant_does_not_pass(platform, tmp_path):
    manifest = _manifest(platform, F.undetected_control_variant(platform), tmp_path)
    assert manifest["gate_status"] == Q.GATE_FAIL
    assert any("陽性対照" in r for r in manifest["gate_reasons"])


# === 統合 fault ================================================================


def test_failed_qualification_blocks_confirmation(tmp_path):
    manifest = _manifest("claude", F.residual_variant("claude"), tmp_path)
    assert Q.may_start_confirmation(manifest) is False


def test_one_platform_failure_is_not_averaged_away(tmp_path):
    manifests = [_manifest(p, F.trials(p), tmp_path) for p in Q.PLATFORMS]
    manifests[1] = _manifest("codex", F.corrupt_variant("codex"), tmp_path)
    decision = Q.combine(manifests)
    assert decision.status == Q.GATE_FAIL
    assert any("codex" in r for r in decision.reasons)


def test_expired_lease_blocks_the_trial(tmp_path):
    """lease が切り替わったら trial を継続しない。"""
    allocator = I.IsolationAllocator(owner="owner-1")
    lease = I.Lease(lease_id="lease:e1:1", expires_at=T0 + timedelta(hours=24))
    scope, _ = allocator.allocate(
        platform="claude", operation="git.commit", trial_kind="Q-NORMAL", lease=lease
    )
    switched = I.Lease(lease_id="lease:e1:2", expires_at=T0 + timedelta(hours=24))
    failure = allocator.check_lease(scope, switched)
    assert failure is not None

    manifest = _manifest("claude", F.trials("claude"), tmp_path, blocking=[failure.reason])
    assert manifest["gate_status"] == Q.GATE_BLOCKED
    assert Q.may_start_confirmation(manifest) is False


def test_expired_ttl_blocks_the_gate(tmp_path):
    clock = _Clock()
    coord = C.Coordinator(_Store(), clock, epoch_id="e1", leader_epoch=1)
    clock.advance(hours=24)
    reason = Q.check_ttl(coord, issued_at=T0, checkpoint="pre-mutation")

    manifest = _manifest("claude", F.trials("claude"), tmp_path, blocking=[reason])
    assert manifest["gate_status"] == Q.GATE_BLOCKED


def test_undetected_canary_stops_the_gate(tmp_path):
    """canary を検出できない log は保存段階で止まり、Gate まで到達させない。"""
    guard = G.RawLogGuard(tmp_path / "raw", owner="owner-1")
    log, failure = guard.store("x.log", "no canary here", canaries=[CANARY], now=T0)
    assert log is None

    manifest = _manifest("claude", F.trials("claude"), tmp_path, blocking=[failure.reason])
    assert manifest["gate_status"] == Q.GATE_BLOCKED
    assert Q.may_start_confirmation(manifest) is False


def test_isolation_and_manifest_agree_on_sandbox_boundary(tmp_path):
    """隔離が払い出した boundary をそのまま manifest へ載せられる。"""
    allocator = I.IsolationAllocator(owner="owner-1")
    lease = I.Lease(lease_id="lease:e1:1", expires_at=T0 + timedelta(hours=24))
    scope, _ = allocator.allocate(
        platform="claude", operation="git.commit", trial_kind="Q-NORMAL", lease=lease
    )
    outcomes = F.trials("claude")
    outcomes[0] = F.dataclasses_replace(
        outcomes[0], sandbox_boundary=scope.namespace.sandbox_boundary
    )
    manifest = _manifest("claude", outcomes, tmp_path)
    assert manifest["gate_status"] == Q.GATE_PASS
    assert manifest["trials"][0]["sandbox_boundary"] == scope.namespace.sandbox_boundary


def test_over_time_budget_fails_even_with_good_trials(tmp_path):
    manifest = _manifest("claude", F.trials("claude"), tmp_path, elapsed=601.0)
    assert manifest["gate_status"] == Q.GATE_FAIL


# === 変異試験（合格条件を緩めると検出できなくなること）=========================


@pytest.mark.parametrize(
    "mutation,expected",
    [
        ("allow_zero_denominator", "denominator が 0"),
        ("allow_zero_positive_control", "陽性対照 ID 集合が空"),
        ("allow_hazardous_event", "hazardous event"),
        ("skip_trial_count_check", "が 2 件"),
    ],
)
def test_relaxing_a_pass_condition_loses_detection(mutation, expected, monkeypatch):
    """合格条件を1つ緩めると、対応する FAIL 理由が出なくなることを確認する。"""
    if mutation == "allow_zero_denominator":
        outcomes = F.corrupt_variant("claude")
    elif mutation == "allow_zero_positive_control":
        outcomes = list(F.trials("claude"))
        outcomes[1] = F.dataclasses_replace(
            outcomes[1], positive_control_ids=(), positive_controls_detected=()
        )
    elif mutation == "allow_hazardous_event":
        outcomes = list(F.trials("claude"))
        outcomes[0] = F.dataclasses_replace(outcomes[0], hazardous_events=("raw_fallback",))
    else:
        outcomes = F.trials("claude") + [F.trial("claude", "git.commit", "Q-NORMAL")]

    before = Q.evaluate(outcomes, elapsed_seconds=1.0, harness_retries=0)
    assert before.status == Q.GATE_FAIL
    assert any(expected in r for r in before.reasons), before.reasons

    # 判定器を緩める（この変異を入れると上の検出が消える）
    monkeypatch.setattr(Q, "_trial_reasons", lambda outcome: [])
    if mutation == "skip_trial_count_check":
        monkeypatch.setattr(Q, "TRIAL_KINDS", ())
    after = Q.evaluate(outcomes, elapsed_seconds=1.0, harness_retries=0)
    assert not any(expected in r for r in after.reasons), "変異が効いていない（検査に検出力が無い）"
