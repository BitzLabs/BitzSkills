---
implements: FLW-NFR-014
depends_on: [FLW-TSK-118]
boundary: plugins/bitz-flow/skills/flow-core/scripts/flowlib/worktree_recovery.py,plugins/bitz-flow/skills/flow-core/scripts/flowlib/worktree_transaction.py,tests/test_flow_m2_recovery.py,tests/test_flow_m2_outcome_binding.py,plugins/bitz-flow/.spec/design/FLW-DSN-017.md,plugins/bitz-flow/.claude-plugin/plugin.json,plugins/bitz-flow/plugin.json,plugins/bitz-flow/.codex-plugin/plugin.json
status: implementing
---

### QUARANTINEDの完了誤分類を是正しoutcomeをreceiptへ束縛する

`SI-FLW-088`（`FLW-REV-027:SYN-005` P1）。

- **実測した欠陥**: `worktree_recovery.audit()`の分類条件が
  `report.state in {"RESULT_DURABLE", "DONE", "QUARANTINED"}`であり、**`QUARANTINED`が
  完了判定の集合に入っている**。`RESULT_DURABLE` eventの`postcondition_digest`は
  *予定*ではなく*実観測*の digest（`quarantined_failure`が観測値を記録する）であるため、
  quarantine後にrepositoryが変化していなければ現在snapshotと一致し、
  **`confirmed-complete`へ分類される**。運用者は隔離された操作を正常完了と誤認する。
  これは`FLW-DSN-017` §13.2の不変条件（`QUARANTINED`を`confirmed-complete`へ
  分類しない）に違反する。
- **作業内容**:
  - `confirmed-complete`を`report.state == "DONE"`**かつ**予定postcondition成立時に限定する。
  - `QUARANTINED`は常に`quarantine`へ分類する（現在snapshotの一致を根拠にしない）。
  - `RESULT_DURABLE`（終局event未着）は`confirmed-complete`にしない。記録された
    requested outcomeが`QUARANTINED`なら`quarantine`、そうでなければ`indeterminate`。
  - `RESULT_DURABLE` eventへ requested outcome（`terminal_state`）と
    `planned_effects_digest`を束縛し、実観測値だけで完了を主張できないようにする。
- **完了条件**:
  - failure時の現在snapshotが記録値と一致しても`confirmed-complete`にならないこと。
  - `DONE`／`incomplete`／`quarantine`の**陽性・陰性対照**をtestで置くこと。
  - 自動Git操作を増やさず、分類は安全側へ狭めるだけであること。
- **見積り**: 実装PR 1本・1 session。
- **実行判定**: `FLW-TSK-118`でreceipt境界が確定した後に適用する。
