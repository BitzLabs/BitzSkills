#!/usr/bin/env python3
"""quality_rule_extractor.py — bitz-quality 再発防止ルール抽出・蓄積スクリプト

レビュー指摘事項や不具合分析から発生要因 (cause) と再発防止ルール (general_rule) を抽出し、
.spec/quality/rules/rules-ledger.md へ追記・自律蓄積する。
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

def append_rule_to_ledger(
    target_dir: Path,
    rule_id: str,
    rule_type: str,
    scope: str,
    general_rule: str,
    cause: str
) -> bool:
    rules_file = target_dir / ".spec/quality/rules/rules-ledger.md"
    if not rules_file.exists():
        rules_file.parent.mkdir(parents=True, exist_ok=True)
        rules_file.write_text(
            "# 再発防止ルール台帳 (Rules Ledger)\n\n"
            "品質レビュー・障害・不具合から得られた教訓を恒久ルールとして蓄積します。\n\n"
            "| Rule ID | 種別 | 対象スコープ | 再発防止ルール (general_rule) | 発生要因 (cause) | 登録日 |\n"
            "|---|---|---|---|---|---|\n",
            encoding="utf-8"
        )

    content = rules_file.read_text(encoding="utf-8")
    
    # 既存IDチェック
    for line in content.splitlines():
        if f"| {rule_id} |" in line:
            print(f"[WARN] 既存の Rule ID '{rule_id}' が既に存在します。スキップします。")
            return False

    today = datetime.now().strftime("%Y-%m-%d")
    new_entry = f"| {rule_id} | {rule_type} | {scope} | {general_rule} | {cause} | {today} |\n"
    
    # 末尾に追記
    if not content.endswith("\n"):
        content += "\n"
    content += new_entry
    rules_file.write_text(content, encoding="utf-8")
    return True

def main() -> int:
    parser = argparse.ArgumentParser(
        description="レビュー指摘から cause と general_rule を抽出し、台帳へ追記します。"
    )
    parser.add_argument("rule_id", help="ルールID (例: R-102)")
    parser.add_argument("target", nargs="?", default=".", help="プロジェクトルートパス")
    parser.add_argument("--type", required=True, help="ルール種別 (例: 認証, DB, エラーハンドリング)")
    parser.add_argument("--scope", required=True, help="対象スコープ (例: auth/jwt, models/user)")
    parser.add_argument("--rule", required=True, help="再発防止ルール (general_rule)")
    parser.add_argument("--cause", required=True, help="発生要因 (cause)")
    
    args = parser.parse_args()
    target_path = Path(args.target)
    
    success = append_rule_to_ledger(
        target_path,
        args.rule_id,
        args.type,
        args.scope,
        args.rule,
        args.cause
    )
    
    if success:
        print(f"[✔] 再発防止ルール {args.rule_id} を台帳に登録しました。")
        return 0
    else:
        return 1

if __name__ == "__main__":
    sys.exit(main())
