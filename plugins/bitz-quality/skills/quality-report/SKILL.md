---
name: quality-report
description: 人間向け総合品質報告書（ダッシュボード・多層ゲート合否・指摘一覧・SDD要件トレーサビリティ・再発防止ルール蓄積状況）を自動生成する。「品質レポートを出力して」「総合品質報告書を作成して」「quality-report」と言われたときに使用する。
metadata:
  version: "0.1.0"
  author: br7.hide
  created: "2026-08-14"
  updated: "2026-08-14"
---

# quality-report

`quality-report` は、開発者・レビュアー・QAリードが PR レビューやリリース判断時に一目で品質状態を確認できる**総合品質報告書（Markdown）**を自動生成するスキルです。

## 1. 報告書の構成

```mermaid
graph TD
    Data[".spec/quality/ (scorings, reports, rules)"] --> Report["quality-report スキル"]
    Report --> Out[".spec/quality/reports/quality-summary-report.md"]
    Out --> Sec1["1. 総合品質ダッシュボード & サインオフ"]
    Out --> Sec2["2. SDD 要件トレーサビリティ状況"]
    Out --> Sec3["3. レビュー指摘 & 再発防止状況"]
    Out --> Sec4["4. リリース判定 & 推奨事項"]
```

## 2. 実行手順

### 手順 1: 総合品質報告書の生成・保存
```bash
python3 <このスキル>/scripts/quality_report.py . --save
```

## 3. 規律

- **完全性の担保**: 各品質モジュール（スコアリング・ゲート・レビュー・トレーサビリティ・ルール台帳）の最新結果を統合して出力すること。
- **サインオフ基準の明示**: 総合判定（PASS / CONDITIONAL / FAIL）とリリース可否の推奨判断を先頭に明記すること。
