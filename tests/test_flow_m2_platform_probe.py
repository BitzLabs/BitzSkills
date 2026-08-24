"""SI-FLW-084 — 実環境 platform probe と production 経路への結線を検証する。

`FLW-REV-027:SYN-001`（P0）は、`PlatformObservation` を構築する production コードが
存在せず、`worktree_runtime.plan()` が必ず `platform evidence is required` で停止すると
判定した。`evaluate_platform()` の呼出元は `tests/` だけだった。

本テストは次を検証する。

- **実観測**: 実行中 OS で probe が実際に filesystem を観測すること（fixture 注入なし）。
- **fail-closed**: network / 未知 / 観測不能を supported へ格上げしないこと。
- **例外を出さない**: probe はどんな入力でも例外を送出せず closed evidence を返すこと。
- **結線**: `plan()` が evidence 未指定でも probe を使い、doctor と同じ生成器を通ること。

他 OS の分類ロジックは構造 test で検査する。**それらは実観測ではない**（実行中 OS 以外の
実観測は `FLW-DSN-017` §13.5 のとおり未実施である）。
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / "plugins" / "bitz-flow" / "skills" / "flow-core"
sys.path.insert(0, str(SKILL / "scripts"))

from flowlib import worktree_operability as OP  # noqa: E402
from flowlib import worktree_platform as PF  # noqa: E402
from flowlib import worktree_runtime as WR  # noqa: E402


@pytest.fixture
def owner_only_dir(tmp_path: Path) -> Path:
    target = tmp_path / "root"
    target.mkdir(mode=0o700)
    os.chmod(target, 0o700)
    return target


# --- 実観測（実行中 OS） -----------------------------------------------------


def test_probe_observes_the_real_filesystem(owner_only_dir):
    """probe が実環境を観測すること（固定値でも fixture 注入でもない）。"""
    evidence = PF.platform_evidence_for(owner_only_dir)
    observation = evidence.observation
    assert observation.platform == PF.current_platform()
    assert observation.filesystem_type not in ("", "unknown"), (
        f"filesystem を観測できていない: {evidence.reasons}"
    )
    assert observation.filesystem_class == "local"
    assert observation.resource_kind == "directory"
    # owner-only な local ディレクトリは supported になるはず。
    assert evidence.supported, f"想定外の不支持: {evidence.reasons}"


def test_probe_detects_non_owner_only_directory(tmp_path):
    """world-readable な root は信頼境界の外なので supported にしない。"""
    target = tmp_path / "open"
    target.mkdir(mode=0o755)
    os.chmod(target, 0o755)
    evidence = PF.platform_evidence_for(target)
    assert not evidence.supported
    assert "acl-not-owner-only" in evidence.reasons


def test_probe_anchors_a_nonexistent_create_target_on_its_parent(owner_only_dir):
    """create の対象はまだ存在しない。親を anchor にして観測できること。"""
    evidence = PF.platform_evidence_for(owner_only_dir / "not-created-yet")
    assert evidence.supported, evidence.reasons


# --- fail-closed -------------------------------------------------------------


@pytest.mark.parametrize("filesystem,expected_class", [
    ("nfs4", "network"), ("cifs", "network"), ("9p", "network"),
    ("fuse.sshfs", "network"), ("virtiofs", "network"),
    ("ext4", "local"), ("apfs", "local"), ("ntfs", "local"),
    (None, "unknown"), ("", "unknown"), ("unknown", "unknown"),
])
def test_filesystem_classification_never_upgrades_to_local(filesystem, expected_class):
    """network / 未知を local へ格上げしないこと。"""
    _, actual = PF.classify_filesystem(filesystem)
    assert actual == expected_class


def test_unknown_fuse_variants_are_treated_as_network():
    """未知の fuse.* を local と誤認しないこと。"""
    _, actual = PF.classify_filesystem("fuse.something-new")
    assert actual == "network"


@pytest.mark.parametrize("path", [
    pytest.param("/nonexistent/deeply/nested/path", id="missing"),
    pytest.param("", id="empty"),
    pytest.param("/dev/null", id="device-node"),
    pytest.param("\x00bad", id="nul-byte"),
])
def test_probe_never_raises(path):
    """観測不能でも例外にせず closed evidence へ閉じること。"""
    evidence = PF.platform_evidence_for(path)
    assert evidence.support_code in (PF.SUPPORTED, PF.UNSUPPORTED_FILESYSTEM)
    if not evidence.supported:
        assert evidence.reasons, "不支持なら理由を必ず持つこと"


def test_unreadable_registry_closes_instead_of_raising(monkeypatch, tmp_path):
    """support registry が読めない場合も例外にしないこと。"""
    monkeypatch.setattr(PF, "SUPPORT_REGISTRY_PATH", tmp_path / "missing.json")
    evidence = PF.platform_evidence_for(tmp_path)
    assert not evidence.supported
    assert "support-registry-unreadable" in evidence.reasons


# --- production 経路への結線 -------------------------------------------------


def test_plan_no_longer_requires_injected_platform_evidence():
    """`platform evidence is required` で必ず停止する経路が消えたこと。

    `FLW-REV-027:SYN-001` の核心。production から evidence を渡す経路が無いまま
    公開集合へ戻すと、この文言で必ず例外停止していた。
    """
    source = (SKILL / "scripts" / "flowlib" / "worktree_runtime.py").read_text(encoding="utf-8")
    assert "platform evidence is required" not in source
    assert "PF.platform_evidence_for(" in source


def test_plan_and_doctor_share_one_evidence_generator():
    """doctor が緑でも plan が別判定になる食い違いを作らないこと。"""
    flowlib = SKILL / "scripts" / "flowlib"
    runtime = (flowlib / "worktree_runtime.py").read_text(encoding="utf-8")
    operability = (flowlib / "worktree_operability.py").read_text(encoding="utf-8")
    assert "platform_evidence_for(" in runtime
    assert "platform_evidence_for(" in operability


def test_doctor_reports_observed_evidence_not_a_self_declaration(tmp_path):
    """doctor が `requires-runtime-evidence` の自己申告を返さないこと。"""
    operability = (SKILL / "scripts" / "flowlib" / "worktree_operability.py")
    source = "\n".join(
        line for line in operability.read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith("#")
    )
    assert "requires-runtime-evidence" not in source


def test_unsupported_platform_is_not_collapsed_into_blocked():
    """環境が対象外であることを `BLOCKED / conflict` へ丸めないこと。"""
    assert issubclass(WR.WorktreeUnsupportedPlatformError, ValueError)
    assert not issubclass(WR.WorktreeUnsupportedPlatformError, WR.WorktreeRuntimeError)
    error = WR.WorktreeUnsupportedPlatformError(("filesystem-class-network",))
    assert error.reasons == ("filesystem-class-network",)


def test_cli_maps_unsupported_platform_to_a_closed_result():
    """CLI が新しい例外を closed result へ写すこと（traceback にしない）。"""
    source = (SKILL / "scripts" / "flowlib" / "cli.py").read_text(encoding="utf-8")
    assert "WorktreeUnsupportedPlatformError" in source
    assert "unsupported-filesystem" in source


# --- registry との整合 -------------------------------------------------------


def test_registry_declares_every_supported_platform():
    """probe が返しうる platform 判別子が registry に揃っていること。"""
    profiles = PF.load_support_profiles(PF.SUPPORT_REGISTRY_PATH)
    assert set(profiles) == set(PF.PLATFORMS)


def test_child_supervision_must_match_the_declared_primitive(owner_only_dir):
    """registry の宣言と実際に使える primitive が食い違えば supported にしないこと。"""
    profiles = dict(PF.load_support_profiles(PF.SUPPORT_REGISTRY_PATH))
    current = PF.current_platform()
    declared = profiles[current]
    profiles[current] = PF.SupportProfile(
        platform=declared.platform,
        filesystem_types=declared.filesystem_types,
        owner_model=declared.owner_model,
        lock_primitive=declared.lock_primitive,
        file_durability=declared.file_durability,
        directory_durability=declared.directory_durability,
        child_supervision="job-object" if current != "windows" else "waitpid",
    )
    evidence = PF.probe_platform(owner_only_dir, profiles=profiles)
    assert not evidence.supported
    assert "child-supervision-unavailable" in evidence.reasons
