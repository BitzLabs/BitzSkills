---
id: CORE-FR-007
version: 1.0
status: verified
domain: governance
priority: medium
origin: SI-CORE-021
verification_method: manual-check
derived_from:
supersedes:
superseded_by:
confidence: high
---

### CORE-FR-007 相対選択：下位ティアへの委託

- **説明**: 委譲先を役割に絶対固定せず、司令塔（ユーザが起動したモデル）の階層内**相対位置**で選ぶ。
  機械的・量産タスクは、司令塔より下位ティアの委譲先が存在する時のみ委譲し、無ければ司令塔が自己実行する。
  役割の束縛モデルが司令塔と同一ティアの経路は、省トークンにならないため無効化する。
- **受入基準 (EARS)**:
  - WHEN タスクが機械的修正または量産で、かつ司令塔より下位ティアの委譲先がレジストリに存在する THEN その委譲先へ委譲すること SHALL
  - IF 司令塔より下位ティアの委譲先が存在しない（司令塔が最下位、または該当役割が同一ティアのみ）THEN 委譲せず司令塔自身が実行すること SHALL
  - IF ある役割の束縛モデルが司令塔モデルと同一ティア THEN 当該委譲経路を無効化すること SHALL
- **検証手段**: delegation-routing の inspection。司令塔ティア別（最上位/中位/最下位）に
  委譲可否と自己実行フォールバック、同一ティア無効化が記述されていることを確認する。
- **Revision History**:
  - 1.0 (2026-07-13) 初版（draft 起票）
