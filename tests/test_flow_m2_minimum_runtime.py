"""FLW-NFR-014 / FLW-TSK-112 minimum-runtime gate."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "plugins" / "bitz-flow" / "skills" / "flow-core"
sys.path.insert(0, str(SKILL / "scripts"))

from flowlib import worktree_contract as C  # noqa: E402
from flowlib import worktree_minimum_runtime as M  # noqa: E402


def bundle(version="0.12.3", contract=2):
    return {"bundle_version": "2.0.0", "contract_version": contract,
            "minimum_runtime_version": version}


def test_marker_schema_remains_closed_v1_contract():
    schema = json.loads((SKILL / "schemas/worktree-v2/minimum-runtime-v1.schema.json").read_text())
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])


@pytest.mark.parametrize("entrypoint", sorted(M.ENTRYPOINTS))
def test_stable_launcher_and_public_cli_accept_only_compatible_active_bundle(tmp_path, entrypoint):
    M.publish_marker(tmp_path, minimum_runtime_version="0.12.3")
    decision = M.startup_gate(
        tmp_path, entrypoint=entrypoint, runtime_version="0.12.3",
        bundle_state="ACTIVE", current_bundle=bundle(),
    )
    assert decision.allowed and decision.code == "READY"


@pytest.mark.parametrize("changes,cause", [
    ({"bundle_state": "PENDING"}, "bundle-pending"),
    ({"bundle_state": "UNKNOWN"}, "unknown-bundle"),
    ({"current_bundle": None}, "unknown-bundle"),
    ({"current_bundle": bundle(contract=1)}, "contract-version-mismatch"),
    ({"current_bundle": bundle("0.13.0")}, "bundle-marker-mismatch"),
    ({"runtime_version": "0.12.2"}, "runtime-too-old"),
])
def test_pending_unknown_and_incompatible_runtime_stop_closed(tmp_path, changes, cause):
    M.publish_marker(tmp_path, minimum_runtime_version="0.12.3")
    args = {"entrypoint": "public-cli", "runtime_version": "0.12.3",
            "bundle_state": "ACTIVE", "current_bundle": bundle()}
    args.update(changes)
    decision = M.startup_gate(tmp_path, **args)
    assert not decision.allowed and decision.code == "BLOCKED" and decision.cause == cause


def test_audit_only_missing_marker_has_zero_filesystem_side_effects(tmp_path):
    root = tmp_path / "missing"
    decision = M.startup_gate(
        root, entrypoint="public-cli", runtime_version="0.12.3",
        bundle_state="ACTIVE", current_bundle=bundle(),
    )
    assert not decision.allowed and not root.exists()
    with pytest.raises(C.ContractError, match="audit-only"):
        M.publish_marker(root, minimum_runtime_version="0.12.3", audit_only=True)
    assert not root.exists()


@pytest.mark.parametrize("step", M.PUBLISH_STEPS)
def test_every_publish_crash_converges_to_complete_old_or_new_marker(tmp_path, step):
    M.publish_marker(tmp_path, minimum_runtime_version="0.12.3")

    def crash(current, _path):
        if current == step:
            raise RuntimeError("crash")

    with pytest.raises(RuntimeError, match="crash"):
        M.publish_marker(tmp_path, minimum_runtime_version="0.13.0", step_hook=crash)
    marker = M.read_marker(tmp_path)
    assert marker["minimum_runtime_version"] in {"0.12.3", "0.13.0"}
    namespace = tmp_path / M.MARKER_RELATIVE_PATH.parent
    assert not list(namespace.glob("*.tmp"))
