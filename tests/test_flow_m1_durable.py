"""FLW-TSK-028: durable append-only store の単体テストと crash 注入。

不変条件（これが破れたら write 全体が信用できない）:
  - durability commit point（directory fsync）に到達しない限り Commit を返さない
    = 呼出側が「記録なしの副作用」を実行する経路が存在しない
  - replica の ack が無ければ commit しない（RPO 0）
  - chain 破損・欠番・重複を自動修復しない（隔離して BLOCKED）
"""

import json
import stat
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / "plugins" / "bitz-flow" / "skills" / "flow-core"
sys.path.insert(0, str(SKILL / "scripts"))

from flowlib import durable as D  # noqa: E402
from flowlib import result as R  # noqa: E402


class MemoryReplica:
    def __init__(self, ack: bool = True):
        self.ack = ack
        self.wal: list[tuple[bytes, str]] = []

    def append_wal(self, entry_bytes, digest):
        if not self.ack:
            return False
        self.wal.append((entry_bytes, digest))
        return True


class BrokenReplica:
    def append_wal(self, entry_bytes, digest):
        raise ConnectionError("replica unreachable")


@pytest.fixture
def replica():
    return MemoryReplica()


@pytest.fixture
def log(tmp_path, replica):
    return D.DurableLog(tmp_path / "intent", replica=replica)


# --- 正常系 -------------------------------------------------------------------


def test_append_returns_commit_and_chains(log, replica):
    first, failure = log.append({"operation_id": "op-1"})
    assert failure is None
    assert first.sequence == 1 and first.previous_digest is None

    second, failure = log.append({"operation_id": "op-2"})
    assert failure is None
    assert second.sequence == 2
    assert second.previous_digest == first.entry_digest
    assert len(replica.wal) == 2


def test_scan_reads_back_the_chain(log):
    log.append({"operation_id": "op-1"})
    log.append({"operation_id": "op-2"})

    report, failure = log.scan()
    assert failure is None and report.healthy
    assert [e["operation_id"] for e in report.entries] == ["op-1", "op-2"]
    assert report.head_sequence == 2


def test_owner_only_permissions(log, tmp_path):
    log.append({"operation_id": "op-1"})
    root = tmp_path / "intent"
    assert not (root.stat().st_mode & (stat.S_IRWXG | stat.S_IRWXO))
    entry = next(root.glob("*.json"))
    assert not (entry.stat().st_mode & (stat.S_IRWXG | stat.S_IRWXO))


def test_stats_exposes_sli_observation_points(log):
    log.append({"operation_id": "op-1"})
    assert log.stats() == {"appends": 1, "chain_problems": 0}


def test_commit_carries_latency_for_sli(log):
    commit, _ = log.append({"operation_id": "op-1"})
    assert commit.latency_ms >= 0.0


# --- crash 注入 ---------------------------------------------------------------


@pytest.mark.parametrize("step", D.STEPS)
def test_crash_at_any_step_yields_no_commit(tmp_path, replica, step):
    """どの段階で中断しても Commit は返らない = 副作用を開始できない。"""
    log = D.DurableLog(tmp_path / "intent", replica=replica, step_hook=D.crash_after(step))
    commit, failure = log.append({"operation_id": "op-1"})
    assert commit is None, f"{step} で中断したのに Commit を返した"
    assert failure.code == D.CODE_BLOCKED


@pytest.mark.parametrize("step", [D.STEP_TEMP_WRITTEN, D.STEP_FILE_FSYNCED])
def test_crash_before_rename_leaves_torn_entry(tmp_path, replica, step):
    root = tmp_path / "intent"
    log = D.DurableLog(root, replica=replica, step_hook=D.crash_after(step))
    log.append({"operation_id": "op-1"})

    healthy = D.DurableLog(root, replica=replica)
    report, _ = healthy.scan()
    assert report.torn, "rename 前の中断は torn entry として観測できなければならない"
    assert report.entries == []


@pytest.mark.parametrize("step", [D.STEP_RENAMED, D.STEP_DIR_FSYNCED])
def test_crash_after_rename_keeps_record_without_side_effect(tmp_path, replica, step):
    """記録が残って副作用が起きない状態は許容する（逆は許さない）。"""
    root = tmp_path / "intent"
    log = D.DurableLog(root, replica=replica, step_hook=D.crash_after(step))
    commit, _ = log.append({"operation_id": "op-1"})
    assert commit is None

    healthy = D.DurableLog(root, replica=replica)
    report, _ = healthy.scan()
    assert report.healthy
    assert [e["operation_id"] for e in report.entries] == ["op-1"]


def test_quarantine_lets_append_resume(tmp_path, replica):
    root = tmp_path / "intent"
    D.DurableLog(root, replica=replica, step_hook=D.crash_after(D.STEP_TEMP_WRITTEN)).append(
        {"operation_id": "op-1"}
    )

    log = D.DurableLog(root, replica=replica)
    report, _ = log.scan()
    moved, failure = log.quarantine_torn(report)
    assert failure is None and moved

    commit, failure = log.append({"operation_id": "op-2"})
    assert failure is None and commit.sequence == 1
    assert (root / D._QUARANTINE_DIR / moved[0]).exists(), "隔離物は削除せず保持する"


# --- RPO 0 --------------------------------------------------------------------


def test_replica_without_ack_does_not_commit(tmp_path):
    log = D.DurableLog(tmp_path / "intent", replica=MemoryReplica(ack=False))
    commit, failure = log.append({"operation_id": "op-1"})
    assert commit is None
    assert failure.code == D.CODE_BLOCKED
    assert "RPO 0" in failure.reason


def test_replica_error_does_not_commit(tmp_path):
    log = D.DurableLog(tmp_path / "intent", replica=BrokenReplica())
    commit, failure = log.append({"operation_id": "op-1"})
    assert commit is None and failure.code == D.CODE_BLOCKED


# --- chain の健全性 -----------------------------------------------------------


def test_tampered_entry_is_detected_and_not_repaired(log, tmp_path):
    log.append({"operation_id": "op-1"})
    entry_path = next((tmp_path / "intent").glob("*.json"))
    record = json.loads(entry_path.read_text(encoding="utf-8"))
    record["entry"]["operation_id"] = "op-tampered"
    entry_path.write_text(json.dumps(record), encoding="utf-8")

    report, _ = log.scan()
    assert not report.healthy
    assert any("digest 不一致" in p for p in report.problems)

    commit, failure = log.append({"operation_id": "op-2"})
    assert commit is None
    assert failure.code == D.CODE_BLOCKED
    assert "自動修復しない" in failure.reason


def test_missing_sequence_is_detected(log, tmp_path):
    log.append({"operation_id": "op-1"})
    log.append({"operation_id": "op-2"})
    root = tmp_path / "intent"
    (root / "000000000001.json").unlink()

    report, _ = log.scan()
    assert not report.healthy
    assert any("欠番" in p for p in report.problems)


def test_broken_previous_digest_is_detected(log, tmp_path):
    log.append({"operation_id": "op-1"})
    log.append({"operation_id": "op-2"})
    root = tmp_path / "intent"
    path = root / "000000000002.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    record["entry"]["previous_entry_digest"] = R.sha256_of(b"unrelated")
    record["entry_digest"] = R.sha256_of(R.canonical_bytes(record["entry"]))
    path.write_text(json.dumps(record), encoding="utf-8")

    report, _ = log.scan()
    assert not report.healthy
    assert any("previous_entry_digest" in p for p in report.problems)


def test_existing_entry_is_never_overwritten(log, tmp_path):
    log.append({"operation_id": "op-1"})
    root = tmp_path / "intent"
    before = (root / "000000000001.json").read_bytes()
    log.append({"operation_id": "op-2"})
    assert (root / "000000000001.json").read_bytes() == before


def test_unknown_crash_step_is_rejected():
    with pytest.raises(ValueError):
        D.crash_after("no-such-step")
