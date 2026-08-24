"""TargetTransaction authority for M2 (FLW-TSK-108).

This module deliberately has no Git or subprocess capability. It owns the target lock,
monotonic fencing counter, append-only journal, receipts, and reconcile closure.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping

from .worktree_contract import (
    CONTRACT_VERSION, EVENT_STATES, MAX_UINT64, ContractError, canonical_json_bytes,
    sha256_digest, validate_digest, validate_mutation_receipt,
    validate_operation_event, validate_uint64_string,
)

PHASES = ("LOCKED", "INTENT_DURABLE", "MUTATING", "RESULT_DURABLE", "DONE")
QUARANTINE_PHASES = ("LOCKED", "INTENT_DURABLE", "MUTATING", "RESULT_DURABLE", "QUARANTINED")
PUBLISH_STEPS = ("temp-written", "file-fsynced", "renamed", "dir-fsynced")

#: INTENT_DURABLE event へ同梱する緊急 receipt の field 名（`SI-FLW-087`）。
#: 旧形式は intent と緊急 receipt を 2 回に分けて publish しており、その間で停止すると
#: 「Git 副作用 0 件・nonce 消費済み・INDETERMINATE」という回収不能状態が生じた。
EMERGENCY_RECEIPT_FIELD = "emergency_receipt"


class TransactionError(RuntimeError):
    def __init__(self, code: str, cause: str):
        super().__init__(cause)
        self.code = code
        self.cause = cause


@dataclass(frozen=True)
class LeaseContext:
    operation_id: str
    target_collision_key: str
    fencing_token: str
    nonce_digest: str
    _lock_stream: object
    purpose: str = "mutation"


@dataclass(frozen=True)
class ChainReport:
    events: tuple[dict[str, object], ...]
    receipts: tuple[dict[str, object], ...]
    closures: tuple[dict[str, object], ...]
    head_digest: str | None
    problems: tuple[str, ...]

    @property
    def healthy(self) -> bool:
        return not self.problems

    @property
    def state(self) -> str:
        if self.problems:
            return "INDETERMINATE"
        return str(self.events[-1]["event"]["state"]) if self.events else "EMPTY"


def _fsync_dir(path: Path) -> None:
    try:
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except OSError as exc:
        raise TransactionError("UNSUPPORTED_FILESYSTEM", "directory durability unavailable") from exc


def _lock(stream: object) -> bool:
    if os.name == "nt":  # pragma: no cover - Windows fixture runner
        import msvcrt
        try:
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            return True
        except OSError:
            return False
    import fcntl
    try:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except BlockingIOError:
        return False


def _unlock(stream: object) -> None:
    if os.name == "nt":  # pragma: no cover - Windows fixture runner
        import msvcrt
        stream.seek(0)
        msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl
        fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


class TargetTransaction:
    """One local authority for a canonical target collision key."""

    def __init__(self, root: str | Path, *, target_collision_key: str,
                 step_hook: Callable[[str, Path], None] | None = None) -> None:
        if not isinstance(target_collision_key, str) or not target_collision_key:
            raise ContractError("target collision key is required")
        self.root = Path(root)
        self.target_collision_key = target_collision_key
        self._hook = step_hook
        self._lease: LeaseContext | None = None

    def acquire(self, *, operation_id: str, nonce: str,
                timeout_seconds: float = 0.0) -> LeaseContext:
        if self._lease is not None:
            raise TransactionError("BLOCKED_LOCK_BUSY", "authority already holds target lock")
        validate_digest(operation_id)
        if not nonce:
            raise ContractError("nonce is required")
        self._prepare_root()
        lock_path = self.root / "target.lock"
        descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
        stream = os.fdopen(descriptor, "r+b", buffering=0)
        if os.name != "nt" and lock_path.stat().st_mode & 0o077:
            stream.close()
            raise TransactionError("UNSUPPORTED_FILESYSTEM", "target lock is not owner-only")
        if lock_path.stat().st_size == 0:
            stream.write(b"0")
            os.fsync(stream.fileno())
        deadline = time.monotonic() + max(0.0, timeout_seconds)
        while not _lock(stream):
            if time.monotonic() >= deadline:
                stream.close()
                raise TransactionError("BLOCKED_LOCK_BUSY", "target lock timeout")
            time.sleep(min(0.01, max(0.0, deadline - time.monotonic())))
        try:
            lease = LeaseContext(
                operation_id, self.target_collision_key, self._issue_fencing_token(),
                sha256_digest(nonce.encode("utf-8")), stream,
            )
            self._lease = lease
            self._append_event(lease, "LOCKED")
            return lease
        except Exception:
            _unlock(stream)
            stream.close()
            self._lease = None
            raise

    def acquire_reconcile(self, *, operation_id: str, expected_fencing_token: str,
                          expected_head_digest: str,
                          timeout_seconds: float = 0.0) -> LeaseContext:
        """Reacquire the target lock after a crash without extending the mutation journal."""
        if self._lease is not None:
            raise TransactionError("BLOCKED_LOCK_BUSY", "authority already holds target lock")
        validate_digest(operation_id)
        validate_digest(expected_head_digest)
        validate_uint64_string(expected_fencing_token)
        self._prepare_root()
        stream = self._acquire_lock_stream(timeout_seconds)
        try:
            report = self.inspect(operation_id)
            if not report.events or report.problems:
                raise TransactionError(
                    "INDETERMINATE", "; ".join(report.problems) or "empty journal"
                )
            actual_token = str(report.events[0]["event"]["fencing_token"])
            if actual_token != expected_fencing_token or report.head_digest != expected_head_digest:
                raise TransactionError("STALE", "reconcile journal head or fencing token changed")
            if self._current_fencing_token() != expected_fencing_token:
                raise TransactionError("STALE", "a newer target fencing token exists")
            lease = LeaseContext(
                operation_id, self.target_collision_key, expected_fencing_token,
                sha256_digest(b"reconcile"), stream, "reconcile",
            )
            self._lease = lease
            return lease
        except Exception:
            _unlock(stream)
            stream.close()
            self._lease = None
            raise

    def release(self, lease: LeaseContext) -> None:
        self._require_lease(lease)
        _unlock(lease._lock_stream)
        lease._lock_stream.close()
        self._lease = None

    def prepare_intent(self, lease: LeaseContext, *, planned_effects_digest: str,
                       precondition_digest: str) -> str:
        self._require_state(lease, "LOCKED")
        validate_digest(planned_effects_digest)
        validate_digest(precondition_digest)
        if self._nonce_was_consumed(lease.nonce_digest):
            raise TransactionError("STALE", "nonce was already consumed")
        def emergency(event_digest: str) -> dict[str, object]:
            return {
                "contract_version": CONTRACT_VERSION,
                "operation_id": lease.operation_id,
                "target_collision_key": lease.target_collision_key,
                "receipt_state": "INDETERMINATE",
                "event_digest": event_digest,
                "supersedes_receipt_digest": None,
                "fencing_token": lease.fencing_token,
            }

        # intent と緊急 receipt は 1 回の atomic publish で同時に確定する。
        # 中間状態が存在しないため、nonce の消費と緊急 receipt の有効化は不可分になる。
        event_digest = self._append_event(
            lease, "INTENT_DURABLE",
            intent={
                "planned_effects_digest": planned_effects_digest,
                "precondition_digest": precondition_digest,
                "nonce_digest": lease.nonce_digest,
            },
            emergency_receipt_factory=emergency,
        )
        return sha256_digest(canonical_json_bytes(emergency(event_digest)))

    def mark_mutating(self, lease: LeaseContext) -> str:
        self._require_state(lease, "INTENT_DURABLE", require_emergency=True)
        return self._append_event(lease, "MUTATING")

    def publish_result(self, lease: LeaseContext, *, terminal_state: str,
                       postcondition_digest: str) -> str:
        if terminal_state not in {"DONE", "QUARANTINED"}:
            raise ContractError("unknown terminal state")
        validate_digest(postcondition_digest)
        report = self._require_state(lease, "MUTATING", require_emergency=True)
        emergency_digest = self._emergency_digest(report)
        result_event = self._append_event(
            lease, "RESULT_DURABLE", result={"postcondition_digest": postcondition_digest}
        )
        terminal_digest = self._publish_receipt({
            "contract_version": CONTRACT_VERSION,
            "operation_id": lease.operation_id,
            "target_collision_key": lease.target_collision_key,
            "receipt_state": "TERMINAL",
            "event_digest": result_event,
            "supersedes_receipt_digest": emergency_digest,
            "fencing_token": lease.fencing_token,
        })
        self._append_event(lease, terminal_state, receipt_digest=terminal_digest)
        return terminal_digest

    def reconcile(self, lease: LeaseContext, *, decision_digest: str) -> str:
        """Append one idempotent human-confirmed closure; never invokes Git."""
        self._require_lease(lease)
        if lease.purpose != "reconcile":
            raise TransactionError("STALE", "a reconcile lease is required")
        validate_digest(decision_digest)
        report = self.inspect(lease.operation_id)
        if not report.events or report.problems:
            raise TransactionError("INDETERMINATE", "; ".join(report.problems) or "empty journal")
        if report.closures:
            if len(report.closures) == 1 and report.closures[0]["decision_digest"] == decision_digest:
                return sha256_digest(canonical_json_bytes(report.closures[0]))
            raise TransactionError("INDETERMINATE", "conflicting closure decision")
        value = {
            "contract_version": CONTRACT_VERSION, "operation_id": lease.operation_id,
            "target_collision_key": lease.target_collision_key,
            "fencing_token": lease.fencing_token, "decision_digest": decision_digest,
            "event_digest": report.head_digest,
        }
        digest = sha256_digest(canonical_json_bytes(value))
        self._atomic_publish(self._closure_dir(lease.operation_id) / f"{digest[7:]}.json", value)
        return digest

    def inspect(self, operation_id: str) -> ChainReport:
        problems: list[str] = []
        events: list[dict[str, object]] = []
        embedded_receipts: list[dict[str, object]] = []
        event_digests: set[str] = set()
        head: str | None = None
        event_dir = self._event_dir(operation_id)
        for path in sorted(event_dir.glob("*.json")) if event_dir.exists() else ():
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
                # 同梱された緊急 receipt を外してから core を評価する。core の形と
                # digest 定義は旧形式と同一に保つため、既存の digest 検査はそのまま効く。
                embedded = record.pop(EMERGENCY_RECEIPT_FIELD, None)
                if set(record) != {"event", "intent", "result", "receipt_digest"}:
                    raise ContractError("transaction record fields mismatch")
                event = validate_operation_event(record["event"])
                digest = sha256_digest(canonical_json_bytes(record))
                self._validate_record_payload(record, str(event["state"]))
                if str(event["state"]) == "INTENT_DURABLE":
                    if embedded is None:
                        # 旧形式（intent と緊急 receipt を別 file へ 2 回 publish）は
                        # 推測移行せず fail-closed にする（`SI-FLW-087`）。
                        raise ContractError("intent record has no embedded emergency receipt")
                    embedded = validate_mutation_receipt(embedded)
                    # 別 file 経路と同じ束縛を同梱にも課す。個数（ちょうど 1 件）の
                    # 検査だけでは、個数は合っているが別 operation を指す receipt を
                    # 見逃す。
                    if (
                        embedded["receipt_state"] != "INDETERMINATE"
                        or embedded["event_digest"] != digest
                        or embedded["operation_id"] != event["operation_id"]
                        or embedded["target_collision_key"] != event["target_collision_key"]
                        or embedded["fencing_token"] != event["fencing_token"]
                    ):
                        raise ContractError("embedded emergency receipt does not bind this intent")
                elif embedded is not None:
                    raise ContractError("only the intent record may embed an emergency receipt")
                if embedded is not None:
                    embedded_receipts.append(embedded)
            except (OSError, json.JSONDecodeError, KeyError, ContractError) as exc:
                problems.append(f"{path.name}: invalid event ({type(exc).__name__})")
                continue
            sequence = int(event["sequence"])
            if sequence != len(events) or event["previous_event_digest"] != head:
                problems.append(f"{path.name}: event gap, branch, or digest mismatch")
                continue
            expected_name = f"{sequence:020d}-{digest[7:]}.json"
            if path.name != expected_name:
                problems.append(f"{path.name}: event filename digest mismatch")
                continue
            if event["operation_id"] != operation_id or event["target_collision_key"] != self.target_collision_key:
                problems.append(f"{path.name}: operation or target mismatch")
                continue
            if events and event["fencing_token"] != events[0]["event"]["fencing_token"]:
                problems.append(f"{path.name}: fencing token changed or rolled back")
                continue
            events.append(record)
            event_digests.add(digest)
            head = digest
        states = tuple(str(item["event"]["state"]) for item in events)
        if states and states not in {PHASES[:len(states)], QUARANTINE_PHASES[:len(states)]}:
            problems.append("unknown or out-of-order operation phase")

        receipts: list[dict[str, object]] = list(embedded_receipts)
        receipt_dir = self._receipt_dir(operation_id)
        for path in sorted(receipt_dir.glob("*.json")) if receipt_dir.exists() else ():
            try:
                value = validate_mutation_receipt(json.loads(path.read_text(encoding="utf-8")))
                digest = sha256_digest(canonical_json_bytes(value))
            except (OSError, json.JSONDecodeError, ContractError) as exc:
                problems.append(f"{path.name}: invalid receipt ({type(exc).__name__})")
                continue
            if value["receipt_state"] == "INDETERMINATE":
                # 緊急 receipt は intent record への同梱だけを正とする。別 file から
                # 持ち込めると 2 回 publish の空隙が復活する（`SI-FLW-087`）。
                problems.append(f"{path.name}: emergency receipt must be embedded in the intent record")
                continue
            if path.stem != digest[7:] or value["event_digest"] not in event_digests:
                problems.append(f"{path.name}: receipt digest or event reference mismatch")
            if events and (
                value["operation_id"] != operation_id
                or value["target_collision_key"] != self.target_collision_key
                or value["fencing_token"] != events[0]["event"]["fencing_token"]
            ):
                problems.append(f"{path.name}: receipt operation, target, or token mismatch")
            receipts.append(value)
        emergency = [r for r in receipts if r["receipt_state"] == "INDETERMINATE"]
        terminal = [r for r in receipts if r["receipt_state"] == "TERMINAL"]
        if len(emergency) > 1 or len(terminal) > 1:
            problems.append("multiple receipt successors")
        if terminal and (not emergency or terminal[0]["supersedes_receipt_digest"] != sha256_digest(canonical_json_bytes(emergency[0]))):
            problems.append("terminal receipt does not uniquely supersede emergency receipt")
        if len(events) >= 2 and len(emergency) != 1:
            problems.append("durable intent does not have exactly one emergency receipt")
        if len(events) < 2 and receipts:
            problems.append("receipt exists before durable intent")
        if terminal:
            referenced = next(
                (record for record in events
                 if sha256_digest(canonical_json_bytes(record)) == terminal[0]["event_digest"]),
                None,
            )
            if referenced is None or referenced["event"]["state"] != "RESULT_DURABLE":
                problems.append("terminal receipt does not reference RESULT_DURABLE")
        if states and states[-1] in {"DONE", "QUARANTINED"}:
            terminal_digest = (
                sha256_digest(canonical_json_bytes(terminal[0])) if len(terminal) == 1 else None
            )
            if len(terminal) != 1 or events[-1]["receipt_digest"] != terminal_digest:
                problems.append("terminal event is not bound to one terminal receipt")

        closures: list[dict[str, object]] = []
        closure_dir = self._closure_dir(operation_id)
        for path in sorted(closure_dir.glob("*.json")) if closure_dir.exists() else ():
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
                expected = {"contract_version", "operation_id", "target_collision_key", "fencing_token", "decision_digest", "event_digest"}
                if set(value) != expected:
                    raise ContractError("closure fields mismatch")
                validate_digest(value["decision_digest"])
                validate_digest(value["event_digest"])
                validate_uint64_string(value["fencing_token"])
                if (
                    value["operation_id"] != operation_id
                    or value["target_collision_key"] != self.target_collision_key
                    or value["event_digest"] != head
                    or not events
                    or value["fencing_token"] != events[0]["event"]["fencing_token"]
                ):
                    raise ContractError("closure binding mismatch")
                if path.stem != sha256_digest(canonical_json_bytes(value))[7:]:
                    raise ContractError("closure digest mismatch")
                closures.append(value)
            except (OSError, json.JSONDecodeError, ContractError) as exc:
                problems.append(f"{path.name}: invalid closure ({type(exc).__name__})")
        if len(closures) > 1:
            problems.append("multiple closure decisions")
        return ChainReport(tuple(events), tuple(receipts), tuple(closures), head, tuple(problems))

    def _prepare_root(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if os.name != "nt" and self.root.stat().st_mode & 0o077:
            raise TransactionError("UNSUPPORTED_FILESYSTEM", "transaction root is not owner-only")
        for name in ("events", "receipts", "closures"):
            (self.root / name).mkdir(mode=0o700, exist_ok=True)

    def _acquire_lock_stream(self, timeout_seconds: float) -> object:
        lock_path = self.root / "target.lock"
        descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
        stream = os.fdopen(descriptor, "r+b", buffering=0)
        if os.name != "nt" and lock_path.stat().st_mode & 0o077:
            stream.close()
            raise TransactionError("UNSUPPORTED_FILESYSTEM", "target lock is not owner-only")
        if lock_path.stat().st_size == 0:
            stream.write(b"0")
            os.fsync(stream.fileno())
        deadline = time.monotonic() + max(0.0, timeout_seconds)
        while not _lock(stream):
            if time.monotonic() >= deadline:
                stream.close()
                raise TransactionError("BLOCKED_LOCK_BUSY", "target lock timeout")
            time.sleep(min(0.01, max(0.0, deadline - time.monotonic())))
        return stream

    def _issue_fencing_token(self) -> str:
        counter_path = self.root / "fencing-counter.json"
        current = 0
        if counter_path.exists():
            try:
                value = json.loads(counter_path.read_text(encoding="utf-8"))
                if set(value) != {"value"}:
                    raise ValueError
                current = int(validate_uint64_string(value["value"]))
            except (OSError, json.JSONDecodeError, ValueError, ContractError) as exc:
                raise TransactionError("INDETERMINATE", "fencing counter is invalid") from exc
        observed = self._maximum_observed_token()
        if current < observed:
            raise TransactionError("INDETERMINATE", "fencing counter rolled back")
        if current >= MAX_UINT64:
            raise TransactionError("INDETERMINATE", "fencing counter overflow")
        token = str(current + 1)
        self._atomic_publish(counter_path, {"value": token}, replace=True)
        return token

    def _current_fencing_token(self) -> str:
        counter_path = self.root / "fencing-counter.json"
        try:
            value = json.loads(counter_path.read_text(encoding="utf-8"))
            if set(value) != {"value"}:
                raise ValueError
            current = validate_uint64_string(value["value"])
        except (OSError, json.JSONDecodeError, ValueError, ContractError) as exc:
            raise TransactionError("INDETERMINATE", "fencing counter is invalid") from exc
        if int(current) != self._maximum_observed_token():
            raise TransactionError("INDETERMINATE", "fencing counter does not match journal")
        return current

    def _maximum_observed_token(self) -> int:
        maximum = 0
        base = self.root / "events"
        for operation_dir in base.iterdir() if base.exists() else ():
            if not operation_dir.is_dir():
                raise TransactionError("INDETERMINATE", "unexpected journal entry")
            try:
                operation_id = validate_digest("sha256:" + operation_dir.name)
            except ContractError as exc:
                raise TransactionError("INDETERMINATE", "invalid operation journal directory") from exc
            report = self.inspect(operation_id)
            if report.problems:
                raise TransactionError("INDETERMINATE", "; ".join(report.problems))
            for record in report.events:
                maximum = max(maximum, int(record["event"]["fencing_token"]))
        return maximum

    def _nonce_was_consumed(self, nonce_digest: str) -> bool:
        for operation_dir in (self.root / "events").iterdir():
            if operation_dir.is_dir():
                try:
                    operation_id = validate_digest("sha256:" + operation_dir.name)
                except ContractError as exc:
                    raise TransactionError("INDETERMINATE", "invalid operation journal directory") from exc
                report = self.inspect(operation_id)
                if report.problems:
                    raise TransactionError("INDETERMINATE", "; ".join(report.problems))
                for record in report.events:
                    intent = record["intent"]
                    if isinstance(intent, Mapping) and intent.get("nonce_digest") == nonce_digest:
                        return True
        return False

    def _append_event(self, lease: LeaseContext, state: str, *,
                      intent: Mapping[str, str] | None = None,
                      result: Mapping[str, str] | None = None,
                      receipt_digest: str | None = None,
                      emergency_receipt_factory: Callable[[str], Mapping[str, object]] | None = None) -> str:
        if state not in EVENT_STATES:
            raise ContractError("unknown event state")
        report = self.inspect(lease.operation_id)
        if report.problems:
            raise TransactionError("INDETERMINATE", "; ".join(report.problems))
        event = {
            "contract_version": CONTRACT_VERSION, "operation_id": lease.operation_id,
            "target_collision_key": lease.target_collision_key,
            "sequence": str(len(report.events)), "previous_event_digest": report.head_digest,
            "state": state, "fencing_token": lease.fencing_token,
        }
        validate_operation_event(event)
        record = {"event": event, "intent": dict(intent) if intent else None,
                  "result": dict(result) if result else None, "receipt_digest": receipt_digest}
        digest = sha256_digest(canonical_json_bytes(record))
        target = self._event_dir(lease.operation_id) / f"{len(report.events):020d}-{digest[7:]}.json"
        if emergency_receipt_factory is None:
            self._atomic_publish(target, record)
            return digest
        # 緊急 receipt を同じ file へ同梱し、**1 回の atomic publish** で確定する
        # （`SI-FLW-087`）。receipt の `event_digest` は同梱前の core record の digest を
        # 指すため循環しない。core の形と digest 定義は従来と同一に保つ。
        receipt = validate_mutation_receipt(emergency_receipt_factory(digest))
        self._atomic_publish(target, {**record, EMERGENCY_RECEIPT_FIELD: receipt})
        return digest

    def _publish_receipt(self, value: Mapping[str, object]) -> str:
        receipt = validate_mutation_receipt(value)
        digest = sha256_digest(canonical_json_bytes(receipt))
        self._atomic_publish(self._receipt_dir(str(receipt["operation_id"])) / f"{digest[7:]}.json", receipt)
        return digest

    def _require_lease(self, lease: LeaseContext) -> None:
        if lease is not self._lease or lease.target_collision_key != self.target_collision_key:
            raise TransactionError("STALE", "lease is not active for this authority")

    def _require_state(self, lease: LeaseContext, expected: str, *,
                       require_emergency: bool = False) -> ChainReport:
        self._require_lease(lease)
        report = self.inspect(lease.operation_id)
        if report.problems:
            raise TransactionError("INDETERMINATE", "; ".join(report.problems))
        if report.state != expected:
            raise TransactionError("STALE", f"operation state is {report.state}, expected {expected}")
        if report.closures:
            raise TransactionError("STALE", "operation already has a reconcile closure")
        if require_emergency:
            self._emergency_digest(report)
        return report

    @staticmethod
    def _emergency_digest(report: ChainReport) -> str:
        emergency = [r for r in report.receipts if r["receipt_state"] == "INDETERMINATE"]
        if len(emergency) != 1:
            raise TransactionError("INDETERMINATE", "one emergency receipt is required")
        return sha256_digest(canonical_json_bytes(emergency[0]))

    def _event_dir(self, operation_id: str) -> Path:
        return self.root / "events" / validate_digest(operation_id)[7:]

    def _receipt_dir(self, operation_id: str) -> Path:
        return self.root / "receipts" / validate_digest(operation_id)[7:]

    def _closure_dir(self, operation_id: str) -> Path:
        return self.root / "closures" / validate_digest(operation_id)[7:]

    @staticmethod
    def _validate_record_payload(record: Mapping[str, object], state: str) -> None:
        intent, result, receipt = record["intent"], record["result"], record["receipt_digest"]
        if state == "INTENT_DURABLE":
            if not isinstance(intent, Mapping) or set(intent) != {
                "planned_effects_digest", "precondition_digest", "nonce_digest"
            } or result is not None or receipt is not None:
                raise ContractError("invalid INTENT_DURABLE payload")
            for value in intent.values():
                validate_digest(value)
        elif state == "RESULT_DURABLE":
            if not isinstance(result, Mapping) or set(result) != {"postcondition_digest"} or intent is not None or receipt is not None:
                raise ContractError("invalid RESULT_DURABLE payload")
            validate_digest(result["postcondition_digest"])
        elif state in {"DONE", "QUARANTINED"}:
            if intent is not None or result is not None or receipt is None:
                raise ContractError("invalid terminal event payload")
            validate_digest(receipt)
        elif intent is not None or result is not None or receipt is not None:
            raise ContractError("phase must not carry unrelated payload")

    def _atomic_publish(self, target: Path, value: Mapping[str, object], *,
                        replace: bool = False) -> None:
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if target.exists() and not replace:
            raise TransactionError("INDETERMINATE", "append-only record already exists")
        temporary = target.parent / f".{target.name}.{os.getpid()}.tmp"
        if temporary.exists():
            raise TransactionError("INDETERMINATE", "torn temporary record exists")
        try:
            descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            try:
                os.write(descriptor, canonical_json_bytes(dict(value)) + b"\n")
                if self._hook:
                    self._hook("temp-written", temporary)
                os.fsync(descriptor)
                if self._hook:
                    self._hook("file-fsynced", temporary)
            finally:
                os.close(descriptor)
            os.replace(temporary, target)
            if self._hook:
                self._hook("renamed", target)
            _fsync_dir(target.parent)
            if self._hook:
                self._hook("dir-fsynced", target)
        except TransactionError:
            raise
        except OSError as exc:
            raise TransactionError("BLOCKED_STORAGE", f"durable publish failed: {exc.strerror}") from exc
