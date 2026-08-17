---
id: FLW-FR-006
version: 1.1
status: implementing
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
  - WHEN worktree writeの承認モードを決定する THEN bitz-flowは配備が意図する承認モードの宣言をrepositoryの追跡下成果物から読み、trusted key registryの存在からモードを推定しないこと SHALL
  - WHEN 承認モードの宣言が`signed-capability`でありtrusted key registryが不在、破損、権限不正、または空である THEN bitz-flowは`plan-digest`へ降格せず`BLOCKED`を返し実worktreeを作らないこと SHALL
  - WHEN 承認モードの宣言が存在しない THEN bitz-flowは`plan-digest`を素の配備として扱い降格として報告しないこと SHALL
  - WHEN 判定した承認モードが宣言より弱い、または宣言を読めない THEN bitz-flowは降格の理由を`warnings`と`data.evidence`の両方へ記録すること SHALL
- **検証手段**: path衝突、repo identity、resume不一致、branch-only、finish部分失敗、dirty保全、manifest外target不変をunit testで検証する。
- **Revision History**:
  - 1.1 (2026-08-17) 承認モードの配備意図を追跡下の宣言から読み、registry削除時の無言降格を`BLOCKED`へ倒す3値判定を追加（`SI-FLW-073`。裁定参照: .spec/reports/decision-2026-08-17-si-flw-072-073-075.md）
  - 1.0 (2026-07-29) accepted SI-FLW-004とFLW-DSN-006/012からdraft起票
