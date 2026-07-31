---
id: FLW-CON-006
version: 1.2
status: approved
domain: governance
priority: high
origin: 2026-07-29 ユーザー指示（draft要件をFLW-NFR-003から順番に解決）
verification_method: unit-test
derived_from:
supersedes:
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
  - WHEN remote branch削除の応答を喪失してexpected SHAのrefが残存する THEN bitz-flowは旧planで再削除せず`BLOCKED`を返し、新snapshotによるplanと明示的人間承認を要求すること SHALL
  - WHEN command policyを検査する THEN bitz-flowは`git reset --hard`、force push、`git clean -f`、`rm -rf`、`sudo`の実装、提案、next actionを各0件にすること SHALL
  - WHEN 破壊操作のnegative fixtureを実行する THEN bitz-flowは証跡不一致時の削除0件、plan外targetの変更0件、禁止commandの出力0件を記録すること SHALL
- **検証手段**: MERGED証跡、head/default到達性、worktree/ref対応、target境界、remote SHA競合、自動連結、禁止commandをunit testで検証する。
- **後継候補**: FLW-FR-001のうち破壊操作とcleanupの安全境界を継承する候補である。
  FLW-FR-004/006/007と合わせた複合後継であり、Promotion Gate後のdeprecated裁定まで
  `supersedes`を発効しない。
- **Revision History**:
  - 1.2 (2026-07-29) remote削除応答喪失時のexpected SHA残存を再plan・再承認へ固定
  - 1.1 (2026-07-29) 複合後継の一部であることを明記し、Promotion前のsupersedesを解除
  - 1.0 (2026-07-29) FLW-CON-002とFLW-DSN-011から破壊操作とcleanup境界を分離してdraft起票
