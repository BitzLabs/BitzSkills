"""FLW-NFR-014 / FLW-TSK-113 atomic bundle promotion."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "plugins" / "bitz-flow" / "skills" / "flow-core"
sys.path.insert(0, str(SKILL / "scripts"))

from flowlib import worktree_contract as C  # noqa: E402
from flowlib import worktree_promotion as P  # noqa: E402

DIGEST = "sha256:" + "a" * 64
OPERATION = "sha256:" + "b" * 64


def bundle():
    documents = {"alpha": C.canonical_json_bytes({"$id": "alpha", "type": "object"})}
    expected = {"alpha": ("codec.alpha", "flowlib.alpha")}
    value = {
        "bundle_version": "2.0.0", "contract_version": 2,
        "minimum_runtime_version": "0.12.3",
        "members": [{"schema_id": "alpha", "schema_digest": C.sha256_digest(documents["alpha"]),
                     "codec_id": "codec.alpha", "runtime_module": "flowlib.alpha"}],
        "platform_allowlist_digest": DIGEST, "created_by_release": "0.12.3",
    }
    return value, expected, documents


def promote(root, **changes):
    value, expected, documents = bundle()
    args = dict(bundle=value, expected_members=expected, schema_documents=documents,
                expected_generation="0", runtime_identity_digest=DIGEST,
                recheck=lambda: ("0", DIGEST))
    args.update(changes)
    return P.promote_bundle(root, **args)


def test_normal_promotion_publishes_one_complete_current_pointer(tmp_path):
    pointer = promote(tmp_path)
    assert pointer["state"] == "ACTIVE" and pointer["generation"] == "1"
    current = json.loads((tmp_path / P.PROMOTION_RELATIVE_PATH / "current.json").read_text())
    assert current == pointer


def test_active_marker_registration_rechecks_current_bundle_under_promotion_lock(tmp_path):
    pointer = promote(tmp_path)
    with pytest.raises(P.PromotionError) as caught:
        P.register_active_operation(
            tmp_path, operation_id=OPERATION, bundle_digest=DIGEST, verify_current=True,
        )
    assert caught.value.code == "STALE"
    active = tmp_path / P.PROMOTION_RELATIVE_PATH / "active"
    assert not active.exists() or not list(active.iterdir())

    P.register_active_operation(
        tmp_path, operation_id=OPERATION,
        bundle_digest=pointer["bundle_digest"], verify_current=True,
    )
    P.abort_active_operation(
        tmp_path, operation_id=OPERATION, bundle_digest=pointer["bundle_digest"],
    )
    assert not list(active.iterdir())


def test_active_operation_blocks_promotion_under_same_lock(tmp_path):
    P.register_active_operation(tmp_path, operation_id=OPERATION, bundle_digest=DIGEST)
    with pytest.raises(P.PromotionError) as caught:
        promote(tmp_path)
    assert caught.value.code == "BLOCKED_ACTIVE_OPERATION"
    P.release_active_operation(tmp_path, operation_id=OPERATION, terminal_receipt_digest=DIGEST)
    assert promote(tmp_path)["generation"] == "1"


@pytest.mark.parametrize("recheck", [lambda: ("1", DIGEST), lambda: ("0", "sha256:" + "c" * 64)])
def test_generation_or_runtime_swap_before_publish_is_stale(tmp_path, recheck):
    with pytest.raises(P.PromotionError) as caught:
        promote(tmp_path, recheck=recheck)
    assert caught.value.code == "STALE"
    assert not (tmp_path / P.PROMOTION_RELATIVE_PATH / "current.json").exists()


def test_member_or_codec_mismatch_never_creates_promotion_namespace(tmp_path):
    value, expected, documents = bundle()
    value["members"][0]["codec_id"] = "codec.wrong"
    with pytest.raises(C.ContractError):
        P.promote_bundle(
            tmp_path, bundle=value, expected_members=expected, schema_documents=documents,
            expected_generation="0", runtime_identity_digest=DIGEST,
            recheck=lambda: ("0", DIGEST),
        )
    assert not (tmp_path / P.PROMOTION_RELATIVE_PATH).exists()


@pytest.mark.parametrize("step", ["temp-written", "file-fsynced", "renamed", "dir-fsynced"])
def test_current_pointer_crash_is_absent_or_complete_never_partial(tmp_path, step):
    def crash(current, path):
        if "current.json" in path.name and current == step:
            raise RuntimeError("crash")
    with pytest.raises(RuntimeError, match="crash"):
        promote(tmp_path, step_hook=crash)
    current = tmp_path / P.PROMOTION_RELATIVE_PATH / "current.json"
    if current.exists():
        value = json.loads(current.read_text())
        assert value["state"] == "ACTIVE" and set(value) == {
            "contract_version", "generation", "bundle_digest", "runtime_identity_digest", "state"
        }


def test_promotion_module_does_not_launch_git_or_unknown_artifact(tmp_path):
    source = (SKILL / "scripts/flowlib/worktree_promotion.py").read_text()
    assert "subprocess" not in source
    assert "Popen(" not in source
