"""qualification の raw event log を安全に扱う guard（FLW-NFR-011 / FLW-FR-013）。

raw log は診断価値が高い一方で、秘密値と個人環境が最も混ざりやすい成果物である。
本モジュールは**保存境界とライフサイクル**だけを担当し、遮断そのものは `flowlib/sanitize.py` に委ねる
（遮断ロジックをここで再実装しない）。

安全側に倒す既定:

- **canary 未検出は「安全」ではない**。redaction が効きすぎて観測不能か、log が欠落しているかの
  どちらかであり、いずれも Gate 停止事由とする。「秘密値が見つからなかったから OK」と読み替えない。
- 保持期限は最大 30 日。自動延長しない（legal hold は別 record を人間が用意した場合のみ）。
- 削除は証跡（対象 digest・時刻・担当）とセットでのみ認める。
"""

from __future__ import annotations

import dataclasses
import os
import stat
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, Sequence

_SKILL = Path(__file__).resolve().parents[3] / "plugins" / "bitz-flow" / "skills" / "flow-core"
sys.path.insert(0, str(_SKILL / "scripts"))

from flowlib import result as R  # noqa: E402
from flowlib import sanitize as S  # noqa: E402

CODE_BLOCKED = "BLOCKED"
CODE_INVALID_INPUT = "INVALID_INPUT"

ALLOWED_ROLES = ("owner", "evaluation-reviewer")
MAX_RETENTION_DAYS = 30
REDACTION_VERSION = "1"

_OWNER_ONLY_DIR = 0o700
_OWNER_ONLY_FILE = 0o600


@dataclasses.dataclass(frozen=True)
class GuardFailure:
    code: str
    reason: str


@dataclasses.dataclass(frozen=True)
class DeletionReceipt:
    target_digest: str
    deleted_at: str
    deleted_by: str

    def as_dict(self) -> dict[str, str]:
        return dataclasses.asdict(self)


@dataclasses.dataclass
class StoredLog:
    path: Path
    digest: str
    redaction_version: str
    canary_detected: bool
    stored_at: datetime
    delete_by: datetime
    delete_owner: str
    redactions: tuple[str, ...] = ()


def redact(text: str) -> tuple[str, list[str]]:
    """行単位で sanitizer にかけ、通らなかった値を伏せる。

    遮断の判断は sanitizer が持つ。ここでは「置き換える」ことだけを行い、
    遮断した種別を可視化のために返す。
    """
    kinds: list[str] = []
    out: list[str] = []
    for line in text.splitlines():
        safe_parts = []
        for token in line.split(" "):
            if not token:
                safe_parts.append(token)
                continue
            kind = S.classify(token)
            if kind is None:
                safe_parts.append(token)
            else:
                kinds.append(kind)
                digest = R.sha256_of(token.encode("utf-8"))
                safe_parts.append(f"[REDACTED:{kind}:len={len(token)}:{digest[:14]}]")
        out.append(" ".join(safe_parts))
    return "\n".join(out), kinds


class RawLogGuard:
    """raw log の保存・検査・削除を owner-only 境界の中で行う。"""

    def __init__(self, root: Path, *, owner: str, retention_days: int = MAX_RETENTION_DAYS) -> None:
        self._root = Path(root)
        self._owner = owner
        self._retention_days = retention_days
        self._receipts: list[DeletionReceipt] = []

    # -- 保存 ----------------------------------------------------------------

    def store(
        self, name: str, text: str, *, canaries: Sequence[str], now: datetime
    ) -> tuple[StoredLog | None, GuardFailure | None]:
        """redaction を通した log を owner-only で保存する。

        canary は**redaction 前の原文**に対して検出する。redaction 後の本文から探すと、
        canary 自体が伏せられて必ず未検出になり、検査が意味を失う。
        """
        if self._retention_days > MAX_RETENTION_DAYS:
            return None, GuardFailure(
                CODE_INVALID_INPUT,
                f"保持期限は最大 {MAX_RETENTION_DAYS} 日（指定: {self._retention_days} 日）",
            )
        if not canaries:
            return None, GuardFailure(
                CODE_BLOCKED, "canary を仕込まない log は観測可能性を検査できない"
            )

        detected = S.detect_canaries(text, canaries)
        if not detected:
            return None, GuardFailure(
                CODE_BLOCKED,
                "秘密値 canary を検出できない（log 欠落または観測不能）— 安全とは扱わない",
            )

        redacted, kinds = redact(text)

        try:
            self._root.mkdir(parents=True, exist_ok=True, mode=_OWNER_ONLY_DIR)
            path = self._root / name
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, _OWNER_ONLY_FILE)
            try:
                os.write(fd, redacted.encode("utf-8"))
            finally:
                os.close(fd)
            os.chmod(path, _OWNER_ONLY_FILE)
            os.chmod(self._root, _OWNER_ONLY_DIR)
        except OSError as exc:
            return None, GuardFailure(CODE_BLOCKED, f"raw log を保存できない: {exc.strerror}")

        return (
            StoredLog(
                path=path,
                digest=R.sha256_of(redacted.encode("utf-8")),
                redaction_version=REDACTION_VERSION,
                canary_detected=True,
                stored_at=now,
                delete_by=now + timedelta(days=self._retention_days),
                delete_owner=self._owner,
                redactions=tuple(kinds),
            ),
            None,
        )

    # -- 読み取り ------------------------------------------------------------

    def read(self, log: StoredLog, *, role: str) -> tuple[str | None, GuardFailure | None]:
        if role not in ALLOWED_ROLES:
            return None, GuardFailure(
                CODE_BLOCKED, f"role '{role}' には raw log の読み取りを許さない"
            )
        try:
            return log.path.read_text(encoding="utf-8"), None
        except OSError as exc:
            return None, GuardFailure(CODE_BLOCKED, f"raw log を読めない: {exc.strerror}")

    # -- 境界の検査 ----------------------------------------------------------

    def check_permissions(self, log: StoredLog) -> GuardFailure | None:
        """group / other から読める状態を許さない。"""
        for target in (log.path, self._root):
            mode = target.stat().st_mode
            if mode & (stat.S_IRWXG | stat.S_IRWXO):
                return GuardFailure(
                    CODE_BLOCKED, f"owner 以外から到達できる permission: {target.name}"
                )
        return None

    def check_expiry(self, log: StoredLog, *, now: datetime) -> GuardFailure | None:
        """保持期限を過ぎた log が残っていないか。"""
        if now >= log.delete_by:
            return GuardFailure(
                CODE_BLOCKED, "保持期限を過ぎた raw log が削除されずに残っている"
            )
        return None

    def check_no_secret_remains(self, log: StoredLog, secrets_: Iterable[str]) -> GuardFailure | None:
        """redaction 後の本文に秘密値が残っていないか。"""
        text = log.path.read_text(encoding="utf-8")
        remaining = [s for s in secrets_ if s and s in text]
        if remaining:
            return GuardFailure(
                CODE_BLOCKED, f"redaction 後も秘密値が {len(remaining)} 件残っている"
            )
        return None

    # -- 削除 ----------------------------------------------------------------

    def delete(
        self, log: StoredLog, *, deleted_by: str, now: datetime
    ) -> tuple[DeletionReceipt | None, GuardFailure | None]:
        """削除は証跡とセットでのみ行う。"""
        if not deleted_by:
            return None, GuardFailure(CODE_BLOCKED, "削除担当の記録が無い削除を認めない")
        try:
            log.path.unlink()
        except OSError as exc:
            return None, GuardFailure(CODE_BLOCKED, f"raw log を削除できない: {exc.strerror}")

        receipt = DeletionReceipt(
            target_digest=log.digest,
            deleted_at=now.isoformat().replace("+00:00", "Z"),
            deleted_by=deleted_by,
        )
        self._receipts.append(receipt)
        return receipt, None

    def receipts(self) -> list[dict[str, str]]:
        return [r.as_dict() for r in self._receipts]

    # -- manifest 用 ---------------------------------------------------------

    def retention_block(self, log: StoredLog) -> dict[str, object]:
        """qualification manifest の `retention` へそのまま載せる辞書。"""
        return {
            "storage_boundary": str(self._root.name),
            "allowed_roles": list(ALLOWED_ROLES),
            "redaction_version": log.redaction_version,
            "max_retention_days": self._retention_days,
            "delete_by": log.delete_by.isoformat().replace("+00:00", "Z"),
            "delete_owner": log.delete_owner,
            "canary_detected": log.canary_detected,
            "deletion_receipts": self.receipts(),
        }
