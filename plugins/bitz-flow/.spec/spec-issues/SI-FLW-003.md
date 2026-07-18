---
id: SI-FLW-003
raised_by: PR #61/#66/#67の不要ブランチ棚卸し（2026-07-18）
target: local/remoteブランチのマージ証跡付き監査コマンド
proposed_change_type: new
status: open
---
- **目的**: PR #67 マージ後の不要ブランチ整理では、local/remote一覧、open PR、merged PRの
  head SHA、worktree占有、remote ref実在を複数コマンドで手動照合した。PR #61/#66も同条件の
  stale branch と判明したが、単に「open PRがない」「mainへ反映済み」だけでは、squash後に進行した
  branchや別worktree使用中のbranchを誤削除し得る。状態変更なしで削除候補と保全対象を分類する。
- **提案する修正**:
  1. `worktree_ops.py audit-branches` または専用 `branch_audit.py` を追加し、default branchとsymrefを除く
     local/remote refを列挙する
  2. open PR、merged PRの最終head SHA、local/remote SHA、worktree占有、merge commit到達性を照合する
  3. `active` / `merged-exact` / `remote-advanced` / `worktree-in-use` / `orphan` /
     `indeterminate` へ分類し、根拠とPR番号を許可リストJSONで返す
  4. auditはブランチ削除、push、worktree除去、PR更新を一切実行しない
- **対象ファイル**: `plugins/bitz-flow/skills/flow-worktree/scripts/worktree_ops.py` または同skill配下の
  新規監査スクリプト、`flow-worktree/SKILL.md`、`tests/test_worktree_ops.py`または新規監査テスト、
  FLW-FR-001系列、bitz-flowの3マニフェスト。
- **確認観点**: 同名branchの複数PR、open+merged混在、remoteのみ、localのみ、PR head後の進行、
  worktree占有、gh失敗、timeoutを検証する。秘密情報とrawコマンド出力を含めない。remote deleteは
  非目標とし、期待SHA付き候補報告までに留める。
- **影響推定・ロールバック**: `--impact FLW-FR-001` はルート1件、bitz-flow 4件。新規の読み取り専用
  CLIで既存cleanupを変更しないため後方互換だが、分類JSONを公開契約とするため通常SDDフローを推奨。
  新規コマンドと文書参照をrevertすれば現行へ戻る。
- **依存**: FLW-FR-001。SI-FLW-002とは独立実装可能だが、失敗診断語彙は揃える。

## 予備判定（推薦）— 裁定は人間専用

| 判定軸 | 確認結果 |
|---|---|
| 既存要件との矛盾 | なし。現行guarded cleanup前の読み取り専用棚卸しを追加する |
| ガードレール抵触 | なし。状態変更を行わない |
| 影響範囲 | flow-worktreeの監査CLI・テスト・文書 |
| 軽量レーン適否 | 不適。新規公開CLIとJSON分類契約を追加する |

**推薦: accept**。3ブランチで同じ照合を反復し、誤削除防止の判断が定型化可能だったため。
