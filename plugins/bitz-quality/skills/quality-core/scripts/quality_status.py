#!/usr/bin/env python3
"""quality_status.py — bitz-quality エージェント向けQAステータス照会スクリプト

5軸リスク評価で判定された関与レベル（レベルA/B/C）に基づき、
必要な工程のみを案内し、不要な工程を自動スキップする適応型ステータス照会を行う。
"""

import argparse
import json
import re
import sys
from pathlib import Path

def get_qa_status(target_dir: Path) -> dict:
    """現在の QA セッション状態と次アクションを集計する（適応型スキップ対応）"""
    quality_dir = target_dir / ".spec/quality"
    
    # 1. 初期化状態チェック
    if not quality_dir.exists():
        return {
            "phase": "uninitialized",
            "phase_name": "未初期化",
            "session_id": "N/A",
            "involvement_level": "未設定",
            "review_verdict": "未実行",
            "trace_verdict": "未実行",
            "requirements_verified": "0/0 (0.0%)",
            "next_action": "python3 plugins/bitz-quality/skills/quality-init/scripts/quality_init.py ."
        }

    # 2. セッション情報の取得
    sessions_dir = quality_dir / "sessions"
    active_session = None
    if sessions_dir.exists():
        session_files = sorted(sessions_dir.glob("qa-session-*.json"))
        if session_files:
            try:
                active_session = json.loads(session_files[-1].read_text(encoding="utf-8"))
            except Exception:
                pass

    # 3. スコアリング情報の取得
    scorings_dir = quality_dir / "scorings"
    has_score = False
    level_code = "C"  # A, B, C
    involvement_level = "レベルC (Self QA)"
    if scorings_dir.exists() and list(scorings_dir.glob("*.md")):
        has_score = True
        for sf in scorings_dir.glob("*.md"):
            content = sf.read_text(encoding="utf-8")
            m = re.search(r"(?:レベル|Level)\s*([ABC])", content, re.IGNORECASE)
            if m:
                level_code = m.group(1).upper()
                involvement_level = f"レベル{level_code}"
                if level_code == "A":
                    involvement_level += " (Full QA)"
                elif level_code == "B":
                    involvement_level += " (Review QA)"
                else:
                    involvement_level += " (Self QA)"

    # 4. テスト設計・観点一覧の取得
    viewpoints_dir = quality_dir / "viewpoints"
    has_viewpoints = bool(viewpoints_dir.exists() and list(viewpoints_dir.glob("*.md")))

    # 5. レポート・ゲート判定の取得
    reports_dir = quality_dir / "reports"
    has_review = False
    review_verdict = "NOT_RUN"
    if reports_dir.exists():
        review_files = list(reports_dir.glob("review-*.md"))
        if review_files:
            has_review = True
            content = review_files[-1].read_text(encoding="utf-8")
            if "判定結果**: **FAIL" in content:
                review_verdict = "FAIL ❌"
            elif "判定結果**: **CONDITIONAL" in content:
                review_verdict = "CONDITIONAL_PASS ⚠️"
            elif "判定結果**: **PASS" in content:
                review_verdict = "PASS ✅"

    # 6. トレーサビリティマトリクスの取得
    matrix_file = reports_dir / "traceability-matrix.md" if reports_dir.exists() else None
    has_matrix = bool(matrix_file and matrix_file.exists())
    trace_verdict = "NOT_RUN"
    if has_matrix:
        content = matrix_file.read_text(encoding="utf-8")
        if "判定**: **PASS" in content:
            trace_verdict = "PASS ✅"
        else:
            trace_verdict = "INCOMPLETE ⚠️"

    # 7. SDD 要件充足率の集計
    req_dir = target_dir / ".spec/requirements"
    total_reqs = 0
    verified_reqs = 0
    if req_dir.exists():
        for f in req_dir.glob("*.md"):
            total_reqs += 1
            if "status: verified" in f.read_text(encoding="utf-8"):
                verified_reqs += 1
    req_rate = (verified_reqs / total_reqs * 100) if total_reqs > 0 else 100.0

    # 8. 適応型フロー（Adaptive Workflow）判定
    if not has_score:
        phase = "scoring"
        phase_name = "Phase 1: リスクスコアリング待ち"
        next_action = "python3 plugins/bitz-quality/skills/quality-score/scripts/quality_score.py <FEATURE_ID> --scale 2 --security 1 --blast-radius 2 --save"

    elif level_code == "C":
        # 【レベルC: Self QA / 最小限】
        # テスト設計・LLM多観点レビュー・トレーサビリティをスキップし、第1層静的チェックのみで即完了
        phase = "done"
        phase_name = "Phase: Done (レベルC: セルフチェック完了・マージ可能)"
        next_action = "python3 plugins/bitz-quality/skills/quality-gate/scripts/quality_gate.py . --staged"

    elif level_code == "B":
        # 【レベルB: Review QA / 標準】
        # 具象ケース設計・ミューテーションをスキップ。観点設計 + LLMレビューを実施
        if not has_viewpoints:
            phase = "design"
            phase_name = "Phase 2: テスト観点設計待ち (レベルB: 観点一覧のみ)"
            next_action = "python3 plugins/bitz-quality/skills/quality-design/scripts/quality_viewpoints.py <FEATURE_ID> . --save"
        elif not has_review or review_verdict == "FAIL ❌":
            phase = "gate"
            phase_name = "Phase 3: 3層品質ゲート検証待ち (レベルB: レビュー実施)"
            next_action = "python3 plugins/bitz-quality/skills/quality-review/scripts/quality_llm_review.py <FEATURE_ID> . --save --auto-ledger"
        else:
            phase = "done"
            phase_name = "Phase: Done (レベルB: レビュー合格・マージ可能)"
            next_action = "python3 plugins/bitz-quality/skills/quality-report/scripts/quality_report.py . --save"

    else:
        # 【レベルA: Full QA / 厳格】
        # 全5工程（影響分析・観点・ケース・3層ゲート・トレーサビリティ・測定系）を完全実行
        if not has_viewpoints:
            phase = "design"
            phase_name = "Phase 2: テスト観点・ケース設計待ち (レベルA: フル設計)"
            next_action = "python3 plugins/bitz-quality/skills/quality-design/scripts/quality_viewpoints.py <FEATURE_ID> . --save"
        elif not has_review or review_verdict == "FAIL ❌":
            phase = "gate"
            phase_name = "Phase 3: 3層品質ゲート検証待ち (レベルA: 厳格検証)"
            next_action = "python3 plugins/bitz-quality/skills/quality-review/scripts/quality_llm_review.py <FEATURE_ID> . --save --auto-ledger"
        elif not has_matrix or trace_verdict != "PASS ✅":
            phase = "trace"
            phase_name = "Phase 4: 要件トレーサビリティ検証待ち (レベルA: 100%照合必須)"
            next_action = "python3 plugins/bitz-quality/skills/quality-trace/scripts/quality_trace.py verify . --save"
        else:
            phase = "done"
            phase_name = "Phase 5: 全品質ゲート合格 (レベルA: フルQA完了)"
            next_action = "python3 plugins/bitz-quality/skills/quality-report/scripts/quality_report.py . --save"

    return {
        "phase": phase,
        "phase_name": phase_name,
        "session_id": active_session.get("session_id") if active_session else "N/A",
        "involvement_level": involvement_level,
        "review_verdict": review_verdict,
        "trace_verdict": trace_verdict,
        "requirements_verified": f"{verified_reqs}/{total_reqs} ({req_rate:.1f}%)",
        "next_action": next_action
    }

def main() -> int:
    parser = argparse.ArgumentParser(
        description="現在の QA セッション状態と適応型次アクションを照会します。"
    )
    parser.add_argument("target", nargs="?", default=".", help="プロジェクトルートパス")
    parser.add_argument("--json", action="store_true", help="JSON 形式で出力する")
    
    args = parser.parse_args()
    target_path = Path(args.target)
    
    status = get_qa_status(target_path)
    
    if args.json:
        print(json.dumps(status, indent=2, ensure_ascii=False))
    else:
        print(f"# BitzQuality 状態サマリー: {status['phase_name']}")
        print(f"- **セッション ID**: `{status['session_id']}`")
        print(f"- **関与レベル**: **{status['involvement_level']}**")
        print(f"- **LLM レビュー判定**: {status['review_verdict']}")
        print(f"- **要件トレーサビリティ**: {status['trace_verdict']}")
        print(f"- **要件検証充足率**: {status['requirements_verified']}")
        print(f"\n## 次のアクション")
        print(f"> `{status['next_action']}`\n")
        
    return 0

if __name__ == "__main__":
    sys.exit(main())
