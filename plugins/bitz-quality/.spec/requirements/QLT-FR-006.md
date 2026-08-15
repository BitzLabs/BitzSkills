---
id: QLT-FR-006
version: 1.0
status: verified
domain: quality-design
priority: high
origin: QA専門エージェント分業モデル + 設計 v0.1.0
verification_method: example-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### QLT-FR-006 影響分析および不具合傾向分析の自律実行

- **説明**: `quality-design` は、変更差分から影響を受けるファイル・API・ドメイン境界を抽出する「影響分析」と、過去の類似バグや再発防止ルールからリスク要因を特定する「不具合傾向分析」を自律実行しなければならない。
- **受入基準 (EARS)**:
  - WHEN 影響分析サブエージェントが起動された THEN システムは Git差分および依存関係から波及範囲（直接変更・間接影響・DB影響）を特定し `.spec/quality/analyses/` に出力する SHALL
  - WHEN 不具合傾向分析サブエージェントが起動された THEN システムは 再発防止ルール台帳（`rules-ledger.md`）およびコミット履歴から該当領域の既知リスクを抽出する SHALL
  - WHEN 各分析が完了した THEN システムは 成果物を `qa-session.json` に記録して後続のテスト設計へ受け渡す SHALL
- **検証手段**: tests/test_quality_design.py（影響分析抽出、ルール照合、セッション連携）
- **Revision History**:
  - 1.0 (2026-08-14) 初版起票 (br7.hide)
  - 1.0 (2026-08-14) 人間裁定・多観点レビュー（QLT-REV-001 PASS）により approved 化 (br7.hide)
  - 1.0 (2026-08-14) implementing / tests/test_quality_design.py 全 PASS により verified 化 (br7.hide)
