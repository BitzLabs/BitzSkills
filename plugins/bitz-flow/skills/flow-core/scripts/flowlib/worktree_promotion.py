"""contract v2のminimum-runtime sentinelとpromotion barrier（FLW-NFR-014）。"""

from __future__ import annotations

import json
import os
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Sequence

from .worktree_contract import (
    CONTRACT_VERSION, MAX_UINT64, ContractError, canonical_json_bytes, sha256_digest,
    validate_contract_bundle, validate_digest, validate_uint64_string,
)


SENTINEL_SCHEMA_VERSION = 1
CONTRACT_SCHEMA_VERSION = 2
SENTINEL_RELATIVE_PATH = Path("bitz-flow-v2") / "minimum-runtime.json"


@dataclass(frozen=True)
class PromotionDecision:
    allowed: bool
    code: str
    reason: str


def _version_tuple(value: str) -> tuple[int, ...]:
    parts = value.split(".")
    if not parts or any(not part.isdigit() for part in parts):
        raise ValueError("runtime version must contain decimal components only")
    return tuple(int(part) for part in parts)


def _canonical_json(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _fsync_dir(path: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    descriptor = os.open(path, flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _secure_directory(path: Path) -> None:
    if path.is_symlink():
        raise ValueError("sentinel namespace must not be a symlink")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = path.stat(follow_symlinks=False)
    if not stat.S_ISDIR(info.st_mode):
        raise ValueError("sentinel namespace must be a directory")
    if hasattr(os, "geteuid") and info.st_uid != os.geteuid():
        raise ValueError("sentinel namespace owner differs from the effective principal")
    if info.st_mode & 0o077:
        raise ValueError("sentinel namespace must be owner-only")


def write_minimum_runtime_sentinel(
    common_dir: str | Path,
    *,
    minimum_runtime_version: str,
    contract_schema_version: int = CONTRACT_SCHEMA_VERSION,
) -> Path:
    """sentinelをfile fsync → atomic replace → directory fsyncで公開する。"""
    _version_tuple(minimum_runtime_version)
    if contract_schema_version != CONTRACT_SCHEMA_VERSION:
        raise ValueError("unsupported contract schema version")
    namespace = Path(common_dir) / SENTINEL_RELATIVE_PATH.parent
    _secure_directory(namespace)
    target = namespace / SENTINEL_RELATIVE_PATH.name
    if target.is_symlink():
        raise ValueError("minimum-runtime sentinel must not be a symlink")
    payload = _canonical_json(
        {
            "schema_version": SENTINEL_SCHEMA_VERSION,
            "minimum_runtime_version": minimum_runtime_version,
            "contract_schema_version": contract_schema_version,
        }
    )
    descriptor, temporary_name = tempfile.mkstemp(prefix=".minimum-runtime.", dir=namespace)
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
        _fsync_dir(namespace)
    finally:
        if temporary.exists():
            temporary.unlink()
    info = target.stat(follow_symlinks=False)
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_mode & 0o077:
        raise ValueError("minimum-runtime sentinel integrity check failed")
    return target


def read_minimum_runtime_sentinel(common_dir: str | Path) -> dict[str, object]:
    target = Path(common_dir) / SENTINEL_RELATIVE_PATH
    if target.is_symlink():
        raise ValueError("minimum-runtime sentinel must not be a symlink")
    info = target.stat(follow_symlinks=False)
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_mode & 0o077:
        raise ValueError("minimum-runtime sentinel integrity check failed")
    value = json.loads(target.read_text(encoding="utf-8"))
    required = {"schema_version", "minimum_runtime_version", "contract_schema_version"}
    if not isinstance(value, dict) or set(value) != required:
        raise ValueError("minimum-runtime sentinel fields mismatch")
    if value["schema_version"] != SENTINEL_SCHEMA_VERSION:
        raise ValueError("unsupported sentinel schema version")
    if value["contract_schema_version"] != CONTRACT_SCHEMA_VERSION:
        raise ValueError("unsupported contract schema version")
    _version_tuple(str(value["minimum_runtime_version"]))
    return value


def promotion_preflight(
    sentinel: Mapping[str, object],
    *,
    entrypoint_inventory: Mapping[str, str],
    supported_entrypoints: Sequence[str],
) -> PromotionDecision:
    """全supported entrypointがsentinel-aware baseline以降かを証明する。"""
    expected = set(supported_entrypoints)
    actual = set(entrypoint_inventory)
    if actual != expected:
        missing = sorted(expected - actual)
        unexpected = sorted(actual - expected)
        return PromotionDecision(False, "UNSUPPORTED", f"entrypoint inventory mismatch: missing={missing}, unexpected={unexpected}")
    try:
        minimum = _version_tuple(str(sentinel["minimum_runtime_version"]))
        versions = {name: _version_tuple(version) for name, version in entrypoint_inventory.items()}
    except (KeyError, TypeError, ValueError) as exc:
        return PromotionDecision(False, "BLOCKED", f"runtime version evidence is invalid: {exc}")
    obsolete = sorted(name for name, version in versions.items() if version < minimum)
    if obsolete:
        return PromotionDecision(False, "BLOCKED", f"pre-baseline entrypoints remain enabled: {obsolete}")
    return PromotionDecision(True, "READY", "all supported entrypoints are sentinel-aware")


# -- Local Safety Profile atomic bundle promotion (FLW-TSK-113) -----------------

PROMOTION_RELATIVE_PATH = Path("bitz-flow-v2") / "promotion"


class PromotionError(RuntimeError):
    def __init__(self, code: str, cause: str):
        super().__init__(cause); self.code = code; self.cause = cause


def _promotion_lock(namespace: Path):
    _secure_directory(namespace)
    path = namespace / "promotion.lock"
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    stream = os.fdopen(descriptor, "r+b", buffering=0)
    if path.stat().st_size == 0:
        stream.write(b"0"); os.fsync(stream.fileno())
    try:
        if os.name == "nt":  # pragma: no cover
            import msvcrt
            stream.seek(0); msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        stream.close(); raise PromotionError("BLOCKED_LOCK_BUSY", "promotion lock busy") from exc
    return stream


def _promotion_unlock(stream) -> None:
    if os.name == "nt":  # pragma: no cover
        import msvcrt
        stream.seek(0); msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl
        fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
    stream.close()


def _atomic_json(target: Path, value: Mapping[str, object], hook=None) -> None:
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = target.parent / f".{target.name}.{os.getpid()}.tmp"
    if temporary.exists():
        raise PromotionError("INDETERMINATE", "torn promotion temporary exists")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(descriptor, canonical_json_bytes(dict(value)) + b"\n")
        if hook: hook("temp-written", temporary)
        os.fsync(descriptor)
        if hook: hook("file-fsynced", temporary)
    finally:
        os.close(descriptor)
    os.replace(temporary, target)
    if hook: hook("renamed", target)
    _fsync_dir(target.parent)
    if hook: hook("dir-fsynced", target)


def _promotion_namespace(common_dir: str | Path) -> Path:
    return Path(common_dir) / PROMOTION_RELATIVE_PATH


def register_active_operation(common_dir: str | Path, *, operation_id: str,
                              bundle_digest: str, verify_current: bool = False) -> Path:
    validate_digest(operation_id); validate_digest(bundle_digest)
    namespace = _promotion_namespace(common_dir); lock = _promotion_lock(namespace)
    try:
        if verify_current:
            current_path = namespace / "current.json"
            try:
                current = json.loads(current_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise PromotionError("INDETERMINATE", "current bundle cannot be verified") from exc
            if current.get("state") != "ACTIVE" or current.get("bundle_digest") != bundle_digest:
                raise PromotionError("STALE", "current bundle changed")
        marker = namespace / "active" / f"{operation_id[7:]}.json"
        if marker.exists():
            raise PromotionError("STALE", "active operation marker already exists")
        _atomic_json(marker, {"contract_version": CONTRACT_VERSION,
                              "operation_id": operation_id, "bundle_digest": bundle_digest})
        return marker
    finally:
        _promotion_unlock(lock)


def release_active_operation(common_dir: str | Path, *, operation_id: str,
                             terminal_receipt_digest: str) -> None:
    validate_digest(operation_id); validate_digest(terminal_receipt_digest)
    namespace = _promotion_namespace(common_dir); lock = _promotion_lock(namespace)
    try:
        marker = namespace / "active" / f"{operation_id[7:]}.json"
        if not marker.is_file():
            raise PromotionError("INDETERMINATE", "active operation marker missing")
        closed = namespace / "closed" / f"{operation_id[7:]}.json"
        _atomic_json(closed, {"contract_version": CONTRACT_VERSION,
                              "operation_id": operation_id,
                              "terminal_receipt_digest": terminal_receipt_digest})
        marker.unlink()
        _fsync_dir(marker.parent)
    finally:
        _promotion_unlock(lock)


def abort_active_operation(common_dir: str | Path, *, operation_id: str,
                           bundle_digest: str) -> None:
    """Remove a marker only when target intent was never made durable."""
    validate_digest(operation_id); validate_digest(bundle_digest)
    namespace = _promotion_namespace(common_dir); lock = _promotion_lock(namespace)
    try:
        marker = namespace / "active" / f"{operation_id[7:]}.json"
        try:
            value = json.loads(marker.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise PromotionError("INDETERMINATE", "active operation marker cannot be aborted") from exc
        if value.get("operation_id") != operation_id or value.get("bundle_digest") != bundle_digest:
            raise PromotionError("INDETERMINATE", "active operation marker changed")
        marker.unlink()
        _fsync_dir(marker.parent)
    finally:
        _promotion_unlock(lock)


def promote_bundle(
    common_dir: str | Path, *, bundle: Mapping[str, object],
    expected_members: Mapping[str, tuple[str, str]], schema_documents: Mapping[str, bytes],
    expected_generation: str, runtime_identity_digest: str,
    recheck: Callable[[], tuple[str, str]], step_hook=None,
) -> dict[str, object]:
    """Validate staging then publish one current pointer inside a local critical section."""
    generation = validate_uint64_string(expected_generation)
    validate_digest(runtime_identity_digest)
    validated = validate_contract_bundle(
        bundle, expected_members=expected_members, schema_documents=schema_documents
    )
    namespace = _promotion_namespace(common_dir); lock = _promotion_lock(namespace)
    try:
        active = namespace / "active"
        if active.exists() and any(active.iterdir()):
            raise PromotionError("BLOCKED_ACTIVE_OPERATION", "active operation exists")
        current_path = namespace / "current.json"
        current = json.loads(current_path.read_text()) if current_path.exists() else None
        actual_generation = str(current["generation"]) if current else "0"
        if actual_generation != generation:
            raise PromotionError("STALE", "current generation changed")
        if int(generation) >= MAX_UINT64:
            raise PromotionError("INDETERMINATE", "promotion generation overflow")
        staged = namespace / "bundles" / validated.digest[7:] / "bundle.json"
        _atomic_json(staged, bundle, step_hook)
        staged_value = json.loads(staged.read_text(encoding="utf-8"))
        staged_bundle = validate_contract_bundle(
            staged_value, expected_members=expected_members, schema_documents=schema_documents
        )
        observed_generation, observed_runtime = recheck()
        if (observed_generation != generation or observed_runtime != runtime_identity_digest
                or staged_bundle.digest != validated.digest):
            raise PromotionError("STALE", "generation, runtime identity, or bundle changed")
        next_generation = str(int(generation) + 1)
        pointer = {"contract_version": CONTRACT_VERSION, "generation": next_generation,
                   "bundle_digest": validated.digest,
                   "runtime_identity_digest": runtime_identity_digest, "state": "ACTIVE"}
        _atomic_json(current_path, pointer, step_hook)
        receipt = {"contract_version": CONTRACT_VERSION,
                   "previous_generation": generation, "generation": next_generation,
                   "bundle_digest": validated.digest, "result": "PROMOTED"}
        _atomic_json(namespace / "receipts" / f"{next_generation}.json", receipt, step_hook)
        return pointer
    finally:
        _promotion_unlock(lock)
