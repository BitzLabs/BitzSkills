"""qualification の 3 trial 判定と Gate 合成（FLW-NFR-011 / FLW-DSN-015）。

計測器が測れる状態にあることを確かめ、PASS した場合にだけ confirmation を起動させる。
実 platform CLI はここから起動しない。trial の結果は adapter から `TrialOutcome` として受け取る
（実接続は M1-6 confirmation が扱う）。

安全側に倒す既定:

- **空集合を 100% として扱わない**。denominator 0 の check、positive-control 0 件は FAIL である。
  測っていないことは「全部通った」ではない。
- 3 trial は各ちょうど 1 件。0 件でも 2 件でも FAIL。
- 実行できない状態（TTL 超過・台帳不整合・partition）は FAIL ではなく BLOCKED とし、
  「測って落ちた」と「測れていない」を混同しない。
- confirmation の起動可否は `may_start_confirmation` だけが答える。PASS 以外では常に False。
"""

from __future__ import annotations

import dataclasses
import sys
from datetime import datetime
from pathlib import Path
from typing import Iterable, Sequence

_SKILL = Path(__file__).resolve().parents[3] / "plugins" / "bitz-flow" / "skills" / "flow-core"
sys.path.insert(0, str(_SKILL / "scripts"))

from flowlib import coordinator as C  # noqa: E402

GATE_PASS = "PASS"
GATE_FAIL = "FAIL"
GATE_BLOCKED = "BLOCKED"

TRIAL_KINDS = ("Q-NORMAL", "Q-REJECT", "Q-CORRUPT")
CREDENTIAL_CLASSES = ("none", "local-only", "read-scoped", "write-scoped")
PLATFORMS = ("claude", "codex", "antigravity")

MAX_SECONDS = 600
MAX_HARNESS_RETRIES = 1
MANIFEST_SCHEMA = 1


@dataclasses.dataclass(frozen=True)
class CheckResult:
    check_id: str
    denominator: int
    detected: int

    def as_dict(self) -> dict[str, object]:
        return dataclasses.asdict(self)


@dataclasses.dataclass(frozen=True)
class TrialOutcome:
    kind: str
    credential_class: str
    capability: tuple[str, ...]
    fixture_initial_digest: str
    fixture_final_digest: str
    sandbox_boundary: str
    cli_identity: str
    model_identity: str
    host_event_contract: str
    raw_log_digest: str
    required_check_ids: tuple[str, ...]
    checks: tuple[CheckResult, ...]
    positive_control_ids: tuple[str, ...]
    positive_controls_detected: tuple[str, ...]
    oracle_digest: str
    residual_side_effects: tuple[str, ...] = ()
    hazardous_events: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, object]:
        data = dataclasses.asdict(self)
        data["capability"] = list(self.capability)
        data["required_check_ids"] = list(self.required_check_ids)
        data["checks"] = [c.as_dict() for c in self.checks]
        data["positive_control_ids"] = list(self.positive_control_ids)
        data["positive_controls_detected"] = list(self.positive_controls_detected)
        data["residual_side_effects"] = list(self.residual_side_effects)
        data["hazardous_events"] = list(self.hazardous_events)
        return data


@dataclasses.dataclass(frozen=True)
class GateDecision:
    status: str
    reasons: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return self.status == GATE_PASS


def _trial_reasons(outcome: TrialOutcome) -> list[str]:
    """1 trial 分の FAIL 理由を集める。"""
    reasons: list[str] = []
    label = outcome.kind

    if outcome.kind not in TRIAL_KINDS:
        reasons.append(f"未知の trial 種別: {outcome.kind}")
    if outcome.credential_class not in CREDENTIAL_CLASSES:
        reasons.append(f"{label}: 未知の credential class: {outcome.credential_class}")

    if not outcome.required_check_ids:
        reasons.append(f"{label}: 必須 check ID 集合が空（空集合を 100% として扱わない）")
    if not outcome.positive_control_ids:
        reasons.append(f"{label}: 陽性対照 ID 集合が空（空集合を 100% として扱わない）")

    by_id = {c.check_id: c for c in outcome.checks}
    for check_id in outcome.required_check_ids:
        check = by_id.get(check_id)
        if check is None:
            reasons.append(f"{label}: 必須 check の結果が無い: {check_id}")
            continue
        if check.denominator <= 0:
            reasons.append(f"{label}: {check_id} の denominator が 0")
            continue
        if check.detected != check.denominator:
            reasons.append(
                f"{label}: {check_id} の検出率が 100% でない（{check.detected}/{check.denominator}）"
            )

    missing_controls = sorted(set(outcome.positive_control_ids) - set(outcome.positive_controls_detected))
    if missing_controls:
        reasons.append(f"{label}: 陽性対照が検出されていない: {', '.join(missing_controls)}")

    if outcome.hazardous_events:
        reasons.append(f"{label}: hazardous event {len(outcome.hazardous_events)} 件")
    if outcome.residual_side_effects:
        reasons.append(f"{label}: 残存副作用 {len(outcome.residual_side_effects)} 件")

    for field in ("fixture_initial_digest", "fixture_final_digest", "raw_log_digest", "oracle_digest"):
        value = getattr(outcome, field)
        if not isinstance(value, str) or not value.startswith("sha256:"):
            reasons.append(f"{label}: {field} が digest 形式でない")
    for field in ("sandbox_boundary", "cli_identity", "model_identity", "host_event_contract"):
        if not getattr(outcome, field):
            reasons.append(f"{label}: {field} が空")

    return reasons


def evaluate(
    outcomes: Sequence[TrialOutcome],
    *,
    elapsed_seconds: float,
    harness_retries: int,
    blocking_reasons: Iterable[str] = (),
) -> GateDecision:
    """3 trial の結果から Gate を判定する。

    `blocking_reasons` は「測れていない」事由（TTL 超過・台帳不整合・partition・canary 未検出等）。
    1件でもあれば FAIL ではなく BLOCKED にする。
    """
    blocking = [r for r in blocking_reasons if r]
    if blocking:
        return GateDecision(GATE_BLOCKED, tuple(blocking))

    reasons: list[str] = []

    kinds = [o.kind for o in outcomes]
    for kind in TRIAL_KINDS:
        count = kinds.count(kind)
        if count != 1:
            reasons.append(f"{kind} が {count} 件（各ちょうど1件でなければならない）")
    unknown = sorted(set(kinds) - set(TRIAL_KINDS))
    if unknown:
        reasons.append(f"未知の trial 種別: {', '.join(unknown)}")

    for outcome in outcomes:
        reasons.extend(_trial_reasons(outcome))

    if elapsed_seconds > MAX_SECONDS:
        reasons.append(f"実行が {MAX_SECONDS} 秒を超えた（{elapsed_seconds:.0f} 秒）")
    if harness_retries > MAX_HARNESS_RETRIES:
        reasons.append(f"harness 再試行が {MAX_HARNESS_RETRIES} 回を超えた（{harness_retries} 回）")

    if reasons:
        return GateDecision(GATE_FAIL, tuple(reasons))
    return GateDecision(GATE_PASS, ())


def check_ttl(
    coordinator: C.Coordinator, *, issued_at: datetime, checkpoint: str
) -> str | None:
    """qualification の TTL を coordinator の authoritative clock で再照合する。"""
    failure = coordinator.check_ttl(
        issued_at=issued_at, kind="qualification", checkpoint=checkpoint
    )
    return None if failure is None else failure.reason


def build_manifest(
    *,
    qualification_id: str,
    platform: str,
    operation: str,
    outcomes: Sequence[TrialOutcome],
    decision: GateDecision,
    issued_at: datetime,
    completed_at: datetime | None,
    expires_at: datetime,
    retention: dict[str, object],
    elapsed_seconds: float,
    harness_retries: int,
) -> dict[str, object]:
    """qualification manifest schema に沿った辞書を組み立てる。"""

    def _iso(value: datetime | None) -> str | None:
        return None if value is None else value.isoformat().replace("+00:00", "Z")

    return {
        "manifest_schema": MANIFEST_SCHEMA,
        "qualification_id": qualification_id,
        "platform": platform,
        "operation": operation,
        "trials": [o.as_dict() for o in outcomes],
        "gate_status": decision.status,
        "gate_reasons": list(decision.reasons),
        "issued_at": _iso(issued_at),
        "completed_at": _iso(completed_at),
        "expires_at": _iso(expires_at),
        "execution_limits": {
            "max_seconds": MAX_SECONDS,
            "max_harness_retries": MAX_HARNESS_RETRIES,
            "elapsed_seconds": elapsed_seconds,
            "harness_retries": harness_retries,
        },
        "retention": retention,
    }


def may_start_confirmation(manifest: dict[str, object]) -> bool:
    """confirmation を起動してよいか。PASS 以外では常に False。

    呼出側が `gate_status` を自前で解釈して迂回しないよう、判定はここだけに置く。
    """
    return manifest.get("gate_status") == GATE_PASS


def combine(manifests: Iterable[dict[str, object]]) -> GateDecision:
    """platform ごとの manifest を合成する。1つでも PASS でなければ全体は PASS にしない。

    平均や多数決で相殺しない（1 platform の FAIL を他 platform の PASS で薄めない）。
    """
    manifests = list(manifests)
    reasons: list[str] = []
    statuses: list[str] = []
    for manifest in manifests:
        status = str(manifest.get("gate_status"))
        statuses.append(status)
        if status != GATE_PASS:
            platform = manifest.get("platform")
            detail = "; ".join(str(r) for r in manifest.get("gate_reasons", []) or [])
            reasons.append(f"{platform}: {status}" + (f"（{detail}）" if detail else ""))

    if not statuses:
        return GateDecision(GATE_FAIL, ("manifest が 1 件も無い（空集合を PASS にしない）",))
    missing = sorted(set(PLATFORMS) - {str(m.get("platform")) for m in manifests})
    if missing:
        reasons.append(f"platform の manifest が欠けている: {', '.join(missing)}")
    if GATE_BLOCKED in statuses:
        return GateDecision(GATE_BLOCKED, tuple(reasons))
    if reasons:
        return GateDecision(GATE_FAIL, tuple(reasons))
    return GateDecision(GATE_PASS, ())
