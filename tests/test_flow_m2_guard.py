"""M2-1 guard core fault fixtures（FLW-NFR-006 / FLW-CON-005 / FLW-CON-006）。"""

import os
import sys
import unicodedata
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / "plugins" / "bitz-flow" / "skills" / "flow-core"
sys.path.insert(0, str(SKILL / "scripts"))

from flowlib import guard as GD  # noqa: E402


class _Tokens:
    def __init__(self):
        self.value = 0

    def __call__(self, _key):
        self.value += 1
        return self.value


@pytest.fixture
def bound_worktree(tmp_path):
    common = tmp_path / "repo" / ".git"
    registry = common / "worktrees" / "wt-1"
    worktree_root = tmp_path / "worktrees"
    worktree = worktree_root / "wt-1"
    registry.mkdir(parents=True)
    worktree.mkdir(parents=True)
    (registry / "gitdir").write_text(str(worktree / ".git") + "\n", encoding="utf-8")
    (worktree / ".git").write_text(f"gitdir: {registry}\n", encoding="utf-8")
    return common, registry, worktree_root, worktree


def _targets(bound_worktree):
    common, registry, root, worktree = bound_worktree
    return GD.worktree_guard_targets(
        common_dir=common,
        worktree_root=root,
        worktree_path=worktree,
        registry_entry=registry,
        local_ref="refs/heads/feat/wt-1",
        case_sensitive=True,
    )


def test_FLW_NFR_006_M2_FLT_001_reverse_request_is_canonical(bound_worktree):
    targets = _targets(bound_worktree)
    manager = GD.TargetGuardManager()
    held, failure = manager.acquire(
        list(reversed(targets)), operation_id="m2-1", next_token=_Tokens()
    )
    assert failure is None
    assert [target.canonical_key for target in held.targets] == sorted(
        target.canonical_key for target in targets
    )


def test_FLW_NFR_006_M2_FLT_002_worktree_guard_always_includes_index(bound_worktree):
    kinds = {target.kind for target in _targets(bound_worktree)}
    assert kinds == {
        GD.KIND_WORKTREE_DIR,
        GD.KIND_WORKTREE_REGISTRY,
        GD.KIND_LOCAL_REF,
        GD.KIND_INDEX,
    }


def test_FLW_NFR_006_M2_FLT_003_discard_blocks_stage_on_same_index(bound_worktree):
    targets = _targets(bound_worktree)
    index = next(target for target in targets if target.kind == GD.KIND_INDEX)
    manager = GD.TargetGuardManager()
    discard, failure = manager.acquire(targets, operation_id="discard", next_token=_Tokens())
    assert failure is None and discard is not None
    stage, failure = manager.acquire([index], operation_id="stage", next_token=_Tokens())
    assert stage is None and failure.code == GD.CODE_BLOCKED


def test_FLW_CON_006_M2_FLT_004_literal_worktree_id_is_rejected(bound_worktree):
    common = bound_worktree[0]
    with pytest.raises(TypeError, match="derive_worktree_id"):
        GD.canonical_worktree_index_target(common, "wt-1")


def test_FLW_CON_006_M2_FLT_005_binding_mismatch_is_orphan(bound_worktree):
    common, registry, _root, worktree = bound_worktree
    (worktree / ".git").write_text(f"gitdir: {registry.parent / 'other'}\n", encoding="utf-8")
    with pytest.raises(GD.CanonicalizationError, match="相互参照"):
        GD.verify_worktree_binding(common, registry, worktree)


def test_FLW_NFR_006_M2_FLT_006_aliases_converge_by_file_identity(bound_worktree):
    _common, _registry, root, worktree = bound_worktree
    alias = root / "alias"
    alias.symlink_to(worktree, target_is_directory=True)
    direct = GD.canonical_worktree_dir_target(worktree, approved_root=root, case_sensitive=True)
    via_alias = GD.canonical_worktree_dir_target(alias, approved_root=root, case_sensitive=True)
    assert direct == via_alias


def test_FLW_CON_006_M2_FLT_007_parent_traversal_is_rejected(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    with pytest.raises(GD.CanonicalizationError):
        GD.canonical_worktree_dir_target(
            root / ".." / "outside", approved_root=root, case_sensitive=True
        )


def test_FLW_CON_006_M2_FLT_007_symlink_escape_is_rejected(tmp_path):
    root = tmp_path / "root"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (root / "escape").symlink_to(outside, target_is_directory=True)
    with pytest.raises(GD.CanonicalizationError, match="escape"):
        GD.canonical_worktree_dir_target(
            root / "escape", approved_root=root, case_sensitive=True
        )


def test_FLW_CON_006_M2_FLT_007_hardlink_is_not_a_worktree_directory(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    source = tmp_path / "source"
    source.write_text("x", encoding="utf-8")
    os.link(source, root / "alias")
    with pytest.raises(GD.CanonicalizationError, match="directory"):
        GD.canonical_worktree_dir_target(
            root / "alias", approved_root=root, case_sensitive=True
        )


def test_FLW_CON_006_M2_FLT_007_device_namespace_is_rejected(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    with pytest.raises(GD.CanonicalizationError, match="device namespace"):
        GD.canonical_worktree_dir_target(
            r"\\?\C:\repo\wt", approved_root=root, case_sensitive=True
        )


def test_FLW_CON_005_M2_FLT_008_root_symlink_replacement_changes_identity(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    root_link = tmp_path / "approved"
    root_link.symlink_to(first, target_is_directory=True)
    before = GD.canonical_worktree_dir_target("wt", approved_root=root_link, case_sensitive=True)
    root_link.unlink()
    root_link.symlink_to(second, target_is_directory=True)
    after = GD.canonical_worktree_dir_target("wt", approved_root=root_link, case_sensitive=True)
    assert before != after


def test_FLW_NFR_006_M2_FLT_009_absent_case_aliases_converge(tmp_path):
    root = tmp_path / "RootWithLetters"
    root.mkdir()
    upper = GD.canonical_worktree_dir_target("Feature/Wt", approved_root=root, case_sensitive=False)
    lower = GD.canonical_worktree_dir_target("feature/wt", approved_root=root, case_sensitive=False)
    assert upper == lower


def test_FLW_NFR_006_M2_FLT_009_unknown_case_rule_blocks(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    with pytest.raises(GD.CanonicalizationError, match="case感度"):
        GD.canonical_worktree_dir_target("wt", approved_root=root, case_sensitive=None)


def test_FLW_CON_006_M2_FLT_057_unicode_aliases_converge(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    nfc = unicodedata.normalize("NFC", "café")
    nfd = unicodedata.normalize("NFD", "café")
    assert GD.canonical_worktree_dir_target(nfc, approved_root=root, case_sensitive=True) == (
        GD.canonical_worktree_dir_target(nfd, approved_root=root, case_sensitive=True)
    )


@pytest.mark.parametrize("alias", ["CON", "name:stream", "folder. ", "PROGRA~1"])
def test_FLW_CON_006_M2_FLT_057_windows_aliases_fail_closed(tmp_path, alias):
    root = tmp_path / "root"
    root.mkdir()
    with pytest.raises(GD.CanonicalizationError):
        GD.canonical_worktree_dir_target(alias, approved_root=root, case_sensitive=True)
