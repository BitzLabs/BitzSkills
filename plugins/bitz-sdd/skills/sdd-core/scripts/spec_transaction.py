#!/usr/bin/env python3
"""SDD-FR-143: workspace-local mutation transaction primitives (stdlib only)."""
from __future__ import annotations

import base64
import hashlib
import json
import os
import socket
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

SCHEMA_VERSION = 1
HASH_ALGORITHM = "sha256"
LOCK_NAME = ".mutation-lock"
TRANSACTIONS_DIR = ".transactions"


class MutationError(RuntimeError):
    """Stable machine-readable mutation failure."""

    def __init__(self, code: str, message: str, exit_code: int = 5):
        super().__init__(message)
        self.code = code
        self.exit_code = exit_code


@dataclass(frozen=True)
class FileChange:
    path: Path
    before: Optional[bytes]
    after: bytes


@dataclass(frozen=True)
class TransactionPlan:
    changes: tuple[FileChange, ...]
    metadata: dict


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json(data: dict) -> bytes:
    return json.dumps(
        data,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _fsync_dir(path: Path) -> None:
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError as exc:
        raise MutationError("durability-unsupported", f"directoryをopenできません: {path}: {exc}", 8) from exc
    try:
        os.fsync(fd)
    except OSError as exc:
        raise MutationError("durability-unsupported", f"directoryをfsyncできません: {path}: {exc}", 8) from exc
    finally:
        os.close(fd)


def _write_temp(directory: Path, payload: bytes, prefix: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    fd, raw_path = tempfile.mkstemp(prefix=prefix, dir=directory)
    path = Path(raw_path)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return path


def _publish_no_replace(temp: Path, destination: Path) -> None:
    """Publish a complete same-filesystem temp without replacing destination."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(temp, destination)
    except FileExistsError as exc:
        raise MutationError("mutation-conflict", f"既存pathを上書きしません: {destination}", 5) from exc
    except OSError as exc:
        raise MutationError(
            "durability-unsupported",
            f"atomic no-replace publishを利用できません: {destination}: {exc}",
            8,
        ) from exc
    temp.unlink(missing_ok=True)
    _fsync_dir(destination.parent)


def _replace_durable(destination: Path, payload: bytes) -> None:
    temp = _write_temp(destination.parent, payload, f".{destination.name}.")
    try:
        os.replace(temp, destination)
        _fsync_dir(destination.parent)
    finally:
        temp.unlink(missing_ok=True)


def _publish_payload(destination: Path, payload: bytes) -> None:
    temp = _write_temp(destination.parent, payload, f".{destination.name}.")
    try:
        _publish_no_replace(temp, destination)
    finally:
        temp.unlink(missing_ok=True)


def _current(path: Path) -> Optional[bytes]:
    try:
        return path.read_bytes()
    except FileNotFoundError:
        return None


def _matches(current: Optional[bytes], expected: Optional[bytes]) -> bool:
    return current == expected


def _start_token(pid: int) -> str:
    stat = Path(f"/proc/{pid}/stat")
    try:
        return stat.read_text(encoding="utf-8").split()[21]
    except (OSError, IndexError):
        return ""


def _owner(root: Path, command: str, paths: tuple[Path, ...]) -> dict:
    targets = []
    for path in paths:
        current = _current(path)
        targets.append({
            "path": str(path.resolve().relative_to(root.resolve())),
            "before_exists": current is not None,
            "before_hash": sha256(current) if current is not None else None,
        })
    return {
        "schema_version": SCHEMA_VERSION,
        "event_id": str(uuid.uuid4()),
        "pid": os.getpid(),
        "process_start": _start_token(os.getpid()),
        "hostname": socket.gethostname(),
        "started_at": utc_now(),
        "command": command,
        "targets": targets,
    }


def _spec_dir(root: Path) -> Path:
    return root.resolve() / ".spec"


def _journal_paths(root: Path) -> list[Path]:
    directory = _spec_dir(root) / TRANSACTIONS_DIR
    return sorted(directory.glob("*.json")) if directory.exists() else []


def assert_clean(root: Path) -> None:
    journals = _journal_paths(root)
    lock = _spec_dir(root) / LOCK_NAME
    if journals:
        raise MutationError(
            "incomplete-transaction",
            "未完了transactionがあります: " + ", ".join(path.stem for path in journals),
            6,
        )
    if lock.exists():
        raise MutationError("mutation-conflict", f"workspace mutation lockが存在します: {lock}", 5)


def acquire_lock(root: Path, command: str, paths: tuple[Path, ...]) -> dict:
    assert_clean(root)
    spec_dir = _spec_dir(root)
    spec_dir.mkdir(parents=True, exist_ok=True)
    owner = _owner(root, command, paths)
    temp = _write_temp(spec_dir, canonical_json(owner), ".mutation-lock.")
    try:
        _publish_no_replace(temp, spec_dir / LOCK_NAME)
    finally:
        temp.unlink(missing_ok=True)
    return owner


def release_lock(root: Path) -> None:
    lock = _spec_dir(root) / LOCK_NAME
    lock.unlink(missing_ok=True)
    _fsync_dir(_spec_dir(root))


def _journal_document(owner: dict, plan: TransactionPlan) -> dict:
    root = Path(owner["workspace_root"])
    targets = []
    for change in plan.changes:
        targets.append({
            "path": str(change.path.resolve().relative_to(root)),
            "before_exists": change.before is not None,
            "before_hash": sha256(change.before) if change.before is not None else None,
            "after_hash": sha256(change.after),
            "after_payload": base64.b64encode(change.after).decode("ascii"),
        })
    return {
        "schema_version": SCHEMA_VERSION,
        "hash_algorithm": HASH_ALGORITHM,
        "event_id": owner["event_id"],
        "phase": "PREPARED",
        "created_at": owner["started_at"],
        "command": owner["command"],
        "metadata": plan.metadata,
        "targets": targets,
    }


def _write_journal_new(path: Path, document: dict) -> None:
    temp = _write_temp(path.parent, canonical_json(document), f".{path.name}.")
    try:
        _publish_no_replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def _write_journal_phase(path: Path, document: dict, phase: str) -> None:
    updated = dict(document)
    updated["phase"] = phase
    _replace_durable(path, canonical_json(updated))
    document["phase"] = phase


def _apply(change: FileChange) -> None:
    current = _current(change.path)
    if not _matches(current, change.before):
        raise MutationError(
            "recovery-ambiguous",
            f"CAS不一致: {change.path}",
            7,
        )
    if change.before is None:
        _publish_payload(change.path, change.after)
    else:
        _replace_durable(change.path, change.after)


def mutate(
    root: Path,
    command: str,
    lock_paths: tuple[Path, ...],
    prepare: Callable[[dict], TransactionPlan],
) -> tuple[str, dict]:
    """Acquire lock, prepare under lock, and durably commit all changes."""
    root = root.resolve()
    owner = acquire_lock(root, command, lock_paths)
    owner["workspace_root"] = str(root)
    journal_path: Optional[Path] = None
    try:
        plan = prepare(owner)
        if not plan.changes:
            raise MutationError("precondition-failed", "変更対象がありません", 4)
        document = _journal_document(owner, plan)
        journal_path = _spec_dir(root) / TRANSACTIONS_DIR / f"{owner['event_id']}.json"
        _write_journal_new(journal_path, document)
        for change in plan.changes:
            _apply(change)
        for change in plan.changes:
            current = _current(change.path)
            if current is None or sha256(current) != sha256(change.after):
                raise MutationError("recovery-ambiguous", f"after hash不一致: {change.path}", 7)
        _write_journal_phase(journal_path, document, "APPLIED")
        _write_journal_phase(journal_path, document, "COMMITTED")
        release_lock(root)
        journal_path.unlink()
        _fsync_dir(journal_path.parent)
        return owner["event_id"], plan.metadata
    except BaseException:
        if journal_path is None or not journal_path.exists():
            release_lock(root)
        raise


def _load_journal(root: Path, event_id: str) -> tuple[Path, dict]:
    path = _spec_dir(root) / TRANSACTIONS_DIR / f"{event_id}.json"
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MutationError("recovery-ambiguous", f"journalを読めません: {path}", 7) from exc
    if (
        document.get("schema_version") != SCHEMA_VERSION
        or document.get("hash_algorithm") != HASH_ALGORITHM
        or document.get("event_id") != event_id
        or document.get("phase") not in {"PREPARED", "APPLIED", "COMMITTED"}
    ):
        raise MutationError("recovery-ambiguous", f"journal schemaが不正です: {path}", 7)
    return path, document


def _read_lock_owner(root: Path) -> Optional[dict]:
    lock = _spec_dir(root) / LOCK_NAME
    if not lock.exists():
        return None
    try:
        owner = json.loads(lock.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MutationError("recovery-ambiguous", "lock owner JSONが不正です", 7) from exc
    if (
        owner.get("schema_version") != SCHEMA_VERSION
        or owner.get("hostname") != socket.gethostname()
        or not isinstance(owner.get("pid"), int)
    ):
        raise MutationError("recovery-ambiguous", "lock ownerを安全に確認できません", 7)
    return owner


def _owner_is_active(owner: dict) -> bool:
    pid = owner["pid"]
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return _start_token(pid) == owner.get("process_start")


def _decode_target(root: Path, target: dict) -> FileChange:
    try:
        after = base64.b64decode(target["after_payload"], validate=True)
        if base64.b64encode(after).decode("ascii") != target["after_payload"]:
            raise ValueError("non-canonical base64")
        if sha256(after) != target["after_hash"]:
            raise ValueError("after hash mismatch")
        before = None
        path = (root / target["path"]).resolve()
        if not path.is_relative_to(root.resolve()):
            raise ValueError("path escapes workspace")
        if target["before_exists"]:
            before_hash = target.get("before_hash")
            if not isinstance(before_hash, str):
                raise ValueError("missing before hash")
            # Recovery only needs the hash; a sentinel is replaced below by hash comparison.
            before = b""
        return FileChange(path=path, before=before, after=after)
    except (KeyError, TypeError, ValueError) as exc:
        raise MutationError("recovery-ambiguous", "journal targetが不正です", 7) from exc


def recover(root: Path, event_id: str) -> str:
    root = root.resolve()
    journal_path, document = _load_journal(root, event_id)
    owner = _read_lock_owner(root)
    if owner is not None:
        if owner.get("event_id") != event_id:
            raise MutationError("recovery-ambiguous", "lockとjournalのevent IDが一致しません", 7)
        if _owner_is_active(owner):
            raise MutationError("mutation-conflict", "transaction owner processは実行中です", 5)
    targets = []
    states = []
    for raw in document["targets"]:
        change = _decode_target(root, raw)
        current = _current(change.path)
        current_hash = sha256(current) if current is not None else None
        before_match = (
            current is None if not raw["before_exists"] else current_hash == raw["before_hash"]
        )
        after_match = current is not None and current_hash == raw["after_hash"]
        if not before_match and not after_match:
            raise MutationError("recovery-ambiguous", f"hash不一致: {change.path}", 7)
        targets.append((change, raw, current))
        states.append("after" if after_match else "before")

    if all(state == "before" for state in states):
        release_lock(root)
        journal_path.unlink()
        _fsync_dir(journal_path.parent)
        return "rolled-back"

    for (change, raw, current), state in zip(targets, states):
        if state == "after":
            continue
        concrete = FileChange(path=change.path, before=current, after=change.after)
        _apply(concrete)

    for change, raw, _ in targets:
        current = _current(change.path)
        if current is None or sha256(current) != raw["after_hash"]:
            raise MutationError("recovery-ambiguous", f"after hash不一致: {change.path}", 7)
    _write_journal_phase(journal_path, document, "APPLIED")
    _write_journal_phase(journal_path, document, "COMMITTED")
    release_lock(root)
    journal_path.unlink()
    _fsync_dir(journal_path.parent)
    return "committed"


def recover_lock(root: Path) -> str:
    root = root.resolve()
    if _journal_paths(root):
        raise MutationError("recovery-ambiguous", "journalがあるため--recover-lockは使えません", 7)
    owner = _read_lock_owner(root)
    if owner is None:
        raise MutationError("recovery-ambiguous", "mutation lockがありません", 7)
    if _owner_is_active(owner):
        raise MutationError("mutation-conflict", "lock owner processは実行中です", 5)
    for target in owner.get("targets", []):
        path = (root / target["path"]).resolve()
        current = _current(path)
        current_hash = sha256(current) if current is not None else None
        expected = target.get("before_hash")
        if target.get("before_exists"):
            if current_hash != expected:
                raise MutationError("recovery-ambiguous", f"before hash不一致: {path}", 7)
        elif current is not None:
            raise MutationError("recovery-ambiguous", f"未開始対象が既に存在します: {path}", 7)
    release_lock(root)
    return "lock-released"
