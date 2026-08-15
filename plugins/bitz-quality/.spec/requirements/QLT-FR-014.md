---
id: QLT-FR-014
version: 1.0
status: verified
domain: quality-measurand
priority: high
origin: ミューテーション自己診断設計 + 設計 v1.0.0
verification_method: example-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### QLT-FR-014 ミューテーション自己診断（人工欠陥注入テスト）によるテスト品質検証

- **説明**: `quality-measurand` は、テストスイートの検出能力を検証するため、一時的な人工欠陥（ミューテーション: 戻り値反転、境界値変更、デバッガ文混入等）をシミュレートし、テストやゲートが正しく検知（Kill）できるかを自己診断できなければならない。
- **受入基準 (EARS)**:
  - WHEN `quality_measurand.py mutate` が実行された THEN システムは 静的チェック・ユニットテストに対する人工欠陥注入シナリオを実行する SHALL
  - WHEN テストが人工欠陥を正しく検出した場合 THEN システムは ミュータントを Killed（撃墜成功）と記録する SHALL
  - WHEN テストが人工欠陥を検知できなかった場合 THEN システムは ミュータントを Survived（検知漏れ）と報告し テスト改善を促す SHALL
- **検証手段**: tests/test_quality_measurand.py（ミューテーション注入、Kill判定、自己診断レポート）
- **Revision History**:
  - 1.0 (2026-08-14) 初版起票・承認 (br7.hide)
  - 1.0 (2026-08-14) implementing / tests/test_quality_measurand.py 全 PASS により verified 化 (br7.hide)
