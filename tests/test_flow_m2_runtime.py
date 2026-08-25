"""FLW-NFR-014 / FLW-TSK-109 plan-digest runtime integration tests."""

from __future__ import annotations

import base64
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "plugins" / "bitz-flow" / "skills" / "flow-core"
sys.path.insert(0, str(SKILL / "scripts"))

from flowlib import worktree_platform as PF  # noqa: E402
from flowlib import worktree_promotion as P  # noqa: E402
from flowlib import worktree_runtime as W  # noqa: E402
from flowlib import worktree_transaction as T  # noqa: E402
from flowlib.worktree_contract import native_component_from_posix, sha256_digest  # noqa: E402

BUNDLE = "sha256:" + "b" * 64


def git(repo: Path, *args: str, check: bool = True) -> str:
    proc = subprocess.run(["git", *args], cwd=repo, text=True, capture_output=True, check=False)
    if check and proc.returncode != 0:
        raise AssertionError(proc.stderr)
    return proc.stdout.strip()


def supported_evidence(root: Path) -> PF.PlatformEvidence:
    stat = root.stat()
    observation = PF.PlatformObservation(
        platform="linux", filesystem_type="ext4", filesystem_class="local",
        owner_principal="test-owner", owner_matches=True, acl_owner_only=True,
        non_follow_walk=True, resource_kind="directory",
        resource_identity=sha256_digest(f"{stat.st_dev}:{stat.st_ino}".encode()),
        native_component=native_component_from_posix(root.name.encode()).as_mapping(),
        case_semantics="sensitive", os_lock=True, file_durability=True,
        directory_durability=True, child_supervision=True,
    )
    profiles = PF.load_support_profiles(
        SKILL / "references" / "worktree-v2-platform-support.json"
    )
    return PF.evaluate_platform(observation, profiles=profiles)


def install_current_bundle(repo: Path) -> None:
    common = Path(git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir"))
    namespace = common / P.PROMOTION_RELATIVE_PATH
    namespace.mkdir(parents=True, mode=0o700)
    namespace.chmod(0o700)
    current = namespace / "current.json"
    current.write_text(json.dumps({
        "contract_version": 2, "generation": "1", "bundle_digest": BUNDLE,
        "runtime_identity_digest": "sha256:" + "a" * 64, "state": "ACTIVE",
    }), encoding="utf-8")
    current.chmod(0o600)


@pytest.fixture
def repository(tmp_path):
    repo = tmp_path / "repo"
    root = tmp_path / "worktrees"
    repo.mkdir(); root.mkdir()
    git(repo, "init", "-b", "main")
    git(repo, "config", "user.name", "Runtime Test")
    git(repo, "config", "user.email", "runtime@example.invalid")
    (repo / "README.md").write_text("base\n", encoding="utf-8")
    git(repo, "add", "README.md"); git(repo, "commit", "-m", "initial")
    install_current_bundle(repo)
    return repo, root


def runtime_plan(repo: Path, *, action: str, path: Path, branch: str, root: Path,
                 **kwargs) -> W.RuntimePlan:
    return W.plan(
        repo, action=action, path=path, branch=branch, worktree_root=root,
        platform_evidence=supported_evidence(root), **kwargs,
    )


def test_repository_observer_is_closed_machine_readable_and_deterministic(repository):
    repo, _ = repository
    observer = W.RepositoryObserver(repo)
    assert observer.snapshot() == observer.snapshot()
    assert observer.snapshot().digest.startswith("sha256:")
    with pytest.raises(W.WorktreeRuntimeError, match="unknown or write-capable"):
        observer.run("update-ref")


def test_plan_digest_create_and_resume_use_target_transaction(repository):
    repo, root = repository
    target = root / "feature"
    create = runtime_plan(repo, action="create", path=target, branch="feat/runtime", root=root)
    result = W.apply(create, confirm=create.operation_id)
    assert result.code == "DONE", result.summary
    assert target.is_dir() and git(target, "branch", "--show-current") == "feat/runtime"
    tx = T.TargetTransaction(
        W._transaction_root(create), target_collision_key=create.context.target_collision_key,
    )
    assert tx.inspect(create.operation_id).state == "DONE"

    resume = runtime_plan(repo, action="resume", path=target, branch="feat/runtime", root=root)
    assert W.apply(resume, confirm=resume.operation_id).code == "DONE"


def test_finish_and_discard_remain_outside_m2(repository):
    repo, root = repository
    for action in ("finish", "discard"):
        with pytest.raises(W.WorktreeRuntimeError, match="unsupported"):
            runtime_plan(repo, action=action, path=root / action, branch=f"feat/{action}", root=root)


def test_signed_capability_inputs_are_immediately_unsupported(repository):
    repo, root = repository
    target = root / "legacy"
    planned = runtime_plan(repo, action="create", path=target, branch="feat/legacy", root=root)
    result = W.apply(
        planned, confirm=planned.operation_id, capability=object(),
        trusted_keys_for_test={"legacy": "ignored"},
    )
    assert (result.code, result.cause) == ("UNSUPPORTED", "unsupported-approval-mode")
    assert not target.exists()
    assert git(repo, "branch", "--list", "feat/legacy") == ""
    assert not W._transaction_root(planned).exists()


@pytest.mark.parametrize("legacy_signal", ["worktree", "head", "index", "registry"])
def test_legacy_deployment_signals_never_downgrade_to_plan_digest(repository, legacy_signal):
    repo, root = repository
    target = root / legacy_signal
    planned = runtime_plan(repo, action="create", path=target, branch=f"feat/{legacy_signal}", root=root)
    declaration = repo / ".bitz-flow" / "approval-mode.json"
    if legacy_signal in {"worktree", "head", "index"}:
        declaration.parent.mkdir()
        declaration.write_text('{"mode":"signed-capability"}', encoding="utf-8")
        if legacy_signal == "head":
            git(repo, "add", str(declaration.relative_to(repo))); git(repo, "commit", "-m", "legacy")
        elif legacy_signal == "index":
            git(repo, "add", str(declaration.relative_to(repo)))
    else:
        common = Path(planned.common_dir)
        registry = common / "bitz-flow-v2" / "trusted-worktree-keys.json"
        registry.parent.mkdir(parents=True, exist_ok=True)
        registry.write_text("{}", encoding="utf-8")
    result = W.apply(planned, confirm=planned.operation_id)
    assert (result.code, result.cause) == ("UNSUPPORTED", "unsupported-approval-mode")
    assert not target.exists()


def test_confirmation_mismatch_is_stale_without_transaction(repository):
    repo, root = repository
    target = root / "mismatch"
    planned = runtime_plan(repo, action="create", path=target, branch="feat/mismatch", root=root)
    result = W.apply(planned, confirm="sha256:" + "0" * 64)
    assert (result.code, result.cause) == ("STALE", "snapshot-mismatch")
    assert not target.exists() and not W._transaction_root(planned).exists()


def test_expired_plan_is_stale(repository):
    repo, root = repository
    planned = runtime_plan(
        repo, action="create", path=root / "expired", branch="feat/expired", root=root,
        expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
    )
    result = W.apply(planned, confirm=planned.operation_id)
    assert (result.code, result.cause) == ("STALE", "approval-expired")
    assert not (root / "expired").exists()


def test_repository_change_after_plan_is_stale(repository):
    repo, root = repository
    target = root / "changed"
    planned = runtime_plan(repo, action="create", path=target, branch="feat/changed", root=root)
    (repo / "new.txt").write_text("change\n", encoding="utf-8")
    result = W.apply(planned, confirm=planned.operation_id)
    assert (result.code, result.cause) == ("STALE", "snapshot-mismatch")
    assert not target.exists()


def test_bundle_change_after_plan_is_stale(repository):
    repo, root = repository
    target = root / "bundle"
    planned = runtime_plan(repo, action="create", path=target, branch="feat/bundle", root=root)
    current = Path(planned.common_dir) / P.PROMOTION_RELATIVE_PATH / "current.json"
    value = json.loads(current.read_text(encoding="utf-8"))
    value["bundle_digest"] = "sha256:" + "c" * 64
    current.write_text(json.dumps(value), encoding="utf-8")
    result = W.apply(planned, confirm=planned.operation_id)
    assert result.code == "STALE"
    assert not target.exists()


def test_crash_before_git_has_emergency_and_terminal_quarantine_receipts(repository):
    repo, root = repository
    target = root / "crash"
    planned = runtime_plan(repo, action="create", path=target, branch="feat/crash", root=root)

    def crash(_step: str) -> None:
        raise W.WorktreeRuntimeError("injected crash")

    result = W.apply(planned, confirm=planned.operation_id, step_hook=crash)
    assert result.code == "INDETERMINATE"
    assert not target.exists()
    tx = T.TargetTransaction(
        W._transaction_root(planned), target_collision_key=planned.context.target_collision_key,
    )
    report = tx.inspect(planned.operation_id)
    assert report.state == "QUARANTINED"
    by_state = {item["receipt_state"]: item for item in report.receipts}
    assert set(by_state) == {"INDETERMINATE", "TERMINAL"}
    assert by_state["TERMINAL"]["supersedes_receipt_digest"] is not None


def test_target_lock_timeout_cleans_pre_intent_marker_without_git(repository):
    repo, root = repository
    target = root / "busy"
    planned = runtime_plan(repo, action="create", path=target, branch="feat/busy", root=root)
    authority = T.TargetTransaction(
        W._transaction_root(planned), target_collision_key=planned.context.target_collision_key,
    )
    lease = authority.acquire(operation_id="sha256:" + "d" * 64, nonce="competing")
    try:
        result = W.apply(planned, confirm=planned.operation_id)
    finally:
        authority.release(lease)
    assert result.code == "BLOCKED"
    assert not target.exists()
    active = Path(planned.common_dir) / P.PROMOTION_RELATIVE_PATH / "active"
    assert not active.exists() or not list(active.iterdir())


def test_promotion_lock_contention_stops_before_target_authority(repository):
    repo, root = repository
    target = root / "promotion-busy"
    planned = runtime_plan(repo, action="create", path=target, branch="feat/promotion-busy", root=root)
    namespace = Path(planned.common_dir) / P.PROMOTION_RELATIVE_PATH
    lock = P._promotion_lock(namespace)
    try:
        result = W.apply(planned, confirm=planned.operation_id)
    finally:
        P._promotion_unlock(lock)
    assert result.code == "BLOCKED"
    assert not target.exists() and not W._transaction_root(planned).exists()


def test_terminal_promotion_cleanup_never_overlaps_target_lock(repository, monkeypatch):
    repo, root = repository
    target = root / "lock-order"
    planned = runtime_plan(repo, action="create", path=target, branch="feat/lock-order", root=root)
    observed = {"target_released": False}
    original = P.release_active_operation

    def checked_release(*args, **kwargs):
        import fcntl
        lock_path = W._transaction_root(planned) / "target.lock"
        with lock_path.open("r+b") as stream:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            observed["target_released"] = True
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        return original(*args, **kwargs)

    monkeypatch.setattr(P, "release_active_operation", checked_release)
    assert W.apply(planned, confirm=planned.operation_id).code == "DONE"
    assert observed["target_released"]


@pytest.mark.parametrize("action", ["create", "resume", "reconcile", "finish", "discard"])
def test_write_worktree_remains_unreachable_from_public_dispatcher(repository, action):
    """write を伴う worktree operation が公開 dispatcher から到達しないこと。

    read-only 3 件（doctor / audit / verify-receipt）は 2026-08-24 の裁定で限定公開した。
    緩めてはならないのは write 側である。
    """
    repo, _ = repository
    proc = subprocess.run(
        [sys.executable, str(SKILL / "scripts" / "flow.py"), "worktree", action,
         "--repo", str(repo), "--format", "json"],
        text=True, capture_output=True, check=False,
    )
    payload = json.loads(proc.stdout)
    assert payload["code"] == "UNSUPPORTED"
    assert payload["operation"] == f"worktree.{action}"
