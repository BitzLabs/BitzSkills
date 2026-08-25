---
implements: FLW-FR-006
depends_on: [FLW-TSK-128]
boundary: plugins/bitz-flow/skills/flow-core/scripts/flowlib/cli.py,plugins/bitz-flow/skills/flow-core/scripts/flowlib/worktree_operability.py,plugins/bitz-flow/skills/flow-core/references/m2-operability-coverage.json,tests/test_flow_m2_readonly_canary.py,tests/test_flow_m1_contract_rows.py,tests/test_flow_m1_write_faults.py,tests/test_flow_m2_operability.py,tests/test_flow_m2_runtime.py,tests/test_flow_m2_confirmation.py,tests/test_flow_m2_legacy_approval.py,tests/test_flow_m2_legacy_chain_precondition.py,plugins/bitz-flow/.spec/design/FLW-DSN-017.md,plugins/bitz-flow/.claude-plugin/plugin.json,plugins/bitz-flow/plugin.json,plugins/bitz-flow/.codex-plugin/plugin.json
status: pending
---

### M2 read-only 3 operationを限定公開しproduction証跡を得る

裁定 2026-08-24（`.spec/reports/decision-2026-08-24-m2-readonly-canary.md`）。
`FLW-REV-028`のGate blocking条件`GP-001`〜`008`消化後の次工程（B → A の B）。

- **なぜ公開するか**: `FLW-CON-008`が要求する「production既定dispatcherを起点とする
  black-box」は、公開集合に無いoperationでは**原理的に取得できない**。
  `FLW-REV-028`の7観点で`実証済み`が0件だった主因はここにあり、
  安全性の証明だけを積んでも増えない。
- **作業内容**:
  - `worktree.doctor` / `audit` / `verify-receipt` を`PUBLISHED_OPERATIONS`と
    `_HANDLERS`へ移す。**write class（`create`／`resume`／`reconcile`／
    `finish`／`discard`）は`_GATED_HANDLERS`のまま。**
  - doctorの`required_human_input`が符丁（`fix-platform-or-bundle`）だったため、
    `worktree_platform.OPERATOR_ACTIONS`とbundle導入手順から**行動可能な**是正を
    組み立てる（`GP-001`の要求をdoctor自身へ適用）。
  - production black-box test（`flow.py`別process起動）を追加する。
  - 出荷面を固定していた既存testを**新しい不変条件（write は依然 gated）**へ更新する。
    弱めない。
  - `FLW-DSN-017` §13.1／§13.7 と coverage manifest を実測へ更新する。
- **完了条件**:
  - read-only 3件がproduction既定dispatcherから到達すること（black-box）。
  - write 5件が`command-unavailable`で閉じること（black-box）。
  - 公開経路の実行でpersistent stateが変化しないこと。
  - doctorの出力が符丁でなく行動可能であること。
  - §13.7 の「接続完全性」に実証が入ること。
- **見積り**: 実装PR 1本・1 session。
- **後退条件**: persistent stateの変化、公開経路のtraceback、`FLW-REV-029`のP0の
  いずれかで`PUBLISHED_OPERATIONS`から外す（裁定記録参照）。
