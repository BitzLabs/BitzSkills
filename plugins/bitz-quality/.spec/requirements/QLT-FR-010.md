---
id: QLT-FR-010
version: 1.0
status: verified
domain: quality-review
priority: high
origin: 再発防止ループ + 設計 v0.3.0
verification_method: example-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### QLT-FR-010 指摘レポートのMarkdown自動生成と台帳連携

- **説明**: `quality-review` は、LLM多観点レビューの結果から指摘事項レポート（`.spec/quality/reports/review-<id>.md`）を自動生成し、検出された P0/P1 指摘については `cause` / `general_rule` を抽出して `rules-ledger.md` へ追記しなければならない。
- **受入基準 (EARS)**:
  - WHEN レビューが完了した THEN システムは 指摘一覧・判定・スコアを含むMarkdownレポートを出力する SHALL
  - WHEN `--auto-ledger` オプションが指定された THEN システムは P0/P1 指摘から自動生成された再発防止ルールを `rules-ledger.md` に登録する SHALL
  - WHEN 指摘が0件の場合 THEN システムは 判定 PASS とクリーンレポートを出力する SHALL
- **検証手段**: tests/test_quality_review.py（レポート生成、自動台帳登録、クリーン判定）
- **Revision History**:
  - 1.0 (2026-08-14) 初版起票・承認 (br7.hide)
  - 1.0 (2026-08-14) implementing / tests/test_quality_review.py 全 PASS により verified 化 (br7.hide)
