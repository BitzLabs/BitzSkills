"""FLW-REV-028:GP-002 — operation 全体 deadline と snapshot 出力上限を検証する。

`SYN-011`: `_supervised_git` は child 単位の budget しか持たず、1 operation は
`snapshot()`（4 child）を plan / apply / post で複数回回すため 15〜20 child を起動する。
child 毎 30 秒なら最悪 450 秒超であり、`FLW-NFR-014` が要求する 30 秒 terminal result は
成立しなかった。

`SYN-002`: snapshot 経路が既定の child 出力上限（8 MiB）を流用しており、未追跡ファイルの
多い repository で plan 自体が失敗しうる。設計値として分離していなかった。

あわせて 10,000 event 規模の journal で chain 検査の収束を実測する。
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "plugins" / "bitz-flow" / "skills" / "flow-core"
sys.path.insert(0, str(SKILL / "scripts"))

from flowlib import process as PROC  # noqa: E402
from flowlib import worktree_runtime as WR  # noqa: E402
from flowlib import worktree_transaction as T  # noqa: E402
from flowlib.worktree_contract import canonical_json_bytes, sha256_digest  # noqa: E402


# --- operation 全体 deadline --------------------------------------------------


def test_deadline_never_hands_a_child_more_than_the_remaining_time():
    """**本 issue の中心**。child へ残り時間を超える budget を配らないこと。"""
    deadline = WR.OperationDeadline(5.0)
    assert deadline.budget_for_child(30.0) <= 5.0
    assert deadline.budget_for_child(None) <= 5.0


def test_sequential_children_exhaust_the_deadline_instead_of_each_getting_the_full_budget():
    """child は逐次実行されるため、時間の経過とともに配分が縮み最後は 0 になること。

    child 単位の budget だけだと 15〜20 child が各 30 秒を消費でき、合計 450 秒超に
    なりうる。ここで検査するのは「各 child は**残り時間**しかもらえない」という性質で
    ある（同時起動しないので単純な総和ではない）。
    """
    deadline = WR.OperationDeadline(0.3)
    allocations = []
    for _ in range(5):
        allocations.append(deadline.budget_for_child(30.0))
        time.sleep(0.1)
    assert allocations == sorted(allocations, reverse=True), f"配分が縮んでいない {allocations}"
    assert allocations[0] <= 0.3, "初回から残り時間を超えて配っている"
    assert allocations[-1] == 0.0, f"尽きても配っている {allocations[-1]}"
    assert deadline.expired()


def test_expired_deadline_does_not_spawn_a_child(tmp_path):
    """残りが尽きたら child を起動せず timeout として返すこと。"""
    started = time.monotonic()
    outcome = WR._supervised_git(
        ("rev-parse", "HEAD"), cwd=tmp_path, deadline=WR.OperationDeadline(0.0),
    )
    assert not outcome.ok
    assert outcome.cause == PROC.CAUSE_TIMEOUT
    assert outcome.exit_category == "operation-deadline"
    assert time.monotonic() - started < 1.0, "child を起動している"


def test_operation_deadline_default_matches_the_terminal_result_requirement():
    """既定 deadline が `FLW-NFR-014` の 30 秒要求と一致すること。"""
    assert WR.DEFAULT_OPERATION_DEADLINE_SECONDS == 30.0
    assert WR.OperationDeadline().total_seconds == 30.0


def test_observer_and_coordinator_receive_the_deadline():
    """snapshot と write child の双方が deadline の配下に入ること。"""
    source = (SKILL / "scripts" / "flowlib" / "worktree_runtime.py").read_text(encoding="utf-8")
    observer = source[source.index("class RepositoryObserver:"):]
    assert "deadline=self.deadline" in observer[:observer.index("def snapshot")]
    coordinator = source[source.index("def run_git("):]
    assert "deadline=self.deadline" in coordinator[:600]


# --- snapshot 出力上限 --------------------------------------------------------


def test_snapshot_limit_is_a_design_value_not_the_child_default():
    """snapshot の出力上限が既定値の流用でないこと。"""
    assert WR.SNAPSHOT_OUTPUT_LIMIT_BYTES != PROC.DEFAULT_OUTPUT_LIMIT_BYTES
    assert WR.SNAPSHOT_OUTPUT_LIMIT_BYTES > PROC.DEFAULT_OUTPUT_LIMIT_BYTES


def test_snapshot_path_passes_the_dedicated_limit():
    """snapshot 経路が専用上限を渡していること（既定へ戻っていないこと）。"""
    source = (SKILL / "scripts" / "flowlib" / "worktree_runtime.py").read_text(encoding="utf-8")
    body = source[source.index("class RepositoryObserver:"):]
    body = body[:body.index("def snapshot")]
    assert "SNAPSHOT_OUTPUT_LIMIT_BYTES" in body


def test_untracked_flood_stays_within_the_snapshot_limit(tmp_path):
    """未追跡ファイルが多い repository でも snapshot が閉じること。

    8 MiB（既定）は porcelain=v2 の未追跡行で約 13 万件に相当する。ここでは規模を
    落として、上限が実際に効く経路であることと closed outcome になることを確かめる。
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    for key, value in (("user.email", "t@example.com"), ("user.name", "t")):
        subprocess.run(["git", "-C", str(repo), "config", key, value], check=True)
    (repo / "a.txt").write_text("a\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "a.txt"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "init"], check=True)
    flood = repo / "untracked"
    flood.mkdir()
    for index in range(2000):
        (flood / f"file-{index:06d}-{'x' * 40}.tmp").write_text("x", encoding="utf-8")

    observer = WR.RepositoryObserver(repo, deadline=WR.OperationDeadline(30.0))
    snapshot = observer.snapshot()
    assert snapshot.digest.startswith("sha256:")


# --- 負荷条件での収束（10,000 event） ----------------------------------------


def _forge_journal(root: Path, operation_id: str, target_key: str, count: int) -> None:
    """chain 検査の負荷を測るため journal を直接生成する。

    API 経由だと 1 event ごとに 4 段階の atomic publish（fsync 含む）が走り、
    10,000 件の生成自体に時間がかかって**測りたいもの（chain 検査）を測れない**。
    """
    events = root / "events" / operation_id[7:]
    events.mkdir(parents=True, exist_ok=True)
    head = None
    for sequence in range(count):
        record = {
            "event": {
                "contract_version": 2, "operation_id": operation_id,
                "target_collision_key": target_key, "sequence": str(sequence),
                "previous_event_digest": head, "state": "LOCKED",
                "fencing_token": "1",
            },
            "intent": None, "result": None, "receipt_digest": None,
        }
        digest = sha256_digest(canonical_json_bytes(record))
        (events / f"{sequence:020d}-{digest[7:]}.json").write_text(
            json.dumps(record, ensure_ascii=False), encoding="utf-8")
        head = digest


@pytest.mark.parametrize("count", [10_000])
def test_chain_inspection_converges_under_load(tmp_path, count):
    """10,000 event 規模でも chain 検査が terminal result 要求内に収束すること。

    chain 検査は全 event を読むため、journal が大きくなると収束時間が伸びる。
    `FLW-NFR-014` の 30 秒要求に対する余裕を実測する。
    """
    root = tmp_path / "tx"
    root.mkdir(mode=0o700)
    operation_id = "sha256:" + "a" * 64
    target_key = "sha256:" + "b" * 64
    _forge_journal(root, operation_id, target_key, count)

    transaction = T.TargetTransaction(root, target_collision_key=target_key)
    started = time.monotonic()
    report = transaction.inspect(operation_id)
    elapsed = time.monotonic() - started

    assert len(report.events) == count, report.problems[:3]
    assert elapsed < WR.DEFAULT_OPERATION_DEADLINE_SECONDS, (
        f"{count} event の chain 検査に {elapsed:.2f} 秒かかった"
        f"（operation deadline {WR.DEFAULT_OPERATION_DEADLINE_SECONDS} 秒）"
    )
    print(f"\n[load] {count} events -> inspect {elapsed:.3f}s")
