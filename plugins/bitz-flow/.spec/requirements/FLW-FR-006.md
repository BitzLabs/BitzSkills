---
id: FLW-FR-006
version: 1.0
status: draft
domain: workflow
priority: high
origin: SI-FLW-004
verification_method: unit-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### FLW-FR-006 worktree-firstライフサイクル

- **説明**: 書込み作業をWorkUnit単位のworktreeへ分離し、作成、再開、完了、失敗保全、discardを状態機械化する。
- **受入基準 (EARS)**:
  - WHEN 新しい書込みWorkUnitを開始する THEN bitz-flowは1 WorkUnit、1 worktree、1 branchの対応をplanすること SHALL
  - WHEN worktree pathを計画する THEN bitz-flowはrepo slug、repo identity短縮値、work IDを含む衝突しないpathを返すこと SHALL
  - WHEN repo外worktreeのcreateを要求する THEN bitz-flowはcanonical pathとeffectsを提示して明示的人間承認を要求すること SHALL
  - WHEN 既存worktreeをresumeする THEN bitz-flowはpath、branch、HEAD、Git common dirがplanと一致した場合だけ同じWorkUnitとして再開すること SHALL
  - WHEN branch-onlyのv1対象を監査する THEN bitz-flowはworktreeが存在しないlegacy WorkUnitとして分類すること SHALL
  - WHEN merged WorkUnitをfinishする THEN bitz-flowはmerge証跡監査後にworktree除去とlocal branch処理を段階別に実行すること SHALL
  - WHEN WorkUnitが失敗状態になる THEN bitz-flowはworktreeと未コミット変更を保持して`failed-retained`を返すこと SHALL
  - WHEN failed-retained WorkUnitをdiscardする THEN bitz-flowは固定manifestの全targetと明示的人間承認が一致した場合だけ列挙targetを除去すること SHALL
- **検証手段**: path衝突、repo identity、resume不一致、branch-only、finish部分失敗、dirty保全、manifest外target不変をunit testで検証する。
- **Revision History**:
  - 1.0 (2026-07-29) accepted SI-FLW-004とFLW-DSN-006/012からdraft起票
