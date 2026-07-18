---
id: SI-FLW-004
raised_by: PR #61/#66/#67のguarded cleanup実運用（2026-07-18）
target: worktreeを伴わないsquash merged branch専用cleanup
proposed_change_type: modify
status: open
---
- **目的**: 現行のsquash cleanupはworktree用のpositional `work-id`を必須とする。PR #61/#66/#67の
  branchは通常checkoutで管理されており、mainへ切替後に実在しない `pr-61` / `pr-66` /
  `si-flw-001` を渡して `cleanup-partial` として処理した。証跡検証は成立したが、存在しないworktreeを
  「除去済み」と解釈するCLIは監査上わかりにくい。worktreeを伴わないbranch専用の状態と入口を追加する。
- **提案する修正**:
  1. `cleanup-branch --branch <name> --squash-pr <number>` を追加し、work-idを要求しない
  2. PR MERGED/head名/head SHA、存在するlocal/remote ref、merge commit到達性、default branch cleanを
     既存guarded cleanupと共通関数で検証する
  3. `branch-only` / `local-cleaned` / `indeterminate` を明示し、worktree path検証を対象外として記録する
  4. local branch削除後もremoteは期待SHA・検査時刻・直前再照会警告を持つ候補報告だけにする
- **対象ファイル**: `plugins/bitz-flow/skills/flow-worktree/scripts/worktree_ops.py`、
  `plugins/bitz-flow/skills/flow-worktree/SKILL.md`、`tests/test_worktree_ops.py`、FLW-FR-001系列、
  bitz-flowの3マニフェスト。
- **確認観点**: 架空work-idが不要になること。worktree cleanup/discardの既存CLI互換性を維持すること。
  local SHA進行、remote SHA進行、branch使用中、dirty main、未マージPRでは削除副作用ゼロで停止すること。
- **影響推定・ロールバック**: FLW-FR-001依存成果物はルート1件・bitz-flow 4件。公開CLI追加と
  cleanup状態機械の共通化を伴うため通常SDDフロー + Design Gateを推奨。新サブコマンドをrevertしても
  現行worktree cleanupは残る。
- **依存**: SI-FLW-003の監査分類を先に確立し、`merged-exact`候補を入力判断に使う。

## 予備判定（推薦）— 裁定は人間専用

| 判定軸 | 確認結果 |
|---|---|
| 既存要件との矛盾 | なし。worktree経路を維持した加法的な入口 |
| ガードレール抵触 | なし。remote自動削除は追加しない |
| 影響範囲 | worktree_opsのcleanup入口・状態分類・テスト |
| 軽量レーン適否 | 不適。削除操作を含む公開CLIの追加 |

**推薦: accept**。安全性は維持されたものの、架空IDを必要とする運用は再現性と監査性を損なうため。
