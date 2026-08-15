#!/usr/bin/env python3
"""quality_doctor.py — bitz-quality 環境診断スクリプト

プロジェクトの .spec/quality/ 構造、依存関係、ルール台帳、セッションファイルの
健全性を読み取り専用で診断し、レポートを出力する。
"""

import argparse
import json
import sys
from pathlib import Path

REQUIRED_SUBDIRS = [
    "sessions",
    "scorings",
    "analyses",
    "viewpoints",
    "reports",
    "rules",
]

def check_quality_health(target_dir: Path) -> tuple[int, list[str]]:
    """プロジェクトの品質環境を診断する"""
    issues = []
    quality_root = target_dir / ".spec" / "quality"
    
    print(f"[*] BitzQuality 環境診断: {target_dir.resolve()}")

    # 1. .spec/quality ルートの存在確認
    if not quality_root.exists():
        issues.append("[FAIL] .spec/quality/ ディレクトリが存在しません (quality-init を実行してください)")
        return 1, issues
    else:
        print("  [PASS] .spec/quality/ ディレクトリが存在します")

    # 2. 必須サブディレクトリの確認
    for subdir in REQUIRED_SUBDIRS:
        subdir_path = quality_root / subdir
        if not subdir_path.exists() or not subdir_path.is_dir():
            issues.append(f"[WARN] 必須サブディレクトリが存在しません: .spec/quality/{subdir}")
        else:
            print(f"  [PASS] サブディレクトリ確認: .spec/quality/{subdir}")

    # 3. ルール台帳の確認
    rules_file = quality_root / "rules" / "rules-ledger.md"
    if not rules_file.exists():
        issues.append("[WARN] 再発防止ルール台帳が存在しません: .spec/quality/rules/rules-ledger.md")
    else:
        print("  [PASS] 再発防止ルール台帳確認: .spec/quality/rules/rules-ledger.md")

    # 4. 進行中セッションの検証
    sessions_dir = quality_root / "sessions"
    if sessions_dir.exists():
        for session_file in sessions_dir.glob("*.json"):
            try:
                data = json.loads(session_file.read_text(encoding="utf-8"))
                if "session_id" not in data or "current_phase" not in data:
                    issues.append(f"[WARN] セッションファイルの形式が不完全です: {session_file.name}")
                else:
                    print(f"  [PASS] セッションファイル検証: {session_file.name} (Phase {data.get('current_phase')})")
            except Exception as e:
                issues.append(f"[ERROR] セッションファイルのパースに失敗しました: {session_file.name} ({e})")

    return (1 if issues else 0), issues

def main() -> int:
    parser = argparse.ArgumentParser(
        description="bitz-quality のプロジェクト品質管理環境を読み取り専用で診断します。"
    )
    parser.add_argument(
        "target",
        nargs="?",
        default=".",
        help="診断対象のプロジェクトルートパス (デフォルト: カレントディレクトリ)"
    )
    
    args = parser.parse_args()
    target_path = Path(args.target)
    
    if not target_path.exists() or not target_path.is_dir():
        print(f"[ERROR] 対象ディレクトリが存在しません: {args.target}", file=sys.stderr)
        return 1

    exit_code, issues = check_quality_health(target_path)
    
    print("\n--- 診断結果サマリー ---")
    if not issues:
        print("[✔] すべてのチェックに合格しました。品質環境は健全です。")
        return 0
    else:
        print(f"[!] {len(issues)} 件の指摘事項があります:")
        for issue in issues:
            print(f"    {issue}")
        return exit_code

if __name__ == "__main__":
    sys.exit(main())
