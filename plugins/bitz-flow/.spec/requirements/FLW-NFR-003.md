---
id: FLW-NFR-003
version: 1.0
status: draft
domain: execution
priority: high
origin: FLW-DSN-013
verification_method: unit-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### FLW-NFR-003 障害復旧と重複副作用防止

- **説明**: write応答喪失、timeout、部分完了、並行実行から外部状態を破壊せず収束する。
- **受入基準 (EARS)**:
  - WHEN write operationを登録する THEN bitz-flowは1件以上の安定Recovery ID、postcondition、retry方針をoperation schemaへ要求すること SHALL
  - WHEN write応答を喪失する THEN bitz-flowはRecovery Matrixの外部証跡を照会して`DONE`、`PARTIAL`、`INDETERMINATE`、`STALE`、`BLOCKED`のいずれかを返すこと SHALL
  - WHEN 副作用の成否を一意に判定できない THEN bitz-flowは同じtargetへの後続mutationを停止すること SHALL
  - WHEN GitHub createまたはcommentを再実行する THEN bitz-flowはidempotency markerを全page照会して重複副作用を防止すること SHALL
  - WHEN 同一concurrency keyのwriteを同一hostで実行する THEN bitz-flowはOS advisory lockで直列化すること SHALL
  - WHEN cross-host createの直列化を証明できない THEN bitz-flowはsingle coordinator前提をplanへ表示するかoperationを`UNSUPPORTED`にすること SHALL
  - WHEN Recovery Matrixのfault fixtureを実行する THEN bitz-flowは重複副作用0件、誤補償0件、INDETERMINATE後のmutation継続0件を記録すること SHALL
- **検証手段**: 全writeの副作用直前、直後、post-check中へfault injectionするunit testで検証する。
- **Revision History**:
  - 1.0 (2026-07-29) FLW-DSN-012/013とFLW-REV-002の残余リスクからdraft起票
