#!/usr/bin/env python3
"""quality_bug_analysis.py — bitz-quality 不具合傾向分析スクリプト

再発防止ルール台帳（rules-ledger.md）および履歴から、変更領域に関連する
過去の類似バグ傾向・禁止規則を照合・抽出し、分析レポートを出力する。
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

def analyze_bug_trends(target_dir: Path, keywords: list[str]) -> dict:
    """台帳からキーワードに関連するルールと傾向を抽出する"""
    rules_file = target_dir / ".spec/quality/rules/rules-ledger.md"
    matched_rules = []
    
    if rules_file.exists():
        content = rules_file.read_text(encoding="utf-8")
        for line in content.splitlines():
            if line.strip().startswith("|") and not line.strip().startswith("| Rule ID") and not line.strip().startswith("|---"):
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 5:
                    rule_id, r_type, scope, general_rule, cause = parts[:5]
                    # キーワードマッチング（キーワード未指定時は全件）
                    if not keywords or any(k.lower() in (scope + general_rule + cause).lower() for k in keywords):
                        matched_rules.append({
                            "id": rule_id,
                            "type": r_type,
                            "scope": scope,
                            "rule": general_rule,
                            "cause": cause
                        })

    return {
        "analyzed_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "keywords": keywords,
        "matched_count": len(matched_rules),
        "rules": matched_rules
    }

def format_bug_analysis_markdown(feature_id: str, result: dict) -> str:
    lines = [
        f"# 不具合傾向分析レポート: {feature_id}",
        f"",
        f"- **分析日時**: {result['analyzed_at']}",
        f"- **対象キーワード**: {', '.join(result['keywords']) if result['keywords'] else '全体'}",
        f"- **該当再発防止ルール数**: {result['matched_count']} 件",
        f"",
        f"## 1. 該当する過去の再発防止ルール (general_rule)",
        f"",
        f"| Rule ID | 種別 | 対象スコープ | 再発防止ルール (general_rule) | 発生要因 (cause) |",
        f"|---|---|---|---|---|",
    ]
    for r in result["rules"]:
        lines.append(f"| {r['id']} | {r['type']} | {r['scope']} | {r['rule']} | {r['cause']} |")
    if not result["rules"]:
        lines.append("| - | - | 全般 | (該当する過去の不具合ルールはありません) | - |")

    lines.extend([
        f"",
        f"## 2. 重点テスト設計指針",
        f"",
    ])
    if result["rules"]:
        lines.append("- 上記の過去発生要因（cause）を再現する異常系テストケースを必ず設計すること。")
        lines.append("- 再発防止ルールが守られていることをテストアサーションで検証すること。")
    else:
        lines.append("- 一般的な境界値・異常系ケースを網羅するテスト設計を実施すること。")

    return "\n".join(lines) + "\n"

def main() -> int:
    parser = argparse.ArgumentParser(
        description="再発防止ルール台帳から過去の不具合傾向を分析します。"
    )
    parser.add_argument("feature_id", help="フィーチャーID (例: FEAT-001)")
    parser.add_argument("target", nargs="?", default=".", help="プロジェクトルートパス")
    parser.add_argument("--keywords", nargs="*", default=[], help="絞り込みキーワード一覧")
    parser.add_argument("--save", action="store_true", help=".spec/quality/analyses/ に保存する")
    
    args = parser.parse_args()
    target_path = Path(args.target)
    
    if not target_path.exists() or not target_path.is_dir():
        print(f"[ERROR] 対象ディレクトリが存在しません: {args.target}", file=sys.stderr)
        return 1

    result = analyze_bug_trends(target_path, keywords=args.keywords)
    md_output = format_bug_analysis_markdown(args.feature_id, result)
    
    if args.save:
        out_dir = target_path / ".spec/quality/analyses"
        out_dir.mkdir(parents=True, exist_ok=True)
        safe_id = args.feature_id.lower().replace("/", "-").replace(" ", "-")
        out_file = out_dir / f"bug-trend-{safe_id}.md"
        out_file.write_text(md_output, encoding="utf-8")
        print(f"[✔] 不具合傾向分析レポートを保存しました: {out_file}")
    else:
        print(md_output)
        
    return 0

if __name__ == "__main__":
    sys.exit(main())
