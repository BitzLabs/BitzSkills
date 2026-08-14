---
id: QLT-FR-020
version: 1.0
status: draft
domain: quality-review
priority: medium
origin: SI-QLT-001 / QLT-DSC-004
verification_method: example-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### QLT-FR-020 個別レビュー結果schemaの固定

- **説明**: 各Reviewerの結果を統合前に独立検証できるversion付きschemaへ固定する。
- **受入基準 (EARS)**:
  - WHEN Reviewerが完了する THEN resultはreviewer/perspective ID・status・score・findings・evidence・duration・target digestを含むこと SHALL
  - WHEN resultを保存する THEN resultはreview ID・attempt世代・started/completed時刻を持つimmutable evidenceとして追記し、既存attemptを上書きしないこと SHALL
  - IF 終了済みまたは取消済みattemptの結果が遅延到着する THEN systemは証跡として隔離してもactive result集合へ戻さないこと SHALL
  - IF 出力がschema不正またはtarget不一致 THEN resultはINVALIDまたはSTALEとして統合の成功母集団から除外すること SHALL
  - WHEN findingを出力する THEN source locationと根拠を持ち、推測はassumptionとして可視化すること SHALL
- **検証手段**: 正常、schema欠落、target不一致、assumption可視化fixtureを検査する。
- **Revision History**:
  - 1.0 (2026-08-14) 初版（draft 起票）
  - 1.0 (2026-08-14) QLT-REV-002 GP-002を反映
