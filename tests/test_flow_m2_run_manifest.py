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


def test_FLW_FR_012_summary_reports_unbounded_budget_before_any_entry(tmp_path):
    proc = call(recorder_in(tmp_path), "--summary")
    assert proc.returncode == 0
    summary = json.loads(proc.stdout)
    assert summary == {"used_pr": 0, "known_session": 0, "unknown_session_prs": [],
                       "budget_mode": "unbounded", "exception_scope": "M2 remediation / FLW-REV-018",
                       "recalibration_pending": "FLW-REV-019:GP-006"}


def test_FLW_FR_012_entries_accumulate_once_and_keep_sessions(tmp_path):
    target = recorder_in(tmp_path)
    assert call(target, "--pr", "281", "--issue", "SI-FLW-061", "--sessions", "2").returncode == 0
    assert call(target, "--pr", "282", "--issue", "SI-FLW-057", "--sessions", "3").returncode == 0
    manifest = json.loads((tmp_path / "run-manifest-m2-remediation.json").read_text())
    assert [e["issue"] for e in manifest["entries"]] == ["SI-FLW-061", "SI-FLW-057"]
    summary = json.loads(call(target, "--summary").stdout)
    assert summary["used_pr"] == 2 and summary["known_session"] == 5


def test_FLW_FR_012_unbounded_budget_does_not_stop_after_old_limit(tmp_path):
    target = recorder_in(tmp_path)
    for pr in (301, 302, 303, 304, 305, 306):
        assert call(target, "--pr", str(pr), "--issue", "SI-FLW-063", "--sessions", "1").returncode == 0


def test_FLW_FR_012_duplicate_pr_is_rejected_without_overwriting_manifest(tmp_path):
    target = recorder_in(tmp_path)
    assert call(target, "--pr", "301", "--issue", "SI-FLW-063", "--sessions", "1").returncode == 0
    before = (tmp_path / "run-manifest-m2-remediation.json").read_text()
    proc = call(target, "--pr", "301", "--issue", "SI-FLW-063", "--sessions", "1")
    assert proc.returncode != 0
    assert "すでに記録済み" in proc.stderr
    assert (tmp_path / "run-manifest-m2-remediation.json").read_text() == before


def test_FLW_FR_012_unbounded_budget_rejects_a_scope_outside_m2_remediation(tmp_path):
    target = recorder_in(tmp_path)
    assert call(target, "--pr", "301", "--issue", "SI-FLW-063", "--sessions", "1").returncode == 0
    manifest_path = tmp_path / "run-manifest-m2-remediation.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["budget"]["scope"] = "M3 remediation / FLW-REV-018"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    proc = call(target, "--summary")
    assert proc.returncode != 0
    assert "M2 remediation" in proc.stderr


def test_FLW_FR_012_recording_requires_pr_issue_and_sessions(tmp_path):
    proc = call(recorder_in(tmp_path), "--sessions", "1")
    assert proc.returncode != 0


def test_unknown_argument_is_rejected(tmp_path):
    assert call(recorder_in(tmp_path), "--bogus").returncode != 0
