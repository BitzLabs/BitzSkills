import subprocess
import sys
import tempfile
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent
EXTRACTOR_SCRIPT = ROOT / "plugins/bitz-quality/skills/quality-review/scripts/quality_rule_extractor.py"
INIT_SCRIPT = ROOT / "plugins/bitz-quality/skills/quality-init/scripts/quality_init.py"

def test_QLT_FR_008_rule_extraction_and_ledger_append():
    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir)
        subprocess.run([sys.executable, str(INIT_SCRIPT), str(target)], check=True)
        
        # ルール追記
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
        
        # 重複IDで再登録
        res2 = subprocess.run(cmd, capture_output=True, text=True)
        assert res2.returncode != 0
        assert "既に存在します" in res2.stdout
