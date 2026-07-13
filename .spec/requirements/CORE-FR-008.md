---
id: CORE-FR-008
version: 1.0
status: approved
domain: governance
priority: medium
origin: SI-CORE-021
verification_method: manual-check
derived_from:
supersedes:
superseded_by:
confidence: high
---

### CORE-FR-008 相対選択：上位ティアへの相談・上申

- **説明**: 高難度の設計・トレードオフ分析・原因不明の不具合調査は、司令塔より**上位ティア**が
  存在する時のみ相談・上申する。司令塔が最上位なら相談相手はいないため、司令塔自身が判断する。
  下位への委譲（CORE-FR-007）と上位への相談・上申を対称に機構化する。
- **受入基準 (EARS)**:
  - WHEN タスクが高難度の設計・トレードオフ分析・原因不明の不具合調査で、かつ司令塔より上位ティアがレジストリに存在する THEN 上位ティアへ相談・上申すること SHALL
  - IF 司令塔より上位ティアが存在しない（司令塔が最上位）THEN 相談先なしとして司令塔自身が判断すること SHALL
- **検証手段**: delegation-routing の inspection。上位ティア存在時の相談・上申経路と、
  最上位時の自己判断フォールバックが記述されていることを確認する。
- **Revision History**:
  - 1.0 (2026-07-13) 初版（draft 起票）
