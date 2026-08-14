import subprocess
import sys
import tempfile
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent
INIT_SCRIPT = ROOT / "plugins/bitz-quality/skills/quality-init/scripts/quality_init.py"

def run_init(target_path: Path, *extra_args: str) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(INIT_SCRIPT), str(target_path)] + list(extra_args)
    return subprocess.run(cmd, capture_output=True, text=True)

def test_QLT_FR_002_creates_subdirectories():
    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir)
        res = run_init(target)
        assert res.returncode == 0, res.stderr
        
        quality_root = target / ".spec" / "quality"
        assert quality_root.exists()
        for subdir in ["sessions", "scorings", "analyses", "viewpoints", "reports", "rules"]:
            assert (quality_root / subdir).is_dir()
            
        rules_file = quality_root / "rules" / "rules-ledger.md"
        assert rules_file.is_file()
        assert "再発防止ルール台帳" in rules_file.read_text(encoding="utf-8")

def test_QLT_FR_002_dry_run_does_not_write():
    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir)
        res = run_init(target, "--dry-run")
        assert res.returncode == 0, res.stderr
        
        quality_root = target / ".spec" / "quality"
        assert not quality_root.exists()

def test_QLT_FR_002_preserves_existing_content():
    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir)
        rules_dir = target / ".spec" / "quality" / "rules"
        rules_dir.mkdir(parents=True, exist_ok=True)
        rules_file = rules_dir / "rules-ledger.md"
        rules_file.write_text("CUSTOM_RULE_CONTENT", encoding="utf-8")
        
        res = run_init(target)
        assert res.returncode == 0, res.stderr
        assert rules_file.read_text(encoding="utf-8") == "CUSTOM_RULE_CONTENT"
