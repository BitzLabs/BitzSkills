---
id: FLW-NFR-003
version: 1.1
status: approved
domain: execution
priority: high
origin: .spec/reports/decision-2026-07-29-bitz-flow-v2-design-gate.md
verification_method: unit-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### FLW-NFR-003 Forward Recoveryの安全な収束

- **説明**: write応答喪失、timeout、部分完了時に、確認済みの外部状態を破壊せず前進再開へ収束する。
- **受入基準 (EARS)**:
  - WHEN write operationを登録する THEN bitz-flowは1件の安定Recovery ID、外部状態で判定可能なpostcondition、retry方針をoperation schemaへ要求すること SHALL
  - WHEN write応答を喪失する、timeoutする、またはpost-checkに失敗する THEN bitz-flowはRecovery Matrixが指定する外部証跡を照会して`DONE`、`PARTIAL`、`INDETERMINATE`、`STALE`、`BLOCKED`のいずれかを返すこと SHALL
  - WHEN recovery結果が`PARTIAL`である THEN bitz-flowは確認済みの`completed_steps`と未完了の`remaining_steps`を返し、確認済み副作用を再実行しないこと SHALL
  - WHEN recovery結果が`INDETERMINATE`である THEN bitz-flowはread-only reconcileだけを許可し、同じcanonical targetへの後続mutationを停止すること SHALL
  - WHEN 部分完了した副作用を外部証跡で確認する THEN bitz-flowは当該副作用を自動削除、自動上書き、または補償操作で巻き戻さないこと SHALL
  - WHEN Recovery Matrixのfault fixtureを実行する THEN bitz-flowはwrite operationのRecovery ID対応率100%、誤補償0件、`INDETERMINATE`後のmutation継続0件を記録すること SHALL
- **検証手段**: 全writeの副作用直前、直後、post-check中へfault injectionし、終了状態、完了段階、後続mutation、補償操作をunit testで検証する。
- **Revision History**:
  - 1.0 (2026-07-29) FLW-DSN-012/013とFLW-REV-002の残余リスクからdraft起票
  - 1.1 (2026-07-29) draftレビューで冪等性、同一host排他、cross-host制約をFLW-NFR-005/006、FLW-CON-004へ分離
