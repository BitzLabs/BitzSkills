"""intent record と evidence ledger が共有する append-only 永続化層（FLW-DSN-015）。

**directory fsync の完了が durability commit point** である。ここに到達するまで、呼出側は
副作用を開始してはならない。本モジュールはそれを型で表現する: 副作用を伴う処理は `Commit` を
要求し、`Commit` は commit point を越えた場合にしか生成されない。中断すれば `Commit` は存在せず、
呼出側は「記録なしの副作用」を実行しようがない。

安全側に倒す既定:

- 記録が残って副作用が起きなかった状態（無駄な BLOCKED）は許すが、その逆は許さない。
- chain 破損・欠番・重複 ID を見つけても**自動修復しない**。隔離して BLOCKED を返し、人間へ渡す。
- RPO 0 のため、primary と独立 failure domain の replica の**双方**が ack しない限り commit しない。
"""

from __future__ import annotations

import dataclasses
import json
import os
import time
from pathlib import Path
from typing import Any, Callable, Protocol

from . import result as R

CODE_BLOCKED = "BLOCKED"
CODE_UNSUPPORTED = "UNSUPPORTED"

#: append の各段階。fault 注入はこの境界でのみ行う。
STEP_TEMP_WRITTEN = "temp-written"
STEP_FILE_FSYNCED = "file-fsynced"
STEP_RENAMED = "renamed"
STEP_DIR_FSYNCED = "dir-fsynced"
STEPS = (STEP_TEMP_WRITTEN, STEP_FILE_FSYNCED, STEP_RENAMED, STEP_DIR_FSYNCED)

_ENTRY_SUFFIX = ".json"
_TEMP_SUFFIX = ".json.tmp"
_QUARANTINE_DIR = "quarantine"
_OWNER_ONLY_DIR = 0o700
_OWNER_ONLY_FILE = 0o600


@dataclasses.dataclass(frozen=True)
class Commit:
    """durability commit point に到達したことの証明。

    副作用（Git の mutation 等）を行う関数は、この型を引数に要求することで
    「intent が永続化される前に副作用を開始しない」ことを構造的に保証する。
    """

    sequence: int
    entry_digest: str
    previous_digest: str | None
    latency_ms: float


@dataclasses.dataclass(frozen=True)
class DurableFailure:
    code: str
    reason: str
    stage: str = "apply"


@dataclasses.dataclass(frozen=True)
class ScanReport:
    entries: list[dict[str, Any]]
    head_digest: str | None
    head_sequence: int
    torn: list[str]
    problems: list[str]

    @property
    def healthy(self) -> bool:
        return not self.problems


class Replica(Protocol):
    """独立 failure domain の同期 replica。"""

    def append_wal(self, entry_bytes: bytes, digest: str) -> bool:
        """WAL entry を fsync まで完了できたら True。"""


class DurableLog:
    """1 entry 1 file の hash-chain append-only ログ。

    `root` は対象 repo の Git common-dir 配下の owner-only 領域を想定する。
    `step_hook` は fault 注入テスト専用で、各段階の直後に呼ばれる。
    """

    def __init__(
        self,
        root: Path,
        *,
        replica: Replica,
        step_hook: Callable[[str, Path], None] | None = None,
    ) -> None:
        self._root = Path(root)
        self._replica = replica
        self._hook = step_hook
        self._appends = 0
        self._chain_problems = 0

    # -- 観測点（SLI）--------------------------------------------------------

    def stats(self) -> dict[str, int]:
        """運用 SLI の観測点。閾値判定は本モジュールの責務ではない。"""
        return {"appends": self._appends, "chain_problems": self._chain_problems}

    # -- 追記 ----------------------------------------------------------------

    def append(self, payload: dict[str, Any]) -> tuple[Commit | None, DurableFailure | None]:
        started = time.monotonic()

        report, failure = self.scan()
        if failure is not None:
            return None, failure
        if not report.healthy:
            self._chain_problems += 1
            return None, DurableFailure(
                CODE_BLOCKED,
                "chain が健全でないため追記しない（自動修復しない）: " + "; ".join(report.problems),
            )

        sequence = report.head_sequence + 1
        entry = dict(payload)
        entry["sequence"] = sequence
        entry["previous_entry_digest"] = report.head_digest
        body = R.canonical_bytes(entry)
        digest = R.sha256_of(body)
        record = R.canonical_bytes({"entry": entry, "entry_digest": digest})

        try:
            self._root.mkdir(parents=True, exist_ok=True, mode=_OWNER_ONLY_DIR)
        except OSError as exc:
            return None, DurableFailure(CODE_BLOCKED, f"永続領域を用意できない: {exc.strerror}")

        dest = self._root / f"{sequence:012d}{_ENTRY_SUFFIX}"
        temp = self._root / f"{sequence:012d}{_TEMP_SUFFIX}"
        if dest.exists():
            return None, DurableFailure(CODE_BLOCKED, f"既存 entry を上書きしない: {dest.name}")

        try:
            fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, _OWNER_ONLY_FILE)
            try:
                os.write(fd, record)
                self._fire(STEP_TEMP_WRITTEN, temp)
                os.fsync(fd)
                self._fire(STEP_FILE_FSYNCED, temp)
            finally:
                os.close(fd)

            os.replace(temp, dest)
            self._fire(STEP_RENAMED, dest)

            failure = self._fsync_dir()
            if failure is not None:
                return None, failure
            self._fire(STEP_DIR_FSYNCED, dest)
        except _Interrupted as exc:
            # fault 注入による中断。commit point 未到達なので Commit を返さない。
            return None, DurableFailure(CODE_BLOCKED, f"append が {exc.step} で中断した")
        except OSError as exc:
            return None, DurableFailure(CODE_BLOCKED, f"append に失敗した: {exc.strerror}")

        # RPO 0: primary が commit しても replica の ack が無ければ呼出側へ ack しない。
        try:
            acked = self._replica.append_wal(record, digest)
        except Exception as exc:
            return None, DurableFailure(
                CODE_BLOCKED, f"replica の ack を確認できない: {type(exc).__name__}"
            )
        if not acked:
            return None, DurableFailure(
                CODE_BLOCKED, "replica が ack しないため RPO 0 を満たせない（新しい attempt を開始しない）"
            )

        self._appends += 1
        return (
            Commit(
                sequence=sequence,
                entry_digest=digest,
                previous_digest=report.head_digest,
                latency_ms=(time.monotonic() - started) * 1000.0,
            ),
            None,
        )

    # -- 走査と隔離 ----------------------------------------------------------

    def scan(self) -> tuple[ScanReport | None, DurableFailure | None]:
        """読み取り専用の走査。torn entry と chain 異常を**報告**する（修復しない）。"""
        if not self._root.exists():
            return ScanReport([], None, 0, [], []), None

        torn = sorted(p.name for p in self._root.glob(f"*{_TEMP_SUFFIX}"))
        problems: list[str] = []
        entries: list[dict[str, Any]] = []
        head_digest: str | None = None
        head_sequence = 0

        paths = sorted(self._root.glob(f"*{_ENTRY_SUFFIX}"))
        seen_sequences: set[int] = set()
        for path in paths:
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                problems.append(f"{path.name}: entry を読めない（torn の疑い）")
                continue

            entry = record.get("entry")
            stored_digest = record.get("entry_digest")
            if not isinstance(entry, dict) or not isinstance(stored_digest, str):
                problems.append(f"{path.name}: entry の形式が不正")
                continue
            if R.sha256_of(R.canonical_bytes(entry)) != stored_digest:
                problems.append(f"{path.name}: digest 不一致（改変または torn）")
                continue

            sequence = entry.get("sequence")
            if not isinstance(sequence, int):
                problems.append(f"{path.name}: sequence が無い")
                continue
            if sequence in seen_sequences:
                problems.append(f"{path.name}: sequence {sequence} が重複している")
                continue
            if sequence != head_sequence + 1:
                problems.append(f"{path.name}: sequence が {head_sequence + 1} でなく {sequence}（欠番）")
                continue
            if entry.get("previous_entry_digest") != head_digest:
                problems.append(f"{path.name}: previous_entry_digest が chain と一致しない")
                continue

            seen_sequences.add(sequence)
            entries.append(entry)
            head_digest = stored_digest
            head_sequence = sequence

        return ScanReport(entries, head_digest, head_sequence, torn, problems), None

    def quarantine_torn(self, report: ScanReport) -> tuple[list[str], DurableFailure | None]:
        """torn entry を隔離ディレクトリへ移す。修復ではなく分離である。"""
        if not report.torn:
            return [], None
        target = self._root / _QUARANTINE_DIR
        try:
            target.mkdir(parents=True, exist_ok=True, mode=_OWNER_ONLY_DIR)
            moved = []
            for name in report.torn:
                os.replace(self._root / name, target / name)
                moved.append(name)
        except OSError as exc:
            return [], DurableFailure(CODE_BLOCKED, f"torn entry を隔離できない: {exc.strerror}")
        return moved, None

    # -- 内部 ----------------------------------------------------------------

    def _fsync_dir(self) -> DurableFailure | None:
        """directory fsync。提供できない platform では write 自体を UNSUPPORTED にする。"""
        try:
            dir_fd = os.open(self._root, os.O_RDONLY)
        except OSError:
            return DurableFailure(
                CODE_UNSUPPORTED,
                "directory fsync を提供できない platform では durability commit point を保証できない",
                stage="validate",
            )
        try:
            os.fsync(dir_fd)
        except OSError:
            return DurableFailure(
                CODE_UNSUPPORTED,
                "directory fsync に失敗したため durability を保証できない",
                stage="validate",
            )
        finally:
            os.close(dir_fd)
        return None

    def _fire(self, step: str, path: Path) -> None:
        if self._hook is not None:
            self._hook(step, path)


class _Interrupted(Exception):
    """fault 注入テストが append を中断させるための例外。"""

    def __init__(self, step: str):
        super().__init__(step)
        self.step = step


def crash_after(step: str) -> Callable[[str, Path], None]:
    """指定した段階の直後に append を中断させる hook を返す（fault fixture 用）。"""
    if step not in STEPS:
        raise ValueError(f"未知の段階: {step}")

    def _hook(current: str, _path: Path) -> None:
        if current == step:
            raise _Interrupted(current)

    return _hook
