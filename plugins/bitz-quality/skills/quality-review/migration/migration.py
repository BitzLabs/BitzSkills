"""Migration and removal gates for the legacy sdd-review path."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MigrationEvidence:
    dual_read: bool
    lossless_export: bool
    golden_corpus: bool
    rollback_rehearsed: bool
    recovery_bundle: bool
    observation_days: int

    @property
    def reversible(self) -> bool:
        return (
            (self.dual_read or self.lossless_export)
            and self.golden_corpus
            and self.rollback_rehearsed
            and self.recovery_bundle
            and self.observation_days > 0
        )


def removal_allowed(*, bitz_sdd_gate: bool, bitz_quality_gate: bool, evidence: MigrationEvidence) -> bool:
    """Removal requires both workspace gates and complete migration evidence."""
    return bitz_sdd_gate and bitz_quality_gate and evidence.reversible


def rollback_mode(*, point_of_no_return: bool) -> str:
    return "forward-fix" if point_of_no_return else "downgrade-rehearsed"
