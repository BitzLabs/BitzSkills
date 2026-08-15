---
id: QLT-FR-013
version: 1.0
status: verified
domain: quality-measurand
priority: high
origin: 測定系モデル化 + 設計 v1.0.0
verification_method: example-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### QLT-FR-013 品質メトリクス（カバレッジ・リスクスコア・ゲート通過率）の統合測定と可視化

- **説明**: `quality-measurand` は、対象プロジェクトの要件カバレッジ、静的ゲート通過率、LLMレビュー指摘数、蓄積ルール数を集計し、統合品質メトリクスレポート（`.spec/quality/reports/quality-metrics.md`）を出力できなければならない。
- **受入基準 (EARS)**:
  - WHEN `quality_measurand.py metrics` が実行された THEN システムは 各品質指標（要件充足率・テスト通過率・未解消指摘数・ルール蓄積数）を集計してMarkdownレポートを出力する SHALL
  - WHEN 品質健全性総合スコアが算出された THEN システムは 0〜100点の総合評価と推奨改善アクションを提示する SHALL
- **検証手段**: tests/test_quality_measurand.py（メトリクス集計、総合スコア算出、レポート生成）
- **Revision History**:
  - 1.0 (2026-08-14) 初版起票・承認 (br7.hide)
  - 1.0 (2026-08-14) implementing / tests/test_quality_measurand.py 全 PASS により verified 化 (br7.hide)
