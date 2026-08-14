---
id: QLT-FR-004
version: 1.0
status: verified
domain: quality-score
priority: high
origin: アルダグラム5軸リスクスコアリング + 設計 v0.1.0
verification_method: example-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### QLT-FR-004 5軸リスクスコアリングと関与レベル自動判定

- **説明**: `quality-score` は、施策の5軸（開発規模・セキュリティ・影響範囲・難易度・習熟度）を評価し、QA関与レベル（レベルA: フルQA / レベルB: QAレビュー / レベルC: セルフQA）を自動判定・記録しなければならない。
- **受入基準 (EARS)**:
  - WHEN 5軸の各スコア (1〜3) が与えられた THEN システムは 合計スコアおよびクリティカル条件に基づき関与レベル (A/B/C) を算定する SHALL
  - WHEN セキュリティまたは影響範囲のスコアが 3 の場合 THEN システムは 合計スコアに関わらず強制的に レベルA (Full QA) と判定する SHALL
  - WHEN `--save` オプションが指定された THEN システムは `.spec/quality/scorings/` 配下に評価レポートMarkdownを保存する SHALL
- **検証手段**: tests/test_quality_score.py（レベルA/B/C境界値、強制レベルA、ファイル保存）
- **Revision History**:
  - 1.0 (2026-08-14) 初版起票 (br7.hide)
  - 1.0 (2026-08-14) 人間裁定・多観点レビュー（QLT-REV-001 PASS）により approved 化 (br7.hide)
  - 1.0 (2026-08-14) implementing / tests/test_quality_score.py 全 PASS により verified 化 (br7.hide)
