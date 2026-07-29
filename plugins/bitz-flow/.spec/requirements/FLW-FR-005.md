---
id: FLW-FR-005
version: 1.0
status: draft
domain: execution
priority: high
origin: FLW-DSN-005
verification_method: unit-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### FLW-FR-005 Git状態変更のplan apply契約

- **説明**: fetch、stage、commit、ff-only sync、branch publish、remote branch削除を共通のplan/apply契約で実行する。
- **受入基準 (EARS)**:
  - WHEN Git write operationをapply指定なしで要求する THEN bitz-flowは副作用を実行せずtarget、preconditions、effects、postconditions、approval、operation IDを返すこと SHALL
  - WHEN apply時のoperation IDまたはsnapshotがplanと一致しない THEN bitz-flowは副作用ゼロで`STALE`を返すこと SHALL
  - WHEN `git.stage`をapplyする THEN bitz-flowは明示pathだけをindexへ追加し、expected index treeをpostconditionとして照合すること SHALL
  - WHEN `git.commit`をapplyする THEN bitz-flowはstdinで受けたmessageとexpected parent/treeを使用し、生成commitをparent、tree、message digestで照合すること SHALL
  - WHEN `git.sync`をapplyする THEN bitz-flowはfast-forward可能なexpected upstreamだけへ同期すること SHALL
  - WHEN `git.publish-branch`をapplyする THEN bitz-flowはremote refがexpected HEADと一致することを再照会すること SHALL
  - WHEN `git.delete-remote-branch`をapplyする THEN bitz-flowは独立した明示的人間承認とexpected remote SHA一致を要求すること SHALL
- **検証手段**: plan副作用ゼロ、stale拒否、path限定stage、commit照合、non-ff拒否、push応答喪失、remote進行のunit testで検証する。
- **Revision History**:
  - 1.0 (2026-07-29) Design Gate承認済みFLW-DSN-005/012/013からdraft起票
