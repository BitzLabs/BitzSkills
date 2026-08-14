#!/usr/bin/env python3
"""quality_viewpoints.py — bitz-quality テスト観点設計スクリプト

仕様・影響分析・不具合傾向分析に基づいて、機能・異常系・境界値・セキュリティ等の
テスト観点一覧を導出し、.spec/quality/viewpoints/ に出力する。
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

STANDARD_VIEWPOINTS = [
    {"category": "正常系 (Functional)", "viewpoint": "基本フローが仕様通りに動作すること", "priority": "P0"},
    {"category": "異常系 (Exception)", "viewpoint": "無効な入力や引数で適切にエラー終了・メッセージ通知されること", "priority": "P0"},
    {"category": "境界値 (Boundary)", "viewpoint": "最小値・最大値・空文字・0件・上限超過時の挙動が正しいこと", "priority": "P1"},
    {"category": "整合性・冪等性 (Integrity)", "viewpoint": "重複実行やリトライ時にデータ破壊や二重処理が発生しないこと", "priority": "P1"},
    {"category": "セキュリティ (Security)", "viewpoint": "シークレット漏洩・不正アクセス・インジェクションの脆弱性がないこと", "priority": "P0"},
    {"category": "運用性 (Operations)", "viewpoint": "エラー時のログ出力および診断ガイダンスが明瞭であること", "priority": "P2"},
]

def generate_viewpoints(feature_id: str, title: str, domain: str) -> dict:
    items = []
    for vp in STANDARD_VIEWPOINTS:
        items.append({
            "category": vp["category"],
            "viewpoint": f"[{domain}] {title}: {vp['viewpoint']}",
            "priority": vp["priority"]
        })
        
    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "feature_id": feature_id,
        "title": title,
        "domain": domain,
        "viewpoints": items
    }

def format_viewpoints_markdown(result: dict) -> str:
    lines = [
        f"# テスト観点設計書: {result['feature_id']} {result['title']}",
        f"",
        f"- **設計日時**: {result['generated_at']}",
        f"- **対象ドメイン**: `{result['domain']}`",
        f"- **観点総数**: {len(result['viewpoints'])} 件",
        f"",
        f"## 1. テスト観点一覧 (Viewpoints Matrix)",
        f"",
        f"| # | 分類カテゴリ | テスト観点内容 | 優先度 |",
        f"|---|---|---|---|",
    ]
    for idx, vp in enumerate(result["viewpoints"], 1):
        lines.append(f"| VP-{idx:02d} | {vp['category']} | {vp['viewpoint']} | {vp['priority']} |")

    lines.extend([
        f"",
        f"## 2. カバレッジ担保指針",
        f"",
        f"- P0 観点は自動ユニットテスト（`tests/`）で 100% カバレッジを必須とする。",
        f"- P1 観点は境界値データを用いたパラメタライズテストで網羅する。",
        f"- P2 観点は運用ログおよびCLIエラー出力の目視・自動確認を行う。",
    ])
    return "\n".join(lines) + "\n"

def main() -> int:
    parser = argparse.ArgumentParser(
        description="機能仕様からテスト観点一覧を設計します。"
    )
    parser.add_argument("feature_id", help="フィーチャーID (例: FEAT-001)")
    parser.add_argument("target", nargs="?", default=".", help="プロジェクトルートパス")
    parser.add_argument("--title", default="機能実装", help="機能タイトル")
    parser.add_argument("--domain", default="core", help="対象ドメイン")
    parser.add_argument("--target-path", dest="target_opt", default=None, help="明示的な対象パス")
    parser.add_argument("--save", action="store_true", help=".spec/quality/viewpoints/ に保存する")
    
    args = parser.parse_args()
    target_path = Path(args.target_opt if args.target_opt else args.target)
    
    result = generate_viewpoints(args.feature_id, args.title, args.domain)
    md_output = format_viewpoints_markdown(result)
    
    if args.save:
        out_dir = target_path / ".spec/quality/viewpoints"
        out_dir.mkdir(parents=True, exist_ok=True)
        safe_id = args.feature_id.lower().replace("/", "-").replace(" ", "-")
        out_file = out_dir / f"viewpoints-{safe_id}.md"
        out_file.write_text(md_output, encoding="utf-8")
        print(f"[✔] テスト観点設計書を保存しました: {out_file}")
    else:
        print(md_output)
        
    return 0

if __name__ == "__main__":
    sys.exit(main())
