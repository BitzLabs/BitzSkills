---
id: SI-FLW-002
raised_by: SI-FLW-001〜PR #67の実運用振り返り（2026-07-18）
target: flow-pr branch_preflight のfetch分離・鮮度検査・工程別診断
proposed_change_type: modify
status: open
---
- **目的**: `branch_preflight.py` は「読み取り専用検査」を名乗りながら内部で `git fetch origin` を
  実行し、remote-tracking ref と `.git/FETCH_HEAD` を更新する。PR #67 の作成前検査では、通常の
  `git fetch --prune origin` は成功した一方、sandbox 内の subprocess から実行した fetch が
  `.git/FETCH_HEAD` の書込み拒否で exit 255 となり、診断が `command-or-data` に集約されたため、
  GitHub障害・認証・sandbox・JSON不正のどれかを特定するには個別コマンドの再実行が必要だった。
  origin更新と非破壊判定を分離し、機密情報を出さずに失敗工程を特定できるようにする。
- **提案する修正**:
  1. fetchを行う既定経路と、呼出側が同一ワークフロー内でfetch済みの場合の検査専用経路
     （`--skip-fetch` または2段階サブコマンド）をDesign Gateで比較し、origin鮮度の前提をJSONへ記録する
  2. `fetch-failed` / `merged-pr-query` / `rev-list-failed` / `tree-diff-failed` /
     `open-pr-query` / `json-invalid` / `command-timeout` を許可リスト診断として区別する
  3. 説明を「読み取り専用」から「ブランチ・PRを変更しない非破壊検査」へ訂正する
  4. sandbox書込み拒否、ネットワーク失敗、gh未認証、不正JSON、skip-fetchの回帰テストを先行追加する
- **対象ファイル**: `plugins/bitz-flow/skills/flow-pr/scripts/branch_preflight.py`、
  `plugins/bitz-flow/skills/flow-pr/SKILL.md`、`tests/test_branch_preflight.py`、FLW-FR-001 / FLW-DSN-001
  の改訂または後継要件、bitz-flowの3マニフェスト。
- **確認観点**: raw stdout/stderr・token・環境変数値をJSONへ含めないこと。skip-fetchが古い
  `origin/<default>` を暗黙にREADY扱いしないこと。既存の終了コード0/2/3とREADY判定を維持すること。
- **影響推定・ロールバック**: `--impact FLW-FR-001` はルート1件、bitz-flow 4件を列挙した。
  公開CLIと診断契約の追加なので通常SDDフロー + Design Gateを推奨する。追加オプションと診断分類を
  一括revertすれば現行挙動へ戻せる。
- **依存**: FLW-FR-001（現行preflight契約）。

## 予備判定（推薦）— 裁定は人間専用

| 判定軸 | 確認結果 |
|---|---|
| 既存要件との矛盾 | なし。READY/INDETERMINATE/REUSE_BLOCKEDは維持し、更新と検査の境界を明確化する |
| ガードレール抵触 | なし。sandbox回避を自動化せず、必要権限を呼出側へ明示する |
| 影響範囲 | flow-prの1スクリプト・SKILL・テストとFLW-FR-001系列 |
| 軽量レーン適否 | 不適。公開CLIと診断JSONの契約追加を伴う |

**推薦: accept**。実運用で安全側停止自体は成功したが、原因特定に手動分解が必要だったため。
