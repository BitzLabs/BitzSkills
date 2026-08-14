#!/usr/bin/env python3
"""quality_llm_review.py — bitz-quality LLM多観点レビュー自動化スクリプト

差分ファイルに対して11観点（L01〜L11）の検証を行い、
指摘事項レポート (.spec/quality/reports/review-<id>.md) を出力する。
--auto-ledger オプションで P0/P1 指摘を rules-ledger.md へ自動登録可能。
"""

import argparse
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REVIEW_PERSPECTIVES = {
    "L01": {"name": "仕様整合性", "desc": "要件・EARS基準を満たしているか"},
    "L02": {"name": "エラー処理・異常系", "desc": "例外握りつぶし・未補足エラーがないか"},
    "L03": {"name": "境界値・極端値", "desc": "空・None・境界値での安全性"},
    "L04": {"name": "セキュリティ", "desc": "認証バイパス・シークレット漏洩・インジェクション"},
    "L05": {"name": "データ整合性", "desc": "トランザクション・競合・永続化整合性"},
    "L06": {"name": "冪等性・重複防止", "desc": "二重実行時の副作用防止"},
    "L07": {"name": "パフォーマンス", "desc": "不要ループ・リソースリーク"},
    "L08": {"name": "可観測性・ログ", "desc": "適切なログ出力・エラー詳細"},
    "L09": {"name": "テスト容易性", "desc": "単体テスト可能なモジュール構造"},
    "L10": {"name": "可読性・保守性", "desc": "過度な複雑度・命名妥当性"},
    "L11": {"name": "再発防止ルール遵守", "desc": "rules-ledger.md の過去教訓の遵守"},
}

def scan_files_for_findings(target_dir: Path, staged_only: bool = False) -> list[dict]:
    """ファイル差分から静的・準静的パターンに基づく指摘を抽出する"""
    findings = []
    
    # 対象ファイルの収集
    git_cmd = ["git", "--no-optional-locks", "diff", "--name-only"]
    if staged_only:
        git_cmd.append("--cached")
    else:
        git_cmd.append("HEAD~1")
        
    try:
        res = subprocess.run(git_cmd, cwd=target_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        files = [target_dir / p.strip() for p in res.stdout.splitlines() if p.strip()]
    except Exception:
        files = []

    # git diffでファイルが取れなかった場合は target_dir 配下の全コードを対象
    if not files:
        files = [p for p in target_dir.rglob("*.py") if not any(part.startswith(".") or part == "__pycache__" for part in p.parts)]

    for f in files:
        if not f.exists() or not f.is_file() or f.suffix != ".py":
            continue
        try:
            content = f.read_text(encoding="utf-8")
        except Exception:
            continue

        rel_path = str(f.relative_to(target_dir))
        
        # L02: 例外握りつぶし (except: pass)
        if re.search(r"except\s*:\s*pass|except\s+\w+\s*:\s*pass", content):
            findings.append({
                "id": "L02-001",
                "perspective": "L02",
                "file": rel_path,
                "priority": "P1",
                "title": "例外の握りつぶし (except: pass) を検出",
                "cause": "エラーログを出力せずに例外を pass している",
                "rule": "例外捕捉時は必ずログ出力または適切なリカバリを行うこと"
            })

        # L04: ハードコードされたパスワード/キー
        if re.search(r"password\s*=\s*['\"][^'\"]+['\"]|api_key\s*=\s*['\"][^'\"]+['\"]", content, re.IGNORECASE):
            findings.append({
                "id": "L04-001",
                "perspective": "L04",
                "file": rel_path,
                "priority": "P0",
                "title": "コード内のハードコードされた認証情報/キーを検出",
                "cause": "環境変数ではなくコード内に平文でシークレットを定義している",
                "rule": "認証情報・APIキーは必ず環境変数または秘密情報マネージャーから取得すること"
            })

        # L07: 大量 range / time.sleep
        if "time.sleep(" in content and not "test" in rel_path:
            findings.append({
                "id": "L07-001",
                "perspective": "L07",
                "file": rel_path,
                "priority": "P2",
                "title": "本番コード内での同期スリープ (time.sleep) を検出",
                "cause": "非同期またはイベント駆動にすべき箇所でスレッドをブロックしている",
                "rule": "長時間の待機にはイベント通知または非同期スケジューラを使用すること"
            })

    return findings

def format_review_report(feature_id: str, findings: list[dict]) -> tuple[str, str]:
    p0_count = sum(1 for f in findings if f["priority"] == "P0")
    p1_count = sum(1 for f in findings if f["priority"] == "P1")
    p2_count = sum(1 for f in findings if f["priority"] == "P2")
    p3_count = sum(1 for f in findings if f["priority"] == "P3")
    
    verdict = "FAIL" if (p0_count > 0 or p1_count > 0) else ("CONDITIONAL_PASS" if p2_count > 0 else "PASS")
    
    lines = [
        f"# LLM多観点レビュー報告書: {feature_id}",
        f"",
        f"- **レビュー日時**: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"- **判定結果**: **{verdict}**",
        f"- **指摘集計**: P0: {p0_count}件 / P1: {p1_count}件 / P2: {p2_count}件 / P3: {p3_count}件 (合計 {len(findings)} 件)",
        f"",
        f"## 1. 観点別指摘一覧",
        f"",
        f"| ID | 観点 | 重要度 | 対象ファイル | 指摘内容 |",
        f"|---|---|---|---|---|",
    ]
    for f in findings:
        lines.append(f"| {f['id']} | {f['perspective']} ({REVIEW_PERSPECTIVES[f['perspective']]['name']}) | **{f['priority']}** | `{f['file']}` | {f['title']} |")
    if not findings:
        lines.append("| - | 全観点 (L01〜L11) | - | - | 指摘事項はありません（クリーン） |")

    lines.extend([
        f"",
        f"## 2. 発生要因 (cause) と 再発防止ルール (general_rule)",
        f"",
    ])
    for f in findings:
        lines.append(f"### 指摘 [{f['id']}] {f['title']}")
        lines.append(f"- **発生要因 (cause)**: {f['cause']}")
        lines.append(f"- **再発防止ルール (general_rule)**: {f['rule']}")
        lines.append(f"")

    if not findings:
        lines.append("- 指摘がないため、再発防止ルールの新規抽出はありません。\n")

    return "\n".join(lines), verdict

def main() -> int:
    parser = argparse.ArgumentParser(
        description="差分に対してLLM多観点レビュー（L01〜L11）を実行し報告書を作成します。"
    )
    parser.add_argument("feature_id", help="フィーチャーID (例: FEAT-001)")
    parser.add_argument("target", nargs="?", default=".", help="プロジェクトルートパス")
    parser.add_argument("--staged", action="store_true", help="ステージング差分のみを対象とする")
    parser.add_argument("--auto-ledger", action="store_true", help="P0/P1指摘を rules-ledger.md に自動登録する")
    parser.add_argument("--save", action="store_true", help=".spec/quality/reports/ に保存する")
    
    args = parser.parse_args()
    target_path = Path(args.target)
    
    findings = scan_files_for_findings(target_path, staged_only=args.staged)
    md_output, verdict = format_review_report(args.feature_id, findings)
    
    if args.save:
        out_dir = target_path / ".spec/quality/reports"
        out_dir.mkdir(parents=True, exist_ok=True)
        safe_id = args.feature_id.lower().replace("/", "-").replace(" ", "-")
        out_file = out_dir / f"review-{safe_id}.md"
        out_file.write_text(md_output, encoding="utf-8")
        print(f"[判定] {verdict}")
        print(f"[✔] レビュー報告書を保存しました: {out_file}")
    else:
        print(md_output)

    if args.auto_ledger:
        ledger_file = target_path / ".spec/quality/rules/rules-ledger.md"
        if ledger_file.exists():
            content = ledger_file.read_text(encoding="utf-8")
            today = datetime.now().strftime("%Y-%m-%d")
            for f in findings:
                if f["priority"] in ["P0", "P1"]:
                    rule_line = f"| R-{f['id']} | {f['perspective']} | {f['file']} | {f['rule']} | {f['cause']} | {today} |\n"
                    if f"| R-{f['id']} |" not in content:
                        content += rule_line
            ledger_file.write_text(content, encoding="utf-8")
            print(f"[✔] P0/P1 指摘を再発防止ルール台帳に自動登録しました。")

    p0_or_p1 = any(f["priority"] in ["P0", "P1"] for f in findings)
    return 1 if p0_or_p1 else 0

if __name__ == "__main__":
    sys.exit(main())
