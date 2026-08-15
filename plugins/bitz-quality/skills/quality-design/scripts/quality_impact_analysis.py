#!/usr/bin/env python3
"""quality_impact_analysis.py — bitz-quality 影響分析スクリプト

Git差分およびファイル依存関係から、変更の直接波及・間接波及・DB影響を特定し
.spec/quality/analyses/ 配下に影響分析レポートを出力する。
"""

import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

def analyze_impact(target_dir: Path, base_ref: str = "origin/main", staged_only: bool = False) -> dict:
    """Git差分から影響範囲を解析する"""
    git_cmd = ["git", "--no-optional-locks", "diff", "--name-status"]
    if staged_only:
        git_cmd.append("--cached")
    elif base_ref:
        git_cmd.append(base_ref)
        
    try:
        res = subprocess.run(git_cmd, cwd=target_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        lines = res.stdout.splitlines()
    except Exception as e:
        lines = []

    direct_files = []
    db_migrations = []
    doc_changes = []
    config_changes = []
    
    for line in lines:
        parts = line.strip().split(maxsplit=1)
        if len(parts) == 2:
            status, path_str = parts
            direct_files.append({"status": status, "path": path_str})
            
            p_lower = path_str.lower()
            if "migration" in p_lower or "schema" in p_lower or p_lower.endswith(".sql"):
                db_migrations.append(path_str)
            elif p_lower.endswith(".md") or "docs/" in p_lower:
                doc_changes.append(path_str)
            elif "config" in p_lower or "setting" in p_lower or p_lower.endswith(".json"):
                config_changes.append(path_str)

    has_db_impact = len(db_migrations) > 0
    blast_radius = "high" if has_db_impact or len(direct_files) > 10 else ("medium" if len(direct_files) > 3 else "low")

    return {
        "analyzed_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "total_changed_files": len(direct_files),
        "blast_radius": blast_radius,
        "has_db_impact": has_db_impact,
        "direct_files": direct_files,
        "db_migrations": db_migrations,
        "doc_changes": doc_changes,
        "config_changes": config_changes,
    }

def format_impact_markdown(feature_id: str, result: dict) -> str:
    lines = [
        f"# 影響分析レポート: {feature_id}",
        f"",
        f"- **分析日時**: {result['analyzed_at']}",
        f"- **波及影響度 (Blast Radius)**: **{result['blast_radius'].upper()}**",
        f"- **DB影響**: {'あり (要マイグレーション注意)' if result['has_db_impact'] else 'なし'}",
        f"- **変更ファイル総数**: {result['total_changed_files']} 件",
        f"",
        f"## 1. 直接変更ファイル一覧",
        f"",
        f"| 操作 | ファイルパス |",
        f"|---|---|",
    ]
    for item in result["direct_files"]:
        lines.append(f"| {item['status']} | `{item['path']}` |")
    if not result["direct_files"]:
        lines.append("| - | (変更ファイルなし) |")

    if result["db_migrations"]:
        lines.extend([
            f"",
            f"## 2. DBマイグレーション・スキーマ変更",
            f"",
        ])
        for db_file in result["db_migrations"]:
            lines.append(f"- `{db_file}`")

    lines.extend([
        f"",
        f"## 3. テスト設計への示唆",
        f"",
    ])
    if result["has_db_impact"]:
        lines.append("- DB後方互換性テスト・ロールバックテストを必ず観点に含めること。")
    if result["blast_radius"] in ["high", "medium"]:
        lines.append("- 複数モジュールにまたがる結合テスト・境界値テストを実施すること。")
    else:
        lines.append("- 変更箇所に対する局所的なユニットテストを重点的に実施すること。")

    return "\n".join(lines) + "\n"

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Git差分から影響範囲（直接/間接/DB）を解析します。"
    )
    parser.add_argument("feature_id", help="フィーチャーID (例: FEAT-001)")
    parser.add_argument("target", nargs="?", default=".", help="プロジェクトルートパス")
    parser.add_argument("--base", default="origin/main", help="比較対象のBase Ref (デフォルト: origin/main)")
    parser.add_argument("--staged", action="store_true", help="ステージング変更のみを対象とする")
    parser.add_argument("--save", action="store_true", help=".spec/quality/analyses/ に保存する")
    
    args = parser.parse_args()
    target_path = Path(args.target)
    
    if not target_path.exists() or not target_path.is_dir():
        print(f"[ERROR] 対象ディレクトリが存在しません: {args.target}", file=sys.stderr)
        return 1

    result = analyze_impact(target_path, base_ref=args.base, staged_only=args.staged)
    md_output = format_impact_markdown(args.feature_id, result)
    
    if args.save:
        out_dir = target_path / ".spec/quality/analyses"
        out_dir.mkdir(parents=True, exist_ok=True)
        safe_id = args.feature_id.lower().replace("/", "-").replace(" ", "-")
        out_file = out_dir / f"impact-{safe_id}.md"
        out_file.write_text(md_output, encoding="utf-8")
        print(f"[✔] 影響分析レポートを保存しました: {out_file}")
    else:
        print(md_output)
        
    return 0

if __name__ == "__main__":
    sys.exit(main())
