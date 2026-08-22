---
implements: FLW-NFR-014
depends_on: [FLW-TSK-106,FLW-TSK-111]
boundary: plugins/bitz-flow/skills/flow-core/scripts/flowlib/worktree_transaction.py,plugins/bitz-flow/skills/flow-core/schemas/worktree-v2/target-transaction-v2.schema.json,plugins/bitz-flow/skills/flow-core/schemas/worktree-v2/operation-event-v2.schema.json,plugins/bitz-flow/skills/flow-core/schemas/worktree-v2/mutation-receipt-v2.schema.json,tests/test_flow_m2_target_transaction.py,plugins/bitz-flow/skills/flow-core/SKILL.md,plugins/bitz-flow/.claude-plugin/plugin.json,plugins/bitz-flow/plugin.json,plugins/bitz-flow/.codex-plugin/plugin.json,.claude-plugin/marketplace.json
status: pending
---

### TargetTransactionでlease・fencing・journalを一元化する

- **作業内容**: Git起動権限を持たない単一moduleへOS lock、単調fencing token、operation journal、
  terminal receipt、reconcile closureの更新authorityを集約する。
  - `LOCKED → INTENT_DURABLE → MUTATING → RESULT_DURABLE → DONE / QUARANTINED`を実装する。
  - 最初のGit mutation前にintentと有効な`INDETERMINATE`緊急receiptをdurable公開する。
  - terminal receiptは緊急receiptのdigestを参照し、最長有効chainの単一後継だけを正とする。
  - eventの上書き・削除・sequence再利用、archive、pruneを実装しない。
- **完了条件**: 複数process競合で最大1 writer、全crash pointで緊急またはterminal receiptが残り、
  nonce再利用、receipt複数後継、gap、branch、改変、token巻戻り・overflowを`INDETERMINATE`へ停止する。
- **見積り**: 単独の実装PR 3とし、4 sessionを上限とする。
- **実行判定**: 並行性とcrash safetyの中核。platform primitiveが不足する環境は`UNSUPPORTED`を維持する。
  実装PR 3のrelease integration ownerとしてplugin/skillをpatch bumpする。
