---
id: QLT-FR-023
version: 1.0
status: draft
domain: quality-review
priority: medium
origin: SI-QLT-001 / QLT-DSC-002 / QLT-DSC-007 H-Q2
verification_method: example-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### QLT-FR-023 レビュー成果物の決定的validator

- **説明**: LLM生成物をGateへ渡す前に決定的validatorで契約検査する。
- **受入基準 (EARS)**:
  - WHEN artifactを検査する THEN validatorはschema・統制語彙・参照ID・target・digest・重複・Gate不変条件を決定的に検査すること SHALL
  - WHEN compact/JSON形式で結果を返す THEN両形式の判定codeと件数を一致させること SHALL
  - IF artifactが大きい THEN省略を可視化し、判定に必要な総数を保持すること SHALL
- **検証手段**: golden/invalid corpusとcompact/JSON parity testで検証する。
- **Revision History**:
  - 1.0 (2026-08-14) 初版（draft 起票）
