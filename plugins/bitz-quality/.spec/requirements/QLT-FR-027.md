---
id: QLT-FR-027
version: 1.0
status: approved
domain: quality-review
priority: high
origin: SI-QLT-002
verification_method: example-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### QLT-FR-027 SDD V4レビューprofile契約

- **説明**: bitz-sdd V4のレビュー品質基準をquality providerが再現可能なprofileとして提供する。
- **受入基準 (EARS)**:
  - WHEN `bitz-sdd-v4@1` profileを解決する THEN systemはconsistency・data-integrity・operations・risk・businessに加えSystem Engineering Reviewとmeasurabilityを必須観点として含めること SHALL
  - WHEN V4 profileを評価する THEN systemはaggregate 4.50以上、各観点4.00以上、critical/major 0件、未追跡P0/P1 0件をGate条件として記録すること SHALL
  - IF V4 Charterまたは公開portが未確定である THEN systemはprofileを`contract pending`として扱い、V4互換PASSを発行しないこと SHALL
  - WHEN profileの判定を生成する THEN systemはprofile digest・threshold・観点一覧・測定母数を結果へ保存すること SHALL
- **検証手段**: V4 profileの正常・閾値未達・観点欠落・Charter pending fixtureとboundary testで検証する。
- **Revision History**:
  - 1.0 (2026-08-14) 初版（draft 起票）
