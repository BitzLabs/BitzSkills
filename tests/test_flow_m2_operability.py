"""FLW-NFR-014 / FLW-TSK-114 operability integration tests."""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "plugins" / "bitz-flow" / "skills" / "flow-core"
sys.path.insert(0, str(SKILL / "scripts"))

from flowlib import cli  # noqa: E402
from flowlib import worktree_operability as O  # noqa: E402
from flowlib import worktree_promotion as P  # noqa: E402
from flowlib import worktree_runtime as WR  # noqa: E402
from flowlib import worktree_transaction as T  # noqa: E402

ORIGINAL = "sha256:" + "a" * 64
TARGET = "sha256:" + "b" * 64
BUNDLE = "sha256:" + "c" * 64


def git(repo, *args):
    return subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()


@pytest.fixture
def repository(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "fixture@example.invalid")
    git(repo, "config", "user.name", "Fixture")
    (repo / "tracked.txt").write_text("one\n", encoding="utf-8")
    git(repo, "add", "tracked.txt")
    git(repo, "commit", "-qm", "init")
    common = Path(git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir"))
    observed = WR.RepositoryObserver(repo).snapshot()
    root = common / "bitz-flow-v2" / "transactions" / TARGET[7:]
    tx = T.TargetTransaction(root, target_collision_key=TARGET)
    lease = tx.acquire(operation_id=ORIGINAL, nonce="mutation")
    tx.prepare_intent(
        lease, planned_effects_digest=BUNDLE,
        precondition_digest=observed.digest,
    )
    tx.release(lease)
    P.register_active_operation(
        common, operation_id=ORIGINAL, bundle_digest=BUNDLE
    )
    return repo, common, tx


def invoke(repo, argv, capsys):
    handlers = {**cli._HANDLERS, **cli._GATED_HANDLERS}
    code = cli.main([*argv, "--repo", str(repo), "--format", "json"], handlers=handlers)
    payload = json.loads(capsys.readouterr().out)
    return code, payload


@pytest.mark.parametrize("action", ["doctor", "audit", "verify-receipt"])
def test_read_only_commands_leave_persistent_state_unchanged(repository, action, capsys):
    repo, common, _ = repository
    before = O.persistent_state_digest(common)
    args = ["worktree", action]
    if action != "doctor":
        args += ["--operation-id", ORIGINAL]
    _, payload = invoke(repo, args, capsys)
    after = O.persistent_state_digest(common)
    assert before == after
    assert payload["data"]["automatic_recovery_allowed"] is False
    assert payload["data"]["side_effect_state"] in {"none", "indeterminate"}
    assert payload["data"]["operator_action"]
    assert set(payload["data"]["journal_usage"]) == {
        "event_count", "receipt_count", "closure_count", "bytes",
    }


def test_audit_and_verify_receipt_use_recovery_and_transaction_chain(repository, capsys):
    repo, _, _ = repository
    code, audit = invoke(
        repo, ["worktree", "audit", "--operation-id", ORIGINAL], capsys
    )
    assert code == 0
    assert audit["data"]["operability"]["classification"] == "confirmed-incomplete"
    code, verified = invoke(
        repo, ["worktree", "verify-receipt", "--operation-id", ORIGINAL], capsys
    )
    assert code == 0
    assert verified["data"]["operability"]["chain_valid"] is True


def test_reconcile_plan_and_apply_are_connected_through_dispatcher(repository, capsys):
    repo, _, tx = repository
    expires = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
    common = [
        "worktree", "reconcile", "--operation-id", ORIGINAL,
        "--decision", "confirmed-incomplete", "--expires-at", expires,
        "--nonce", "reconcile-nonce", "--bundle-digest", BUNDLE,
    ]
    code, planned = invoke(repo, common, capsys)
    assert code == 0 and planned["code"] == "READY"
    operation_id = planned["operation_id"]
    code, applied = invoke(
        repo, [*common, "--apply", "--confirm", operation_id], capsys
    )
    assert code == 0 and applied["code"] == "DONE"
    assert applied["data"]["side_effect_state"] == "closure-only"
    assert applied["data"]["operability"]["marker_released"] is True
    assert len(tx.inspect(ORIGINAL).closures) == 1


def test_reconcile_apply_without_confirmation_is_closed_stop(repository, capsys):
    repo, _, _ = repository
    expires = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
    code, payload = invoke(repo, [
        "worktree", "reconcile", "--operation-id", ORIGINAL,
        "--decision", "confirmed-incomplete", "--expires-at", expires,
        "--nonce", "reconcile-nonce", "--bundle-digest", BUNDLE, "--apply",
    ], capsys)
    assert code != 0
    for field in (
        "result_code", "cause_code", "side_effect_state",
        "automatic_recovery_allowed", "operator_action", "receipt_path",
        "journal_usage",
    ):
        assert field in payload["data"]
    assert payload["data"]["operator_action"] == "manual-inspection"


def test_reconcile_never_launches_git_mutation(repository, capsys, monkeypatch):
    repo, _, _ = repository
    expires = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
    planned = O.reconcile_plan(
        repo, operation_id=ORIGINAL, decision="confirmed-incomplete",
        expires_at=expires, nonce="one", bundle_digest=BUNDLE,
    )

    def forbidden(*_args, **_kwargs):
        raise AssertionError("Git observation should have been injected before this boundary")

    # Reconcile receives a pre-bound observer; write-capable Git has no import path in operability.
    source = (SKILL / "scripts/flowlib/worktree_operability.py").read_text()
    tree = ast.parse(source)
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert "subprocess" not in imports
    assert planned.plan is not None


def test_signed_capability_is_immediately_rejected_on_public_dispatcher(tmp_path, capsys):
    code = cli.main([
        "worktree", "reconcile", "--capability-file", str(tmp_path / "old.json"),
        "--format", "json",
    ])
    payload = json.loads(capsys.readouterr().out)
    assert code == 8
    assert payload["code"] == "UNSUPPORTED"
    assert payload["data"]["cause"] == "unsupported-approval-mode"
    assert "reason" not in payload["data"]


@pytest.mark.parametrize("signal", ["declaration", "trusted-registry"])
def test_retired_approval_configuration_is_rejected_without_downgrade(
    repository, signal, capsys,
):
    repo, common, _ = repository
    if signal == "declaration":
        path = repo / ".bitz-flow" / "approval-mode.json"
    else:
        path = common / "bitz-flow-v2" / "trusted-worktree-keys.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not-consumed", encoding="utf-8")
    code, payload = invoke(repo, ["worktree", "doctor"], capsys)
    assert code == 8
    assert payload["data"]["cause"] == "unsupported-approval-mode"
    assert "not-consumed" not in json.dumps(payload)


def test_all_operability_commands_exist_but_remain_gated_in_production(capsys):
    expected = {"doctor", "audit", "verify-receipt", "reconcile"}
    assert expected <= {
        action for domain, action in cli._GATED_HANDLERS if domain == "worktree"
    }
    assert not any(
        ("worktree", action) in cli.PUBLISHED_OPERATIONS for action in expected
    )
    for action in expected:
        code = cli.main(["worktree", action, "--format", "json"])
        payload = json.loads(capsys.readouterr().out)
        assert code == 8 and payload["code"] == "UNSUPPORTED"


def test_coverage_manifest_covers_every_acceptance_row_and_flow_edge():
    manifest = json.loads(
        (SKILL / "references/m2-operability-coverage.json").read_text(encoding="utf-8")
    )
    assert set(manifest["acceptance_rows"]) == {
        "plan-state-change", "lock-contention", "pre-intent-storage",
        "post-intent-pre-child-crash", "child-unknown", "postcondition-pre-terminal",
        "terminal-pre-marker-release", "journal-corruption", "promotion-failure",
        "readonly-invariance", "reconcile-retry", "unsupported-environment-or-approval",
    }
    assert set(manifest["flow_edges"]) == {
        "plan", "apply-start", "git-mutation", "apply-end", "audit",
        "verify-receipt", "reconcile", "promotion", "startup-gate",
    }
    assert all(manifest["acceptance_rows"].values())
    assert all(manifest["flow_edges"].values())
