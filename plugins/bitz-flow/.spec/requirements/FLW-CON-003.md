---
id: FLW-CON-003
version: 1.0
status: approved
domain: governance
priority: high
origin: .spec/reports/decision-2026-07-29-bitz-flow-v2-design-gate.md
verification_method: unit-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### FLW-CON-003 SDDとGitHubの責務分離

- **説明**: `.spec`を仕様・裁定のSSOT、GitHubを協調・実行状態のSSOTとして維持する。
- **受入基準 (EARS)**:
  - WHEN bitz-flowがspec-issue、requirement、taskを参照する THEN bitz-flowは`.spec`の本文とstatusを変更しないこと SHALL
  - WHEN GitHub Issueがrequirementを参照する THEN bitz-flowはrequirement本文をIssueへ複製せずIDとURLだけを記録すること SHALL
  - WHEN taskをGitHubへ同期する THEN bitz-flowはtask statusを人間専用statusの変更命令として解釈しないこと SHALL
  - WHEN GitHub Project fieldを更新する THEN bitz-flowは当該fieldを`.spec` statusのSSOTとして扱わないこと SHALL
  - WHEN IssueLinkの不整合を検出する THEN bitz-flowはread-only reconcile planを返してSDD側の更新を呼出側へ委ねること SHALL
  - WHEN `.spec` status変更をGitHubから要求する THEN bitz-flowは副作用ゼロで`UNSUPPORTED`を返すこと SHALL
- **検証手段**: Issue publish、task link、Project update、reconcile-link、status変更要求のfixtureで`.spec`差分0件をunit test検証する。
- **Revision History**:
  - 1.0 (2026-07-29) FLW-DSN-002/007のSSOT境界からdraft起票
