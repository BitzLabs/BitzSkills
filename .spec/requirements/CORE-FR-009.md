---
id: CORE-FR-009
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

### CORE-FR-009 プラットフォーム別委譲レジストリ（役割→委譲先→ティアの SSOT）

- **説明**: 役割→委譲先→ティア順序の束縛を宣言する**委譲レジストリ**を委譲判断の唯一の正（SSOT）とする。
  Claude と Antigravity はモデル体系が全く異なるため、レジストリを**分離**して保持し、一方の更新が
  他方に干渉しないようにする。委譲ルーティング文書は具体モデル名を直書きせず役割を介して参照し、
  モデル世代交代時の追随を局所編集に収める。
- **受入基準 (EARS)**:
  - THE 委譲レジストリは役割・委譲先・ティア順序の束縛を宣言し、委譲判断の唯一の正（SSOT）であること SHALL
  - THE Claude 用レジストリと Antigravity 用レジストリは分離され、一方の更新が他方に影響しないこと SHALL
  - WHEN 委譲ルーティング文書がモデルを参照する THEN 具体モデル名を直書きせず役割を介して参照すること SHALL
- **検証手段**: レジストリ構造と対象文書の inspection。役割/委譲先/ティアの宣言、
  Claude・Antigravity の分離、ルーティング文書のモデル名非直書きを確認する（機械検証は CORE-NFR-001）。
- **Revision History**:
  - 1.0 (2026-07-13) 初版（draft 起票）
