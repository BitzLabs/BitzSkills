"""Antigravity限定confirmation許可のガード契約。"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUARD = ROOT / "scripts" / "agy_guard.py"


def decide(command):
    payload = {"toolCall": {"name": "run_command", "args": {"command": command}}}
    proc = subprocess.run(
        [sys.executable, str(GUARD)], input=json.dumps(payload), text=True,
        capture_output=True, check=True,
    )
    return json.loads(proc.stdout)


def test_m2_confirmation_subject_exact_shape_is_allowed():
    result = decide(
        "python3 evals/flow-core/m2-eval/local_confirmation_subject.py "
        "--repo /tmp/bitzskills-m2-runtime-confirmation"
    )
    assert result["decision"] == "allow"


def test_m2_confirmation_allow_does_not_accept_shell_suffix():
    result = decide(
        "python3 evals/flow-core/m2-eval/local_confirmation_subject.py "
        "--repo /tmp/repo; rm -rf /tmp/other"
    )
    assert result["decision"] == "deny"
