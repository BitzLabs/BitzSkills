"""正本台帳の保全と復旧（FLW-NFR-007 / FLW-NFR-011 / FLW-DSN-015）。

`FLW-DSN-015` は「M1 中に最低1回 restore fixture で RPO/RTO を検証する」と定めている。
その1回をここで行う。

- **RPO 0** — primary が全損しても、**ack 済み（確認済み）entry の欠落が 0** であること。
  replica の WAL から chain を再構成できる。
- **RTO 4時間** — 復旧手順の所要時間を計測できる形にする。手順が「たぶん動く」ではなく
  「実際に動いて何秒だった」と言える状態にしておく。

backup は暗号化する。台帳そのものに秘密値は入れない設計だが、attempt の metadata や
run 固有情報が漏れる経路を残さないため、保存時点で暗号化しておく。
"""

from __future__ import annotations

import base64
import dataclasses
import hashlib
import hmac
import json
import os
import time
from pathlib import Path
from typing import Iterable, Sequence

CODE_BLOCKED = "BLOCKED"
CODE_OK = "OK"

#: 運用 SLI。閾値判定そのものは呼出側の責務。
SLI_MAX_APPEND_LATENCY_MS_P95 = 2000.0
SLI_MIN_AVAILABILITY = 0.99
SLI_MAX_CHAIN_INCONSISTENCY = 0
RTO_SECONDS = 4 * 3600


@dataclasses.dataclass(frozen=True)
class RecoveryFailure:
    code: str
    reason: str


@dataclasses.dataclass(frozen=True)
class Backup:
    path: Path
    entry_count: int
    chain_digest: str
    created_at: float


@dataclasses.dataclass(frozen=True)
class RestoreReport:
    restored_entries: int
    missing_acked_entries: int
    chain_digest: str
    elapsed_seconds: float

    @property
    def rpo_zero(self) -> bool:
        return self.missing_acked_entries == 0

    @property
    def within_rto(self) -> bool:
        return self.elapsed_seconds <= RTO_SECONDS


def chain_digest(entries: Sequence[dict]) -> str:
    """entry 列を順序込みで要約する。復旧前後の同一性判定に使う。"""
    digest = hashlib.sha256()
    for entry in entries:
        digest.update(
            json.dumps(entry, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        )
        digest.update(b"\x1e")
    return f"sha256:{digest.hexdigest()}"


def _cipher(key: bytes, data: bytes) -> bytes:
    """HMAC ベースの keystream による対称暗号（依存を増やさないための最小実装）。

    強度は AEAD に劣る。**秘密値を台帳へ書かない**という一次防御があり、これは
    「backup ファイルを平文で置かない」ための二次防御である。
    """
    out = bytearray()
    counter = 0
    while len(out) < len(data):
        block = hmac.new(key, counter.to_bytes(8, "big"), hashlib.sha256).digest()
        out.extend(block)
        counter += 1
    return bytes(a ^ b for a, b in zip(data, out))


def backup(entries: Sequence[dict], destination: Path, *, key: bytes) -> Backup:
    """正本 snapshot を暗号化して保存する。"""
    payload = json.dumps(
        {"entries": list(entries)}, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    body = _cipher(key, payload)
    mac = hmac.new(key, body, hashlib.sha256).hexdigest()

    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, json.dumps({"mac": mac, "body": base64.b64encode(body).decode()}).encode())
        os.fsync(fd)
    finally:
        os.close(fd)

    return Backup(
        path=destination,
        entry_count=len(entries),
        chain_digest=chain_digest(entries),
        created_at=time.time(),
    )


def read_backup(path: Path, *, key: bytes) -> tuple[list[dict] | None, RecoveryFailure | None]:
    try:
        stored = json.loads(path.read_text(encoding="utf-8"))
        body = base64.b64decode(stored["body"])
    except (OSError, ValueError, KeyError) as exc:
        return None, RecoveryFailure(CODE_BLOCKED, f"backup を読めない: {type(exc).__name__}")

    if not hmac.compare_digest(stored["mac"], hmac.new(key, body, hashlib.sha256).hexdigest()):
        return None, RecoveryFailure(CODE_BLOCKED, "backup の MAC が一致しない（改変の疑い）")

    payload = json.loads(_cipher(key, body).decode("utf-8"))
    return payload["entries"], None


def restore_from_replica(
    backup_path: Path,
    replica_wal: Iterable[dict],
    *,
    key: bytes,
    acked_entry_ids: Sequence[int],
) -> tuple[RestoreReport | None, RecoveryFailure | None]:
    """primary 全損から復旧する。

    backup snapshot に replica の WAL を重ねて chain を再構成し、
    **ack 済み entry の欠落が 0** であることを確かめる。
    """
    started = time.monotonic()

    snapshot, failure = read_backup(backup_path, key=key)
    if failure is not None:
        return None, failure

    merged: dict[int, dict] = {}
    for entry in list(snapshot) + list(replica_wal):
        attempt_id = entry.get("attempt_id")
        if attempt_id is None:
            return None, RecoveryFailure(CODE_BLOCKED, "attempt_id を持たない entry がある")
        merged[attempt_id] = entry

    ordered = [merged[key_] for key_ in sorted(merged)]
    missing = [i for i in acked_entry_ids if i not in merged]

    return (
        RestoreReport(
            restored_entries=len(ordered),
            missing_acked_entries=len(missing),
            chain_digest=chain_digest(ordered),
            elapsed_seconds=time.monotonic() - started,
        ),
        None,
    )


@dataclasses.dataclass
class SliObserver:
    """運用 SLI の観測点。閾値判定は呼出側が行う。"""

    append_latencies_ms: list[float] = dataclasses.field(default_factory=list)
    chain_inconsistencies: int = 0
    coordinator_probes: int = 0
    coordinator_failures: int = 0

    def record_append(self, latency_ms: float) -> None:
        self.append_latencies_ms.append(latency_ms)

    def record_probe(self, *, ok: bool) -> None:
        self.coordinator_probes += 1
        if not ok:
            self.coordinator_failures += 1

    def p95_append_latency_ms(self) -> float | None:
        if not self.append_latencies_ms:
            return None
        ordered = sorted(self.append_latencies_ms)
        index = max(0, int(round(0.95 * len(ordered))) - 1)
        return ordered[index]

    def availability(self) -> float | None:
        if self.coordinator_probes == 0:
            return None
        return 1.0 - (self.coordinator_failures / self.coordinator_probes)

    def breaches(self) -> list[str]:
        """閾値を割った SLI を並べる（判定材料。停止するかは呼出側）。"""
        found: list[str] = []
        latency = self.p95_append_latency_ms()
        if latency is not None and latency > SLI_MAX_APPEND_LATENCY_MS_P95:
            found.append(f"append latency p95 が {SLI_MAX_APPEND_LATENCY_MS_P95}ms を超えた")
        availability = self.availability()
        if availability is not None and availability < SLI_MIN_AVAILABILITY:
            found.append(f"coordinator availability が {SLI_MIN_AVAILABILITY} を下回った")
        if self.chain_inconsistencies > SLI_MAX_CHAIN_INCONSISTENCY:
            found.append("hash-chain / fencing の不整合を検出した")
        return found
