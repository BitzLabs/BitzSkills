"""M2 Local Safety Profile の plan/apply integration boundary。

承認は plan-digest のみに限定し、旧 signed-capability 入力は即時拒否する。
write-capable Git child は :class:`MutationCoordinator` だけが起動し、永続状態は
``TargetTransaction`` と promotion barrier の authority 経由で更新する。
"""

from __future__ import annotations

import dataclasses
import json
import os
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Mapping

from . import guard, process as PROC, result as R
from . import worktree_capability as C
from . import worktree_approval as A
from . import worktree_platform as PF
from . import worktree_promotion as P
from . import worktree_transaction as T
from .worktree_contract import (
    CONTRACT_VERSION, ContractError, canonical_json_bytes, native_component_from_posix,
    sha256_digest,
)


@dataclasses.dataclass(frozen=True)
class RepositorySnapshot:
    head_oid: str
    index_digest: str
    worktree_digest: str
    worktree_list_digest: str

    @property
    def digest(self) -> str:
        return sha256_digest(canonical_json_bytes(dataclasses.asdict(self)))


#: worktree 経路の既定 timeout。`process.py` が範囲へ丸める（read 1〜300 / write 10〜300）。
DEFAULT_WORKTREE_TIMEOUT_SECONDS = 30.0

#: **operation 全体**の既定 deadline（`FLW-REV-028:GP-002`）。
#: `FLW-NFR-014` は 30 秒 terminal result を要求するが、1 operation は `snapshot()`
#: （4 child）を plan / apply / post で複数回回すため 15〜20 child を起動する。
#: child 単位の budget だけでは合計が保証を超えるので、operation 単位でも締める。
DEFAULT_OPERATION_DEADLINE_SECONDS = 30.0

#: snapshot 観測の出力上限（`FLW-REV-028:GP-002`）。
#: `git status --porcelain=v2 -z --untracked-files=all` は未追跡ファイルが多い repository で
#: 既定の child 上限（8 MiB）を超えうる。porcelain=v2 の未追跡行は概ね `? <path>\0` なので
#: 8 MiB は約 13 万件に相当する。既定値の流用ではなく**設計値**として分離し、
#: 超過は closed result と operator action で閉じる。
SNAPSHOT_OUTPUT_LIMIT_BYTES = 64 * 1024 * 1024


class OperationDeadline:
    """operation 全体の残り時間を配る（`FLW-REV-028:GP-002`）。

    child ごとに独立した budget を与えると、child 数だけ最大時間を消費できてしまう。
    各 child には **残り時間** を配り、尽きたら child を起動しない。
    """

    def __init__(self, total_seconds: float | None = None) -> None:
        self.total_seconds = float(
            DEFAULT_OPERATION_DEADLINE_SECONDS if total_seconds is None else total_seconds
        )
        self._expires_at = time.monotonic() + self.total_seconds

    def remaining(self) -> float:
        return self._expires_at - time.monotonic()

    def expired(self) -> bool:
        return self.remaining() <= 0.0

    def budget_for_child(self, child_seconds: float | None) -> float:
        """child へ配る budget。残り時間を超えない。"""
        requested = DEFAULT_WORKTREE_TIMEOUT_SECONDS if child_seconds is None else child_seconds
        return max(0.0, min(float(requested), self.remaining()))


def _supervised_git(
    args, *, cwd, timeout_seconds: float | None = None, mutating: bool = False,
    env_overrides=None, deadline: "OperationDeadline | None" = None,
    output_limit_bytes: int | None = None,
) -> PROC.ProcessOutcome:
    """Git child を必ず監督下で起動する（`SI-FLW-086`）。

    以前は素の `subprocess.run` を `timeout=` なしで呼んでおり、hang した child が
    無期限にブロックしていた。`process.py` は TimeoutBudget・SIGTERM→grace→SIGKILL・
    出力上限・Windows job object を実装済みなので、worktree 経路もそれを通す。

    `deadline` を渡すと **operation 全体の残り時間**を超えない budget を配る。
    残りが尽きていれば child を起動せず timeout として返す（`FLW-REV-028:GP-002`）。
    """
    if deadline is not None and deadline.expired():
        return PROC.ProcessOutcome(
            ok=False, command_name="git", exit_status=None, stdout=b"", stderr=b"",
            output_truncated=False, duration_ms=0, cause=PROC.CAUSE_TIMEOUT,
            stage=PROC.STAGE_INSPECT, exit_category="operation-deadline",
        )
    if deadline is not None:
        budget = deadline.budget_for_child(timeout_seconds)
    else:
        budget = DEFAULT_WORKTREE_TIMEOUT_SECONDS if timeout_seconds is None else timeout_seconds
    return PROC.run(
        ["git", "-c", "color.ui=false", "-c", "core.pager=cat", *args],
        cwd=str(cwd), timeout_seconds=budget, mutating=mutating,
        env_overrides=env_overrides,
        output_limit_bytes=(
            PROC.DEFAULT_OUTPUT_LIMIT_BYTES if output_limit_bytes is None else output_limit_bytes
        ),
    )


class RepositoryObserver:
    """Fixed, machine-readable, read-only Git observation boundary."""

    _COMMANDS = {
        "head": ("rev-parse", "--verify", "HEAD"),
        "index": ("diff", "--cached", "--binary", "--no-ext-diff"),
        "worktree": ("status", "--porcelain=v2", "-z", "--untracked-files=all"),
        "worktree-list": ("worktree", "list", "--porcelain", "-z"),
        "approval-head": ("ls-tree", "-r", "--name-only", "HEAD", "--", ".bitz-flow/approval-mode.json"),
        "approval-index": ("diff", "--cached", "--name-only", "--", ".bitz-flow/approval-mode.json"),
    }

    def __init__(self, repo: str | Path, *, timeout_seconds: float | None = None,
                 deadline: OperationDeadline | None = None) -> None:
        self.repo = Path(repo).resolve(strict=True)
        self.timeout_seconds = timeout_seconds
        self.deadline = deadline

    def run(self, observation: str) -> bytes:
        args = self._COMMANDS.get(observation)
        if args is None:
            raise WorktreeRuntimeError("unknown or write-capable repository observation")
        outcome = _supervised_git(
            args, cwd=self.repo, timeout_seconds=self.timeout_seconds,
            env_overrides={"GIT_OPTIONAL_LOCKS": "0"}, deadline=self.deadline,
            # snapshot は operation の必須経路であり、既定の child 上限を流用すると
            # 未追跡ファイルの多い repository で plan 自体が失敗する（`FLW-REV-028:GP-002`）。
            output_limit_bytes=SNAPSHOT_OUTPUT_LIMIT_BYTES,
        )
        if not outcome.ok:
            if outcome.cause == PROC.CAUSE_TIMEOUT:
                raise WorktreeChildTimeoutError(f"git {args[0]}", outcome.cause)
            raise WorktreeRuntimeError(f"repository observation failed: {observation}")
        return outcome.stdout

    def snapshot(self) -> RepositorySnapshot:
        head = self.run("head").decode("ascii").strip()
        return RepositorySnapshot(
            head,
            sha256_digest(self.run("index")),
            sha256_digest(self.run("worktree")),
            sha256_digest(self.run("worktree-list")),
        )


WRITE_ACTIONS = frozenset({"create", "resume"})
MUTATING_STEPS = {
    "create": ("git-worktree-add",),
    "resume": ("publish-resume-receipt",),
}

@dataclasses.dataclass(frozen=True)
class RuntimePlan:
    action: str
    repo: str
    common_dir: str
    worktree_root: str
    path: str
    branch: str
    start_point: str
    default_branch: str
    expected_head: str | None
    registry_entry: str
    context: A.ApprovalContext
    repository_snapshot: RepositorySnapshot
    platform_evidence: PF.PlatformEvidence
    bundle_digest: str
    snapshot: str
    operation_id: str
    effects: tuple[str, ...]
    #: この operation の全 child へ伝播する budget（`SI-FLW-086`）。
    timeout_seconds: float = DEFAULT_WORKTREE_TIMEOUT_SECONDS


@dataclasses.dataclass(frozen=True)
class RuntimeDecision:
    code: str
    summary: str
    completed_steps: tuple[str, ...] = ()
    remaining_steps: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()
    cause: str | None = None


class WorktreeChildTimeoutError(ValueError):
    """Git child の終了を有限時間内に証明できなかったことを表す（`SI-FLW-086`）。

    `QUARANTINED`（再観測が予定 postcondition と不一致）と区別する。timeout は
    「副作用が起きたか自体が不明」であり、`FLW-DSN-017` §13.2 の
    「終了状態を証明できない Git child」に該当して `INDETERMINATE` へ閉じる。
    """

    def __init__(self, command: str, cause: str) -> None:
        super().__init__(f"child did not terminate within budget: {command}")
        self.command = command
        self.cause = cause


class WorktreeUnsupportedPlatformError(ValueError):
    """platform evidence が supported でないことを表す（`SI-FLW-084`）。

    `WorktreeRuntimeError` と分けるのは、呼び出し側が `BLOCKED / conflict` へ
    丸めてしまうと運用者が「環境が対象外」なのか「競合で止まった」のかを
    識別できないためである。理由は closed evidence の `reasons` をそのまま運ぶ。
    """

    def __init__(self, reasons: tuple[str, ...]) -> None:
        super().__init__("platform evidence is not supported")
        self.reasons = tuple(reasons)


class WorktreeRuntimeError(ValueError):
    """worktree runtime が意図して投げる失敗。

    以前は `RuntimeError` という名前で組み込み例外を module 内で遮蔽しており、
    mutation 境界の except が素の `ValueError` / `KeyError` を捕捉できなかった
    （`FLW-REV-016:SYN-003`）。固有名にして遮蔽をやめる。
    """


def _git(repo: Path, *args: str, check: bool = True,
         timeout_seconds: float | None = None,
         deadline: OperationDeadline | None = None) -> subprocess.CompletedProcess[str]:
    read_only = (
        bool(args)
        and (
            args[0] in {"rev-parse", "status", "merge-base"}
            or (args[0] == "worktree" and len(args) > 1 and args[1] == "list")
        )
    )
    if not read_only:
        raise WorktreeRuntimeError("unknown or write-capable Git command")
    outcome = _supervised_git(args, cwd=repo, timeout_seconds=timeout_seconds,
                              deadline=deadline)
    if outcome.cause == PROC.CAUSE_TIMEOUT:
        raise WorktreeChildTimeoutError(f"git {args[0]}", outcome.cause)
    if check and not outcome.ok:
        raise WorktreeRuntimeError(f"git {args[0]} failed")
    return subprocess.CompletedProcess(
        args=list(args), returncode=outcome.exit_status if outcome.exit_status is not None else -1,
        stdout=outcome.stdout.decode("utf-8", "replace"),
        stderr=outcome.stderr.decode("utf-8", "replace"),
    )


def _common_dir(repo: Path, *, deadline: OperationDeadline | None = None) -> Path:
    value = _git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir",
                 deadline=deadline).stdout.strip()
    return Path(value).resolve()


def _head(repo: Path, ref: str, *, deadline: OperationDeadline | None = None) -> str | None:
    proc = _git(repo, "rev-parse", "--verify", ref, check=False, deadline=deadline)
    return proc.stdout.strip() if proc.returncode == 0 else None


def _parent_identity(path: Path) -> str:
    parent = path.parent.resolve(strict=True)
    stat = parent.stat()
    return f"dev:{stat.st_dev}:ino:{stat.st_ino}"


def _instance_digest(path: Path, registry: Path, head: str | None) -> str | None:
    if not path.is_dir() or not registry.is_dir() or head is None:
        return None
    stat = path.stat()
    return R.sha256_of(R.canonical_bytes([str(path.resolve()), stat.st_dev, stat.st_ino, str(registry), head]))


def _nonexistence_digest(path: Path) -> str | None:
    if path.exists():
        return None
    return R.sha256_of(R.canonical_bytes([str(path.resolve(strict=False)), _parent_identity(path), False]))


def _registry_for(common: Path, path: Path) -> Path:
    return common / "worktrees" / path.name


def _repository_identity(common: Path) -> str:
    stat = common.stat()
    return sha256_digest(canonical_json_bytes({
        "common_dir": str(common), "device": stat.st_dev, "inode": stat.st_ino,
    }))


def _current_bundle_digest(common: Path) -> str:
    current = common / P.PROMOTION_RELATIVE_PATH / "current.json"
    try:
        value = json.loads(current.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorktreeRuntimeError("active contract bundle is unavailable") from exc
    if value.get("state") != "ACTIVE":
        raise WorktreeRuntimeError("active contract bundle is unavailable")
    digest = value.get("bundle_digest")
    try:
        from .worktree_contract import validate_digest
        return validate_digest(digest)
    except ContractError as exc:
        raise WorktreeRuntimeError("active contract bundle digest is invalid") from exc


def _approval_expiry(value: datetime | None) -> str:
    expiry = value or (datetime.now(timezone.utc) + timedelta(minutes=10))
    if expiry.tzinfo is None or expiry.utcoffset() is None:
        raise WorktreeRuntimeError("approval expiry must include a timezone")
    return expiry.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def plan(
    repo: str | Path, *, action: str, path: str | Path, branch: str,
    worktree_root: str | Path, start_point: str = "HEAD", default_branch: str = "main",
    platform_evidence: PF.PlatformEvidence | None = None,
    expires_at: datetime | None = None, nonce: str | None = None,
    bundle_digest: str | None = None, timeout_seconds: float | None = None,
    deadline: OperationDeadline | None = None,
) -> RuntimePlan:
    if action not in WRITE_ACTIONS:
        raise WorktreeRuntimeError(f"unsupported worktree action: {action}")
    root = Path(repo).resolve(strict=True)
    budget = PROC.normalize_timeout(timeout_seconds)
    # operation 全体の deadline。child 単位の budget と二重の網にする。
    # 呼び出し側が持っていれば**それを使う**。`_rederive` が新しい deadline を開始すると
    # operation 合計が 30 秒を超えうる（`FLW-REV-029:SYN-002`）。
    if deadline is None:
        deadline = OperationDeadline(timeout_seconds)
    observer = RepositoryObserver(root, timeout_seconds=budget, deadline=deadline)
    observed = observer.snapshot()
    common = _common_dir(root, deadline=deadline)
    approved_root = Path(worktree_root).resolve(strict=True)
    target = Path(path)
    if not target.is_absolute():
        target = approved_root / target
    target = target.resolve(strict=False)
    try:
        target.relative_to(approved_root)
    except ValueError as exc:
        raise WorktreeRuntimeError("worktree path escapes approved root") from exc
    registry = _registry_for(common, target)
    dir_target = guard.canonical_worktree_dir_target(
        target, approved_root=approved_root, case_sensitive=True
    )
    registry_target = guard.canonical_worktree_registry_target(
        common, registry, case_sensitive=True
    )
    head = _head(root, branch, deadline=deadline) or _head(root, start_point, deadline=deadline)
    instance = _instance_digest(target, registry, head)
    nonexistent = _nonexistence_digest(target)
    if action == "create":
        if target.exists() or registry.exists() or _head(
                root, f"refs/heads/{branch}", deadline=deadline) is not None:
            raise WorktreeRuntimeError("create target, registry, or branch already exists")
        instance = None
        if nonexistent is None:
            raise WorktreeRuntimeError("create target nonexistence cannot be proven")
    else:
        if instance is None:
            raise WorktreeRuntimeError("existing worktree binding cannot be proven")
        nonexistent = None
        guard.verify_worktree_binding(common, registry, target)
    if platform_evidence is None:
        # production から evidence を渡す経路が無く、ここが必ず例外で止まっていた
        # （`FLW-REV-027:SYN-001`）。既定を実環境 probe にして production 経路を閉じる。
        # probe は例外を投げず、観測不能を closed evidence の reasons へ載せる。
        platform_evidence = PF.platform_evidence_for(approved_root)
    if not platform_evidence.supported:
        raise WorktreeUnsupportedPlatformError(platform_evidence.reasons)
    collision = PF.collision_key(
        parent_identity=sha256_digest(_parent_identity(target).encode("utf-8")),
        native_component=native_component_from_posix(os.fsencode(target.name)).as_mapping(),
        case_semantics=platform_evidence.observation.case_semantics,
    )
    expiry = _approval_expiry(expires_at)
    facts = {
        "action": action, "repo": str(root), "path": str(target), "branch": branch,
        "start_point": start_point, "default_branch": default_branch,
        "expected_head": head, "repository_snapshot": dataclasses.asdict(observed),
        "target_collision_key": collision, "expires_at": expiry,
    }
    nonce_value = nonce or sha256_digest(canonical_json_bytes(["bitz-flow/worktree-nonce/v2", facts]))
    context = A.ApprovalContext(
        CONTRACT_VERSION, f"worktree.{action}", _repository_identity(common), collision,
        observed.head_oid, observed.index_digest, observed.worktree_digest,
        MUTATING_STEPS[action], expiry, nonce_value,
    )
    snapshot = observed.digest
    operation_id = context.operation_id
    active_bundle = bundle_digest or _current_bundle_digest(common)
    return RuntimePlan(
        action, str(root), str(common), str(approved_root), str(target), branch,
        start_point, default_branch, head, str(registry), context, observed,
        platform_evidence, active_bundle, snapshot,
        operation_id, MUTATING_STEPS[action], budget,
    )


def capability_from_json(value: Mapping[str, object]) -> C.WorktreeApprovalCapability:
    try:
        expires = datetime.fromisoformat(str(value["expires_at"]).replace("Z", "+00:00"))
        return C.WorktreeApprovalCapability(
            worktree_dir_guard_key=str(value["worktree_dir_guard_key"]),
            worktree_registry_guard_key=str(value["worktree_registry_guard_key"]),
            parent_dir_identity=str(value["parent_dir_identity"]),
            nonexistence_digest=value.get("nonexistence_digest"),
            instance_identity_digest=value.get("instance_identity_digest"),
            worktree_root_canonical=str(value["worktree_root_canonical"]),
            case_sensitivity=bool(value["case_sensitivity"]),
            expires_at=expires,
            nonce=str(value["nonce"]), operation_id=str(value["operation_id"]),
            algorithm=str(value.get("algorithm", "Ed25519")), key_id=str(value["key_id"]),
            signature=str(value["signature"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise WorktreeRuntimeError("capability envelope is invalid") from exc


def derive_nonce(operation_id: str) -> str:
    """承認 nonce を `operation_id` から決定的に導出する（`SI-FLW-061`）。

    呼び出し側が nonce を自由に選べると、再試行のたびに新しい値を選ぶだけで
    単回性が承認の束縛にならない（`FLW-REV-011:SYN-011` を閉じられない）。
    `operation_id` は承認 context 全体の digest なので、これに束縛すると

    - 同じ承認の再利用 → 同じ nonce → ledger が `USED` → 拒否
    - 世界が変わった → 新しい `operation_id` → 新しい nonce → 新規承認が必要

    となり、承認と単回性が一致する。
    """
    return R.sha256_of(("bitz-flow/worktree-nonce/v1:" + operation_id).encode())


def trusted_key_registry_path(common_dir: str | Path) -> Path:
    return Path(common_dir) / "bitz-flow-v2" / "trusted-worktree-keys.json"


def signature_mode_status(common_dir: str | Path) -> tuple[bool, str]:
    """承認モードの判定と、**降格した理由**を返す。

    従来は使える／使えないの2値で、`chmod 644`・削除・空化のいずれでも黙って
    `False` を返していた。そのため高保証配備（registry を置いている配備）の承認強度が、
    common-dir へ書ける主体によって**無言で** `plan-digest` へ外せた
    （`FLW-REV-018:SYN-008`）。

    registry が**存在しない**配備は素の `plan-digest` であり降格ではない。
    registry が**存在するのに使えない**場合だけを降格として報告する。
    """
    path = trusted_key_registry_path(common_dir)
    try:
        exists = path.exists() or path.is_symlink()
    except OSError as exc:
        return False, f"trusted key registry を確認できない（{type(exc).__name__}）"
    if not exists:
        return False, ""
    try:
        return bool(load_trusted_keys(common_dir)), ""
    except WorktreeRuntimeError as exc:
        return False, f"trusted key registry が存在するが使えない: {exc}"


def signature_mode_available(common_dir: str | Path) -> bool:
    """trusted key registry が使える配備かを、例外を投げずに判定する（モード判定用）。"""
    return signature_mode_status(common_dir)[0]


def approval_mode_declaration_path(repo: str | Path) -> Path:
    """配備が要求する承認モードの宣言（git 追跡下）。鍵の実体（common-dir、owner-only）
    とは所在を分離する（`FLW-DSN-016` §4 `SI-FLW-073`）。"""
    return Path(repo) / ".bitz-flow" / "approval-mode.json"


def read_approval_mode_declaration(repo: str | Path) -> tuple[str | None, str | None]:
    """宣言ファイルを読む。戻り値は ``(mode, error)``。

    宣言ファイルが無ければ ``(None, None)``（宣言なし＝`plan-digest`）。読めない・
    値が不正な場合は ``(None, エラー文言)`` — 「宣言なし」と区別して呼出側が
    fail-closed に倒せるようにする。
    """
    path = approval_mode_declaration_path(repo)
    if not path.exists():
        return None, None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return None, f"承認モード宣言を読めない（{type(exc).__name__}）"
    mode = value.get("mode") if isinstance(value, dict) else None
    if mode not in C.MODES:
        return None, f"承認モード宣言の値が不正: {mode!r}"
    return mode, None


@dataclasses.dataclass(frozen=True)
class ApprovalModeDecision:
    """承認モードの判定結果。``mode`` が ``None`` なら BLOCKED（降格せず停止）。"""

    mode: str | None
    blocked_reason: str | None = None
    evidence: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


def resolve_approval_mode(repo: str | Path, common_dir: str | Path) -> ApprovalModeDecision:
    """配備が要求する承認モードを宣言から読み、鍵の実体の健全性と突き合わせる。

    従来の `signature_mode_status` は trusted key registry の**存在**からモードを
    推定していた。この推定は registry を削除できる主体に対して承認強度を無言で
    落とす — `chmod 644` は `BLOCKED` になるが、**registry を削除すると `apply` が
    `DONE` を返して実 worktree を作っていた**（`FLW-REV-019:OPS-304` / `RSK-204`）。
    配備意図の宣言（git 追跡下）を鍵の実体（common-dir、owner-only）から分離し、
    判定を2値から3値へ改める（`FLW-DSN-016` §4）。

    | 宣言 | registry | 判定 |
    |---|---|---|
    | `signed-capability` | 健全 | `signed-capability` |
    | `signed-capability` | 不在・破損・権限不正・空 | `None`（BLOCKED、降格しない） |
    | 宣言なし | 任意 | `plan-digest`（降格ではなく素の配備） |

    宣言ファイル自体が読めない・値が不正な場合も、意図を確認できない以上
    黙って `plan-digest` へは倒さず `BLOCKED` にする。
    """
    declared_mode, declaration_error = read_approval_mode_declaration(repo)
    if declaration_error is not None:
        message = f"承認モード宣言が読めない: {declaration_error}"
        return ApprovalModeDecision(None, blocked_reason=message, evidence=(message,), warnings=(message,))
    if declared_mode is None:
        return ApprovalModeDecision(C.MODE_PLAN_DIGEST)
    if declared_mode == C.MODE_PLAN_DIGEST:
        return ApprovalModeDecision(C.MODE_PLAN_DIGEST)

    # declared_mode == C.MODE_SIGNED_CAPABILITY
    registry_available, registry_degraded = signature_mode_status(common_dir)
    if registry_available:
        return ApprovalModeDecision(C.MODE_SIGNED_CAPABILITY)
    reason = registry_degraded or "trusted key registry が存在しない"
    message = (
        "承認モード宣言は signed-capability だが trusted key registry が使えない"
        f"（{reason}）。降格せず停止する"
    )
    return ApprovalModeDecision(None, blocked_reason=message, evidence=(message,), warnings=(message,))


def load_trusted_keys(common_dir: str | Path) -> dict[str, str]:
    """固定owner-only registryからtrusted public keyだけを読む。CLI引数で差し替えない。"""
    path = Path(common_dir) / "bitz-flow-v2" / "trusted-worktree-keys.json"
    try:
        stat = path.lstat()
        if path.is_symlink() or not path.is_file() or stat.st_uid != os.getuid() or stat.st_mode & 0o077:
            raise WorktreeRuntimeError("trusted key registry must be owner-only regular file")
        value = json.loads(path.read_text(encoding="utf-8"))
    except WorktreeRuntimeError:
        raise
    except (OSError, ValueError) as exc:
        raise WorktreeRuntimeError("trusted key registry unavailable") from exc
    if not isinstance(value, dict) or not value:
        raise WorktreeRuntimeError("trusted key registry is empty or invalid")
    return {str(k): str(v) for k, v in value.items()}


RECEIPTS_READABLE = "readable"
RECEIPTS_UNREADABLE = "unreadable"


@dataclasses.dataclass(frozen=True)
class ReceiptSurvey:
    """receipt store を検証しながら読んだ結果。

    `worktree.audit` の判定はこの1つの観測に依存する。
    `status` が `unreadable` のときは**どの分類も主張しない**。
    """

    status: str
    reason: str = ""
    managed: frozenset[str] = dataclasses.field(default_factory=frozenset)
    expected_heads: Mapping[str, str] = dataclasses.field(default_factory=dict)
    mutation_receipts: int = 0
    completed_steps: tuple[str, ...] = ()

    @property
    def readable(self) -> bool:
        return self.status == RECEIPTS_READABLE


def read_receipt_chain(receipts: Path) -> tuple[tuple[dict, ...], str]:
    """receipt chain を**検証しながら**読む。

    旧形式も連番・`record_digest`・`previous_record_digest` を持つため、読み出し時に
    chain 全体を検証する。手書き receipt を1件置くだけで audit の判定を
    偽装でき、逆に1件の欠落が検出されなかった（`FLW-REV-018:SYN-001`）。

    `FLW-DSN-015` は evidence ledger について「未取込 lease、重複 ID、**欠番、
    chain 破損**で Gate を `blocked` にする」と既に定めている。同じ規則を receipt へ
    適用するだけであり、新しい概念は導入しない。
    """
    try:
        entries = sorted(receipts.glob("*.json"))
    except OSError as exc:
        return (), f"receipt store を列挙できない（{type(exc).__name__}）"

    records: list[dict] = []
    previous: str | None = None
    for index, entry in enumerate(entries, start=1):
        if entry.name != f"{index:012d}.json":
            return (), f"receipt の連番が途切れている（{entry.name} は {index} 番目）"
        try:
            body = json.loads(entry.read_text(encoding="utf-8"))
            record, digest = body["record"], body["record_digest"]
        except (OSError, ValueError, KeyError, TypeError) as exc:
            return (), f"receipt を読めない（{entry.name}: {type(exc).__name__}）"
        if R.sha256_of(R.canonical_bytes(record)) != digest:
            return (), f"receipt の digest が本文と一致しない（{entry.name}）"
        if record.get("sequence") != index:
            return (), f"receipt の sequence が位置と一致しない（{entry.name}）"
        if record.get("previous_record_digest") != previous:
            return (), f"receipt chain の連結が切れている（{entry.name}）"
        previous = digest
        records.append(record)
    return tuple(records), ""


def survey_receipts(repo: str | Path) -> ReceiptSurvey:
    """receipt store を検証して読み、audit が要る観測値をまとめて返す。

    「receipt が1件も無い」と「receipt を読めない」を区別する。前者は突合が成立した
    うえでの空集合だが、後者では**すべての worktree が外部起因に見えてしまう**。
    `FLW-DSN-016` §8 は audit の照合不能を `INDETERMINATE` ＋ `human-stop` と定めており、
    分類を推測してはならない。
    """
    root = Path(repo)
    try:
        common = _common_dir(root)
    except (WorktreeRuntimeError, OSError, ValueError) as exc:
        return ReceiptSurvey(RECEIPTS_UNREADABLE,
                             f"common-dir を解決できない（{type(exc).__name__}）")
    receipts = common / "bitz-flow-v2" / "receipts"
    if not receipts.exists():
        # 一度も write operation を通していない repo。突合自体は成立している。
        return ReceiptSurvey(RECEIPTS_READABLE)
    if not receipts.is_dir():
        # 「存在しない」と同一視すると全 worktree が外部起因に見える
        # （`FLW-REV-018:SYN-003`）。store 単位の異常は照合不能である。
        return ReceiptSurvey(RECEIPTS_UNREADABLE, "receipt store がディレクトリではない")

    records, failure = read_receipt_chain(receipts)
    if failure:
        return ReceiptSurvey(RECEIPTS_UNREADABLE, failure)

    managed: set[str] = set()
    heads: dict[str, str] = {}
    mutations = 0
    steps: tuple[str, ...] = ()
    for record in records:
        if record.get("state") in ("MUTATING", "DONE"):
            mutations += 1
        steps = tuple(record.get("completed_steps") or steps)
        target = record.get("target") or {}
        path, action = target.get("path"), target.get("action")
        if not path or record.get("state") != "DONE":
            continue
        if action in ("create", "resume"):
            managed.add(str(path))
            if target.get("expected_head"):
                heads[str(path)] = str(target["expected_head"])
        elif action in ("finish", "discard"):
            managed.discard(str(path))
            heads.pop(str(path), None)
    return ReceiptSurvey(RECEIPTS_READABLE, "", frozenset(managed), heads, mutations, steps)


def managed_worktrees(repo: str | Path) -> frozenset[str]:
    """receipt が「この operation 群で作った」と記録している worktree path。

    `worktree.audit` はこれと `git worktree list` を突き合わせて、
    operation 外で作られた worktree を検出する。
    `create` が DONE のものを加え、`finish` / `discard` が DONE のものを除く。
    """
    return survey_receipts(repo).managed


def parse_worktree_registry(porcelain: str) -> dict[str, str | None]:
    """`git worktree list --porcelain` を path → HEAD の対応へ読む。

    HEAD も同じ出力に含まれるため、追加の git 呼び出しをせずに読める。
    """
    registry: dict[str, str | None] = {}
    current: str | None = None
    for line in porcelain.splitlines():
        if line.startswith("worktree "):
            current = line.split(" ", 1)[1]
            registry[current] = None
        elif line.startswith("HEAD ") and current is not None:
            registry[current] = line.split(" ", 1)[1]
    return registry


def reconcile_registry(
    registry: Mapping[str, str | None], survey: ReceiptSurvey, main_worktree: str,
) -> tuple[dict, ...]:
    """registry と receipt を**双方向に**突き合わせる。

    外部起因は2形ある（`FLW-DSN-016` §7）。片方向の照合では、
    「registry にいるが receipt に無い」しか拾えず、
    「receipt が managed と記録しているのに registry から消えた」「実体が消えた」を
    見落としていた（`FLW-REV-018:SYN-002`）。

    HEAD の変化は managed worktree での通常の作業でも起きるため
    `head_changed` として**事実を報告するだけ**とし、`divergence` には数えない。
    """
    rows: list[dict] = []
    for path in sorted(set(registry) | set(survey.managed)):
        if path == main_worktree:
            continue
        registered = path in registry
        managed = path in survey.managed
        present = Path(path).is_dir()
        expected = survey.expected_heads.get(path)
        observed = registry.get(path)
        head_changed = bool(managed and expected and observed and expected != observed)
        if not managed:
            divergence = "unmanaged"          # bitz-flow が作っていない worktree
        elif not registered:
            divergence = "registry-missing"   # receipt はあるが registry から消えた
        elif not present:
            divergence = "directory-missing"  # registry にはあるが実体が無い
        else:
            divergence = ""
        rows.append({"path": path, "registered": registered, "managed": managed,
                     "present": present, "head_changed": head_changed,
                     "divergence": divergence})
    return tuple(rows)


def _legacy_approval_input_present(
    plan_value: RuntimePlan, *, capability: object | None,
    trusted_keys_for_test: Mapping[str, str] | None,
) -> bool:
    """Observe every retired signed-capability signal without consuming its content."""
    if capability is not None or trusted_keys_for_test is not None:
        return True
    repo = Path(plan_value.repo)
    common = Path(plan_value.common_dir)
    observer = RepositoryObserver(repo)
    try:
        head = observer.run("approval-head")
        index = observer.run("approval-index")
        worktree_path = repo / ".bitz-flow" / "approval-mode.json"
        declaration_present = bool(head.strip() or index.strip() or os.path.lexists(worktree_path))
        registry_present = os.path.lexists(common / "bitz-flow-v2" / "trusted-worktree-keys.json")
    except (OSError, WorktreeRuntimeError):
        return True
    return A.has_unsupported_approval_input(
        declaration_present=declaration_present,
        capability_file_present=capability is not None,
        trusted_registry_configured=registry_present,
    )


def _rederive(plan_value: RuntimePlan, *, deadline: OperationDeadline | None = None) -> RuntimePlan:
    expires = datetime.fromisoformat(plan_value.context.expires_at.replace("Z", "+00:00"))
    return plan(
        plan_value.repo, action=plan_value.action, path=plan_value.path,
        branch=plan_value.branch, worktree_root=plan_value.worktree_root,
        start_point=plan_value.start_point, default_branch=plan_value.default_branch,
        platform_evidence=plan_value.platform_evidence, expires_at=expires,
        nonce=plan_value.context.nonce, deadline=deadline,
    )


def _transaction_root(plan_value: RuntimePlan) -> Path:
    return (
        Path(plan_value.common_dir) / "bitz-flow-v2" / "transactions"
        / plan_value.context.target_collision_key[7:]
    )


def _closed_failure(code: str, summary: str, plan_value: RuntimePlan, *,
                    cause: str | None = None, completed: tuple[str, ...] = (),
                    evidence: tuple[str, ...] = ()) -> RuntimeDecision:
    remaining = plan_value.effects[len(completed):]
    return RuntimeDecision(code, summary, completed, remaining, evidence, cause)


class MutationCoordinator:
    """The only runtime component allowed to launch write-capable Git children."""

    def __init__(self, plan_value: RuntimePlan, transaction: T.TargetTransaction,
                 lease: T.LeaseContext, *, step_hook: Callable[[str], None] | None = None,
                 deadline: OperationDeadline | None = None) -> None:
        self.plan = plan_value
        self.transaction = transaction
        self.lease = lease
        self.step_hook = step_hook
        self._mutating = False
        self.deadline = deadline

    def _recheck(self) -> None:
        current = _rederive(self.plan, deadline=self.deadline)
        if (
            current.operation_id != self.plan.operation_id
            or current.repository_snapshot != self.plan.repository_snapshot
            or current.bundle_digest != self.plan.bundle_digest
            or current.context.target_collision_key != self.plan.context.target_collision_key
        ):
            raise WorktreeRuntimeError("repository, target, or contract bundle changed after plan")

    def _begin_mutation(self, step: str) -> None:
        self._recheck()
        if self.step_hook is not None:
            self.step_hook(step)
        self._recheck()
        if not self._mutating:
            self.transaction.mark_mutating(self.lease)
            self._mutating = True

    def run_git(self, step: str, *args: str, cwd: str | Path | None = None) -> None:
        self._begin_mutation(step)
        outcome = _supervised_git(
            args, cwd=Path(cwd or self.plan.repo),
            timeout_seconds=self.plan.timeout_seconds, mutating=True,
            deadline=self.deadline,
        )
        if outcome.cause == PROC.CAUSE_TIMEOUT:
            # write child の終了を証明できない。副作用の有無が不明なので
            # 失敗（QUARANTINED）へ畳まず INDETERMINATE へ閉じる。
            raise WorktreeChildTimeoutError(f"git {args[0]}", outcome.cause)
        if not outcome.ok:
            raise WorktreeRuntimeError(f"git {args[0]} failed")

    def record_only(self, step: str) -> None:
        self._begin_mutation(step)


def _map_transaction_error(exc: T.TransactionError, plan_value: RuntimePlan) -> RuntimeDecision:
    if exc.code == "STALE":
        return _closed_failure("STALE", exc.cause, plan_value, cause="snapshot-mismatch")
    if exc.code == "UNSUPPORTED_FILESYSTEM":
        return _closed_failure("UNSUPPORTED", exc.cause, plan_value, cause="unsupported-filesystem")
    if exc.code == "INDETERMINATE":
        return _closed_failure("INDETERMINATE", exc.cause, plan_value, cause="result-indeterminate")
    return _closed_failure("BLOCKED", exc.cause, plan_value, cause="timeout")


def apply(
    plan_value: RuntimePlan, *, confirm: str,
    capability: C.WorktreeApprovalCapability | None = None,
    backup_receipt: bool = False,
    step_hook: Callable[[str], None] | None = None,
    trusted_keys_for_test: Mapping[str, str] | None = None,
) -> RuntimeDecision:
    """Apply one plan-digest operation through promotion and target authorities.

    ``capability`` and ``trusted_keys_for_test`` remain signature-compatible only so
    older callers receive a closed rejection instead of a Python argument error.
    Their values are never parsed, verified, or downgraded to plan-digest.
    """
    del backup_receipt  # M2 create/resume has no backup-receipt mode.
    # apply は plan とは別の起動なので deadline もここで新たに開始する
    # （plan の残り時間を持ち越さない。`FLW-REV-028:GP-002`）。
    deadline = OperationDeadline(plan_value.timeout_seconds)
    unsupported = _legacy_approval_input_present(
        plan_value, capability=capability, trusted_keys_for_test=trusted_keys_for_test,
    )
    try:
        rederived = _rederive(plan_value, deadline=deadline)
    except (WorktreeRuntimeError, ContractError, OSError, ValueError):
        rederived = plan_value
    transaction = T.TargetTransaction(
        _transaction_root(plan_value),
        target_collision_key=plan_value.context.target_collision_key,
    )
    existing = transaction.inspect(plan_value.operation_id)
    nonce_unused = not existing.events and not existing.problems
    authorization = A.authorize_plan_digest(
        plan_value.context, confirm=confirm, now=datetime.now(timezone.utc),
        nonce_unused=nonce_unused, rederived_context=rederived.context,
        unsupported_approval_input=unsupported,
    )
    if authorization.reason_code == A.UNSUPPORTED_APPROVAL_MODE:
        return _closed_failure(
            "UNSUPPORTED", "signed-capability approval inputs are not supported in M2",
            plan_value, cause="unsupported-approval-mode",
        )
    if not authorization.allowed:
        cause = "snapshot-mismatch" if authorization.reason_code in {
            "CONFIRMATION_MISMATCH", "CONTEXT_STALE", "NONCE_REUSED",
        } else "approval-expired"
        return _closed_failure("STALE", authorization.reason_code or "approval rejected",
                               plan_value, cause=cause)
    if existing.problems:
        return _closed_failure(
            "INDETERMINATE", "; ".join(existing.problems), plan_value,
            cause="result-indeterminate",
        )
    if not plan_value.platform_evidence.supported:
        return _closed_failure(
            "UNSUPPORTED", "platform evidence is not supported", plan_value,
            cause="unsupported-filesystem", evidence=plan_value.platform_evidence.reasons,
        )
    if rederived.operation_id != plan_value.operation_id or rederived.bundle_digest != plan_value.bundle_digest:
        return _closed_failure("STALE", "context changed after plan", plan_value,
                               cause="snapshot-mismatch")

    common = Path(plan_value.common_dir)
    marker_registered = False
    lease: T.LeaseContext | None = None
    intent_durable = False
    completed: list[str] = []
    terminal_receipt: str | None = None

    def quarantined_failure(exc: BaseException) -> RuntimeDecision:
        nonlocal lease, marker_registered, terminal_receipt
        if not intent_durable:
            return _closed_failure("BLOCKED", str(exc), plan_value, cause="snapshot-mismatch")
        try:
            if terminal_receipt is None:
                if lease is None:
                    raise WorktreeRuntimeError("target lease ended without a terminal receipt")
                report = transaction.inspect(plan_value.operation_id)
                if report.state == "INTENT_DURABLE":
                    transaction.mark_mutating(lease)
                elif report.state != "MUTATING":
                    raise WorktreeRuntimeError(f"cannot quarantine transaction state {report.state}")
                terminal_receipt = transaction.publish_result(
                    lease, terminal_state="QUARANTINED",
                    postcondition_digest=RepositoryObserver(
                        plan_value.repo, deadline=deadline).snapshot().digest,
                )
            if lease is not None:
                transaction.release(lease)
                lease = None
            P.release_active_operation(
                common, operation_id=plan_value.operation_id,
                terminal_receipt_digest=terminal_receipt,
            )
            marker_registered = False
        except (T.TransactionError, P.PromotionError, WorktreeRuntimeError, OSError, ValueError):
            return _closed_failure(
                "INDETERMINATE", str(exc), plan_value, cause="result-indeterminate",
                completed=tuple(completed),
            )
        return _closed_failure(
            "INDETERMINATE", str(exc), plan_value, cause="result-indeterminate",
            completed=tuple(completed), evidence=(terminal_receipt,),
        )

    try:
        P.register_active_operation(
            common, operation_id=plan_value.operation_id,
            bundle_digest=plan_value.bundle_digest, verify_current=True,
        )
        marker_registered = True
        lease = transaction.acquire(
            operation_id=plan_value.operation_id, nonce=plan_value.context.nonce,
            timeout_seconds=0.0,
        )
        after_lease = _rederive(plan_value, deadline=deadline)
        if (
            after_lease.operation_id != plan_value.operation_id
            or after_lease.repository_snapshot != plan_value.repository_snapshot
            or after_lease.bundle_digest != plan_value.bundle_digest
        ):
            raise WorktreeRuntimeError("context changed after target lease")
        transaction.prepare_intent(
            lease,
            planned_effects_digest=sha256_digest(canonical_json_bytes(list(plan_value.effects))),
            precondition_digest=plan_value.repository_snapshot.digest,
        )
        intent_durable = True
        coordinator = MutationCoordinator(plan_value, transaction, lease,
                                          step_hook=step_hook, deadline=deadline)
        if plan_value.action == "create":
            coordinator.run_git(
                "git-worktree-add", "worktree", "add", "-b", plan_value.branch,
                plan_value.path, plan_value.start_point,
            )
            completed.append("git-worktree-add")
        elif plan_value.action == "resume":
            coordinator.record_only("publish-resume-receipt")
            guard.verify_worktree_binding(common, Path(plan_value.registry_entry), Path(plan_value.path))
            completed.append("publish-resume-receipt")
        else:  # defensive: plan() already rejects this closed set violation.
            raise WorktreeRuntimeError("unsupported M2 mutation action")
        post = RepositoryObserver(plan_value.repo, deadline=deadline).snapshot().digest
        terminal_receipt = transaction.publish_result(
            lease, terminal_state="DONE", postcondition_digest=post,
        )
        transaction.release(lease)
        lease = None
        P.release_active_operation(
            common, operation_id=plan_value.operation_id,
            terminal_receipt_digest=terminal_receipt,
        )
        marker_registered = False
        return RuntimeDecision(
            "DONE", f"worktree.{plan_value.action} completed", tuple(completed), (),
            (terminal_receipt,), None,
        )
    except P.PromotionError as exc:
        if intent_durable:
            return quarantined_failure(exc)
        code = "STALE" if exc.code == "STALE" else (
            "INDETERMINATE" if exc.code == "INDETERMINATE" else "BLOCKED"
        )
        return _closed_failure(code, exc.cause, plan_value,
                               cause="result-indeterminate" if code == "INDETERMINATE" else "snapshot-mismatch")
    except T.TransactionError as exc:
        if intent_durable:
            return quarantined_failure(exc)
        return _map_transaction_error(exc, plan_value)
    except WorktreeChildTimeoutError as exc:
        # child の終了を証明できない。`QUARANTINED`（再観測が予定 postcondition と
        # 不一致）へ畳むと「観測できた」ことになってしまうため、緊急 receipt を
        # 保持したまま `INDETERMINATE` へ閉じる（`FLW-DSN-017` §13.2 / `SI-FLW-086`）。
        return _closed_failure(
            "INDETERMINATE", str(exc), plan_value, cause="result-indeterminate",
            completed=tuple(completed), evidence=(exc.command, exc.cause),
        )
    except (WorktreeRuntimeError, ContractError, OSError, ValueError, KeyError) as exc:
        return quarantined_failure(exc)
    finally:
        if lease is not None:
            try:
                transaction.release(lease)
            except (T.TransactionError, OSError):
                pass
        if marker_registered and not intent_durable:
            try:
                P.abort_active_operation(
                    common, operation_id=plan_value.operation_id,
                    bundle_digest=plan_value.bundle_digest,
                )
            except (P.PromotionError, OSError):
                pass
