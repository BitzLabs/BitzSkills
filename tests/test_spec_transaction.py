"""SDD-FR-143 workspace mutation transaction tests."""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

MODULE = (
    Path(__file__).resolve().parent.parent
    / "plugins" / "bitz-sdd" / "skills" / "sdd-core" / "scripts" / "spec_transaction.py"
)
spec = importlib.util.spec_from_file_location("spec_transaction", MODULE)
tx = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = tx
spec.loader.exec_module(tx)


def _workspace(tmp_path):
    (tmp_path / ".spec").mkdir()
    return tmp_path


def _mark_lock_owner_dead(root):
    lock = root / ".spec" / ".mutation-lock"
    owner = json.loads(lock.read_text(encoding="utf-8"))
    owner["pid"] = 999_999_999
    owner["process_start"] = ""
    lock.write_text(
        json.dumps(owner, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )


def test_SDD_FR_143_mutate_updates_multiple_files_and_cleans_metadata(tmp_path):
    root = _workspace(tmp_path)
    first = root / ".spec" / "requirements" / "REQ.md"
    second = root / ".spec" / "STATE.md"
    first.parent.mkdir()
    first.write_bytes(b"old requirement\n")
    second.write_bytes(b"old state\n")

    def prepare(_owner):
        return tx.TransactionPlan(
            changes=(
                tx.FileChange(first, b"old requirement\n", b"new requirement\n"),
                tx.FileChange(second, b"old state\n", b"new state\n"),
            ),
            metadata={"kind": "update"},
        )

    tx.mutate(root, "test", (first, second), prepare)
    assert first.read_bytes() == b"new requirement\n"
    assert second.read_bytes() == b"new state\n"
    assert not (root / ".spec" / ".mutation-lock").exists()
    assert not list((root / ".spec" / ".transactions").glob("*.json"))


def test_SDD_FR_143_precondition_failure_releases_lock(tmp_path):
    root = _workspace(tmp_path)
    target = root / ".spec" / "STATE.md"

    def prepare(_owner):
        raise tx.MutationError("precondition-failed", "no", 4)

    with pytest.raises(tx.MutationError, match="no"):
        tx.mutate(root, "test", (target,), prepare)
    assert not (root / ".spec" / ".mutation-lock").exists()


def test_SDD_FR_143_cas_failure_keeps_journal_for_recovery(tmp_path):
    root = _workspace(tmp_path)
    target = root / ".spec" / "STATE.md"
    target.write_bytes(b"before")

    def prepare(_owner):
        return tx.TransactionPlan(
            changes=(tx.FileChange(target, b"different", b"after"),),
            metadata={},
        )

    with pytest.raises(tx.MutationError) as error:
        tx.mutate(root, "test", (target,), prepare)
    assert error.value.code == "recovery-ambiguous"
    assert (root / ".spec" / ".mutation-lock").exists()
    assert len(list((root / ".spec" / ".transactions").glob("*.json"))) == 1


def test_SDD_FR_143_recover_rolls_back_unapplied_transaction(tmp_path):
    root = _workspace(tmp_path)
    target = root / ".spec" / "STATE.md"
    target.write_bytes(b"before")
    owner = tx.acquire_lock(root, "test", (target,))
    owner["workspace_root"] = str(root.resolve())
    plan = tx.TransactionPlan(
        changes=(tx.FileChange(target, b"before", b"after"),),
        metadata={},
    )
    document = tx._journal_document(owner, plan)
    journal = root / ".spec" / ".transactions" / f"{owner['event_id']}.json"
    tx._write_journal_new(journal, document)
    _mark_lock_owner_dead(root)

    assert tx.recover(root, owner["event_id"]) == "rolled-back"
    assert target.read_bytes() == b"before"
    assert not journal.exists()
    assert not (root / ".spec" / ".mutation-lock").exists()


def test_SDD_FR_143_recover_completes_partially_applied_transaction(tmp_path):
    root = _workspace(tmp_path)
    first = root / ".spec" / "one.md"
    second = root / ".spec" / "two.md"
    first.write_bytes(b"old1")
    second.write_bytes(b"old2")
    owner = tx.acquire_lock(root, "test", (first, second))
    owner["workspace_root"] = str(root.resolve())
    plan = tx.TransactionPlan(
        changes=(
            tx.FileChange(first, b"old1", b"new1"),
            tx.FileChange(second, b"old2", b"new2"),
        ),
        metadata={},
    )
    document = tx._journal_document(owner, plan)
    journal = root / ".spec" / ".transactions" / f"{owner['event_id']}.json"
    tx._write_journal_new(journal, document)
    first.write_bytes(b"new1")
    _mark_lock_owner_dead(root)

    assert tx.recover(root, owner["event_id"]) == "committed"
    assert first.read_bytes() == b"new1"
    assert second.read_bytes() == b"new2"


def test_SDD_FR_143_journal_uses_sha256_and_canonical_base64(tmp_path):
    root = _workspace(tmp_path)
    target = root / ".spec" / "new.md"
    owner = tx.acquire_lock(root, "test", (target,))
    owner["workspace_root"] = str(root.resolve())
    document = tx._journal_document(
        owner,
        tx.TransactionPlan(
            changes=(tx.FileChange(target, None, "日本語\n".encode()),),
            metadata={},
        ),
    )
    encoded = tx.canonical_json(document)
    parsed = json.loads(encoded)
    assert parsed["hash_algorithm"] == "sha256"
    assert parsed["schema_version"] == 1
    assert parsed["targets"][0]["after_hash"] == tx.sha256("日本語\n".encode())
    tx.release_lock(root)


def test_SDD_FR_143_recover_rejects_active_transaction_owner(tmp_path):
    root = _workspace(tmp_path)
    target = root / ".spec" / "STATE.md"
    target.write_bytes(b"before")
    owner = tx.acquire_lock(root, "test", (target,))
    owner["workspace_root"] = str(root.resolve())
    document = tx._journal_document(
        owner,
        tx.TransactionPlan(
            changes=(tx.FileChange(target, b"before", b"after"),),
            metadata={},
        ),
    )
    journal = root / ".spec" / ".transactions" / f"{owner['event_id']}.json"
    tx._write_journal_new(journal, document)

    with pytest.raises(tx.MutationError) as error:
        tx.recover(root, owner["event_id"])

    assert error.value.code == "mutation-conflict"
