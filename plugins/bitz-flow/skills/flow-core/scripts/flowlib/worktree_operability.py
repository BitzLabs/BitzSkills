"""M2 doctor/audit/verify-receipt/reconcile integration surface (FLW-TSK-114)."""

from __future__ import annotations

import hashlib
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from . import worktree_platform as PF
from . import worktree_promotion as P
from . import worktree_recovery as RC
from . import worktree_runtime as WR
from . import worktree_transaction as T
from .worktree_contract import (
    CONTRACT_VERSION, ContractError, canonical_json_bytes, sha256_digest, validate_digest,
)


class OperabilityError(RuntimeError):
    def __init__(self, code: str, cause: str, summary: str):
        super().__init__(summary)
        self.code = code
        self.cause = cause
        self.summary = summary


@dataclass(frozen=True)
class JournalUsage:
    event_count: int
    receipt_count: int
    closure_count: int
    bytes: int

    def as_mapping(self) -> dict[str, int]:
        return {
            "event_count": self.event_count,
            "receipt_count": self.receipt_count,
            "closure_count": self.closure_count,
            "bytes": self.bytes,
        }


@dataclass(frozen=True)
class OperabilityDecision:
    code: str
    cause: str | None
    summary: str
    side_effect_state: str
    operator_action: str
    operation_id: str | None
    receipt_path: str | None
    journal_usage: JournalUsage
    details: dict[str, object]
    plan: RC.ReconcilePlan | None = None


def persistent_state_digest(common_dir: str | Path) -> str:
    """Hash names, modes and bytes below bitz-flow-v2 without changing them."""
    root = Path(common_dir) / "bitz-flow-v2"
    digest = hashlib.sha256()
    if not root.exists():
        digest.update(b"absent")
        return "sha256:" + digest.hexdigest()
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        stat = path.lstat()
        digest.update(relative + b"\0" + oct(stat.st_mode & 0o777).encode() + b"\0")
        if path.is_symlink():
            digest.update(b"symlink\0" + os.readlink(path).encode("utf-8"))
        elif path.is_file():
            digest.update(b"file\0" + path.read_bytes())
        elif path.is_dir():
            digest.update(b"directory\0")
        else:
            digest.update(b"unsupported\0")
    return "sha256:" + digest.hexdigest()


def _common(repo: str | Path) -> Path:
    try:
        return WR._common_dir(Path(repo).resolve(strict=True))
    except (OSError, WR.WorktreeRuntimeError) as exc:
        raise OperabilityError("INVALID_INPUT", "not-repository", "Git repositoryを観測できない") from exc


def _transaction(common: Path, operation_id: str) -> T.TargetTransaction:
    validate_digest(operation_id)
    roots = common / "bitz-flow-v2" / "transactions"
    matches: list[Path] = []
    for candidate in sorted(roots.iterdir()) if roots.is_dir() else ():
        if not candidate.is_dir():
            raise OperabilityError("INDETERMINATE", "result-indeterminate", "transaction rootが不正")
        if (candidate / "events" / operation_id[7:]).is_dir():
            matches.append(candidate)
    if len(matches) != 1:
        raise OperabilityError(
            "INDETERMINATE", "result-indeterminate",
            "operation journalを一意に特定できない",
        )
    try:
        collision_key = validate_digest("sha256:" + matches[0].name)
    except ContractError as exc:
        raise OperabilityError(
            "INDETERMINATE", "result-indeterminate", "target collision keyが不正"
        ) from exc
    return T.TargetTransaction(matches[0], target_collision_key=collision_key)


def _usage(transaction: T.TargetTransaction, operation_id: str) -> JournalUsage:
    paths = (
        tuple(transaction._event_dir(operation_id).glob("*.json"))
        + tuple(transaction._receipt_dir(operation_id).glob("*.json"))
        + tuple(transaction._closure_dir(operation_id).glob("*.json"))
    )
    total = 0
    for path in paths:
        try:
            total += path.stat().st_size
        except OSError as exc:
            raise OperabilityError(
                "INDETERMINATE", "result-indeterminate", "journal使用量を観測できない"
            ) from exc
    report = transaction.inspect(operation_id)
    return JournalUsage(len(report.events), len(report.receipts), len(report.closures), total)


def _receipt_path(common: Path, transaction: T.TargetTransaction,
                  operation_id: str) -> str | None:
    report = transaction.inspect(operation_id)
    terminal = [item for item in report.receipts if item["receipt_state"] == "TERMINAL"]
    if len(terminal) != 1:
        return None
    from .worktree_contract import canonical_json_bytes, sha256_digest
    digest = sha256_digest(canonical_json_bytes(terminal[0]))
    path = transaction._receipt_dir(operation_id) / f"{digest[7:]}.json"
    return path.relative_to(common).as_posix()


def _read_only_guard(common: Path, action):
    before = persistent_state_digest(common)
    try:
        decision = action()
    except Exception:
        if before != persistent_state_digest(common):
            raise OperabilityError(
                "INDETERMINATE", "result-indeterminate",
                "failed read-only operation changed persistent state",
            )
        raise
    after = persistent_state_digest(common)
    if before != after:
        raise OperabilityError(
            "INDETERMINATE", "result-indeterminate",
            "read-only operation中にpersistent stateが変化した",
        )
    decision.details["persistent_state_digest"] = before
    return decision


def has_unsupported_approval_input(repo: str | Path) -> bool:
    """Detect retired approval signals without reading their contents."""
    try:
        root = Path(repo).resolve(strict=True)
        common = _common(root)
        observer = WR.RepositoryObserver(root)
        tracked = observer.run("approval-head").strip() or observer.run("approval-index").strip()
        declaration = os.path.lexists(root / ".bitz-flow" / "approval-mode.json")
        registry = os.path.lexists(common / "bitz-flow-v2" / "trusted-worktree-keys.json")
        return bool(tracked or declaration or registry)
    except (OSError, OperabilityError, WR.WorktreeRuntimeError):
        return True


#: doctor が検出する bundle 側 problem に対応する operator action。
#: platform 側は `worktree_platform.OPERATOR_ACTIONS` を使う。
_BUNDLE_ACTIONS = {
    "current-bundle-missing": "contract bundle を導入する（bitz-flow の初期化を実行する）",
    "minimum-runtime-missing": "minimum runtime sentinel を導入する（bitz-flow の初期化を実行する）",
    "current-bundle-invalid": "contract bundle が壊れている。bitz-flow を再インストールする",
    "current-bundle-not-active": "contract bundle が active でない。promotion を完了させる",
}


def _doctor_operator_action(evidence, problems, common: Path) -> str:
    """診断結果から**行動可能な**是正を組み立てる（`FLW-REV-028:GP-001` の要求を doctor へ）。

    符丁（`fix-platform-or-bundle`）を返しても利用者は何をすればよいか判らない。
    platform 側の理由は `OPERATOR_ACTIONS` から、bundle 側は導入手順から引く。
    """
    actions: list[str] = []
    if not evidence.supported:
        actions.append(PF.operator_action(evidence.reasons, target=common.parent))
    actions.extend(_BUNDLE_ACTIONS[p] for p in problems if p in _BUNDLE_ACTIONS)
    unknown = [p for p in problems if p not in _BUNDLE_ACTIONS]
    if unknown:
        actions.append(f"未分類の問題を報告する: {', '.join(sorted(unknown))}")
    return " / ".join(dict.fromkeys(actions)) or "報告する"


def doctor(repo: str | Path) -> OperabilityDecision:
    common = _common(repo)

    def inspect() -> OperabilityDecision:
        evidence = PF.platform_evidence_for(common)
        namespace = common / "bitz-flow-v2"
        promotion = namespace / "promotion"
        transactions = namespace / "transactions"
        active = tuple((promotion / "active").glob("*.json")) if (promotion / "active").is_dir() else ()
        transaction_roots = tuple(transactions.iterdir()) if transactions.is_dir() else ()
        current = promotion / "current.json"
        problems: list[str] = []
        bundle_digest = None
        if current.is_file():
            try:
                value = json.loads(current.read_text(encoding="utf-8"))
                if set(value) != {
                    "contract_version", "generation", "bundle_digest",
                    "runtime_identity_digest", "state",
                } or value.get("contract_version") != CONTRACT_VERSION:
                    raise ContractError("current pointer fields mismatch")
                bundle_digest = validate_digest(value.get("bundle_digest"))
                validate_digest(value.get("runtime_identity_digest"))
                if value.get("state") != "ACTIVE":
                    problems.append("current-bundle-not-active")
                bundle_path = promotion / "bundles" / bundle_digest[7:] / "bundle.json"
                bundle_value = json.loads(bundle_path.read_text(encoding="utf-8"))
                if sha256_digest(canonical_json_bytes(bundle_value)) != bundle_digest:
                    problems.append("current-bundle-digest-mismatch")
            except (OSError, json.JSONDecodeError, ContractError):
                problems.append("current-bundle-invalid")
        else:
            problems.append("current-bundle-missing")
        try:
            P.read_minimum_runtime_sentinel(common)
        except (OSError, ValueError, json.JSONDecodeError):
            problems.append("minimum-runtime-missing")
        journal_files = tuple(
            path
            for root in transaction_roots if root.is_dir()
            for path in root.rglob("*.json") if path.is_file()
        )
        total_bytes = sum(path.stat().st_size for path in journal_files)
        usage = JournalUsage(
            sum("events" in path.parts for path in journal_files),
            sum("receipts" in path.parts for path in journal_files),
            sum("closures" in path.parts for path in journal_files),
            total_bytes,
        )
        code = "OK" if not problems else "INDETERMINATE"
        return OperabilityDecision(
            code,
            None if code == "OK" else "result-indeterminate",
            "M2 local safety namespaceを診断した",
            "none",
            # doctor は利用者が最初に走らせる診断である。`fix-platform-or-bundle` の
            # ような符丁を返しても何をすればよいか判らない（`FLW-REV-028:GP-001` と
            # 同じ要求を doctor 自身へ適用する）。platform 側の理由は
            # `OPERATOR_ACTIONS` から、bundle 側は導入手順を返す。
            "none" if code == "OK" else _doctor_operator_action(evidence, problems, common),
            None,
            None,
            usage,
            {
                # 以前は OS 名を自己申告し `platform_support` を
                # "requires-runtime-evidence" と書いていた（＝証跡が無いと自ら宣言）。
                # plan と同じ生成器で実測し、doctor が緑でも plan が別判定になる
                # 食い違いを無くす（`SI-FLW-084`）。
                "platform": evidence.observation.platform,
                "platform_support": evidence.support_code,
                "platform_reasons": list(evidence.reasons),
                "filesystem_type": evidence.observation.filesystem_type,
                "filesystem_class": evidence.observation.filesystem_class,
                "bundle_digest": bundle_digest,
                "active_marker_count": len(active),
                "transaction_root_count": len(transaction_roots),
                "problems": problems,
            },
        )

    return _read_only_guard(common, inspect)


def audit_operation(repo: str | Path, *, operation_id: str) -> OperabilityDecision:
    common = _common(repo)

    def inspect() -> OperabilityDecision:
        transaction = _transaction(common, operation_id)
        observed = WR.RepositoryObserver(repo).snapshot()
        report = RC.audit(transaction, operation_id=operation_id, observed_snapshot=observed)
        indeterminate = report.classification == RC.INDETERMINATE
        return OperabilityDecision(
            "INDETERMINATE" if indeterminate else "OK",
            "result-indeterminate" if indeterminate else None,
            f"recovery classification: {report.classification}",
            "indeterminate" if report.transaction_state == "MUTATING" else "none",
            "manual-inspection" if indeterminate else "create-reconcile-plan",
            operation_id,
            _receipt_path(common, transaction, operation_id),
            _usage(transaction, operation_id),
            {
                "classification": report.classification,
                "transaction_state": report.transaction_state,
                "journal_head_digest": report.journal_head_digest,
                "fencing_token": report.fencing_token,
                "problems": list(report.problems),
                "audit_digest": report.digest,
            },
        )

    return _read_only_guard(common, inspect)


def verify_receipt(repo: str | Path, *, operation_id: str) -> OperabilityDecision:
    common = _common(repo)

    def inspect() -> OperabilityDecision:
        transaction = _transaction(common, operation_id)
        report = transaction.inspect(operation_id)
        valid = report.healthy and bool(report.events)
        return OperabilityDecision(
            "OK" if valid else "INDETERMINATE",
            None if valid else "result-indeterminate",
            "journal/receipt chainは有効" if valid else "journal/receipt chainを検証できない",
            "none",
            "audit-operation" if valid else "manual-inspection",
            operation_id,
            _receipt_path(common, transaction, operation_id),
            _usage(transaction, operation_id),
            {
                "chain_valid": valid,
                "transaction_state": report.state,
                "journal_head_digest": report.head_digest,
                "problems": list(report.problems),
            },
        )

    return _read_only_guard(common, inspect)


def reconcile_plan(repo: str | Path, *, operation_id: str, decision: str,
                   expires_at: str, nonce: str,
                   bundle_digest: str | None = None) -> OperabilityDecision:
    common = _common(repo)

    def build() -> OperabilityDecision:
        transaction = _transaction(common, operation_id)
        observed = WR.RepositoryObserver(repo).snapshot()
        report = RC.audit(transaction, operation_id=operation_id, observed_snapshot=observed)
        bundle = bundle_digest or WR._current_bundle_digest(common)
        plan = RC.build_reconcile_plan(
            audit_report=report,
            decision=decision,
            repository_identity=WR._repository_identity(common),
            expires_at=expires_at,
            nonce=nonce,
            bundle_digest=bundle,
        )
        return OperabilityDecision(
            "READY", None, "reconcile plan ready", "none", "confirm-reconcile-plan",
            plan.operation_id, _receipt_path(common, transaction, operation_id),
            _usage(transaction, operation_id),
            {
                "original_operation_id": operation_id,
                "audit_digest": report.digest,
                "decision": decision,
                "bundle_digest": bundle,
                "approval_context": plan.context.as_mapping(),
            },
            plan,
        )

    return _read_only_guard(common, build)


def reconcile_apply(repo: str | Path, *, plan: RC.ReconcilePlan, confirm: str,
                    now: datetime, nonce_unused: bool = True,
                    timeout_seconds: float = 0.0) -> OperabilityDecision:
    common = _common(repo)
    transaction = _transaction(common, plan.original_operation_id)
    result = RC.reconcile(
        transaction=transaction,
        plan=plan,
        confirm=confirm,
        now=now,
        nonce_unused=nonce_unused,
        observe=WR.RepositoryObserver(repo).snapshot,
        common_dir=str(common),
        timeout_seconds=timeout_seconds,
    )
    return OperabilityDecision(
        "DONE", None, "reconcile closureを確定した", "closure-only", "none",
        result.operation_id,
        _receipt_path(common, transaction, plan.original_operation_id),
        _usage(transaction, plan.original_operation_id),
        {
            "original_operation_id": plan.original_operation_id,
            "closure_digest": result.closure_digest,
            "audit_digest": result.audit_digest,
            "marker_released": result.marker_released,
        },
        plan,
    )
