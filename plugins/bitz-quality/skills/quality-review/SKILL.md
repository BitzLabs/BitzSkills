---
name: quality-review
description: レビュー指摘事項から発生要因（cause）と再発防止ルール（general_rule）を抽出し、再発防止ルール台帳（rules-ledger.md）へ自律蓄積する。「レビュー指摘をルール化して」「再発防止ルールを登録して」「quality-review」と言われたときに使用する。QA全体の統括は quality-core、品質ゲート判定は quality-gate が担当する。
metadata:
  version: "0.1.0"
  author: br7.hide
  created: "2026-08-14"
  updated: "2026-08-14"
---

# quality-review

`quality-review` は、**再発防止自律蓄積ループ**を担うスキルです。
レビュー指摘や不具合から発生要因（`cause`）と再発防止ルール（`general_rule`）を抽出し、台帳へ永続化します。

## 1. 再発防止ループの構成

```mermaid
graph LR
    Review["多観点レビュー / Gate"] --> Finding["Critical / High 指摘"]
    Finding --> Extract["cause / general_rule 抽出"]
    Extract --> Ledger["rules-ledger.md 追記"]
    Ledger --> NextGate["次回以降の品質ゲート / 不具合分析へ自動反映"]
```

## 2. 実行手順

```bash
python3 <このスキル>/scripts/quality_rule_extractor.py R-102 . \
  --type "API" \
  --scope "endpoints/user" \
  --rule "レスポンスに機密情報（パスワードハッシュ等）を含めない" \
  --cause "シリアライザのフィールド除外設定漏れ"
```

## 3. 規律

- **cause と general_rule のペア必須**: 指摘に対する「なぜ起きたか」と「どう防ぐか」が明記されていないルールは登録しない。
- **次回ゲートへの自動フィードバック**: 登録されたルールは `quality-design`（不具合傾向分析）および `quality-gate`（静的チェック）のインプットとして直ちに機能する。
