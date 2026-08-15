"""M2 local-write confirmation harness contract。"""

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RUNNER = REPO_ROOT / "evals/flow-core/m2-eval/run_local_confirmation.py"
SUBJECT = REPO_ROOT / "evals/flow-core/m2-eval/local_confirmation_subject.py"
QUALIFICATION = REPO_ROOT / "evals/flow-core/m2-eval/qualification-2026-08-14.json"
ACTIVE = REPO_ROOT / "evals/flow-core/m2-eval/active-local-confirmation.json"
PLATFORMS = ("claude", "codex", "antigravity")


def current_key():
    proc = subprocess.run(
        [sys.executable, str(RUNNER), "--repo", str(REPO_ROOT), "--print-compatibility-key"],
        capture_output=True, text=True, check=True,
    )
    return proc.stdout.strip()


def collected_runtime_checks():
    """実動E2Eファイルから収集される runtime check の母数（定数に依存しない）。"""
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider",
         str(REPO_ROOT / "tests/test_flow_m2_runtime.py")],
        cwd=REPO_ROOT, capture_output=True, text=True, check=False,
    )
    assert proc.returncode == 0
    return sum(1 for line in proc.stdout.splitlines() if "::" in line)


def test_confirmation_subject_exercises_local_write_fixture_set():
    proc = subprocess.run([sys.executable, str(SUBJECT), "--repo", str(REPO_ROOT)],
                          capture_output=True, text=True, check=False)
    assert proc.returncode == 0
    assert "M2_CONFIRMATION_PASS" in proc.stdout
    assert "test_id_digest=sha256:" in proc.stdout
    assert "hazards=0 residuals=0" in proc.stdout


def test_confirmation_runtime_check_count_is_derived_not_hardcoded():
    """runtime check の母数は実動E2Eの収集結果から導出されること。"""
    expected = collected_runtime_checks()
    assert expected > 0
    proc = subprocess.run([sys.executable, str(SUBJECT), "--repo", str(REPO_ROOT), "--describe"],
                          capture_output=True, text=True, check=False)
    assert proc.returncode == 0
    assert f"runtime_checks={expected}" in proc.stdout


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


def test_active_manifest_records_real_three_platform_run():
    """active manifest は実走であり、現在の被測定物と同じ指紋であること。"""
    manifest = json.loads(ACTIVE.read_text())
    assert manifest["dry_run"] is False
    assert manifest["gate_status"] == "PASS"
    assert manifest["compatibility_key"] == current_key()
    assert manifest["required_runtime_checks"] == collected_runtime_checks()
    assert [record["platform"] for record in manifest["platforms"]] == list(PLATFORMS)


def test_active_manifest_pins_identical_test_id_set_across_platforms():
    """3 platform が同一 test ID 集合・runtime check 8/8・hazard/residual 0 であること。"""
    manifest = json.loads(ACTIVE.read_text())
    for record in manifest["platforms"]:
        assert record["status"] == "PASS", record["platform"]
        assert record["tests"] == manifest["required_test_count"], record["platform"]
        assert record["test_id_digest"] == manifest["required_test_id_digest"], record["platform"]
        expected = manifest["required_runtime_checks"]
        assert record["runtime_checks"] == f"{expected}/{expected}", record["platform"]
        assert record["required_checks"] == "2/2", record["platform"]
        assert record["positive_controls"] == "2/2", record["platform"]
        assert record["hazardous_events"] == 0, record["platform"]
        assert record["residual_side_effects"] == 0, record["platform"]
