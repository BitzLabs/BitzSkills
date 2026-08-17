"""M2 worktree finish/discard・retention・quarantine安全核。"""

from __future__ import annotations

import dataclasses
from datetime import datetime
from typing import Any, Iterable, Mapping, Sequence


FINISH_STEPS = (
    "verify-pr-merge", "verify-target-oid", "verify-reachability", "create-retention-ref",
    "remove-registry-entry", "remove-worktree-dir", "delete-local-branch",
)
DISCARD_STEPS = (
    "freeze-manifest", "verify-manifest-scope", "create-retention-ref",
    "remove-registry-entry", "remove-worktree-dir", "delete-local-branch",
)
#: `create` / `resume` の step 列。`worktree_runtime.MUTATING_STEPS` と同じ語彙を使う
#: （`SI-FLW-057`。M2 scope の2 operation に前進経路が無かったための追加）。
#: `finish` / `discard` の語彙不一致（`FLW-REV-016:SYN-002`）は M3 の `SI-FLW-060` が扱う。
CREATE_STEPS = ("git-worktree-add",)
RESUME_STEPS = ("publish-resume-receipt",)

STEPS_BY_OPERATION = {
    "worktree.create": CREATE_STEPS,
    "worktree.resume": RESUME_STEPS,
    "worktree.finish": FINISH_STEPS,
    "worktree.discard": DISCARD_STEPS,
}

MUTATING_STEPS = frozenset(
    {"create-retention-ref", "remove-registry-entry", "remove-worktree-dir", "delete-local-branch",
     "git-worktree-add", "publish-resume-receipt"}
)

# release_class（quarantine 解除区分。正は schemas/result-v1.schema.json $defs/release_class。
# FLW-DSN-016 §2 所在表・§6）。`classify_quarantine` はこの4定数以外を返さない。
RELEASE_NOT_STARTED = "worktree-not-started"
RELEASE_RESUMABLE = "worktree-resumable"
RELEASE_CONFIRMED_DONE = "worktree-confirmed-done"
RELEASE_UNRESOLVED = "worktree-unresolved"
RELEASE_CLASSES = (RELEASE_NOT_STARTED, RELEASE_RESUMABLE, RELEASE_CONFIRMED_DONE, RELEASE_UNRESOLVED)


@dataclasses.dataclass(frozen=True)
class CleanupDecision:
    code: str
    completed_steps: tuple[str, ...] = ()
    remaining_steps: tuple[str, ...] = ()
    recovery_class: str = "human-stop"
    reason: str = ""


def reconcile_steps(operation: str, completed: tuple[str, ...]) -> CleanupDecision:
    """receipt の completed 列から前進可否を判定する。

    以前は `finish` 以外をすべて `DISCARD_STEPS` と比較しており、`create` / `resume` は
    **黙って別 operation の step 列に照合されていた**（`SI-FLW-057`）。
    未知の operation は既定へ倒さず `INDETERMINATE` にする。
    """
    steps = STEPS_BY_OPERATION.get(operation)
    if steps is None:
        return CleanupDecision("INDETERMINATE", reason=f"reconcile 対象外の operation: {operation}")
    if completed != steps[: len(completed)]:
        return CleanupDecision("INDETERMINATE", reason="receipt chainがstep列のprefixでない")
    if completed == steps:
        return CleanupDecision("DONE", completed)
    return CleanupDecision(
        "PARTIAL", completed, steps[len(completed) :], "reconcile-only",
        "残stepは新plan・新承認・新operation IDまで自動実行しない",
    )


def finish_precondition(
    *, work_unit_state: str, worktree_state: str, branch_audit_state: str,
    backup_receipt: bool, merge_proof: bool, target_oid_matches: bool, reachable: bool,
) -> CleanupDecision:
    if work_unit_state != "AUDITED" or branch_audit_state != "MERGED_EXACT":
        return CleanupDecision("BLOCKED", reason="finishはAUDITEDかつMERGED_EXACTだけ許可")
    if worktree_state == "MISMATCH":
        return CleanupDecision("BLOCKED", reason="MISMATCH worktreeは削除しない")
    if worktree_state == "DIRTY" and not backup_receipt:
        return CleanupDecision("BLOCKED", reason="dirty worktreeの退避receiptが無い")
    if not (merge_proof and target_oid_matches and reachable):
        return CleanupDecision("BLOCKED", reason="merge・target OID・到達性証跡が不足")
    return CleanupDecision("DONE")


@dataclasses.dataclass(frozen=True)
class ManifestTarget:
    path: str
    kind: str
    identity: str


@dataclasses.dataclass(frozen=True)
class DiscardManifest:
    digest: str
    instance_digest: str
    targets: tuple[ManifestTarget, ...]
    root: str


def validate_discard(
    manifest: DiscardManifest, *, expected_digest: str, observed_instance_digest: str,
    backup_receipt: bool, dirty: bool, stable_identity_supported: bool,
) -> CleanupDecision:
    if manifest.digest != expected_digest:
        return CleanupDecision("STALE", recovery_class="replan-human", reason="manifest digest不一致")
    if manifest.instance_digest != observed_instance_digest:
        return CleanupDecision("STALE", recovery_class="replan-human", reason="instance identity不一致")
    if dirty and not backup_receipt:
        return CleanupDecision("BLOCKED", reason="dirty/untracked内容の退避が無い")
    if not stable_identity_supported:
        return CleanupDecision("UNSUPPORTED", reason="stable identity/dirfd相対削除を確保できない")
    root = manifest.root.rstrip("/") + "/"
    for target in manifest.targets:
        normalized = target.path.replace("\\", "/")
        if not normalized.startswith(root) or "/../" in normalized or not target.identity:
            return CleanupDecision("BLOCKED", reason="manifestにroot外またはidentity不明targetがある")
    return CleanupDecision("DONE")


def validate_next_graph(*, result_code: str, nodes: Iterable[str], human_approval: bool) -> bool:
    nodes = tuple(nodes)
    if "git.delete-remote-branch.apply" in nodes:
        return False
    if result_code in {"PARTIAL", "STALE", "INDETERMINATE"}:
        if any(node.endswith(".apply") for node in nodes) and not human_approval:
            return False
    return True


@dataclasses.dataclass(frozen=True)
class QuarantineEvidence:
    chain_valid: bool
    completed_steps: tuple[str, ...]
    instance_nonce_matches: bool
    mutation_receipts: int
    all_postconditions_match: bool
    #: この target に対する bitz-flow の intent（PENDING を含む receipt 記録）が
    #: 1件でも存在するか。既定 True は「呼出側が明示しない限り従来どおり存在する
    #: 前提を保つ」ための後方互換値（既存呼出側は intent の有無を区別していなかった）。
    #: `worktree.audit` は §7 の「bitz-flow が作っていない worktree」（`unmanaged`）を
    #: `False` で明示する — receipt が1件も無い target は `not-started` ではなく
    #: `unresolved` へ倒す（`not-started` は「intent はある」ことが前提のため）。
    has_intent: bool = True


def classify_quarantine(evidence: QuarantineEvidence, *, total_mutating_steps: int) -> str:
    if not evidence.chain_valid or not evidence.has_intent or not evidence.instance_nonce_matches:
        return RELEASE_UNRESOLVED
    if evidence.mutation_receipts == 0:
        return RELEASE_NOT_STARTED
    if evidence.mutation_receipts == total_mutating_steps and evidence.all_postconditions_match:
        return RELEASE_CONFIRMED_DONE
    if evidence.completed_steps and evidence.all_postconditions_match:
        return RELEASE_RESUMABLE
    return RELEASE_UNRESOLVED


#: §7 INDETERMINATE の理由（本モジュールが実際に区別できる部分集合）。receipt store
#: 全体が読めない場合は呼出側（`worktree.audit`）が既に別経路で INDETERMINATE を
#: 返しており（`survey.readable` が False）、ここへは届かない。store が「一度も
#: 存在しない」のか「作られてから消えた」のかは、いまの receipt log が痕跡を残さない
#: ため区別できない（残余限界。検出には `worktree_runtime.py` 側の receipt schema
#: 拡張が要り、本モジュールの boundary 外）。
INDETERMINATE_REASONS = ("receipt-store-unreadable", "self-operation-in-progress")

#: 自 operation の未完了痕跡（receipt log の実際の語彙）。`FLW-DSN-016` §7 が挙げる
#: write_state の `PENDING_INTENT` / `MUTATING` / `RECONCILING` / `PARTIAL` は、
#: `worktree_runtime._ReceiptLog` が使う独自語彙（`PENDING` / `MUTATING` / `DONE` /
#: `QUARANTINED`）と同名ではない（M2 worktree write は `flowlib.intent.IntentStore` を
#: 経由しておらず、この receipt log が実質的な intent 記録である）。`DONE` /
#: `QUARANTINED`（終端）以外はすべて自 operation の途中である。
SELF_OPERATION_IN_PROGRESS_STATES = frozenset({"PENDING", "MUTATING"})

#: worktree が「存在するはず」の action（create / resume の完了後）。finish / discard の
#: 完了後は worktree が存在しないことが正しい postcondition である。
_PRESENCE_EXPECTED_ACTIONS = frozenset({"create", "resume"})


def classify_quarantine_target(
    *,
    chain_valid: bool,
    records: Sequence[Mapping[str, Any]],
    directory_exists: bool,
    registry_exists: bool,
    ref_exists: bool,
    instance_nonce_matches: bool,
) -> tuple[str | None, str | None]:
    """target 単位で §6 の4区分または §7 の INDETERMINATE を実観測から算出する。

    `records` はこの target の path を持つ receipt 記録を sequence 順（古い→新しい）で
    渡す。以前は集合全体の evidence を固定入力で1回だけ計算しており、到達可能な像が
    `worktree-unresolved` の1点へ潰れていた（`FLW-REV-019`）。

    戻り値は ``(release_class, undetermined_reason)``。分類できないときは
    ``release_class`` が ``None`` になり、``undetermined_reason`` に理由を残す
    （`release_class: null` と4区分の混在を区別可能にする）。
    """
    if not chain_valid:
        return None, "receipt-store-unreadable"
    if records and records[-1].get("state") in SELF_OPERATION_IN_PROGRESS_STATES:
        # 自 operation の中断を外部起因の quarantine と誤分類しない（§7）。
        return None, "self-operation-in-progress"

    has_intent = bool(records)
    completed_steps = tuple(records[-1].get("completed_steps") or ()) if records else ()
    mutation_receipts = len(completed_steps)
    action = (records[-1].get("target") or {}).get("action") if records else None
    steps = STEPS_BY_OPERATION.get(f"worktree.{action}") if action else None
    total_mutating_steps = len(steps) if steps else 0

    if action is None:
        all_postconditions_match = False
    else:
        expected_presence = action in _PRESENCE_EXPECTED_ACTIONS
        all_postconditions_match = (
            directory_exists == expected_presence
            and registry_exists == expected_presence
            and ref_exists == expected_presence
            and instance_nonce_matches
        )

    evidence = QuarantineEvidence(
        chain_valid=chain_valid,
        completed_steps=completed_steps,
        instance_nonce_matches=instance_nonce_matches,
        mutation_receipts=mutation_receipts,
        all_postconditions_match=all_postconditions_match,
        has_intent=has_intent,
    )
    return classify_quarantine(evidence, total_mutating_steps=total_mutating_steps), None


#: compact 表示用の重大度順（重い→軽い）。`None`（INDETERMINATE）が最も重い —
#: 事実を確定できないことは、確定した4区分のどれよりも保守的に扱う。
RELEASE_CLASS_SEVERITY: tuple[str | None, ...] = (
    None, RELEASE_UNRESOLVED, RELEASE_RESUMABLE, RELEASE_CONFIRMED_DONE, RELEASE_NOT_STARTED,
)


def most_severe_release_class(classes: Sequence[str | None]) -> str | None:
    """target 群の release_class から compact 表示へ出す代表値を選ぶ。"""
    present = set(classes)
    for candidate in RELEASE_CLASS_SEVERITY:
        if candidate in present:
            return candidate
    raise ValueError("classes が空である")


def may_reissue_guard(*, lease_expired: bool, owner_stopped: bool, children_stopped: bool,
                      os_lock_released: bool, postcondition_reconciled: bool) -> bool:
    return all((lease_expired, owner_stopped, children_stopped, os_lock_released, postcondition_reconciled))


def recovery_for(code: str, cause: str) -> CleanupDecision:
    known = {
        ("PARTIAL", "step-interrupted"): "reconcile-only",
        ("STALE", "snapshot-mismatch"): "replan-human",
        ("BLOCKED", "quarantined"): "human-stop",
    }
    recovery = known.get((code, cause))
    return CleanupDecision(
        code if recovery else "INDETERMINATE", recovery_class=recovery or "human-stop",
        reason="" if recovery else "未登録または矛盾するrecovery tuple",
    )


@dataclasses.dataclass(frozen=True)
class RetentionRef:
    name: str
    tip_oid: str
    created_at: datetime
    expires_at: datetime | None
    quarantine_resolved: bool


def create_retention_ref(work_id: str, timestamp: str, tip_oid: str,
                         existing_oid: str | None) -> CleanupDecision:
    if existing_oid is not None and existing_oid != tip_oid:
        return CleanupDecision("BLOCKED", reason="同名retention refが別OIDを指す")
    return CleanupDecision("DONE")


def may_prune_retention(ref: RetentionRef, *, now: datetime, explicit_approval: bool) -> bool:
    return bool(
        explicit_approval and ref.expires_at is not None and now >= ref.expires_at
        and ref.quarantine_resolved
    )
