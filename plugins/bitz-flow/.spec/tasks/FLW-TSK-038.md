---
implements: FLW-NFR-007, FLW-FR-013
depends_on: [FLW-TSK-037]
boundary: plugins/bitz-flow/skills/flow-core/scripts/flowlib/intent.py, tests/test_flow_m1_intent.py
status: pending
---

### intent storeとquarantineライフサイクル

- **作業内容**: `flowlib/intent.py` に durable intent の記録と quarantine のライフサイクルを実装する。
  永続化そのものは durable store（append-only・hash-chain・RPO 0）に委ね、ここでは
  **write 状態機械の不変条件**を担当する。

  - **状態遷移**: `PLANNED → GUARDED → PENDING_INTENT → MUTATING → RECONCILING →`
    `DONE` / `PARTIAL` / `STALE` / `QUARANTINED`、および `QUARANTINED → HumanReview → 解除`。
    各状態の不変条件（durable intent の要否、mutation 許可、次回同 target write の可否）を
    構造で表現し、**`PENDING_INTENT` の永続化前に副作用を開始できない**ようにする。
  - **intent record v1** の schema に沿った record を書く。既存 record を上書きせず、
    状態変更は同一 operation ID の **hash-chain entry として追記**する。
  - **解除 receipt**: `DONE` または副作用不成立を証明できた場合だけ intent を解除し、receipt を追記する。
  - **quarantine**: 成否または因果を一意化できない場合に確定させる。
    quarantine 中の target への次回 write は**人間の解除まで `BLOCKED`**。
    解除は観測結論（`confirmed-done` / `no-effect` / `orphan-object-no-reachable-effect` /
    `abandoned-with-compensation` / `unresolved`）と必須証跡の対応表に従い、
    `unresolved` は解除不可とする。解除 receipt には reviewer・根拠 digest・旧新 token・結論・時刻を残す。
  - **単回 authorization capability**: 解除後の mutation には
    `target, snapshot_digest, prior_operation_id, reviewer, expires_at, nonce` を署名した
    capability と**新しい operation ID** を要求する。target alias 不一致・期限切れ・nonce 再利用・
    旧 operation への循環参照は拒否する。nonce の状態遷移は coordinator core が正。

- **完了条件**: 上記の単体テストが PASS し、次の負の対照が拒否されること —
  intent 永続化前の mutation 開始、既存 record の上書き、`unresolved` での quarantine 解除、
  旧 operation ID の再利用、期限切れ capability での mutation、nonce の再利用、
  `PARTIAL` / `STALE` からの自動再 apply。
  `M1-FLT-001`（intent 各点 crash）、`M1-FLT-002`（intent fsync 後・mutation 前 crash で
  pending 保持・次回 write BLOCKED）、`M1-FLT-004`（reconcile 中 crash で blind retry 0）、
  `M1-FLT-027`（capability nonce 消費各点 crash・key 失効）が期待どおりであること。
  `.venv/bin/pytest -q` が全件 PASS すること。

- **備考**: 公開 operation を増やさない（`FLW-DSN-014` 縮退規則3）。
  自動巻き戻し・補償は `FLW-NFR-003` により禁止であり、ここでも実装しない。
  署名検証の暗号実装は本タスクの範囲外とし、**capability の検証契約**（必須項目・拒否条件）を実装する。
