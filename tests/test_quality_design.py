import subprocess
import sys
import tempfile
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent
IMPACT_SCRIPT = ROOT / "plugins/bitz-quality/skills/quality-design/scripts/quality_impact_analysis.py"
BUG_SCRIPT = ROOT / "plugins/bitz-quality/skills/quality-design/scripts/quality_bug_analysis.py"
VIEWPOINT_SCRIPT = ROOT / "plugins/bitz-quality/skills/quality-design/scripts/quality_viewpoints.py"
CASES_SCRIPT = ROOT / "plugins/bitz-quality/skills/quality-design/scripts/quality_cases.py"
INIT_SCRIPT = ROOT / "plugins/bitz-quality/skills/quality-init/scripts/quality_init.py"

def run_impact(target_path: Path, *args: str) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(IMPACT_SCRIPT), "FEAT-001", str(target_path)] + list(args)
    return subprocess.run(cmd, capture_output=True, text=True)

def run_bug(target_path: Path, *args: str) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(BUG_SCRIPT), "FEAT-001", str(target_path)] + list(args)
    return subprocess.run(cmd, capture_output=True, text=True)

def run_viewpoints(target_path: Path, *args: str) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(VIEWPOINT_SCRIPT), "FEAT-001", str(target_path), "--title", "認証機能"] + list(args)
    return subprocess.run(cmd, capture_output=True, text=True)

def run_cases(target_path: Path, *args: str) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(CASES_SCRIPT), "FEAT-001", str(target_path), "--title", "認証機能"] + list(args)
    return subprocess.run(cmd, capture_output=True, text=True)

def test_QLT_FR_006_impact_analysis_output():
    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir)
        subprocess.run([sys.executable, str(INIT_SCRIPT), str(target)], check=True)
        
        res = run_impact(target, "--save")
        assert res.returncode == 0, res.stderr
        
        report_file = target / ".spec/quality/analyses/impact-feat-001.md"
        assert report_file.is_file()
        assert "影響分析レポート: FEAT-001" in report_file.read_text(encoding="utf-8")

def test_QLT_FR_006_bug_analysis_matching():
    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir)
        subprocess.run([sys.executable, str(INIT_SCRIPT), str(target)], check=True)
        
        rules_file = target / ".spec/quality/rules/rules-ledger.md"
        rules_file.write_text(
            "# 台帳\n\n| Rule ID | 種別 | 対象スコープ | 再発防止ルール (general_rule) | 発生要因 (cause) | 登録日 |\n|---|---|---|---|---|---|\n| R-101 | 認証 | auth/token | トークン有効期限を厳格検証 | 期限切れトークンをバイパス | 2026-08-14 |\n",
            encoding="utf-8"
        )
        
        res = run_bug(target, "--keywords", "auth", "--save")
        assert res.returncode == 0, res.stderr
        
        report_file = target / ".spec/quality/analyses/bug-trend-feat-001.md"
        assert report_file.is_file()
        content = report_file.read_text(encoding="utf-8")
        assert "R-101" in content
        assert "トークン有効期限を厳格検証" in content

def test_QLT_FR_007_viewpoints_generation():
    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir)
        subprocess.run([sys.executable, str(INIT_SCRIPT), str(target)], check=True)
        
        res = run_viewpoints(target, "--save")
        assert res.returncode == 0, res.stderr
        
        vp_file = target / ".spec/quality/viewpoints/viewpoints-feat-001.md"
        assert vp_file.is_file()
        content = vp_file.read_text(encoding="utf-8")
        assert "テスト観点設計書: FEAT-001" in content
        assert "正常系 (Functional)" in content
        assert "境界値 (Boundary)" in content
        assert "セキュリティ (Security)" in content

def test_QLT_FR_007_cases_scaffold_generation():
    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir)
        res = run_cases(target, "--scaffold")
        assert res.returncode == 0, res.stderr
        
        test_file = target / "tests/test_feat_001.py"
        assert test_file.is_file()
        code = test_file.read_text(encoding="utf-8")
        assert "test_feat_001_happy_path" in code
        assert "test_feat_001_boundary_data" in code
        assert "sql_injection" in code
        assert "xss_payload" in code
