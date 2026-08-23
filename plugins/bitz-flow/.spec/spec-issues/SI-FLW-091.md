---
id: SI-FLW-091
raised_by: FLW-REV-027
target: bitz-flow review ledger
proposed_change_type: modify
status: accepted
---
- **目的**: 過去レビューの未解決P0/P1 statusと後続PASS判定の台帳不整合を解消する。
- **提案する修正**: 88件のopen/tracked findingを後続是正証跡へ照合し、resolvedまたは現行issueへの追跡状態へ更新する。最新synthesisの`carried_over`生成を自動検査する。
- **対象ファイル**: `plugins/bitz-flow/.spec/reviews/FLW-REV-*.json`、review synthesis tests/tooling。
- **確認観点**: 未解決P0/P1が最新reviewの`carried_over`から欠落しないこと。resolved化には実在する修正・検証証跡があること。
- **影響推定・ロールバック**: 実装動作は変えずレビュー台帳だけに限定する。既存成果物の履歴内容は削除せずstatus/参照を修正する。
- **依存**: なし。accept推薦（機械集計で88件の未解決を確認）。
