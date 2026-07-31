---
id: FLW-NFR-005
version: 1.0
status: approved
domain: execution
priority: high
origin: 2026-07-29 ユーザー指示（draft要件をFLW-NFR-003から順番に解決）
verification_method: unit-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### FLW-NFR-005 GitHub writeの冪等性と重複副作用防止

- **説明**: GitHubのcreate/comment応答を喪失して再実行しても、同じ論理操作の副作用を重複生成しない。
- **受入基準 (EARS)**:
  - WHEN 重複し得るGitHub createまたはcomment operationを登録する THEN bitz-flowは安定`idempotency_id`と本文末尾へ1つだけ配置する固定markerを要求すること SHALL
  - WHEN GitHub createまたはcommentを再実行する THEN bitz-flowはmutation前に同じmarkerを全page照会すること SHALL
  - WHEN 排他前提が成立しmarker照会結果が0件、1件、または複数件である THEN bitz-flowはそれぞれ新規実行、既存URLまたはIDを復元した`DONE`、副作用を伴わない`BLOCKED`を返すこと SHALL
  - WHEN pagination、権限、または一時障害によりmarkerを全件照会できない THEN bitz-flowは`INDETERMINATE`を返してcreateまたはcommentを実行しないこと SHALL
  - WHEN createまたはcomment直後のmarker再照会で複数件を検出する THEN bitz-flowは`BLOCKED`を返し、重複対象を自動close、delete、またはeditしないこと SHALL
  - WHEN 応答喪失と再実行のfault fixtureを実行する THEN bitz-flowは同じ`idempotency_id`による重複副作用0件とblind retry 0件を記録すること SHALL
- **検証手段**: marker 0件・1件・複数件、pagination不完備、応答喪失、post-create競合を模擬し、外部write呼出回数と終了状態をunit testで検証する。
- **Revision History**:
  - 1.0 (2026-07-29) FLW-NFR-003からGitHub create/commentの冪等性を分離してdraft起票
