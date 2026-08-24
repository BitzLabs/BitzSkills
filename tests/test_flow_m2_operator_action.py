"""FLW-REV-028:GP-001 — 不支持理由へ行動可能な operator action を与える。

理由を出すだけでは「なぜ動かないか」は判っても「どうすれば動くか」が判らない。
とくに `acl-not-owner-only` は **既定 umask (0755) の worktree root が必ず拒否される**
条件であり、利用者が最初に踏む。

あわせて `FLW-TSK-116`／`117` で追加した handler の非ok契約違反を検証する。
`WorktreeUnsupportedPlatformError` / `WorktreeChildTimeoutError` の写像は
`R.build_result` を直呼びして `recovery_class` を欠いており、到達すると ValueError に
なっていた。`FLW-TSK-123` の dispatcher 網はそれを `UNAVAILABLE` へ丸めるため
traceback にはならないが、**意図した closed result が失われる**（網が欠陥を隠していた）。
dispatcher 網は最後の受け皿であり、個別 handler の契約遵守を代替しない。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "plugins" / "bitz-flow" / "skills" / "flow-core"
RUNBOOK = ROOT / "plugins" / "bitz-flow" / "docs" / "runbooks" / "m2-worktree-quarantine.md"
sys.path.insert(0, str(SKILL / "scripts"))

from flowlib import cli  # noqa: E402
from flowlib import worktree_platform as PF  # noqa: E402
from flowlib import worktree_runtime as WR  # noqa: E402


# --- operator action の内容 ---------------------------------------------------


def test_default_umask_rejection_names_the_target_and_the_required_mode():
    """`acl-not-owner-only` が対象 path と必要 mode を示すこと。"""
    action = PF.operator_action(("acl-not-owner-only",), target="/srv/worktrees")
    assert "/srv/worktrees" in action
    assert "0700" in action


@pytest.mark.parametrize("reason", sorted(PF.OPERATOR_ACTIONS))
def test_every_known_reason_has_a_non_empty_action(reason):
    """既知の理由すべてに行動可能な文が対応すること。"""
    action = PF.operator_action((reason,))
    assert action.strip()
    assert action != reason, f"{reason}: 理由をそのまま返している（行動になっていない）"


def test_unknown_reason_falls_back_to_doctor():
    """未知の理由でも空にせず doctor へ誘導すること。"""
    assert "doctor" in PF.operator_action(("brand-new-reason",))


def test_evaluate_platform_reasons_are_all_covered():
    """`evaluate_platform` が出しうる理由が action 表から漏れていないこと。

    漏れると、その理由に当たった利用者だけが行動を示されない。
    """
    source = (SKILL / "scripts" / "flowlib" / "worktree_platform.py").read_text(encoding="utf-8")
    import re
    emitted = set(re.findall(r'reasons\.append\("([a-z-]+)"\)', source))
    emitted |= set(re.findall(r'^\s+"([a-z-]+)": \(', source, re.M))
    missing = sorted(r for r in emitted if r not in PF.OPERATOR_ACTIONS)
    assert not missing, f"action 表に無い理由 {missing}"


# --- 非ok契約の遵守 ----------------------------------------------------------


def _closed(**kwargs):
    return cli._simple_result(repo="/x", **kwargs)


@pytest.mark.parametrize("code,cause,label", [
    ("UNSUPPORTED", "unsupported-filesystem", "platform-unsupported"),
    ("INDETERMINATE", "result-indeterminate", "child-timeout"),
    ("UNAVAILABLE", "result-indeterminate", "dispatcher-net"),
    ("UNSUPPORTED", "unsupported-approval-mode", "legacy-approval"),
])
def test_closed_results_satisfy_the_non_ok_contract(code, cause, label):
    """非ok result が cause / recovery_class / required_human_input を満たすこと。"""
    result = _closed(operation="worktree.create", code=code, summary="s",
                     cause=cause, stage="plan",
                     required_human_input="対象を是正する")
    data = result["data"]
    assert data["cause"] == cause, label
    assert data["recovery_class"] in {"human-stop", "reconcile-only",
                                      "replan-human", "retry-read"}, label
    if data["recovery_class"] == "human-stop":
        assert data["required_human_input"], label


def test_platform_and_timeout_handlers_do_not_bypass_the_contract():
    """2 handler が `build_result` 直呼びに戻っていないこと。

    直呼びすると `recovery_class` を欠いて ValueError になり、dispatcher 網が
    それを `UNAVAILABLE` へ丸めるため、意図した result が静かに失われる。
    """
    source = (SKILL / "scripts" / "flowlib" / "cli.py").read_text(encoding="utf-8")
    for name in ("WorktreeUnsupportedPlatformError", "WorktreeChildTimeoutError"):
        start = source.index(f"except worktree_runtime.{name} as exc:")
        body = source[start:source.index("except", start + 10)]
        assert "_simple_result(" in body, f"{name}: 非ok契約を満たす経路を通っていない"
        assert "R.build_result(" not in body, f"{name}: build_result を直呼びしている"


def test_unsupported_platform_handler_carries_the_operator_action():
    """platform 不支持の result が operator action を運ぶこと。"""
    source = (SKILL / "scripts" / "flowlib" / "cli.py").read_text(encoding="utf-8")
    start = source.index("except worktree_runtime.WorktreeUnsupportedPlatformError as exc:")
    body = source[start:source.index("except", start + 10)]
    assert "operator_action(" in body
    assert "exc.reasons" in body


def test_error_types_remain_distinguishable():
    """環境対象外と child timeout を同じ型へ畳んでいないこと。"""
    assert not issubclass(WR.WorktreeUnsupportedPlatformError, WR.WorktreeChildTimeoutError)
    assert not issubclass(WR.WorktreeChildTimeoutError, WR.WorktreeUnsupportedPlatformError)


# --- runbook -----------------------------------------------------------------


def test_runbook_documents_owner_only_worktree_root():
    """runbook に worktree root の作成手順（owner-only）があること。"""
    text = RUNBOOK.read_text(encoding="utf-8")
    assert "0700" in text
    assert "acl-not-owner-only" in text
