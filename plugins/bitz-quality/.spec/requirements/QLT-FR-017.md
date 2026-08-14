---
id: QLT-FR-017
version: 1.0
status: approved
domain: quality-review
priority: medium
origin: SI-QLT-001 / QLT-DSC-001
verification_method: example-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### QLT-FR-017 論理Reviewerとplatform adapterの分離

- **説明**: モデル非依存の論理Reviewer契約と、Claude/Codex/Antigravity固有の起動方法をadapterとして分離する。
- **受入基準 (EARS)**:
  - WHEN reviewを計画する THEN systemは論理Reviewer ID・観点・入力契約をplatform固有設定なしで確定すること SHALL
  - WHEN platformで実行する THEN adapterは論理契約を変更せずplatform固有agent/promptへ写像すること SHALL
  - IF platformが必須能力を持たない THEN adapterは代替を推測せずUNSUPPORTEDを返すこと SHALL
- **検証手段**: 3platform adapter fixtureで同一論理Reviewer ID・必須入力・明示UNSUPPORTEDを検証する。
- **Revision History**:
  - 1.0 (2026-08-14) 初版（draft 起票）
