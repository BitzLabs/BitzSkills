"""台帳の backup / restore（FLW-NFR-007 / FLW-NFR-011）。

FLW-DSN-015 が求める「M1 中に最低1回の RPO/RTO 検証」をここで行う。
"""

import json
import stat
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "evals" / "flow-core" / "m1-eval"))

import recovery_ops as RO  # noqa: E402

KEY = b"test-key-do-not-use-in-production"


def _entries(count=3):
    return [
        {"attempt_id": i, "objective_id": f"obj-{i}", "attempt_status": "PASS",
         "platform": "claude", "note": "日本語も含む"}
        for i in range(1, count + 1)
    ]


@pytest.fixture
def destination(tmp_path):
    return tmp_path / "backup" / "ledger.enc"


# --- backup ---------------------------------------------------------------------


def test_backup_is_not_plaintext(destination):
    entries = _entries()
    RO.backup(entries, destination, key=KEY)
    raw = destination.read_text(encoding="utf-8")
    assert "obj-1" not in raw, "平文で内容が読めてはならない"
    assert "日本語も含む" not in raw


def test_backup_is_owner_only(destination):
    RO.backup(_entries(), destination, key=KEY)
    assert not (destination.stat().st_mode & (stat.S_IRWXG | stat.S_IRWXO))


def test_backup_records_chain_digest(destination):
    entries = _entries()
    result = RO.backup(entries, destination, key=KEY)
    assert result.entry_count == 3
    assert result.chain_digest == RO.chain_digest(entries)


def test_backup_round_trips(destination):
    entries = _entries()
    RO.backup(entries, destination, key=KEY)
    restored, failure = RO.read_backup(destination, key=KEY)
    assert failure is None
    assert restored == entries


def test_wrong_key_is_rejected(destination):
    RO.backup(_entries(), destination, key=KEY)
    restored, failure = RO.read_backup(destination, key=b"another-key")
    assert restored is None
    assert "MAC" in failure.reason


def test_tampered_backup_is_detected(destination):
    RO.backup(_entries(), destination, key=KEY)
    stored = json.loads(destination.read_text(encoding="utf-8"))
    stored["body"] = stored["body"][:-4] + "AAAA"
    destination.write_text(json.dumps(stored), encoding="utf-8")

    restored, failure = RO.read_backup(destination, key=KEY)
    assert restored is None and "MAC" in failure.reason


def test_missing_backup_is_reported(tmp_path):
    restored, failure = RO.read_backup(tmp_path / "nope.enc", key=KEY)
    assert restored is None and failure.code == RO.CODE_BLOCKED


# --- restore（RPO 0）------------------------------------------------------------


def test_restore_recovers_snapshot_only(destination):
    entries = _entries()
    RO.backup(entries, destination, key=KEY)
    report, failure = RO.restore_from_replica(
        destination, [], key=KEY, acked_entry_ids=[1, 2, 3]
    )
    assert failure is None
    assert report.restored_entries == 3
    assert report.rpo_zero is True
    assert report.chain_digest == RO.chain_digest(entries)


def test_replica_wal_fills_entries_after_snapshot(destination):
    """M1-FLT-028 相当: snapshot 後・終了 entry 直後に primary が全損した場面。"""
    RO.backup(_entries(2), destination, key=KEY)
    wal = [{"attempt_id": 3, "objective_id": "obj-3", "attempt_status": "PASS"}]

    report, failure = RO.restore_from_replica(
        destination, wal, key=KEY, acked_entry_ids=[1, 2, 3]
    )
    assert failure is None
    assert report.restored_entries == 3
    assert report.missing_acked_entries == 0, "確認済み entry の欠落は 0"


def test_missing_acked_entry_breaks_rpo_zero(destination):
    RO.backup(_entries(2), destination, key=KEY)
    report, failure = RO.restore_from_replica(
        destination, [], key=KEY, acked_entry_ids=[1, 2, 3]
    )
    assert failure is None
    assert report.missing_acked_entries == 1
    assert report.rpo_zero is False, "ack 済みが欠けていれば RPO 0 を主張しない"


def test_wal_entry_supersedes_snapshot_for_same_id(destination):
    RO.backup([{"attempt_id": 1, "attempt_status": "STARTED"}], destination, key=KEY)
    report, _ = RO.restore_from_replica(
        destination, [{"attempt_id": 1, "attempt_status": "PASS"}], key=KEY, acked_entry_ids=[1]
    )
    assert report.restored_entries == 1


def test_entry_without_attempt_id_is_rejected(destination):
    RO.backup(_entries(1), destination, key=KEY)
    report, failure = RO.restore_from_replica(
        destination, [{"no_id": True}], key=KEY, acked_entry_ids=[1]
    )
    assert report is None and failure.code == RO.CODE_BLOCKED


# --- RTO ------------------------------------------------------------------------


def test_restore_records_elapsed_time(destination):
    RO.backup(_entries(), destination, key=KEY)
    report, _ = RO.restore_from_replica(destination, [], key=KEY, acked_entry_ids=[1, 2, 3])
    assert report.elapsed_seconds >= 0.0
    assert report.within_rto is True


def test_rto_target_is_four_hours():
    assert RO.RTO_SECONDS == 4 * 3600


def test_chain_digest_is_order_sensitive():
    a = RO.chain_digest([{"attempt_id": 1}, {"attempt_id": 2}])
    b = RO.chain_digest([{"attempt_id": 2}, {"attempt_id": 1}])
    assert a != b


def test_restore_orders_entries_by_attempt_id(destination):
    RO.backup([{"attempt_id": 3}, {"attempt_id": 1}], destination, key=KEY)
    report, _ = RO.restore_from_replica(
        destination, [{"attempt_id": 2}], key=KEY, acked_entry_ids=[1, 2, 3]
    )
    expected = RO.chain_digest([{"attempt_id": 1}, {"attempt_id": 2}, {"attempt_id": 3}])
    assert report.chain_digest == expected


# --- SLI ------------------------------------------------------------------------


def test_sli_thresholds_match_the_design():
    assert RO.SLI_MAX_APPEND_LATENCY_MS_P95 == 2000.0
    assert RO.SLI_MIN_AVAILABILITY == 0.99
    assert RO.SLI_MAX_CHAIN_INCONSISTENCY == 0


def test_healthy_sli_has_no_breach():
    observer = RO.SliObserver()
    for _ in range(100):
        observer.record_append(10.0)
        observer.record_probe(ok=True)
    assert observer.breaches() == []


def test_slow_append_is_a_breach():
    """遅いものが 10% あれば p95 が閾値を超える。"""
    observer = RO.SliObserver()
    observer.append_latencies_ms = [100.0] * 90 + [5000.0] * 10
    assert any("append latency" in b for b in observer.breaches())


def test_p95_is_not_dragged_by_a_few_outliers():
    """5% の外れ値では p95 は動かない（p95 の定義どおり）。"""
    observer = RO.SliObserver()
    observer.append_latencies_ms = [100.0] * 95 + [5000.0] * 5
    assert observer.p95_append_latency_ms() == 100.0
    assert observer.breaches() == []


def test_low_availability_is_a_breach():
    observer = RO.SliObserver()
    for i in range(100):
        observer.record_probe(ok=i >= 5)
    assert any("availability" in b for b in observer.breaches())


def test_any_chain_inconsistency_is_a_breach():
    observer = RO.SliObserver()
    observer.chain_inconsistencies = 1
    assert any("hash-chain" in b for b in observer.breaches())


def test_no_observation_yields_no_false_breach():
    """観測が無いことを「健全」とも「異常」とも言わない。"""
    observer = RO.SliObserver()
    assert observer.p95_append_latency_ms() is None
    assert observer.availability() is None
    assert observer.breaches() == []
