import subprocess
import sys
import tempfile
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent
REPORT_SCRIPT = ROOT / "plugins/bitz-quality/skills/quality-report/scripts/quality_report.py"
INIT_SCRIPT = ROOT / "plugins/bitz-quality/skills/quality-init/scripts/quality_init.py"

def test_QLT_FR_016_quality_summary_report_generation():
    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir)
        subprocess.run([sys.executable, str(INIT_SCRIPT), str(target)], check=True)
        
        # 報告書生成
        res = subprocess.run([sys.executable, str(REPORT_SCRIPT), str(target), "--save"], capture_output=True, text=True)
        assert res.returncode == 0, res.stderr
        
        report_file = target / ".spec/quality/reports/quality-summary-report.md"
        assert report_file.is_file()
        content = report_file.read_text(encoding="utf-8")
        assert "総合品質報告書" in content
        assert "品質ダッシュボード" in content
        assert "SDD 要件トレーサビリティ状況" in content
        assert "リリース判定と推奨事項" in content
