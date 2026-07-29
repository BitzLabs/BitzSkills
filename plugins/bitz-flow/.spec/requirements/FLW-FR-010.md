---
id: FLW-FR-010
version: 1.0
status: draft
domain: workflow
priority: high
origin: .spec/reports/decision-2026-07-29-bitz-flow-v2-design-gate.md
verification_method: unit-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### FLW-FR-010 CHANGELOGとReleaseライフサイクル

- **説明**: 同じcanonical change setからCHANGELOG、release notes、tag、GitHub Releaseを段階生成する。
- **受入基準 (EARS)**:
  - WHEN release planを作成する THEN bitz-flowはversion、component、target SHA、前回tag、canonical change setを固定すること SHALL
  - WHEN canonical change setを導出する THEN bitz-flowはtargetへ到達可能なmerge commitと一意に対応するmerged PRだけを採用すること SHALL
  - WHEN CHANGELOGを生成する THEN bitz-flowはrelease labelとbreaking情報で分類したpreview digestを返すこと SHALL
  - WHEN CHANGELOGをapplyする THEN bitz-flowは同一directory tempの検証後にatomic replaceし、最終digestを照合すること SHALL
  - WHEN tagを処理する THEN bitz-flowはlocal annotated tag作成とremote tag pushを別operationで実行すること SHALL
  - WHEN release draftを作成する THEN bitz-flowはexpected tag、target、notes digest、idempotency markerを記録すること SHALL
  - WHEN release publishをapplyする THEN bitz-flowは明示的人間承認とdraft、tag、target、notes一致を再確認すること SHALL
  - WHEN project固有のversion bump、build、署名が必要である THEN bitz-flowは外部証跡を要求し任意commandを実行しないこと SHALL
- **検証手段**: pagination、PR重複、atomicity、tag応答喪失、draft重複、target不一致、publish承認をunit testで検証する。
- **Revision History**:
  - 1.0 (2026-07-29) Design Gate承認済みFLW-DSN-009/013からdraft起票
