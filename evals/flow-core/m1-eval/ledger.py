"""evidence ledger の合成と candidate 選択（FLW-NFR-011 / FLW-DSN-015）。

合成器が守るのは一点に尽きる: **結果の選り好みをさせない**。

同じ目的に対して複数の attempt が存在するとき、「一番良かったもの」を Gate へ出せてしまうと、
測定は事実の記録ではなく願望の記録になる。そこで `evaluation_objective_id` ごとの
**最初の適格 attempt** を candidate に固定し、後から来た良い結果でそれを置換しない。

安全側に倒す既定:

- **FAIL を PASS へ置換しない**。再実行には新しい confirmation epoch と compatibility key を要求する。
  key や epoch を変えただけで失敗履歴をリセットすることも許さない。
- **再試行は1回だけ**。事前拘束した instrument / environment failure に一致し、かつ
  **被測定物 event が 0 件**の場合に限る。被測定物が動いた形跡があれば、それは測定結果である。
- **late-evidence は candidate を置換しない**。partition から復旧して届いた PASS は追記するが、
  すでに `UNKNOWN` で確定した candidate を書き換えない。
- 既存 entry を**上書きしない**。訂正は訂正 entry の追記で表す。
"""

from __future__ import annotations

import dataclasses
from typing import Iterable, Mapping, Sequence

STATUS_STARTED = "STARTED"
STATUS_PASS = "PASS"
STATUS_FAIL = "FAIL"
STATUS_ABORTED = "ABORTED"
STATUS_UNKNOWN = "UNKNOWN"
ATTEMPT_STATUSES = (STATUS_STARTED, STATUS_PASS, STATUS_FAIL, STATUS_ABORTED, STATUS_UNKNOWN)

#: candidate になり得る終了状態。STARTED（未終了）と UNKNOWN は candidate にしない。
_TERMINAL = frozenset({STATUS_PASS, STATUS_FAIL})

GATE_BLOCKED = "BLOCKED"


@dataclasses.dataclass(frozen=True)
class LedgerFailure:
    code: str
    reason: str


@dataclasses.dataclass(frozen=True)
class Attempt:
    attempt_id: int
    objective_id: str
    epoch_id: str
    compatibility_key: str
    platform: str
    status: str
    eligibility_rule_id: str = "rule-1"
    retryable_failure_codes: tuple[str, ...] = ()
    failure_code: str | None = None
    failure_axis: tuple[str, ...] = ()
    subject_events: int = 0
    retry_of: int | None = None
    late: bool = False

    @property
    def terminal(self) -> bool:
        return self.status in _TERMINAL


@dataclasses.dataclass(frozen=True)
class RetryDecision:
    allowed: bool
    reason: str


class Ledger:
    """正本台帳。追記のみで、既存 entry を書き換えない。"""

    def __init__(self) -> None:
        self._entries: list[Attempt] = []
        self._corrections: list[dict[str, object]] = []
        self._retry_consumed: set[int] = set()

    # -- 登録 ----------------------------------------------------------------

    @property
    def entries(self) -> tuple[Attempt, ...]:
        return tuple(self._entries)

    def register(self, attempt: Attempt) -> LedgerFailure | None:
        if attempt.status not in ATTEMPT_STATUSES:
            return LedgerFailure("INVALID_INPUT", f"未知の attempt_status: {attempt.status}")
        if any(e.attempt_id == attempt.attempt_id for e in self._entries):
            return LedgerFailure(GATE_BLOCKED, f"attempt ID が重複している: {attempt.attempt_id}")

        # FAIL 済みの objective へ、同じ epoch / key で PASS を登録させない。
        if attempt.status == STATUS_PASS:
            failed = [
                e for e in self._entries
                if e.objective_id == attempt.objective_id and e.status == STATUS_FAIL
            ]
            same_context = [
                e for e in failed
                if e.epoch_id == attempt.epoch_id and e.compatibility_key == attempt.compatibility_key
            ]
            if same_context and attempt.retry_of is None:
                return LedgerFailure(
                    GATE_BLOCKED,
                    "同じ epoch / compatibility key で FAIL を PASS へ置換できない"
                    "（新しい confirmation epoch と key を要求する）",
                )

        self._entries.append(attempt)
        return None

    def append_correction(self, attempt_id: int, *, new_classification: str, rationale: str) -> None:
        """failure 分類の訂正。旧 entry を書き換えず追記で表す。"""
        self._corrections.append(
            {"attempt_id": attempt_id, "classification": new_classification, "rationale": rationale}
        )

    @property
    def corrections(self) -> tuple[dict[str, object], ...]:
        return tuple(self._corrections)

    # -- candidate -----------------------------------------------------------

    def candidate_for(self, objective_id: str) -> Attempt | None:
        """objective ごとの**最初の適格 attempt**を返す。

        後から届いた結果（late-evidence）で置換しない。
        """
        for entry in self._entries:
            if entry.objective_id != objective_id:
                continue
            if entry.late:
                continue
            if not entry.terminal:
                continue
            if entry.attempt_id in self._retry_consumed:
                # 再試行のために non-candidate terminal として確定させた attempt。
                continue
            return entry
        return None

    def late_evidence_for(self, objective_id: str) -> tuple[Attempt, ...]:
        return tuple(e for e in self._entries if e.objective_id == objective_id and e.late)

    # -- 再試行 --------------------------------------------------------------

    def may_retry(self, attempt: Attempt) -> RetryDecision:
        """再試行してよいか。事前拘束と被測定物 event の有無で決める。"""
        if attempt.subject_events > 0:
            return RetryDecision(
                False, "被測定物の event を取得しているため測定結果である（再試行しない）"
            )
        if attempt.failure_code is None:
            return RetryDecision(False, "failure 分類が unknown のため再試行しない")
        if attempt.failure_code not in attempt.retryable_failure_codes:
            return RetryDecision(
                False, f"事前拘束していない failure code: {attempt.failure_code}"
            )
        if len(set(attempt.failure_axis)) > 1:
            return RetryDecision(False, "複数の failure 軸が競合しているため再試行しない")
        if attempt.attempt_id in self._retry_consumed:
            return RetryDecision(False, "この attempt の retry slot は消費済み")
        if attempt.retry_of is not None:
            return RetryDecision(False, "再試行の後継をさらに再試行しない（最大1件）")
        return RetryDecision(True, "instrument / environment failure かつ被測定物 event 0 件")

    def consume_retry(
        self, attempt: Attempt, *, successor_id: int
    ) -> tuple[Attempt | None, LedgerFailure | None]:
        """retry slot を消費して後継を1件だけ発行する。元 attempt は無効化せず併記する。"""
        decision = self.may_retry(attempt)
        if not decision.allowed:
            return None, LedgerFailure(GATE_BLOCKED, decision.reason)

        self._retry_consumed.add(attempt.attempt_id)
        successor = dataclasses.replace(
            attempt, attempt_id=successor_id, status=STATUS_STARTED,
            retry_of=attempt.attempt_id, failure_code=None, failure_axis=(),
        )
        failure = self.register(successor)
        if failure is not None:
            self._retry_consumed.discard(attempt.attempt_id)
            return None, failure
        return successor, None

    def successors_of(self, attempt_id: int) -> tuple[Attempt, ...]:
        return tuple(e for e in self._entries if e.retry_of == attempt_id)

    # -- 中断・partition -----------------------------------------------------

    def mark_unknown(self, attempt_id: int, *, reason: str) -> LedgerFailure | None:
        """終了 entry を持たない attempt に UNKNOWN を追記する（既存 entry は書き換えない）。"""
        original = next((e for e in self._entries if e.attempt_id == attempt_id), None)
        if original is None:
            return LedgerFailure(GATE_BLOCKED, f"未登録の attempt: {attempt_id}")
        if original.status != STATUS_STARTED:
            return LedgerFailure(
                GATE_BLOCKED, f"STARTED でない attempt を UNKNOWN にしない（現在 {original.status}）"
            )
        index = self._entries.index(original)
        self._entries[index] = dataclasses.replace(original, status=STATUS_UNKNOWN)
        self.append_correction(attempt_id, new_classification=STATUS_UNKNOWN, rationale=reason)
        return None

    # -- 双方向照合 ----------------------------------------------------------

    def reconcile(
        self, partial: Mapping[str, Sequence[int]], *, chain_intact: bool = True
    ) -> LedgerFailure | None:
        """platform 部分台帳と正本を突き合わせる。"""
        if not chain_intact:
            return LedgerFailure(GATE_BLOCKED, "hash-chain が破損している")

        authoritative = {e.attempt_id for e in self._entries}
        by_platform: dict[str, set[int]] = {}
        for platform, ids in partial.items():
            seen: set[int] = set()
            for attempt_id in ids:
                if attempt_id in seen:
                    return LedgerFailure(
                        GATE_BLOCKED, f"{platform} の部分台帳に重複 ID がある: {attempt_id}"
                    )
                seen.add(attempt_id)
            by_platform[platform] = seen

        for platform, ids in by_platform.items():
            missing = sorted(ids - authoritative)
            if missing:
                return LedgerFailure(
                    GATE_BLOCKED,
                    f"{platform} に正本未取込の attempt がある: {missing}",
                )

        covered = set().union(*by_platform.values()) if by_platform else set()
        orphan = sorted(authoritative - covered)
        if orphan:
            return LedgerFailure(
                GATE_BLOCKED, f"どの platform 部分台帳にも現れない attempt がある: {orphan}"
            )

        if authoritative:
            expected = set(range(1, max(authoritative) + 1))
            gaps = sorted(expected - authoritative)
            if gaps:
                return LedgerFailure(GATE_BLOCKED, f"attempt ID に欠番がある: {gaps}")

        return None
