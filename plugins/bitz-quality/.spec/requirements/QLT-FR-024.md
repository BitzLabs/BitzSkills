---
id: QLT-FR-024
version: 1.0
status: approved
domain: quality-review
priority: medium
origin: SI-QLT-001 / QLT-DSC-007 H-Q1
verification_method: example-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### QLT-FR-024 3platform adapter qualification

- **説明**: 3platform adapterの適格性を同一protocolで測定する。
- **受入基準 (EARS)**:
  - WHEN adapter qualificationを実行する THEN platform×profileごとに正常・既知拒否・観測破損を独立trialで測ること SHALL
  - IF 必須field保持またはverdict parityが100%未満 THEN当該adapterを既定利用可能にしないこと SHALL
  - WHEN evidenceを再利用する THEN platform/model/tool/schemaのcompatibility key一致を必須にすること SHALL
- **検証手段**: Claude/Codex/Antigravity fixtureとfault injection manifestで検証する。
- **Revision History**:
  - 1.0 (2026-08-14) 初版（draft 起票）
