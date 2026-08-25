---
implements: FLW-NFR-014
depends_on: [FLW-TSK-129]
boundary: plugins/bitz-flow/skills/flow-core/scripts/flowlib/worktree_operability.py,plugins/bitz-flow/skills/flow-core/scripts/flowlib/worktree_runtime.py,tests/test_flow_m2_deadline_propagation.py,tests/test_flow_m2_operation_budget.py,plugins/bitz-flow/.spec/design/FLW-DSN-017.md,plugins/bitz-flow/.claude-plugin/plugin.json,plugins/bitz-flow/plugin.json,plugins/bitz-flow/.codex-plugin/plugin.json
status: implementing
---

### operation deadlineを全経路へ実効化し振る舞いで検査する

`FLW-REV-029:GP-001`（P0 `SYN-001`）／`GP-002`（`SYN-002`）／`GP-006`（`SYN-009`）。
3つは同じ関心事である。裁定参照:
`.spec/reports/decision-2026-08-24-canary-forward-fix.md`。

- **実測した欠陥**:
  - **公開した3 operationにdeadlineが無い**（P0）。`worktree_operability.py`に
    `OperationDeadline`の参照が0件。`doctor`（L169）／`audit_operation`（L292）／
    `verify_receipt`（L321）が作る`RepositoryObserver`と`_transaction`が無期限で走る。
  - **deadline伝播に抜け道がある**。`worktree_runtime.py`の`_common_dir()`／`_head()`
    （L342／L359／L363／L641）はdeadlineを受け取らず、`_rederive()`（L807／L874）は
    **新しいdeadlineを開始する**。
  - **`persistent_state_digest`が全bytes読み**。read-only guardは各operationの前後
    2回走るため、100 MiB級journalでは200 MiBの読み取りが公開経路へ入る。
  - **確認がsource照合だった**。`test_observer_and_coordinator_receive_the_deadline`は
    sourceの2文字列しか見ておらず、上の抜け道を見逃した。これが`SYN-001`と`SYN-002`の
    直接原因である。
- **作業内容**:
  - 公開3 operationへ`OperationDeadline`を結線する。
  - `_common_dir`／`_head`／`_rederive`を含む全child経路へ**単一の**deadlineを配る。
    `_rederive`は新規に開始せず受け取る。
  - `persistent_state_digest`を逐次読みへ変える。
  - **検査を振る舞いへ置き換える**（`GP-006`）。source照合をGP消化の単独根拠にしない。
    実際に期限を尽きさせ、child起動が止まることを観測する。
- **完了条件**:
  - 公開3 operationがdeadline配下に入ること（**振る舞いで検査**）。
  - deadlineを受け取らないchild経路が0件であること（**振る舞いで検査**）。
  - `persistent_state_digest`が全bytesを一度にロードしないこと。
  - source照合testを振る舞い検査へ置き換えること。
- **見積り**: 実装PR 1本・1 session。
- **実行判定**: 本taskの完了までは`origin/main`へマージしない（裁定記録の担保1）。
