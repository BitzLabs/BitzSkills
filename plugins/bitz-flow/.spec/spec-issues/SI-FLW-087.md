---
id: SI-FLW-087
raised_by: FLW-REV-027
target: flow-core TargetTransaction
proposed_change_type: modify
status: accepted
---
- **目的**: intent durable化と有効な緊急receiptの間にcrash可能な不健全chainを残さない。
- **提案する修正**: intentと緊急receiptを単一durable transaction recordとして公開するか、receipt確定前を`INTENT_DURABLE`と扱わない中間状態へ変更する。
- **対象ファイル**: `worktree_transaction.py`、target-transaction/event schema、crash injection tests。
- **確認観点**: intent event publish直後を含む全境界でkillしてもhealthy chain 100%、Git副作用0、nonce再利用不可、audit/reconcile可能であること。
- **影響推定・ロールバック**: 永続形式へ触れるためDesign Gate対象。旧形式は推測移行せずfail-closedとし、schema/runtime/testを同一rollback単位にする。
- **依存**: なし。accept推薦（`FLW-NFR-014`のdurable receipt受入基準に直接違反）。
