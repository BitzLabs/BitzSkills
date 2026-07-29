---
id: FLW-CON-006
version: 1.0
status: draft
domain: governance
priority: high
origin: FLW-DSN-011
verification_method: unit-test
derived_from:
supersedes: FLW-FR-001
superseded_by:
confidence: high
---

### FLW-CON-006 破壊操作とcleanupの安全境界

- **説明**: v1の後片付け不変条件を継承し、破壊操作を証跡一致時の明示的な単一operationへ限定する。
- **受入基準 (EARS)**:
  - WHEN merge後cleanupをplanまたはapplyする THEN bitz-flowはPR state、head branch、head SHA、merge commitのdefault到達性、worktreeとrefの対応を再照会すること SHALL
  - WHEN cleanup証跡が欠落、不一致、または一意でない THEN bitz-flowはworktree、local branch、remote branchを変更せず`BLOCKED`を返すこと SHALL
  - WHEN cleanup targetがdefault branch、管理manifest外、別worktree使用中、またはplan後に進行したrefである THEN bitz-flowは対象を変更せず`BLOCKED`を返すこと SHALL
  - WHEN remote branch削除を計画する THEN bitz-flowは独立した`git.delete-remote-branch` operationとして扱い、merge、local cleanup、releaseへ自動連結しないこと SHALL
  - WHEN remote branch削除をapplyする THEN bitz-flowは削除直前にremote refとexpected SHAを再照会し、一致しない場合は削除しないこと SHALL
  - WHEN command policyを検査する THEN bitz-flowは`git reset --hard`、force push、`git clean -f`、`rm -rf`、`sudo`の実装、提案、next actionを各0件にすること SHALL
  - WHEN 破壊操作のnegative fixtureを実行する THEN bitz-flowは証跡不一致時の削除0件、plan外targetの変更0件、禁止commandの出力0件を記録すること SHALL
- **検証手段**: MERGED証跡、head/default到達性、worktree/ref対応、target境界、remote SHA競合、自動連結、禁止commandをunit testで検証する。
- **Revision History**:
  - 1.0 (2026-07-29) FLW-CON-002とFLW-DSN-011から破壊操作とcleanup境界を分離してdraft起票
