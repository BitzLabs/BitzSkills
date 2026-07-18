---
id: FLW-FR-001
version: 1.0
status: implementing
domain: governance
priority: high
origin: SI-FLW-001
verification_method: unit-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### FLW-FR-001 squash merge 後のブランチ終端化と安全な後片付け

- **説明**: squash merge 済みの head ブランチを次の作業へ再利用せず、最新のデフォルトブランチから再分岐する。マージ後の worktree とローカルブランチの削除は、GitHub の MERGED 証跡、PR head SHA、merge commit の到達性、管理対象 worktree の対応を検証してから順序立てて実行し、証跡が不足する場合は安全側に停止する。リモートブランチは競合更新を破壊しないよう自動削除せず、期待 SHA 付きの候補報告までとする。
- **受入基準 (EARS)**:
  - WHEN PR 作成前に候補 head ブランチを検査する THEN flow-pr は同じ head を持つマージ済み PR、デフォルトブランチとの差分、既存 open PR の base と mergeability を読み取り専用で照会し、再利用・空差分・base 不一致・競合を検出した場合は通常続行を拒否すること SHALL
  - IF PR または Git 状態の照会が失敗するか結果を判定できない THEN flow-pr の事前検査は再利用可と推定せず非ゼロ終了して人間確認を求めること SHALL
  - WHEN squash merge 後の cleanup を実行または再開する THEN worktree_ops.py は PR の state が MERGED、headRefName が削除対象ブランチ、存在する worktree・ローカル ref・remote ref の先端が headRefOid と一致し、mergeCommit が origin のデフォルトブランチへ到達済みであることを削除前に検証すること SHALL
  - IF squash merge の証跡が欠落または不一致である THEN worktree_ops.py は worktree・ローカルブランチ・リモートブランチを削除せず非ゼロ終了すること SHALL
  - WHEN squash merge の証跡がすべて成立する THEN worktree_ops.py はデフォルトブランチの fast-forward、worktree 除去、証跡付きローカルブランチ強制削除、remote prune、remote ref の再照会の順序を守り、完了済み段階を安全に skip して再実行できること SHALL
  - WHEN prune 後にリモートブランチが実在する THEN worktree_ops.py は PR の headRefOid と一致する ref だけを削除候補として報告し、同時更新を条件付きで防げない自動 remote delete は実行しないこと SHALL
  - WHEN cleanup の入力を受理する THEN worktree_ops.py は work-id・branch・default branch・正規化した管理対象 worktree パスを検証し、存在する worktree は path・branch・HEAD の対応を確認して、デフォルトブランチ・管理外対象・矛盾する部分状態を拒否すること SHALL
  - WHEN 外部の git または gh コマンドが失敗またはタイムアウトする THEN 各ヘルパーは完了済み段階を含む機密情報なしの構造化診断を返して安全側に停止すること SHALL
  - WHEN マージ済み branch の再利用防止と cleanup の回帰テストを実行する THEN MERGED・未マージ・head進行・worktree不一致・途中失敗再開・stale ref・GitHub照会失敗・タイムアウトの各ケースが自動テストで green になること SHALL
  - WHEN python3 scripts/release_check.py と python3 scripts/spec inspect --workspace . plugins/* を実行する THEN bitz-flow の version bump と仕様トレースを含む全チェックが PASS すること SHALL
- **検証手段**: branch preflight の終了コード・差分・mergeability・構造化診断、cleanup の PR head SHA と対象 ref の一致、入力境界、コマンド順序、冪等再開、副作用ゼロの安全側停止、remote ref の報告専用化を `tests/test_branch_preflight.py` と `tests/test_worktree_ops.py` で検証する（unit-test）。既存 add/list/cleanup/discard の互換性テスト、skill-validator、全 pytest、release_check、monorepo spec inspect も実行する。
- **Revision History**:
  - 1.0 (2026-07-18) 初版（draft 起票。SI-FLW-001 の起票時前提を現行 flow-pr / flow-worktree / worktree_ops.py と照合し、趣旨を変える乖離がないことを確認）
  - 1.0 (2026-07-18) Design Review の critical / major 指摘を反映（PR head SHA照合、入力境界、冪等再開、timeout、remote deleteの安全側縮退、差分・mergeability検査を契約化。draft 内の補強でversion据え置き）
