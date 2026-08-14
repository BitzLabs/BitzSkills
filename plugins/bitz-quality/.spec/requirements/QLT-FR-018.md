---
id: QLT-FR-018
version: 1.0
status: approved
domain: quality-review
priority: medium
origin: SI-QLT-001 / QLT-DSC-004
verification_method: example-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### QLT-FR-018 version付きreview profileとperspective registry

- **説明**: review profileとperspective registryをversion付き閉集合契約として定義する。
- **受入基準 (EARS)**:
  - WHEN profileを解決する THEN systemはschema version・必須観点・条件・重み・Gate閾値を確定すること SHALL
  - IF 未知field・重複ID・不正な重み・未定義観点がある THEN validatorはprofileを拒否すること SHALL
  - WHEN project overrideを適用する THEN base profileとoverrideの出典digestを結果へ記録すること SHALL
- **検証手段**: valid/unknown/duplicate/invalid-weight/override fixtureを検査する。
- **Revision History**:
  - 1.0 (2026-08-14) 初版（draft 起票）
