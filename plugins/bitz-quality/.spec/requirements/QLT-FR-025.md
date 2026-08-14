---
id: QLT-FR-025
version: 1.0
status: draft
domain: quality-review
priority: medium
origin: SI-QLT-001 / QLT-DSC-007 H-Q5
verification_method: example-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### QLT-FR-025 sdd-review読取互換と段階移管canary

- **説明**: 現行sdd-review成果物を保全し、段階的に所有権を移管する。
- **受入基準 (EARS)**:
  - WHEN legacy reviewを読む THEN adapterは既存field・P0/P1・verdict・Gate前提の意味を失わず正規化すること SHALL
  - WHEN shadow canaryを行う THEN sdd-reviewとquality-reviewの必須field保持100%、P0/P1消失0、verdict差0を要求すること SHALL
  - IF parity未達 THEN sdd-reviewをdeprecatedにせずquality adapterを既定化しないこと SHALL
  - WHEN移管する THEN加法導入、consumer切替、旧入口deprecated、削除の各Gateを分離すること SHALL
- **検証手段**: 既存review corpusのgolden testとV1→Quality→V1往復canaryで検証する。
- **Revision History**:
  - 1.0 (2026-08-14) 初版（draft 起票）
