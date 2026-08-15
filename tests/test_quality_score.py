import subprocess
import sys
import tempfile
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent
SCORE_SCRIPT = ROOT / "plugins/bitz-quality/skills/quality-score/scripts/quality_score.py"

def run_score(*args: str, cwd: Path = None) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(SCORE_SCRIPT)] + list(args)
    return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)

def test_QLT_FR_004_level_c_self_qa():
    # 低スコア合計 (5点)
    res = run_score(
        "FEAT-001",
        "--scale", "1",
        "--security", "1",
        "--blast-radius", "1",
        "--complexity", "1",
        "--familiarity", "1",
    )
    assert res.returncode == 0, res.stderr
    assert "Level C (Self QA)" in res.stdout
    assert "5 / 15 点" in res.stdout

def test_QLT_FR_004_level_b_review_qa():
    # 中スコア合計 (9点)
    res = run_score(
        "FEAT-002",
        "--scale", "2",
        "--security", "1",
        "--blast-radius", "2",
        "--complexity", "2",
        "--familiarity", "2",
    )
    assert res.returncode == 0, res.stderr
    assert "Level B (Review QA)" in res.stdout
    assert "9 / 15 点" in res.stdout

def test_QLT_FR_004_level_a_high_score():
    # 高スコア合計 (13点)
    res = run_score(
        "FEAT-003",
        "--scale", "3",
        "--security", "2",
        "--blast-radius", "2",
        "--complexity", "3",
        "--familiarity", "3",
    )
    assert res.returncode == 0, res.stderr
    assert "Level A (Full QA)" in res.stdout
    assert "13 / 15 点" in res.stdout

def test_QLT_FR_004_forced_level_a_by_security():
    # 合計は低い (7点) がセキュリティが 3
    res = run_score(
        "FEAT-004",
        "--scale", "1",
        "--security", "3",
        "--blast-radius", "1",
        "--complexity", "1",
        "--familiarity", "1",
    )
    assert res.returncode == 0, res.stderr
    assert "Level A (Full QA)" in res.stdout
    assert "セキュリティ重要度=3 のため強制適用" in res.stdout

def test_QLT_FR_004_forced_level_a_by_blast_radius():
    # 合計は低い (7点) が影響範囲(DBマイグレーション)が 3
    res = run_score(
        "FEAT-005",
        "--scale", "1",
        "--security", "1",
        "--blast-radius", "3",
        "--complexity", "1",
        "--familiarity", "1",
    )
    assert res.returncode == 0, res.stderr
    assert "Level A (Full QA)" in res.stdout
    assert "影響範囲=3" in res.stdout

def test_QLT_FR_004_save_to_scorings_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir)
        res = run_score(
            "FEAT-SAVE",
            "--scale", "2",
            "--save",
            cwd=target,
        )
        assert res.returncode == 0, res.stderr
        saved_file = target / ".spec/quality/scorings/score-feat-save.md"
        assert saved_file.is_file()
        assert "FEAT-SAVE" in saved_file.read_text(encoding="utf-8")
