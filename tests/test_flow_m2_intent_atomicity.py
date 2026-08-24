"""SI-FLW-087 — intent と緊急 receipt の間に crash 空隙が無いことを検証する。

`FLW-REV-027:SYN-004`（P1）。旧実装は `INTENT_DURABLE` event の atomic publish と
緊急 receipt の atomic publish を **2 回に分けて** 行っていた。その 2 回の間で停止すると

- Git 副作用は証明可能に 0 件（`mark_mutating` が `require_emergency=True` を要求する）
- しかし nonce は `INTENT_DURABLE` 公開時点で消費済み
- chain 検査は「緊急 receipt がちょうど 1 件でない」として `INDETERMINATE`

となり、**副作用ゼロの target が同一 plan では二度と実行できないまま隔離**された。

`FLW-DSN-017` §4.2（`FLW-GATE-006` で承認）に従い 1 回の atomic publish へ統合した。
本テストは 4 つの publish step すべてで停止させ、不変条件を検査する。

  intent が確定したなら、必ず有効な緊急 receipt が付いている。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / "plugins" / "bitz-flow" / "skills" / "flow-core"
sys.path.insert(0, str(SKILL / "scripts"))

from flowlib import worktree_transaction as T  # noqa: E402
from flowlib.worktree_contract import canonical_json_bytes, sha256_digest  # noqa: E402

DIGEST = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64


def _transaction(tmp_path: Path) -> T.TargetTransaction:
    root = tmp_path / "tx"
    root.mkdir(mode=0o700)
    return T.TargetTransaction(root, target_collision_key=DIGEST_B)


def _emergency(report) -> list:
    return [r for r in report.receipts if r["receipt_state"] == "INDETERMINATE"]


@pytest.mark.parametrize("crash_step", T.PUBLISH_STEPS)
def test_no_crash_point_leaves_a_durable_intent_without_an_emergency_receipt(tmp_path, crash_step):
    """全 publish step で停止させても回収不能状態が生じないこと。

    これが `SI-FLW-087` の中心的な受入基準である。
    """
    tx = _transaction(tmp_path)
    lease = tx.acquire(operation_id=DIGEST, nonce="one")

    def crash(step, _path):
        if step == crash_step:
            raise RuntimeError("crash")

    tx._hook = crash
    with pytest.raises(RuntimeError, match="crash"):
        tx.prepare_intent(lease, planned_effects_digest=DIGEST,
                          precondition_digest=DIGEST_B)
    tx._hook = None

    report = tx.inspect(DIGEST)
    assert not report.problems, f"{crash_step}: chain が不健全 {report.problems}"
    assert report.state in {"LOCKED", "INTENT_DURABLE"}
    if report.state == "INTENT_DURABLE":
        assert len(_emergency(report)) == 1, (
            f"{crash_step}: intent 確定なのに緊急 receipt が無い（回収不能）"
        )
    else:
        assert not _emergency(report), f"{crash_step}: intent 未確定なのに receipt がある"
    tx.release(lease)


def test_healthy_intent_binds_nonce_and_emergency_receipt_together(tmp_path):
    """nonce の消費と緊急 receipt の有効化が不可分であること。"""
    tx = _transaction(tmp_path)
    lease = tx.acquire(operation_id=DIGEST, nonce="one")
    tx.prepare_intent(lease, planned_effects_digest=DIGEST, precondition_digest=DIGEST_B)
    report = tx.inspect(DIGEST)
    assert report.state == "INTENT_DURABLE"
    assert len(_emergency(report)) == 1
    intent_event = report.events[-1]
    assert intent_event["intent"]["nonce_digest"] == lease.nonce_digest
    tx.release(lease)


def test_intent_and_emergency_receipt_live_in_one_file(tmp_path):
    """2 回 publish が復活していないこと（file 数で確認する）。"""
    tx = _transaction(tmp_path)
    lease = tx.acquire(operation_id=DIGEST, nonce="one")
    tx.prepare_intent(lease, planned_effects_digest=DIGEST, precondition_digest=DIGEST_B)
    tx.release(lease)
    receipt_dir = tx._receipt_dir(DIGEST)
    separate = list(receipt_dir.glob("*.json")) if receipt_dir.exists() else []
    assert not separate, f"緊急 receipt が別 file になっている: {separate}"
    events = sorted(tx._event_dir(DIGEST).glob("*.json"))
    intent_file = json.loads(events[-1].read_text(encoding="utf-8"))
    assert T.EMERGENCY_RECEIPT_FIELD in intent_file


def test_embedded_receipt_binds_the_core_record_digest(tmp_path):
    """同梱 receipt の `event_digest` が core record（同梱前）の digest を指すこと。"""
    tx = _transaction(tmp_path)
    lease = tx.acquire(operation_id=DIGEST, nonce="one")
    tx.prepare_intent(lease, planned_effects_digest=DIGEST, precondition_digest=DIGEST_B)
    tx.release(lease)
    path = sorted(tx._event_dir(DIGEST).glob("*.json"))[-1]
    raw = json.loads(path.read_text(encoding="utf-8"))
    embedded = raw.pop(T.EMERGENCY_RECEIPT_FIELD)
    assert embedded["event_digest"] == sha256_digest(canonical_json_bytes(raw))
    assert path.name.endswith(embedded["event_digest"][7:] + ".json")


# --- 旧形式の fail-closed ----------------------------------------------------


def test_legacy_intent_without_embedded_receipt_fails_closed(tmp_path):
    """旧形式 chain を推測移行せず fail-closed にすること。"""
    tx = _transaction(tmp_path)
    lease = tx.acquire(operation_id=DIGEST, nonce="one")
    tx.prepare_intent(lease, planned_effects_digest=DIGEST, precondition_digest=DIGEST_B)
    tx.release(lease)
    path = sorted(tx._event_dir(DIGEST).glob("*.json"))[-1]
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw.pop(T.EMERGENCY_RECEIPT_FIELD)          # 旧形式へ戻す
    path.write_text(json.dumps(raw), encoding="utf-8")
    report = tx.inspect(DIGEST)
    assert report.problems, "旧形式を黙って受理してはならない"
    assert report.state == "INDETERMINATE"


def test_emergency_receipt_cannot_be_reintroduced_as_a_separate_file(tmp_path):
    """別 file から緊急 receipt を持ち込めないこと（2 回 publish の空隙の復活防止）。"""
    tx = _transaction(tmp_path)
    lease = tx.acquire(operation_id=DIGEST, nonce="one")
    tx.prepare_intent(lease, planned_effects_digest=DIGEST, precondition_digest=DIGEST_B)
    tx.release(lease)
    path = sorted(tx._event_dir(DIGEST).glob("*.json"))[-1]
    embedded = json.loads(path.read_text(encoding="utf-8"))[T.EMERGENCY_RECEIPT_FIELD]
    receipt_dir = tx._receipt_dir(DIGEST)
    receipt_dir.mkdir(parents=True, exist_ok=True)
    digest = sha256_digest(canonical_json_bytes(embedded))
    (receipt_dir / f"{digest[7:]}.json").write_text(json.dumps(embedded), encoding="utf-8")
    report = tx.inspect(DIGEST)
    assert report.problems, "別 file の緊急 receipt を受理してはならない"


def test_non_intent_records_may_not_embed_an_emergency_receipt(tmp_path):
    """intent 以外の record への同梱を拒否すること。"""
    tx = _transaction(tmp_path)
    lease = tx.acquire(operation_id=DIGEST, nonce="one")
    tx.prepare_intent(lease, planned_effects_digest=DIGEST, precondition_digest=DIGEST_B)
    tx.mark_mutating(lease)
    tx.release(lease)
    path = sorted(tx._event_dir(DIGEST).glob("*.json"))[-1]
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw[T.EMERGENCY_RECEIPT_FIELD] = {"receipt_state": "INDETERMINATE"}
    path.write_text(json.dumps(raw), encoding="utf-8")
    assert tx.inspect(DIGEST).problems

# --- 同梱 receipt の改竄検出 --------------------------------------------------
#
# 下流の「緊急 receipt はちょうど 1 件」検査だけでは、**個数は合っているが中身が
# 別 intent を指す** receipt を見逃す。同梱そのものを検証する必要がある。


def _tamper_embedded(tmp_path: Path, mutate) -> object:
    tx = _transaction(tmp_path)
    lease = tx.acquire(operation_id=DIGEST, nonce="one")
    tx.prepare_intent(lease, planned_effects_digest=DIGEST, precondition_digest=DIGEST_B)
    tx.release(lease)
    path = sorted(tx._event_dir(DIGEST).glob("*.json"))[-1]
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw[T.EMERGENCY_RECEIPT_FIELD] = mutate(dict(raw[T.EMERGENCY_RECEIPT_FIELD]))
    path.write_text(json.dumps(raw), encoding="utf-8")
    return tx.inspect(DIGEST)


def test_embedded_receipt_pointing_at_another_intent_is_rejected(tmp_path):
    """`event_digest` が この intent を指さない同梱 receipt を拒否すること。"""
    def mutate(receipt):
        receipt["event_digest"] = DIGEST_B
        return receipt
    report = _tamper_embedded(tmp_path, mutate)
    assert report.problems, "別 intent を指す同梱 receipt を受理してはならない"


def test_embedded_receipt_must_be_an_emergency_receipt(tmp_path):
    """同梱枠に TERMINAL receipt を置けないこと。"""
    def mutate(receipt):
        receipt["receipt_state"] = "TERMINAL"
        receipt["supersedes_receipt_digest"] = DIGEST_B
        return receipt
    report = _tamper_embedded(tmp_path, mutate)
    assert report.problems, "同梱枠の TERMINAL receipt を受理してはならない"


@pytest.mark.parametrize("mutate,label", [
    (lambda r: {k: v for k, v in r.items() if k != "fencing_token"}, "missing-field"),
    (lambda r: {**r, "unexpected": 1}, "unknown-field"),
    (lambda r: {**r, "operation_id": "not-a-digest"}, "bad-operation-id"),
    (lambda r: {**r, "contract_version": 99}, "bad-contract-version"),
])
def test_malformed_embedded_receipt_is_rejected(tmp_path, mutate, label):
    """壊れた同梱 receipt を黙って受理しないこと。"""
    report = _tamper_embedded(tmp_path, mutate)
    assert report.problems, f"{label}: 壊れた同梱 receipt を受理してはならない"
