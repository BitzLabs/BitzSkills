"""M2 worktree operationの実動plan/apply adapter。

公開dispatcherからのみ利用し、全mutationを単回Ed25519 capability、永続nonce、
append-only receipt chainの内側で実行する。remote writeは扱わない。
"""

from __future__ import annotations

import base64
import dataclasses
import itertools
import json
import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Mapping

from . import guard, result as R
from . import worktree_capability as C


WRITE_ACTIONS = frozenset({"create", "resume", "finish", "discard"})
MUTATING_STEPS = {
    "create": ("git-worktree-add",),
    "resume": ("publish-resume-receipt",),
    "finish": ("git-worktree-remove", "delete-local-branch"),
    "discard": ("create-retention-ref", "git-worktree-remove", "delete-local-branch"),
}

# `TargetGuardManager` は runtime 内で共有し、同一 process の複数 apply を同じ
# canonical target 集合で直列化する。process 間 coordinator と crash 後の
# quarantine 復旧は別の実装単位で永続化する。
_TARGET_GUARDS = guard.TargetGuardManager()
_FENCING_TOKENS = itertools.count(1)


def _next_fencing_token(_canonical_key: str) -> int:
    return next(_FENCING_TOKENS)


def _targets_for_apply(plan_value: "RuntimePlan") -> tuple[guard.Target, ...]:
    """apply の全 mutation target を canonical 昇順で導出する。

    create の registry/worktree はまだ存在しないため binding の実在照合だけを
    省く。opaque worktree ID は registry entry 名から導出できるため、index を
    含む4 targetの集合自体は plan 時点で固定できる。
    """
    return guard.worktree_guard_targets(
        common_dir=plan_value.common_dir,
        worktree_root=plan_value.worktree_root,
        worktree_path=plan_value.path,
        registry_entry=plan_value.registry_entry,
        local_ref=plan_value.branch,
        case_sensitive=plan_value.context.case_sensitivity,
        require_binding=plan_value.action != "create",
    )


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
    context: C.WorktreeApprovalContext
    snapshot: str
    operation_id: str
    effects: tuple[str, ...]


@dataclasses.dataclass(frozen=True)
class RuntimeDecision:
    code: str
    summary: str
    completed_steps: tuple[str, ...] = ()
    remaining_steps: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()


class WorktreeRuntimeError(ValueError):
    """worktree runtime が意図して投げる失敗。

    以前は `RuntimeError` という名前で組み込み例外を module 内で遮蔽しており、
    mutation 境界の except が素の `ValueError` / `KeyError` を捕捉できなかった
    （`FLW-REV-016:SYN-003`）。固有名にして遮蔽をやめる。
    """


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        ["git", "-c", "color.ui=false", "-c", "core.pager=cat", *args],
        cwd=repo, capture_output=True, text=True, check=False,
    )
    if check and proc.returncode != 0:
        raise WorktreeRuntimeError(f"git {args[0]} failed")
    return proc


def _common_dir(repo: Path) -> Path:
    value = _git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir").stdout.strip()
    return Path(value).resolve()


def _head(repo: Path, ref: str) -> str | None:
    proc = _git(repo, "rev-parse", "--verify", ref, check=False)
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


def plan(
    repo: str | Path, *, action: str, path: str | Path, branch: str,
    worktree_root: str | Path, start_point: str = "HEAD", default_branch: str = "main",
) -> RuntimePlan:
    if action not in WRITE_ACTIONS:
        raise WorktreeRuntimeError(f"unsupported worktree action: {action}")
    root = Path(repo).resolve(strict=True)
    common = _common_dir(root)
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
    head = _head(root, branch) or _head(root, start_point)
    instance = _instance_digest(target, registry, head)
    nonexistent = _nonexistence_digest(target)
    if action == "create":
        if target.exists() or registry.exists() or _head(root, f"refs/heads/{branch}") is not None:
            raise WorktreeRuntimeError("create target, registry, or branch already exists")
        instance = None
        if nonexistent is None:
            raise WorktreeRuntimeError("create target nonexistence cannot be proven")
    else:
        if instance is None:
            raise WorktreeRuntimeError("existing worktree binding cannot be proven")
        nonexistent = None
        guard.verify_worktree_binding(common, registry, target)
    context = C.WorktreeApprovalContext(
        worktree_dir_guard_key=dir_target.canonical_key,
        worktree_registry_guard_key=registry_target.canonical_key,
        parent_dir_identity=_parent_identity(target),
        nonexistence_digest=nonexistent,
        instance_identity_digest=instance,
        worktree_root_canonical=str(approved_root),
        case_sensitivity=True,
        operation_id=f"worktree.{action}",
    )
    facts = {
        "action": action, "repo": str(root), "path": str(target), "branch": branch,
        "start_point": start_point, "default_branch": default_branch,
        "expected_head": head, "context": dataclasses.asdict(context),
    }
    snapshot = R.sha256_of(R.canonical_bytes(facts))
    operation_id = R.sha256_of(R.canonical_bytes(["bitz-flow/worktree-plan/v1", facts]))
    return RuntimePlan(
        action, str(root), str(common), str(approved_root), str(target), branch,
        start_point, default_branch, head, str(registry), context, snapshot,
        operation_id, MUTATING_STEPS[action],
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


def ed25519_verifier(public_keys: Mapping[str, str]) -> C.SignatureVerifier:
    if shutil.which("openssl") is None:
        raise WorktreeRuntimeError("OpenSSL Ed25519 verifier unavailable")
    def verify(payload: dict, signature: str, key_id: str) -> bool:
        encoded = public_keys.get(key_id)
        if encoded is None:
            return False
        try:
            key_der = base64.b64decode(encoded, validate=True)
            signature_bytes = base64.b64decode(signature, validate=True)
            with tempfile.TemporaryDirectory(prefix="bitz-flow-ed25519-") as directory:
                key_path = Path(directory) / "public.der"
                signature_path = Path(directory) / "signature.bin"
                message_path = Path(directory) / "message.bin"
                key_path.write_bytes(key_der)
                signature_path.write_bytes(signature_bytes)
                message_path.write_bytes(R.canonical_bytes(payload))
                proc = subprocess.run(
                    ["openssl", "pkeyutl", "-verify", "-pubin", "-inkey", str(key_path),
                     "-keyform", "DER", "-rawin", "-in", str(message_path),
                     "-sigfile", str(signature_path)], capture_output=True, check=False,
                )
                return proc.returncode == 0
        except (ValueError, TypeError, OSError):
            return False
    return verify


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


def _fsync_dir(path: Path) -> None:
    """directory entry を永続化する。file の fsync だけでは名前が残らない。"""
    dir_fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)


class _NonceLedger:
    def __init__(self, common: Path, nonce: str) -> None:
        digest = R.sha256_of(nonce.encode())[7:]
        self.path = common / "bitz-flow-v2" / "nonces" / f"{digest}.json"

    def state(self) -> str:
        if not self.path.exists():
            return C.NONCE_UNUSED
        try:
            return str(json.loads(self.path.read_text(encoding="utf-8"))["state"])
        except (OSError, ValueError, KeyError):
            return C.NONCE_QUARANTINED

    def begin(self, nonce: str, operation_id: str) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        payload = R.canonical_bytes({"nonce": nonce, "operation_id": operation_id, "state": C.NONCE_USED_PENDING})
        try:
            fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            return False
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload); stream.flush(); os.fsync(stream.fileno())
        # directory entry を fsync しないと、crash 後に nonce file ごと消え得る。
        # 単回性の担保が receipt log と非対称だった（`FLW-REV-018:SYN-007`）。
        _fsync_dir(self.path.parent)
        return True

    def finish(self, nonce: str, operation_id: str, state: str) -> None:
        payload = R.canonical_bytes({"nonce": nonce, "operation_id": operation_id, "state": state})
        # temp 名に pid を使うと、pid 名前空間が別のプロセス間で衝突し得る。
        # 同一 directory 内の一意名を OS に作らせる（`FLW-REV-018:SYN-007`）。
        fd, temp_name = tempfile.mkstemp(dir=self.path.parent, prefix=".nonce.", suffix=".tmp")
        temp = Path(temp_name)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(payload); stream.flush(); os.fsync(stream.fileno())
            os.chmod(temp, 0o600)
            os.replace(temp, self.path)
        except BaseException:
            temp.unlink(missing_ok=True)
            raise
        _fsync_dir(self.path.parent)


def receipt_target(plan_value: "RuntimePlan") -> dict:
    """receipt に載せる「何を変えたか」（`SI-FLW-064`）。

    従来の payload は `operation_id` / `state` / `completed_steps` だけで、
    **変更対象を一切指していなかった**。そのため
    `worktree.audit` が operation 外の worktree を区別できず、M2 出口条件
    「operation 外変更の audit 検出・quarantine 接続」が実装不能だった。
    事後の監査と復旧に要る最小の観測値だけを載せる。
    """
    return {
        "action": plan_value.action,
        "path": plan_value.path,
        "branch": plan_value.branch,
        "worktree_root": plan_value.worktree_root,
        "expected_head": plan_value.expected_head,
    }


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

    書き込み側（`_ReceiptLog._append_locked`）は連番・`record_digest`・
    `previous_record_digest` を正しく作っているのに、読み出し側がそれを一切
    検証していなかった。そのため手書き receipt を1件置くだけで audit の判定を
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


class _ReceiptLog:
    def __init__(self, common: Path) -> None:
        self.root = common / "bitz-flow-v2" / "receipts"

    def append(self, payload: dict) -> str:
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            import fcntl
        except ImportError as exc:
            raise WorktreeRuntimeError("receipt locking unavailable") from exc
        lock_path = self.root / ".append.lock"
        with lock_path.open("a+b") as lock_stream:
            fcntl.flock(lock_stream.fileno(), fcntl.LOCK_EX)
            return self._append_locked(payload)

    def _append_locked(self, payload: dict) -> str:
        entries = sorted(self.root.glob("*.json"))
        previous = None
        sequence = len(entries) + 1
        if entries:
            previous = json.loads(entries[-1].read_text(encoding="utf-8"))["record_digest"]
        record = dict(payload, sequence=sequence, previous_record_digest=previous)
        digest = R.sha256_of(R.canonical_bytes(record))
        body = R.canonical_bytes({"record": record, "record_digest": digest})
        path = self.root / f"{sequence:012d}.json"
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(body); stream.flush(); os.fsync(stream.fileno())
        _fsync_dir(self.root)
        return digest


def apply(
    plan_value: RuntimePlan, *, confirm: str,
    capability: C.WorktreeApprovalCapability | None = None,
    backup_receipt: bool = False,
    step_hook: Callable[[str], None] | None = None,
    trusted_keys_for_test: Mapping[str, str] | None = None,
) -> RuntimeDecision:
    """承認済み plan を適用する。

    承認モードは配備が決める（`SI-FLW-061`）。trusted key registry があれば
    `signed-capability`、無ければ `plan-digest`。registry は**本関数が自ら読む**
    （`FLW-REV-016:RSK-204`。呼び出し側から鍵を受け取らない）。
    `trusted_keys_for_test` は fixture 専用の注入口であり、公開経路では使わない。
    """
    if confirm != plan_value.operation_id:
        return RuntimeDecision("STALE", "operation_id mismatch", remaining_steps=plan_value.effects)
    common = Path(plan_value.common_dir)
    public_keys: Mapping[str, str] = trusted_keys_for_test or {}
    if trusted_keys_for_test is None:
        # 配備意図の宣言（git 追跡下）を鍵の実体（common-dir）から分離した3値判定
        # （`FLW-DSN-016` §4 `SI-FLW-073`）。宣言が signed-capability なのに registry が
        # 使えない場合は降格せず停止する。読めないからといって `plan-digest` へ落とすと、
        # 宣言または common-dir へ書ける主体が承認強度を無言で外せる
        # （`FLW-REV-018:SYN-008` / `FLW-REV-019:OPS-304`）。
        decision = resolve_approval_mode(plan_value.repo, common)
        if decision.mode is None:
            return RuntimeDecision(
                "BLOCKED", decision.blocked_reason, remaining_steps=plan_value.effects,
                evidence=decision.evidence,
            )
        if decision.mode == C.MODE_SIGNED_CAPABILITY:
            public_keys = load_trusted_keys(common)
    mode = C.MODE_SIGNED_CAPABILITY if public_keys else C.MODE_PLAN_DIGEST

    verifier: C.SignatureVerifier = lambda payload, signature, key_id: False
    if mode == C.MODE_SIGNED_CAPABILITY:
        if capability is None:
            return RuntimeDecision(
                "BLOCKED", "署名モードでは単回承認 capability が必要",
                remaining_steps=plan_value.effects,
            )
        try:
            verifier = ed25519_verifier(public_keys)
        except WorktreeRuntimeError as exc:
            return RuntimeDecision("UNSUPPORTED", str(exc), remaining_steps=plan_value.effects)

    # nonce はどちらのモードでも operation_id から導出し、承認へ束縛する。
    nonce = derive_nonce(plan_value.operation_id)
    if mode == C.MODE_SIGNED_CAPABILITY and capability is not None and capability.nonce != nonce:
        return RuntimeDecision(
            "BLOCKED", "capability の nonce が operation_id から導出された値と一致しない",
            remaining_steps=plan_value.effects,
        )
    ledger = _NonceLedger(common, nonce)
    failure = C.authorize_worktree_write(
        capability, context=plan_value.context, now=datetime.now(timezone.utc),
        trusted_key_ids=tuple(public_keys), nonce_state=ledger.state(),
        verify_signature=verifier, mode=mode,
    )
    if failure is not None:
        return RuntimeDecision(failure.code, failure.reason, remaining_steps=plan_value.effects)
    try:
        targets = _targets_for_apply(plan_value)
    except (guard.CanonicalizationError, OSError, ValueError) as exc:
        return RuntimeDecision(
            "BLOCKED", f"target guard を導出できない: {exc}", remaining_steps=plan_value.effects
        )
    guard_set, guard_failure = _TARGET_GUARDS.acquire(
        targets, operation_id=plan_value.operation_id, next_token=_next_fencing_token
    )
    if guard_failure is not None or guard_set is None:
        reason = guard_failure.reason if guard_failure is not None else "target guard を取得できない"
        return RuntimeDecision("BLOCKED", reason, remaining_steps=plan_value.effects)

    def released(decision: RuntimeDecision) -> RuntimeDecision:
        _TARGET_GUARDS.release(guard_set)
        return decision

    if not ledger.begin(nonce, plan_value.operation_id):
        return released(RuntimeDecision(
            "BLOCKED", "承認 nonce は消費済み", remaining_steps=plan_value.effects
        ))
    receipts = _ReceiptLog(common)
    completed: list[str] = []
    try:
        receipts.append({"operation_id": plan_value.operation_id, "state": "PENDING",
                          "completed_steps": [], "target": receipt_target(plan_value)})
    except (WorktreeRuntimeError, OSError, ValueError, KeyError) as exc:
        ledger.finish(nonce, plan_value.operation_id, C.NONCE_QUARANTINED)
        return released(RuntimeDecision("BLOCKED", str(exc), remaining_steps=plan_value.effects))
    repo, path = Path(plan_value.repo), Path(plan_value.path)

    def before(step: str) -> None:
        current_context = plan_value.context
        if not completed or path.exists():
            refreshed = plan(
                repo, action=plan_value.action, path=path, branch=plan_value.branch,
                worktree_root=plan_value.worktree_root, start_point=plan_value.start_point,
                default_branch=plan_value.default_branch,
            )
            if refreshed.operation_id != plan_value.operation_id:
                raise WorktreeRuntimeError("worktree state changed after approval")
            current_context = refreshed.context
        pending_failure = C.reauthorize_pending_worktree_write(
            capability, context=current_context, now=datetime.now(timezone.utc),
            trusted_key_ids=tuple(public_keys), verify_signature=verifier, mode=mode,
        )
        if pending_failure is not None:
            raise WorktreeRuntimeError(pending_failure.reason)
        for target in targets:
            target_failure = _TARGET_GUARDS.verify_before_mutation(guard_set, target)
            if target_failure is not None:
                raise WorktreeRuntimeError(target_failure.reason)
        if step_hook is not None:
            step_hook(step)

    try:
        if plan_value.action == "create":
            before("git-worktree-add")
            _git(repo, "worktree", "add", "-b", plan_value.branch, str(path), plan_value.start_point)
            completed.append("git-worktree-add")
            receipts.append({"operation_id": plan_value.operation_id, "state": "MUTATING",
                          "completed_steps": completed, "target": receipt_target(plan_value)})
        elif plan_value.action == "resume":
            before("publish-resume-receipt")
            guard.verify_worktree_binding(common, Path(plan_value.registry_entry), path)
            completed.append("publish-resume-receipt")
            receipts.append({"operation_id": plan_value.operation_id, "state": "MUTATING",
                          "completed_steps": completed, "target": receipt_target(plan_value)})
        else:
            tip = _head(repo, f"refs/heads/{plan_value.branch}")
            if tip != plan_value.expected_head:
                raise WorktreeRuntimeError("branch tip changed after plan")
            dirty = bool(_git(path, "status", "--porcelain").stdout)
            if dirty and not backup_receipt:
                raise WorktreeRuntimeError("dirty worktree requires backup receipt")
            if plan_value.action == "finish":
                if _git(repo, "merge-base", "--is-ancestor", tip or "", plan_value.default_branch, check=False).returncode != 0:
                    raise WorktreeRuntimeError("finish requires merged/reachable branch tip")
            else:
                before("create-retention-ref")
                retained = f"refs/bitz-flow/retained/{plan_value.branch.replace('/', '-')}-{(tip or '')[:12]}"
                _git(repo, "update-ref", retained, tip or "")
                completed.append("create-retention-ref")
                receipts.append({"operation_id": plan_value.operation_id, "state": "MUTATING",
                          "completed_steps": completed, "target": receipt_target(plan_value)})
            before("git-worktree-remove")
            remove_args = ["worktree", "remove"] + (["--force"] if plan_value.action == "discard" else []) + [str(path)]
            _git(repo, *remove_args)
            completed.append("git-worktree-remove")
            receipts.append({"operation_id": plan_value.operation_id, "state": "MUTATING",
                          "completed_steps": completed, "target": receipt_target(plan_value)})
            before("delete-local-branch")
            _git(repo, "branch", "-D" if plan_value.action == "discard" else "-d", plan_value.branch)
            completed.append("delete-local-branch")
        receipt = receipts.append({"operation_id": plan_value.operation_id, "state": "DONE",
                          "completed_steps": completed, "target": receipt_target(plan_value)})
        ledger.finish(nonce, plan_value.operation_id, C.NONCE_USED_DONE)
        return released(RuntimeDecision(
            "DONE", f"worktree.{plan_value.action} completed", tuple(completed), (), (receipt,)
        ))
    except (WorktreeRuntimeError, OSError, ValueError, KeyError) as exc:
        # 復旧経路自身も失敗しうる。receipt log が読めない状況では QUARANTINED の追記も
        # 同じ例外で落ち、`try/finally` だけでは例外が apply() から脱出していた
        # （`SI-FLW-063`。PR #282 の是正が届いていなかった経路）。
        # 副作用は既に起きているので、記録に失敗しても判定は返しきる。
        quarantine_failure = None
        try:
            receipts.append({"operation_id": plan_value.operation_id, "state": "QUARANTINED",
                          "completed_steps": completed, "target": receipt_target(plan_value)})
        except (WorktreeRuntimeError, OSError, ValueError, KeyError) as receipt_exc:
            quarantine_failure = receipt_exc
        finally:
            try:
                ledger.finish(nonce, plan_value.operation_id, C.NONCE_QUARANTINED)
            except (WorktreeRuntimeError, OSError, ValueError, KeyError):
                pass
        remaining = plan_value.effects[len(completed):]
        code = "PARTIAL" if completed else "BLOCKED"
        summary = str(exc)
        if quarantine_failure is not None:
            summary = f"{summary}（quarantine receipt も記録できない: {quarantine_failure}）"
        return released(RuntimeDecision(code, summary, tuple(completed), tuple(remaining)))
