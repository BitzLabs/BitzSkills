"""Fail-closed execution primitives for quality-review."""

from __future__ import annotations

import json
import os
import re
import tempfile
import threading
from pathlib import Path
from typing import Any


def resolve_timeout(*, required: bool) -> dict[str, str]:
    if required:
        return {"attempt": "BLOCKED", "run": "BLOCKED"}
    return {"attempt": "BLOCKED", "run": "CONDITIONAL_PASS"}


class GenerationFence:
    """Monotonic generation with compare-and-swap result acceptance."""

    def __init__(self) -> None:
        self._generation = 0
        self._lock = threading.Lock()

    def begin(self) -> tuple[int, str]:
        with self._lock:
            self._generation += 1
            return self._generation, f"fence-{self._generation}"

    def accept(self, generation: int, token: str, *, run_accepts_result: bool = True) -> bool:
        with self._lock:
            return run_accepts_result and generation == self._generation and token == f"fence-{generation}"


def read_snapshot(root: Path, relative: str) -> bytes:
    """Read only a path below the content-addressed snapshot root."""
    base = root.resolve()
    candidate = (base / relative).resolve()
    if candidate != base and base not in candidate.parents:
        raise PermissionError("snapshot escape rejected")
    if not candidate.is_file():
        raise FileNotFoundError(relative)
    return candidate.read_bytes()


def publish_generation(directory: Path, generation: str, manifest: dict[str, Any]) -> Path:
    """Publish manifest, then atomically replace the sole current pointer."""
    directory.mkdir(parents=True, exist_ok=True)
    manifest_path = directory / f"manifest-{generation}.json"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=directory, delete=False) as stream:
        json.dump(manifest, stream, sort_keys=True, separators=(",", ":"))
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
        temporary = Path(stream.name)
    os.replace(temporary, manifest_path)
    pointer_tmp = directory / ".current.tmp"
    pointer_tmp.write_text(manifest_path.name + "\n", encoding="utf-8")
    with pointer_tmp.open("rb") as stream:
        os.fsync(stream.fileno())
    os.replace(pointer_tmp, directory / "current")
    return manifest_path


_SECRET = re.compile(r"(?i)(token|password|secret|authorization)=([^\s]+)")


def redact_log(raw: str, *, opt_in: bool = False, max_bytes: int = 64 * 1024) -> str:
    if not opt_in:
        raise PermissionError("raw log persistence requires explicit opt-in")
    if len(raw.encode("utf-8")) > max_bytes:
        raise ValueError("raw log exceeds capacity limit")
    return _SECRET.sub(r"\1=[REDACTED]", raw)
