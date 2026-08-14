"""Adapter qualification and requalification rules."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

FAULTS = frozenset({"green", "red", "stale", "unknown"})


@dataclass(frozen=True)
class Qualification:
    compatibility_key: str
    platforms: tuple[str, ...]
    trials_per_platform: int
    fault_matrix: frozenset[str]
    parity: bool

    @property
    def qualified(self) -> bool:
        return (
            bool(self.platforms)
            and self.trials_per_platform >= 3
            and self.fault_matrix == FAULTS
            and self.parity
        )


def qualify(
    trials: Mapping[str, Iterable[Mapping[str, object]]],
    *,
    compatibility_key: str,
) -> Qualification:
    normalized = {platform: list(values) for platform, values in trials.items()}
    platforms = tuple(sorted(normalized))
    flattened = [trial for values in normalized.values() for trial in values]
    faults = frozenset(str(trial.get("verdict", "unknown")).lower() for trial in flattened)
    parity = all(bool(trial.get("required_fields", False)) for trial in flattened)
    minimum_trials = min((len(values) for values in normalized.values()), default=0)
    return Qualification(compatibility_key, platforms, minimum_trials, faults, parity)


def is_current(record: Qualification, current_compatibility_key: str) -> bool:
    return record.qualified and record.compatibility_key == current_compatibility_key
