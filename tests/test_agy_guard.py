"""Antigravity限定confirmation許可のガード契約。"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GUARD = ROOT / "scripts" / "agy_guard.py"

SUBJECT = "python3 evals/flow-core/m2-eval/local_confirmation_subject.py --repo /tmp/repo"
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
    assert decide(SUBJECT)["decision"] == "allow"


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
