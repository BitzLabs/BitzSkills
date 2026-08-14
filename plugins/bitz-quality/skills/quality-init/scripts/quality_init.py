#!/usr/bin/env python3
"""quality_init.py — bitz-quality 環境初期化スクリプト

プロジェクトルートまたは指定ワークスペースに .spec/quality/ ディレクトリ構造と
初期設定ファイルを安全に作成・展開する。
"""

import argparse
import json
import os
import sys
from pathlib import Path

SUBDIRECTORIES = [
    "sessions",
    "scorings",
    "analyses",
    "viewpoints",
    "reports",
    "rules",
]

DEFAULT_SESSION_TEMPLATE = {
    "version": "1.0",
    "session_id": "init",
    "current_phase": 0,
    "status": "ready",
    "inputs": [],
    "artifacts": {
        "impact_analysis": None,
        "risk_scoring": None,
        "spec_review": None,
        "test_viewpoints": [],
        "test_cases": [],
        "quality_summary": None
    },
    "history": []
}

INITIAL_RULES_TEMPLATE = """# 再発防止ルール台帳 (general_rule)

レビューや不具合分析で抽出された `general_rule`（再発防止ルール）を記録・蓄積する台帳です。
`quality-gate` および `quality-review` は本台帳を参照して品質チェックを実施します。

## ルール一覧

| Rule ID | 種別 | 対象スコープ | 再発防止ルール (general_rule) | 発生要因 (cause) | 登録日 |
|---|---|---|---|---|---|
| R-001 | 設計 | 全般 | 公開契約・マニフェストを変更した場合はリリース前検証スクリプトをパスさせる | マニフェスト間のバージョン不整合 | 2026-08-14 |
"""

def init_quality_workspace(target_dir: Path, dry_run: bool = False) -> int:
    """指定ディレクトリに .spec/quality/ を初期化する"""
    quality_root = target_dir / ".spec" / "quality"
    
    print(f"[*] BitzQuality 環境初期化: {target_dir.resolve()}")
    if dry_run:
        print("    [DRY-RUN モード: 実際のファイル書き込みは行いません]")

    # 1. サブディレクトリ作成
    for subdir in SUBDIRECTORIES:
        dir_path = quality_root / subdir
        if not dir_path.exists():
            print(f"    + ディレクトリ作成: {dir_path.relative_to(target_dir)}")
            if not dry_run:
                dir_path.mkdir(parents=True, exist_ok=True)
        else:
            print(f"    = 既存ディレクトリ: {dir_path.relative_to(target_dir)}")

    # 2. 初期ルールの作成
    rules_file = quality_root / "rules" / "rules-ledger.md"
    if not rules_file.exists():
        print(f"    + ファイル作成: {rules_file.relative_to(target_dir)}")
        if not dry_run:
            rules_file.write_text(INITIAL_RULES_TEMPLATE, encoding="utf-8")
    else:
        print(f"    = 既存ファイル: {rules_file.relative_to(target_dir)}")

    print("[✔] 初期化が正常に完了しました。")
    return 0

def main() -> int:
    parser = argparse.ArgumentParser(
        description="bitz-quality の .spec/quality/ ディレクトリ構造と設定を初期化します。"
    )
    parser.add_argument(
        "target",
        nargs="?",
        default=".",
        help="初期化対象のプロジェクトルートパス (デフォルト: カレントディレクトリ)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="書き込みを行わずに作成予定のファイル・ディレクトリを表示します"
    )
    
    args = parser.parse_args()
    target_path = Path(args.target)
    
    if not target_path.exists() or not target_path.is_dir():
        print(f"[ERROR] 対象ディレクトリが存在しません: {args.target}", file=sys.stderr)
        return 1

    return init_quality_workspace(target_path, dry_run=args.dry_run)

if __name__ == "__main__":
    sys.exit(main())
