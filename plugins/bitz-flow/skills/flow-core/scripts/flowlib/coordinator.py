"""M1 write の coordinator core（FLW-DSN-015）。

単一の authoritative coordinator だけが attempt ID と lease を発行する。本モジュールが持つのは
採番・CAS・fencing token・時刻の**意味論とその不変条件**だけで、永続化そのものは呼出側が渡す
`CasStore` の実装（durable store）に委ねる。

安全側に倒す既定:

- 証明できないものは再発行しない。lease 満了「だけ」では guard を再発行せず、旧 token を
  quarantine へ確定できるまで無期限 BLOCKED を保つ。停止中の旧 command を kill できない環境で
  待たせ続けるのは、二重 write を許すより安全である。
- 時刻の正は coordinator 側にしかない。API は時刻を引数で受け取らないため、runner の local clock を
  正にする経路が構造的に存在しない。
- store へ到達できないときは採番しない（partition 中の offline 採番の禁止）。
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta
from typing import Any, Protocol

LEASE_SECONDS = 24 * 3600
QUALIFICATION_TTL_SECONDS = 24 * 3600
EVIDENCE_TTL_SECONDS = 7 * 24 * 3600

CODE_BLOCKED = "BLOCKED"
CODE_INVALID_INPUT = "INVALID_INPUT"

TTL_KINDS = {
    "qualification": QUALIFICATION_TTL_SECONDS,
    "evidence": EVIDENCE_TTL_SECONDS,
}
#: TTL は trial 開始時と mutation 直前の2点で検査する（片方だけでは drift を検出できない）。
TTL_CHECKPOINTS = frozenset({"start", "pre-mutation"})

NONCE_UNUSED = "UNUSED"
NONCE_USED_PENDING = "USED_PENDING"
NONCE_USED_DONE = "USED_DONE"
NONCE_QUARANTINED = "QUARANTINED"

_STATE_KEY = "coordinator/state"
_NONCE_KEY_PREFIX = "coordinator/nonce/"
_GUARD_KEY_PREFIX = "coordinator/guard/"


class AuthoritativeClock(Protocol):
    """coordinator store 側の時刻。runner の local clock を渡さない。"""

    def now(self) -> datetime: ...


class CasStore(Protocol):
    """linearizable な compare-and-set を提供する永続化層。

    到達不能な場合は例外を送出してよい（coordinator は採番せず BLOCKED を返す）。
    """

    def read(self, key: str) -> tuple[Any | None, int]:
        """(値, version) を返す。未登録なら (None, 0)。"""

    def compare_and_set(self, key: str, expected_version: int, value: Any) -> bool:
        """version が一致したときだけ書き込む。書けたら True。"""


@dataclasses.dataclass(frozen=True)
class CoordinatorFailure:
    """採番・検査の失敗。result envelope への写像は呼出側が行う。"""

    code: str
    reason: str
    stage: str = "validate"
    indefinite: bool = False
    """人間の解除まで自動解消しない BLOCKED であることを示す。"""


@dataclasses.dataclass(frozen=True)
class Attempt:
    attempt_id: int
    epoch_id: str
    leader_epoch: int
    fencing_token: int
    lease_id: str
    issued_at: datetime
    expires_at: datetime


@dataclasses.dataclass(frozen=True)
class ReleaseProof:
    """guard token を再発行してよいことの証明（FLW-DSN-015）。

    lease の満了はこの証明の代わりにならない。coordinator-operator が観測した事実だけを渡す。
    """

    owner_process_exited: bool = False
    child_git_processes_exited: bool = False
    os_lock_released: bool = False
    reconcile_completed: bool = False
    old_token_quarantined: bool = False

    def missing(self) -> list[str]:
        return [f.name for f in dataclasses.fields(self) if not getattr(self, f.name)]


class Coordinator:
    """単一の authoritative coordinator。

    `leader_epoch` は「自分が leader だと思っている世代」で、store 側の値より古ければ
    stale leader として一切の採番を拒否する。
    """

    def __init__(
        self,
        store: CasStore,
        clock: AuthoritativeClock,
        *,
        epoch_id: str,
        leader_epoch: int,
        lease_seconds: int = LEASE_SECONDS,
    ) -> None:
        self._store = store
        self._clock = clock
        self._epoch_id = epoch_id
        self._leader_epoch = leader_epoch
        self._lease_seconds = lease_seconds

    # -- attempt 採番 --------------------------------------------------------

    def issue_attempt(self) -> tuple[Attempt | None, CoordinatorFailure | None]:
        """単調増加の attempt ID と lease、fencing token を発行する。

        欠番を作らないため ID の事前予約は行わず、CAS が通った値だけを採番済みとして扱う。
        """
        try:
            state, version = self._store.read(_STATE_KEY)
        except Exception as exc:  # store 到達不能。offline 採番はしない。
            return None, CoordinatorFailure(
                CODE_BLOCKED, f"coordinator store へ到達できないため採番しない: {type(exc).__name__}"
            )

        state = state or {"leader_epoch": self._leader_epoch, "attempt_counter": 0}

        stored_epoch = int(state.get("leader_epoch", 0))
        if self._leader_epoch < stored_epoch:
            return None, CoordinatorFailure(
                CODE_BLOCKED,
                f"stale leader（自 epoch {self._leader_epoch} < store {stored_epoch}）のため採番しない",
            )

        attempt_id = int(state.get("attempt_counter", 0)) + 1
        issued_at = self._clock.now()
        expires_at = issued_at + timedelta(seconds=self._lease_seconds)
        new_state = {
            "leader_epoch": self._leader_epoch,
            "attempt_counter": attempt_id,
        }

        try:
            committed = self._store.compare_and_set(_STATE_KEY, version, new_state)
        except Exception as exc:
            return None, CoordinatorFailure(
                CODE_BLOCKED, f"採番の CAS が完了を確認できない: {type(exc).__name__}"
            )
        if not committed:
            return None, CoordinatorFailure(
                CODE_BLOCKED, "採番が他の writer と競合した（linearizable CAS 不成立）"
            )

        return (
            Attempt(
                attempt_id=attempt_id,
                epoch_id=self._epoch_id,
                leader_epoch=self._leader_epoch,
                fencing_token=attempt_id,
                lease_id=f"lease:{self._epoch_id}:{attempt_id}",
                issued_at=issued_at,
                expires_at=expires_at,
            ),
            None,
        )

    # -- TTL -----------------------------------------------------------------

    def check_ttl(
        self, *, issued_at: datetime, kind: str, checkpoint: str
    ) -> CoordinatorFailure | None:
        """TTL を検査する。境界時刻ちょうどは**期限切れ**として扱う（安全側）。"""
        if kind not in TTL_KINDS:
            return CoordinatorFailure(CODE_INVALID_INPUT, f"未知の TTL 種別: {kind}")
        if checkpoint not in TTL_CHECKPOINTS:
            return CoordinatorFailure(CODE_INVALID_INPUT, f"未知の検査点: {checkpoint}")

        expires_at = issued_at + timedelta(seconds=TTL_KINDS[kind])
        if self._clock.now() >= expires_at:
            return CoordinatorFailure(
                CODE_BLOCKED,
                f"{kind} の TTL が {checkpoint} 時点で満了しているため不適格",
            )
        return None

    # -- guard token ---------------------------------------------------------

    def reissue_guard_token(
        self, *, target_key: str, proof: ReleaseProof
    ) -> tuple[int | None, CoordinatorFailure | None]:
        """旧 token を quarantine へ確定できた場合だけ新しい fencing token を発行する。"""
        missing = proof.missing()
        if missing:
            return None, CoordinatorFailure(
                CODE_BLOCKED,
                "guard 再発行の証明が不足しているため無期限 BLOCKED: " + ", ".join(missing),
                indefinite=True,
            )

        key = _GUARD_KEY_PREFIX + target_key
        try:
            current, version = self._store.read(key)
            token = int((current or {}).get("token", 0)) + 1
            committed = self._store.compare_and_set(
                key, version, {"token": token, "previous_state": "QUARANTINED"}
            )
        except Exception as exc:
            return None, CoordinatorFailure(
                CODE_BLOCKED, f"guard 状態を確定できない: {type(exc).__name__}", indefinite=True
            )
        if not committed:
            return None, CoordinatorFailure(CODE_BLOCKED, "guard 再発行が競合した")
        return token, None

    # -- 単回 nonce ----------------------------------------------------------

    def begin_nonce(self, nonce: str) -> CoordinatorFailure | None:
        """UNUSED → USED_PENDING。消費済み・確定待ちの nonce は再利用させない。"""
        key = _NONCE_KEY_PREFIX + nonce
        try:
            current, version = self._store.read(key)
            state = (current or {}).get("state", NONCE_UNUSED)
            if state != NONCE_UNUSED:
                return CoordinatorFailure(
                    CODE_BLOCKED,
                    f"nonce は再利用できない（現在の状態 {state}）",
                    indefinite=state == NONCE_USED_PENDING,
                )
            committed = self._store.compare_and_set(key, version, {"state": NONCE_USED_PENDING})
        except Exception as exc:
            return CoordinatorFailure(
                CODE_BLOCKED, f"nonce の消費を確定できない: {type(exc).__name__}"
            )
        if not committed:
            return CoordinatorFailure(CODE_BLOCKED, "nonce の消費が競合した（二重消費の防止）")
        return None

    def finish_nonce(self, nonce: str, *, outcome: str) -> CoordinatorFailure | None:
        """USED_PENDING → USED_DONE / QUARANTINED。"""
        if outcome not in (NONCE_USED_DONE, NONCE_QUARANTINED):
            return CoordinatorFailure(CODE_INVALID_INPUT, f"未知の nonce 終了状態: {outcome}")

        key = _NONCE_KEY_PREFIX + nonce
        try:
            current, version = self._store.read(key)
            state = (current or {}).get("state", NONCE_UNUSED)
            if state != NONCE_USED_PENDING:
                return CoordinatorFailure(
                    CODE_BLOCKED, f"USED_PENDING でない nonce は確定できない（現在 {state}）"
                )
            committed = self._store.compare_and_set(key, version, {"state": outcome})
        except Exception as exc:
            return CoordinatorFailure(
                CODE_BLOCKED, f"nonce の確定を書き込めない: {type(exc).__name__}"
            )
        if not committed:
            return CoordinatorFailure(CODE_BLOCKED, "nonce の確定が競合した")
        return None
