import subprocess
import sys
import tempfile
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent
GATE_SCRIPT = ROOT / "plugins/bitz-quality/skills/quality-gate/scripts/quality_gate.py"

def run_gate(target_path: Path, *extra_args: str) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(GATE_SCRIPT), str(target_path)] + list(extra_args)
    return subprocess.run(cmd, capture_output=True, text=True)

def test_QLT_FR_005_clean_project_passes():
    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir)
        (target / "src.py").write_text("def hello():\n    return 'world'\n", encoding="utf-8")
        res = run_gate(target)
        assert res.returncode == 0, res.stderr
        assert "すべて合格 (PASS)" in res.stdout

def test_QLT_FR_005_debugger_statement_fails():
    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir)
        (target / "bad.py").write_text("def test():\n    debugger;\n", encoding="utf-8")
        res = run_gate(target)
        assert res.returncode != 0
        assert "S02: デバッガ文" in res.stdout

def test_QLT_FR_005_secret_token_fails():
    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir)
        (target / "secret.py").write_text("OPENAI_KEY = 'sk-1234567890abcdef1234567890abcdef'\n", encoding="utf-8")
        res = run_gate(target)
        assert res.returncode != 0
        assert "S03: OpenAI APIキーらしきシークレット" in res.stdout
