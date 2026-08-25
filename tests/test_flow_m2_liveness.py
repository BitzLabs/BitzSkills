"""SI-FLW-086 — worktree 経路の Git child が有限時間で収束することを検証する。

`FLW-REV-027:SYN-003`（P1）。`process.py` は TimeoutBudget・SIGTERM→grace→SIGKILL・
出力上限・Windows job object をすべて実装済みだったが、**worktree 経路はそれを
一切使っていなかった**。`worktree_runtime.py` の全 subprocess 呼び出しが素の
`subprocess.run` で `timeout=` を持たず、hang した Git child は無期限にブロックした。

timeout は「失敗」ではなく「副作用の有無が不明」である。`QUARANTINED`（再観測が
予定 postcondition と不一致＝観測はできた）へ畳まず `INDETERMINATE` へ閉じる
（`FLW-DSN-017` §13.2）。
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / "plugins" / "bitz-flow" / "skills" / "flow-core"
RUNTIME_SOURCE = SKILL / "scripts" / "flowlib" / "worktree_runtime.py"
sys.path.insert(0, str(SKILL / "scripts"))

from flowlib import process as PROC  # noqa: E402
from flowlib import worktree_promotion as P  # noqa: E402
from flowlib import worktree_runtime as WR  # noqa: E402


BUNDLE = "sha256:" + "b" * 64


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(["git", "-C", str(repo), *args],
                          capture_output=True, text=True, check=True)
    return proc.stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """plan() が要求する active contract bundle まで揃えた repository。"""
    path = tmp_path / "repo"
    path.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(path)], check=True)
    _git(path, "config", "user.email", "t@example.com")
    _git(path, "config", "user.name", "t")
    (path / "a.txt").write_text("a\n", encoding="utf-8")
    _git(path, "add", "a.txt")
    _git(path, "commit", "-qm", "chore: init")
    common = Path(_git(path, "rev-parse", "--path-format=absolute", "--git-common-dir"))
    namespace = common / P.PROMOTION_RELATIVE_PATH
    namespace.mkdir(parents=True, mode=0o700)
    namespace.chmod(0o700)
    current = namespace / "current.json"
    current.write_text(json.dumps({
        "contract_version": 2, "generation": "1", "bundle_digest": BUNDLE,
        "runtime_identity_digest": "sha256:" + "a" * 64, "state": "ACTIVE",
    }), encoding="utf-8")
    current.chmod(0o600)
    return path


def _except_body(source: str, exception_name: str) -> str:
    """指定 except 節の本体だけを切り出す（次の except / finally までで止める）。

    固定文字数で切ると隣の except 節まで拾い、検査が意味を失う。
    """
    lines = source.splitlines()
    start = next(
        i for i, line in enumerate(lines)
        if line.strip().startswith("except") and exception_name in line
    )
    indent = len(lines[start]) - len(lines[start].lstrip())
    body = []
    for line in lines[start + 1:]:
        stripped = line.strip()
        if stripped and (len(line) - len(line.lstrip())) <= indent:
            break
        body.append(line)
    return "\n".join(body)


def _source_without_comments() -> str:
    return "\n".join(
        line for line in RUNTIME_SOURCE.read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith("#")
    )


# --- 素の subprocess が残っていないこと --------------------------------------


def test_worktree_runtime_never_spawns_an_unsupervised_child():
    """全 child が `process.run()` の監督下にあること。"""
    source = _source_without_comments()
    assert "subprocess.run(" not in source, (
        "監督されていない child が残っている。hang すると無期限にブロックする"
    )
    assert "subprocess.Popen(" not in source


def test_dead_openssl_verifier_is_gone():
    """呼出元 0 件のまま無制限 openssl child を起動していた死コードが無いこと。"""
    source = RUNTIME_SOURCE.read_text(encoding="utf-8")
    assert "def ed25519_verifier" not in source
    assert "openssl" not in source


# --- hang する child が有限時間で閉じること ----------------------------------


def test_hanging_child_converges_within_the_budget():
    """終了しない child でも budget 内に closed outcome を返すこと。

    `sleep` を Git の代わりに使い、process supervision そのものを検査する。
    無期限ブロックしないことと、実時間が budget + grace の範囲に収まることを見る。
    """
    started = time.monotonic()
    outcome = PROC.run([sys.executable, "-c", "import time; time.sleep(60)"],
                       timeout_seconds=1)
    elapsed = time.monotonic() - started
    assert not outcome.ok
    assert outcome.cause == PROC.CAUSE_TIMEOUT
    # budget 1 秒 + terminate grace 2 秒 に十分な余裕を見た上限。
    assert elapsed < 15, f"収束に {elapsed:.1f} 秒かかった"


def test_child_ignoring_sigterm_is_still_killed():
    """SIGTERM を無視する child も escalate して回収すること。"""
    program = (
        "import signal, time\n"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        "time.sleep(60)\n"
    )
    started = time.monotonic()
    outcome = PROC.run([sys.executable, "-c", program], timeout_seconds=1)
    elapsed = time.monotonic() - started
    assert not outcome.ok
    assert outcome.cause == PROC.CAUSE_TIMEOUT
    assert elapsed < 20, f"SIGKILL への escalate に {elapsed:.1f} 秒かかった"


def test_output_flood_is_bounded():
    """出力上限を超えた child を終了させ closed outcome を返すこと。"""
    program = "import sys\nwhile True: sys.stdout.write('x' * 4096)\n"
    outcome = PROC.run([sys.executable, "-c", program],
                       timeout_seconds=20, output_limit_bytes=256 * 1024)
    assert not outcome.ok
    assert outcome.output_truncated or outcome.cause is not None
    assert len(outcome.stdout) <= 2 * 256 * 1024


# --- budget の伝播 -----------------------------------------------------------


def test_plan_carries_a_finite_budget_for_every_child(repo, allowlisted_root):
    """plan が budget を持ち、apply の child へ伝播すること。

    worktree root は allowlist 済み filesystem 上に要る。`tmp_path` は tmpfs のことが
    あり、tmpfs は durability 保証が成立しないため allowlist 外である
    （`FLW-REV-028:GP-007`）。
    """
    root = allowlisted_root / "wt"
    root.mkdir(mode=0o700)
    plan = WR.plan(repo, action="create", path=root / "w1", branch="feature/x",
                   worktree_root=root, timeout_seconds=12)
    assert plan.timeout_seconds == 12


def test_plan_defaults_to_a_finite_budget(repo, allowlisted_root):
    """budget 未指定でも無期限にしないこと。"""
    root = allowlisted_root / "wt"
    root.mkdir(mode=0o700)
    plan = WR.plan(repo, action="create", path=root / "w1", branch="feature/x",
                   worktree_root=root)
    assert 0 < plan.timeout_seconds <= PROC.READ_TIMEOUT_MAX_SECONDS


@pytest.mark.parametrize("requested", [None, 0, -1, 0.0, 10**9, float("inf")])
def test_budget_is_finite_for_any_requested_value(requested):
    """どんな要求値でも child budget が有限かつ正になること。

    実際の安全性は定数ではなく `normalize_timeout` の丸めが担保する。定数を 0 に
    しても丸めが下限へ寄せるため無期限にはならない — その不変条件を直接検査する。
    """
    for mutating in (False, True):
        budget = PROC.normalize_timeout(requested, mutating=mutating)
        assert budget > 0
        assert budget <= PROC.READ_TIMEOUT_MAX_SECONDS
        assert budget == budget  # NaN でないこと


def test_cli_propagates_timeout_into_the_worktree_path():
    """`--timeout-seconds` が worktree 経路へ渡ること。"""
    source = (SKILL / "scripts" / "flowlib" / "cli.py").read_text(encoding="utf-8")
    marker = source[source.index("plan_value = worktree_runtime.plan("):]
    assert "timeout_seconds=args.timeout_seconds" in marker[:600]


# --- timeout を失敗へ畳まないこと --------------------------------------------


def test_child_timeout_is_distinct_from_a_plain_failure():
    """timeout を `WorktreeRuntimeError` と同一視しないこと。"""
    assert not issubclass(WR.WorktreeChildTimeoutError, WR.WorktreeRuntimeError)
    error = WR.WorktreeChildTimeoutError("git worktree", PROC.CAUSE_TIMEOUT)
    assert error.command == "git worktree"
    assert error.cause == PROC.CAUSE_TIMEOUT


def test_write_timeout_closes_as_indeterminate_not_quarantined():
    """write child の timeout は `INDETERMINATE` へ閉じること。

    `QUARANTINED` は「再観測が予定 postcondition と不一致」であり、観測できた
    ことを含意する。timeout は副作用の有無自体が不明なので畳んではならない。
    """
    body = _except_body(_source_without_comments(), "WorktreeChildTimeoutError")
    assert '"INDETERMINATE"' in body
    assert "result-indeterminate" in body
    assert "quarantined_failure" not in body, (
        "timeout を QUARANTINED へ畳んでいる。副作用の有無が不明なので畳めない"
    )


def test_cli_maps_child_timeout_to_a_closed_result():
    """CLI が timeout を closed result へ写すこと（traceback にしない）。"""
    source = (SKILL / "scripts" / "flowlib" / "cli.py").read_text(encoding="utf-8")
    assert "WorktreeChildTimeoutError" in source
    handler = source[source.index("except worktree_runtime.WorktreeChildTimeoutError as exc:"):]
    assert "INDETERMINATE" in handler[:700]
