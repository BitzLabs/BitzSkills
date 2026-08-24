---
implements: FLW-NFR-014
depends_on: [FLW-TSK-117]
boundary: plugins/bitz-flow/skills/flow-core/scripts/flowlib/worktree_transaction.py,plugins/bitz-flow/skills/flow-core/schemas/worktree-v2/operation-event-v2.schema.json,tests/test_flow_m2_target_transaction.py,tests/test_flow_m2_intent_atomicity.py,plugins/bitz-flow/.spec/design/FLW-DSN-017.md,plugins/bitz-flow/.claude-plugin/plugin.json,plugins/bitz-flow/plugin.json,plugins/bitz-flow/.codex-plugin/plugin.json
status: done
---

### intentと緊急receiptを単一durable recordへ統合する

`SI-FLW-087`（`FLW-REV-027:SYN-004` P1）。設計は`FLW-DSN-017` §4.2（v2.3）で
`FLW-GATE-006`により承認済み。**永続形式の変更を伴う。**

- **実測した欠陥**: `prepare_intent`が`INTENT_DURABLE` eventのatomic publishと
  緊急receiptのatomic publishを2回に分けて行っていた。この2回の間で停止すると、
  chain検査`len(events) >= 2 and len(emergency) != 1`が問題を記録して`INDETERMINATE`に
  なる一方、`mark_mutating`が`require_emergency=True`を要求するため`MUTATING`へ進めない。
  **Git副作用は証明可能に0件なのにnonceは消費済み**であり、副作用ゼロのtargetが
  同一planで再実行できないまま隔離される。
- **作業内容**:
  - 緊急receiptを`INTENT_DURABLE` event fileへ`emergency_receipt`として同梱し、
    **1回のatomic publish**で確定する。
  - 循環参照を避けるため、同梱前のcore record（`event`／`intent`／`result`／
    `receipt_digest`）のdigestを`event_digest`とする。**coreの形とdigest定義は
    旧形式と同一**に保ち、既存のdigest・filename検査をそのまま効かせる。
  - `inspect()`が同梱receiptを読み、`INTENT_DURABLE`に同梱が無い場合は
    **推測移行せずfail-closed**にする。
  - 緊急receiptを別fileから持ち込む経路を塞ぐ（2回publishの空隙の復活を防ぐ）。
  - 旧設計を固定していた既存testを、新しい不変条件へ書き換える。
- **完了条件**:
  - 4つのpublish step（temp-written／file-fsynced／renamed／dir-fsynced）の
    **どこで停止しても** chainがhealthyであること。すなわち「intentが未確定（`LOCKED`）」
    または「intent確定かつ有効な緊急receipt付き」のどちらかであり、
    **「intent確定かつ緊急receipt無し」が発生しないこと**。
  - Git副作用0件、nonce再利用不可、audit／reconcile可能であること。
  - 旧形式chainを推測移行せずfail-closedにすること。
- **見積り**: 実装PR 1本・1 session。
- **実行判定**: 永続形式変更のため`FLW-DSN-017` §4.2の承認（`FLW-GATE-006`）が前提。
  schema／runtime／testを同一rollback単位に置く。
