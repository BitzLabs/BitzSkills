"""contract v2のminimum-runtime sentinelとpromotion barrier（FLW-NFR-014）。"""

from __future__ import annotations

import json
import os
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence


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
