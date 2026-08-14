"""M1-3 の出口判定 — fault fixture 17件（FLW-DSN-015 の fault fixture catalog）。

各テスト名に fixture ID を含め、どの fixture がどの検証に対応するか機械的に辿れるようにする。
対象は M1-3 割付分（FLT-001〜009, 016, 019, 020, 024〜027, 029）で、
FLT-010〜015 / 017 / 018 / 021〜023 / 028 / 030 は M1-5 の担当。
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / "plugins" / "bitz-flow" / "skills" / "flow-core"
FLOW = SKILL / "scripts" / "flow.py"
sys.path.insert(0, str(SKILL / "scripts"))

from flowlib import commit_causality as CC  # noqa: E402
from flowlib import durable as D  # noqa: E402
from flowlib import git_write as W  # noqa: E402
from flowlib import guard as GD  # noqa: E402
from flowlib import intent as IN  # noqa: E402
from flowlib import recovery as RC  # noqa: E402
from flowlib import result as R  # noqa: E402

T0 = datetime(2026, 8, 12, tzinfo=timezone.utc)
DIGEST = R.sha256_of(b"snapshot")

#: このファイルが担当する fixture（M1-3 割付）。
M1_3_FIXTURES = (
    "M1-FLT-001", "M1-FLT-002", "M1-FLT-003", "M1-FLT-004", "M1-FLT-005",
    "M1-FLT-006", "M1-FLT-007", "M1-FLT-008", "M1-FLT-009", "M1-FLT-016",
    "M1-FLT-019", "M1-FLT-020", "M1-FLT-024", "M1-FLT-025", "M1-FLT-026",
    "M1-FLT-027", "M1-FLT-029",
)


class _Replica:
    def __init__(self, ack=True):
        self.ack = ack

    def append_wal(self, entry_bytes, digest):
        return self.ack


class _Tokens:
    def __init__(self):
        self._n = 0

    def __call__(self, key):
        self._n += 1
        return self._n


@pytest.fixture
def log(tmp_path):
    return D.DurableLog(tmp_path / "intent", replica=_Replica())


@pytest.fixture
def store(log):
    return IN.IntentStore(log, repo_identity={"local_common_dir": DIGEST}, owner_process="p1")


@pytest.fixture
def manager():
    return GD.TargetGuardManager()


@pytest.fixture
def tokens():
    return _Tokens()


@pytest.fixture
def repo(tmp_path):
    path = tmp_path / "repo"
    path.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(path)], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "t@example.com"], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "t"], check=True)
    (path / "a.txt").write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(path), "add", "a.txt"], check=True)
    subprocess.run(["git", "-C", str(path), "commit", "-qm", "chore: init"], check=True)
    (path / "b.txt").write_text("new\n", encoding="utf-8")
    (path / "c.txt").write_text("other\n", encoding="utf-8")
    return path


def _open(store, operation_id="op-1"):
    return store.open(
        operation_id=operation_id,
        targets=[{"kind": "index", "canonical_key": "index:abc:wt-1"}],
        snapshot_digest=DIGEST,
        expected_effect_digest=R.sha256_of(b"e"),
    )


# === FLT-001: intent の各点 crash ==============================================


@pytest.mark.parametrize("step", D.STEPS)
def test_m1_flt_001_intent_crash_at_each_point(tmp_path, step):
    """record 不在なら副作用 0、torn なら隔離。いずれも Commit を渡さない。"""
    root = tmp_path / "i"
    log = D.DurableLog(root, replica=_Replica(), step_hook=D.crash_after(step))
    store = IN.IntentStore(log, repo_identity={}, owner_process="p")
    intent = _open(store)
    store.transition(intent, IN.GUARDED)

    failure = store.transition(intent, IN.PENDING_INTENT)
    assert failure is not None, "commit point 未到達で PENDING_INTENT にしない"
    assert intent.commit is None
    assert intent.state == IN.GUARDED

    report, _ = D.DurableLog(root, replica=_Replica()).scan()
    if step in (D.STEP_TEMP_WRITTEN, D.STEP_FILE_FSYNCED):
        assert report.torn, "rename 前の中断は torn として隔離対象になる"
    else:
        assert report.healthy, "rename 後は valid な chain として読める"


# === FLT-002: intent fsync 後・mutation 前 crash ================================


def test_m1_flt_002_pending_intent_blocks_next_write(store, manager, tokens, tmp_path):
    intent = _open(store)
    store.transition(intent, IN.GUARDED)
    store.transition(intent, IN.PENDING_INTENT)
    assert intent.blocks_next_write is True

    target = GD.Target("index", "index:abc:wt-1")
    manager.mark_pending(target, intent.operation_id)
    guard_set, failure = manager.acquire([target], operation_id="op-2", next_token=tokens)
    assert guard_set is None
    assert failure.code == GD.CODE_BLOCKED


# === FLT-003: commit CAS 直後 crash ============================================


def test_m1_flt_003_cas_crash_without_receipt_is_indeterminate(repo):
    subprocess.run(["git", "-C", str(repo), "add", "b.txt"], check=True)
    plan, _ = CC.plan_commit(repo, message="feat: x\n", ref="refs/heads/main")
    CC.save_object(repo, plan)
    CC.cas_update_ref(repo, plan, operation_id="op-1", fencing_token=1)

    code, conclusion, failure = CC.conclude(repo, plan, receipt=None, operation_id="op-1")
    assert code == CC.CODE_INDETERMINATE
    assert conclusion == CC.CONCLUSION_UNRESOLVED


# === FLT-004: reconcile 中 crash ===============================================


def test_m1_flt_004_reconciling_keeps_pending_and_forbids_blind_retry(store):
    intent = _open(store)
    for state in (IN.GUARDED, IN.PENDING_INTENT, IN.MUTATING, IN.RECONCILING):
        store.transition(intent, state)
    assert intent.requires_intent and intent.blocks_next_write

    decision = RC.decide(operation="git.commit", phase="post-apply", code=RC.UNCLASSIFIED_OUTCOME)
    assert decision.recovery_class == RC.RECONCILE_ONLY
    assert "command blind retry" in decision.forbidden
    assert decision.max_postcondition_rechecks == 2


# === FLT-005: stage / commit の cross-family 競合 ===============================


def test_m1_flt_005_cross_family_allows_one_mutation(manager, tokens, tmp_path):
    common = tmp_path / "repo" / ".git"
    common.mkdir(parents=True)
    index = GD.canonical_index_target(common, "wt-1")

    stage, failure = manager.acquire([index], operation_id="op-stage", next_token=tokens, family_lock="index")
    assert failure is None
    commit, failure = manager.acquire([index], operation_id="op-commit", next_token=tokens, family_lock="ref")
    assert commit is None and failure.code == GD.CODE_BLOCKED

    assert manager.verify_before_mutation(stage, index) is None, "敗者側だけが止まる"


# === FLT-006: 複数 target の逆順要求 ===========================================


def test_m1_flt_006_reverse_order_is_normalized(manager, tokens, tmp_path):
    common = tmp_path / "repo" / ".git"
    common.mkdir(parents=True)
    targets = GD.order([
        GD.canonical_local_ref_target(common, "main"),
        GD.canonical_index_target(common, "wt-1"),
    ])
    guard_set, failure = manager.acquire(list(reversed(targets)), operation_id="op-1", next_token=tokens)
    assert failure is None
    assert [t.canonical_key for t in guard_set.targets] == [t.canonical_key for t in targets]


# === FLT-007: 副作用後の output-limit ==========================================


def test_m1_flt_007_output_limit_after_side_effect_reconciles(store):
    decision = RC.decide(operation="git.stage", phase="post-apply", code=RC.UNCLASSIFIED_OUTCOME)
    assert decision.recovery_class == RC.RECONCILE_ONLY
    assert decision.max_postcondition_rechecks == RC.MAX_POSTCONDITION_RECHECKS
    assert RC.validate_next_actions(
        code=RC.UNCLASSIFIED_OUTCOME, next_actions=list(decision.allowed_next)
    ) is None


# === FLT-008: 未知の recovery tuple ============================================


def test_m1_flt_008_unknown_tuple_stops_with_empty_next():
    decision = RC.decide(operation="git.commit", phase="who-knows", code="STALE")
    assert decision.recovery_class == RC.HUMAN_STOP
    assert decision.allowed_next == ()
    assert decision.required_human_input


# === FLT-009: NEXT chain に apply を混入 =======================================


def test_m1_flt_009_apply_in_next_chain_fails_graph_check():
    graph = {"git.status": ["git.diff-summary"], "git.diff-summary": ["git.commit"]}
    reason = RC.validate_next_actions(code="PARTIAL", next_actions=["git.status"], graph=graph)
    assert reason and "git.commit" in reason


# === FLT-016: pre-object intent 直後 / object 保存直後 crash ====================


def test_m1_flt_016_before_object_save_is_no_effect(repo):
    subprocess.run(["git", "-C", str(repo), "add", "b.txt"], check=True)
    plan, _ = CC.plan_commit(repo, message="feat: x\n", ref="refs/heads/main")
    before = CC.resolve_ref(repo, "refs/heads/main")

    code, conclusion, _ = CC.conclude(repo, plan, receipt=None, operation_id="op-1")
    assert conclusion == CC.CONCLUSION_ABANDONED_NO_EFFECT
    assert CC.resolve_ref(repo, "refs/heads/main") == before


def test_m1_flt_016_after_object_save_keeps_ref_unchanged(repo):
    subprocess.run(["git", "-C", str(repo), "add", "b.txt"], check=True)
    plan, _ = CC.plan_commit(repo, message="feat: x\n", ref="refs/heads/main")
    before = CC.resolve_ref(repo, "refs/heads/main")
    CC.save_object(repo, plan)

    code, conclusion, _ = CC.conclude(repo, plan, receipt=None, operation_id="op-1")
    assert conclusion == CC.CONCLUSION_ORPHAN_OBJECT
    assert CC.resolve_ref(repo, "refs/heads/main") == before, "ref は不変"


# === FLT-019: symlink / case / worktree alias ==================================


def test_m1_flt_019_aliases_converge_to_one_guard(manager, tokens, tmp_path):
    common = tmp_path / "repo" / ".git"
    common.mkdir(parents=True)
    link = tmp_path / "alias"
    link.symlink_to(common, target_is_directory=True)

    first, failure = manager.acquire(
        [GD.canonical_index_target(common, "wt-1")], operation_id="op-1", next_token=tokens
    )
    assert failure is None
    second, failure = manager.acquire(
        [GD.canonical_index_target(link, "wt-1")], operation_id="op-2", next_token=tokens
    )
    assert second is None, "alias 経由でも同一 target として直列化する"
    assert failure.code == GD.CODE_BLOCKED


def test_m1_flt_019_distinct_worktrees_do_not_collide(manager, tokens, tmp_path):
    common = tmp_path / "repo" / ".git"
    common.mkdir(parents=True)
    a, _ = manager.acquire([GD.canonical_index_target(common, "wt-1")], operation_id="op-1", next_token=tokens)
    b, failure = manager.acquire([GD.canonical_index_target(common, "wt-2")], operation_id="op-2", next_token=tokens)
    assert failure is None and b is not None


# === FLT-020: authorization nonce の再利用・別 target 転用 ======================


def test_m1_flt_020_nonce_reuse_is_rejected_before_mutation():
    capability = IN.Capability(
        target="index:abc:wt-1", snapshot_digest=DIGEST, prior_operation_id="op-1",
        reviewer="rev", expires_at=T0 + timedelta(hours=1), nonce="n-1", key_id="k1",
    )
    failure = IN.authorize_mutation(
        capability, target="index:abc:wt-1", snapshot_digest=DIGEST,
        new_operation_id="op-2", prior_operation_id="op-1", now=T0,
        trusted_key_ids=("k1",), nonce_state="USED_PENDING",
    )
    assert failure is not None and "nonce" in failure.reason


def test_m1_flt_020_capability_cannot_be_diverted_to_another_target():
    capability = IN.Capability(
        target="index:abc:wt-1", snapshot_digest=DIGEST, prior_operation_id="op-1",
        reviewer="rev", expires_at=T0 + timedelta(hours=1), nonce="n-1", key_id="k1",
    )
    failure = IN.authorize_mutation(
        capability, target="local-ref:abc:refs/heads/main", snapshot_digest=DIGEST,
        new_operation_id="op-2", prior_operation_id="op-1", now=T0,
        trusted_key_ids=("k1",), nonce_state="UNUSED",
    )
    assert failure is not None and "target" in failure.reason


# === FLT-024: 別 clone / remote alias から同一 remote ref =======================


def test_m1_flt_024_same_remote_ref_from_different_clones(manager, tokens):
    a = GD.canonical_remote_ref_target("github.com", "R_1", "main")
    b = GD.canonical_remote_ref_target("GitHub.com", "R_1", "refs/heads/main")
    first, failure = manager.acquire([a], operation_id="op-a", next_token=tokens)
    assert failure is None
    second, failure = manager.acquire([b], operation_id="op-b", next_token=tokens)
    assert second is None and failure.code == GD.CODE_BLOCKED


# === FLT-025: token 照合後 pause → lease 満了 → guard 再発行 ====================


def test_m1_flt_025_reissue_requires_stop_proof(tmp_path):
    from flowlib import coordinator as C

    class _Store:
        def __init__(self):
            self._d = {}

        def read(self, key):
            return self._d.get(key, (None, 0))

        def compare_and_set(self, key, expected_version, value):
            _, version = self.read(key)
            if version != expected_version:
                return False
            self._d[key] = (value, version + 1)
            return True

    class _Clock:
        def now(self):
            return T0 + timedelta(days=2)  # lease は満了している

    coord = C.Coordinator(_Store(), _Clock(), epoch_id="e1", leader_epoch=1)
    token, failure = coord.reissue_guard_token(target_key="index:abc", proof=C.ReleaseProof())
    assert token is None
    assert failure.indefinite is True, "lease 満了だけでは再発行しない"

    token, failure = coord.reissue_guard_token(
        target_key="index:abc",
        proof=C.ReleaseProof(True, True, True, True, True),
    )
    assert failure is None and token == 1


# === FLT-026: object 保存後・CAS 前 crash ======================================


def test_m1_flt_026_orphan_object_is_kept(repo):
    subprocess.run(["git", "-C", str(repo), "add", "b.txt"], check=True)
    plan, _ = CC.plan_commit(repo, message="feat: x\n", ref="refs/heads/main")
    CC.save_object(repo, plan)

    code, conclusion, failure = CC.conclude(repo, plan, receipt=None, operation_id="op-1")
    assert conclusion == CC.CONCLUSION_ORPHAN_OBJECT
    assert CC.object_exists(repo, plan.planned_oid), "object を削除しない"
    assert IN.CONCLUSION_APPROVERS[conclusion] == ("repository-owner", "evaluation-reviewer")


# === FLT-027: capability nonce 消費の各点 crash・key 失効 =======================


def test_m1_flt_027_used_pending_nonce_is_quarantined():
    from flowlib import coordinator as C

    class _Store:
        def __init__(self):
            self._d = {}

        def read(self, key):
            return self._d.get(key, (None, 0))

        def compare_and_set(self, key, expected_version, value):
            _, version = self.read(key)
            if version != expected_version:
                return False
            self._d[key] = (value, version + 1)
            return True

    class _Clock:
        def now(self):
            return T0

    coord = C.Coordinator(_Store(), _Clock(), epoch_id="e1", leader_epoch=1)
    assert coord.begin_nonce("n-1") is None
    failure = coord.begin_nonce("n-1")  # 消費途中で crash した後の再試行
    assert failure.indefinite is True
    assert coord.finish_nonce("n-1", outcome=C.NONCE_QUARANTINED) is None


def test_m1_flt_027_revoked_key_is_rejected():
    capability = IN.Capability(
        target="t", snapshot_digest=DIGEST, prior_operation_id="op-1", reviewer="rev",
        expires_at=T0 + timedelta(hours=1), nonce="n", key_id="revoked",
    )
    failure = IN.authorize_mutation(
        capability, target="t", snapshot_digest=DIGEST, new_operation_id="op-2",
        prior_operation_id="op-1", now=T0, trusted_key_ids=("k1",), nonce_state="UNUSED",
    )
    assert failure is not None and "署名鍵" in failure.reason


# === FLT-029: index digest 照合直後の割込み ====================================


def test_m1_flt_029_native_lock_excludes_git_add(repo):
    common = repo / ".git"
    outcome = {}

    def intruder(_c):
        outcome["proc"] = subprocess.run(
            ["git", "-C", str(repo), "add", "c.txt"], capture_output=True, text=True
        )

    plan, _ = W.plan_stage(repo, common, ["b.txt"])
    digest, failure = W.apply_stage(common, plan, on_locked=intruder)
    assert outcome["proc"].returncode != 0
    assert failure is None and digest is not None


def test_m1_flt_029_lock_ignoring_writer_is_quarantined(repo):
    common = repo / ".git"

    def intruder(_c):
        W.index_path(common).write_bytes(b"DIRTY")

    plan, _ = W.plan_stage(repo, common, ["b.txt"])
    digest, failure = W.apply_stage(common, plan, on_locked=intruder)
    assert digest is None
    assert failure.code == W.CODE_BLOCKED


# === 公開面の非退行 ============================================================


def _flow_json(*args, repo):
    proc = subprocess.run(
        [sys.executable, str(FLOW), "--repo", str(repo), *args, "--format", "json"],
        capture_output=True, text=True,
    )
    return json.loads(proc.stdout), proc.returncode


@pytest.mark.parametrize("action", ["stage", "commit", "fetch", "sync", "publish-branch"])
def test_write_operations_are_still_unsupported(repo, action):
    """M1-3 で実装しても公開しない（M2 未完了のため。FLW-DSN-014 縮退規則3）。"""
    result, exit_code = _flow_json("git", action, repo=repo)
    assert result["code"] == "UNSUPPORTED"
    assert exit_code == 8
    assert result["data"]["effects"] == []


def test_reachable_codes_are_still_m0_only(repo):
    seen = set()
    for args in (("repo", "inspect"), ("git", "status"), ("git", "commit"), ("git", "stage")):
        result, _ = _flow_json(*args, repo=repo)
        seen.add(result["code"])
    assert seen <= {"OK", "INVALID_INPUT", "BLOCKED", "UNAVAILABLE", "STALE", "UNSUPPORTED"}


def test_only_m0_and_m2_worktree_are_reachable_from_dispatcher():
    """dispatcher は M0 と M2 worktree runtime だけを公開する。"""
    from flowlib import cli

    expected = {
        ("repo", "inspect"), ("git", "status"), ("git", "diff-summary"),
        ("worktree", "audit"), ("worktree", "create"),
        ("worktree", "resume"), ("worktree", "finish"),
        ("worktree", "discard"),
    }
    assert set(cli._HANDLERS) == expected


# === fixture の網羅 ============================================================


def test_all_m1_3_fixtures_have_a_test():
    source = Path(__file__).read_text(encoding="utf-8")
    missing = [f for f in M1_3_FIXTURES if f.replace("-", "_").lower() not in source.lower()]
    assert missing == [], f"対応するテストが無い fixture: {missing}"
    assert len(M1_3_FIXTURES) == 17
