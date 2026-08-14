---
id: QLT-FR-030
version: 1.0
status: draft
domain: quality-review
priority: high
origin: SI-QLT-002
verification_method: example-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### QLT-FR-030 qualification・移行・rollback契約

- **説明**: platform qualificationとsdd-review移行を再現可能にし、後戻り可能な状態で運用する。
- **受入基準 (EARS)**:
  - WHEN adapterをqualificationする THEN各platform・compatibility keyにつき同一fixtureの独立3 trial、green/red/stale/unknown fault matrix、100% required field/parityを満たすこと SHALL
  - IF platform・model・agent schema・tool/profile/schema versionが変化する THEN qualificationは失効し再認定を要求すること SHALL
  - WHEN移行stageを進める THEN systemはdual-readまたはlossless export、golden corpus、rollback rehearsal、復旧bundleと観測期間を記録すること SHALL
  - WHEN `sdd-review`のdeprecation/removalを裁定する THEN bitz-sdd workspaceのDesign/Promotion Gateとbitz-qualityのGateを別々に通過すること SHALL
  - IF rollbackがpoint-of-no-return後である THEN systemはdowngradeを保証せずforward-fixと復旧bundleを明示すること SHALL
- **検証手段**: qualification trial/expiry、migration parity、rollback rehearsal、cross-workspace Gate dependency fixtureで検証する。
- **Revision History**:
  - 1.0 (2026-08-14) 初版（draft 起票）
