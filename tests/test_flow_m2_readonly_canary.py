"""M2 read-only 限定公開の production black-box 証跡（裁定 2026-08-24）。

`FLW-CON-008` が要求する「production 既定 dispatcher を起点とする black-box」は、
公開集合に無い operation では**原理的に取得できない**。`FLW-REV-028` の 7 観点で
`実証済み` が 0 件だった主因はここにある。

read-only 3 operation を限定公開したことで、`worktree.doctor` / `audit` /
`verify-receipt` について初めて production 経路の実証が取れる。本ファイルは
`flow.py` を別 process として起動し、handler 注入を一切使わない。

裁定記録: `.spec/reports/decision-2026-08-24-m2-readonly-canary.md`
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

from flowlib import worktree_promotion as P  # noqa: E402

READ_ONLY = ("doctor", "audit", "verify-receipt")


def _flow(*args, repo: Path) -> tuple[dict, int]:
    """production 既定 dispatcher を別 process で起動する（handler 注入なし）。"""
    proc = subprocess.run(
        [sys.executable, str(FLOW), "--repo", str(repo), *args, "--format", "json"],
        capture_output=True, text=True,
    )
    return json.loads(proc.stdout), proc.returncode


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


def _common_dir(repo: Path) -> Path:
    out = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--path-format=absolute", "--git-common-dir"],
        capture_output=True, text=True, check=True).stdout.strip()
    return Path(out)


# --- production 到達性 --------------------------------------------------------


@pytest.mark.parametrize("action", READ_ONLY)
def test_read_only_operation_is_reachable_from_the_production_dispatcher(repo, action):
    """**本 canary の中心**。公開集合に入り production から到達すること。"""
    payload, _ = _flow("worktree", action, repo=repo)
    assert payload["operation"] == f"worktree.{action}"
    assert payload["data"].get("cause") != "command-unavailable", (
        f"{action} が公開されていない"
    )


@pytest.mark.parametrize("action", ["create", "resume", "reconcile", "finish", "discard"])
def test_write_operation_stays_unreachable(repo, action):
    """write class は引き続き到達しないこと（縮退規則3 の本体）。"""
    payload, code = _flow("worktree", action, repo=repo)
    assert code == 8
    assert payload["code"] == "UNSUPPORTED"
    assert payload["data"]["cause"] == "command-unavailable"


# --- read-only の実証（persistent state 不変） --------------------------------


@pytest.mark.parametrize("action", READ_ONLY)
def test_production_run_does_not_change_persistent_state(repo, action):
    """公開経路の実行が M2 の永続状態を変えないこと（`readonly-invariance`）。"""
    common = _common_dir(repo)
    before = P.PROMOTION_RELATIVE_PATH  # namespace の存在有無ごと digest へ含める
    namespace = common / before.parent
    snapshot = sorted(str(p) for p in namespace.rglob("*")) if namespace.exists() else []
    _flow("worktree", action, "--operation-id", "sha256:" + "a" * 64, repo=repo)
    after = sorted(str(p) for p in namespace.rglob("*")) if namespace.exists() else []
    assert snapshot == after, f"{action} が永続状態を変えた"


@pytest.mark.parametrize("action", READ_ONLY)
def test_production_run_never_emits_a_traceback(repo, action):
    """公開経路から traceback を出さないこと（`FLW-REV-028:GP-005`）。"""
    proc = subprocess.run(
        [sys.executable, str(FLOW), "--repo", str(repo), "worktree", action,
         "--format", "json"],
        capture_output=True, text=True,
    )
    assert "Traceback (most recent call last)" not in proc.stderr, proc.stderr[:400]


# --- doctor の出力が行動可能であること ---------------------------------------


def test_doctor_reports_actionable_guidance_from_production(repo):
    """doctor が符丁ではなく行動可能な是正を返すこと（`FLW-REV-028:GP-001`）。

    doctor は利用者が最初に走らせる診断であり、`fix-platform-or-bundle` のような
    符丁を返しても何をすればよいか判らない。
    """
    payload, _ = _flow("worktree", "doctor", repo=repo)
    guidance = payload["data"].get("required_human_input") or ""
    assert guidance not in ("", "none", "fix-platform-or-bundle"), guidance
    assert len(guidance) > 20, f"行動可能な長さではない: {guidance!r}"


def test_doctor_reports_observed_platform_evidence_from_production(repo):
    """doctor が実測した platform evidence を返すこと（自己申告でないこと）。"""
    payload, _ = _flow("worktree", "doctor", repo=repo)
    operability = payload["data"]["operability"]
    assert operability["platform_support"] in {"SUPPORTED", "UNSUPPORTED_FILESYSTEM"}
    assert operability["filesystem_type"], "filesystem を観測していない"
    assert "requires-runtime-evidence" not in json.dumps(operability)


# --- 入力契約 -----------------------------------------------------------------


@pytest.mark.parametrize("action", ["audit", "verify-receipt"])
def test_operation_id_is_required_and_closed(repo, action):
    """必須入力の欠落を closed result で示すこと。"""
    payload, code = _flow("worktree", action, repo=repo)
    assert code != 0
    assert payload["code"] == "INVALID_INPUT"
    assert payload["data"]["cause"] == "invalid-path"
