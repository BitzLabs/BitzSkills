"""FLW-NFR-014 / FLW-TSK-106 pure contract kernel。"""

from __future__ import annotations

import inspect
import json
import sys
import unicodedata
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "plugins" / "bitz-flow" / "skills" / "flow-core"
sys.path.insert(0, str(SKILL / "scripts"))

from flowlib import worktree_contract as C  # noqa: E402

DIGEST = "sha256:" + "a" * 64


def test_canonical_json_is_deterministic_and_preserves_unicode_form():
    nfc = "é"
    nfd = unicodedata.normalize("NFD", nfc)
    assert C.canonical_json_bytes({"b": 2, "a": nfc}) == b'{"a":"\xc3\xa9","b":2}'
    assert C.canonical_json_bytes({"a": nfc}) != C.canonical_json_bytes({"a": nfd})
    assert C.sha256_digest(C.canonical_json_bytes({"a": nfc})) != C.sha256_digest(C.canonical_json_bytes({"a": nfd}))


@pytest.mark.parametrize("value", [1.0, float("nan"), float("inf"), "\x00", "\ud800", 1 << 53, ("tuple",)])
def test_canonical_json_rejects_non_contract_values(value):
    with pytest.raises(C.ContractError):
        C.canonical_json_bytes({"value": value})


@pytest.mark.parametrize("raw", [b'{"b":2, "a":1}', b'{"b":2,"a":1}', b'{"a":1,"a":1}', b'{"a":1}\n'])
def test_parse_canonical_json_rejects_noncanonical_bytes(raw):
    with pytest.raises(C.ContractError):
        C.parse_canonical_json(raw)


def test_parse_canonical_json_round_trip():
    raw = C.canonical_json_bytes({"a": [True, None, 2], "b": "x"})
    assert C.canonical_json_bytes(C.parse_canonical_json(raw)) == raw


@pytest.mark.parametrize("value", [DIGEST, "sha256:" + "0" * 64])
def test_digest_accepts_only_prefixed_lowercase_full_hash(value):
    assert C.validate_digest(value) == value


@pytest.mark.parametrize("value", ["a" * 64, "sha256:" + "A" * 64, "sha256:abc", 1])
def test_digest_rejects_noncanonical_value(value):
    with pytest.raises(C.ContractError):
        C.validate_digest(value)


@pytest.mark.parametrize("value", ["0", "9007199254740992", "18446744073709551615"])
def test_uint64_is_a_decimal_string(value):
    assert C.validate_uint64_string(value) == value


@pytest.mark.parametrize("value", [0, -1, "-1", "01", "+1", "18446744073709551616"])
def test_uint64_rejects_noncanonical_or_overflow(value):
    with pytest.raises(C.ContractError):
        C.validate_uint64_string(value)


@pytest.mark.parametrize("value", ["0.0.0", "1.2.3-alpha.1", "1.2.3+build.7"])
def test_strict_semver_accepts_valid_values(value):
    assert C.SemVer.parse(value)


@pytest.mark.parametrize("value", ["v1.2.3", "1.2", "01.2.3", "1.2.3-01", " 1.2.3"])
def test_strict_semver_rejects_loose_values(value):
    with pytest.raises(C.ContractError):
        C.SemVer.parse(value)


def test_semver_precedence_ignores_build_and_orders_prerelease():
    assert C.SemVer.parse("1.0.0-alpha.1") < C.SemVer.parse("1.0.0-alpha.beta") < C.SemVer.parse("1.0.0")
    assert C.SemVer.parse("1.0.0+one") == C.SemVer.parse("1.0.0+two")


def test_native_posix_and_windows_components_round_trip_without_normalization():
    posix = b"name-\xff"
    encoded_posix = C.native_component_from_posix(posix)
    assert C.native_component_to_posix(encoded_posix.as_mapping()) == posix
    windows = "name-\ud800"
    encoded_windows = C.native_component_from_windows(windows)
    assert C.native_component_to_windows(encoded_windows.as_mapping()) == windows
    nfc = C.native_component_from_windows("é")
    nfd = C.native_component_from_windows(unicodedata.normalize("NFD", "é"))
    assert nfc != nfd


def test_native_component_rejects_unknown_discriminator_and_platform_identity_kind_mixup():
    with pytest.raises(C.ContractError):
        C.native_component_to_posix({"platform": "posix", "encoding": "utf8", "value": "eA"})
    identity = {"platform": "linux", "kind": "file", "identity": DIGEST}
    with pytest.raises(C.ContractError, match="kind mismatch"):
        C.validate_platform_identity(identity, expected_kind="directory")


def _event(**changes):
    value = {
        "contract_version": 2,
        "operation_id": DIGEST,
        "target_collision_key": "target",
        "sequence": "0",
        "previous_event_digest": None,
        "state": "LOCKED",
        "fencing_token": "1",
    }
    value.update(changes)
    return value


def test_event_and_receipt_closed_state_contracts():
    assert C.validate_operation_event(_event())["state"] == "LOCKED"
    with pytest.raises(C.ContractError, match="unknown operation event state"):
        C.validate_operation_event(_event(state="UNKNOWN"))
    emergency = {
        "contract_version": 2, "operation_id": DIGEST, "target_collision_key": "target",
        "receipt_state": "INDETERMINATE", "event_digest": DIGEST,
        "supersedes_receipt_digest": None, "fencing_token": "1",
    }
    assert C.validate_mutation_receipt(emergency)["receipt_state"] == "INDETERMINATE"
    terminal = {**emergency, "receipt_state": "TERMINAL", "supersedes_receipt_digest": DIGEST}
    assert C.validate_mutation_receipt(terminal)["receipt_state"] == "TERMINAL"
    with pytest.raises(C.ContractError, match="supersede"):
        C.validate_mutation_receipt({**terminal, "supersedes_receipt_digest": None})


def _bundle(member_ids=("alpha", "beta")):
    documents = {name: C.canonical_json_bytes({"$id": name, "type": "object"}) for name in member_ids}
    expected = {name: (f"codec.{name}", f"flowlib.{name}") for name in member_ids}
    members = [
        {"schema_id": name, "schema_digest": C.sha256_digest(documents[name]), "codec_id": expected[name][0], "runtime_module": expected[name][1]}
        for name in reversed(member_ids)
    ]
    value = {
        "bundle_version": "2.0.0", "contract_version": 2, "minimum_runtime_version": "0.12.1",
        "members": members, "platform_allowlist_digest": DIGEST, "created_by_release": "0.12.1",
    }
    return value, expected, documents


def test_bundle_requires_exact_code_owned_inventory_and_is_order_independent():
    value, expected, documents = _bundle()
    first = C.validate_contract_bundle(value, expected_members=expected, schema_documents=documents, round_trip_checker=lambda member: True)
    second = C.validate_contract_bundle({**value, "members": list(reversed(value["members"]))}, expected_members=expected, schema_documents=documents)
    assert first.digest == second.digest


@pytest.mark.parametrize("mutation", [
    lambda value: value["members"].pop(),
    lambda value: value["members"].append(dict(value["members"][0])),
    lambda value: value["members"][0].update({"unknown": True}),
    lambda value: value["members"][0].update({"runtime_module": "wrong"}),
    lambda value: value["members"][0].update({"schema_digest": DIGEST}),
])
def test_bundle_rejects_missing_duplicate_unknown_and_mismatch(mutation):
    value, expected, documents = _bundle()
    mutation(value)
    with pytest.raises(C.ContractError):
        C.validate_contract_bundle(value, expected_members=expected, schema_documents=documents)


def test_bundle_rejects_codec_round_trip_failure_and_contract_kernel_has_no_external_process_dependency():
    value, expected, documents = _bundle()
    with pytest.raises(C.ContractError, match="round-trip"):
        C.validate_contract_bundle(value, expected_members=expected, schema_documents=documents, round_trip_checker=lambda member: False)
    source = inspect.getsource(C)
    assert "import subprocess" not in source
    assert "import os" not in source
