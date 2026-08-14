"""M2 write前 reconnaissance と運用証跡（FLW-NFR-004 / 008）。"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from datetime import datetime, timedelta
from typing import Any, Iterable


@dataclasses.dataclass(frozen=True)
class ReconnaissanceLimits:
    deadline_seconds: float
    max_items: int
    absolute_bytes: int

    def valid(self) -> bool:
        return self.deadline_seconds > 0 and self.max_items > 0 and self.absolute_bytes > 0


@dataclasses.dataclass(frozen=True)
class InFlightWork:
    branch: str
    work_id: str | None
    paths: tuple[str, ...]
    worktree_present: bool
    pushed: bool
    pr_present: bool


@dataclasses.dataclass(frozen=True)
class ReconnaissanceResult:
    code: str
    items: tuple[InFlightWork, ...] = ()
    overlaps: tuple[str, ...] = ()
    reason: str = ""
    complete: bool = False


def inspect_in_flight(
    *,
    candidates: Iterable[InFlightWork],
    touched_paths: Iterable[str],
    limits: ReconnaissanceLimits | None,
    elapsed_seconds: float,
    observed_bytes: int,
    source_complete: bool,
) -> ReconnaissanceResult:
    """local-only branchを含むin-flight作業を上限付きで列挙する。"""
    if limits is None or not limits.valid():
        return ReconnaissanceResult("BLOCKED", reason="active benchmark manifestの上限が無効")
    items = tuple(candidates)
    if not source_complete:
        return ReconnaissanceResult("INDETERMINATE", reason="列挙結果が完全でない")
    if elapsed_seconds > limits.deadline_seconds:
        return ReconnaissanceResult("BLOCKED", reason="reconnaissance timeout")
    if len(items) > limits.max_items or observed_bytes > limits.absolute_bytes:
        return ReconnaissanceResult("BLOCKED", reason="reconnaissance budget超過")

    targets = tuple(_normalize_path(path) for path in touched_paths)
    overlaps = sorted(
        {
            item.branch
            for item in items
            if any(_paths_overlap(target, _normalize_path(path)) for target in targets for path in item.paths)
        }
    )
    return ReconnaissanceResult("DONE", items, tuple(overlaps), complete=True)


def authorize_write_entry(result: ReconnaissanceResult | None) -> str:
    """reconnaissanceを省略・打切りしたwrite WorkUnitを開始させない。"""
    return "DONE" if result is not None and result.code == "DONE" and result.complete else "BLOCKED"


def _normalize_path(path: str) -> tuple[str, ...]:
    return tuple(part for part in path.replace("\\", "/").strip("/").split("/") if part and part != ".")


def _paths_overlap(left: tuple[str, ...], right: tuple[str, ...]) -> bool:
    shortest = min(len(left), len(right))
    return left[:shortest] == right[:shortest]


def quarantine_escalation(*, detected_at: datetime, now: datetime, unresolved: bool) -> str:
    """2営業日相当（安全側に48時間）またはunresolvedをownerへ即時上申する。"""
    return "ESCALATE" if unresolved or now - detected_at >= timedelta(hours=48) else "MONITOR"


@dataclasses.dataclass(frozen=True)
class EvidenceEntry:
    payload: dict[str, Any]
    previous_digest: str | None
    digest: str


class EvidenceChain:
    """append-only証跡chain。読出し時に先頭から全entryを再検証する。"""

    def __init__(self) -> None:
        self._entries: list[EvidenceEntry] = []

    @staticmethod
    def _digest(payload: dict[str, Any], previous: str | None) -> str:
        body = json.dumps(
            {"payload": payload, "previous_digest": previous},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return "sha256:" + hashlib.sha256(body).hexdigest()

    def append(self, payload: dict[str, Any]) -> EvidenceEntry:
        previous = self._entries[-1].digest if self._entries else None
        entry = EvidenceEntry(dict(payload), previous, self._digest(payload, previous))
        self._entries.append(entry)
        return entry

    def entries(self) -> tuple[EvidenceEntry, ...]:
        return tuple(self._entries)

    @classmethod
    def verify(cls, entries: Iterable[EvidenceEntry]) -> str:
        previous = None
        for entry in entries:
            if entry.previous_digest != previous or entry.digest != cls._digest(entry.payload, previous):
                return "INDETERMINATE"
            previous = entry.digest
        return "DONE"
