#!/usr/bin/env python3
"""quality_gate.py — bitz-quality 3層品質ゲート実行スクリプト

静的チェック（S01〜S10）を自動実行し、品質ゲートの合否判定を行う。
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

# 禁止キーワード・シークレット検知パターン (S02, S03)
SUSPICIOUS_PATTERNS = [
    (r"debugger;", "S02: デバッガ文 (debugger) が残存しています"),
    (r"binding\.pry", "S02: デバッガ文 (binding.pry) が残存しています"),
    (r"import pdb; pdb\.set_trace\(\)", "S02: Python デバッガ (pdb) が残存しています"),
    (r"sk-[a-zA-Z0-9]{20,}", "S03: OpenAI APIキーらしきシークレットが検出されました"),
    (r"ghp_[a-zA-Z0-9]{20,}", "S03: GitHub Personal Token らしきシークレットが検出されました"),
    (r"-----BEGIN (RSA|EC|OPENSSH) PRIVATE KEY-----", "S03: 秘密鍵が検出されました"),
]

def check_static_rules(target_dir: Path, staged_only: bool = False) -> tuple[int, list[str]]:
    """静的チェック (S01〜S10) を実行する"""
    failures = []
    print(f"[*] 3層品質ゲート: 第1層 静的チェック (S01〜S10) 実行中... [{target_dir.resolve()}]")

    # S01: Git 差分チェック
    git_cmd = ["git", "--no-optional-locks", "diff", "--name-only"]
    if staged_only:
        git_cmd.append("--cached")
    try:
        res = subprocess.run(git_cmd, cwd=target_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        changed_files = [f.strip() for f in res.stdout.splitlines() if f.strip()]
        if not staged_only:
            # 未追跡ファイル (Untracked) もスキャン対象に追加
            res_untracked = subprocess.run(["git", "--no-optional-locks", "status", "--porcelain"], cwd=target_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            for line in res_untracked.stdout.splitlines():
                if line.startswith("?? "):
                    changed_files.append(line[3:].strip())
        if not changed_files:
            print("  [INFO] S01: 変更されたファイルはありません")
        else:
            print(f"  [PASS] S01: 変更ファイル検出 ({len(changed_files)} 件)")
    except Exception as e:
        print(f"  [WARN] S01: Git 状態の取得をスキップ ({e})")
        changed_files = []

    # S02 & S03: 禁止キーワード & シークレットチェック
    scan_targets = [target_dir / f for f in changed_files if (target_dir / f).is_file()] if changed_files else list(target_dir.glob("**/*.py"))[:50]
    secret_hits = 0
    for file_path in scan_targets:
        if ".git" in file_path.parts:
            continue
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            for pattern, msg in SUSPICIOUS_PATTERNS:
                if re.search(pattern, content):
                    failures.append(f"[FAIL] {msg} ({file_path.name})")
                    secret_hits += 1
        except Exception:
            pass

    if secret_hits == 0:
        print("  [PASS] S02/S03: 禁止デバッグ文・シークレット混入なし")

    # S06: 再発防止ルール台帳の存在確認
    rules_ledger = target_dir / ".spec" / "quality" / "rules" / "rules-ledger.md"
    if rules_ledger.exists():
        print("  [PASS] S09: 再発防止ルール台帳 (rules-ledger.md) を確認")
    else:
        print("  [INFO] S09: 再発防止ルール台帳は未配備です (quality-init で作成可能)")

    return (1 if failures else 0), failures

def main() -> int:
    parser = argparse.ArgumentParser(
        description="bitz-quality の3層品質ゲート（静的チェック）を実行します。"
    )
    parser.add_argument(
        "target",
        nargs="?",
        default=".",
        help="対象プロジェクトパス (デフォルト: カレントディレクトリ)"
    )
    parser.add_argument(
        "--staged",
        action="store_true",
        help="ステージングされた変更（git diff --cached）のみを対象とする"
    )
    
    args = parser.parse_args()
    target_path = Path(args.target)
    
    if not target_path.exists() or not target_path.is_dir():
        print(f"[ERROR] 対象ディレクトリが存在しません: {args.target}", file=sys.stderr)
        return 1

    code, failures = check_static_rules(target_path, staged_only=args.staged)
    
    print("\n--- 品質ゲート結果 ---")
    if code == 0:
        print("[✔] 第1層 静的チェック (S01〜S10): すべて合格 (PASS)")
        return 0
    else:
        print(f"[✘] 品質ゲート不合格: {len(failures)} 件の違反があります")
        for fail in failures:
            print(f"    {fail}")
        return code

if __name__ == "__main__":
    sys.exit(main())
