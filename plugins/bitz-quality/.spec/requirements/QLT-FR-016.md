---
id: QLT-FR-016
version: 1.0
status: verified
domain: quality-report
priority: high
origin: 人間向け総合品質報告書設計 + 設計 v1.0.0
verification_method: example-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### QLT-FR-016 人間向け総合品質報告書の自動生成

- **説明**: `quality-report` は、人間（レビュアー・リード・QA）が施策の品質状態を一目で把握できるよう、総合スコア・リスク関与レベル・多層ゲート合否・指摘一覧・SDD要件トレーサビリティ・再発防止ルール蓄積状況を統合した Markdown 報告書（`.spec/quality/reports/quality-summary-report.md`）を自動生成できなければならない。
- **受入基準 (EARS)**:
  - WHEN `quality_report.py` が実行された THEN システムは 各品質モジュール（スコア・ゲート・レビュー・トレーサビリティ・ルール台帳）の最新結果を統合した総合報告書を出力する SHALL
  - WHEN `--save` オプションが指定された THEN システムは `.spec/quality/reports/quality-summary-report.md` に永続化する SHALL
  - WHEN 報告書が生成された THEN システムは リリース可否判定（PASS/CONDITIONAL/FAIL）とサマリーを先頭に明示する SHALL
- **検証手段**: tests/test_quality_report.py（総合レポート生成、セクション完全性、合否判定）
- **Revision History**:
  - 1.0 (2026-08-14) 初版起票・承認 (br7.hide)
  - 1.0 (2026-08-14) implementing / tests/test_quality_report.py 全 PASS により verified 化 (br7.hide)
