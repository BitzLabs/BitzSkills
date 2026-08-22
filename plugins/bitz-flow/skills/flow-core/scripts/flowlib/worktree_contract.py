"""M2 Local Safety Profileのpure contract kernel（FLW-NFR-014）。

OS、Git、filesystem、subprocessへ触れず、呼出側から渡された値だけを検証する。
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
from dataclasses import dataclass
from functools import total_ordering
from typing import Any, Callable, Mapping, Sequence

CONTRACT_VERSION = 2
MAX_SAFE_JSON_INTEGER = (1 << 53) - 1
MAX_UINT64 = (1 << 64) - 1
DIGEST_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")
SEMVER_RE = re.compile(
    r"(?P<major>0|[1-9][0-9]*)\."
    r"(?P<minor>0|[1-9][0-9]*)\."
    r"(?P<patch>0|[1-9][0-9]*)"
    r"(?:-(?P<pre>(?:0|[1-9][0-9]*|[0-9A-Za-z-]*[A-Za-z-][0-9A-Za-z-]*)"
    r"(?:\.(?:0|[1-9][0-9]*|[0-9A-Za-z-]*[A-Za-z-][0-9A-Za-z-]*))*))?"
    r"(?:\+(?P<build>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?\Z"
)
EVENT_STATES = frozenset(
    {"LOCKED", "INTENT_DURABLE", "MUTATING", "RESULT_DURABLE", "DONE", "QUARANTINED"}
)
RECEIPT_STATES = frozenset({"INDETERMINATE", "TERMINAL"})


class ContractError(ValueError):
    """closed contractに適合しない値。"""


def _validate_json_value(value: Any, *, location: str = "$") -> None:
    if value is None or isinstance(value, bool):
        return
    if isinstance(value, int):
        if abs(value) > MAX_SAFE_JSON_INTEGER:
            raise ContractError(f"{location}: integer exceeds the safe JSON range")
        return
    if isinstance(value, float):
        raise ContractError(f"{location}: float is not part of the canonical contract")
    if isinstance(value, str):
        if "\x00" in value:
            raise ContractError(f"{location}: NUL is not allowed")
        if any(0xD800 <= ord(char) <= 0xDFFF for char in value):
            raise ContractError(f"{location}: surrogate code point is not allowed")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_json_value(item, location=f"{location}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ContractError(f"{location}: object keys must be strings")
            _validate_json_value(key, location=f"{location}.<key>")
            _validate_json_value(item, location=f"{location}.{key}")
        return
    raise ContractError(f"{location}: unsupported JSON value type {type(value).__name__}")


def canonical_json_bytes(value: Any) -> bytes:
    """正規化を行わず、決定的なUTF-8 canonical JSONを返す。"""
    _validate_json_value(value)
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _closed_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ContractError(f"duplicate object key: {key}")
        value[key] = item
    return value


def parse_canonical_json(data: bytes) -> Any:
    """canonical bytesだけをdecodeする。空白やkey順差も拒否する。"""
    if not isinstance(data, bytes):
        raise TypeError("canonical JSON input must be bytes")
    try:
        text = data.decode("utf-8", errors="strict")
        value = json.loads(
            text,
            object_pairs_hook=_closed_object,
            parse_float=lambda value: (_ for _ in ()).throw(ContractError(f"float is not allowed: {value}")),
            parse_constant=lambda value: (_ for _ in ()).throw(ContractError(f"constant is not allowed: {value}")),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractError(f"invalid canonical JSON: {exc}") from exc
    if canonical_json_bytes(value) != data:
        raise ContractError("input is valid JSON but not canonical JSON")
    return value


def sha256_digest(data: bytes) -> str:
    if not isinstance(data, bytes):
        raise TypeError("digest input must be bytes")
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def validate_digest(value: object) -> str:
    if not isinstance(value, str) or DIGEST_RE.fullmatch(value) is None:
        raise ContractError("digest must be sha256:<64 lowercase hex>")
    return value


def validate_uint64_string(value: object) -> str:
    if not isinstance(value, str) or re.fullmatch(r"0|[1-9][0-9]*", value) is None:
        raise ContractError("uint64 must be a canonical decimal string")
    if int(value) > MAX_UINT64:
        raise ContractError("uint64 exceeds 2^64-1")
    return value


@total_ordering
@dataclass(frozen=True)
class SemVer:
    major: int
    minor: int
    patch: int
    prerelease: tuple[str, ...] = ()
    build: tuple[str, ...] = ()

    @classmethod
    def parse(cls, value: object) -> "SemVer":
        if not isinstance(value, str):
            raise ContractError("SemVer must be a string")
        match = SEMVER_RE.fullmatch(value)
        if match is None:
            raise ContractError("invalid strict SemVer")
        return cls(
            int(match.group("major")),
            int(match.group("minor")),
            int(match.group("patch")),
            tuple((match.group("pre") or "").split(".")) if match.group("pre") else (),
            tuple((match.group("build") or "").split(".")) if match.group("build") else (),
        )

    def _precedence(self) -> tuple[Any, ...]:
        if not self.prerelease:
            pre: tuple[Any, ...] = ((2, ""),)
        else:
            pre = tuple((0, int(part)) if part.isdigit() else (1, part) for part in self.prerelease)
        return self.major, self.minor, self.patch, pre

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, SemVer):
            return NotImplemented
        return self._precedence() < other._precedence()

    def __eq__(self, other: object) -> bool:
        return isinstance(other, SemVer) and self._precedence() == other._precedence()


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64decode(value: object) -> bytes:
    if not isinstance(value, str) or re.fullmatch(r"[A-Za-z0-9_-]*", value) is None:
        raise ContractError("native component is not unpadded base64url")
    try:
        decoded = base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
    except (ValueError, TypeError) as exc:
        raise ContractError("native component is not unpadded base64url") from exc
    if _b64encode(decoded) != value:
        raise ContractError("native component base64url is not canonical")
    return decoded


@dataclass(frozen=True)
class NativeComponent:
    platform: str
    encoding: str
    value: str

    def as_mapping(self) -> dict[str, str]:
        return {"platform": self.platform, "encoding": self.encoding, "value": self.value}


def native_component_from_posix(value: bytes) -> NativeComponent:
    if not isinstance(value, bytes) or b"\x00" in value or b"/" in value:
        raise ContractError("POSIX component must be non-NUL bytes without slash")
    return NativeComponent("posix", "bytes-base64url", _b64encode(value))


def native_component_to_posix(value: Mapping[str, object]) -> bytes:
    _require_fields(value, {"platform", "encoding", "value"}, "native component")
    if value["platform"] != "posix" or value["encoding"] != "bytes-base64url":
        raise ContractError("native component platform/encoding mismatch")
    decoded = _b64decode(value["value"])
    if b"\x00" in decoded or b"/" in decoded:
        raise ContractError("invalid POSIX component")
    return decoded


def native_component_from_windows(value: str) -> NativeComponent:
    if not isinstance(value, str) or "\x00" in value or "\\" in value or "/" in value:
        raise ContractError("Windows component must not contain NUL or separator")
    return NativeComponent("windows", "utf16le-base64url", _b64encode(value.encode("utf-16-le", "surrogatepass")))


def native_component_to_windows(value: Mapping[str, object]) -> str:
    _require_fields(value, {"platform", "encoding", "value"}, "native component")
    if value["platform"] != "windows" or value["encoding"] != "utf16le-base64url":
        raise ContractError("native component platform/encoding mismatch")
    raw = _b64decode(value["value"])
    if len(raw) % 2:
        raise ContractError("Windows component has an odd UTF-16LE byte length")
    decoded = raw.decode("utf-16-le", "surrogatepass")
    if "\x00" in decoded or "\\" in decoded or "/" in decoded:
        raise ContractError("invalid Windows component")
    return decoded


def _require_fields(value: Mapping[str, object], expected: set[str], label: str) -> None:
    if not isinstance(value, Mapping):
        raise ContractError(f"{label} must be an object")
    actual = set(value)
    if actual != expected:
        raise ContractError(f"{label} fields mismatch: missing={sorted(expected-actual)}, unknown={sorted(actual-expected)}")


def validate_platform_identity(value: Mapping[str, object], *, expected_kind: str | None = None) -> dict[str, str]:
    _require_fields(value, {"platform", "kind", "identity"}, "platform identity")
    if value["platform"] not in {"linux", "macos", "windows"}:
        raise ContractError("unknown platform identity discriminator")
    if value["kind"] not in {"file", "directory"}:
        raise ContractError("unknown identity kind")
    if expected_kind is not None and value["kind"] != expected_kind:
        raise ContractError("platform identity kind mismatch")
    identity = validate_digest(value["identity"])
    return {"platform": str(value["platform"]), "kind": str(value["kind"]), "identity": identity}


def validate_operation_event(value: Mapping[str, object]) -> dict[str, object]:
    fields = {"contract_version", "operation_id", "target_collision_key", "sequence", "previous_event_digest", "state", "fencing_token"}
    _require_fields(value, fields, "operation event")
    if value["contract_version"] != CONTRACT_VERSION:
        raise ContractError("unsupported contract version")
    if not isinstance(value["operation_id"], str) or not value["operation_id"]:
        raise ContractError("operation_id is required")
    if not isinstance(value["target_collision_key"], str) or not value["target_collision_key"]:
        raise ContractError("target_collision_key is required")
    if value["state"] not in EVENT_STATES:
        raise ContractError("unknown operation event state")
    sequence = validate_uint64_string(value["sequence"])
    token = validate_uint64_string(value["fencing_token"])
    previous = value["previous_event_digest"]
    if previous is not None:
        previous = validate_digest(previous)
    return {**value, "sequence": sequence, "fencing_token": token, "previous_event_digest": previous}


def validate_mutation_receipt(value: Mapping[str, object]) -> dict[str, object]:
    fields = {"contract_version", "operation_id", "target_collision_key", "receipt_state", "event_digest", "supersedes_receipt_digest", "fencing_token"}
    _require_fields(value, fields, "mutation receipt")
    if value["contract_version"] != CONTRACT_VERSION:
        raise ContractError("unsupported contract version")
    if value["receipt_state"] not in RECEIPT_STATES:
        raise ContractError("unknown receipt state")
    validate_digest(value["event_digest"])
    validate_uint64_string(value["fencing_token"])
    supersedes = value["supersedes_receipt_digest"]
    if value["receipt_state"] == "INDETERMINATE" and supersedes is not None:
        raise ContractError("emergency receipt must not supersede another receipt")
    if value["receipt_state"] == "TERMINAL" and supersedes is None:
        raise ContractError("terminal receipt must supersede the emergency receipt")
    if supersedes is not None:
        validate_digest(supersedes)
    return dict(value)


@dataclass(frozen=True)
class BundleMember:
    schema_id: str
    schema_digest: str
    codec_id: str
    runtime_module: str


@dataclass(frozen=True)
class ContractBundle:
    bundle_version: str
    contract_version: int
    minimum_runtime_version: str
    members: tuple[BundleMember, ...]
    platform_allowlist_digest: str
    created_by_release: str

    def as_mapping(self) -> dict[str, object]:
        return {
            "bundle_version": self.bundle_version,
            "contract_version": self.contract_version,
            "minimum_runtime_version": self.minimum_runtime_version,
            "members": [member.__dict__ for member in self.members],
            "platform_allowlist_digest": self.platform_allowlist_digest,
            "created_by_release": self.created_by_release,
        }

    @property
    def digest(self) -> str:
        ordered = {**self.as_mapping(), "members": [member.__dict__ for member in sorted(self.members, key=lambda item: item.schema_id)]}
        return sha256_digest(canonical_json_bytes(ordered))


def validate_contract_bundle(
    value: Mapping[str, object],
    *,
    expected_members: Mapping[str, tuple[str, str]],
    schema_documents: Mapping[str, bytes],
    round_trip_checker: Callable[[BundleMember], bool] | None = None,
) -> ContractBundle:
    fields = {"bundle_version", "contract_version", "minimum_runtime_version", "members", "platform_allowlist_digest", "created_by_release"}
    _require_fields(value, fields, "contract bundle")
    SemVer.parse(value["bundle_version"])
    SemVer.parse(value["minimum_runtime_version"])
    SemVer.parse(value["created_by_release"])
    if value["contract_version"] != CONTRACT_VERSION:
        raise ContractError("unsupported contract version")
    validate_digest(value["platform_allowlist_digest"])
    if not isinstance(value["members"], list):
        raise ContractError("bundle members must be an array")
    members: list[BundleMember] = []
    for raw in value["members"]:
        _require_fields(raw, {"schema_id", "schema_digest", "codec_id", "runtime_module"}, "bundle member")
        member = BundleMember(str(raw["schema_id"]), validate_digest(raw["schema_digest"]), str(raw["codec_id"]), str(raw["runtime_module"]))
        if not member.schema_id or not member.codec_id or not member.runtime_module:
            raise ContractError("bundle member identifiers must be non-empty")
        members.append(member)
    ids = [member.schema_id for member in members]
    if len(ids) != len(set(ids)):
        raise ContractError("duplicate schema ID")
    if set(ids) != set(expected_members):
        raise ContractError(f"bundle member set mismatch: missing={sorted(set(expected_members)-set(ids))}, unknown={sorted(set(ids)-set(expected_members))}")
    if set(schema_documents) != set(expected_members):
        raise ContractError("schema document inventory mismatch")
    for member in members:
        expected_codec, expected_module = expected_members[member.schema_id]
        if (member.codec_id, member.runtime_module) != (expected_codec, expected_module):
            raise ContractError(f"bundle member implementation mismatch: {member.schema_id}")
        schema_value = parse_canonical_json(schema_documents[member.schema_id])
        if sha256_digest(canonical_json_bytes(schema_value)) != member.schema_digest:
            raise ContractError(f"schema digest mismatch: {member.schema_id}")
        if round_trip_checker is not None and not round_trip_checker(member):
            raise ContractError(f"schema/codec round-trip mismatch: {member.schema_id}")
    return ContractBundle(
        str(value["bundle_version"]),
        CONTRACT_VERSION,
        str(value["minimum_runtime_version"]),
        tuple(members),
        str(value["platform_allowlist_digest"]),
        str(value["created_by_release"]),
    )
