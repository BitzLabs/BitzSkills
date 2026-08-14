"""FLW-FR-006 / FLW-CON-005 / FLW-CON-006 worktree実動E2E。"""

from __future__ import annotations

import base64
import dataclasses
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "plugins" / "bitz-flow" / "skills" / "flow-core"
sys.path.insert(0, str(SKILL / "scripts"))

from flowlib import result as R  # noqa: E402
from flowlib import worktree_capability as C  # noqa: E402
from flowlib import worktree_runtime as W  # noqa: E402


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, text=True, capture_output=True, check=True).stdout.strip()


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
    return repo, root


def signed(plan, nonce):
    values = {
        **dataclasses.asdict(plan.context),
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=10),
        "nonce": nonce,
        "algorithm": "Ed25519",
        "key_id": "owner-key",
        "signature": "",
    }
    cap = C.WorktreeApprovalCapability(**values)
    with tempfile.TemporaryDirectory(prefix="bitz-flow-sign-") as directory:
        private_path = Path(directory) / "private.pem"
        public_path = Path(directory) / "public.der"
        signature_path = Path(directory) / "signature.bin"
        message_path = Path(directory) / "message.bin"
        subprocess.run(
            ["openssl", "genpkey", "-algorithm", "ED25519", "-out", str(private_path)],
            capture_output=True, check=True,
        )
        subprocess.run(
            ["openssl", "pkey", "-in", str(private_path), "-pubout", "-outform", "DER",
             "-out", str(public_path)], capture_output=True, check=True,
        )
        message_path.write_bytes(R.canonical_bytes(cap.signed_payload()))
        subprocess.run(
            ["openssl", "pkeyutl", "-sign", "-inkey", str(private_path), "-rawin",
             "-in", str(message_path), "-out", str(signature_path)], capture_output=True, check=True,
        )
        public = public_path.read_bytes()
        signature = signature_path.read_bytes()
    cap = dataclasses.replace(cap, signature=base64.b64encode(signature).decode())
    keys = {"owner-key": base64.b64encode(public).decode()}
    return cap, keys


def test_FLW_FR_006_create_resume_finish_actual_git_worktree(repository):
    repo, root = repository
    path = root / "feature"
    create = W.plan(repo, action="create", path=path, branch="feat/runtime", worktree_root=root)
    cap, keys = signed(create, "nonce-create")
    result = W.apply(create, confirm=create.operation_id, capability=cap, public_keys=keys)
    assert result.code == "DONE"
    assert path.is_dir() and git(path, "branch", "--show-current") == "feat/runtime"

    resume = W.plan(repo, action="resume", path=path, branch="feat/runtime", worktree_root=root)
    cap, keys = signed(resume, "nonce-resume")
    assert W.apply(resume, confirm=resume.operation_id, capability=cap, public_keys=keys).code == "DONE"

    git(repo, "merge", "--ff-only", "feat/runtime")
    finish = W.plan(repo, action="finish", path=path, branch="feat/runtime", worktree_root=root)
    cap, keys = signed(finish, "nonce-finish")
    result = W.apply(finish, confirm=finish.operation_id, capability=cap, public_keys=keys)
    assert result.code == "DONE"
    assert not path.exists()
    assert subprocess.run(["git", "show-ref", "--verify", "refs/heads/feat/runtime"], cwd=repo).returncode != 0


def test_FLW_CON_006_discard_retains_tip_and_removes_actual_worktree(repository):
    repo, root = repository
    path = root / "discard"
    create = W.plan(repo, action="create", path=path, branch="feat/discard", worktree_root=root)
    cap, keys = signed(create, "nonce-create-discard")
    assert W.apply(create, confirm=create.operation_id, capability=cap, public_keys=keys).code == "DONE"
    (path / "change.txt").write_text("committed\n", encoding="utf-8")
    git(path, "add", "change.txt"); git(path, "commit", "-m", "discard me")
    tip = git(path, "rev-parse", "HEAD")

    discard = W.plan(repo, action="discard", path=path, branch="feat/discard", worktree_root=root)
    cap, keys = signed(discard, "nonce-discard")
    result = W.apply(discard, confirm=discard.operation_id, capability=cap, public_keys=keys)
    assert result.code == "DONE" and not path.exists()
    retained = git(repo, "for-each-ref", "--format=%(objectname)", "refs/bitz-flow/retained/")
    assert tip in retained


def test_FLW_CON_005_missing_bad_or_reused_capability_has_no_git_side_effect(repository):
    repo, root = repository
    path = root / "blocked"
    plan = W.plan(repo, action="create", path=path, branch="feat/blocked", worktree_root=root)
    cap, keys = signed(plan, "nonce-blocked")
    wrong = dataclasses.replace(cap, signature=base64.b64encode(b"x" * 64).decode())
    result = W.apply(plan, confirm=plan.operation_id, capability=wrong, public_keys=keys)
    assert result.code == "BLOCKED" and not path.exists()
    result = W.apply(plan, confirm="sha256:wrong", capability=cap, public_keys=keys)
    assert result.code == "STALE" and not path.exists()
    assert W.apply(plan, confirm=plan.operation_id, capability=cap, public_keys=keys).code == "DONE"
    second = W.apply(plan, confirm=plan.operation_id, capability=cap, public_keys=keys)
    assert second.code == "BLOCKED"


def test_FLW_CON_006_crash_before_first_mutation_quarantines_nonce_without_side_effect(repository):
    repo, root = repository
    path = root / "crash"
    plan = W.plan(repo, action="create", path=path, branch="feat/crash", worktree_root=root)
    cap, keys = signed(plan, "nonce-crash")
    result = W.apply(
        plan, confirm=plan.operation_id, capability=cap, public_keys=keys,
        step_hook=lambda step: (_ for _ in ()).throw(W.RuntimeError(f"crash:{step}")),
    )
    assert result.code == "BLOCKED" and not path.exists()
    assert W.apply(plan, confirm=plan.operation_id, capability=cap, public_keys=keys).code == "BLOCKED"


def test_FLW_CON_005_state_change_after_plan_is_stale_and_has_no_git_side_effect(repository):
    repo, root = repository
    path = root / "occupied"
    plan = W.plan(repo, action="create", path=path, branch="feat/occupied", worktree_root=root)
    cap, keys = signed(plan, "nonce-occupied")
    path.mkdir()

    result = W.apply(plan, confirm=plan.operation_id, capability=cap, public_keys=keys)

    assert result.code == "BLOCKED"
    assert git(repo, "branch", "--list", "feat/occupied") == ""
    assert list(path.iterdir()) == []


def test_FLW_CON_005_trusted_registry_rejects_group_readable_file(repository):
    repo, _ = repository
    common = Path(git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir"))
    registry = common / "bitz-flow-v2" / "trusted-worktree-keys.json"
    registry.parent.mkdir(parents=True, exist_ok=True)
    registry.write_text('{"owner-key":"unused"}', encoding="utf-8")
    registry.chmod(0o640)

    with pytest.raises(W.RuntimeError, match="owner-only"):
        W.load_trusted_keys(common)


def test_FLW_CON_006_partial_discard_retains_tip_and_quarantines_receipt(repository):
    repo, root = repository
    path = root / "partial"
    create = W.plan(repo, action="create", path=path, branch="feat/partial", worktree_root=root)
    cap, keys = signed(create, "nonce-create-partial")
    assert W.apply(create, confirm=create.operation_id, capability=cap, public_keys=keys).code == "DONE"
    discard = W.plan(repo, action="discard", path=path, branch="feat/partial", worktree_root=root)
    cap, keys = signed(discard, "nonce-discard-partial")

    def fail_after_retention(step):
        if step == "git-worktree-remove":
            raise W.RuntimeError("injected after retention")

    result = W.apply(
        discard, confirm=discard.operation_id, capability=cap, public_keys=keys,
        step_hook=fail_after_retention,
    )

    assert result.code == "PARTIAL"
    assert result.completed_steps == ("create-retention-ref",)
    assert path.is_dir()
    retained = git(repo, "for-each-ref", "--format=%(refname)", "refs/bitz-flow/retained/")
    assert "refs/bitz-flow/retained/feat-partial-" in retained
    common = Path(discard.common_dir)
    records = [json.loads(p.read_text(encoding="utf-8"))["record"]
               for p in sorted((common / "bitz-flow-v2" / "receipts").glob("*.json"))]
    matching = [record for record in records if record["operation_id"] == discard.operation_id]
    assert [record["state"] for record in matching] == ["PENDING", "MUTATING", "QUARANTINED"]


def test_FLW_FR_006_dispatcher_create_plan_exposes_signed_capability_context(repository):
    repo, root = repository
    command = [
        sys.executable, str(SKILL / "scripts" / "flow.py"), "worktree", "create",
        "--repo", str(repo), "--path", str(root / "cli"), "--branch", "feat/cli",
        "--worktree-root", str(root), "--format", "json",
    ]
    proc = subprocess.run(command, text=True, capture_output=True, check=False)
    payload = json.loads(proc.stdout)
    assert proc.returncode == 0
    assert payload["code"] == "READY" and payload["operation"] == "worktree.create"
    assert payload["operation_id"].startswith("sha256:")
    assert payload["data"]["capability_context"]["operation_id"] == "worktree.create"

    runtime_plan = W.plan(
        repo, action="create", path=root / "cli", branch="feat/cli", worktree_root=root
    )
    cap, keys = signed(runtime_plan, "nonce-cli")
    cap_file = root / "capability.json"
    cap_data = dataclasses.asdict(cap)
    cap_data["expires_at"] = cap.expires_at.isoformat()
    cap_file.write_text(json.dumps(cap_data), encoding="utf-8")
    common = Path(git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir"))
    registry = common / "bitz-flow-v2" / "trusted-worktree-keys.json"
    registry.parent.mkdir(parents=True, exist_ok=True)
    registry.write_text(json.dumps(keys), encoding="utf-8")
    registry.chmod(0o600)
    apply_command = command + [
        "--apply", "--confirm", payload["operation_id"],
        "--capability-file", str(cap_file),
        "--approval-ref", "decision:test",
    ]
    applied = subprocess.run(apply_command, text=True, capture_output=True, check=False)
    applied_payload = json.loads(applied.stdout)
    assert applied.returncode == 0 and applied_payload["code"] == "DONE"
    assert (root / "cli").is_dir()
