"""FLW-NFR-014 / FLW-TSK-111 platform evidence adapter。"""

from __future__ import annotations

import json
import sys
import unicodedata
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "plugins" / "bitz-flow" / "skills" / "flow-core"
REGISTRY = SKILL / "references" / "worktree-v2-platform-support.json"
SCHEMA = SKILL / "schemas" / "worktree-v2" / "platform-evidence-v2.schema.json"
sys.path.insert(0, str(SKILL / "scripts"))

from flowlib import worktree_contract as C  # noqa: E402
from flowlib import worktree_platform as P  # noqa: E402

DIGEST = "sha256:" + "a" * 64


def _component(platform: str, value: str = "target") -> dict[str, str]:
    if platform == "windows":
        return C.native_component_from_windows(value).as_mapping()
    return C.native_component_from_posix(value.encode()).as_mapping()


def _observation(platform: str, **changes) -> P.PlatformObservation:
    filesystem = {"linux": "ext4", "macos": "apfs", "windows": "ntfs"}[platform]
    value = {
        "platform": platform,
        "filesystem_type": filesystem,
        "filesystem_class": "local",
        "owner_principal": "owner-1",
        "owner_matches": True,
        "acl_owner_only": True,
        "non_follow_walk": True,
        "resource_kind": "directory",
        "resource_identity": DIGEST,
        "native_component": _component(platform),
        "case_semantics": "insensitive" if platform == "windows" else "sensitive",
        "os_lock": True,
        "file_durability": True,
        "directory_durability": True,
        "child_supervision": True,
        "semantic_self_test": True,
    }
    value.update(changes)
    return P.PlatformObservation(**value)


def test_registry_and_schema_are_closed_and_cover_three_platforms():
    profiles = P.load_support_profiles(REGISTRY)
    assert set(profiles) == {"linux", "macos", "windows"}
    assert P.support_registry_digest(profiles).startswith("sha256:")
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])


@pytest.mark.parametrize("platform", ["linux", "macos", "windows"])
def test_registered_local_platforms_return_the_same_logical_supported_evidence(platform):
    evidence = P.evaluate_platform(_observation(platform), profiles=P.load_support_profiles(REGISTRY))
    assert evidence.supported
    assert evidence.support_code == P.SUPPORTED
    assert evidence.reasons == ()
    mapping = evidence.as_mapping()
    assert mapping["contract_version"] == 2
    assert set(mapping) == set(json.loads(SCHEMA.read_text())["required"])


@pytest.mark.parametrize("changes,reason", [
    ({"filesystem_class": "network", "filesystem_type": "nfs"}, "filesystem-class-network"),
    ({"filesystem_class": "unknown", "filesystem_type": "mystery"}, "filesystem-class-unknown"),
    ({"owner_principal": None}, "owner-unobservable"),
    ({"owner_matches": False}, "owner-mismatch"),
    ({"acl_owner_only": False}, "acl-not-owner-only"),
    ({"non_follow_walk": False}, "non-follow-walk-unavailable"),
    ({"os_lock": False}, "os-lock-unavailable"),
    ({"file_durability": False}, "file-durability-unavailable"),
    ({"directory_durability": False}, "directory-durability-unavailable"),
    ({"child_supervision": False}, "child-supervision-unavailable"),
    ({"semantic_self_test": False}, "semantic-self-test-failed"),
])
def test_unknown_or_unproven_platform_capabilities_stop_safely(changes, reason):
    evidence = P.evaluate_platform(_observation("linux", **changes), profiles=P.load_support_profiles(REGISTRY))
    assert not evidence.supported
    assert evidence.support_code == P.UNSUPPORTED_FILESYSTEM
    assert reason in evidence.reasons


def test_self_test_cannot_promote_a_filesystem_missing_from_static_allowlist():
    evidence = P.evaluate_platform(
        _observation("linux", filesystem_type="new-local-fs", semantic_self_test=True),
        profiles=P.load_support_profiles(REGISTRY),
    )
    assert not evidence.supported
    assert "filesystem-type-not-allowlisted" in evidence.reasons


def test_empty_owner_is_unobservable():
    evidence = P.evaluate_platform(
        _observation("linux", owner_principal=""),
        profiles=P.load_support_profiles(REGISTRY),
    )
    assert evidence.support_code == P.UNSUPPORTED_FILESYSTEM
    assert "owner-unobservable" in evidence.reasons


@pytest.mark.parametrize("changes", [
    {"filesystem_type": "EXT4"},
    {"owner_matches": "yes"},
])
def test_malformed_observation_cannot_use_python_truthiness(changes):
    with pytest.raises(C.ContractError):
        P.evaluate_platform(
            _observation("linux", **changes),
            profiles=P.load_support_profiles(REGISTRY),
        )


def test_case_collision_key_converges_only_with_platform_fold_evidence():
    upper = _component("windows", "Target")
    lower = _component("windows", "target")
    folded = _component("windows", "target")
    first = P.collision_key(parent_identity=DIGEST, native_component=upper, case_semantics="insensitive", folded_component=folded)
    second = P.collision_key(parent_identity=DIGEST, native_component=lower, case_semantics="insensitive", folded_component=folded)
    assert first == second
    with pytest.raises(C.ContractError, match="folded"):
        P.collision_key(parent_identity=DIGEST, native_component=upper, case_semantics="insensitive")


def test_sensitive_collision_key_preserves_nfc_and_nfd_as_distinct_entries():
    nfc = _component("linux", "é")
    nfd = _component("linux", unicodedata.normalize("NFD", "é"))
    first = P.collision_key(parent_identity=DIGEST, native_component=nfc, case_semantics="sensitive")
    second = P.collision_key(parent_identity=DIGEST, native_component=nfd, case_semantics="sensitive")
    assert first != second


def test_native_platform_mismatch_and_identity_kind_are_rejected():
    with pytest.raises(C.ContractError):
        P.evaluate_platform(
            _observation("windows", native_component=_component("linux")),
            profiles=P.load_support_profiles(REGISTRY),
        )
    with pytest.raises(C.ContractError, match="identity kind"):
        P.evaluate_platform(
            _observation("linux", resource_kind="socket"),
            profiles=P.load_support_profiles(REGISTRY),
        )
