import json
import subprocess
import sys
import tempfile
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent
DOCTOR_SCRIPT = ROOT / "plugins/bitz-quality/skills/quality-doctor/scripts/quality_doctor.py"
INIT_SCRIPT = ROOT / "plugins/bitz-quality/skills/quality-init/scripts/quality_init.py"

def run_doctor(target_path: Path) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(DOCTOR_SCRIPT), str(target_path)]
    return subprocess.run(cmd, capture_output=True, text=True)

def test_QLT_FR_003_healthy_after_init():
    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir)
        # まず初期化
        subprocess.run([sys.executable, str(INIT_SCRIPT), str(target)], check=True)
        
        res = run_doctor(target)
        assert res.returncode == 0, res.stderr
        assert "品質環境は健全です" in res.stdout

def test_QLT_FR_003_missing_quality_root_fails():
    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir)
        res = run_doctor(target)
        assert res.returncode != 0
        assert "ディレクトリが存在しません" in res.stdout or "quality-init" in res.stdout

def test_QLT_FR_003_missing_subdir_warns():
    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir)
        subprocess.run([sys.executable, str(INIT_SCRIPT), str(target)], check=True)
        
        # サブディレクトリを削除
        (target / ".spec/quality/scorings").rmdir()
        
        res = run_doctor(target)
        assert res.returncode != 0
        assert "必須サブディレクトリが存在しません" in res.stdout

def test_QLT_FR_003_invalid_session_json():
    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir)
        subprocess.run([sys.executable, str(INIT_SCRIPT), str(target)], check=True)
        
        # 壊れたセッションJSONを作成
        session_file = target / ".spec/quality/sessions/broken.json"
        session_file.write_text("{broken json", encoding="utf-8")
        
        res = run_doctor(target)
        assert res.returncode != 0
        assert "パースに失敗しました" in res.stdout
