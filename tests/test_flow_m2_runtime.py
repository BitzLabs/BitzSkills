"""FLW-FR-006 / FLW-CON-005 / FLW-CON-006 worktree実動E2E。"""

from __future__ import annotations

import contextlib
import io
import base64
import dataclasses
import json
import shutil
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


# === SI-FLW-059: 公開 dispatcher 経由の E2E ==================================
#
# 出荷面は M0 read-only に限定されている（2026-08-15 裁定）ため、fixture は
# `{**_HANDLERS, **_GATED_HANDLERS}` を注入して公開経路を丸ごと通す
# （裁定 2026-08-16。`.spec/reports/decision-2026-08-16-si-flw-059-dispatcher-e2e.md`）。
# production では既定以外を渡さない。


def _dispatch(*argv):
    """公開 dispatcher を fixture 用ハンドラ表で起動し、結果 JSON を返す。

    `--format json` だけを通していたため、result 契約に従わない `next_actions` を入れても
    検出できず、既定形式で `KeyError` を投げる状態を出荷しかけた（`SI-FLW-065`）。
    既定 renderer は下の専用テストで担保する。
    """
    from flowlib import cli

    # 二重実行は write を2回走らせてしまうため、既定 renderer の検査は
    # 副作用の無い operation を対象にした専用テストで担保する（下の SI_FLW_065）。
    table = {**cli._HANDLERS, **cli._GATED_HANDLERS}
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = cli.main([*argv, "--format", "json"], handlers=table)
    return json.loads(buffer.getvalue()), code


def test_SI_FLW_059_dispatcher_create_then_resume_via_public_path(repository):
    """create → resume を公開経路の plan/apply で通し、実 worktree が作られること。"""
    repo, root = repository
    target = root / "pub"
    base = ["worktree", "create", "--repo", str(repo), "--path", str(target),
            "--branch", "feat/pub", "--worktree-root", str(root)]

    plan_result, _ = _dispatch(*base)
    assert plan_result["code"] == "READY", plan_result["summary"]
    assert plan_result["data"]["approval_mode"] == "plan-digest"
    operation_id = plan_result["operation_id"]

    applied, _ = _dispatch(*base, "--apply", "--confirm", operation_id)
    assert applied["code"] == "DONE", applied["summary"]
    assert target.is_dir()

    resume_base = ["worktree", "resume", "--repo", str(repo), "--path", str(target),
                   "--branch", "feat/pub", "--worktree-root", str(root)]
    resume_plan, _ = _dispatch(*resume_base)
    assert resume_plan["code"] == "READY"
    resumed, _ = _dispatch(*resume_base, "--apply", "--confirm", resume_plan["operation_id"])
    assert resumed["code"] == "DONE", resumed["summary"]


def test_SI_FLW_059_dispatcher_rejects_a_stale_confirm_without_side_effect(repository):
    """公開経路で confirm 不一致なら副作用0で停止すること。"""
    repo, root = repository
    target = root / "stale"
    result, _ = _dispatch(
        "worktree", "create", "--repo", str(repo), "--path", str(target),
        "--branch", "feat/stale", "--worktree-root", str(root),
        "--apply", "--confirm", "sha256:" + "0" * 64,
    )
    assert result["code"] == "STALE"
    assert not target.exists()


def test_SI_FLW_059_dispatcher_blocks_approval_reuse(repository):
    """承認の使い回しが公開経路で拒否されること（nonce 単回性）。"""
    repo, root = repository
    target = root / "reuse"
    base = ["worktree", "create", "--repo", str(repo), "--path", str(target),
            "--branch", "feat/reuse", "--worktree-root", str(root)]
    plan_result, _ = _dispatch(*base)
    operation_id = plan_result["operation_id"]
    assert _dispatch(*base, "--apply", "--confirm", operation_id)[0]["code"] == "DONE"
    again, _ = _dispatch(*base, "--apply", "--confirm", operation_id)
    assert again["code"] in {"BLOCKED", "STALE"}


def test_SI_FLW_059_dispatcher_requires_confirm_for_apply(repository):
    repo, root = repository
    result, _ = _dispatch(
        "worktree", "create", "--repo", str(repo), "--path", str(root / "noconfirm"),
        "--branch", "feat/noconfirm", "--worktree-root", str(root), "--apply",
    )
    assert result["code"] == "APPROVAL_REQUIRED"
    assert not (root / "noconfirm").exists()


def test_SI_FLW_059_audit_goes_through_the_contract_layer(repository):
    """audit が result を返し、--limit を尊重すること。"""
    repo, root = repository
    result, _ = _dispatch("worktree", "audit", "--repo", str(repo), "--limit", "1")
    assert result["code"] in {"OK", "BLOCKED"}
    assert result["data"]["page"]["shown"] <= 1
    for row in result["data"]["items"]:
        assert set(row) == {"path", "registered", "managed", "present",
                            "head_changed", "divergence"}, row


def test_SI_FLW_064_audit_detects_an_operation_external_worktree(repository):
    """陽性対照 — operation 外で作られた worktree を検出し BLOCKED にすること。

    git の registry は `git worktree add` で必ず登録されるため区別に使えない。
    bitz-flow 自身の receipt が記録した対象と突き合わせる（`SI-FLW-064`）。
    """
    repo, root = repository
    outside = root / "outside"
    git(repo, "worktree", "add", "-b", "feat/outside", str(outside))
    try:
        result, _ = _dispatch("worktree", "audit", "--repo", str(repo))
        assert result["code"] == "BLOCKED", result["summary"]
        assert any(str(outside) in path for path in result["data"]["quarantine"]["targets"])
        # `human-stop` は空 NEXT である（`FLW-DSN-016` §8）。解除は operation ではなく
        # reviewer の裁定なので、示せる次の operation は存在しない。
        # 「次に何をするか」は required_human_input と解除区分が担う。
        assert result["next_actions"] == []
        assert result["data"]["required_human_input"]
    finally:
        git(repo, "worktree", "remove", "--force", str(outside))


def test_SYN_011_audit_connects_the_detection_to_quarantine(repository):
    """検出結果が設計の quarantine 語彙へ接続されること（`FLW-REV-017:SYN-011`）。

    M2 出口条件は「operation 外変更の audit 検出**・quarantine 接続**」である。
    検出だけでは後半を満たさない。以前は `external_changes` という独自語彙しか無く、
    裁定者が「quarantine へ接続した」と読める証跡が result に存在しなかった。
    """
    repo, root = repository
    outside = root / "outside-quarantine"
    git(repo, "worktree", "add", "-b", "feat/outside-q", str(outside))
    try:
        result, _ = _dispatch("worktree", "audit", "--repo", str(repo))
        assert result["code"] == "BLOCKED", result["summary"]
        quarantine = result["data"]["quarantine"]
        # 語彙は設計（FLW-DSN-016 §6）と実装（worktree_cleanup）の側にある。
        # `worktree_state` は公開 result に載せない — `ORPHAN` は
        # `branch_audit_state` の値であり `worktree_state` の閉集合には無い
        # （`FLW-REV-018:SYN-005`）。
        assert "worktree_state" not in quarantine
        assert quarantine["required"] is True
        assert quarantine["release_class"] == "worktree-unresolved"
        assert any(str(outside) in path for path in quarantine["targets"])
        assert result["data"]["cause"] == "quarantined"
        assert result["data"]["recovery_class"] == "human-stop"
    finally:
        git(repo, "worktree", "remove", "--force", str(outside))


def test_SYN_011_audit_is_indeterminate_when_receipts_are_unreadable(repository):
    """receipt を読めないときに分類を推測しないこと（`FLW-DSN-016` §8 の audit 行）。

    「receipt が1件も無い」と「receipt を読めない」を同一視すると、後者で
    **すべての worktree が外部起因に見える**。BLOCKED を偽って立てるのは
    「分類の推測」であり設計が禁じている。
    """
    repo, root = repository
    target = root / "for-indeterminate"
    base = ["worktree", "create", "--repo", str(repo), "--path", str(target),
            "--branch", "feat/indeterminate", "--worktree-root", str(root)]
    plan_result, _ = _dispatch(*base)
    applied, _ = _dispatch(*base, "--apply", "--confirm", plan_result["operation_id"])
    assert applied["code"] == "DONE", applied["summary"]

    receipts = sorted((repo / ".git" / "bitz-flow-v2" / "receipts").glob("*.json"))
    assert receipts, "receipt が書かれていること"
    receipts[0].write_text("{ broken", encoding="utf-8")

    result, _ = _dispatch("worktree", "audit", "--repo", str(repo))
    assert result["code"] == "INDETERMINATE", result["summary"]
    assert result["data"]["recovery_class"] == "human-stop"
    assert result["next_actions"] == [], "INDETERMINATE から NEXT を示さないこと"
    assert result["data"]["required_human_input"]
    assert not result["data"]["items"], "推測した分類を載せないこと"


def test_SI_FLW_064_audit_accepts_an_operation_created_worktree(repository):
    """陰性対照 — operation が作った worktree は外部変更にしないこと。

    検出器が「常に BLOCKED」なら反証できない検査になる。
    """
    repo, root = repository
    target = root / "managed"
    base = ["worktree", "create", "--repo", str(repo), "--path", str(target),
            "--branch", "feat/managed", "--worktree-root", str(root)]
    plan_result, _ = _dispatch(*base)
    applied, _ = _dispatch(*base, "--apply", "--confirm", plan_result["operation_id"])
    assert applied["code"] == "DONE", applied["summary"]

    result, _ = _dispatch("worktree", "audit", "--repo", str(repo))
    rows = {row["path"]: row for row in result["data"]["items"]}
    assert rows[str(target)]["managed"] is True
    assert rows[str(target)]["divergence"] == ""
    assert result["code"] == "OK", result["summary"]


def test_SI_FLW_064_receipt_records_the_change_target(repository):
    """receipt が「何を変えたか」を持つこと（従来は operation_id だけだった）。"""
    repo, root = repository
    target = root / "recorded"
    create = W.plan(repo, action="create", path=target, branch="feat/recorded",
                    worktree_root=root)
    assert W.apply(create, confirm=create.operation_id).code == "DONE"
    common = Path(git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir"))
    records = [json.loads(p.read_text(encoding="utf-8"))["record"]
               for p in sorted((common / "bitz-flow-v2" / "receipts").glob("*.json"))]
    done = [r for r in records
            if r["operation_id"] == create.operation_id and r["state"] == "DONE"]
    assert done, "DONE receipt が存在する"
    change = done[-1]["target"]
    assert change["path"] == str(target)
    assert change["branch"] == "feat/recorded"
    assert change["action"] == "create"


def test_SI_FLW_059_default_table_still_hides_worktree(repository):
    """注入しなければ公開経路からは到達できないこと（出荷面は変わっていない）。"""
    from flowlib import cli

    repo, _ = repository
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        cli.main(["worktree", "audit", "--repo", str(repo), "--format", "json"])
    assert json.loads(buffer.getvalue())["code"] == "UNSUPPORTED"


def test_SI_FLW_063_approval_source_matches_the_actual_mode(repository):
    """receipt が実際に使った承認モードを名乗ること（`SI-FLW-063`（RSK-204 / OPS-303））。

    以前は無条件に `signed-capability` を名乗り、同じ result の
    `data.approval_mode: plan-digest` と矛盾していた。承認強度を強く見せる危険側の誤り。
    """
    repo, root = repository
    base = ["worktree", "create", "--repo", str(repo), "--path", str(root / "src"),
            "--branch", "feat/src", "--worktree-root", str(root)]
    plan_result, _ = _dispatch(*base)
    applied, _ = _dispatch(*base, "--apply", "--confirm", plan_result["operation_id"])
    assert applied["code"] == "DONE", applied["summary"]
    assert applied["data"]["approval_mode"] == "plan-digest"
    assert applied["approval"]["source"] == applied["data"]["approval_mode"]


def test_SI_FLW_063_recovery_path_survives_a_failing_quarantine_append(repository):
    """復旧経路が失敗しても apply() から例外を出さないこと（`SI-FLW-063`（DIN-101 / RSK-202））。

    receipt log が読めない状況では QUARANTINED の追記も同じ例外で落ちる。
    以前は `try/finally` だけだったため例外が apply() を脱出し、副作用適用済みなのに
    PARTIAL を返せなかった。
    """
    repo, root = repository
    create = W.plan(repo, action="create", path=root / "recov", branch="feat/recov",
                    worktree_root=root)
    original = W._ReceiptLog.append

    def always_broken(self, record):
        state = record.get("state")
        if state == "PENDING":
            return original(self, record)
        raise ValueError(f"receipt log unreadable at {state}")

    W._ReceiptLog.append = always_broken
    try:
        result = W.apply(create, confirm=create.operation_id)
    finally:
        W._ReceiptLog.append = original

    assert (root / "recov").is_dir(), "副作用は起きている"
    assert result.code == "PARTIAL", f"例外を脱出させず判定を返すこと: {result.summary}"
    assert "quarantine receipt も記録できない" in result.summary


def test_SI_FLW_065_every_published_operation_renders_in_the_default_format(repository):
    """公開経路の全 operation が既定 renderer で描画できること。

    `--format json` だけを検査していると、result 契約に従わない `next_actions` を
    入れても通ってしまう。既定形式は利用者が実際に見る出力である。
    """
    from flowlib import cli

    repo, root = repository
    table = {**cli._HANDLERS, **cli._GATED_HANDLERS}
    outside = root / "renderable"
    git(repo, "worktree", "add", "-b", "feat/renderable", str(outside))
    plan_argv = ["worktree", "create", "--repo", str(repo), "--path", str(root / "planned"),
                 "--branch", "feat/planned", "--worktree-root", str(root)]
    try:
        cases = (["repo", "inspect", "--repo", str(repo)],
                 ["git", "status", "--repo", str(repo)],
                 ["git", "diff-summary", "--repo", str(repo)],
                 ["worktree", "audit", "--repo", str(repo)],   # external 検出つき（BLOCKED）
                 plan_argv)                                    # write の plan は副作用なし
        for argv in cases:
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                cli.main(argv, handlers=table)      # 例外を投げないこと自体が検査
            assert buffer.getvalue().strip(), argv
    finally:
        git(repo, "worktree", "remove", "--force", str(outside))


def test_SI_FLW_065_audit_next_action_follows_the_result_contract(repository):
    """外部変更を検出したときの result が契約の形で描画できること。

    `SI-FLW-065` の欠陥は「next_actions に契約外の dict を入れて既定 renderer が
    落ちる」であった。現在この経路は `human-stop` で空 NEXT を返すため、
    NEXT の形の検査だけでは空振りする。**既定 renderer を実際に通す**ことと、
    NEXT が出る場合に契約の形であることの両方を押さえる。
    """
    from flowlib import cli

    repo, root = repository
    outside = root / "contract"
    git(repo, "worktree", "add", "-b", "feat/contract", str(outside))
    try:
        result, _ = _dispatch("worktree", "audit", "--repo", str(repo))
        assert result["code"] == "BLOCKED"
        for action in result["next_actions"]:
            assert set(action) == {"domain", "action", "args"}, action

        # 既定形式（compact）でも同じ経路を通す。audit は read-only なので
        # 二重実行しても副作用が無い。
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            cli.main(["worktree", "audit", "--repo", str(repo)],
                     handlers={**cli._HANDLERS, **cli._GATED_HANDLERS})
        rendered = buffer.getvalue()
        assert "BLOCKED" in rendered
        assert "cause=quarantined" in rendered, "quarantine 接続が既定出力から読めること"
        assert "quarantine=worktree-unresolved" in rendered, "解除区分が既定出力から読めること"
    finally:
        git(repo, "worktree", "remove", "--force", str(outside))


# --- FLW-REV-018: audit の ground truth と分類の健全性 ------------------------


def _receipt_dir(repo):
    return repo / ".git" / "bitz-flow-v2" / "receipts"


def _create_managed_worktree(repo, root, name):
    """公開経路で worktree を1つ作り、その path を返す。"""
    target = root / name
    base = ["worktree", "create", "--repo", str(repo), "--path", str(target),
            "--branch", f"feat/{name}", "--worktree-root", str(root)]
    plan_result, _ = _dispatch(*base)
    applied, _ = _dispatch(*base, "--apply", "--confirm", plan_result["operation_id"])
    assert applied["code"] == "DONE", applied["summary"]
    return target


def test_SYN_001_forged_receipt_cannot_launder_an_external_worktree(repository):
    """陽性対照 — 手書き receipt 1件で外部 worktree を managed に洗浄できないこと。

    従来は `record_digest` を誰も検証しておらず、receipt を1件置くだけで
    audit の検出を無効化できた（独立レビュア2名が別経路で実測）。
    """
    repo, root = repository
    outside = root / "forged"
    git(repo, "worktree", "add", "-b", "feat/forged", str(outside))
    try:
        receipts = _receipt_dir(repo)
        receipts.mkdir(parents=True, exist_ok=True)
        # digest も chain も持たない、それらしい receipt を置く
        forged = {"record": {"sequence": 1, "previous_record_digest": None,
                             "state": "DONE", "operation_id": "forged",
                             "target": {"action": "create", "path": str(outside)}},
                  "record_digest": "sha256:" + "0" * 64}
        (receipts / "000000000001.json").write_text(json.dumps(forged), encoding="utf-8")

        result, _ = _dispatch("worktree", "audit", "--repo", str(repo))
        assert result["code"] == "INDETERMINATE", result["summary"]
        assert result["data"]["recovery_class"] == "human-stop"
        assert not any(row.get("managed") for row in result["data"]["items"])
    finally:
        git(repo, "worktree", "remove", "--force", str(outside))


def test_SYN_001_a_missing_receipt_is_detected_instead_of_silently_dropped(repository):
    """陽性対照 — receipt が1件欠けたら照合不能として扱うこと。

    従来は欠落に気づかず、正規の worktree が「外部起因」へ誤分類された。
    """
    repo, root = repository
    _create_managed_worktree(repo, root, "dropped")
    entries = sorted(_receipt_dir(repo).glob("*.json"))
    assert len(entries) >= 2, "create は複数 receipt を書く"
    entries[0].unlink()

    result, _ = _dispatch("worktree", "audit", "--repo", str(repo))
    assert result["code"] == "INDETERMINATE", result["summary"]
    assert "連番" in result["data"]["required_human_input"]


def test_SYN_001_an_intact_chain_is_accepted(repository):
    """陰性対照 — 無傷の chain は照合成立とすること（常時 INDETERMINATE にしない）。"""
    repo, root = repository
    target = _create_managed_worktree(repo, root, "intact")
    result, _ = _dispatch("worktree", "audit", "--repo", str(repo))
    assert result["code"] == "OK", result["summary"]
    rows = {row["path"]: row for row in result["data"]["items"]}
    assert rows[str(target)]["managed"] is True


def test_SYN_002_external_deletion_of_a_managed_worktree_is_detected(repository):
    """陽性対照 — managed worktree の実体が外部から消えたら検出すること。

    従来は registry → receipt の片方向しか見ておらず、`OK` を返していた。
    """
    repo, root = repository
    target = _create_managed_worktree(repo, root, "vanished")
    shutil.rmtree(target)

    result, _ = _dispatch("worktree", "audit", "--repo", str(repo))
    assert result["code"] == "BLOCKED", result["summary"]
    rows = {row["path"]: row for row in result["data"]["items"]}
    assert rows[str(target)]["divergence"] == "directory-missing"
    assert str(target) in result["data"]["quarantine"]["targets"]
    assert result["data"]["quarantine"]["release_class"] == "worktree-unresolved"
    assert result["data"]["quarantine"]["binding_findings"]


def test_SYN_002_head_movement_is_reported_but_not_a_violation(repository):
    """陰性対照 — managed worktree での通常の作業（HEAD 前進）を違反にしないこと。

    出口条件6は「worktree の生成・消失・binding 不整合」に限る（裁定 2026-08-16 案1）。
    任意のコミットの正当性は判定しない。
    """
    repo, root = repository
    target = _create_managed_worktree(repo, root, "working")
    (target / "note.txt").write_text("work", encoding="utf-8")
    git(target, "add", "note.txt")
    git(target, "-c", "user.email=t@e", "-c", "user.name=t", "commit", "-m", "feat: work")

    result, _ = _dispatch("worktree", "audit", "--repo", str(repo))
    assert result["code"] == "OK", result["summary"]
    rows = {row["path"]: row for row in result["data"]["items"]}
    assert rows[str(target)]["head_changed"] is True, "事実としては報告すること"
    assert rows[str(target)]["divergence"] == "", "違反にはしないこと"


def test_SYN_003_a_receipt_store_that_is_not_a_directory_is_indeterminate(repository):
    """陽性対照 — store がディレクトリでない場合を「1件も無い」と同一視しないこと。

    同一視すると全 worktree が外部起因に見え、`BLOCKED` を偽って立てる。
    """
    repo, root = repository
    outside = root / "store-broken"
    git(repo, "worktree", "add", "-b", "feat/store-broken", str(outside))
    try:
        receipts = _receipt_dir(repo)
        receipts.parent.mkdir(parents=True, exist_ok=True)
        receipts.write_text("not a directory", encoding="utf-8")

        result, _ = _dispatch("worktree", "audit", "--repo", str(repo))
        assert result["code"] == "INDETERMINATE", result["summary"]
        assert "ディレクトリではない" in result["data"]["required_human_input"]
    finally:
        git(repo, "worktree", "remove", "--force", str(outside))


def test_SYN_004_release_class_is_computed_from_the_survey(repository):
    """解除区分が固定リテラルではなく観測から計算されていること。

    従来は全フィールド固定の evidence を渡しており、分類ではなく表示だった。
    """
    from flowlib import worktree_cleanup as CL

    repo, root = repository
    outside = root / "computed"
    git(repo, "worktree", "add", "-b", "feat/computed", str(outside))
    try:
        result, _ = _dispatch("worktree", "audit", "--repo", str(repo))
        assert result["code"] == "BLOCKED"
        assert result["data"]["quarantine"]["release_class"] == "worktree-unresolved"
        # 分類器が入力に反応することを、同じ関数へ別の証跡を与えて示す
        assert CL.classify_quarantine(
            CL.QuarantineEvidence(True, ("git-worktree-add",), True, 1, True),
            total_mutating_steps=1) == "worktree-confirmed-done"
    finally:
        git(repo, "worktree", "remove", "--force", str(outside))


def test_SYN_005_public_result_uses_only_closed_enum_vocabulary(repository):
    """公開 result が閉集合の外の状態値を載せないこと。

    `ORPHAN` は `branch_audit_state` の値で、`worktree_state` の閉集合
    （`ABSENT` / `CLEAN` / `DIRTY` / `MISMATCH`）には無い。
    """
    repo, root = repository
    outside = root / "enum"
    git(repo, "worktree", "add", "-b", "feat/enum", str(outside))
    try:
        result, _ = _dispatch("worktree", "audit", "--repo", str(repo))
        payload = json.dumps(result, ensure_ascii=False)
        assert "ORPHAN" not in payload
        assert "worktree_state" not in payload
    finally:
        git(repo, "worktree", "remove", "--force", str(outside))
