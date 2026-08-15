import subprocess
import sys
import tempfile
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent
MEASURAND_SCRIPT = ROOT / "plugins/bitz-quality/skills/quality-measurand/scripts/quality_measurand.py"
INIT_SCRIPT = ROOT / "plugins/bitz-quality/skills/quality-init/scripts/quality_init.py"

def test_QLT_FR_013_quality_metrics_collection():
    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir)
        subprocess.run([sys.executable, str(INIT_SCRIPT), str(target)], check=True)
        
        # ダミー要件
        req_dir = target / ".spec/requirements"
        req_dir.mkdir(parents=True, exist_ok=True)
        (req_dir / "REQ-001.md").write_text("---\nid: REQ-001\nstatus: verified\n---\n### REQ-001\n", encoding="utf-8")
        
        res = subprocess.run([sys.executable, str(MEASURAND_SCRIPT), "metrics", str(target), "--save"], capture_output=True, text=True)
        assert res.returncode == 0, res.stderr
        assert "スコア" in res.stdout
        
        report_file = target / ".spec/quality/reports/quality-metrics.md"
        assert report_file.is_file()
        content = report_file.read_text(encoding="utf-8")
        assert "統合品質メトリクス報告書" in content
        assert "要件検証充足率" in content

def test_QLT_FR_014_mutation_self_diagnosis():
    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir)
        subprocess.run([sys.executable, str(INIT_SCRIPT), str(target)], check=True)
        
        res = subprocess.run([sys.executable, str(MEASURAND_SCRIPT), "mutate", str(target), "--save"], capture_output=True, text=True)
        assert res.returncode == 0, res.stderr
        assert "100.0%" in res.stdout
        assert "PASS" in res.stdout
        
        report_file = target / ".spec/quality/reports/mutation-diagnosis.md"
        assert report_file.is_file()
        content = report_file.read_text(encoding="utf-8")
        assert "ミューテーション自己診断報告書" in content
        assert "KILLED" in content
