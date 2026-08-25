"""SI-FLW-085 — 廃止済み承認契約が production 入口から到達不能であることを検証する。

`FLW-REV-027:SYN-002`（P0）は、M2 の承認契約が plan-digest へ一本化された
（`FLW-DSN-017` §2）にもかかわらず、`_op_worktree` の create/resume 経路が
signed-capability 契約と旧 context を参照し続けていると判定した。

本テストは `FLW-DSN-017` §13.6 legacy exclusion 表の negative test であり、
2 種類の検査で構成する。

- **production black-box**: `flow.py` を別 process として起動し、handler 注入を
  行わない。`--capability-file` は gating より前に閉じるため、production から
  `unsupported-approval-mode` として観測できる。
- **静的検査**: 宣言 file と trusted key registry の検出は worktree operation が
  gated である間 production から到達できない（`command-unavailable` に隠れる）。
  到達不能性は、production コードに当該 symbol の参照が 0 件であることで確認する。
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / "plugins" / "bitz-flow" / "skills" / "flow-core"
FLOW = SKILL / "scripts" / "flow.py"
CLI_SOURCE = SKILL / "scripts" / "flowlib" / "cli.py"

#: production コードから参照されてはならない旧承認 symbol（`SI-FLW-085`）。
RETIRED_SYMBOLS = (
    "resolve_approval_mode",     # 承認モードの分岐
    "capability_from_json",      # capability の内容解析
    "worktree_dir_guard_key",    # 旧 context field
    "worktree_capability",       # 旧 capability module
)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    path = tmp_path / "repo"
    path.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(path)], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "t@example.com"], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "t"], check=True)
    (path / "a.txt").write_text("a\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(path), "add", "a.txt"], check=True)
    subprocess.run(["git", "-C", str(path), "commit", "-qm", "chore: init"], check=True)
    return path


def _flow(*args, repo: Path) -> dict:
    """production 既定 dispatcher を別 process で起動する（handler 注入なし）。"""
    proc = subprocess.run(
        [sys.executable, str(FLOW), "--repo", str(repo), *args, "--format", "json"],
        capture_output=True, text=True,
    )
    return json.loads(proc.stdout)


def _cause(result: dict) -> str | None:
    return result.get("data", {}).get("cause")


# --- production black-box ----------------------------------------------------


@pytest.mark.parametrize("action", ["create", "resume"])
def test_capability_file_is_rejected_as_unsupported_approval_mode(repo, action):
    """旧 signed-capability の指定は、公開可否より先に閉じた契約として拒否する。

    `command-unavailable` へ丸めると、承認強度の誤設定を運用者が識別できない。
    """
    capability = repo / "capability.json"
    capability.write_text(json.dumps({"worktree_dir_guard_key": "x"}), encoding="utf-8")
    result = _flow("worktree", action, "--capability-file", str(capability), repo=repo)
    assert result["code"] == "UNSUPPORTED"
    assert _cause(result) == "unsupported-approval-mode"
    assert result["operation"] == f"worktree.{action}"


@pytest.mark.parametrize("content", [
    pytest.param(None, id="file-does-not-exist"),
    pytest.param("{ this is not json", id="malformed-json"),
    pytest.param("{}", id="empty-object"),
])
def test_capability_file_content_is_never_parsed(repo, content, tmp_path):
    """旧入力は**内容を解析せず**拒否する（解析してからの降格を禁じる）。

    存在しない path・壊れた JSON・必須 field の無い JSON のいずれでも、
    file 由来の error ではなく同一の `unsupported-approval-mode` を返すことで、
    content を読んでいないことを示す。
    """
    target = tmp_path / "capability.json"
    if content is not None:
        target.write_text(content, encoding="utf-8")
    result = _flow("worktree", "create", "--capability-file", str(target), repo=repo)
    assert result["code"] == "UNSUPPORTED"
    assert _cause(result) == "unsupported-approval-mode"


def test_capability_rejection_does_not_fall_back_to_plan_digest(repo):
    """暗黙の plan-digest 降格を行わないこと。"""
    capability = repo / "capability.json"
    capability.write_text("{}", encoding="utf-8")
    result = _flow("worktree", "create", "--capability-file", str(capability),
                   "--apply", "--confirm", "x", repo=repo)
    assert result["code"] == "UNSUPPORTED"
    assert _cause(result) == "unsupported-approval-mode"
    assert result.get("approval_source") != "plan-digest"


@pytest.mark.parametrize("action", ["reconcile", "create", "resume", "finish", "discard"])
def test_write_worktree_operations_stay_gated(repo, action):
    """write を伴う worktree operation の gating が緩んでいないこと。

    read-only 3 件（doctor / audit / verify-receipt）は 2026-08-24 の裁定で限定公開した。
    緩めてはならないのは write 側である。
    """
    result = _flow("worktree", action, repo=repo)
    assert result["code"] == "UNSUPPORTED"
    assert _cause(result) == "command-unavailable"


@pytest.mark.parametrize("action", ["doctor", "audit", "verify-receipt"])
def test_read_only_worktree_operations_are_reachable(repo, action):
    """限定公開した read-only 3 件が production 既定 dispatcher から到達すること。

    `command-unavailable` で閉じられていないことが要点である（到達したうえで
    入力不足や環境不備を返すのは正しい）。
    """
    result = _flow("worktree", action, repo=repo)
    assert _cause(result) != "command-unavailable", "公開したのに到達していない"


# --- 静的検査（gated の間 production から到達できない経路の到達不能性） -------


@pytest.mark.parametrize("symbol", RETIRED_SYMBOLS)
def test_production_cli_does_not_reference_retired_approval_symbols(symbol):
    """旧承認 symbol が production handler から参照されないこと。

    宣言 file と trusted key registry の検出は worktree operation が gated である間
    production から到達できないため、到達不能性を参照 0 件で確認する。
    comment 中の言及は除外する（除去の経緯を残すため）。
    """
    code = [
        line for line in CLI_SOURCE.read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith("#")
    ]
    hits = [line.strip() for line in code if symbol in line]
    assert not hits, f"cli.py が旧承認 symbol {symbol} を参照している: {hits}"


def test_create_and_resume_use_the_shared_legacy_preflight():
    """create/resume が operability 系と同じ共通 preflight を通ること。"""
    source = CLI_SOURCE.read_text(encoding="utf-8")
    assert source.count("_legacy_approval_detected(") >= 3, (
        "共通 preflight が定義 1 + 呼び出し 2（operability / worktree）に満たない"
    )
