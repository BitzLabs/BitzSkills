"""M2是正枠 run manifest の契約（SI-FLW-058 の先行分。SYN-015 の是正）。"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECORDER = ROOT / "evals/flow-core/m2-eval/record_run.py"


def run(*args, cwd):
    return subprocess.run([sys.executable, str(RECORDER), *args],
                          capture_output=True, text=True, cwd=cwd, check=False)


def recorder_in(tmp_path):
    """manifest を tmp へ隔離するため、スクリプトを複製して実行する。"""
    target = tmp_path / "record_run.py"
    target.write_text(RECORDER.read_text(encoding="utf-8"), encoding="utf-8")
    return target


def call(target, *args):
    return subprocess.run([sys.executable, str(target), *args],
                          capture_output=True, text=True, check=False)


def test_summary_reports_the_approved_budget_before_any_entry(tmp_path):
    proc = call(recorder_in(tmp_path), "--summary")
    assert proc.returncode == 0
    summary = json.loads(proc.stdout)
    assert summary == {"used_pr": 0, "used_session": 0, "budget_pr": 4,
                       "budget_session": 13, "exhausted": False}


def test_entries_accumulate_and_are_append_only(tmp_path):
    target = recorder_in(tmp_path)
    assert call(target, "--pr", "281", "--issue", "SI-FLW-061", "--sessions", "2").returncode == 0
    assert call(target, "--pr", "282", "--issue", "SI-FLW-057", "--sessions", "3").returncode == 0
    manifest = json.loads((tmp_path / "run-manifest-m2-remediation.json").read_text())
    assert [e["issue"] for e in manifest["entries"]] == ["SI-FLW-061", "SI-FLW-057"]
    summary = json.loads(call(target, "--summary").stdout)
    assert summary["used_pr"] == 2 and summary["used_session"] == 5


def test_budget_exhaustion_exits_non_zero(tmp_path):
    """予算到達で自動停止する（2026-08-15 裁定の付帯条件3）。"""
    target = recorder_in(tmp_path)
    for pr in (281, 282, 283):
        assert call(target, "--pr", str(pr), "--issue", "SI-FLW-061").returncode == 0
    proc = call(target, "--pr", "284", "--issue", "SI-FLW-057")
    assert proc.returncode == 1
    assert "予算到達" in proc.stdout


def test_recording_requires_pr_and_issue(tmp_path):
    proc = call(recorder_in(tmp_path), "--sessions", "1")
    assert proc.returncode != 0


def test_unknown_argument_is_rejected(tmp_path):
    assert call(recorder_in(tmp_path), "--bogus").returncode != 0
