"""FLW-NFR-014 contract v2 schemaとpromotion barrier。"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "plugins" / "bitz-flow" / "skills" / "flow-core"
SCHEMAS = SKILL / "schemas" / "worktree-v2"
sys.path.insert(0, str(SKILL / "scripts"))

from flowlib import worktree_capability as C  # noqa: E402
from flowlib import worktree_promotion as P  # noqa: E402


DIGEST = "sha256:" + "a" * 64
LEGACY_SCHEMAS = {
    "approval-capability-v2.schema.json",
    "approval-binding-v2.schema.json",
    "target-lease-v2.schema.json",
    "fencing-counter-v2.schema.json",
    "mutation-intention-v2.schema.json",
    "mutation-postcondition-v2.schema.json",
    "mutation-receipt-v2.schema.json",
    "lock-namespace-v2.schema.json",
    "minimum-runtime-v1.schema.json",
}
LOCAL_SAFETY_SCHEMAS = {
    "contract-bundle-v2.schema.json",
    "approval-context-v2.schema.json",
}
EXPECTED_SCHEMAS = LEGACY_SCHEMAS | LOCAL_SAFETY_SCHEMAS


def capability_value() -> dict[str, object]:
    return {
        "contract_version": 2,
        "approval_declaration_digest": DIGEST,
        "repository_identity_digest": DIGEST,
        "worktree_dir_guard_key": "dir-key",
        "worktree_registry_guard_key": "registry-key",
        "parent_dir_identity": DIGEST,
        "nonexistence_digest": DIGEST,
        "instance_identity_digest": None,
        "worktree_root_canonical": "/worktrees",
        "case_sensitivity": "sensitive",
        "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
        "nonce": "nonce",
        "operation_id": "worktree.create",
        "algorithm": "Ed25519",
        "key_id": "owner-key",
        "signature": "signature",
    }


def test_FLW_NFR_014_all_v2_records_are_closed_versioned_schemas():
    paths = {path.name for path in SCHEMAS.glob("*.schema.json")}
    assert paths == EXPECTED_SCHEMAS
    for path in SCHEMAS.glob("*.schema.json"):
        schema = json.loads(path.read_text(encoding="utf-8"))
        assert schema["type"] == "object"
        assert schema["additionalProperties"] is False
        assert set(schema["required"]) == set(schema["properties"])


def test_FLW_NFR_014_legacy_signed_schema_exists_but_is_not_a_local_safety_schema():
    assert "approval-capability-v2.schema.json" in LEGACY_SCHEMAS
    assert "approval-capability-v2.schema.json" not in LOCAL_SAFETY_SCHEMAS


def test_FLW_NFR_014_capability_v2_parser_accepts_the_closed_contract():
    capability = C.capability_v2_from_mapping(capability_value())
    assert capability.contract_version == C.CAPABILITY_CONTRACT_VERSION
    assert capability.approval_declaration_digest == DIGEST
    assert "signature" not in capability.signed_payload()
    assert capability.signed_payload()["approval_declaration_digest"] == DIGEST


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda value: value.pop("approval_declaration_digest"), "missing"),
        (lambda value: value.update({"unknown": True}), "unknown"),
        (lambda value: value.update({"contract_version": 1}), "version"),
        (lambda value: value.update({"approval_declaration_digest": "sha256:BAD"}), "digest"),
        (lambda value: value.update({"case_sensitivity": True}), "discriminator"),
    ],
)
def test_FLW_NFR_014_capability_v1_missing_unknown_and_noncanonical_values_are_rejected(mutation, message):
    value = capability_value()
    mutation(value)
    with pytest.raises(ValueError, match=message):
        C.capability_v2_from_mapping(value)


def test_FLW_NFR_014_minimum_runtime_sentinel_is_durable_closed_and_owner_only(tmp_path):
    common = tmp_path / "common"
    common.mkdir()
    target = P.write_minimum_runtime_sentinel(common, minimum_runtime_version="0.12.0")
    assert target == common / P.SENTINEL_RELATIVE_PATH
    assert target.stat().st_mode & 0o077 == 0
    assert target.stat().st_nlink == 1
    assert P.read_minimum_runtime_sentinel(common) == {
        "schema_version": 1,
        "minimum_runtime_version": "0.12.0",
        "contract_schema_version": 2,
    }
    encoded = target.read_bytes()
    assert encoded.endswith(b"\n")
    assert encoded == P._canonical_json(json.loads(encoded))


def test_FLW_NFR_014_symlinked_sentinel_is_rejected(tmp_path):
    common = tmp_path / "common"
    namespace = common / "bitz-flow-v2"
    namespace.mkdir(parents=True, mode=0o700)
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    (namespace / "minimum-runtime.json").symlink_to(outside)
    with pytest.raises(ValueError, match="symlink"):
        P.write_minimum_runtime_sentinel(common, minimum_runtime_version="0.12.0")


def test_FLW_NFR_014_promotion_requires_every_supported_entrypoint_at_the_baseline():
    sentinel = {"minimum_runtime_version": "0.12.0"}
    supported = ["linux-cli", "macos-cli", "windows-cli"]
    ready = P.promotion_preflight(
        sentinel,
        entrypoint_inventory={name: "0.12.0" for name in supported},
        supported_entrypoints=supported,
    )
    assert (ready.allowed, ready.code) == (True, "READY")

    obsolete = P.promotion_preflight(
        sentinel,
        entrypoint_inventory={"linux-cli": "0.12.0", "macos-cli": "0.11.3", "windows-cli": "0.12.0"},
        supported_entrypoints=supported,
    )
    assert (obsolete.allowed, obsolete.code) == (False, "BLOCKED")
    assert "macos-cli" in obsolete.reason

    incomplete = P.promotion_preflight(
        sentinel,
        entrypoint_inventory={"linux-cli": "0.12.0", "macos-cli": "0.12.0"},
        supported_entrypoints=supported,
    )
    assert (incomplete.allowed, incomplete.code) == (False, "UNSUPPORTED")
