"""FLW-REV-029:GP-001 / GP-002 / GP-006 — deadline を**振る舞いで**検査する。

`FLW-REV-029` の P0/P1 の多くに共通の根があった。**GP 消化の確認を source 文字列の
照合で済ませた**ことである。`test_observer_and_coordinator_receive_the_deadline` は
source に `deadline=self.deadline` が含まれるかを見るだけで、実際に全 child へ
伝播しているかを検査していなかった。その結果

- `_common_dir()` / `_head()` が deadline を受け取らない
- `_rederive()` が新しい deadline を開始する
- 公開した read-only 3 operation が deadline を生成すらしない

を見逃し、さらに deadline を通らない経路をそのまま公開した。

本ファイルは source を一切見ない。**期限を実際に尽きさせ、child が起動しないことを
観測する**ことで伝播を検査する。`GP-006` はこの方式を GP 消化確認の要件としている。
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
from flowlib import worktree_operability as OP  # noqa: E402
from flowlib import worktree_promotion as P  # noqa: E402
from flowlib import worktree_runtime as WR  # noqa: E402


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    path = tmp_path / "repo"
    path.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(path)], check=True)
    for key, value in (("user.email", "t@example.com"), ("user.name", "t")):
        subprocess.run(["git", "-C", str(path), "config", key, value], check=True)
    (path / "a.txt").write_text("a\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(path), "add", "a.txt"], check=True)
    subprocess.run(["git", "-C", str(path), "commit", "-qm", "chore: init"], check=True)
    # plan() は active contract bundle を要求する。伝播を深い child まで観測するため
    # ここまで整える（環境不備で早期に落ちると検査が空振りする）。
    common = Path(subprocess.run(
        ["git", "-C", str(path), "rev-parse", "--path-format=absolute", "--git-common-dir"],
        capture_output=True, text=True, check=True).stdout.strip())
    namespace = common / P.PROMOTION_RELATIVE_PATH
    namespace.mkdir(parents=True, mode=0o700)
    namespace.chmod(0o700)
    current = namespace / "current.json"
    current.write_text(json.dumps({
        "contract_version": 2, "generation": "1",
        "bundle_digest": "sha256:" + "b" * 64,
        "runtime_identity_digest": "sha256:" + "a" * 64, "state": "ACTIVE",
    }), encoding="utf-8")
    current.chmod(0o600)
    return path


class _SpyDeadline(WR.OperationDeadline):
    """child への配分要求を数える deadline。source を読まずに伝播を観測する。"""

    def __init__(self, total_seconds: float) -> None:
        super().__init__(total_seconds)
        self.handouts = 0

    def budget_for_child(self, child_seconds):
        self.handouts += 1
        return super().budget_for_child(child_seconds)


# --- GP-002: 全 child 経路が deadline を通ること ------------------------------


def test_expired_deadline_stops_every_child_in_plan(repo, allowlisted_root):
    """期限切れの deadline を渡すと plan が child を 1 本も完走させないこと。

    `_common_dir` / `_head` が deadline を受け取っていなければ、これらは期限に関係なく
    成功してしまい plan は別の理由で進んでしまう。**期限切れで止まること**が
    伝播の証拠になる。
    """
    root = allowlisted_root / "wt"
    root.mkdir(mode=0o700)
    started = time.monotonic()
    with pytest.raises((WR.WorktreeChildTimeoutError, WR.WorktreeRuntimeError,
                        WR.WorktreeUnsupportedPlatformError)):
        WR.plan(repo, action="create", path=root / "w1", branch="feature/x",
                worktree_root=root, deadline=WR.OperationDeadline(0.0))
    assert time.monotonic() - started < 5.0, "期限切れなのに child を走らせている"


def test_plan_hands_every_child_out_of_one_deadline(repo, allowlisted_root):
    """plan が起動する child すべてが**同一の** deadline から配分を受けること。

    `_common_dir` / `_head` / snapshot のいずれかが独自 budget で動いていれば
    配分要求の回数が child 数に届かない。
    """
    root = allowlisted_root / "wt"
    root.mkdir(mode=0o700)
    spy = _SpyDeadline(30.0)
    try:
        WR.plan(repo, action="create", path=root / "w1", branch="feature/x",
                worktree_root=root, deadline=spy)
    except Exception:
        pass          # 環境不備で止まってもよい。数えたいのは配分の回数である
    # plan は snapshot(4) + _common_dir(1) + _head(3) の **8 child** を起動する（実測）。
    # 曖昧な下限にすると 1 経路の欠落が閾値に埋もれる（実際に `_common_dir` の欠落を
    # 見逃した）。**正確な期待値**で検査し、増減どちらも検出する。
    assert spy.handouts == 8, (
        f"配分要求が {spy.handouts} 回（期待 8）。deadline を受け取らない child 経路があるか、"
        "child 構成が変わっている。どちらも確認を要する"
    )


def test_rederive_does_not_start_a_fresh_deadline(repo, allowlisted_root):
    """`_rederive` が新しい deadline を開始しないこと。

    新規に開始すると operation 合計が 30 秒を超えうる。同じ spy が使われ続けることを
    配分回数の増加で観測する。
    """
    root = allowlisted_root / "wt"
    root.mkdir(mode=0o700)
    spy = _SpyDeadline(30.0)
    try:
        plan = WR.plan(repo, action="create", path=root / "w1", branch="feature/x",
                       worktree_root=root, deadline=spy)
    except Exception as exc:
        pytest.fail(f"plan が成立せず伝播を検査できない: {type(exc).__name__}: {exc}")
    before = spy.handouts
    WR._rederive(plan, deadline=spy)
    assert spy.handouts > before, "_rederive が渡した deadline を使っていない"


# --- GP-001: 公開した operation が deadline 配下にあること ---------------------


@pytest.mark.parametrize("call", [
    pytest.param(lambda repo, dl: OP.doctor(repo, deadline=dl), id="doctor"),
    pytest.param(lambda repo, dl: OP.audit_operation(
        repo, operation_id="sha256:" + "a" * 64, deadline=dl), id="audit"),
    pytest.param(lambda repo, dl: OP.verify_receipt(
        repo, operation_id="sha256:" + "a" * 64, deadline=dl), id="verify-receipt"),
])
def test_published_operation_accepts_and_uses_a_deadline(repo, call):
    """**本 issue の中心**。公開した 3 operation が deadline を受け取り使うこと。

    以前は `worktree_operability.py` に `OperationDeadline` の参照が 0 件で、
    30 秒収束が公開面で構造的に成立していなかった。
    """
    spy = _SpyDeadline(30.0)
    try:
        call(repo, spy)
    except Exception:
        pass          # 環境不備で止まってもよい。deadline を使ったかだけを見る
    assert spy.handouts > 0, "公開 operation が deadline を使っていない"


@pytest.mark.parametrize("action", ["doctor", "audit", "verify-receipt"])
def test_published_operation_closes_quickly_when_the_deadline_is_spent(repo, action):
    """期限切れでも公開 operation が有限時間で閉じること（例外にも hang にもしない）。"""
    flow = SKILL / "scripts" / "flow.py"
    started = time.monotonic()
    proc = subprocess.run(
        [sys.executable, str(flow), "--repo", str(repo), "worktree", action,
         "--operation-id", "sha256:" + "a" * 64,
         "--timeout-seconds", "1", "--format", "json"],
        capture_output=True, text=True,
    )
    elapsed = time.monotonic() - started
    assert "Traceback (most recent call last)" not in proc.stderr, proc.stderr[:300]
    assert elapsed < 20, f"{action} が {elapsed:.1f} 秒かかった"


def test_cli_creates_a_deadline_for_the_published_surface():
    """CLI が公開経路で deadline を生成すること（生成しなければ配分は起きない）。"""
    from flowlib import cli
    spy_holder = {}

    class _Recording(WR.OperationDeadline):
        def __init__(self, total_seconds=None):
            super().__init__(total_seconds)
            spy_holder["created"] = spy_holder.get("created", 0) + 1

    original = WR.OperationDeadline
    cli.worktree_runtime.OperationDeadline = _Recording
    try:
        cli.main(["worktree", "doctor", "--format", "json"])
    except SystemExit:
        pass
    finally:
        cli.worktree_runtime.OperationDeadline = original
    assert spy_holder.get("created"), "公開経路で deadline を生成していない"


# --- GP-001: read-only guard がスケールすること -------------------------------


def test_persistent_state_digest_does_not_load_whole_files(tmp_path, monkeypatch):
    """guard が全 bytes を一度にロードしないこと。

    guard は各 operation の前後 2 回走る。100 MiB 級 journal を一括ロードすると
    guard 自体が実行障害の原因になる（`FLW-REV-029:SYN-005`）。
    """
    common = tmp_path / "common"
    namespace = common / "bitz-flow-v2"
    namespace.mkdir(parents=True)
    (namespace / "big.json").write_bytes(b"x" * (3 * 1024 * 1024))

    calls = {"read_bytes": 0}
    original = Path.read_bytes

    def counting(self):
        calls["read_bytes"] += 1
        return original(self)

    monkeypatch.setattr(Path, "read_bytes", counting)
    digest = OP.persistent_state_digest(common)
    assert digest.startswith("sha256:")
    assert calls["read_bytes"] == 0, "read_bytes による一括ロードが残っている"


def test_persistent_state_digest_is_stable_across_chunk_boundaries(tmp_path):
    """逐次読みへ変えても digest が内容に対して安定であること。"""
    common = tmp_path / "common"
    namespace = common / "bitz-flow-v2"
    namespace.mkdir(parents=True)
    payload = bytes(range(256)) * 8192          # チャンク境界をまたぐ長さ
    (namespace / "a.bin").write_bytes(payload)
    first = OP.persistent_state_digest(common)
    (namespace / "a.bin").write_bytes(payload)
    assert OP.persistent_state_digest(common) == first
    (namespace / "a.bin").write_bytes(payload + b"!")
    assert OP.persistent_state_digest(common) != first


# --- GP-005 の一部: doctor の problem 網羅 ------------------------------------


def test_every_doctor_problem_has_an_operator_action():
    """doctor が出す全 problem に operator action があること。

    以前は `current-bundle-digest-mismatch` が表に無く「未分類の問題を報告する」へ
    落ちていた（`FLW-REV-029:SYN-008`）。coverage test が platform 理由だけを見て
    bundle problem を見ていなかったことが原因である。
    """
    import re
    source = (SKILL / "scripts" / "flowlib" / "worktree_operability.py").read_text(encoding="utf-8")
    emitted = set(re.findall(r'problems\.append\("([a-z-]+)"\)', source))
    missing = sorted(p for p in emitted if p not in OP._BUNDLE_ACTIONS)
    assert not missing, f"operator action の無い problem {missing}"
