"""BitzSDD V4 review profile (contract version 1)."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

PROFILE_ID = "bitz-sdd-v4@1"
PERSPECTIVES = (
    "consistency",
    "data-integrity",
    "operations",
    "risk",
    "business",
    "system-engineering",
    "measurability",
)
THRESHOLDS = {
    "aggregate_min": 4.50,
    "perspective_min": 4.00,
    "critical_max": 0,
    "major_max": 0,
    "untracked_p0_p1_max": 0,
}


def profile_digest() -> str:
    payload = {"id": PROFILE_ID, "perspectives": PERSPECTIVES, "thresholds": THRESHOLDS}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def evaluate(
    scores: Mapping[str, float],
    *,
    aggregate: float,
    critical: int = 0,
    major: int = 0,
    untracked_p0_p1: int = 0,
    sample_size: int = 0,
    charter_status: str = "confirmed",
) -> dict[str, Any]:
    """Evaluate a V4 review and return a reproducible, fail-closed result."""
    missing = [name for name in PERSPECTIVES if name not in scores]
    if charter_status != "confirmed":
        verdict = "CONTRACT_PENDING"
        reason = "V4 Charter or public port is not confirmed"
    elif missing or sample_size <= 0:
        verdict = "BLOCKED"
        reason = "required perspective or measurement sample is missing"
    elif (
        aggregate < THRESHOLDS["aggregate_min"]
        or any(scores[name] < THRESHOLDS["perspective_min"] for name in PERSPECTIVES)
        or critical > THRESHOLDS["critical_max"]
        or major > THRESHOLDS["major_max"]
        or untracked_p0_p1 > THRESHOLDS["untracked_p0_p1_max"]
    ):
        verdict = "FAIL"
        reason = "one or more V4 gate thresholds are unmet"
    else:
        verdict = "PASS"
        reason = "all V4 gate thresholds are met"
    return {
        "profile": PROFILE_ID,
        "profile_digest": profile_digest(),
        "verdict": verdict,
        "reason": reason,
        "thresholds": THRESHOLDS,
        "perspectives": list(PERSPECTIVES),
        "scores": dict(scores),
        "aggregate": aggregate,
        "critical": critical,
        "major": major,
        "untracked_p0_p1": untracked_p0_p1,
        "sample_size": sample_size,
    }
