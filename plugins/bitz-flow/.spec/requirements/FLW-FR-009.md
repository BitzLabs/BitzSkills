---
id: FLW-FR-009
version: 1.0
status: approved
domain: workflow
priority: high
origin: SI-FLW-005
verification_method: unit-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### FLW-FR-009 段階的PRライフサイクル

- **説明**: PRをprepare、publish、checks、ready、merge-plan、merge、post-mergeへ分け、外部状態から再開する。
- **受入基準 (EARS)**:
  - WHEN `pr.prepare`を実行する THEN bitz-flowはbranch preflight、PR本文digest、base、head SHAを副作用なしで返すこと SHALL
  - WHEN `pr.publish`をapplyする THEN bitz-flowはexpected remote SHAを確認してDraft PRを1件だけ作成すること SHALL
  - WHEN PR作成応答を喪失する THEN bitz-flowはmarkerとhead SHAが一致するopen PRを照会してDONE、再開、BLOCKEDのいずれかを返すこと SHALL
  - WHEN `pr.checks`を実行する THEN bitz-flowはCI、review、base、head、draft状態を許可リストresultで返すこと SHALL
  - WHEN `pr.ready`をapplyする THEN bitz-flowはhead一致と公開前提を再照会してdraft=falseをpostcondition確認すること SHALL
  - WHEN `pr.merge`をapplyする THEN bitz-flowは明示的人間承認、expected head、CI、review、base条件を再確認してsquash mergeすること SHALL
  - WHEN merge後監査を実行する THEN bitz-flowはMERGED、merge commit、mergedAt、default到達性を確認してWorkUnit状態を更新すること SHALL
  - WHEN PR処理が完了する THEN bitz-flowはremote branch削除を自動連結しないこと SHALL
- **検証手段**: Draft再開、重複PR、CI pending/failed、head進行、review不足、merge応答喪失、post-merge監査をunit testで検証する。
- **Revision History**:
  - 1.0 (2026-07-29) accepted SI-FLW-005とFLW-DSN-008/013からdraft起票
