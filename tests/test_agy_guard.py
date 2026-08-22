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
        "RunPersistent": False, "WaitMsBeforeAsync": 5000,
        "toolAction": "Running confirmation subject",
        "toolSummary": "Run confirmation subject"}


def test_allow_covers_the_measured_payload_shape():
    """陰性対照 — 実測した正規形は通ること（厳格化で正規経路を落とさない）。"""
    response = judge(REAL)
    assert response["decision"] == "allow"
    assert response["permissionOverrides"] == [f"command({SUBJECT})"]


def test_allow_covers_a_sandbox_bypass_only_for_the_exact_subject():
    """M2 write試験の限定subjectだけはsandbox解除を許可し、別commandへ一般化しない。"""
    assert judge({**REAL, "BypassSandbox": True})["decision"] == "allow"
    assert judge({**REAL, "BypassSandbox": True,
                  "CommandLine": "git status"}).get("decision") != "allow"
    assert judge({**REAL, "BypassSandbox": "true"}).get("decision") != "allow"


def test_allow_refuses_unknown_fields():
    """未知の field を持つ payload は allow しない（形が変わったら既定へ倒す）。"""
    assert judge({**REAL, "note": "git commit -am pwned"}).get("decision") != "allow"
    assert judge({"command": SUBJECT}).get("decision") != "allow"


def test_allow_refuses_a_cwd_with_shell_metacharacters():
    assert judge({**REAL, "Cwd": "/tmp/x; rm -r /tmp/y"}).get("decision") != "allow"


def test_allow_refuses_a_cwd_other_than_the_bound_repo():
    assert judge({**REAL, "Cwd": "/tmp/other"}).get("decision") != "allow"


@pytest.mark.parametrize("change", [
    pytest.param({"RunPersistent": True}, id="persistent"),
    pytest.param({"WaitMsBeforeAsync": True}, id="wait-bool"),
    pytest.param({"WaitMsBeforeAsync": 10001}, id="wait-too-large"),
    pytest.param({"toolAction": ""}, id="empty-action"),
    pytest.param({"toolSummary": "x\nmalformed"}, id="summary-control"),
    pytest.param({"toolSummary": "x" * 257}, id="summary-too-long"),
])
def test_allow_refuses_unsafe_current_antigravity_metadata(change):
    assert judge({**REAL, **change}).get("decision") != "allow"


def test_allow_accepts_current_payload_without_optional_sandbox_fields():
    payload = {
        "CommandLine": SUBJECT,
        "Cwd": "/tmp/repo",
        "WaitMsBeforeAsync": 5000,
        "toolAction": "Running confirmation subject",
        "toolSummary": "Run confirmation subject",
    }
    assert judge(payload)["decision"] == "allow"


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


# === FLW-TSK-101: パス正規化と極性反転（read-only allowlist） ==================
#
# `ASK_PATTERNS` は生文字列の正規表現であり `/./` や重複スラッシュを挟むだけで
# 照合から外れていた。ガード資産の保護は書き込み動詞の列挙であり、列挙に無い
# 動詞（sed -i / リダイレクト / install / dd / patch / ln -sf / インタプリタからの
# open(..., "w")）が素通りした。動詞列挙に安全性を載せる方式は成立しない。


@pytest.mark.parametrize("path", [
    pytest.param("/home/agent/./.claude/skills", id="dot-segment"),
    pytest.param("/home/agent//.claude/skills", id="double-slash"),
    pytest.param("/home/agent/x/../.claude/skills", id="dot-dot-traversal"),
    pytest.param("/home/agent/.claude/./skills", id="dot-segment-mid-path"),
    pytest.param("/home/agent/a/b/../../.claude/skills", id="multi-dot-dot"),
])
def test_path_normalization_variants_still_reach_force_ask(path):
    """陽性対照 — `/./`・`//`・`..` を挟んでも正規化後に ASK 照合へ到達すること。

    正規化前の生文字列だけを見る照合では、これらはいずれも
    `/home/[^/\\s]+/\\.claude/skills` の literal 照合から外れていた。
    """
    assert judge({**REAL, "CommandLine": f"cat {path}"})["decision"] == "force_ask", path


def test_tilde_normalization_expands_before_matching():
    """`~` 展開が実際の home directory へ展開されたうえで正規化されること（単体）。"""
    import importlib.util

    spec = importlib.util.spec_from_file_location("agy_guard", GUARD)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    home = module.os.path.expanduser("~")
    assert module._normalize_candidate("~/./.claude/skills") == f"{home}/.claude/skills"
    assert module._normalize_candidate("~//.claude/skills") == f"{home}/.claude/skills"


@pytest.mark.parametrize("command", [
    pytest.param("sed -i s/x/y/ scripts/agy_guard.py", id="sed-in-place"),
    pytest.param("install -m 000 /tmp/evil scripts/agy_guard.py", id="install"),
    pytest.param("dd if=/dev/zero of=scripts/agy_guard.py", id="dd"),
    pytest.param("patch scripts/agy_guard.py x.diff", id="patch"),
    pytest.param("ln -sf /tmp/evil scripts/agy_guard.py", id="symlink-replace"),
    pytest.param(
        'python3 -c "open(\'scripts/agy_guard.py\', \'w\').write(\'x\')"',
        id="interpreter-write",
    ),
    pytest.param("echo pwned>scripts/agy_guard.py", id="redirection-no-space"),
])
def test_write_verb_variants_outside_the_old_enumeration_are_now_denied(command):
    """陽性対照 — 旧・書き込み動詞列挙に無い変種がすべて deny になること（極性反転）。

    以前は `(chmod|chown|mv|cp|rm|truncate|tee)` の列挙だけを見ており、これらは
    いずれも列挙に無い動詞・リダイレクト・インタプリタ経由の書き込みのため
    素通りしていた。
    """
    assert judge({**REAL, "CommandLine": command})["decision"] == "deny", command


@pytest.mark.parametrize("command", [
    pytest.param("cat scripts/agy_guard.py", id="cat"),
    pytest.param("grep pattern scripts/agy_guard.py", id="grep"),
    pytest.param("head -n 5 .claude/settings.json", id="head"),
    pytest.param("tail -n 5 .agents/hooks.json", id="tail"),
    pytest.param("diff a.json .claude/settings.json", id="diff"),
    pytest.param("git show HEAD:scripts/agy_guard.py", id="git-show"),
    pytest.param("git log -- scripts/agy_guard.py", id="git-log"),
])
def test_read_only_allowlist_still_reaches_the_guard_assets(command):
    """陰性対照 — enumerate された read-only 形は deny にならないこと（過剰拒否の防止）。"""
    assert judge({**REAL, "CommandLine": command}).get("decision") != "deny", command


@pytest.mark.parametrize("command", [
    pytest.param("git show --output=scripts/agy_guard.py HEAD", id="show-output"),
    pytest.param("git diff --output=.agents/hooks.json HEAD~1", id="diff-output"),
    pytest.param("git log --output=.claude/settings.json HEAD", id="log-output"),
])
def test_git_read_only_subcommands_with_output_options_are_denied(command):
    """read-only subcommand 名だけでは書込み option を許可しない。"""
    assert judge({**REAL, "CommandLine": command})["decision"] == "deny", command


def test_read_only_form_with_bypass_sandbox_is_still_denied():
    """`BypassSandbox` はガード資産の read-only allowlist を無効化する。"""
    assert judge(
        {**REAL, "CommandLine": "cat scripts/agy_guard.py", "BypassSandbox": True}
    )["decision"] == "deny"


def test_read_only_form_with_shell_metacharacter_is_still_denied():
    """read-only program でも shell metacharacter があれば chaining の余地があるため deny。"""
    assert judge(
        {**REAL, "CommandLine": "cat scripts/agy_guard.py; rm -rf /tmp/x"}
    )["decision"] == "deny"


def test_measured_m2_confirmation_shape_still_allows_after_the_rewrite():
    """回帰 — 既存の M2 confirmation subject の許可形が引き続き通ること。"""
    response = judge(REAL)
    assert response["decision"] == "allow"
    assert response["permissionOverrides"] == [f"command({SUBJECT})"]
