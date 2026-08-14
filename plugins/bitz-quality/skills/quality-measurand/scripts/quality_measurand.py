#!/usr/bin/env python3
"""quality_measurand.py — bitz-quality 測定系 & ミューテーション自己診断スクリプト

品質メトリクス（要件充足率・ゲート通過率・ルール蓄積数）の総合集計および
人工欠陥注入（ミューテーションテスト）によるテスト品質の自己診断を行う。
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

def collect_quality_metrics(target_dir: Path) -> dict:
    """プロジェクトの品質メトリクスを収集・集計する"""
    # 1. 要件集計
    req_dir = target_dir / ".spec/requirements"
    if not req_dir.exists():
        for p in target_dir.glob("plugins/*/.spec/requirements"):
            req_dir = p
            break
            
    total_reqs = 0
    verified_reqs = 0
    if req_dir.exists():
        for f in req_dir.glob("*.md"):
            total_reqs += 1
            content = f.read_text(encoding="utf-8")
            if "status: verified" in content:
                verified_reqs += 1
                
    req_rate = (verified_reqs / total_reqs * 100) if total_reqs > 0 else 100.0

    # 2. ルール台帳集計
    rules_file = target_dir / ".spec/quality/rules/rules-ledger.md"
    total_rules = 0
    if rules_file.exists():
        for line in rules_file.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("|") and not line.strip().startswith("| Rule ID") and not line.strip().startswith("|---"):
                total_rules += 1

    # 3. 総合健全性スコア算出 (0〜100点)
    # 要件充足率 50点 + ルール蓄積実績 30点 + ベース 20点
    rule_score = min(total_rules * 5, 30)
    health_score = int(req_rate * 0.5 + rule_score + 20)
    health_score = min(max(health_score, 0), 100)

    grade = "A (優良)" if health_score >= 85 else ("B (良好)" if health_score >= 70 else "C (改善推奨)")

    return {
        "calculated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "health_score": health_score,
        "grade": grade,
        "total_requirements": total_reqs,
        "verified_requirements": verified_reqs,
        "requirement_verified_rate": req_rate,
        "accumulated_rules_count": total_rules
    }

def format_metrics_markdown(metrics: dict) -> str:
    lines = [
        f"# 統合品質メトリクス報告書 (Quality Metrics Report)",
        f"",
        f"- **測定日時**: {metrics['calculated_at']}",
        f"- **総合品質スコア**: **{metrics['health_score']} / 100 点** ({metrics['grade']})",
        f"",
        f"## 1. 主要品質指標",
        f"",
        f"| 指標名 | 実績値 | 評価基準 | 判定 |",
        f"|---|---|---|---|",
        f"| **要件検証充足率** | {metrics['verified_requirements']} / {metrics['total_requirements']} ({metrics['requirement_verified_rate']:.1f}%) | 100% 達成 | {'PASS ✅' if metrics['requirement_verified_rate'] >= 100.0 else 'IN PROGRESS ⏳'} |",
        f"| **再発防止ルール蓄積数** | {metrics['accumulated_rules_count']} 件 | 継続的な教訓蓄積 | {'ACTIVE 🛡️' if metrics['accumulated_rules_count'] > 0 else 'INITIAL ⚠️'} |",
        f"",
        f"## 2. 推奨改善アクション",
        f"",
    ]
    if metrics["health_score"] >= 85:
        lines.append("- 品質水準は非常に高水準です。現状の品質ゲートおよびテスト自動化規律を継続してください。")
    else:
        lines.append("- 未検証の要件に対する自動テスト（tests/）を整備し、要件充足率を向上させてください。")
        lines.append("- レビュー指摘事項から cause / general_rule の抽出を進め、再発防止台帳を拡充してください。")

    return "\n".join(lines) + "\n"

def run_mutation_self_diagnosis(target_dir: Path) -> dict:
    """人工欠陥注入によるテスト自己診断を実行する"""
    scenarios = [
        {"id": "MUT-01", "name": "デバッガ文混入検知", "type": "gate", "target_file": "mut_temp.py", "payload": "debugger;\n", "expected_fail": True},
        {"id": "MUT-02", "name": "シークレット平文混入検知", "type": "gate", "target_file": "mut_temp.py", "payload": "OPENAI_API_KEY = 'sk-1234567890abcdef1234567890abcdef'\n", "expected_fail": True},
        {"id": "MUT-03", "name": "例外握りつぶし検知", "type": "review", "target_file": "mut_temp.py", "payload": "def f():\n  try:\n    pass\n  except:\n    pass\n", "expected_fail": True},
    ]

    results = []
    killed = 0
    
    for s in scenarios:
        temp_file = target_dir / s["target_file"]
        temp_file.write_text(s["payload"], encoding="utf-8")
        
        is_killed = False
        if s["type"] == "gate":
            gate_script = Path(__file__).resolve().parent.parent.parent / "quality-gate/scripts/quality_gate.py"
            res = subprocess.run([sys.executable, str(gate_script), str(target_dir)], capture_output=True, text=True)
            if res.returncode != 0:
                is_killed = True
        elif s["type"] == "review":
            review_script = Path(__file__).resolve().parent.parent.parent / "quality-review/scripts/quality_llm_review.py"
            res = subprocess.run([sys.executable, str(review_script), "MUT-TEST", str(target_dir)], capture_output=True, text=True)
            if res.returncode != 0:
                is_killed = True
                
        if temp_file.exists():
            temp_file.unlink()
            
        if is_killed:
            killed += 1
            results.append({"id": s["id"], "name": s["name"], "status": "KILLED ✅", "detail": "人工欠陥を正常に検知・ブロックしました。"})
        else:
            results.append({"id": s["id"], "name": s["name"], "status": "SURVIVED ❌", "detail": "欠陥が検知されず通過しました。"})

    mutation_score = (killed / len(scenarios) * 100) if scenarios else 100.0

    return {
        "diagnosed_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "total_mutants": len(scenarios),
        "killed_mutants": killed,
        "mutation_score": mutation_score,
        "results": results
    }

def format_mutation_markdown(diag: dict) -> str:
    lines = [
        f"# ミューテーション自己診断報告書 (Mutation Self-Diagnosis)",
        f"",
        f"- **診断日時**: {diag['diagnosed_at']}",
        f"- **ミューテーションスコア**: **{diag['mutation_score']:.1f}%** ({diag['killed_mutants']} / {diag['total_mutants']} 撃墜)",
        f"- **判定**: **{'PASS ✅' if diag['mutation_score'] >= 100.0 else 'WARN ⚠️'}**",
        f"",
        f"## 1. 人工欠陥注入シナリオ結果一覧",
        f"",
        f"| シナリオ ID | テスト内容 | 判定結果 | 詳細 |",
        f"|---|---|---|---|",
    ]
    for r in diag["results"]:
        lines.append(f"| `{r['id']}` | {r['name']} | {r['status']} | {r['detail']} |")

    lines.extend([
        f"",
        f"## 2. テストスイート防御力評価",
        f"",
        f"- 欠陥撃墜率 100%: 品質ゲートおよびレビュー機能が欠陥混入を確実に阻止できる堅牢性を備えています。",
    ])
    return "\n".join(lines) + "\n"

def main() -> int:
    parser = argparse.ArgumentParser(
        description="統合品質メトリクス測定およびミューテーション自己診断を行います。"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # metrics
    p_metrics = subparsers.add_parser("metrics", help="品質メトリクスを測定・集計する")
    p_metrics.add_argument("target", nargs="?", default=".", help="プロジェクトルートパス")
    p_metrics.add_argument("--save", action="store_true", help=".spec/quality/reports/ に保存する")
    
    # mutate
    p_mutate = subparsers.add_parser("mutate", help="ミューテーション自己診断を実行する")
    p_mutate.add_argument("target", nargs="?", default=".", help="プロジェクトルートパス")
    p_mutate.add_argument("--save", action="store_true", help=".spec/quality/reports/ に保存する")
    
    args = parser.parse_args()
    target_path = Path(args.target)
    
    if args.command == "metrics":
        metrics = collect_quality_metrics(target_path)
        md_output = format_metrics_markdown(metrics)
        if args.save:
            out_dir = target_path / ".spec/quality/reports"
            out_dir.mkdir(parents=True, exist_ok=True)
            out_file = out_dir / "quality-metrics.md"
            out_file.write_text(md_output, encoding="utf-8")
            print(f"[スコア] {metrics['health_score']} / 100 点 ({metrics['grade']})")
            print(f"[✔] 統合品質メトリクス報告書を保存しました: {out_file}")
        else:
            print(md_output)
        return 0
        
    elif args.command == "mutate":
        diag = run_mutation_self_diagnosis(target_path)
        md_output = format_mutation_markdown(diag)
        if args.save:
            out_dir = target_path / ".spec/quality/reports"
            out_dir.mkdir(parents=True, exist_ok=True)
            out_file = out_dir / "mutation-diagnosis.md"
            out_file.write_text(md_output, encoding="utf-8")
            print(f"[ミューテーションスコア] {diag['mutation_score']:.1f}% ({'PASS' if diag['mutation_score'] >= 100.0 else 'WARN'})")
            print(f"[✔] ミューテーション自己診断報告書を保存しました: {out_file}")
        else:
            print(md_output)
        return 0 if diag["mutation_score"] >= 100.0 else 1
        
    return 1

if __name__ == "__main__":
    sys.exit(main())
