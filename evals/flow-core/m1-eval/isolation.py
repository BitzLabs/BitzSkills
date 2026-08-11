"""qualification trial の隔離 namespace 割り当てと残存副作用検査（FLW-NFR-011 / FLW-NFR-012）。

trial 同士が干渉すると、測定結果は「被測定物の性質」ではなく「実行順序」を測ってしまう。
platform × operation × trial ごとに独立した repo / remote namespace を割り当て、
同じ lease に拘束したまま fixture 作成から mutation までを行い、終了時に初期状態へ
戻っていることを確かめる。

安全側に倒す既定:

- run ID は暗号論的乱数から作る。連番や決定論的な値は他 trial から**推測できてしまう**ため、
  隔離の前提が崩れる。
- lease は coordinator core が発行したものを受け取るだけで、harness 側では採番しない。
  lease が切り替わった・期限切れになった場合は継続せず BLOCKED にする。
- 各 mutation の直前に ref / HEAD を CAS 再照合する。照合できなければ mutation を実行しない。
- 残存副作用が 1 件でもあれば PASS にしない。
"""

from __future__ import annotations

import dataclasses
import secrets
import sys
from pathlib import Path
from typing import Any, Iterable

_SKILL = Path(__file__).resolve().parents[3] / "plugins" / "bitz-flow" / "skills" / "flow-core"
sys.path.insert(0, str(_SKILL / "scripts"))

from flowlib import result as R  # noqa: E402

CODE_BLOCKED = "BLOCKED"
CODE_INVALID_INPUT = "INVALID_INPUT"

TRIAL_KINDS = ("Q-NORMAL", "Q-REJECT", "Q-CORRUPT")
#: run ID のエントロピー。推測可能な値を避けるための下限。
RUN_ID_BYTES = 16


@dataclasses.dataclass(frozen=True)
class IsolationFailure:
    code: str
    reason: str


@dataclasses.dataclass(frozen=True)
class Lease:
    """coordinator core が発行した lease の写し（harness 側では作らない）。"""

    lease_id: str
    expires_at: Any

    def same_as(self, other: "Lease | None") -> bool:
        return other is not None and other.lease_id == self.lease_id


@dataclasses.dataclass(frozen=True)
class Namespace:
    platform: str
    operation: str
    trial_kind: str
    run_id: str
    owner: str
    lease_id: str
    repo_namespace: str
    remote_namespace: str

    @property
    def sandbox_boundary(self) -> str:
        """manifest の sandbox_boundary へそのまま載せる識別子。"""
        return f"{self.repo_namespace}|{self.remote_namespace}"


@dataclasses.dataclass
class TrialScope:
    """fixture 作成から mutation 完了までを1つの lease に拘束する作業単位。"""

    namespace: Namespace
    lease: Lease
    initial_digest: str | None = None
    final_digest: str | None = None
    released: bool = False


def new_run_id() -> str:
    """推測不能な run ID。"""
    return secrets.token_hex(RUN_ID_BYTES)


def fixture_digest(entries: Iterable[tuple[str, str]]) -> str:
    """fixture の状態を (path, 内容 digest) の列から canonical に要約する。"""
    return R.sha256_of(R.canonical_bytes(sorted(entries)))


class IsolationAllocator:
    """trial ごとの namespace を払い出し、解放漏れを検出する。"""

    def __init__(self, owner: str) -> None:
        self._owner = owner
        self._active: dict[str, TrialScope] = {}

    # -- 払い出し ------------------------------------------------------------

    def allocate(
        self, *, platform: str, operation: str, trial_kind: str, lease: Lease
    ) -> tuple[TrialScope | None, IsolationFailure | None]:
        if trial_kind not in TRIAL_KINDS:
            return None, IsolationFailure(CODE_INVALID_INPUT, f"未知の trial 種別: {trial_kind}")
        if not lease.lease_id:
            return None, IsolationFailure(
                CODE_BLOCKED, "lease を取得していない状態で namespace を払い出さない"
            )

        run_id = new_run_id()
        namespace = Namespace(
            platform=platform,
            operation=operation,
            trial_kind=trial_kind,
            run_id=run_id,
            owner=self._owner,
            lease_id=lease.lease_id,
            repo_namespace=f"qual-{platform}-{operation.replace('.', '-')}-{trial_kind.lower()}-{run_id}",
            remote_namespace=f"bitz-flow-qual/{run_id}",
        )
        scope = TrialScope(namespace=namespace, lease=lease)
        self._active[run_id] = scope
        return scope, None

    def release(self, scope: TrialScope) -> None:
        """解放は冪等。"""
        scope.released = True
        self._active.pop(scope.namespace.run_id, None)

    def unreleased(self) -> list[str]:
        """解放漏れの run ID。"""
        return sorted(self._active)

    # -- lease 拘束 ----------------------------------------------------------

    def check_lease(self, scope: TrialScope, current: Lease | None) -> IsolationFailure | None:
        """fixture 作成時と同じ lease のままかを確かめる。"""
        if not scope.lease.same_as(current):
            return IsolationFailure(
                CODE_BLOCKED,
                "lease が fixture 作成時から切り替わったため trial を継続しない",
            )
        return None

    # -- mutation 直前の CAS 再照合 -------------------------------------------

    def guard_mutation(
        self, scope: TrialScope, *, current: Lease | None, expected_ref: str, observed_ref: str | None
    ) -> IsolationFailure | None:
        """mutation の直前に lease と ref / HEAD を再照合する。

        `observed_ref` が None（照合できない）ときは mutation を実行させない。
        """
        failure = self.check_lease(scope, current)
        if failure is not None:
            return failure
        if observed_ref is None:
            return IsolationFailure(
                CODE_BLOCKED, "ref / HEAD を再照合できないため mutation を実行しない"
            )
        if observed_ref != expected_ref:
            return IsolationFailure(
                CODE_BLOCKED, "mutation 直前の ref / HEAD が plan 時点と一致しない（TOCTOU）"
            )
        return None

    # -- 残存副作用 ----------------------------------------------------------

    def finish(
        self, scope: TrialScope, *, final_digest: str, declared_effects: Iterable[str] = ()
    ) -> list[str]:
        """終了時の残存副作用を返す（空なら副作用なし）。"""
        scope.final_digest = final_digest
        residual: list[str] = []
        if scope.initial_digest is None:
            residual.append("初期 digest が記録されていないため副作用の有無を判定できない")
        elif scope.initial_digest != final_digest:
            declared = list(declared_effects)
            if declared:
                residual.append(
                    "fixture が初期状態へ戻っていない（宣言された effects: " + ", ".join(declared) + "）"
                )
            else:
                residual.append("fixture が初期状態へ戻っていない（宣言外の変更）")
        return residual
