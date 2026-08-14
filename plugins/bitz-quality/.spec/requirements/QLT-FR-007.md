---
id: QLT-FR-007
version: 1.0
status: verified
domain: quality-design
priority: high
origin: アルダグラムQA専門エージェント分業モデル + 設計 v0.1.0
verification_method: example-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### QLT-FR-007 テスト観点一覧・具象ケース・境界値テストデータの自動設計

- **説明**: `quality-design` は、影響分析と仕様に基づいて機能テスト・異常系・境界値・セキュリティ等のテスト観点一覧を導出し、具象テストケースおよびテスト入力データを自動設計しなければならない。
- **受入基準 (EARS)**:
  - WHEN テスト観点設計エージェントが起動された THEN システムは 機能・非機能・異常系・境界値・互換性の各観点を網羅した設計書を `.spec/quality/viewpoints/` に作成する SHALL
  - WHEN テストケース・データ設計エージェントが起動された THEN システムは 各観点に対応する具象テストケースと境界値テストデータを生成する SHALL
  - WHEN 生成されたテスト設計書が人間によって承認された THEN システムは 自動テストコード（`tests/`）の骨格スキャフォールドを出力する SHALL
- **検証手段**: tests/test_quality_design.py（観点網羅性、ケース生成、データ生成）
- **Revision History**:
  - 1.0 (2026-08-14) 初版起票 (br7.hide)
  - 1.0 (2026-08-14) 人間裁定・多観点レビュー（QLT-REV-001 PASS）により approved 化 (br7.hide)
  - 1.0 (2026-08-14) implementing / tests/test_quality_design.py 全 PASS により verified 化 (br7.hide)
