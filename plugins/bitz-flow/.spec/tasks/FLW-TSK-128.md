---
implements: FLW-NFR-014
depends_on: [FLW-TSK-127]
boundary: plugins/bitz-flow/.spec/design/FLW-DSN-017.md,tests/test_flow_m2_legacy_chain_precondition.py,plugins/bitz-flow/docs/runbooks/m2-worktree-quarantine.md,plugins/bitz-flow/.claude-plugin/plugin.json,plugins/bitz-flow/plugin.json,plugins/bitz-flow/.codex-plugin/plugin.json
status: pending
---

### 旧形式chainの移行を前提条件として明示する

`FLW-REV-028:GP-004`（P1）。裁定: **案B（実装せず前提条件として明示）**。
`tmpfs`のときと同じ判断軸で、**発生しない状態のための復旧経路を作らない**。

- **実測した欠陥**:
  - 旧形式（intentと緊急receiptを2 fileへ分離publishする形。`FLW-TSK-118`以前）のchainは
    `inspect()`がfail-closedで`INDETERMINATE`へ閉じるため、reconcileもauditも通らない。
  - §4.2 は「doctorがmanual rollback手順を提示する」と書いていたが**実装が無い**。
    設計が存在しない機能を約束している状態だった。
- **なぜ実装しないか**:
  - M2は未公開である（worktree全8 operationが`_GATED_HANDLERS`にあり公開dispatcher非到達）。
    したがって旧形式chainを持つrepositoryは**存在しない**。
  - 存在しない状態のための復旧経路は、実環境で発火せず、しかも検証手段も無い。
    `FLW-TSK-126`（tmpfs／semantic self-test）と同じ判断軸を適用する。
- **作業内容**:
  - §1.2 へ公開前提条件として「対象repositoryに旧形式chainが存在しないこと」を明示する。
  - §4.2 の「doctorがmanual rollback手順を提示する」という**約束を取り下げ**、
    実装しない理由と再検討条件を書く。
  - fail-closedの挙動そのものは変えない（`FLW-TSK-118`で実装済み）。
  - runbookへ、旧形式chainを踏んだ場合の判別と連絡先を書く。
- **完了条件**:
  - 設計に「存在しない機能の約束」が残っていないこと（機械検査）。
  - 旧形式chainが依然fail-closedであること（回帰していないこと）。
  - 再検討条件が明記されていること。
- **見積り**: 実装PR 1本・0.5 session。**runtimeは変えない。**
- **実行判定**: 公開後に旧形式chainが実在しうるようになった時点で再検討する。
  条件は §4.2 に明記する。
