---
id: SI-FLW-088
raised_by: FLW-REV-027
target: flow-core recovery audit
proposed_change_type: modify
status: open
---
- **目的**: `QUARANTINED`を正常完了と誤分類せず、運用者判断を誤った事実へ固定しない。
- **提案する修正**: `confirmed-complete`を`DONE`かつ予定postcondition成立時に限定し、`QUARANTINED`は常にindeterminate/quarantineへ分類する。receiptへrequested/actual outcomeとplanned-effects digestを束縛する。
- **対象ファイル**: `worktree_recovery.py`、transaction receipt、operability audit、recovery tests。
- **確認観点**: failure時の現在snapshotが一致してもcompleteにならないこと。DONE/incomplete/quarantineの陽性・陰性対照を置くこと。
- **影響推定・ロールバック**: audit分類とreceipt schemaに影響。自動Git操作は増やさず安全側へ狭める。
- **依存**: `SI-FLW-087`のreceipt境界確定後に適用。accept推薦（現行分類の誤陽性）。
