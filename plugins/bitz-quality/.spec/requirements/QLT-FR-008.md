---
id: QLT-FR-008
version: 1.0
status: verified
domain: quality-review
priority: high
origin: アルダグラム再発防止ループ + 設計 v0.1.0
verification_method: example-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### QLT-FR-008 指摘事項に対する cause / general_rule 抽出と台帳反映ループ

- **説明**: `quality-review` および `quality-gate` は、レビュー指摘事項に発生要因（`cause`）と再発防止ルール（`general_rule`）の記述を義務付け、台帳（`rules-ledger.md`）へ自律蓄積しなければならない。
- **受入基準 (EARS)**:
  - WHEN 多観点レビューで重大な指摘 (Critical/High) が記録された THEN システムは 指摘ごとに cause と general_rule のペアを抽出する SHALL
  - WHEN 抽出された general_rule が承認された THEN システムは `.spec/quality/rules/rules-ledger.md` へ追記してルール台帳を更新する SHALL
  - WHEN 次回以降の品質ゲートが実行された THEN システムは 蓄積された rules-ledger.md を読み込んで自動チェック対象に含める SHALL
- **検証手段**: tests/test_quality_review.py（cause/general_rule 抽出、台帳追記、ゲート連携）
- **Revision History**:
  - 1.0 (2026-08-14) 初版起票 (br7.hide)
  - 1.0 (2026-08-14) 人間裁定・多観点レビュー（QLT-REV-001 PASS）により approved 化 (br7.hide)
  - 1.0 (2026-08-14) implementing / tests/test_quality_review.py 全 PASS により verified 化 (br7.hide)
