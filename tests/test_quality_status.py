import json
import subprocess
import sys
import tempfile
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent
STATUS_SCRIPT = ROOT / "plugins/bitz-quality/skills/quality-core/scripts/quality_status.py"
INIT_SCRIPT = ROOT / "plugins/bitz-quality/skills/quality-init/scripts/quality_init.py"
SCORE_SCRIPT = ROOT / "plugins/bitz-quality/skills/quality-score/scripts/quality_score.py"
VIEWPOINTS_SCRIPT = ROOT / "plugins/bitz-quality/skills/quality-design/scripts/quality_viewpoints.py"
REVIEW_SCRIPT = ROOT / "plugins/bitz-quality/skills/quality-review/scripts/quality_llm_review.py"

def test_QLT_FR_015_quality_status_uninitialized_and_init():
    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir)
        
        # 1. 未初期化時
        res0 = subprocess.run([sys.executable, str(STATUS_SCRIPT), str(target), "--json"], capture_output=True, text=True)
        assert res0.returncode == 0
        data0 = json.loads(res0.stdout)
        assert data0["phase"] == "uninitialized"
        assert "quality_init.py" in data0["next_action"]
        
        # 2. 初期化後（スコアリング待ち）
        subprocess.run([sys.executable, str(INIT_SCRIPT), str(target)], check=True)
        res1 = subprocess.run([sys.executable, str(STATUS_SCRIPT), str(target), "--json"], capture_output=True, text=True)
        assert res1.returncode == 0
        data1 = json.loads(res1.stdout)
        assert data1["phase"] == "scoring"
        assert "quality_score.py" in data1["next_action"]

def test_QLT_FR_015_adaptive_flow_level_c_skips_design_and_review():
    """レベルC (Self QA): スコア判定後、テスト設計やLLMレビューをスキップして即マージ可能判定になること"""
    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir)
        subprocess.run([sys.executable, str(INIT_SCRIPT), str(target)], check=True)
        
        # レベルC のスコアリング（低リスク: 合計5点）
        subprocess.run([
            sys.executable, str(SCORE_SCRIPT), "FEAT-10",
            "--scale", "1", "--security", "1", "--blast-radius", "1", "--complexity", "1", "--familiarity", "1",
            "--save"
        ], cwd=str(target), check=True)
        
        res = subprocess.run([sys.executable, str(STATUS_SCRIPT), str(target), "--json"], capture_output=True, text=True)
        assert res.returncode == 0
        data = json.loads(res.stdout)
        
        # レベルC はテスト観点やレビューを要求せず即 Done
        assert data["phase"] == "done"
        assert "レベルC" in data["involvement_level"]
        assert "Done" in data["phase_name"]

def test_QLT_FR_015_adaptive_flow_level_b_requires_viewpoints_and_review_only():
    """レベルB (Review QA): 観点設計とレビューを要求し、具象ケース・ミューテーションをスキップすること"""
    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir)
        subprocess.run([sys.executable, str(INIT_SCRIPT), str(target)], check=True)
        
        # レベルB のスコアリング（中リスク: 合計10点）
        subprocess.run([
            sys.executable, str(SCORE_SCRIPT), "FEAT-20",
            "--scale", "2", "--security", "2", "--blast-radius", "2", "--complexity", "2", "--familiarity", "2",
            "--save"
        ], cwd=str(target), check=True)
        
        # 1. 観点一覧設計待ち
        res1 = subprocess.run([sys.executable, str(STATUS_SCRIPT), str(target), "--json"], capture_output=True, text=True)
        data1 = json.loads(res1.stdout)
        assert data1["phase"] == "design"
        assert "quality_viewpoints.py" in data1["next_action"]
        
        # 2. 観点一覧を生成
        subprocess.run([sys.executable, str(VIEWPOINTS_SCRIPT), "FEAT-20", str(target), "--title", "通常機能", "--save"], check=True)
        
        # 3. レビュー待ち
        res2 = subprocess.run([sys.executable, str(STATUS_SCRIPT), str(target), "--json"], capture_output=True, text=True)
        data2 = json.loads(res2.stdout)
        assert data2["phase"] == "gate"
        assert "quality_llm_review.py" in data2["next_action"]
        
        # 4. レビュー実行（クリーンなコード）
        (target / "code.py").write_text("def f():\n    return 1\n", encoding="utf-8")
        subprocess.run([sys.executable, str(REVIEW_SCRIPT), "FEAT-20", str(target), "--save"], check=True)
        
        # 5. レベルB はケース生成やトレーサビリティをスキップして Done
        res3 = subprocess.run([sys.executable, str(STATUS_SCRIPT), str(target), "--json"], capture_output=True, text=True)
        data3 = json.loads(res3.stdout)
        assert data3["phase"] == "done"
        assert "レベルB" in data3["involvement_level"]
