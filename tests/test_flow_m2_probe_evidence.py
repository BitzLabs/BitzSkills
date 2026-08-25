"""FLW-REV-028:GP-006 / GP-008 — probe が検証していない性質を主張しないこと。

セカンドオピニオン（codex / antigravity）が指摘し、実測で確認した2件。

- `GP-006`: probe は `Path.resolve()` / `os.stat()` で symlink を追跡する一方、
  `non_follow_walk` は `O_NOFOLLOW` 等の**属性存在だけ**で True にしていた。
  symlink 経由の 0700 ディレクトリが `SUPPORTED` を返した。§1.2 は「非 symlink/
  reparse-point の namespace」を信頼すると規定する。
- `GP-008`: `_case_semantics` は**絶対 path 全体**を swapcase して存在確認していたため
  mount 単位の semantics を測れなかった。誤って `sensitive` と判定すると
  `collision_key` が case alias を畳めず、同一資源への競合が直列化されない。
  `_linux_filesystem_type` は st_dev 先頭一致で bind mount に弱かった。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "plugins" / "bitz-flow" / "skills" / "flow-core"
sys.path.insert(0, str(SKILL / "scripts"))

from flowlib import worktree_platform as PF  # noqa: E402


@pytest.fixture
def owner_only(allowlisted_root: Path) -> Path:
    """allowlist 済み filesystem 上の owner-only ディレクトリ（`FLW-REV-028:GP-007`）。"""
    target = allowlisted_root / "real"
    target.mkdir(mode=0o700)
    os.chmod(target, 0o700)
    return target


# --- GP-006: symlink の実証検出 ----------------------------------------------


def test_direct_owner_only_directory_is_supported(owner_only):
    """陽性対照。symlink を含まない path は支持されること（過剰拒否の検出）。"""
    evidence = PF.platform_evidence_for(owner_only)
    assert evidence.supported, evidence.reasons


def test_symlinked_root_is_refused(allowlisted_root, owner_only):
    """**本 issue の中心**。symlink 経由の root を支持しないこと。"""
    link = allowlisted_root / "link"
    link.symlink_to(owner_only)
    evidence = PF.platform_evidence_for(link)
    assert not evidence.supported
    assert "non-follow-walk-unavailable" in evidence.reasons


def test_symlink_in_an_ancestor_is_refused(allowlisted_root, owner_only):
    """祖先が symlink でも拒否すること（末端だけを見ない）。"""
    link = allowlisted_root / "link"
    link.symlink_to(owner_only)
    evidence = PF.platform_evidence_for(link / "not-created-yet")
    assert not evidence.supported
    assert "non-follow-walk-unavailable" in evidence.reasons


def test_symlink_proof_inspects_the_requested_path_not_the_resolved_one():
    """解決後の path を検査しても常に symlink 無しになる。要求された path を見ること。"""
    source = (SKILL / "scripts" / "flowlib" / "worktree_platform.py").read_text(encoding="utf-8")
    body = source[source.index("def probe_platform("):]
    proof_at = body.index("path_is_symlink_free(")
    resolve_at = body.index(".resolve(strict=False)")
    assert proof_at < resolve_at, "resolve() の後に symlink 実証を行っている"


@pytest.mark.parametrize("missing", ["not-created-yet", "a/b/c"])
def test_nonexistent_create_target_is_not_treated_as_a_symlink(owner_only, missing):
    """未作成の create target を symlink 扱いしないこと。"""
    assert PF.path_is_symlink_free(owner_only / missing) is True


# --- GP-008: mount 局所の case semantics -------------------------------------


def test_case_semantics_uses_the_entry_name_not_the_whole_path(tmp_path):
    """祖先の case 差に引きずられないこと。"""
    parent = tmp_path / "Mixed"
    parent.mkdir()
    target = parent / "Sub"
    target.mkdir()
    # 全 path 反転では判定できないが、entry 名だけなら判定できる。
    assert PF._case_semantics(target) in {"sensitive", "insensitive"}


def test_same_named_sibling_is_not_mistaken_for_case_insensitivity(tmp_path):
    """同名の**別 entry** を insensitive と誤認しないこと。

    case-sensitive fs では `Sub` と `sUB` は別 entry として共存できる。存在確認だけで
    insensitive と判定すると、`collision_key` が別資源を同一へ畳んでしまう。
    """
    parent = tmp_path / "p"
    parent.mkdir()
    (parent / "Sub").mkdir()
    try:
        (parent / "sUB").mkdir()
    except FileExistsError:
        pytest.skip("case-insensitive filesystem のため対照を作れない")
    assert PF._case_semantics(parent / "Sub") == "sensitive"


def test_case_semantics_returns_none_without_letters(tmp_path):
    """判定材料が無ければ推測せず None を返すこと。"""
    target = tmp_path / "1234"
    target.mkdir()
    assert PF._case_semantics(target) is None


def test_case_semantics_unobservable_closes_instead_of_guessing(tmp_path):
    """判定不能を supported へ格上げしないこと。"""
    target = tmp_path / "5678"
    target.mkdir(mode=0o700)
    os.chmod(target, 0o700)
    evidence = PF.platform_evidence_for(target)
    assert not evidence.supported
    assert "case-semantics-unobservable" in evidence.reasons


# --- GP-008: mount point 最長一致 --------------------------------------------


def test_filesystem_type_resolves_the_deepest_mount(tmp_path):
    """実行中 OS で最下層の mount 種別を返すこと。"""
    resolved = PF._linux_filesystem_type(tmp_path)
    assert resolved, "mount 種別を解決できていない"
    assert resolved == resolved.lower()


def test_mountinfo_octal_escapes_are_decoded():
    """mount point の 8 進 escape を解くこと（`\\040` = 空白）。"""
    assert PF._unescape_mountinfo(r"/mnt/with\040space") == "/mnt/with space"
    assert PF._unescape_mountinfo("/plain/path") == "/plain/path"


# bind mount を作るには root が要り実環境で対照できないため、選択ロジックを
# 合成 mountinfo で検証する。第 5 列が mount point、`-` の次が fstype。
_ROOT_LINE = "1 0 8:1 / / rw,relatime shared:1 - ext4 /dev/sda1 rw"
_TMP_LINE = "2 1 8:1 / /tmp rw,relatime shared:2 - tmpfs tmpfs rw"
_BIND_LINE = "3 1 8:1 /srv/data /tmp/bind rw,relatime shared:3 - xfs /dev/sdb1 rw"


@pytest.mark.parametrize("order,label", [
    ((_ROOT_LINE, _TMP_LINE, _BIND_LINE), "深い順が後"),
    ((_BIND_LINE, _TMP_LINE, _ROOT_LINE), "深い順が先"),
    ((_TMP_LINE, _BIND_LINE, _ROOT_LINE), "混在"),
])
def test_mount_selection_takes_the_longest_match_regardless_of_order(order, label):
    """最長一致で選び行順に依存しないこと（先頭一致だと親を返す）。"""
    assert PF.select_mount_type(order, Path("/tmp/bind/x")) == "xfs", label
    assert PF.select_mount_type(order, Path("/tmp/other")) == "tmpfs", label
    assert PF.select_mount_type(order, Path("/var/log")) == "ext4", label


def test_mount_selection_ignores_malformed_lines():
    """壊れた行を無視して選択を続けること。"""
    lines = ("garbage", "1 0 8:1 / /", _TMP_LINE, "2 1 8:1 / /tmp rw -")
    assert PF.select_mount_type(lines, Path("/tmp/x")) == "tmpfs"


def test_mount_selection_returns_none_when_nothing_matches():
    """一致する mount が無ければ推測せず None を返すこと。"""
    assert PF.select_mount_type((_TMP_LINE,), Path("/var/log")) is None
