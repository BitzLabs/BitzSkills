---
id: SI-FLW-090
raised_by: FLW-REV-027
target: bitz-flow M2 verification / task trace
proposed_change_type: modify
status: accepted
---
- **目的**: fixture内部の検証とproduction接続完了を区別し、`verified`・task `done`・coverageの過大主張を解消する。
- **提案する修正**: 実環境probe、production dispatcher、timeout、crash境界、recovery分類を検証仕様へ追加し、既存taskの境界と未接続点を再記録する。`FLW-FR-006`へcreate/resume是正taskを直接トレースし、M3のfinish/discardを明示する。
- **対象ファイル**: `FLW-NFR-014`、`FLW-FR-006`、TSK-106〜114、test-spec、coverage manifest、verification evidence、confirmation。
- **確認観点**: 既定dispatcher実走、3platform実観測、全crash point、30秒条件がmachine evidenceへ結び付くこと。最終レビューPASS前にPromotion Gateを通さないこと。
- **影響推定・ロールバック**: NFR影響10成果物、FR影響14成果物。状態遷移は人間裁定を伴い、証跡更新は是正実装後に限定する。
- **依存**: `SI-FLW-084`〜`SI-FLW-089`。accept推薦（現行verified証跡がproduction経路を覆わない）。
