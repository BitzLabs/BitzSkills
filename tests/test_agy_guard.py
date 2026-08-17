"""Antigravity限定confirmation許可のガード契約。"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GUARD = ROOT / "scripts" / "agy_guard.py"

SUBJECT = "python3 /tmp/repo/evals/flow-core/m2-eval/local_confirmation_subject.py --repo /tmp/repo"
DESTRUCTIVE = "rm" + " -rf"


def judge(args):
    payload = {"toolCall": {"name": "run_command", "args": args}}
    proc = subprocess.run(
        [sys.executable, str(GUARD)], input=json.dumps(payload), text=True,
        capture_output=True, check=True,
    )
    return json.loads(proc.stdout)


def decide(command):
    return judge({"command": command})


def test_m2_confirmation_subject_exact_shape_is_allowed():
    """`CommandLine` を持つ実測形だけが allow される（`{"command": ...}` は Antigravity の形ではない）。"""
    assert judge({"CommandLine": SUBJECT, "Cwd": "/tmp/repo"})["decision"] == "allow"
    assert judge({"command": SUBJECT}).get("decision") != "allow"


@pytest.mark.parametrize("command", [
    pytest.param(f"{SUBJECT}; {DESTRUCTIVE} /tmp/other", id="shell-suffix"),
    pytest.param(f"{SUBJECT};rm$IFS-rf$IFS/tmp/other", id="ifs-suffix"),
    pytest.param(f"{SUBJECT}&&sudo$IFS-i", id="and-sudo"),
    pytest.param(f"python3 evals/flow-core/m2-eval/local_confirmation_subject.py "
                 f"--repo '/tmp/repo && sudo {DESTRUCTIVE} /'", id="quoted-argument"),
    pytest.param("python3 evals/flow-core/m2-eval/local_confirmation_subject.py --repo $(id)",
                 id="command-substitution"),
    pytest.param("python3 evals/flow-core/m2-eval/local_confirmation_subject.py --repo `id`",
                 id="backtick"),
    pytest.param(f"{SUBJECT} | sh", id="pipe"),
])
def test_m2_confirmation_allow_never_covers_shell_escapes(command):
    """許可形に見せかけた shell 逸脱は allow にしない（deny か無意見へ落とす）。"""
    assert judge({"command": command}).get("decision") != "allow"


@pytest.mark.parametrize("args", [
    pytest.param({"command": SUBJECT, "note": f"sudo {DESTRUCTIVE} /"}, id="sibling-string"),
    pytest.param({"command": SUBJECT, "env": [f"sudo {DESTRUCTIVE} /"]}, id="sibling-list"),
    pytest.param({"command": SUBJECT, "meta": {"pre": "git push --force origin main"}},
                 id="sibling-nested"),
])
def test_m2_confirmation_allow_does_not_shield_sibling_fields(args):
    """同居フィールドに禁止操作を積んでも allow で覆わない。"""
    assert judge(args)["decision"] == "deny"


@pytest.mark.parametrize("command", [
    pytest.param(f"{DESTRUCTIVE} /tmp/other", id="bare-destructive"),
    pytest.param("git push --force origin main", id="force-push"),
    pytest.param("git reset --hard HEAD~1", id="reset-hard"),
    pytest.param("sudo systemctl restart nginx", id="sudo"),
])
def test_guardrail_denies_are_unaffected_by_the_allow_path(command):
    assert decide(command)["decision"] == "deny"


# === SI-FLW-063: allow 述語の相乗り（RSK-201 / OPS-301） ======================
#
# 以前の allow 述語は「args のどこかに正規形があり、他の値にシェルメタ文字が無ければ allow」
# だった。下記はいずれもメタ文字を含まないため allow を通っていた。
# **2026-08-15 の事故で実際に使われた操作種別（コミットとガード無力化）を含む。**


@pytest.mark.parametrize("payload", [
    pytest.param("git commit -am pwned", id="commit"),
    pytest.param("git push origin main", id="push"),
    pytest.param("git branch -D main", id="branch-delete"),
    pytest.param("mv scripts/agy_guard.py /tmp/z", id="guard-move"),
    pytest.param("chmod 000 scripts/agy_guard.py", id="guard-chmod"),
    pytest.param("git checkout -b sneaky", id="branch-create"),
])
def test_allow_never_covers_a_piggybacked_command(payload):
    """正規形と同居する別コマンドを allow で覆わないこと。

    これらはシェルメタ文字を含まないため、旧述語（メタ文字が無ければ allow）を通っていた。
    2026-08-15 の事故で実際に使われた操作種別を含む（`SI-FLW-063`（RSK-201））。
    """
    assert judge({"command": SUBJECT, "note": payload}).get("decision") != "allow"


#: Antigravity の run_command が実際に送る形（2026-08-16 に guard へ入力して実測）。
REAL = {"CommandLine": SUBJECT, "Cwd": "/tmp/repo", "BypassSandbox": False,
        "RunPersistent": False, "WaitMsBeforeAsync": 5000}


def test_allow_covers_the_measured_payload_shape():
    """陰性対照 — 実測した正規形は通ること（厳格化で正規経路を落とさない）。"""
    response = judge(REAL)
    assert response["decision"] == "allow"
    assert response["permissionOverrides"] == [f"command({SUBJECT})"]


def test_allow_refuses_a_sandbox_bypass():
    """sandbox 解除を allow で覆わないこと。実測で BypassSandbox=True の経路が存在する。"""
    assert judge({**REAL, "BypassSandbox": True}).get("decision") != "allow"


def test_allow_refuses_unknown_fields():
    """未知の field を持つ payload は allow しない（形が変わったら既定へ倒す）。"""
    assert judge({**REAL, "note": "git commit -am pwned"}).get("decision") != "allow"
    assert judge({"command": SUBJECT}).get("decision") != "allow"


def test_allow_refuses_a_cwd_with_shell_metacharacters():
    assert judge({**REAL, "Cwd": "/tmp/x; rm -r /tmp/y"}).get("decision") != "allow"


def test_allow_refuses_a_different_command_line():
    assert judge({**REAL, "CommandLine": "git push origin main"}).get("decision") != "allow"


# --- SYN-009: 評価順の固定と、禁止操作の独立 deny -----------------------------


def test_SYN_009_allow_does_not_bypass_force_ask():
    """allow 分岐が ASK より先に評価されると force_ask を迂回できた（実測済み）。

    許可形の `--repo` へ実環境のスキル配置先を渡すだけで allow を取れる状態だった。
    評価順は DENY → ASK → ALLOW に固定する。
    """
    outside = ("python3 evals/flow-core/m2-eval/local_confirmation_subject.py "
               "--repo /home/hide/.claude/skills")
    assert judge({**REAL, "CommandLine": outside})["decision"] == "force_ask"


def test_SYN_009_denies_guard_neutralization_regardless_of_allow():
    """ガードレール実体を無力化する操作は allow の有無と独立に deny すること。

    これらを通すと以後のすべての判定が無意味になる。
    2026-08-15 の事故で実際に使われた操作種別である。
    """
    for command in (
        "chmod 000 scripts/agy_guard.py",
        "mv scripts/agy_guard.py /tmp/z",
        "cp /tmp/evil .agents/hooks.json",
        "tee .claude/settings.json",
        "cat /home/hide/.claude/.credentials.json",
    ):
        assert judge({**REAL, "CommandLine": command})["decision"] == "deny", command


def test_SYN_009_denies_forced_branch_deletion():
    assert judge({**REAL, "CommandLine": "git branch -D main"})["decision"] == "deny"


def test_SYN_009_keeps_unrelated_commands_without_opinion():
    """陰性対照 — 無関係なコマンドまで deny しないこと（過剰拒否の防止）。"""
    assert judge({**REAL, "CommandLine": "ls -la"}) == {}
