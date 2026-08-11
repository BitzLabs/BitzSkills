"""M1-4 の出口判定 — operation catalog の M1 contract 全行を実装と突合する。

catalog（人間向け）と実装（機械可読）が食い違うと、読み手は catalog を信じて誤った前提で
呼び出す。ここで**片方だけの変更を落とす**ようにしておく。

公開面の非退行も併せて固定する。M2 未完了の間は Git write を公開しない
（`FLW-DSN-014` 縮退規則3）。
"""

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / "plugins" / "bitz-flow" / "skills" / "flow-core"
FLOW = SKILL / "scripts" / "flow.py"
CATALOG = SKILL / "references" / "operation-catalog.md"
sys.path.insert(0, str(SKILL / "scripts"))

from flowlib import cli  # noqa: E402
from flowlib import commit_causality as CC  # noqa: E402
from flowlib import doctor as DOC  # noqa: E402
from flowlib import git_publish as PUB  # noqa: E402
from flowlib import git_sync as SYNC  # noqa: E402
from flowlib import git_write as WR  # noqa: E402
from flowlib import guard as GD  # noqa: E402
from flowlib import recovery as RC  # noqa: E402

M0_OPERATIONS = {"repo.inspect", "git.status", "git.diff-summary"}
M0_REACHABLE_CODES = {"OK", "INVALID_INPUT", "BLOCKED", "UNAVAILABLE", "STALE", "UNSUPPORTED"}

#: catalog の「class / approval / retry / concurrency_key」表（M1 節）から読む行。
_ROW = re.compile(
    r"^\|\s*`(?P<operation>[a-z][a-z0-9.-]+)`\s*\|\s*`(?P<klass>[a-z-]+)`\s*\|"
    r"\s*`(?P<approval>[a-z-]+)`\s*\|\s*`(?P<retry>[a-z-]+)`\s*\|"
    r"\s*(?P<concurrency>[^|]+)\|"
)


def _catalog_rows() -> dict[str, dict[str, str]]:
    rows: dict[str, dict[str, str]] = {}
    for line in CATALOG.read_text(encoding="utf-8").splitlines():
        match = _ROW.match(line)
        if match:
            rows[match.group("operation")] = {
                "class": match.group("klass"),
                "approval": match.group("approval"),
                "retry": match.group("retry"),
                "concurrency_key": match.group("concurrency").strip(),
            }
    return rows


@pytest.fixture(scope="module")
def rows():
    parsed = _catalog_rows()
    assert parsed, "catalog の M1 表を読めていない"
    return parsed


@pytest.fixture(scope="module")
def repo(tmp_path_factory):
    path = tmp_path_factory.mktemp("m1-contract")
    subprocess.run(["git", "init", "-q", "-b", "main", str(path)], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "t@example.com"], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "t"], check=True)
    (path / "a.txt").write_text("x\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(path), "add", "a.txt"], check=True)
    subprocess.run(["git", "-C", str(path), "commit", "-qm", "chore: init"], check=True)
    return path


# === catalog と実装の突合 =====================================================


def test_catalog_covers_all_m1_operations(rows):
    expected = {
        "git.diff-detail", "git.log", "git.branches", "git.conflicts", "worktree.list",
        "repo.doctor", "git.fetch", "git.stage", "git.commit", "git.sync",
        "git.publish-branch", "git.delete-remote-branch",
    }
    assert expected <= set(rows), f"catalog に無い operation: {sorted(expected - set(rows))}"
    assert len(rows) == 12


def test_read_operations_are_declared_read(rows):
    for operation in ("git.diff-detail", "git.log", "git.branches", "git.conflicts",
                      "worktree.list", "repo.doctor"):
        assert rows[operation]["class"] == "read"
        assert rows[operation]["approval"] == "none"
        assert rows[operation]["retry"] == "safe"


def test_local_write_operations_are_declared_local_write(rows):
    for operation in ("git.fetch", "git.stage", "git.commit", "git.sync"):
        assert rows[operation]["class"] == "local-write"
        assert rows[operation]["approval"] == "mutation"
        assert rows[operation]["retry"] == "reconcile-first"


def test_remote_write_and_destructive_require_explicit_human(rows):
    assert rows["git.publish-branch"]["class"] == "remote-write"
    assert rows["git.delete-remote-branch"]["class"] == "destructive"
    for operation in ("git.publish-branch", "git.delete-remote-branch"):
        assert rows[operation]["approval"] == "explicit-human"
        assert rows[operation]["retry"] == "manual-only"


def test_implementation_agrees_with_declared_approval(rows):
    """explicit-human と宣言した operation は、承認なしで実行できない。"""
    assert PUB.APPROVAL_EXPLICIT_HUMAN == rows["git.publish-branch"]["approval"]
    assert PUB.APPROVAL_EXPLICIT_HUMAN == rows["git.delete-remote-branch"]["approval"]


def test_recovery_module_knows_the_same_operation_set(rows):
    known = set(RC.READ_OPERATIONS) | set(RC.WRITE_OPERATIONS)
    assert set(rows) <= known, f"recovery が知らない operation: {sorted(set(rows) - known)}"


def test_doctor_knows_the_same_operation_set(rows):
    assert set(rows) <= set(DOC.OPERATION_CAPABILITIES)


def test_declared_recovery_ids_exist_in_implementation():
    catalog = CATALOG.read_text(encoding="utf-8")
    for recovery_id in ("REC-FETCH", "REC-STAGE", "REC-COMMIT", "REC-SYNC", "REC-PUSH"):
        assert recovery_id in catalog
    assert SYNC.REC_FETCH == "REC-FETCH"
    assert SYNC.REC_SYNC == "REC-SYNC"
    assert PUB.REC_PUSH == "REC-PUSH"


def test_read_operations_declare_no_concurrency_key(rows):
    """read は直列化キーを持たない（持つと不要な待ちが生まれる）。"""
    for operation in ("git.diff-detail", "git.log", "git.branches", "git.conflicts",
                      "worktree.list", "repo.doctor"):
        assert rows[operation]["concurrency_key"] == "`null`"


def test_write_operations_declare_a_concurrency_key(rows):
    """write は必ず直列化キーを持つ（無いと同時 mutation を止められない）。"""
    for operation in ("git.fetch", "git.stage", "git.commit", "git.sync",
                      "git.publish-branch", "git.delete-remote-branch"):
        key = rows[operation]["concurrency_key"]
        assert key and key != "`null`", f"{operation} に concurrency_key が無い"


def test_guard_identity_vocabulary_is_documented():
    """guard identity の閉集合は output-contract.md 側に記載する（catalog は operation 別記述）。"""
    contract = (SKILL / "references" / "output-contract.md").read_text(encoding="utf-8")
    for kind in GD.GUARD_IDENTITY_KINDS:
        assert kind in contract


# === 禁止事項を提示しない =====================================================


FORBIDDEN = ("reset --hard", "force push", "clean -f", "rebase", "stash", "passthrough")


def test_catalog_declares_forbidden_operations():
    text = CATALOG.read_text(encoding="utf-8")
    assert "明示的な非対応" in text
    for token in ("reset", "clean", "force push", "rebase", "stash"):
        assert token in text


def test_no_module_exposes_forbidden_entry_points():
    for module in (WR, CC, SYNC, PUB):
        for name in dir(module):
            if name.startswith("_"):
                continue
            lowered = name.lower()
            for banned in ("force", "reset", "rebase", "stash", "clean"):
                assert banned not in lowered, f"{module.__name__}.{name}"


def test_recovery_never_proposes_forbidden_operations():
    for rule in RC.MATRIX:
        for action in rule.allowed_next:
            for banned in FORBIDDEN:
                assert banned not in action


# === 重複 commit 0 =============================================================


def test_same_plan_does_not_create_two_commits(repo):
    """同じ plan から二重に ref を進めない。"""
    (repo / "b.txt").write_text("b\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "b.txt"], check=True)
    plan, failure = CC.plan_commit(repo, message="feat: dup check\n", ref="refs/heads/main")
    assert failure is None
    CC.save_object(repo, plan)

    first, failure = CC.cas_update_ref(repo, plan, operation_id="op-1", fencing_token=1)
    assert failure is None
    second, failure = CC.cas_update_ref(repo, plan, operation_id="op-1", fencing_token=1)
    assert second is None, "同じ plan の二度目の CAS が成立してはならない"
    assert failure.code == CC.CODE_STALE

    count = subprocess.run(
        ["git", "-C", str(repo), "rev-list", "--count", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert count == "2", "commit が重複していない"


def test_stage_plan_applied_twice_is_stale(repo):
    common = repo / ".git"
    (repo / "c.txt").write_text("c\n", encoding="utf-8")
    plan, _ = WR.plan_stage(repo, common, ["c.txt"])
    digest, failure = WR.apply_stage(common, plan)
    assert failure is None

    again, failure = WR.apply_stage(common, plan)
    assert again is None
    assert failure.code == WR.CODE_STALE


# === 公開面の非退行 ============================================================


def _flow_json(*args, repo):
    proc = subprocess.run(
        [sys.executable, str(FLOW), "--repo", str(repo), *args, "--format", "json"],
        capture_output=True, text=True,
    )
    return json.loads(proc.stdout), proc.returncode


def test_dispatcher_still_exposes_only_m0(rows):
    exposed = {f"{domain}.{action}" for domain, action in cli._HANDLERS}
    assert exposed == M0_OPERATIONS
    assert not (exposed & set(rows)), "M1 operation を公開してはならない"


@pytest.mark.parametrize(
    "operation",
    ["git.diff-detail", "git.log", "git.branches", "git.conflicts", "worktree.list",
     "repo.doctor", "git.fetch", "git.stage", "git.commit", "git.sync",
     "git.publish-branch", "git.delete-remote-branch"],
)
def test_m1_operations_return_unsupported(operation, repo):
    domain, action = operation.split(".")
    result, exit_code = _flow_json(domain, action, repo=repo)
    assert result["code"] == "UNSUPPORTED"
    assert exit_code == 8
    assert result["data"]["effects"] == []


def test_reachable_codes_are_still_m0_only(repo):
    seen = set()
    for args in (("repo", "inspect"), ("git", "status"), ("git", "diff-summary"),
                 ("git", "commit"), ("git", "publish-branch"), ("repo", "doctor")):
        result, _ = _flow_json(*args, repo=repo)
        seen.add(result["code"])
    assert seen <= M0_REACHABLE_CODES


def test_unsupported_does_not_propose_raw_commands(repo):
    proc = subprocess.run(
        [sys.executable, str(FLOW), "--repo", str(repo), "git", "publish-branch"],
        capture_output=True, text=True,
    )
    text = proc.stdout + proc.stderr
    for banned in ("git push", "git commit", "gh pr", "$ "):
        assert banned not in text
