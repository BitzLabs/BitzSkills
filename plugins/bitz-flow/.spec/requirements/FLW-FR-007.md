---
id: FLW-FR-007
version: 1.0
status: approved
domain: tooling
priority: high
origin: SI-FLW-003
verification_method: unit-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### FLW-FR-007 ブランチ監査とbranch-only分類

- **説明**: local/remote branch、worktree、PR、到達性を状態変更なしで照合し、削除判断材料を返す。
- **受入基準 (EARS)**:
  - WHEN branch auditを実行する THEN bitz-flowはdefault branchとsymrefを除くlocal/remote branchを列挙すること SHALL
  - WHEN branchを分類する THEN bitz-flowはopen PR、merged PRのhead SHA、local/remote SHA、worktree占有、default到達性を照合すること SHALL
  - WHEN branch証跡が一意に成立する THEN bitz-flowは`active`、`merged-exact`、`remote-advanced`、`worktree-in-use`、`orphan`のいずれかを返すこと SHALL
  - WHEN branch証跡が不足または競合する THEN bitz-flowは`indeterminate`を返すこと SHALL
  - WHEN branch auditを実行する THEN bitz-flowはbranch削除、push、worktree除去、PR更新を行わないこと SHALL
  - WHEN merged-exact branchを報告する THEN bitz-flowはPR番号、expected SHA、検査snapshotをevidenceとして返すこと SHALL
- **検証手段**: 同名複数PR、openとmerged混在、remote-only、local-only、head進行、worktree占有、timeoutをunit testで検証する。
- **Revision History**:
  - 1.0 (2026-07-29) accepted SI-FLW-003とFLW-DSN-006/012からdraft起票
