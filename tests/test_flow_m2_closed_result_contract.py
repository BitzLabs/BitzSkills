"""FLW-REV-028:GP-005 — 公開経路へ traceback を出さないことを検証する。

`FLW-REV-028:SYN-007`（P0）。`collision_key` は case-insensitive のとき
`folded_component` を必須とするが probe に導出経路が無く `plan()` も渡さないため、
再現すると `ContractError` が送出された。`ContractError` は `ValueError` 派生であり
CLI が捕捉する 3 型（`WorktreeChildTimeoutError` / `WorktreeUnsupportedPlatformError` /
`WorktreeRuntimeError`）のいずれでもないため **closed result ではなく traceback** に
なっていた。

これは特定 1 経路の問題ではなく **公開 result 契約の穴** である。例外型を列挙する方式は
穴が開くため、dispatcher 単位で取りこぼしを受け止める。本テストは公開経路
（`flow.py` の別 process 起動）から traceback が出ないことを直接確認する。
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "plugins" / "bitz-flow" / "skills" / "flow-core"
FLOW = SKILL / "scripts" / "flow.py"
sys.path.insert(0, str(SKILL / "scripts"))

from flowlib import worktree_platform as PF  # noqa: E402


def _flow(*args, cwd: Path | None = None):
    """production 既定 dispatcher を別 process で起動する（handler 注入なし）。"""
    return subprocess.run(
        [sys.executable, str(FLOW), *args, "--format", "json"],
        capture_output=True, text=True, cwd=str(cwd) if cwd else None,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    path = tmp_path / "repo"
    path.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(path)], check=True)
    for key, value in (("user.email", "t@example.com"), ("user.name", "t")):
        subprocess.run(["git", "-C", str(path), "config", key, value], check=True)
    (path / "a.txt").write_text("a\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(path), "add", "a.txt"], check=True)
    subprocess.run(["git", "-C", str(path), "commit", "-qm", "chore: init"], check=True)
    return path


# --- traceback を出さないこと -------------------------------------------------


@pytest.mark.parametrize("argv,label", [
    (("repo", "inspect"), "m0-read"),
    (("git", "status"), "m0-status"),
    (("worktree", "create"), "gated-write"),
    (("worktree", "audit"), "gated-read"),
    (("issue", "create"), "unknown-milestone"),
    (("bogus", "action"), "unknown-domain"),
])
def test_public_dispatcher_never_emits_a_traceback(repo, argv, label):
    """公開経路の出力が常に closed result であり traceback を含まないこと。"""
    proc = _flow(*argv, "--repo", str(repo))
    assert "Traceback (most recent call last)" not in proc.stderr, (
        f"{label}: traceback が公開経路へ出た\n{proc.stderr[:400]}"
    )
    payload = json.loads(proc.stdout)
    assert payload["code"], f"{label}: closed result になっていない"


# NUL バイトは execve が受け付けないため、いかなる実起動経路からも到達しない。
# 到達可能な悪性入力だけを並べる。
@pytest.mark.parametrize("argv,label", [
    (("repo", "inspect", "--repo", "/nonexistent/path"), "missing-repo"),
    (("repo", "inspect", "--timeout-seconds", "-1"), "negative-timeout"),
    (("repo", "inspect", "--timeout-seconds", "inf"), "inf-timeout"),
    (("git", "diff-summary", "--base", "--not-a-ref"), "flag-like-ref"),
    (("git", "diff-summary", "--base", "a" * 5000), "very-long-ref"),
    (("repo", "inspect", "--snapshot", "not-a-digest"), "bad-snapshot"),
    (("worktree", "create", "--path", "../../escape"), "path-escape"),
    (("worktree", "create", "--path", "line\nbreak"), "newline-in-path"),
])
def test_hostile_input_still_produces_a_closed_result(repo, argv, label):
    """到達可能な悪性入力でも traceback にせず closed result へ写すこと。"""
    proc = _flow(*argv, "--repo", str(repo)) if "--repo" not in argv else _flow(*argv)
    assert "Traceback (most recent call last)" not in proc.stderr, (
        f"{label}: traceback が公開経路へ出た\n{proc.stderr[:400]}"
    )
    if proc.stdout.strip():
        payload = json.loads(proc.stdout)
        assert payload["code"], f"{label}: closed result になっていない"


def test_dispatcher_has_a_catch_all_for_unexpected_exceptions():
    """例外型の列挙ではなく handler の外側で取りこぼしを受け止めること。

    型を列挙する方式は穴が開く（`ContractError` が実際に漏れた）。
    """
    source = (SKILL / "scripts" / "flowlib" / "cli.py").read_text(encoding="utf-8")
    marker = source[source.index("result, view = handler(root, args, started)"):]
    head = marker[:900]
    assert "except Exception" in head, "dispatcher に取りこぼしの網が無い"
    assert "result-indeterminate" in head


def test_closed_result_does_not_leak_internal_details(repo):
    """公開 result へ内部型名・traceback・絶対 path 断片を載せないこと。"""
    proc = _flow("worktree", "create", "--repo", str(repo))
    body = proc.stdout
    for leaked in ("ContractError", "WorktreeRuntimeError", "Traceback",
                   "flowlib/", "site-packages"):
        assert leaked not in body, f"内部情報が公開 result へ漏れている: {leaked}"


# --- case-insensitive を閉じること -------------------------------------------


def test_case_insensitive_is_closed_instead_of_raising():
    """case-insensitive 環境を `UNSUPPORTED_FILESYSTEM` へ閉じること。

    folding 規則を新設せず閉じる（裁定 2026-08-24 案 B）。実物の case-insensitive
    volume を観測できない環境で規則を作れば、また検証していない性質の主張になる。
    """
    profiles = PF.load_support_profiles(PF.SUPPORT_REGISTRY_PATH)
    observation = PF.PlatformObservation(
        platform="linux", filesystem_type="ext4", filesystem_class="local",
        owner_principal="1000", owner_matches=True, acl_owner_only=True,
        non_follow_walk=True, resource_kind="directory",
        resource_identity="sha256:" + "a" * 64,
        native_component=PF.native_component_from_posix(b"w1").as_mapping(),
        case_semantics="insensitive",       # ← ここだけが supported 環境と違う
        os_lock=True, file_durability=True, directory_durability=True,
        child_supervision=True,
    )
    evidence = PF.evaluate_platform(observation, profiles=profiles)
    assert not evidence.supported
    assert "case-insensitive-unsupported" in evidence.reasons


# --- 保証 scope ---------------------------------------------------------------


@pytest.mark.parametrize("platform", ["macos", "windows"])
def test_out_of_scope_platforms_are_closed_with_a_reason(platform):
    """保証対象外の platform を理由付きで不支持にすること（実装は残す）。"""
    profiles = PF.load_support_profiles(PF.SUPPORT_REGISTRY_PATH)
    observation = PF.PlatformObservation(
        platform=platform,
        filesystem_type="apfs" if platform == "macos" else "ntfs",
        filesystem_class="local",
        owner_principal="1000", owner_matches=True, acl_owner_only=True,
        non_follow_walk=True, resource_kind="directory",
        resource_identity="sha256:" + "a" * 64,
        native_component=(
            PF.native_component_from_posix(b"w1").as_mapping() if platform == "macos"
            else PF.native_component_from_windows("w1").as_mapping()
        ),
        case_semantics="sensitive",
        os_lock=True, file_durability=True, directory_durability=True,
        child_supervision=True,
    )
    evidence = PF.evaluate_platform(observation, profiles=profiles)
    assert not evidence.supported
    assert "platform-out-of-scope" in evidence.reasons


def test_scope_is_linux_only_and_implementations_are_retained():
    """保証は Linux のみ。probe 実装は削除しないこと（再開のため）。"""
    assert PF.SUPPORTED_SCOPE == frozenset({"linux"})
    assert PF.PLATFORMS == frozenset({"linux", "macos", "windows"})
    source = (SKILL / "scripts" / "flowlib" / "worktree_platform.py").read_text(encoding="utf-8")
    assert "_macos_filesystem_type" in source
    assert "_windows_volume" in source
