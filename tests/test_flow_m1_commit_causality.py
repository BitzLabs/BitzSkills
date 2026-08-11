"""REC-COMMIT の因果証跡（FLW-FR-005 / FLW-NFR-003）を実 Git リポジトリで検証する。

中心命題: **receipt が無ければ DONE にしない**。ref が planned OID を指していても、
それを書いたのが自分だと証明できない限り INDETERMINATE として人間へ回す。
"""

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / "plugins" / "bitz-flow" / "skills" / "flow-core"
sys.path.insert(0, str(SKILL / "scripts"))

from flowlib import commit_causality as CC  # noqa: E402

MESSAGE = "feat(x): add feature\n\nImplements FLW-FR-005\n"


def _git(repo: Path, *args: str):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True)


@pytest.fixture
def repo(tmp_path):
    path = tmp_path / "repo"
    path.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(path)], check=True)
    _git(path, "config", "user.email", "t@example.com")
    _git(path, "config", "user.name", "t")
    (path / "a.txt").write_text("base\n", encoding="utf-8")
    _git(path, "add", "a.txt")
    _git(path, "commit", "-qm", "chore: init")
    (path / "b.txt").write_text("new\n", encoding="utf-8")
    _git(path, "add", "b.txt")
    return path


def _plan(repo):
    plan, failure = CC.plan_commit(repo, message=MESSAGE, ref="refs/heads/main")
    assert failure is None, failure
    return plan


def _plan_and_save(repo):
    """手順3（intent）の後に手順4（object 保存）を済ませた状態を作る。"""
    plan = _plan(repo)
    oid, failure = CC.save_object(repo, plan)
    assert failure is None and oid == plan.planned_oid
    return plan


# --- message の事前検査 --------------------------------------------------------


@pytest.mark.parametrize(
    "message", ["feat: x", "fix(scope): y", "refactor!: z", "docs(a-b): c"]
)
def test_conventional_messages_pass(message):
    assert CC.lint_message(message) is None


@pytest.mark.parametrize("message", ["update stuff", "", "FEAT: x", "feat x"])
def test_non_conventional_messages_are_rejected(message):
    failure = CC.lint_message(message)
    assert failure is not None and failure.code == CC.CODE_INVALID_INPUT


def test_plan_rejects_bad_message(repo):
    plan, failure = CC.plan_commit(repo, message="whatever", ref="refs/heads/main")
    assert plan is None and failure.code == CC.CODE_INVALID_INPUT


# --- plan は副作用を持たない ---------------------------------------------------


def test_plan_does_not_move_the_ref(repo):
    before = CC.resolve_ref(repo, "refs/heads/main")
    plan = _plan(repo)
    assert CC.resolve_ref(repo, "refs/heads/main") == before
    assert plan.old_oid == before


def test_plan_does_not_write_the_commit_object(repo):
    """planned OID を計算しても object store には書かない（手順4 は intent の後）。"""
    plan = _plan(repo)
    assert not CC.object_exists(repo, plan.planned_oid)


def test_save_object_writes_exactly_the_planned_oid(repo):
    plan = _plan(repo)
    oid, failure = CC.save_object(repo, plan)
    assert failure is None
    assert oid == plan.planned_oid, "保存した OID が plan と違えば因果を追跡できない"
    assert CC.object_exists(repo, plan.planned_oid)


def test_plan_is_deterministic(repo):
    a = _plan(repo)
    b = _plan(repo)
    assert a.planned_oid == b.planned_oid, "同じ入力からは同じ planned OID が出る"
    assert a.canonical_bytes == b.canonical_bytes


def test_planned_oid_matches_canonical_bytes(repo):
    plan = _plan(repo)
    assert plan.tree_oid in plan.canonical_bytes.decode("utf-8", "replace")
    assert MESSAGE.splitlines()[0] in plan.canonical_bytes.decode("utf-8", "replace")


# --- CAS と receipt ------------------------------------------------------------


def test_cas_moves_ref_and_returns_receipt(repo):
    plan = _plan_and_save(repo)
    receipt, failure = CC.cas_update_ref(repo, plan, operation_id="op-1", fencing_token=7)
    assert failure is None
    assert receipt.before_oid == plan.old_oid
    assert receipt.after_oid == plan.planned_oid
    assert CC.resolve_ref(repo, "refs/heads/main") == plan.planned_oid


def test_cas_fails_when_ref_moved(repo):
    """plan 後に ref が動いていれば CAS は成立しない。"""
    plan = _plan_and_save(repo)
    (repo / "c.txt").write_text("other\n", encoding="utf-8")
    _git(repo, "add", "c.txt")
    _git(repo, "commit", "-qm", "chore: other")

    receipt, failure = CC.cas_update_ref(repo, plan, operation_id="op-1", fencing_token=7)
    assert receipt is None
    assert failure.code == CC.CODE_STALE
    assert failure.cause == "snapshot-mismatch"


def test_conclude_done_requires_receipt_and_matching_ref(repo):
    plan = _plan_and_save(repo)
    receipt, _ = CC.cas_update_ref(repo, plan, operation_id="op-1", fencing_token=7)
    code, conclusion, failure = CC.conclude(repo, plan, receipt=receipt, operation_id="op-1")
    assert code == CC.CODE_DONE
    assert conclusion == CC.CONCLUSION_CONFIRMED_DONE
    assert failure is None


# --- receipt が無い場合（中心命題）---------------------------------------------


def test_ref_at_planned_oid_without_receipt_is_indeterminate(repo):
    """M1-FLT-003: CAS 直後 crash で receipt を失った状況。"""
    plan = _plan_and_save(repo)
    CC.cas_update_ref(repo, plan, operation_id="op-1", fencing_token=7)

    code, conclusion, failure = CC.conclude(repo, plan, receipt=None, operation_id="op-1")
    assert code == CC.CODE_INDETERMINATE, "ref が一致していても DONE と推定しない"
    assert conclusion == CC.CONCLUSION_UNRESOLVED
    assert "DONE と推定しない" in failure.reason


def test_receipt_from_another_operation_is_not_proof(repo):
    plan = _plan_and_save(repo)
    receipt, _ = CC.cas_update_ref(repo, plan, operation_id="op-other", fencing_token=7)
    code, conclusion, failure = CC.conclude(repo, plan, receipt=receipt, operation_id="op-1")
    assert code == CC.CODE_INDETERMINATE
    assert "operation ID が一致しない" in failure.reason


def test_object_saved_but_ref_unchanged_is_orphan_object(repo):
    """M1-FLT-026: object 保存後・CAS 前 crash。object は削除しない。"""
    plan = _plan_and_save(repo)  # object は保存済み、ref は未更新
    assert CC.object_exists(repo, plan.planned_oid)

    code, conclusion, failure = CC.conclude(repo, plan, receipt=None, operation_id="op-1")
    assert code == CC.CODE_INDETERMINATE
    assert conclusion == CC.CONCLUSION_ORPHAN_OBJECT
    assert "削除しない" in failure.reason
    assert CC.object_exists(repo, plan.planned_oid), "結論を出しても object は残す"


def test_object_absent_and_ref_unchanged_is_no_effect(repo):
    """M1-FLT-016: object 保存前 crash。副作用 0 を証明できる。"""
    plan = _plan(repo)
    code, conclusion, failure = CC.conclude(repo, plan, receipt=None, operation_id="op-1")
    assert code == CC.CODE_BLOCKED
    assert conclusion == CC.CONCLUSION_ABANDONED_NO_EFFECT
    assert failure is None


def test_third_party_ref_move_is_unresolved(repo):
    plan = _plan(repo)
    (repo / "d.txt").write_text("x\n", encoding="utf-8")
    _git(repo, "add", "d.txt")
    _git(repo, "commit", "-qm", "chore: third party")

    code, conclusion, failure = CC.conclude(repo, plan, receipt=None, operation_id="op-1")
    assert code == CC.CODE_INDETERMINATE
    assert conclusion == CC.CONCLUSION_UNRESOLVED


# --- 誤帰属をしない -------------------------------------------------------------


def test_identical_commit_from_another_run_is_not_attributed(repo):
    """同じ parent / tree / message の commit があっても、自分の成功と見なさない。"""
    plan = _plan(repo)
    # 別の実行が同一内容の commit を作って ref を進めた状況を再現する
    other = subprocess.run(
        ["git", "-C", str(repo), "commit-tree", plan.tree_oid, "-p", plan.old_oid],
        input=MESSAGE.encode("utf-8"), capture_output=True, check=True,
        env={**__import__("os").environ,
             "GIT_AUTHOR_DATE": "2026-01-01T00:00:00+00:00",
             "GIT_COMMITTER_DATE": "2026-01-01T00:00:00+00:00"},
    ).stdout.decode().strip()
    _git(repo, "update-ref", "refs/heads/main", other)

    code, conclusion, failure = CC.conclude(repo, plan, receipt=None, operation_id="op-1")
    assert code == CC.CODE_INDETERMINATE
    assert conclusion == CC.CONCLUSION_UNRESOLVED


def test_no_search_based_success_api_exists():
    """「一致する commit を探して DONE にする」入口を提供しない。"""
    for name in dir(CC):
        assert "search" not in name.lower(), f"検索による成功判定の入口: {name}"
    assert "receipt" in CC.find_matching_commit_is_not_proof()


def test_partial_is_never_produced(repo):
    """単一 ref CAS は原子的で PARTIAL は到達不能。"""
    plan = _plan_and_save(repo)
    receipt, _ = CC.cas_update_ref(repo, plan, operation_id="op-1", fencing_token=7)
    for used_receipt in (receipt, None):
        code, _, _ = CC.conclude(repo, plan, receipt=used_receipt, operation_id="op-1")
        assert code != "PARTIAL"
