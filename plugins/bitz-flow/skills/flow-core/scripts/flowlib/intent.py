"""durable intent と quarantine のライフサイクル（FLW-DSN-015）。

write 状態機械の不変条件を担当する。永続化そのものは durable store に委ねる。

```
PLANNED → GUARDED → PENDING_INTENT → MUTATING → RECONCILING
                                                   ├→ DONE
                                                   ├→ PARTIAL
                                                   ├→ STALE
                                                   └→ QUARANTINED → (人間解除)
```

安全側に倒す既定:

- **`PENDING_INTENT` の永続化前に副作用を開始できない**。durable store の `Commit` が無ければ
  `MUTATING` へ進めない構造にする。副作用前に中断しても intent が残る方を、
  「記録なしの重複 write」より優先する。
- `PARTIAL` / `STALE` からの**自動再 apply を禁止**する。read-only の reconcile か、
  人間が確認した新しい plan だけを許す。
- quarantine の解除は観測結論と必須証跡が揃った場合のみ。`unresolved` は解除できない。
- 解除後の mutation には**新しい operation ID** と単回 capability を要求する。旧 ID を再利用しない。
"""

from __future__ import annotations

import dataclasses
from datetime import datetime
from typing import Any, Iterable, Sequence

from . import durable as D
from . import result as R

CODE_BLOCKED = "BLOCKED"
CODE_INVALID_INPUT = "INVALID_INPUT"
CODE_INDETERMINATE = "INDETERMINATE"

# write_state（closed enum。正は schemas/result-v1.schema.json）
PLANNED = "PLANNED"
GUARDED = "GUARDED"
PENDING_INTENT = "PENDING_INTENT"
MUTATING = "MUTATING"
RECONCILING = "RECONCILING"
DONE = "DONE"
PARTIAL = "PARTIAL"
STALE = "STALE"
QUARANTINED = "QUARANTINED"
WRITE_STATES = (
    PLANNED, GUARDED, PENDING_INTENT, MUTATING, RECONCILING, DONE, PARTIAL, STALE, QUARANTINED
)

#: durable intent を必須とする状態。
_REQUIRES_INTENT = frozenset({PENDING_INTENT, MUTATING, RECONCILING, PARTIAL, STALE, QUARANTINED})
#: 次回の同 target write を BLOCKED にする状態。
_BLOCKS_NEXT_WRITE = frozenset({PENDING_INTENT, MUTATING, RECONCILING, QUARANTINED})
#: 自動での再 apply を許さない状態。
_NO_AUTO_REAPPLY = frozenset({PARTIAL, STALE, QUARANTINED})

_ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    PLANNED: frozenset({GUARDED}),
    GUARDED: frozenset({PENDING_INTENT}),
    PENDING_INTENT: frozenset({MUTATING}),
    MUTATING: frozenset({RECONCILING}),
    RECONCILING: frozenset({DONE, PARTIAL, STALE, QUARANTINED}),
    DONE: frozenset(),
    PARTIAL: frozenset(),
    STALE: frozenset(),
    QUARANTINED: frozenset(),
}

# intent_record_state（正は schemas/intent-record-v1.schema.json）
RECORD_PENDING = "PENDING"
RECORD_RECONCILING = "RECONCILING"
RECORD_PARTIAL = "PARTIAL"
RECORD_STALE = "STALE"
RECORD_QUARANTINED = "QUARANTINED"
RECORD_RELEASED = "RELEASED"
INTENT_RECORD_STATES = (
    RECORD_PENDING, RECORD_RECONCILING, RECORD_PARTIAL, RECORD_STALE, RECORD_QUARANTINED,
    RECORD_RELEASED,
)

_RECORD_STATE_FOR = {
    PENDING_INTENT: RECORD_PENDING,
    MUTATING: RECORD_PENDING,
    RECONCILING: RECORD_RECONCILING,
    DONE: RECORD_RELEASED,
    PARTIAL: RECORD_PARTIAL,
    STALE: RECORD_STALE,
    QUARANTINED: RECORD_QUARANTINED,
}

#: quarantine の観測結論 → 解除に必要な承認者（`unresolved` は解除不可）。
CONCLUSION_APPROVERS: dict[str, tuple[str, ...]] = {
    "confirmed-done": ("evaluation-reviewer",),
    "no-effect": ("evaluation-reviewer",),
    "orphan-object-no-reachable-effect": ("repository-owner", "evaluation-reviewer"),
    "abandoned-with-compensation": ("repository-owner", "evaluation-reviewer"),
    "unresolved": (),
}
#: 結論ごとに必須となる証跡。
CONCLUSION_EVIDENCE: dict[str, tuple[str, ...]] = {
    "confirmed-done": ("intent", "cas_receipt", "current_ref", "object", "fencing"),
    "no-effect": ("snapshot_unchanged", "no_side_effect"),
    "orphan-object-no-reachable-effect": ("planned_oid_unreachable", "old_ref_unchanged", "object_exists", "gc_not_running"),
    "abandoned-with-compensation": ("compensating_operation_id", "compensating_result"),
    "unresolved": (),
}


@dataclasses.dataclass(frozen=True)
class IntentFailure:
    code: str
    reason: str


@dataclasses.dataclass(frozen=True)
class Capability:
    """quarantine 解除後の mutation を1回だけ許す authorization capability。"""

    target: str
    snapshot_digest: str
    prior_operation_id: str
    reviewer: str
    expires_at: datetime
    nonce: str
    algorithm: str = "Ed25519"
    key_id: str = ""
    signature: str = ""


@dataclasses.dataclass
class WriteIntent:
    operation_id: str
    targets: tuple[dict[str, str], ...]
    snapshot_digest: str
    expected_effect_digest: str
    state: str = PLANNED
    commit: D.Commit | None = None
    receipt_digest: str | None = None
    conclusion: str | None = None

    @property
    def requires_intent(self) -> bool:
        return self.state in _REQUIRES_INTENT

    @property
    def blocks_next_write(self) -> bool:
        return self.state in _BLOCKS_NEXT_WRITE

    @property
    def allows_auto_reapply(self) -> bool:
        return self.state not in _NO_AUTO_REAPPLY


class IntentStore:
    """intent の記録と状態遷移。既存 record を上書きせず追記する。"""

    def __init__(self, log: D.DurableLog, *, repo_identity: dict[str, Any], owner_process: str) -> None:
        self._log = log
        self._repo_identity = repo_identity
        self._owner_process = owner_process

    # -- 記録 ----------------------------------------------------------------

    def open(
        self,
        *,
        operation_id: str,
        targets: Sequence[dict[str, str]],
        snapshot_digest: str,
        expected_effect_digest: str,
    ) -> WriteIntent:
        return WriteIntent(
            operation_id=operation_id,
            targets=tuple(targets),
            snapshot_digest=snapshot_digest,
            expected_effect_digest=expected_effect_digest,
        )

    def transition(
        self,
        intent: WriteIntent,
        to_state: str,
        *,
        fencing_tokens: dict[str, int] | None = None,
        created_at: str = "",
        receipt_digest: str | None = None,
    ) -> IntentFailure | None:
        """状態遷移を検査し、必要なら durable な record を追記する。"""
        if to_state not in WRITE_STATES:
            return IntentFailure(CODE_INVALID_INPUT, f"未知の write_state: {to_state}")
        allowed = _ALLOWED_TRANSITIONS[intent.state]
        if to_state not in allowed:
            return IntentFailure(
                CODE_INVALID_INPUT, f"許されない遷移: {intent.state} → {to_state}"
            )

        if to_state == PENDING_INTENT:
            record = {
                "schema_version": 1,
                "operation_id": intent.operation_id,
                "repo_identity": self._repo_identity,
                "targets": [dict(t) for t in intent.targets],
                "fencing_tokens": dict(fencing_tokens or {}),
                "snapshot_digest": intent.snapshot_digest,
                "expected_effect_digest": intent.expected_effect_digest,
                "intent_record_state": RECORD_PENDING,
                "created_at": created_at,
                "owner_process": self._owner_process,
                "receipt_digest": None,
            }
            commit, failure = self._log.append(record)
            if failure is not None:
                # commit point に達していないので副作用を開始させない。
                return IntentFailure(CODE_BLOCKED, f"intent を永続化できない: {failure.reason}")
            intent.commit = commit
        elif to_state == MUTATING and intent.commit is None:
            return IntentFailure(
                CODE_BLOCKED,
                "durable intent の commit point に到達していないため mutation を開始しない",
            )
        elif to_state in _RECORD_STATE_FOR and to_state != PENDING_INTENT:
            record = {
                "schema_version": 1,
                "operation_id": intent.operation_id,
                "intent_record_state": _RECORD_STATE_FOR[to_state],
                "receipt_digest": receipt_digest,
            }
            _, failure = self._log.append(record)
            if failure is not None:
                return IntentFailure(CODE_BLOCKED, f"状態を追記できない: {failure.reason}")

        intent.state = to_state
        if receipt_digest is not None:
            intent.receipt_digest = receipt_digest
        return None

    # -- 解除 ----------------------------------------------------------------

    def release(self, intent: WriteIntent) -> IntentFailure | None:
        """DONE または副作用不成立を証明できた場合だけ intent を解除する。"""
        if intent.state != DONE:
            return IntentFailure(
                CODE_BLOCKED, f"{intent.state} の intent は解除しない（証跡として保持する）"
            )
        if intent.receipt_digest is None:
            return IntentFailure(
                CODE_INDETERMINATE,
                "receipt が無い状態を DONE と推定しない",
            )
        return None

    # -- quarantine -----------------------------------------------------------

    def quarantine_release(
        self,
        intent: WriteIntent,
        *,
        conclusion: str,
        evidence: Iterable[str],
        approvers: Iterable[str],
        reviewer: str,
        old_token: int,
        new_token: int,
        at: str,
    ) -> tuple[dict[str, Any] | None, IntentFailure | None]:
        """quarantine を解除し、解除 receipt を hash-chain へ追記する。"""
        if intent.state != QUARANTINED:
            return None, IntentFailure(CODE_INVALID_INPUT, "quarantine 中でない intent は解除しない")
        if conclusion not in CONCLUSION_APPROVERS:
            return None, IntentFailure(CODE_INVALID_INPUT, f"未知の観測結論: {conclusion}")

        required_approvers = CONCLUSION_APPROVERS[conclusion]
        if not required_approvers:
            return None, IntentFailure(
                CODE_BLOCKED, "unresolved は解除できない（quarantine を継続する）"
            )

        missing_approvers = sorted(set(required_approvers) - set(approvers))
        if missing_approvers:
            return None, IntentFailure(
                CODE_BLOCKED, "承認が不足している: " + ", ".join(missing_approvers)
            )

        missing_evidence = sorted(set(CONCLUSION_EVIDENCE[conclusion]) - set(evidence))
        if missing_evidence:
            return None, IntentFailure(
                CODE_BLOCKED, "必須証跡が不足している: " + ", ".join(missing_evidence)
            )

        receipt = {
            "schema_version": 1,
            "operation_id": intent.operation_id,
            "intent_record_state": RECORD_RELEASED,
            "release_conclusion": conclusion,
            "reviewer": reviewer,
            "evidence_digest": R.sha256_of(R.canonical_bytes(sorted(evidence))),
            "old_fencing_token": old_token,
            "new_fencing_token": new_token,
            "released_at": at,
        }
        _, failure = self._log.append(receipt)
        if failure is not None:
            return None, IntentFailure(CODE_BLOCKED, f"解除 receipt を追記できない: {failure.reason}")

        intent.conclusion = conclusion
        return receipt, None


# --- 解除後の mutation --------------------------------------------------------


def authorize_mutation(
    capability: Capability,
    *,
    target: str,
    snapshot_digest: str,
    new_operation_id: str,
    prior_operation_id: str,
    now: datetime,
    trusted_key_ids: Sequence[str],
    nonce_state: str,
) -> IntentFailure | None:
    """quarantine 解除後の mutation を許してよいか検査する。

    署名の暗号検証そのものは範囲外で、ここでは**受け入れ条件**を機械化する。
    """
    if capability.target != target:
        return IntentFailure(CODE_BLOCKED, "capability の target が一致しない（別 target への転用）")
    if capability.snapshot_digest != snapshot_digest:
        return IntentFailure(CODE_BLOCKED, "capability の snapshot が現在の観測と一致しない")
    if capability.prior_operation_id != prior_operation_id:
        return IntentFailure(CODE_BLOCKED, "capability が参照する旧 operation が一致しない")
    if new_operation_id == prior_operation_id:
        return IntentFailure(
            CODE_BLOCKED, "解除後の mutation には新しい operation ID を要求する（旧 ID の再利用は不可）"
        )
    if now >= capability.expires_at:
        return IntentFailure(CODE_BLOCKED, "capability の有効期限が切れている")
    if capability.algorithm != "Ed25519":
        return IntentFailure(CODE_BLOCKED, f"許可されない署名方式: {capability.algorithm}")
    if capability.key_id not in trusted_key_ids:
        return IntentFailure(CODE_BLOCKED, "失効または未登録の署名鍵")
    if nonce_state != "UNUSED":
        return IntentFailure(
            CODE_BLOCKED, f"capability の nonce は再利用できない（現在の状態 {nonce_state}）"
        )
    return None
