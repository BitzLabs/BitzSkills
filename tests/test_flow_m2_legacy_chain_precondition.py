"""FLW-REV-028:GP-004 — 旧形式 chain を前提条件として扱うことを検証する。

旧形式（intent と緊急 receipt を 2 file へ分離 publish する形。`FLW-TSK-118` 以前）の
chain は `inspect()` が fail-closed で `INDETERMINATE` へ閉じる。§4.2 は以前
「doctor が manual rollback 手順を提示する」と書いていたが実装が無く、**設計が存在しない
機能を約束している**状態だった。

M2 は未公開であり旧形式 chain を持つ repository は存在しない。したがって移行手段は
実装せず、§1.2 の公開前提条件として明示する（`FLW-TSK-126` の tmpfs と同じ判断軸で、
発生しない状態のための復旧経路を作らない）。

本テストは (1) fail-closed が回帰していないこと、(2) 設計に存在しない機能の約束が
残っていないこと、(3) 再検討条件が明記されていることを検査する。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "plugins" / "bitz-flow" / ".spec"
DESIGN = SPEC / "design" / "FLW-DSN-017.md"
RUNBOOK = ROOT / "plugins" / "bitz-flow" / "docs" / "runbooks" / "m2-worktree-quarantine.md"
SKILL = ROOT / "plugins" / "bitz-flow" / "skills" / "flow-core"
sys.path.insert(0, str(SKILL / "scripts"))

from flowlib import cli  # noqa: E402
from flowlib import worktree_transaction as T  # noqa: E402

DIGEST = "sha256:" + "a" * 64
TARGET = "sha256:" + "b" * 64


def _design() -> str:
    return DESIGN.read_text(encoding="utf-8")


# --- fail-closed が回帰していないこと ----------------------------------------


def _legacy_chain(tmp_path: Path) -> T.TargetTransaction:
    """現行形式で作ってから同梱 receipt を外し、旧形式 chain を再現する。"""
    root = tmp_path / "tx"
    root.mkdir(mode=0o700)
    transaction = T.TargetTransaction(root, target_collision_key=TARGET)
    lease = transaction.acquire(operation_id=DIGEST, nonce="one")
    transaction.prepare_intent(lease, planned_effects_digest=DIGEST,
                               precondition_digest=TARGET)
    transaction.release(lease)
    intent_file = sorted(transaction._event_dir(DIGEST).glob("*.json"))[-1]
    record = json.loads(intent_file.read_text(encoding="utf-8"))
    record.pop(T.EMERGENCY_RECEIPT_FIELD)          # 旧形式へ戻す
    intent_file.write_text(json.dumps(record), encoding="utf-8")
    return transaction


def test_legacy_chain_still_fails_closed(tmp_path):
    """旧形式 chain を黙って受理しないこと（`FLW-TSK-118` の回帰検出）。"""
    transaction = _legacy_chain(tmp_path)
    report = transaction.inspect(DIGEST)
    assert report.problems, "旧形式を受理している"
    assert report.state == "INDETERMINATE"


def test_legacy_chain_is_not_silently_migrated(tmp_path):
    """推測で現行形式へ移行しないこと。"""
    transaction = _legacy_chain(tmp_path)
    transaction.inspect(DIGEST)
    intent_file = sorted(transaction._event_dir(DIGEST).glob("*.json"))[-1]
    record = json.loads(intent_file.read_text(encoding="utf-8"))
    assert T.EMERGENCY_RECEIPT_FIELD not in record, "inspect が chain を書き換えている"


# --- 前提条件が明示されていること --------------------------------------------


def test_design_declares_the_precondition_in_the_trust_boundary():
    """§1.2 の信頼境界へ公開前提条件が書かれていること。"""
    text = _design()
    boundary = text[text.index("### 1.2 信頼するもの"):text.index("### 1.3 M2で保証しないこと")]
    assert "旧形式" in boundary
    assert "前提条件" in boundary


def test_design_no_longer_promises_an_unimplemented_doctor_migration():
    """存在しない機能の約束が残っていないこと。

    §4.2 は以前「doctor が manual rollback 手順を提示する」と書いていたが実装が無かった。
    §12（ロールバック）の pre-v2 runtime に関する記述は別の話なので、§4.2 だけを見る。
    """
    text = _design()
    section = text[text.index("### 4.2 "):text.index("## 5. contract bundle")]
    assert "manual rollback手順を\n提示する" not in section
    assert "実装しない理由" in section


def test_design_records_the_condition_to_revisit():
    """実装しない判断の再検討条件が明記されていること。"""
    text = _design()
    section = text[text.index("### 4.2 "):text.index("## 5. contract bundle")]
    assert "再検討の条件" in section


def test_precondition_holds_today_because_no_write_operation_is_published():
    """前提が今日成立している根拠を機械で確かめる。

    chain を作るのは **write operation** だけである。read-only 3 件は 2026-08-24 に
    限定公開したが、`create` / `resume` が非公開である限り新しい chain は生まれず、
    旧形式 chain も生まれない。前提条件が依存しているのは「worktree が全て gated」では
    なく「**write が未公開**」である。
    """
    published = {f"{domain}.{action}" for domain, action in cli.PUBLISHED_OPERATIONS}
    writers = {"worktree.create", "worktree.resume", "worktree.reconcile"}
    assert not (published & writers), (
        f"chain を作る operation が公開されている {published & writers}。"
        "旧形式 chain の前提条件を再検討すること"
    )


def test_runbook_tells_the_operator_what_a_legacy_chain_looks_like():
    """運用者が旧形式 chain を踏んだときに判別できること。"""
    assert "旧形式" in RUNBOOK.read_text(encoding="utf-8")
