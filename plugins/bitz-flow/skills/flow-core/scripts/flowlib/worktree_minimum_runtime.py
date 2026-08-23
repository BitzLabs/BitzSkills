"""Minimum-runtime marker and startup gate (FLW-TSK-112)."""

from __future__ import annotations

import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping

from .worktree_contract import CONTRACT_VERSION, ContractError, SemVer

MARKER_SCHEMA_VERSION = 1
MARKER_RELATIVE_PATH = Path("bitz-flow-v2") / "minimum-runtime.json"
PUBLISH_STEPS = ("temp-written", "file-fsynced", "renamed", "dir-fsynced")
ENTRYPOINTS = frozenset({"stable-launcher", "public-cli"})


@dataclass(frozen=True)
class RuntimeGateDecision:
    allowed: bool
    code: str
    cause: str


def _marker_value(minimum_runtime_version: str) -> dict[str, object]:
    SemVer.parse(minimum_runtime_version)
    return {
        "schema_version": MARKER_SCHEMA_VERSION,
        "minimum_runtime_version": minimum_runtime_version,
        "contract_schema_version": CONTRACT_VERSION,
    }


def _validate_marker(value: object) -> dict[str, object]:
    expected = {"schema_version", "minimum_runtime_version", "contract_schema_version"}
    if not isinstance(value, dict) or set(value) != expected:
        raise ContractError("minimum-runtime marker fields mismatch")
    if value["schema_version"] != MARKER_SCHEMA_VERSION:
        raise ContractError("unsupported minimum-runtime marker schema")
    if value["contract_schema_version"] != CONTRACT_VERSION:
        raise ContractError("unsupported contract schema version")
    SemVer.parse(value["minimum_runtime_version"])
    return value


def _secure_namespace(path: Path) -> None:
    if path.is_symlink():
        raise ContractError("minimum-runtime namespace must not be a symlink")
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    info = path.stat(follow_symlinks=False)
    if not stat.S_ISDIR(info.st_mode) or (os.name != "nt" and info.st_mode & 0o077):
        raise ContractError("minimum-runtime namespace must be an owner-only directory")
    if hasattr(os, "geteuid") and info.st_uid != os.geteuid():
        raise ContractError("minimum-runtime namespace owner mismatch")


def _fsync_dir(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def publish_marker(
    common_dir: str | Path,
    *,
    minimum_runtime_version: str,
    audit_only: bool = False,
    step_hook: Callable[[str, Path], None] | None = None,
) -> Path:
    """Publish one complete marker; audit-only calls are rejected before any write."""
    if audit_only:
        raise ContractError("audit-only mode cannot publish minimum-runtime marker")
    value = _marker_value(minimum_runtime_version)
    namespace = Path(common_dir) / MARKER_RELATIVE_PATH.parent
    _secure_namespace(namespace)
    target = namespace / MARKER_RELATIVE_PATH.name
    if target.is_symlink():
        raise ContractError("minimum-runtime marker must not be a symlink")
    temporary = namespace / f".{target.name}.{os.getpid()}.tmp"
    if temporary.exists():
        raise ContractError("torn minimum-runtime temporary marker exists")
    body = json.dumps(value, sort_keys=True, separators=(",", ":")).encode() + b"\n"
    try:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            os.write(descriptor, body)
            if step_hook:
                step_hook("temp-written", temporary)
            os.fsync(descriptor)
            if step_hook:
                step_hook("file-fsynced", temporary)
        finally:
            os.close(descriptor)
        os.replace(temporary, target)
        if step_hook:
            step_hook("renamed", target)
        _fsync_dir(namespace)
        if step_hook:
            step_hook("dir-fsynced", target)
    finally:
        if temporary.exists():
            temporary.unlink()
    return target


def read_marker(common_dir: str | Path) -> dict[str, object]:
    """Read without creating or modifying the namespace."""
    target = Path(common_dir) / MARKER_RELATIVE_PATH
    if target.is_symlink():
        raise ContractError("minimum-runtime marker must not be a symlink")
    info = target.stat(follow_symlinks=False)
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or (
        os.name != "nt" and info.st_mode & 0o077
    ):
        raise ContractError("minimum-runtime marker integrity check failed")
    try:
        return _validate_marker(json.loads(target.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError("minimum-runtime marker cannot be read") from exc


def startup_gate(
    common_dir: str | Path,
    *,
    entrypoint: str,
    runtime_version: str,
    bundle_state: str,
    current_bundle: Mapping[str, object] | None,
) -> RuntimeGateDecision:
    """Fail closed for missing/pending/unknown bundle or unsupported runtime."""
    if entrypoint not in ENTRYPOINTS:
        return RuntimeGateDecision(False, "BLOCKED", "unknown-entrypoint")
    try:
        marker = read_marker(common_dir)
        runtime = SemVer.parse(runtime_version)
    except (OSError, ContractError):
        return RuntimeGateDecision(False, "BLOCKED", "minimum-runtime-marker-invalid")
    if bundle_state != "ACTIVE":
        return RuntimeGateDecision(False, "BLOCKED", "bundle-pending" if bundle_state == "PENDING" else "unknown-bundle")
    required = {"bundle_version", "contract_version", "minimum_runtime_version"}
    if not isinstance(current_bundle, Mapping) or not required.issubset(current_bundle):
        return RuntimeGateDecision(False, "BLOCKED", "unknown-bundle")
    try:
        bundle_runtime = SemVer.parse(current_bundle["minimum_runtime_version"])
        SemVer.parse(current_bundle["bundle_version"])
    except ContractError:
        return RuntimeGateDecision(False, "BLOCKED", "unknown-bundle")
    if current_bundle["contract_version"] != CONTRACT_VERSION:
        return RuntimeGateDecision(False, "BLOCKED", "contract-version-mismatch")
    marker_runtime = SemVer.parse(marker["minimum_runtime_version"])
    if marker_runtime != bundle_runtime:
        return RuntimeGateDecision(False, "BLOCKED", "bundle-marker-mismatch")
    if runtime < marker_runtime:
        return RuntimeGateDecision(False, "BLOCKED", "runtime-too-old")
    return RuntimeGateDecision(True, "READY", "compatible")
