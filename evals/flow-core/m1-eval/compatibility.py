"""compatibility key v1 と失効規則（FLW-NFR-011 / FLW-DSN-015）。

「この証跡を再利用してよいか」を決める鍵。**再利用の可否を人の記憶や勘で決めさせない**ために、
何が同じなら同じと見なすかを閉集合として固定する。

安全側に倒す既定:

- **欠落・未知 field は互換と見なさない**。「知らない field があるが他は同じだから互換」という
  判断をしない。閉集合の外側は常に `blocked`。
- credential や rate-limit 残量のような**短命状態を key に含めない**。含めると同じ環境でも
  key が揺れて再利用が成立しない。代わりに合成の直前に dynamic fingerprint で再照合する。
- `evidence_id`（raw log digest・attempt ID・run 固有 metadata）と**分離**する。混ぜると
  「同じ条件の別 run」を同一視できなくなる。
"""

from __future__ import annotations

import dataclasses
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping

_SKILL = Path(__file__).resolve().parents[3] / "plugins" / "bitz-flow" / "skills" / "flow-core"
sys.path.insert(0, str(_SKILL / "scripts"))

from flowlib import result as R  # noqa: E402

STATUS_COMPATIBLE = "compatible"
STATUS_INCOMPATIBLE = "incompatible"
STATUS_BLOCKED = "blocked"

#: compatibility key を構成する閉集合（13要素）。ここに無い field は key に入れない。
KEY_FIELDS = (
    "scoring_rule",
    "runner",
    "adapter",
    "oracle",
    "fixture",
    "prompt",
    "skill",
    "result_schema",
    "event_schema",
    "transitive_dependencies",
    "model_identity",
    "cli_version",
    "host_event_contract_version",
    "trial_assignment",
)

#: 変更されると **全 platform** の証跡を失効させる共通入力。
COMMON_FIELDS = frozenset({
    "scoring_rule", "runner", "oracle", "fixture", "prompt", "skill",
    "result_schema", "event_schema", "transitive_dependencies", "trial_assignment",
})
#: 変更されても **当該 platform だけ** を失効させる platform 固有入力。
PLATFORM_FIELDS = frozenset({
    "adapter", "model_identity", "cli_version", "host_event_contract_version",
})

#: key に含めない短命状態。合成直前の dynamic fingerprint で再照合する。
EPHEMERAL_FIELDS = frozenset({
    "credential_class", "credential", "rate_limit_remaining", "quota_remaining",
    "started_at", "hostname", "pid",
})


@dataclasses.dataclass(frozen=True)
class KeyResult:
    status: str
    key: str | None
    reasons: tuple[str, ...] = ()

    @property
    def usable(self) -> bool:
        return self.status == STATUS_COMPATIBLE


@dataclasses.dataclass(frozen=True)
class Invalidation:
    """失効の判定結果。"""

    scope: str  # "all-platforms" / "single-platform" / "none"
    platforms: tuple[str, ...]
    changed_fields: tuple[str, ...]

    @property
    def invalidates_everything(self) -> bool:
        return self.scope == "all-platforms"


def build_key(inputs: Mapping[str, Any]) -> KeyResult:
    """閉集合の全 field が揃っている場合だけ key を作る。"""
    reasons: list[str] = []

    missing = [name for name in KEY_FIELDS if name not in inputs]
    if missing:
        reasons.append("欠落 field: " + ", ".join(sorted(missing)))

    unknown = [
        name for name in inputs
        if name not in KEY_FIELDS and name not in EPHEMERAL_FIELDS
    ]
    if unknown:
        reasons.append("未知 field: " + ", ".join(sorted(unknown)))

    ephemeral = [name for name in inputs if name in EPHEMERAL_FIELDS]
    if ephemeral:
        # 短命状態は key に含めないだけで、渡されること自体は許す（呼出側の利便）。
        pass

    if reasons:
        return KeyResult(STATUS_BLOCKED, None, tuple(reasons))

    payload = {name: inputs[name] for name in KEY_FIELDS}
    return KeyResult(STATUS_COMPATIBLE, R.sha256_of(R.canonical_bytes(payload)), ())


def compare(before: Mapping[str, Any], after: Mapping[str, Any]) -> KeyResult:
    """2つの入力集合が互換かを判定する。"""
    left = build_key(before)
    right = build_key(after)
    if not left.usable:
        return KeyResult(STATUS_BLOCKED, None, left.reasons)
    if not right.usable:
        return KeyResult(STATUS_BLOCKED, None, right.reasons)
    if left.key == right.key:
        return KeyResult(STATUS_COMPATIBLE, left.key, ())
    changed = tuple(sorted(n for n in KEY_FIELDS if before.get(n) != after.get(n)))
    return KeyResult(STATUS_INCOMPATIBLE, None, ("変更された field: " + ", ".join(changed),))


def invalidation_for(
    before: Mapping[str, Any], after: Mapping[str, Any], *, platform: str
) -> Invalidation:
    """何が変わったかから失効範囲を決める。

    共通入力が1つでも変われば全 platform。platform 固有入力だけなら当該 platform だけ。
    """
    changed = tuple(sorted(n for n in KEY_FIELDS if before.get(n) != after.get(n)))
    if not changed:
        return Invalidation("none", (), ())
    if any(name in COMMON_FIELDS for name in changed):
        return Invalidation("all-platforms", (), changed)
    return Invalidation("single-platform", (platform,), changed)


def dynamic_fingerprint(state: Mapping[str, Any]) -> str:
    """合成直前に再照合する短命状態の指紋。compatibility key とは別物。"""
    payload = {name: state[name] for name in sorted(state) if name in EPHEMERAL_FIELDS}
    return R.sha256_of(R.canonical_bytes(payload))


def evidence_id(*, raw_log_digest: str, attempt_id: int, run_metadata: Mapping[str, Any]) -> str:
    """個別 run の同一性。compatibility key と混ぜない。"""
    return R.sha256_of(
        R.canonical_bytes(
            {"raw_log_digest": raw_log_digest, "attempt_id": attempt_id,
             "run_metadata": dict(run_metadata)}
        )
    )


def reusable_platforms(
    stored: Mapping[str, Mapping[str, Any]], current: Mapping[str, Any], *, changed_platform: str
) -> tuple[list[str], list[str]]:
    """保存済み証跡のうち再利用できる platform と、再実測が要る platform を返す。"""
    reusable: list[str] = []
    stale: list[str] = []
    for platform, inputs in sorted(stored.items()):
        merged = dict(current)
        merged.update({k: v for k, v in inputs.items() if k in PLATFORM_FIELDS})
        invalidation = invalidation_for(inputs, merged, platform=platform)
        if invalidation.scope == "none":
            reusable.append(platform)
        elif invalidation.scope == "single-platform" and platform != changed_platform:
            reusable.append(platform)
        else:
            stale.append(platform)
    return reusable, stale
