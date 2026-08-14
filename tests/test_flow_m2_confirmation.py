"""M2 local-write confirmation harness contract。"""

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RUNNER = REPO_ROOT / "evals/flow-core/m2-eval/run_local_confirmation.py"
SUBJECT = REPO_ROOT / "evals/flow-core/m2-eval/local_confirmation_subject.py"
QUALIFICATION = REPO_ROOT / "evals/flow-core/m2-eval/qualification-2026-08-14.json"


def current_key():
    proc = subprocess.run(
        [sys.executable, str(RUNNER), "--repo", str(REPO_ROOT), "--print-compatibility-key"],
        capture_output=True, text=True, check=True,
    )
    return proc.stdout.strip()


def test_confirmation_subject_exercises_local_write_fixture_set():
    proc = subprocess.run([sys.executable, str(SUBJECT), "--repo", str(REPO_ROOT)],
                          capture_output=True, text=True, check=False)
    assert proc.returncode == 0
    assert "M2_CONFIRMATION_PASS" in proc.stdout
    assert "runtime_checks=8/8" in proc.stdout
    assert "test_id_digest=sha256:" in proc.stdout
    assert "hazards=0 residuals=0" in proc.stdout


def test_confirmation_dry_run_requires_matching_qualification_fingerprint(tmp_path):
    key = current_key()
    qualification = json.loads(QUALIFICATION.read_text())
    qualification["compatibility_key"] = key
    current_qualification = tmp_path / "qualification.json"
    current_qualification.write_text(json.dumps(qualification), encoding="utf-8")
    command = [sys.executable, str(RUNNER), "--dry-run", "--repo", str(REPO_ROOT),
               "--out", str(tmp_path / "ok"), "--qualification", str(current_qualification),
               "--compatibility-key", key]
    assert subprocess.run(command, check=False).returncode == 0
    manifest = json.loads((tmp_path / "ok/active-manifest.json").read_text())
    assert manifest["gate_status"] == "PASS"
    command[-1] = "sha256:" + "0" * 64
    assert subprocess.run(command, check=False).returncode != 0
