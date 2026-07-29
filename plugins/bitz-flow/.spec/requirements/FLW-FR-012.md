---
id: FLW-FR-012
version: 1.0
status: draft
domain: governance
priority: high
origin: FLW-DSN-011
verification_method: unit-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### FLW-FR-012 v1からv2への段階移行

- **説明**: v1を稼働契約として維持したままv2をM0〜M5で検証し、Promotion Gate後にだけ正を切り替える。
- **受入基準 (EARS)**:
  - WHEN v2 Promotion Gateが未完了である THEN bitz-flowはFLW-FR-001/002とFLW-DSN-001をcurrent契約として扱うこと SHALL
  - WHEN v2 prereleaseを検証する THEN bitz-flowはM0からM5の各出口条件と即時停止条件をmilestone順に適用すること SHALL
  - WHEN migration診断を実行する THEN bitz-flowは旧skill名、旧script名、bitz-sdd委譲先、plugin version、result schemaの参照を列挙すること SHALL
  - WHEN v2 canaryが停止条件に達する THEN bitz-flowは後続promotionを停止して直前v1のpin手順を返すこと SHALL
  - WHEN rollbackを実行する THEN bitz-flowはv2が作成したIssue、PR、release、worktreeを自動削除しないこと SHALL
  - WHEN v2 Promotion Gateを提出する THEN bitz-flowは3platformのv1からv2からv1への往復canaryと旧参照ゼロの証跡を要求すること SHALL
  - WHEN v2 Promotion Gateが承認される THEN bitz-flowは旧要件のdeprecated裁定と旧入口撤去を別段階で実行すること SHALL
- **検証手段**: version/schema誤起動、旧参照検出、milestone停止、v1 pin、往復canary、外部成果物保全をunit testとmigration fixtureで検証する。
- **Revision History**:
  - 1.0 (2026-07-29) Design Gate承認済みFLW-DSN-011からdraft起票
