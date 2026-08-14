import subprocess
import sys
import tempfile
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent
TRACE_SCRIPT = ROOT / "plugins/bitz-quality/skills/quality-trace/scripts/quality_trace.py"
INIT_SCRIPT = ROOT / "plugins/bitz-quality/skills/quality-init/scripts/quality_init.py"

def test_QLT_FR_011_traceability_verification():
    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir)
        subprocess.run([sys.executable, str(INIT_SCRIPT), str(target)], check=True)
        
        # 要件ファイルの作成
        req_dir = target / ".spec/requirements"
        req_dir.mkdir(parents=True, exist_ok=True)
        (req_dir / "REQ-001.md").write_text("---\nid: REQ-001\nstatus: verified\n---\n### REQ-001 テスト要件\n", encoding="utf-8")
        (req_dir / "REQ-002.md").write_text("---\nid: REQ-002\nstatus: verified\n---\n### REQ-002 未カバー要件\n", encoding="utf-8")
        
        # テストファイルの作成（REQ-001 のみカバー）
        tests_dir = target / "tests"
        tests_dir.mkdir(parents=True, exist_ok=True)
        (tests_dir / "test_sample.py").write_text("def test_req_001_logic():\n    assert True\n", encoding="utf-8")
        
        # 1. 未カバーが存在するので returncode != 0
        res1 = subprocess.run([sys.executable, str(TRACE_SCRIPT), "verify", str(target), "--save"], capture_output=True, text=True)
        assert res1.returncode != 0
        assert "INCOMPLETE" in res1.stdout or "未カバー" in res1.stdout
        
        # 2. REQ-002 のテストを追加して再実行
        (tests_dir / "test_sample2.py").write_text("def test_req_002_logic():\n    assert True\n", encoding="utf-8")
        res2 = subprocess.run([sys.executable, str(TRACE_SCRIPT), "verify", str(target), "--save"], capture_output=True, text=True)
        assert res2.returncode == 0, res2.stderr
        assert "100.0%" in res2.stdout
        assert "PASS" in res2.stdout

def test_QLT_FR_012_verification_evidence_report():
    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir)
        subprocess.run([sys.executable, str(INIT_SCRIPT), str(target)], check=True)
        
        req_dir = target / ".spec/requirements"
        req_dir.mkdir(parents=True, exist_ok=True)
        (req_dir / "REQ-100.md").write_text("---\nid: REQ-100\nstatus: verified\n---\n### REQ-100 証跡テスト\n", encoding="utf-8")
        
        tests_dir = target / "tests"
        tests_dir.mkdir(parents=True, exist_ok=True)
        (tests_dir / "test_evidence.py").write_text("def test_req_100():\n    assert True\n", encoding="utf-8")
        
        res = subprocess.run([sys.executable, str(TRACE_SCRIPT), "verify", str(target), "--save"], capture_output=True, text=True)
        assert res.returncode == 0
        
        matrix_file = target / ".spec/quality/reports/traceability-matrix.md"
        assert matrix_file.is_file()
        content = matrix_file.read_text(encoding="utf-8")
        assert "REQ-100" in content
        assert "COVERED" in content
