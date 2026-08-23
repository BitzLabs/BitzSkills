---
id: SI-FLW-086
raised_by: FLW-REV-027
target: flow-core process supervision / operability
proposed_change_type: modify
status: open
---
- **目的**: Git childのhang時にも30秒以内のclosed terminal resultへ収束させる。
- **提案する修正**: read/write共通の有限TimeoutBudgetとprocess supervisionを実装し、terminate/kill/wait、出力上限、reconciliation reserveを適用する。終了を証明できないwriteは緊急receiptを保持して`INDETERMINATE`へ閉じる。
- **対象ファイル**: `worktree_runtime.py`、process adapter、operability CLI、fault/load tests。
- **確認観点**: `--timeout-seconds`が全childへ伝播すること。hang・出力超過・終了不能でも例外や無期限lockにならず、10,000 event/100 MiB条件で30秒以内に閉じること。
- **影響推定・ロールバック**: Git起動経路全体に影響するため独立変更とし、公開は再確認までgatedにする。
- **依存**: `SI-FLW-084`のplatform child-supervision観測と整合させる。accept推薦（受入基準の実装欠落）。
