"""M1-5 の出口判定 — fault fixture 13件（FLW-DSN-015 の fault fixture catalog）。

対象は M1-5 割付分（FLT-010〜015, 017, 018, 021〜023, 028, 030）。
FLT-001〜009 / 016 / 019 / 020 / 024〜027 / 029 は M1-3 で検証済み。
"""

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / "plugins" / "bitz-flow" / "skills" / "flow-core"
FLOW = SKILL / "scripts" / "flow.py"
M1_EVAL = REPO_ROOT / "evals" / "flow-core" / "m1-eval"
sys.path.insert(0, str(M1_EVAL))
sys.path.insert(0, str(M1_EVAL / "fixtures"))
sys.path.insert(0, str(SKILL / "scripts"))

import compatibility as C  # noqa: E402
import ledger as L  # noqa: E402
import qualification as Q  # noqa: E402
import qualification_fixtures as F  # noqa: E402
import raw_log_guard as G  # noqa: E402
import recovery_ops as RO  # noqa: E402
from flowlib import coordinator as CO  # noqa: E402
from flowlib import durable as D  # noqa: E402

T0 = datetime(2026, 8, 12, tzinfo=timezone.utc)
KEY = b"m1-5-fault-key"
CANARY = "CANARY-m1-5"

#: このファイルが担当する fixture（M1-5 割付）。
M1_5_FIXTURES = (
    "M1-FLT-010", "M1-FLT-011", "M1-FLT-012", "M1-FLT-013", "M1-FLT-014",
    "M1-FLT-015", "M1-FLT-017", "M1-FLT-018", "M1-FLT-021", "M1-FLT-022",
    "M1-FLT-023", "M1-FLT-028", "M1-FLT-030",
)

RETRYABLE = ("instrument-unavailable", "environment-unavailable")


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


class _Clock:
    def __init__(self, now=T0):
        self._now = now

    def now(self):
        return self._now

    def advance(self, **kw):
        self._now += timedelta(**kw)


class _Replica:
    def __init__(self, ack=True):
        self.ack = ack

    def append_wal(self, entry_bytes, digest):
        return self.ack


def _attempt(attempt_id, status=L.STATUS_PASS, **overrides):
    base = dict(
        attempt_id=attempt_id, objective_id="obj-1", epoch_id="e1",
        compatibility_key="sha256:k1", platform="claude", status=status,
        retryable_failure_codes=RETRYABLE,
    )
    base.update(overrides)
    return L.Attempt(**base)


def _inputs(**overrides):
    base = {
        "scoring_rule": "sha256:rule-1", "runner": "sha256:runner-1",
        "adapter": "sha256:adapter-1", "oracle": "sha256:oracle-1",
        "fixture": "sha256:fixture-1", "prompt": "sha256:prompt-1",
        "skill": "sha256:skill-1", "result_schema": "bitz-flow/result/v1",
        "event_schema": "claude/event/v1", "transitive_dependencies": ["git"],
        "model_identity": "claude-opus-5", "cli_version": "1.0",
        "host_event_contract_version": "v1", "trial_assignment": {"Q-NORMAL": 1},
    }
    base.update(overrides)
    return base


@pytest.fixture
def ledger():
    return L.Ledger()


# === FLT-010: ledger partition / 未登録 run ====================================


def test_m1_flt_010_unregistered_run_blocks_the_gate(ledger):
    ledger.register(_attempt(1))
    failure = ledger.reconcile({"claude": [1, 99]})
    assert failure.code == L.GATE_BLOCKED
    assert "正本未取込" in failure.reason


def test_m1_flt_010_runner_does_not_start_without_ledger_entry(tmp_path):
    """台帳へ先行登録できなければ起動しない。"""
    log = D.DurableLog(tmp_path / "l", replica=_Replica(ack=False))
    commit, failure = log.append({"attempt_id": 1})
    assert commit is None and failure.code == D.CODE_BLOCKED


# === FLT-011: FAIL 後に PASS を同 epoch へ登録 =================================


def test_m1_flt_011_pass_cannot_replace_fail(ledger):
    ledger.register(_attempt(1, status=L.STATUS_FAIL))
    failure = ledger.register(_attempt(2, status=L.STATUS_PASS))
    assert failure.code == L.GATE_BLOCKED
    assert ledger.candidate_for("obj-1").status == L.STATUS_FAIL


# === FLT-012: eligibility の事後変更 ===========================================


def test_m1_flt_012_correction_is_appended_and_original_kept(ledger):
    ledger.register(_attempt(1, status=L.STATUS_FAIL, eligibility_rule_id="rule-1",
                             failure_code="instrument-unavailable"))
    ledger.append_correction(1, new_classification="environment-unavailable", rationale="再分析")

    original = next(e for e in ledger.entries if e.attempt_id == 1)
    assert original.eligibility_rule_id == "rule-1"
    assert original.failure_code == "instrument-unavailable", "元 entry を書き換えない"
    assert ledger.corrections[-1]["classification"] == "environment-unavailable"


# === FLT-013: model / CLI / event version の変更 ===============================


@pytest.mark.parametrize(
    "field", ["model_identity", "cli_version", "host_event_contract_version", "adapter"]
)
def test_m1_flt_013_platform_version_change_invalidates_that_platform(field):
    result = C.invalidation_for(_inputs(), _inputs(**{field: "changed"}), platform="codex")
    assert result.scope == "single-platform"
    assert result.platforms == ("codex",)


def test_m1_flt_013_common_change_invalidates_every_platform():
    result = C.invalidation_for(_inputs(), _inputs(scoring_rule="changed"), platform="codex")
    assert result.invalidates_everything is True


# === FLT-014: raw log の秘密値・期限超過 =======================================


def test_m1_flt_014_secret_canary_undetected_fails(tmp_path):
    guard = G.RawLogGuard(tmp_path / "raw", owner="o")
    log, failure = guard.store("x.log", "no canary", canaries=[CANARY], now=T0)
    assert log is None and failure.code == G.CODE_BLOCKED


def test_m1_flt_014_expired_raw_log_fails(tmp_path):
    guard = G.RawLogGuard(tmp_path / "raw", owner="o")
    log, _ = guard.store("x.log", f"line {CANARY}", canaries=[CANARY], now=T0)
    failure = guard.check_expiry(log, now=T0 + timedelta(days=31))
    assert failure.code == G.CODE_BLOCKED


def test_m1_flt_014_blocks_the_gate(tmp_path):
    guard = G.RawLogGuard(tmp_path / "raw", owner="o")
    _, failure = guard.store("x.log", "no canary", canaries=[CANARY], now=T0)
    decision = Q.evaluate(
        F.trials("claude"), elapsed_seconds=1.0, harness_retries=0,
        blocking_reasons=[failure.reason],
    )
    assert decision.status == Q.GATE_BLOCKED


# === FLT-015: qualification と confirmation の間の drift ========================


def test_m1_flt_015_drift_prevents_confirmation():
    before = _inputs()
    after = _inputs(fixture="sha256:fixture-2")
    comparison = C.compare(before, after)
    assert comparison.status == C.STATUS_INCOMPATIBLE

    decision = Q.evaluate(
        F.trials("claude"), elapsed_seconds=1.0, harness_retries=0,
        blocking_reasons=["qualification と confirmation の間で fixture が変わった"],
    )
    manifest = {"gate_status": decision.status}
    assert Q.may_start_confirmation(manifest) is False


def test_m1_flt_015_dynamic_fingerprint_detects_ephemeral_drift():
    a = C.dynamic_fingerprint({"credential_class": "write-scoped"})
    b = C.dynamic_fingerprint({"credential_class": "read-scoped"})
    assert a != b, "合成直前の再照合で短命状態の変化を捉える"


# === FLT-017: stale coordinator leader が append ================================


def test_m1_flt_017_stale_leader_is_fenced():
    store = _Store()
    CO.Coordinator(store, _Clock(), epoch_id="e2", leader_epoch=9).issue_attempt()

    stale = CO.Coordinator(store, _Clock(), epoch_id="e1", leader_epoch=3)
    attempt, failure = stale.issue_attempt()
    assert attempt is None
    assert failure.code == CO.CODE_BLOCKED
    assert "stale leader" in failure.reason


# === FLT-018: partition 後に late PASS 到着 =====================================


def test_m1_flt_018_late_pass_does_not_become_candidate(ledger):
    ledger.register(_attempt(1, status=L.STATUS_STARTED))
    ledger.mark_unknown(1, reason="partition")
    ledger.register(_attempt(2, status=L.STATUS_PASS, late=True))

    assert ledger.candidate_for("obj-1") is None
    assert len(ledger.late_evidence_for("obj-1")) == 1


# === FLT-021: FAIL 後に key / epoch だけ変更 ====================================


def test_m1_flt_021_key_change_alone_keeps_old_fail(ledger):
    ledger.register(_attempt(1, status=L.STATUS_FAIL))
    ledger.register(_attempt(2, status=L.STATUS_PASS, compatibility_key="sha256:k2"))
    assert ledger.candidate_for("obj-1").status == L.STATUS_FAIL


def test_m1_flt_021_epoch_change_alone_keeps_old_fail(ledger):
    ledger.register(_attempt(1, status=L.STATUS_FAIL))
    ledger.register(_attempt(2, status=L.STATUS_PASS, epoch_id="e2"))
    assert ledger.candidate_for("obj-1").status == L.STATUS_FAIL


# === FLT-022: 実行中 / Gate commit 直前の TTL 切れ ==============================


@pytest.mark.parametrize("checkpoint", ["start", "pre-mutation"])
def test_m1_flt_022_expired_ttl_blocks_the_gate(checkpoint):
    clock = _Clock()
    coord = CO.Coordinator(_Store(), clock, epoch_id="e1", leader_epoch=1)
    clock.advance(hours=24)
    reason = Q.check_ttl(coord, issued_at=T0, checkpoint=checkpoint)
    assert reason is not None

    decision = Q.evaluate(
        F.trials("claude"), elapsed_seconds=1.0, harness_retries=0, blocking_reasons=[reason]
    )
    assert decision.status == Q.GATE_BLOCKED


def test_m1_flt_022_boundary_time_is_expired():
    clock = _Clock()
    coord = CO.Coordinator(_Store(), clock, epoch_id="e1", leader_epoch=1)
    clock.advance(seconds=CO.QUALIFICATION_TTL_SECONDS)
    assert Q.check_ttl(coord, issued_at=T0, checkpoint="pre-mutation") is not None


# === FLT-023: append の各点 crash ===============================================


@pytest.mark.parametrize("step", D.STEPS)
def test_m1_flt_023_append_crash_isolates_torn_entry(tmp_path, step):
    root = tmp_path / f"l-{step}"
    log = D.DurableLog(root, replica=_Replica(), step_hook=D.crash_after(step))
    commit, failure = log.append({"attempt_id": 1})
    assert commit is None and failure is not None

    healthy = D.DurableLog(root, replica=_Replica())
    report, _ = healthy.scan()
    if step in (D.STEP_TEMP_WRITTEN, D.STEP_FILE_FSYNCED):
        assert report.torn
        moved, _ = healthy.quarantine_torn(report)
        assert moved
    else:
        assert report.healthy


def test_m1_flt_023_valid_chain_recovers_with_rpo_zero(tmp_path):
    root = tmp_path / "l"
    log = D.DurableLog(root, replica=_Replica())
    log.append({"attempt_id": 1})
    log.append({"attempt_id": 2})

    report, _ = log.scan()
    backup_path = tmp_path / "b" / "ledger.enc"
    RO.backup(report.entries, backup_path, key=KEY)

    restored, failure = RO.restore_from_replica(
        backup_path, [], key=KEY, acked_entry_ids=[1, 2]
    )
    assert failure is None and restored.rpo_zero is True


# === FLT-028: primary 全損 ======================================================


def test_m1_flt_028_replica_wal_replay_loses_nothing(tmp_path):
    backup_path = tmp_path / "b" / "ledger.enc"
    RO.backup([{"attempt_id": 1}, {"attempt_id": 2}], backup_path, key=KEY)
    wal = [{"attempt_id": 3}, {"attempt_id": 4}]

    report, failure = RO.restore_from_replica(
        backup_path, wal, key=KEY, acked_entry_ids=[1, 2, 3, 4]
    )
    assert failure is None
    assert report.missing_acked_entries == 0
    assert report.restored_entries == 4


def test_m1_flt_028_missing_acked_entry_is_visible(tmp_path):
    backup_path = tmp_path / "b" / "ledger.enc"
    RO.backup([{"attempt_id": 1}], backup_path, key=KEY)
    report, _ = RO.restore_from_replica(backup_path, [], key=KEY, acked_entry_ids=[1, 2])
    assert report.rpo_zero is False, "欠落を隠して RPO 0 を主張しない"


# === FLT-030: retry nonce の二重消費 ============================================


def test_m1_flt_030_retry_slot_is_single_use(ledger):
    attempt = _attempt(1, status=L.STATUS_FAIL, failure_code="instrument-unavailable",
                       failure_axis=("instrument",))
    ledger.register(attempt)

    first, failure = ledger.consume_retry(attempt, successor_id=2)
    assert failure is None and first is not None
    second, failure = ledger.consume_retry(attempt, successor_id=3)
    assert second is None, "二重消費できない"
    assert len(ledger.successors_of(1)) == 1, "successor は最大 1 件"


def test_m1_flt_030_no_retry_leaves_no_successor(ledger):
    attempt = _attempt(1, status=L.STATUS_PASS)
    ledger.register(attempt)
    assert ledger.may_retry(attempt).allowed is False
    assert ledger.successors_of(1) == (), "successor 0 件"


def test_m1_flt_030_no_id_gap_after_retry(ledger):
    attempt = _attempt(1, status=L.STATUS_FAIL, failure_code="environment-unavailable",
                       failure_axis=("environment",))
    ledger.register(attempt)
    ledger.consume_retry(attempt, successor_id=2)
    assert ledger.reconcile({"claude": [1, 2]}) is None, "欠番 0"


def test_m1_flt_030_nonce_double_consumption_is_blocked():
    coord = CO.Coordinator(_Store(), _Clock(), epoch_id="e1", leader_epoch=1)
    assert coord.begin_nonce("retry-1") is None
    failure = coord.begin_nonce("retry-1")
    assert failure.code == CO.CODE_BLOCKED


# === 公開面の非退行 ============================================================


@pytest.fixture(scope="module")
def repo(tmp_path_factory):
    path = tmp_path_factory.mktemp("m1-5-repo")
    subprocess.run(["git", "init", "-q", "-b", "main", str(path)], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "t@example.com"], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "t"], check=True)
    (path / "a.txt").write_text("x\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(path), "add", "a.txt"], check=True)
    subprocess.run(["git", "-C", str(path), "commit", "-qm", "chore: init"], check=True)
    return path


@pytest.mark.parametrize("action", ["commit", "stage", "fetch", "sync", "publish-branch"])
def test_write_operations_remain_unsupported(repo, action):
    proc = subprocess.run(
        [sys.executable, str(FLOW), "--repo", str(repo), "git", action, "--format", "json"],
        capture_output=True, text=True,
    )
    result = json.loads(proc.stdout)
    assert result["code"] == "UNSUPPORTED" and proc.returncode == 8


# === fixture の網羅 ============================================================


def test_all_m1_5_fixtures_have_a_test():
    source = Path(__file__).read_text(encoding="utf-8")
    missing = [f for f in M1_5_FIXTURES if f.replace("-", "_").lower() not in source.lower()]
    assert missing == [], f"対応するテストが無い fixture: {missing}"
    assert len(M1_5_FIXTURES) == 13


def test_m1_3_and_m1_5_fixtures_do_not_overlap():
    m1_3 = {
        "M1-FLT-001", "M1-FLT-002", "M1-FLT-003", "M1-FLT-004", "M1-FLT-005",
        "M1-FLT-006", "M1-FLT-007", "M1-FLT-008", "M1-FLT-009", "M1-FLT-016",
        "M1-FLT-019", "M1-FLT-020", "M1-FLT-024", "M1-FLT-025", "M1-FLT-026",
        "M1-FLT-027", "M1-FLT-029",
    }
    assert not (m1_3 & set(M1_5_FIXTURES))
    assert len(m1_3) + len(M1_5_FIXTURES) == 30, "catalog の 30 件を漏れなく分担する"
