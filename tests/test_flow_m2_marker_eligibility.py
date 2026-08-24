"""SI-FLW-089 — reconcile closure が marker 適格性確認より先行しないことを検証する。

`FLW-REV-027:SYN-006`（P1）。`reconcile()` は

  target lock → 再 audit → **closure 追記（不可逆）** → target lock 解放
  → promotion lock → marker 解放

の順で進み、marker の適格性を検査するのは最後の `release_reconciled_operation` だった。
marker 欠落・不正・不一致は **closure を追記した後** に判明する。不可逆な追記が
適格性確認より先行していた。

lock order 不変条件（target lock と promotion lock を同時に保持しない）は維持する。
"""

from __future__ import annotations

import ast
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "plugins" / "bitz-flow" / "skills" / "flow-core"
RECOVERY_SOURCE = SKILL / "scripts" / "flowlib" / "worktree_recovery.py"
sys.path.insert(0, str(SKILL / "scripts"))

from flowlib import worktree_promotion as P  # noqa: E402
from flowlib import worktree_recovery as RC  # noqa: E402
from flowlib import worktree_runtime as R  # noqa: E402
from flowlib import worktree_transaction as T  # noqa: E402

DIGEST = "sha256:" + "a" * 64
BUNDLE = "sha256:" + "b" * 64
OTHER_BUNDLE = "sha256:" + "d" * 64
REPOSITORY = "sha256:" + "c" * 64


def _snapshot(suffix: str = "0") -> R.RepositorySnapshot:
    return R.RepositorySnapshot(
        suffix * 40, "sha256:" + suffix * 64, "sha256:" + suffix * 64,
        "sha256:" + suffix * 64,
    )


def _interrupted(tmp_path: Path, observed, *, register: bool = True):
    """crash で marker を保持したままの operation を作る。"""
    tx = T.TargetTransaction(tmp_path / "authority", target_collision_key="target-1")
    lease = tx.acquire(operation_id=DIGEST, nonce="mutation-nonce")
    tx.prepare_intent(lease, planned_effects_digest=BUNDLE,
                      precondition_digest=observed.digest)
    tx.release(lease)
    if register:
        P.register_active_operation(tmp_path / "common", operation_id=DIGEST,
                                    bundle_digest=BUNDLE)
    return tx


def _plan(tmp_path: Path, tx, observed, *, bundle: str = BUNDLE, bind_marker: bool = True):
    marker = None
    if bind_marker:
        marker = P.inspect_active_marker(tmp_path / "common", operation_id=DIGEST)
    report = RC.audit(tx, operation_id=DIGEST, observed_snapshot=observed,
                      active_marker=marker)
    return RC.build_reconcile_plan(
        audit_report=report, decision=report.classification,
        repository_identity=REPOSITORY,
        expires_at=(datetime.now(timezone.utc) + timedelta(minutes=5))
        .isoformat().replace("+00:00", "Z"),
        nonce="reconcile-nonce", bundle_digest=bundle,
    )


def _run(tmp_path: Path, tx, plan, observed):
    return RC.reconcile(
        transaction=tx, plan=plan, confirm=plan.context.operation_id,
        now=datetime.now(timezone.utc), nonce_unused=True,
        observe=lambda: observed, common_dir=str(tmp_path / "common"),
    )


def _closures(tx) -> int:
    return len(tx.inspect(DIGEST).closures)


# --- marker 欠落・不一致では closure 0 件 ------------------------------------


def test_missing_marker_appends_no_closure(tmp_path):
    """marker が無い operation へ reconcile を案内しないこと。"""
    observed = _snapshot()
    tx = _interrupted(tmp_path, observed, register=False)
    plan = _plan(tmp_path, tx, observed, bind_marker=False)
    with pytest.raises(RC.RecoveryError, match="crash-held"):
        _run(tmp_path, tx, plan, observed)
    assert _closures(tx) == 0, "不適格なのに closure が追記された"


def test_marker_for_another_bundle_appends_no_closure(tmp_path):
    """別 bundle の marker へ reconcile しないこと。"""
    observed = _snapshot()
    tx = _interrupted(tmp_path, observed)
    plan = _plan(tmp_path, tx, observed, bundle=OTHER_BUNDLE)
    with pytest.raises(RC.RecoveryError, match="bundle"):
        _run(tmp_path, tx, plan, observed)
    assert _closures(tx) == 0


def test_marker_replaced_after_the_audit_appends_no_closure(tmp_path):
    """audit 後に marker が差し替わったら closure を追記しないこと。"""
    observed = _snapshot()
    tx = _interrupted(tmp_path, observed)
    plan = _plan(tmp_path, tx, observed)
    marker = tmp_path / "common" / P.PROMOTION_RELATIVE_PATH / "active" / f"{DIGEST[7:]}.json"
    payload = json.loads(marker.read_text(encoding="utf-8"))
    payload["contract_version"] = 99            # audit 時と異なる内容へ差し替える
    marker.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(RC.RecoveryError, match="changed since the audit"):
        _run(tmp_path, tx, plan, observed)
    assert _closures(tx) == 0


def test_normal_completion_is_not_offered_for_reconcile(tmp_path):
    """正常 `DONE` で marker が解放済みの operation へ案内しないこと。"""
    observed = _snapshot()
    tx = _interrupted(tmp_path, observed)
    plan = _plan(tmp_path, tx, observed)
    P.release_active_operation(tmp_path / "common", operation_id=DIGEST,
                               terminal_receipt_digest=BUNDLE)
    with pytest.raises(RC.RecoveryError, match="crash-held"):
        _run(tmp_path, tx, plan, observed)
    assert _closures(tx) == 0


# --- 陽性対照と冪等性 --------------------------------------------------------


def test_eligible_marker_produces_exactly_one_closure(tmp_path):
    """適格な marker では closure が 1 件だけ作られること（過剰な拒否の検出）。"""
    observed = _snapshot()
    tx = _interrupted(tmp_path, observed)
    plan = _plan(tmp_path, tx, observed)
    result = _run(tmp_path, tx, plan, observed)
    assert result.closure_digest
    assert _closures(tx) == 1


def test_retry_after_marker_release_converges_on_a_single_closure(tmp_path):
    """closure 済み・marker 解放済みの再試行が単一 closure へ収束すること。"""
    observed = _snapshot()
    tx = _interrupted(tmp_path, observed)
    plan = _plan(tmp_path, tx, observed)
    first = _run(tmp_path, tx, plan, observed)
    second = _run(tmp_path, tx, plan, observed)
    assert second.closure_digest == first.closure_digest
    assert _closures(tx) == 1


def test_retry_after_closure_before_marker_release_converges(tmp_path, monkeypatch):
    """closure 後・marker closure 前の crash が再試行で収束すること。"""
    observed = _snapshot()
    tx = _interrupted(tmp_path, observed)
    plan = _plan(tmp_path, tx, observed)
    real_release = P.release_reconciled_operation
    calls = {"n": 0}

    def crash_once(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise P.PromotionError("INDETERMINATE", "injected crash")
        return real_release(*args, **kwargs)

    monkeypatch.setattr(RC.P, "release_reconciled_operation", crash_once)
    with pytest.raises(RC.RecoveryError):
        _run(tmp_path, tx, plan, observed)
    assert _closures(tx) == 1
    monkeypatch.setattr(RC.P, "release_reconciled_operation", real_release)
    _run(tmp_path, tx, plan, observed)
    assert _closures(tx) == 1, "再試行で closure が増えてはならない"


# --- lock order 不変条件 -----------------------------------------------------


def test_marker_inspection_happens_before_the_target_lock(tmp_path):
    """適格性検査が target lock 取得より前に置かれていること（source 上の順序）。"""
    source = RECOVERY_SOURCE.read_text(encoding="utf-8")
    body = source[source.index("def reconcile(*, transaction"):]
    inspect_at = body.index("inspect_active_marker(")
    lock_at = body.index("acquire_reconcile(")
    closure_at = body.index("transaction.reconcile(")
    assert inspect_at < lock_at < closure_at, (
        "marker 適格性検査が target lock / closure より後にある"
    )


def test_promotion_lock_is_never_held_while_holding_the_target_lock(tmp_path):
    """target lock 保持中に promotion lock を取らないこと。

    `acquire_reconcile` と `transaction.release(lease)` の間に promotion 系の
    呼び出しが現れないことを AST で検査する。
    """
    tree = ast.parse(RECOVERY_SOURCE.read_text(encoding="utf-8"))
    func = next(n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == "reconcile")
    source = RECOVERY_SOURCE.read_text(encoding="utf-8")
    segment = ast.get_source_segment(source, func) or ""
    held = segment[segment.index("acquire_reconcile("):segment.index("transaction.release(lease)")]
    for forbidden in ("inspect_active_marker(", "release_reconciled_operation(",
                      "register_active_operation(", "release_active_operation("):
        assert forbidden not in held, (
            f"target lock 保持中に promotion lock を取っている: {forbidden}"
        )
