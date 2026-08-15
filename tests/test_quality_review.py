import subprocess
import sys
import tempfile
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent
EXTRACTOR_SCRIPT = ROOT / "plugins/bitz-quality/skills/quality-review/scripts/quality_rule_extractor.py"
REVIEW_SCRIPT = ROOT / "plugins/bitz-quality/skills/quality-review/scripts/quality_llm_review.py"
INIT_SCRIPT = ROOT / "plugins/bitz-quality/skills/quality-init/scripts/quality_init.py"

def test_QLT_FR_008_rule_extraction_and_ledger_append():
    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir)
        subprocess.run([sys.executable, str(INIT_SCRIPT), str(target)], check=True)
        
        cmd = [
            sys.executable,
            str(EXTRACTOR_SCRIPT),
            "R-201",
            str(target),
            "--type", "API",
            "--scope", "endpoints/user",
            "--rule", "レスポンスに機密情報を含めない",
            "--cause", "シリアライザの除外漏れ"
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        assert res.returncode == 0, res.stderr
        
        ledger = target / ".spec/quality/rules/rules-ledger.md"
        assert ledger.is_file()
        content = ledger.read_text(encoding="utf-8")
        assert "R-201" in content
        assert "endpoints/user" in content
        assert "レスポンスに機密情報を含めない" in content
        assert "シリアライザの除外漏れ" in content

def test_QLT_FR_008_duplicate_rule_id_skipped():
    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir)
        subprocess.run([sys.executable, str(INIT_SCRIPT), str(target)], check=True)
        
        cmd = [
            sys.executable,
            str(EXTRACTOR_SCRIPT),
            "R-201",
            str(target),
            "--type", "API",
            "--scope", "endpoints/user",
            "--rule", "ルール1",
            "--cause", "原因1"
        ]
        res1 = subprocess.run(cmd, capture_output=True, text=True)
        assert res1.returncode == 0
        
        res2 = subprocess.run(cmd, capture_output=True, text=True)
        assert res2.returncode != 0
        assert "既に存在します" in res2.stdout

def test_QLT_FR_009_clean_code_passes_llm_review():
    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir)
        subprocess.run([sys.executable, str(INIT_SCRIPT), str(target)], check=True)
        
        # クリーンなコード
        (target / "clean.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
        
        res = subprocess.run([sys.executable, str(REVIEW_SCRIPT), "FEAT-200", str(target), "--save"], capture_output=True, text=True)
        assert res.returncode == 0, res.stderr
        assert "PASS" in res.stdout
        
        report = target / ".spec/quality/reports/review-feat-200.md"
        assert report.is_file()
        assert "指摘事項はありません" in report.read_text(encoding="utf-8")

def test_QLT_FR_010_findings_report_and_auto_ledger():
    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir)
        subprocess.run([sys.executable, str(INIT_SCRIPT), str(target)], check=True)
        
        # 問題のあるコード（except: pass と hardcoded password）
        (target / "bad_code.py").write_text(
            "def login():\n    password = 'mysecretpassword123'\n    try:\n        pass\n    except:\n        pass\n",
            encoding="utf-8"
        )
        
        res = subprocess.run([sys.executable, str(REVIEW_SCRIPT), "FEAT-201", str(target), "--save", "--auto-ledger"], capture_output=True, text=True)
        assert res.returncode == 1  # P0/P1 があるので FAIL
        assert "FAIL" in res.stdout
        
        # レポート確認
        report = target / ".spec/quality/reports/review-feat-201.md"
        assert report.is_file()
        content = report.read_text(encoding="utf-8")
        assert "L02" in content
        assert "L04" in content
        
        # 台帳への自動登録確認
        ledger = target / ".spec/quality/rules/rules-ledger.md"
        ledger_text = ledger.read_text(encoding="utf-8")
        assert "R-L02-001" in ledger_text or "R-L04-001" in ledger_text
