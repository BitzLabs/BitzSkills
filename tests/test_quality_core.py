import json
import subprocess
import sys
import tempfile
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent
SESSION_SCRIPT = ROOT / "plugins/bitz-quality/skills/quality-core/scripts/quality_session.py"
INIT_SCRIPT = ROOT / "plugins/bitz-quality/skills/quality-init/scripts/quality_init.py"

def test_QLT_FR_001_session_lifecycle():
    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir)
        subprocess.run([sys.executable, str(INIT_SCRIPT), str(target)], check=True)
        
        # 1. init
        res_init = subprocess.run(
            [sys.executable, str(SESSION_SCRIPT), "init", "FEAT-100", str(target), "--title", "注文機能"],
            capture_output=True,
            text=True
        )
        assert res_init.returncode == 0, res_init.stderr
        
        session_file = target / ".spec/quality/sessions/qa-session-feat-100.json"
        assert session_file.is_file()
        
        data = json.loads(session_file.read_text(encoding="utf-8"))
        assert data["feature_id"] == "FEAT-100"
        assert data["current_phase"] == "phase_0_intake"
        
        # 2. update phase
        res_up = subprocess.run(
            [sys.executable, str(SESSION_SCRIPT), "update", str(session_file), "--next-phase", "phase_1_scoring", "--note", "リスク判定完了"],
            capture_output=True,
            text=True
        )
        assert res_up.returncode == 0, res_up.stderr
        
        data2 = json.loads(session_file.read_text(encoding="utf-8"))
        assert data2["current_phase"] == "phase_1_scoring"
        assert len(data2["history"]) == 2
        assert data2["history"][-1]["note"] == "リスク判定完了"
