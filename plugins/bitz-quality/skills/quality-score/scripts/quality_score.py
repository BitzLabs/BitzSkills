#!/usr/bin/env python3
"""quality_score.py — bitz-quality 5軸リスクスコアリング & 関与レベル判定スクリプト

施策の5軸（開発規模・セキュリティ・影響範囲・難易度・習熟度）を評価し、
QA関与レベル（レベルA: フル / レベルB: レビュー / レベルC: セルフ）を自動判定・記録する。
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

AXES = {
    "scale": {"name": "開発規模 (Scale)", "desc": "1:小規模(<100行), 2:中規模(100-500行), 3:大規模(>500行)"},
    "security": {"name": "セキュリティ (Security)", "desc": "1:影響なし, 2:参照のみ, 3:認証/権限/暗号/PII変更"},
    "blast_radius": {"name": "影響範囲 (Blast Radius)", "desc": "1:局所的, 2:複数モジュール, 3:コア基盤/DBマイグレーション"},
    "complexity": {"name": "難易度 (Complexity)", "desc": "1:低(定型), 2:中(標準ロジック), 3:高(非同期/並行/複雑状態)"},
    "familiarity": {"name": "習熟度 (Familiarity)", "desc": "1:熟知, 2:標準, 3:初見/新技術/不慣れ"}
}

def calculate_level(scores: dict[str, int]) -> tuple[str, str]:
    """スコアから関与レベルと理由を判定する"""
    total = sum(scores.values())
    
    # クリティカルルール: セキュリティまたは影響範囲が 3 の場合は強制レベルA
    if scores.get("security") == 3:
        return "Level A (Full QA)", f"合計スコア {total}点（セキュリティ重要度=3 のため強制適用）"
    if scores.get("blast_radius") == 3:
        return "Level A (Full QA)", f"合計スコア {total}点（影響範囲=3 [DB/基盤変更] のため強制適用）"
    
    if total >= 12:
        return "Level A (Full QA)", f"合計スコア {total}点 (>=12: 高リスク施策)"
    elif total >= 8:
        return "Level B (Review QA)", f"合計スコア {total}点 (8-11: 中リスク施策)"
    else:
        return "Level C (Self QA)", f"合計スコア {total}点 (5-7: 低リスク施策)"

def generate_markdown_report(target_id: str, scores: dict[str, int], level: str, reason: str, details: str = "") -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    total = sum(scores.values())
    
    lines = [
        f"# リスクスコアリング評価書: {target_id}",
        f"",
        f"- **評価日時**: {now}",
        f"- **判定結果**: **{level}**",
        f"- **判定理由**: {reason}",
        f"- **合計スコア**: {total} / 15 点",
        f"",
        f"## 5軸評価詳細",
        f"",
        f"| 軸 | 項目 | スコア (1-3) | 評価基準 |",
        f"|---|---|---|---|",
    ]
    for key, info in AXES.items():
        score = scores.get(key, 1)
        lines.append(f"| {key} | {info['name']} | {score} | {info['desc']} |")
    
    if details:
        lines.extend([
            f"",
            f"## 評価メモ・特記事項",
            f"",
            f"{details}",
        ])
    
    lines.extend([
        f"",
        f"## 推奨アクション",
        f"",
    ])
    if "Level A" in level:
        lines.append("- `quality-design` によるフルテスト設計（影響・観点・ケース・データ）を実施する。")
        lines.append("- `quality-gate` の 3層チェック（静的+LLMレビュー）を通過させる。")
    elif "Level B" in level:
        lines.append("- `quality-design` でテスト観点一覧を設計し、人間またはQAエージェントのレビューを受ける。")
        lines.append("- 静的チェック（S01〜S10）を全件通過させる。")
    else:
        lines.append("- 単体テスト（ユニットテスト）の実装とセルフチェックを実施する。")
    
    return "\n".join(lines) + "\n"

def main() -> int:
    parser = argparse.ArgumentParser(
        description="施策の5軸リスクスコアリングを行い、QA関与レベルを判定します。"
    )
    parser.add_argument("feature_id", help="評価対象のフィーチャーIDまたは施策名 (例: FEATURE-001)")
    parser.add_argument("--scale", type=int, choices=[1, 2, 3], default=1, help="開発規模 (1-3)")
    parser.add_argument("--security", type=int, choices=[1, 2, 3], default=1, help="セキュリティ (1-3)")
    parser.add_argument("--blast-radius", type=int, choices=[1, 2, 3], default=1, help="影響範囲 (1-3)")
    parser.add_argument("--complexity", type=int, choices=[1, 2, 3], default=1, help="難易度 (1-3)")
    parser.add_argument("--familiarity", type=int, choices=[1, 2, 3], default=1, help="習熟度 (1-3)")
    parser.add_argument("--details", default="", help="特記事項やスコアの根拠")
    parser.add_argument("--output", help="出力先ファイルパス（指定なしの場合は標準出力）")
    parser.add_argument("--save", action="store_true", help=".spec/quality/scorings/ に自動保存する")
    
    args = parser.parse_args()
    
    scores = {
        "scale": args.scale,
        "security": args.security,
        "blast_radius": args.blast_radius,
        "complexity": args.complexity,
        "familiarity": args.familiarity,
    }
    
    level, reason = calculate_level(scores)
    report_md = generate_markdown_report(args.feature_id, scores, level, reason, details=args.details)
    
    if args.save:
        output_dir = Path(".spec/quality/scorings")
        output_dir.mkdir(parents=True, exist_ok=True)
        safe_id = args.feature_id.lower().replace("/", "-").replace(" ", "-")
        out_path = output_dir / f"score-{safe_id}.md"
        out_path.write_text(report_md, encoding="utf-8")
        print(f"[✔] スコアリング結果を保存しました: {out_path}")
    elif args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report_md, encoding="utf-8")
        print(f"[✔] スコアリング結果を出力しました: {out_path}")
    else:
        print(report_md)
        
    return 0

if __name__ == "__main__":
    sys.exit(main())
