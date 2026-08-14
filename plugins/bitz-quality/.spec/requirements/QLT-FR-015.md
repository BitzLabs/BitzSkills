---
id: QLT-FR-015
version: 1.0
status: verified
domain: quality-core
priority: high
origin: エージェント自律ナビゲーション設計 + 設計 v1.0.0
verification_method: example-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### QLT-FR-015 エージェント向け軽量QA状態照会と次アクション提案

- **説明**: `quality-core` は、エージェントが自律的にQA進行状況を把握できるよう、現在のQAフェーズ・リスク関与レベル・ゲート合否・未解決指摘・SDD要件カバレッジを軽量集計し、次に実行すべき推奨アクションを提示できなければならない。
- **受入基準 (EARS)**:
  - WHEN `quality_status.py` が実行された THEN システムは 現在のQAフェーズ（intake/scoring/design/gate/trace/done）と各種ゲート判定を要約表示する SHALL
  - WHEN 未完了の工程が存在する THEN システムは 次に呼び出すべき推奨スキルおよびコマンドを具体的に提示する SHALL
  - WHEN 全工程が完了している THEN システムは 完了状態 (done) と リリース可能サマリーを出力する SHALL
- **検証手段**: tests/test_quality_status.py（フェーズ判定、次アクション提示、完了時サマリー）
- **Revision History**:
  - 1.0 (2026-08-14) 初版起票・承認 (br7.hide)
  - 1.0 (2026-08-14) implementing / tests/test_quality_status.py 全 PASS により verified 化 (br7.hide)
