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


def signed(plan, nonce=None):
    # nonce は operation_id から導出される（SI-FLW-061）。
    # 明示指定は「導出値と違う nonce を拒否する」negative fixture のためだけに使う。
    nonce = W.derive_nonce(plan.operation_id) if nonce is None else nonce
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
    cap, keys = signed(create)
    result = W.apply(create, confirm=create.operation_id, capability=cap, trusted_keys_for_test=keys)
    assert result.code == "DONE"
    assert path.is_dir() and git(path, "branch", "--show-current") == "feat/runtime"

    resume = W.plan(repo, action="resume", path=path, branch="feat/runtime", worktree_root=root)
    cap, keys = signed(resume)
    assert W.apply(resume, confirm=resume.operation_id, capability=cap, trusted_keys_for_test=keys).code == "DONE"

    git(repo, "merge", "--ff-only", "feat/runtime")
    finish = W.plan(repo, action="finish", path=path, branch="feat/runtime", worktree_root=root)
    cap, keys = signed(finish)
    result = W.apply(finish, confirm=finish.operation_id, capability=cap, trusted_keys_for_test=keys)
    assert result.code == "DONE"
    assert not path.exists()
    assert subprocess.run(["git", "show-ref", "--verify", "refs/heads/feat/runtime"], cwd=repo).returncode != 0


def test_FLW_CON_006_discard_retains_tip_and_removes_actual_worktree(repository):
    repo, root = repository
    path = root / "discard"
    create = W.plan(repo, action="create", path=path, branch="feat/discard", worktree_root=root)
    cap, keys = signed(create)
    assert W.apply(create, confirm=create.operation_id, capability=cap, trusted_keys_for_test=keys).code == "DONE"
    (path / "change.txt").write_text("committed\n", encoding="utf-8")
    git(path, "add", "change.txt"); git(path, "commit", "-m", "discard me")
    tip = git(path, "rev-parse", "HEAD")

    discard = W.plan(repo, action="discard", path=path, branch="feat/discard", worktree_root=root)
    cap, keys = signed(discard)
    result = W.apply(discard, confirm=discard.operation_id, capability=cap, trusted_keys_for_test=keys)
    assert result.code == "DONE" and not path.exists()
    retained = git(repo, "for-each-ref", "--format=%(objectname)", "refs/bitz-flow/retained/")
    assert tip in retained


def test_FLW_CON_005_missing_bad_or_reused_capability_has_no_git_side_effect(repository):
    repo, root = repository
    path = root / "blocked"
    plan = W.plan(repo, action="create", path=path, branch="feat/blocked", worktree_root=root)
    cap, keys = signed(plan)
    wrong = dataclasses.replace(cap, signature=base64.b64encode(b"x" * 64).decode())
    result = W.apply(plan, confirm=plan.operation_id, capability=wrong, trusted_keys_for_test=keys)
    assert result.code == "BLOCKED" and not path.exists()
    result = W.apply(plan, confirm="sha256:wrong", capability=cap, trusted_keys_for_test=keys)
    assert result.code == "STALE" and not path.exists()
    assert W.apply(plan, confirm=plan.operation_id, capability=cap, trusted_keys_for_test=keys).code == "DONE"
    second = W.apply(plan, confirm=plan.operation_id, capability=cap, trusted_keys_for_test=keys)
    assert second.code == "BLOCKED"


def test_FLW_CON_006_crash_before_first_mutation_quarantines_nonce_without_side_effect(repository):
    repo, root = repository
    path = root / "crash"
    plan = W.plan(repo, action="create", path=path, branch="feat/crash", worktree_root=root)
    cap, keys = signed(plan)
    result = W.apply(
        plan, confirm=plan.operation_id, capability=cap, trusted_keys_for_test=keys,
        step_hook=lambda step: (_ for _ in ()).throw(W.WorktreeRuntimeError(f"crash:{step}")),
    )
    assert result.code == "BLOCKED" and not path.exists()
    assert W.apply(plan, confirm=plan.operation_id, capability=cap, trusted_keys_for_test=keys).code == "BLOCKED"


def test_FLW_CON_005_state_change_after_plan_is_stale_and_has_no_git_side_effect(repository):
    repo, root = repository
    path = root / "occupied"
    plan = W.plan(repo, action="create", path=path, branch="feat/occupied", worktree_root=root)
    cap, keys = signed(plan)
    path.mkdir()

    result = W.apply(plan, confirm=plan.operation_id, capability=cap, trusted_keys_for_test=keys)

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

    with pytest.raises(W.WorktreeRuntimeError, match="owner-only"):
        W.load_trusted_keys(common)


def test_FLW_CON_006_partial_discard_retains_tip_and_quarantines_receipt(repository):
    repo, root = repository
    path = root / "partial"
    create = W.plan(repo, action="create", path=path, branch="feat/partial", worktree_root=root)
    cap, keys = signed(create)
    assert W.apply(create, confirm=create.operation_id, capability=cap, trusted_keys_for_test=keys).code == "DONE"
    discard = W.plan(repo, action="discard", path=path, branch="feat/partial", worktree_root=root)
    cap, keys = signed(discard)

    def fail_after_retention(step):
        if step == "git-worktree-remove":
            raise W.WorktreeRuntimeError("injected after retention")

    result = W.apply(
        discard, confirm=discard.operation_id, capability=cap, trusted_keys_for_test=keys,
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


@pytest.mark.parametrize("action", ["audit", "create", "resume", "finish", "discard"])
def test_FLW_CON_006_worktree_is_not_reachable_from_the_dispatcher(repository, action):
    """出荷面は M0 read-only だけで、worktree は公開入口から到達できないこと。

    ROADMAP の縮退規則3（M2 出口が閉じるまで worktree を公開しない）の機械検査。
    安全核と runtime adapter は実装済みだが公開集合から外してある
    （裁定 2026-08-15 — `.spec/reports/decision-2026-08-15-m0-shipping-surface-and-m2-rescope.md`）。
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


def test_FLW_CON_006_dispatcher_apply_creates_no_worktree(repository):
    """公開入口へ apply 一式を渡しても副作用が起きないこと。"""
    repo, root = repository
    target = root / "cli"
    proc = subprocess.run(
        [sys.executable, str(SKILL / "scripts" / "flow.py"), "worktree", "create",
         "--repo", str(repo), "--path", str(target), "--branch", "feat/cli",
         "--worktree-root", str(root), "--apply", "--confirm", "sha256:" + "0" * 64,
         "--approval-ref", "decision:test", "--format", "json"],
        text=True, capture_output=True, check=False,
    )
    assert json.loads(proc.stdout)["code"] == "UNSUPPORTED"
    assert not target.exists()
    assert "feat/cli" not in git(repo, "branch", "--format=%(refname:short)")


# === plan-digest モード（既定。SI-FLW-061） ===================================


def test_SI_FLW_061_plan_digest_mode_applies_without_a_signature(repository):
    """registry が無い配備では署名なしで承認が成立し、実 worktree が作られること。"""
    repo, root = repository
    create = W.plan(repo, action="create", path=root / "pd", branch="feat/pd", worktree_root=root)
    assert not W.signature_mode_available(create.common_dir)
    result = W.apply(create, confirm=create.operation_id)
    assert result.code == "DONE", result.summary
    assert (root / "pd").is_dir()


def test_SI_FLW_061_plan_digest_rejects_confirm_mismatch_without_side_effect(repository):
    repo, root = repository
    create = W.plan(repo, action="create", path=root / "pd2", branch="feat/pd2", worktree_root=root)
    result = W.apply(create, confirm="sha256:" + "0" * 64)
    assert result.code == "STALE"
    assert not (root / "pd2").exists()


def test_SI_FLW_061_nonce_is_derived_from_operation_id_and_blocks_reuse(repository):
    """nonce は承認へ束縛される。同じ承認の再適用は消費済みとして拒否されること。"""
    repo, root = repository
    create = W.plan(repo, action="create", path=root / "pd3", branch="feat/pd3", worktree_root=root)
    assert W.derive_nonce(create.operation_id) == W.derive_nonce(create.operation_id)
    assert W.derive_nonce(create.operation_id) != W.derive_nonce(create.operation_id + "x")
    assert W.apply(create, confirm=create.operation_id).code == "DONE"
    again = W.apply(create, confirm=create.operation_id)
    assert again.code in {"BLOCKED", "STALE"}


def test_SI_FLW_061_signed_mode_rejects_a_capability_whose_nonce_is_not_derived(repository):
    """署名モードでも nonce は operation_id 由来でなければ拒否されること。"""
    repo, root = repository
    create = W.plan(repo, action="create", path=root / "pd4", branch="feat/pd4", worktree_root=root)
    cap, keys = signed(create, "attacker-chosen-nonce")
    result = W.apply(create, confirm=create.operation_id, capability=cap, trusted_keys_for_test=keys)
    assert result.code == "BLOCKED"
    assert not (root / "pd4").exists()


def test_SI_FLW_061_signed_mode_requires_a_capability(repository):
    repo, root = repository
    create = W.plan(repo, action="create", path=root / "pd5", branch="feat/pd5", worktree_root=root)
    _, keys = signed(create)
    result = W.apply(create, confirm=create.operation_id, trusted_keys_for_test=keys)
    assert result.code == "BLOCKED"
    assert not (root / "pd5").exists()


# === SI-FLW-057: mutation境界の例外分類と create/resume の reconcile 経路 =======


def test_SI_FLW_057_plain_valueerror_in_mutation_is_reported_as_partial(repository):
    """副作用適用後の素の ValueError が transaction 境界を貫通しないこと。

    以前は module 内の `RuntimeError(ValueError)` が組み込みを遮蔽し、mutation 境界の
    `except (RuntimeError, OSError)` が素の ValueError を捕捉しなかった。その結果
    worktree は作成済みなのに「副作用前に停止」を意味する BLOCKED が返っていた
    （`FLW-REV-016:SYN-003`）。
    """
    repo, root = repository
    create = W.plan(repo, action="create", path=root / "vex", branch="feat/vex", worktree_root=root)
    seen: list[str] = []

    def hook(step: str) -> None:
        seen.append(step)

    original = W._ReceiptLog.append
    calls = {"n": 0}

    def flaky(self, record):
        calls["n"] += 1
        if record.get("state") == "MUTATING":
            raise ValueError("plain ValueError after the first mutation")
        return original(self, record)

    W._ReceiptLog.append = flaky
    try:
        result = W.apply(create, confirm=create.operation_id, step_hook=hook)
    finally:
        W._ReceiptLog.append = original

    assert (root / "vex").is_dir(), "副作用は実際に起きている"
    assert result.code == "PARTIAL", f"副作用後の失敗を BLOCKED と誤報しない: {result.summary}"
    assert result.completed_steps == ("git-worktree-add",)


def test_SI_FLW_057_keyerror_in_mutation_is_also_caught(repository):
    repo, root = repository
    create = W.plan(repo, action="create", path=root / "kex", branch="feat/kex", worktree_root=root)
    original = W._ReceiptLog.append

    def flaky(self, record):
        if record.get("state") == "MUTATING":
            raise KeyError("missing field")
        return original(self, record)

    W._ReceiptLog.append = flaky
    try:
        result = W.apply(create, confirm=create.operation_id)
    finally:
        W._ReceiptLog.append = original
    assert result.code == "PARTIAL"


def test_SI_FLW_057_create_and_resume_have_a_reconcile_path():
    """create / resume が別 operation の step 列へ黙って照合されないこと。"""
    from flowlib import worktree_cleanup as CL

    assert CL.reconcile_steps("worktree.create", ()).code == "PARTIAL"
    assert CL.reconcile_steps("worktree.create", ("git-worktree-add",)).code == "DONE"
    assert CL.reconcile_steps("worktree.resume", ("publish-resume-receipt",)).code == "DONE"
    # 別 operation の step は前置にならない
    assert CL.reconcile_steps("worktree.create", ("verify-pr-merge",)).code == "INDETERMINATE"
    # 未知 operation を既定へ倒さない
    assert CL.reconcile_steps("worktree.unknown", ()).code == "INDETERMINATE"


def test_SI_FLW_057_partial_create_receipt_reconciles_against_the_same_vocabulary(repository):
    """実 receipt の completed 列が、cleanup 核の step 列の真の前置になること。"""
    from flowlib import worktree_cleanup as CL

    repo, root = repository
    create = W.plan(repo, action="create", path=root / "rec", branch="feat/rec", worktree_root=root)
    assert W.apply(create, confirm=create.operation_id).code == "DONE"
    common = Path(git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir"))
    records = [json.loads(p.read_text(encoding="utf-8"))["record"]
               for p in sorted((common / "bitz-flow-v2" / "receipts").glob("*.json"))]
    done = [r for r in records
            if r["operation_id"] == create.operation_id and r["state"] == "DONE"]
    assert done, "DONE receipt が存在する"
    decision = CL.reconcile_steps("worktree.create", tuple(done[-1]["completed_steps"]))
    assert decision.code == "DONE", decision.reason
