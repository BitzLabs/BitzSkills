"""FLW-REV-029:GP-005 — 判定 API が名前どおりの判定をすることを検証する。

`SYN-006` は 2 つを指摘した。片方は実測で**再現しなかった**。

- **audit の code と operator action の矛盾（再現した）**: `audit_operation` は
  `INDETERMINATE` 以外をすべて `OK` にし、その全部に `create-reconcile-plan` を促していた。
  `confirmed-complete`（何もしなくてよい）にも reconcile を促し、`quarantine` と
  `confirmed-incomplete`（復旧を要する）を `OK` と表示していた。**運用者は隔離された
  操作を正常と誤認する。**
- **`verify_receipt` が receipts を見ていない（再現しなかった）**: `transaction.inspect()`
  が receipt chain を検証して `problems` へ畳み込んでおり、`healthy` はその結果である。
  下の陽性対照が示すとおり receipt を削除・破損させれば判定は実際に反転する。
  指摘は source の見た目に基づくもので、振る舞いとしては成立していなかった。
  ここに陽性対照を置いて**再現しないことを証跡として固定する**。

`SYN-007` は dispatcher の網が例外を一律 `UNAVAILABLE` へ変換し、種別も発生箇所も
残さなかったこと。実際にこの網が `FLW-TSK-116`／`117` の handler 欠陥
（`recovery_class` 欠落による ValueError）を隠していた。

`GP-006` に従い、source 文字列の照合ではなく**実際に壊して振る舞いを見る**。
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "plugins" / "bitz-flow" / "skills" / "flow-core"
sys.path.insert(0, str(SKILL / "scripts"))

from flowlib import cli  # noqa: E402
from flowlib import worktree_operability as OP  # noqa: E402
from flowlib import worktree_recovery as RC  # noqa: E402
from flowlib import worktree_runtime as R  # noqa: E402
from flowlib import worktree_transaction as T  # noqa: E402

DIGEST = "sha256:" + "a" * 64
EFFECTS = "sha256:" + "b" * 64


def _snapshot(suffix: str) -> R.RepositorySnapshot:
    return R.RepositorySnapshot(
        suffix * 40, "sha256:" + suffix * 64, "sha256:" + suffix * 64,
        "sha256:" + suffix * 64,
    )


def _transaction(tmp_path: Path, *, terminal_state: str | None) -> T.TargetTransaction:
    """1 operation を実際に進める。`terminal_state` が None なら MUTATING で止める。"""
    root = tmp_path / "authority"
    root.mkdir(mode=0o700)
    tx = T.TargetTransaction(root, target_collision_key="target-1")
    lease = tx.acquire(operation_id=DIGEST, nonce="judgement-nonce")
    tx.prepare_intent(lease, planned_effects_digest=EFFECTS,
                      precondition_digest=_snapshot("1").digest)
    tx.mark_mutating(lease)
    if terminal_state is not None:
        tx.publish_result(lease, terminal_state=terminal_state,
                          postcondition_digest=_snapshot("2").digest)
    tx.release(lease)
    return tx


def _receipt_files(tx: T.TargetTransaction) -> list[Path]:
    return sorted(Path(tx.root).glob("receipts/*/*.json"))


def _chain_is_valid(tx: T.TargetTransaction) -> bool:
    """`verify_receipt` が `OK` を返す条件そのもの。"""
    report = tx.inspect(DIGEST)
    return report.healthy and bool(report.events)


# --- SYN-006(a): receipt を壊すと判定が反転すること（再現しない、の陽性対照）------


def test_intact_chain_is_valid(tmp_path):
    """陰性対照。健全な chain を誤って無効にしないこと。"""
    tx = _transaction(tmp_path, terminal_state="DONE")
    assert _chain_is_valid(tx)
    assert len(_receipt_files(tx)) == 1, "terminal receipt が file として存在すること"


def test_deleting_the_terminal_receipt_invalidates_the_chain(tmp_path):
    """**陽性対照**。receipt を消せば判定が反転すること。

    これが成り立つ限り「`verify_receipt` は receipts を見ていない」は振る舞いとしては
    成立しない。判定は `inspect()` が receipt chain を検証した結果に依存している。
    """
    tx = _transaction(tmp_path, terminal_state="DONE")
    for path in _receipt_files(tx):
        path.unlink()
    assert not _chain_is_valid(tx), "receipt を消しても有効と判定している"
    assert tx.inspect(DIGEST).state == "INDETERMINATE"


def test_corrupting_the_terminal_receipt_invalidates_the_chain(tmp_path):
    """**陽性対照**。receipt を壊せば判定が反転すること。"""
    tx = _transaction(tmp_path, terminal_state="DONE")
    for path in _receipt_files(tx):
        path.write_text("{}", encoding="utf-8")
    assert not _chain_is_valid(tx), "receipt を壊しても有効と判定している"


def test_removing_the_embedded_emergency_receipt_invalidates_the_chain(tmp_path):
    """緊急 receipt は intent record へ同梱される。外せば判定が反転すること。"""
    tx = _transaction(tmp_path, terminal_state=None)
    assert _chain_is_valid(tx)
    for path in sorted(Path(tx.root).glob("events/*/*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        if T.EMERGENCY_RECEIPT_FIELD in record:
            del record[T.EMERGENCY_RECEIPT_FIELD]
            path.write_text(json.dumps(record), encoding="utf-8")
    assert not _chain_is_valid(tx), "緊急 receipt を外しても有効と判定している"


def test_receipt_count_is_exposed_to_the_operator(tmp_path):
    """何件の receipt を読んだかが判ること（判定の根拠を運用者へ示す）。"""
    tx = _transaction(tmp_path, terminal_state="DONE")
    report = tx.inspect(DIGEST)
    assert len(report.receipts) == 2, "同梱の緊急 receipt と terminal receipt の 2 件"


# --- SYN-006(b): audit の code と operator action が矛盾しないこと --------------


@pytest.mark.parametrize("classification", sorted(OP._AUDIT_ACTIONS))
def test_audit_code_and_operator_action_agree(classification):
    """復旧を要する分類を `OK` にせず、不要な分類に reconcile を促さないこと。

    旧実装は `INDETERMINATE` 以外の**全部**に `create-reconcile-plan` を促しながら
    `OK` を返していた。両方向とも誤っていた。
    """
    needs_recovery = classification in OP._CLASSIFICATIONS_NEEDING_RECOVERY
    action = OP._AUDIT_ACTIONS[classification]
    if needs_recovery:
        assert action != "none", f"{classification}: 復旧が要るのに action が none"
    else:
        assert action == "none", f"{classification}: 復旧不要なのに reconcile を促している"


def test_only_confirmed_complete_is_treated_as_ok():
    """`OK` になるのは `confirmed-complete` だけであること。"""
    ok = set(OP._AUDIT_ACTIONS) - OP._CLASSIFICATIONS_NEEDING_RECOVERY
    assert ok == {RC.CONFIRMED_COMPLETE}, f"OK 扱いの分類が広すぎる: {sorted(ok)}"


def test_every_recovery_classification_has_an_action():
    """recovery が定義する全分類に action があること（新分類の取りこぼし防止）。"""
    known = {RC.CONFIRMED_COMPLETE, RC.CONFIRMED_INCOMPLETE, RC.INDETERMINATE, RC.QUARANTINE}
    assert set(OP._AUDIT_ACTIONS) == known


def test_quarantined_operation_is_not_reported_as_ok(tmp_path, monkeypatch):
    """**本 issue の中心**。隔離された操作を `OK` と表示しないこと（実経路）。"""
    tx = _transaction(tmp_path, terminal_state="QUARANTINED")
    report = RC.audit(tx, operation_id=DIGEST, observed_snapshot=_snapshot("2"))
    assert report.classification == RC.QUARANTINE
    needs_recovery = report.classification in OP._CLASSIFICATIONS_NEEDING_RECOVERY
    assert needs_recovery, "隔離を復旧不要としている"
    assert OP._AUDIT_ACTIONS[report.classification] == "create-reconcile-plan"


def test_completed_operation_is_not_asked_to_reconcile(tmp_path):
    """正常完了した操作へ reconcile を促さないこと（実経路。旧実装はこれを促していた）。"""
    tx = _transaction(tmp_path, terminal_state="DONE")
    report = RC.audit(tx, operation_id=DIGEST, observed_snapshot=_snapshot("2"))
    assert report.classification == RC.CONFIRMED_COMPLETE
    assert OP._AUDIT_ACTIONS[report.classification] == "none"


# --- SYN-007: 内部障害が観測できること ---------------------------------------


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
    return path


def test_unexpected_failure_is_recorded_for_developers(repo, monkeypatch, capsys):
    """網が受け止めた例外の種別と発生箇所が内部向けに残ること。

    以前は一律 `UNAVAILABLE` へ変換して何も残さず、実際にこの網が handler 欠陥を
    隠していた。
    """
    def exploding(root, args, started):
        raise KeyError("injected internal defect")

    monkeypatch.setitem(cli._HANDLERS, ("repo", "inspect"), exploding)
    cli.LAST_UNEXPECTED_FAILURE = None
    cli.main(["repo", "inspect", "--repo", str(repo), "--format", "json"])
    capsys.readouterr()

    record = cli.LAST_UNEXPECTED_FAILURE
    assert record, "内部記録が残っていない"
    assert record["exception_type"] == "KeyError"
    assert record["operation"] == "repo.inspect"
    assert record["origin_file"], "発生箇所が判らない"


def test_internal_record_never_reaches_the_public_result(repo, monkeypatch, capsys):
    """内部記録が公開 result へ漏れないこと（利用者への秘匿は維持する）。"""
    def exploding(root, args, started):
        raise KeyError("secret detail /home/someone/private")

    monkeypatch.setitem(cli._HANDLERS, ("repo", "inspect"), exploding)
    cli.main(["repo", "inspect", "--repo", str(repo), "--format", "json"])
    payload = capsys.readouterr().out
    assert payload
    for leaked in ("KeyError", "secret detail", "/home/someone", "Traceback"):
        assert leaked not in payload, f"内部情報が公開 result へ漏れている: {leaked}"


def test_internal_log_file_is_opt_in(repo, monkeypatch, tmp_path, capsys):
    """記録 file は明示的に有効化したときだけ作られること。"""
    def exploding(root, args, started):
        raise KeyError("injected")

    monkeypatch.setitem(cli._HANDLERS, ("repo", "inspect"), exploding)
    monkeypatch.delenv(cli.UNEXPECTED_LOG_ENV, raising=False)
    cli.main(["repo", "inspect", "--repo", str(repo), "--format", "json"])
    capsys.readouterr()
    assert not list(tmp_path.glob("*.jsonl")), "既定で log file を作っている"

    target = tmp_path / "internal.jsonl"
    monkeypatch.setenv(cli.UNEXPECTED_LOG_ENV, str(target))
    cli.main(["repo", "inspect", "--repo", str(repo), "--format", "json"])
    capsys.readouterr()
    assert target.exists()
    record = json.loads(target.read_text(encoding="utf-8").splitlines()[-1])
    assert record["exception_type"] == "KeyError"


def test_recording_failure_does_not_break_the_operation(repo, monkeypatch, capsys):
    """記録に失敗しても closed result を返し続けること。"""
    def exploding(root, args, started):
        raise KeyError("injected")

    monkeypatch.setitem(cli._HANDLERS, ("repo", "inspect"), exploding)
    monkeypatch.setenv(cli.UNEXPECTED_LOG_ENV, "/proc/nonexistent/cannot-write.jsonl")
    code = cli.main(["repo", "inspect", "--repo", str(repo), "--format", "json"])
    payload = json.loads(capsys.readouterr().out)
    assert code != 0
    assert payload["code"] == "UNAVAILABLE"


def test_published_operation_records_internal_failures_too(repo, monkeypatch, capsys):
    """公開した worktree 経路でも内部記録が働くこと。"""
    def exploding(root, args, started):
        raise RuntimeError("injected")

    monkeypatch.setitem(cli._HANDLERS, ("worktree", "doctor"), exploding)
    cli.LAST_UNEXPECTED_FAILURE = None
    cli.main(["worktree", "doctor", "--repo", str(repo), "--format", "json"])
    capsys.readouterr()
    assert cli.LAST_UNEXPECTED_FAILURE
    assert cli.LAST_UNEXPECTED_FAILURE["operation"] == "worktree.doctor"
