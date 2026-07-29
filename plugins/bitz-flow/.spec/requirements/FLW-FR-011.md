---
id: FLW-FR-011
version: 1.0
status: draft
domain: tooling
priority: medium
origin: .spec/reports/decision-2026-07-29-bitz-flow-v2-design-gate.md
verification_method: unit-test
derived_from:
supersedes: FLW-FR-002
superseded_by:
confidence: high
---

### FLW-FR-011 flow-doctor v2環境診断

- **説明**: v2 operationの実行前提と縮退理由を、対象projectへ書き込まず共通result契約で診断する。
- **受入基準 (EARS)**:
  - WHEN flow-doctorを実行する THEN flow-doctorはPython、Git、gh、repository、remote、default branch、認証hostを読み取り専用で診断すること SHALL
  - WHEN operation別capabilityを診断する THEN flow-doctorは必要version、scope、filesystem、locking、process tree収束の成否を返すこと SHALL
  - WHEN 前提が不足する THEN flow-doctorは不足stage、許可語彙cause、導入または設定のnext actionを返すこと SHALL
  - WHEN 診断対象がGitHubを使用しない THEN flow-doctorはgh欠如をwarningとして返すこと SHALL
  - WHEN flow-doctor resultを生成する THEN flow-doctorはflow-coreと同じ共通envelope schemaを満たすこと SHALL
  - WHEN flow-doctorを実行する THEN flow-doctorは対象project、Git ref、GitHub状態を変更しないこと SHALL
- **検証手段**: 依存欠如、未認証、remote欠如、unsupported filesystem、schema golden一致、副作用ゼロをunit testで検証する。
- **Revision History**:
  - 1.0 (2026-07-29) FLW-FR-002のv2後継としてdraft起票
