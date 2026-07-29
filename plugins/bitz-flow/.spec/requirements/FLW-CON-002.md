---
id: FLW-CON-002
version: 1.1
status: draft
domain: governance
priority: high
origin: .spec/reports/decision-2026-07-29-bitz-flow-v2-design-gate.md
verification_method: unit-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### FLW-CON-002 Operation Contractと副作用上限

- **説明**: 全公開operationを同一schemaで宣言し、planが列挙した副作用をapplyの上限として固定する。
- **受入基準 (EARS)**:
  - WHEN operationを登録する THEN bitz-flowはoperation、class、target、preconditions、effects、approval、postconditions、retry、evidenceをOperation Contractへ要求すること SHALL
  - WHEN write operationを登録する THEN bitz-flowはconcurrency key、partial、安定Recovery IDをOperation Contractへ追加要求すること SHALL
  - WHEN operationをplanする THEN bitz-flowは外部状態を変更せずcanonical target、snapshot、preconditions、effectsから安定operation IDを生成すること SHALL
  - WHEN operationをapplyする THEN bitz-flowはpreconditionsを再照会してoperation IDを再計算し、plan時と一致する場合だけ列挙済みeffectsを実行すること SHALL
  - WHEN operationがplanにない副作用を要求する THEN bitz-flowはapplyを`BLOCKED`にすること SHALL
  - WHEN catalogに登録されていないoperationまたはactionを要求する THEN bitz-flowは副作用ゼロで`UNSUPPORTED`を返すこと SHALL
  - WHEN Operation Contractの全catalog fixtureを検査する THEN bitz-flowは必須field欠落0件、plan時mutation 0件、effects上限逸脱0件を記録すること SHALL
- **検証手段**: schema欠落、plan副作用、snapshot変化、operation ID不一致、effects逸脱、未登録actionをunit testで検証する。
- **Revision History**:
  - 1.0 (2026-07-29) FLW-FR-001のv2後継安全境界としてdraft起票
  - 1.1 (2026-07-29) draftレビューで明示承認をFLW-CON-005、破壊操作とcleanupをFLW-CON-006へ分離し、出力安全はFLW-NFR-002へ一本化
