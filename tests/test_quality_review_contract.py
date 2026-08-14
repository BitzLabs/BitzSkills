import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "plugins/bitz-quality/skills/quality-review/cli/quality_review_cli.py"


def run(*args):
    return subprocess.run([sys.executable, str(CLI), *args], capture_output=True, text=True)


def test_cli_commands_and_exit_code_mapping(tmp_path):
    result = tmp_path / "result.json"
    result.write_text(json.dumps({"verdict": "PASS"}), encoding="utf-8")
    assert run("validate", "--input", str(result)).returncode == 0
    result.write_text(json.dumps({"verdict": "BLOCKED"}), encoding="utf-8")
    assert run("validate", "--input", str(result)).returncode == 2


def test_unknown_argument_is_rejected():
    assert run("plan", "--unknown").returncode == 2


def test_missing_validate_input_is_usage_error():
    assert run("validate").returncode == 3
