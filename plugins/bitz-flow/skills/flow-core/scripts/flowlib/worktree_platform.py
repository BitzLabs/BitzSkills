"""Local Safety Profileのplatform evidence adapter（FLW-TSK-111）。

OS固有probeの観測結果をclosed evidenceへ写し、コード同梱allowlistとsemantic
self-testの両方が成立した場合だけsupportedにする。外部profileや署名policyは扱わない。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from .worktree_contract import (
    CONTRACT_VERSION,
    ContractError,
    canonical_json_bytes,
    native_component_to_posix,
    native_component_to_windows,
    sha256_digest,
    validate_digest,
)

PROFILE_VERSION = 1
SUPPORTED = "SUPPORTED"
UNSUPPORTED_FILESYSTEM = "UNSUPPORTED_FILESYSTEM"
PLATFORMS = frozenset({"linux", "macos", "windows"})
FILESYSTEM_CLASSES = frozenset({"local", "network", "unknown"})
CASE_SEMANTICS = frozenset({"sensitive", "insensitive"})


@dataclass(frozen=True)
class SupportProfile:
    platform: str
    filesystem_types: frozenset[str]
    owner_model: str
    lock_primitive: str
    file_durability: str
    directory_durability: str
    child_supervision: str


@dataclass(frozen=True)
class PlatformObservation:
    platform: str
    filesystem_type: str
    filesystem_class: str
    owner_principal: str | None
    owner_matches: bool
    acl_owner_only: bool
    non_follow_walk: bool
    resource_kind: str
    resource_identity: str
    native_component: Mapping[str, str]
    case_semantics: str
    os_lock: bool
    file_durability: bool
    directory_durability: bool
    child_supervision: bool
    semantic_self_test: bool


@dataclass(frozen=True)
class PlatformEvidence:
    observation: PlatformObservation
    support_code: str
    reasons: tuple[str, ...]

    @property
    def supported(self) -> bool:
        return self.support_code == SUPPORTED

    def as_mapping(self) -> dict[str, object]:
        value = {
            "contract_version": CONTRACT_VERSION,
            "profile_version": PROFILE_VERSION,
            **self.observation.__dict__,
            "native_component": dict(self.observation.native_component),
            "support_code": self.support_code,
            "reasons": list(self.reasons),
        }
        return value


def _require_fields(value: Mapping[str, object], expected: set[str], label: str) -> None:
    if not isinstance(value, Mapping) or set(value) != expected:
        actual = set(value) if isinstance(value, Mapping) else set()
        raise ContractError(
            f"{label} fields mismatch: missing={sorted(expected-actual)}, unknown={sorted(actual-expected)}"
        )


def load_support_profiles(path: str | Path) -> dict[str, SupportProfile]:
    """コード同梱static registryをclosed形式で読む。"""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    _require_fields(raw, {"schema_version", "profiles"}, "platform support registry")
    if raw["schema_version"] != PROFILE_VERSION or not isinstance(raw["profiles"], list):
        raise ContractError("unsupported platform support registry")
    fields = {
        "platform", "filesystem_types", "owner_model", "lock_primitive",
        "file_durability", "directory_durability", "child_supervision",
    }
    profiles: dict[str, SupportProfile] = {}
    for item in raw["profiles"]:
        _require_fields(item, fields, "platform support profile")
        platform = item["platform"]
        filesystems = item["filesystem_types"]
        if platform not in PLATFORMS or platform in profiles:
            raise ContractError("unknown or duplicate platform support profile")
        if not isinstance(filesystems, list) or not filesystems or any(
            not isinstance(name, str) or not name or name.lower() != name for name in filesystems
        ) or len(filesystems) != len(set(filesystems)):
            raise ContractError("filesystem allowlist must be unique lowercase names")
        values = [item[name] for name in fields - {"platform", "filesystem_types"}]
        if any(not isinstance(value, str) or not value for value in values):
            raise ContractError("platform primitive identifiers must be non-empty strings")
        profiles[platform] = SupportProfile(
            platform,
            frozenset(filesystems),
            item["owner_model"],
            item["lock_primitive"],
            item["file_durability"],
            item["directory_durability"],
            item["child_supervision"],
        )
    if set(profiles) != PLATFORMS:
        raise ContractError("platform support registry must cover the three registered platforms")
    return profiles


def support_registry_digest(profiles: Mapping[str, SupportProfile]) -> str:
    value = [
        {
            "platform": profile.platform,
            "filesystem_types": sorted(profile.filesystem_types),
            "owner_model": profile.owner_model,
            "lock_primitive": profile.lock_primitive,
            "file_durability": profile.file_durability,
            "directory_durability": profile.directory_durability,
            "child_supervision": profile.child_supervision,
        }
        for profile in sorted(profiles.values(), key=lambda item: item.platform)
    ]
    return sha256_digest(canonical_json_bytes({"schema_version": PROFILE_VERSION, "profiles": value}))


def _validate_native_component(platform: str, value: Mapping[str, str]) -> None:
    if platform in {"linux", "macos"}:
        native_component_to_posix(value)
    else:
        native_component_to_windows(value)


def evaluate_platform(
    observation: PlatformObservation,
    *,
    profiles: Mapping[str, SupportProfile],
) -> PlatformEvidence:
    """観測不能を推測で補わず、理由をclosed evidenceへ残す。"""
    boolean_fields = (
        "owner_matches", "acl_owner_only", "non_follow_walk", "os_lock",
        "file_durability", "directory_durability", "child_supervision",
        "semantic_self_test",
    )
    if any(type(getattr(observation, name)) is not bool for name in boolean_fields):
        raise ContractError("platform observation flags must be booleans")
    if observation.platform not in PLATFORMS:
        raise ContractError("unknown platform discriminator")
    if (
        not isinstance(observation.filesystem_type, str)
        or not observation.filesystem_type
        or observation.filesystem_type.lower() != observation.filesystem_type
    ):
        raise ContractError("filesystem type must be a non-empty lowercase name")
    if observation.filesystem_class not in FILESYSTEM_CLASSES:
        raise ContractError("unknown filesystem class")
    if observation.case_semantics not in CASE_SEMANTICS:
        raise ContractError("unknown case semantics")
    if observation.resource_kind not in {"file", "directory"}:
        raise ContractError("unknown resource identity kind")
    validate_digest(observation.resource_identity)
    _validate_native_component(observation.platform, observation.native_component)
    profile = profiles.get(observation.platform)
    reasons: list[str] = []
    if profile is None:
        reasons.append("platform-not-allowlisted")
    if observation.filesystem_class != "local":
        reasons.append(f"filesystem-class-{observation.filesystem_class}")
    if profile is not None and observation.filesystem_type.lower() not in profile.filesystem_types:
        reasons.append("filesystem-type-not-allowlisted")
    checks = {
        "owner-unobservable": (
            isinstance(observation.owner_principal, str)
            and bool(observation.owner_principal)
        ),
        "owner-mismatch": observation.owner_matches,
        "acl-not-owner-only": observation.acl_owner_only,
        "non-follow-walk-unavailable": observation.non_follow_walk,
        "os-lock-unavailable": observation.os_lock,
        "file-durability-unavailable": observation.file_durability,
        "directory-durability-unavailable": observation.directory_durability,
        "child-supervision-unavailable": observation.child_supervision,
        "semantic-self-test-failed": observation.semantic_self_test,
    }
    reasons.extend(reason for reason, passed in checks.items() if not passed)
    return PlatformEvidence(
        observation,
        SUPPORTED if not reasons else UNSUPPORTED_FILESYSTEM,
        tuple(sorted(reasons)),
    )


def collision_key(
    *,
    parent_identity: str,
    native_component: Mapping[str, str],
    case_semantics: str,
    folded_component: Mapping[str, str] | None = None,
) -> str:
    """不在targetをparent identityとnative componentへ束縛する。"""
    validate_digest(parent_identity)
    if case_semantics not in CASE_SEMANTICS:
        raise ContractError("unknown case semantics")
    platform = native_component.get("platform")
    if platform == "posix":
        native_component_to_posix(native_component)
    elif platform == "windows":
        native_component_to_windows(native_component)
    else:
        raise ContractError("unknown native component platform")
    selected = native_component
    if case_semantics == "insensitive":
        if folded_component is None or folded_component.get("platform") != platform:
            raise ContractError("case-insensitive target requires a platform-derived folded component")
        if platform == "posix":
            native_component_to_posix(folded_component)
        else:
            native_component_to_windows(folded_component)
        selected = folded_component
    return sha256_digest(canonical_json_bytes({
        "parent_identity": parent_identity,
        "case_semantics": case_semantics,
        "component": dict(selected),
    }))
