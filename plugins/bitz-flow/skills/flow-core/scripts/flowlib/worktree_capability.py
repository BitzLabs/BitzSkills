"""M2 worktree write の単回承認 capability（FLW-NFR-007）。"""

from __future__ import annotations

import dataclasses
import threading
from collections.abc import Callable, Sequence
from datetime import datetime
from typing import Any


CODE_BLOCKED = "BLOCKED"
CODE_STALE = "STALE"

NONCE_UNUSED = "UNUSED"
NONCE_USED_PENDING = "USED_PENDING"
NONCE_USED_DONE = "USED_DONE"
NONCE_QUARANTINED = "QUARANTINED"
NONCE_STATES = frozenset(
    {NONCE_UNUSED, NONCE_USED_PENDING, NONCE_USED_DONE, NONCE_QUARANTINED}
)

_INSTANCE_OPERATIONS = frozenset(
    {"worktree.resume", "worktree.finish", "worktree.discard"}
)


@dataclasses.dataclass(frozen=True)
class CapabilityFailure:
    code: str
    reason: str


@dataclasses.dataclass(frozen=True)
class WorktreeApprovalCapability:
    """人間が確認した worktree write の署名対象を閉じ込める envelope。"""

    worktree_dir_guard_key: str
    worktree_registry_guard_key: str
    parent_dir_identity: str
    nonexistence_digest: str | None
    instance_identity_digest: str | None
    worktree_root_canonical: str
    case_sensitivity: bool
    expires_at: datetime
    nonce: str
    operation_id: str
    algorithm: str = "Ed25519"
    key_id: str = ""
    signature: str = ""

    def signed_payload(self) -> dict[str, Any]:
        """署名検証へ渡す canonical 化前の論理 payload を返す。"""
        return {
            "worktree_dir_guard_key": self.worktree_dir_guard_key,
            "worktree_registry_guard_key": self.worktree_registry_guard_key,
            "parent_dir_identity": self.parent_dir_identity,
            "nonexistence_digest": self.nonexistence_digest,
            "instance_identity_digest": self.instance_identity_digest,
            "worktree_root_canonical": self.worktree_root_canonical,
            "case_sensitivity": self.case_sensitivity,
            "expires_at": self.expires_at.isoformat(),
            "nonce": self.nonce,
            "operation_id": self.operation_id,
            "algorithm": self.algorithm,
            "key_id": self.key_id,
        }


@dataclasses.dataclass(frozen=True)
class WorktreeApprovalContext:
    """guard 取得直後と各副作用直前に再観測する現在値。"""

    worktree_dir_guard_key: str
    worktree_registry_guard_key: str
    parent_dir_identity: str
    nonexistence_digest: str | None
    instance_identity_digest: str | None
    worktree_root_canonical: str
    case_sensitivity: bool
    operation_id: str


SignatureVerifier = Callable[[dict[str, Any], str, str], bool]


#: 承認モード。`plan-digest` が既定で、trusted key registry のある配備だけ `signed-capability`。
MODE_PLAN_DIGEST = "plan-digest"
MODE_SIGNED_CAPABILITY = "signed-capability"
MODES = frozenset({MODE_PLAN_DIGEST, MODE_SIGNED_CAPABILITY})


def authorize_worktree_write(
    capability: WorktreeApprovalCapability | None,
    *,
    context: WorktreeApprovalContext,
    now: datetime,
    trusted_key_ids: Sequence[str],
    nonce_state: str,
    verify_signature: SignatureVerifier,
    mode: str = MODE_SIGNED_CAPABILITY,
) -> CapabilityFailure | None:
    """worktree write を in-band で許可できるか fail-closed に判定する。"""
    if mode == MODE_PLAN_DIGEST:
        return _authorize_plan_digest(context, nonce_state, (NONCE_UNUSED,))
    return _authorize_worktree_write(
        capability, context=context, now=now, trusted_key_ids=trusted_key_ids,
        nonce_state=nonce_state, allowed_nonce_states=(NONCE_UNUSED,),
        verify_signature=verify_signature,
    )


def reauthorize_pending_worktree_write(
    capability: WorktreeApprovalCapability | None,
    *,
    context: WorktreeApprovalContext,
    now: datetime,
    trusted_key_ids: Sequence[str],
    verify_signature: SignatureVerifier,
    mode: str = MODE_SIGNED_CAPABILITY,
) -> CapabilityFailure | None:
    """nonce消費後、各mutating step直前に同じscopeと署名を再検証する。"""
    if mode == MODE_PLAN_DIGEST:
        return _authorize_plan_digest(context, NONCE_USED_PENDING, (NONCE_USED_PENDING,))
    return _authorize_worktree_write(
        capability, context=context, now=now, trusted_key_ids=trusted_key_ids,
        nonce_state=NONCE_USED_PENDING, allowed_nonce_states=(NONCE_USED_PENDING,),
        verify_signature=verify_signature,
    )


def _authorize_plan_digest(
    context: WorktreeApprovalContext, nonce_state: str, allowed_nonce_states: Sequence[str],
) -> CapabilityFailure | None:
    """署名なしモードの判定（`SI-FLW-061`）。

    scope と freshness は `operation_id`（承認 context 全体の digest）と apply 側の
    plan 再導出が既に束縛しているため、ここでは**再確認しない**。
    自明に真になる比較を承認の根拠として並べると反証できない検査になるためである
    （`FLW-REV-016:SYN-007` と同じ失敗を持ち込まない）。

    本経路が担うのは次の2点だけである。

    1. nonce の単回性。nonce は `operation_id` から導出されるため承認へ束縛されている
    2. plan が生成した identity 観測が operation に対して整合していること
    """
    if nonce_state not in allowed_nonce_states:
        return CapabilityFailure(CODE_BLOCKED, f"承認 nonce は再利用できない: {nonce_state}")
    if context.operation_id == "worktree.create":
        if context.nonexistence_digest is None or context.instance_identity_digest is not None:
            return CapabilityFailure(CODE_BLOCKED, "create の identity 観測が不正")
    elif context.operation_id in _INSTANCE_OPERATIONS:
        if context.instance_identity_digest is None or context.nonexistence_digest is not None:
            return CapabilityFailure(CODE_BLOCKED, "instance operation の identity 観測が不正")
    else:
        return CapabilityFailure(CODE_BLOCKED, "承認対象外の operation")
    return None


def _authorize_worktree_write(
    capability: WorktreeApprovalCapability | None,
    *, context: WorktreeApprovalContext, now: datetime,
    trusted_key_ids: Sequence[str], nonce_state: str,
    allowed_nonce_states: Sequence[str], verify_signature: SignatureVerifier,
) -> CapabilityFailure | None:
    if capability is None:
        return CapabilityFailure(CODE_BLOCKED, "単回承認 capability が無いため write を開始しない")
    if capability.algorithm != "Ed25519":
        return CapabilityFailure(CODE_BLOCKED, "許可されない署名方式")
    if capability.key_id not in trusted_key_ids:
        return CapabilityFailure(CODE_BLOCKED, "失効または未登録の署名鍵")
    if not capability.signature or not verify_signature(
        capability.signed_payload(), capability.signature, capability.key_id
    ):
        return CapabilityFailure(CODE_BLOCKED, "capability の署名を検証できない")
    if now >= capability.expires_at:
        return CapabilityFailure(CODE_BLOCKED, "capability の有効期限が切れている")
    if nonce_state not in allowed_nonce_states:
        return CapabilityFailure(CODE_BLOCKED, f"capability nonce は再利用できない: {nonce_state}")

    scope_pairs = (
        ("operation", capability.operation_id, context.operation_id),
        ("worktree-dir guard", capability.worktree_dir_guard_key, context.worktree_dir_guard_key),
        (
            "worktree-registry guard",
            capability.worktree_registry_guard_key,
            context.worktree_registry_guard_key,
        ),
        ("worktree root", capability.worktree_root_canonical, context.worktree_root_canonical),
        ("case sensitivity", capability.case_sensitivity, context.case_sensitivity),
    )
    for label, approved, current in scope_pairs:
        if approved != current:
            return CapabilityFailure(CODE_BLOCKED, f"capability の {label} scope が一致しない")

    freshness_pairs = (
        ("parent directory identity", capability.parent_dir_identity, context.parent_dir_identity),
        ("nonexistence digest", capability.nonexistence_digest, context.nonexistence_digest),
        (
            "instance identity digest",
            capability.instance_identity_digest,
            context.instance_identity_digest,
        ),
    )
    for label, approved, current in freshness_pairs:
        if approved != current:
            return CapabilityFailure(CODE_STALE, f"承認後に {label} が変化した")

    if context.operation_id == "worktree.create":
        if capability.nonexistence_digest is None or capability.instance_identity_digest is not None:
            return CapabilityFailure(CODE_BLOCKED, "create capability の identity field が不正")
    elif context.operation_id in _INSTANCE_OPERATIONS:
        if capability.instance_identity_digest is None or capability.nonexistence_digest is not None:
            return CapabilityFailure(CODE_BLOCKED, "instance capability の identity field が不正")
    else:
        return CapabilityFailure(CODE_BLOCKED, "capability 対象外の operation")
    return None


class NonceLedger:
    """target guard 内で使う nonce 状態機械。状態遷移を process 内で直列化する。"""

    def __init__(self) -> None:
        self._states: dict[str, str] = {}
        self._lock = threading.Lock()

    def state(self, nonce: str) -> str:
        with self._lock:
            return self._states.get(nonce, NONCE_UNUSED)

    def begin(self, nonce: str) -> bool:
        with self._lock:
            if self._states.get(nonce, NONCE_UNUSED) != NONCE_UNUSED:
                return False
            self._states[nonce] = NONCE_USED_PENDING
            return True

    def finish(self, nonce: str, *, quarantined: bool = False) -> bool:
        with self._lock:
            if self._states.get(nonce) != NONCE_USED_PENDING:
                return False
            self._states[nonce] = NONCE_QUARANTINED if quarantined else NONCE_USED_DONE
            return True


@dataclasses.dataclass(frozen=True)
class WorktreeBindingObservation:
    directory_exists: bool
    registry_exists: bool
    bidirectional_binding_valid: bool


@dataclasses.dataclass(frozen=True)
class WorktreeAuditFinding:
    worktree_state: str
    result_code: str
    quarantine_required: bool
    reason: str


def audit_external_binding_change(
    observation: WorktreeBindingObservation,
) -> WorktreeAuditFinding | None:
    """guard 外の削除・registry 改変を ORPHAN として quarantine へ接続する。"""
    if (
        observation.directory_exists
        and observation.registry_exists
        and observation.bidirectional_binding_valid
    ):
        return None
    return WorktreeAuditFinding(
        worktree_state="ORPHAN",
        result_code=CODE_BLOCKED,
        quarantine_required=True,
        reason="worktree directory と registry の外部変更または相互参照不一致を検出した",
    )


def audit_unmanaged_worktree(paths: Sequence[str]) -> WorktreeAuditFinding | None:
    """receipt に裏付けの無い worktree を `ORPHAN` として quarantine へ接続する。

    `audit_external_binding_change` は「登録済み worktree の binding が壊れた」場合を見る。
    こちらは「bitz-flow の operation が作っていない worktree が registry にいる」場合で、
    `FLW-DSN-016 §7` の guard 外要因（手動 `git worktree add`・外部ツール・別クローンからの
    操作）に当たる。どちらも外部起因の `ORPHAN` であり、§6 の解除区分へ接続する点は同じ。

    公開 `worktree.audit` は検出（前半）だけを実装しており、quarantine への接続（後半）に
    対応する語彙が出力に無かった（`FLW-REV-017:SYN-011` / `RVC-302`）。
    """
    if not paths:
        return None
    return WorktreeAuditFinding(
        worktree_state="ORPHAN",
        result_code=CODE_BLOCKED,
        quarantine_required=True,
        reason=f"receipt に対応の無い worktree を {len(paths)} 件検出した",
    )
