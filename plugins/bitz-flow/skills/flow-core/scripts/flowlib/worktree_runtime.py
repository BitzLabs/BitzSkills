"""M2 worktree operationの実動plan/apply adapter。

公開dispatcherからのみ利用し、全mutationを単回Ed25519 capability、永続nonce、
append-only receipt chainの内側で実行する。remote writeは扱わない。
"""

from __future__ import annotations

import base64
import dataclasses
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


class RuntimeError(ValueError):
    pass


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        ["git", "-c", "color.ui=false", "-c", "core.pager=cat", *args],
        cwd=repo, capture_output=True, text=True, check=False,
    )
    if check and proc.returncode != 0:
        raise RuntimeError(f"git {args[0]} failed")
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
        raise RuntimeError(f"unsupported worktree action: {action}")
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
        raise RuntimeError("worktree path escapes approved root") from exc
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
            raise RuntimeError("create target, registry, or branch already exists")
        instance = None
        if nonexistent is None:
            raise RuntimeError("create target nonexistence cannot be proven")
    else:
        if instance is None:
            raise RuntimeError("existing worktree binding cannot be proven")
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
        raise RuntimeError("capability envelope is invalid") from exc


def ed25519_verifier(public_keys: Mapping[str, str]) -> C.SignatureVerifier:
    if shutil.which("openssl") is None:
        raise RuntimeError("OpenSSL Ed25519 verifier unavailable")
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


def load_trusted_keys(common_dir: str | Path) -> dict[str, str]:
    """固定owner-only registryからtrusted public keyだけを読む。CLI引数で差し替えない。"""
    path = Path(common_dir) / "bitz-flow-v2" / "trusted-worktree-keys.json"
    try:
        stat = path.lstat()
        if path.is_symlink() or not path.is_file() or stat.st_uid != os.getuid() or stat.st_mode & 0o077:
            raise RuntimeError("trusted key registry must be owner-only regular file")
        value = json.loads(path.read_text(encoding="utf-8"))
    except RuntimeError:
        raise
    except (OSError, ValueError) as exc:
        raise RuntimeError("trusted key registry unavailable") from exc
    if not isinstance(value, dict) or not value:
        raise RuntimeError("trusted key registry is empty or invalid")
    return {str(k): str(v) for k, v in value.items()}


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
        return True

    def finish(self, nonce: str, operation_id: str, state: str) -> None:
        temp = self.path.with_suffix(f".tmp.{os.getpid()}")
        payload = R.canonical_bytes({"nonce": nonce, "operation_id": operation_id, "state": state})
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload); stream.flush(); os.fsync(stream.fileno())
        os.replace(temp, self.path)


class _ReceiptLog:
    def __init__(self, common: Path) -> None:
        self.root = common / "bitz-flow-v2" / "receipts"

    def append(self, payload: dict) -> str:
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            import fcntl
        except ImportError as exc:
            raise RuntimeError("receipt locking unavailable") from exc
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
        dir_fd = os.open(self.root, os.O_RDONLY)
        try: os.fsync(dir_fd)
        finally: os.close(dir_fd)
        return digest


def apply(
    plan_value: RuntimePlan, *, confirm: str, capability: C.WorktreeApprovalCapability,
    public_keys: Mapping[str, str], backup_receipt: bool = False,
    step_hook: Callable[[str], None] | None = None,
) -> RuntimeDecision:
    if confirm != plan_value.operation_id:
        return RuntimeDecision("STALE", "operation_id mismatch", remaining_steps=plan_value.effects)
    try:
        verifier = ed25519_verifier(public_keys)
    except RuntimeError as exc:
        return RuntimeDecision("UNSUPPORTED", str(exc), remaining_steps=plan_value.effects)
    common = Path(plan_value.common_dir)
    ledger = _NonceLedger(common, capability.nonce)
    failure = C.authorize_worktree_write(
        capability, context=plan_value.context, now=datetime.now(timezone.utc),
        trusted_key_ids=tuple(public_keys), nonce_state=ledger.state(), verify_signature=verifier,
    )
    if failure is not None:
        return RuntimeDecision(failure.code, failure.reason, remaining_steps=plan_value.effects)
    if not ledger.begin(capability.nonce, plan_value.operation_id):
        return RuntimeDecision("BLOCKED", "capability nonce already consumed", remaining_steps=plan_value.effects)
    receipts = _ReceiptLog(common)
    completed: list[str] = []
    try:
        receipts.append({"operation_id": plan_value.operation_id, "state": "PENDING", "completed_steps": []})
    except (RuntimeError, OSError, ValueError) as exc:
        ledger.finish(capability.nonce, plan_value.operation_id, C.NONCE_QUARANTINED)
        return RuntimeDecision("BLOCKED", str(exc), remaining_steps=plan_value.effects)
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
                raise RuntimeError("worktree state changed after approval")
            current_context = refreshed.context
        pending_failure = C.reauthorize_pending_worktree_write(
            capability, context=current_context, now=datetime.now(timezone.utc),
            trusted_key_ids=tuple(public_keys), verify_signature=verifier,
        )
        if pending_failure is not None:
            raise RuntimeError(pending_failure.reason)
        if step_hook is not None:
            step_hook(step)

    try:
        if plan_value.action == "create":
            before("git-worktree-add")
            _git(repo, "worktree", "add", "-b", plan_value.branch, str(path), plan_value.start_point)
            completed.append("git-worktree-add")
            receipts.append({"operation_id": plan_value.operation_id, "state": "MUTATING", "completed_steps": completed})
        elif plan_value.action == "resume":
            before("publish-resume-receipt")
            guard.verify_worktree_binding(common, Path(plan_value.registry_entry), path)
            completed.append("publish-resume-receipt")
            receipts.append({"operation_id": plan_value.operation_id, "state": "MUTATING", "completed_steps": completed})
        else:
            tip = _head(repo, f"refs/heads/{plan_value.branch}")
            if tip != plan_value.expected_head:
                raise RuntimeError("branch tip changed after plan")
            dirty = bool(_git(path, "status", "--porcelain").stdout)
            if dirty and not backup_receipt:
                raise RuntimeError("dirty worktree requires backup receipt")
            if plan_value.action == "finish":
                if _git(repo, "merge-base", "--is-ancestor", tip or "", plan_value.default_branch, check=False).returncode != 0:
                    raise RuntimeError("finish requires merged/reachable branch tip")
            else:
                before("create-retention-ref")
                retained = f"refs/bitz-flow/retained/{plan_value.branch.replace('/', '-')}-{(tip or '')[:12]}"
                _git(repo, "update-ref", retained, tip or "")
                completed.append("create-retention-ref")
                receipts.append({"operation_id": plan_value.operation_id, "state": "MUTATING", "completed_steps": completed})
            before("git-worktree-remove")
            remove_args = ["worktree", "remove"] + (["--force"] if plan_value.action == "discard" else []) + [str(path)]
            _git(repo, *remove_args)
            completed.append("git-worktree-remove")
            receipts.append({"operation_id": plan_value.operation_id, "state": "MUTATING", "completed_steps": completed})
            before("delete-local-branch")
            _git(repo, "branch", "-D" if plan_value.action == "discard" else "-d", plan_value.branch)
            completed.append("delete-local-branch")
        receipt = receipts.append({"operation_id": plan_value.operation_id, "state": "DONE", "completed_steps": completed})
        ledger.finish(capability.nonce, plan_value.operation_id, C.NONCE_USED_DONE)
        return RuntimeDecision("DONE", f"worktree.{plan_value.action} completed", tuple(completed), (), (receipt,))
    except (RuntimeError, OSError) as exc:
        try:
            receipts.append({"operation_id": plan_value.operation_id, "state": "QUARANTINED", "completed_steps": completed})
        finally:
            ledger.finish(capability.nonce, plan_value.operation_id, C.NONCE_QUARANTINED)
        remaining = plan_value.effects[len(completed):]
        code = "PARTIAL" if completed else "BLOCKED"
        return RuntimeDecision(code, str(exc), tuple(completed), tuple(remaining))
