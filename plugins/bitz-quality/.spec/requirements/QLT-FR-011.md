---
id: QLT-FR-011
version: 1.0
status: verified
domain: quality-trace
priority: high
origin: bitz-sdd V4 契約接続 + 設計 v0.4.0
verification_method: example-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### QLT-FR-011 EARS 要件 ID とテストケース ID の自動トレーサビリティ照合

- **説明**: `quality-trace` は、`.spec/requirements/` 内の EARS 要件 ID（例: `QLT-FR-001`）と `tests/` 配下の自動テスト関数・docstring を照合し、要件カバレッジおよび未テスト要件を可視化・検証できなければならない。
- **受入基準 (EARS)**:
  - WHEN `quality_trace.py verify` が実行された THEN システムは 全要件 ID とテストコード内の参照を突合し トレーサビリティマトリクスを出力する SHALL
  - WHEN テスト参照のない要件が存在する THEN システムは 未カバー要件一覧を出力し 警告または非ゼロ終了する SHALL
  - WHEN 全要件がテストでカバーされている THEN システムは 100% カバー確認と ゼロ終了コード (0) を返す SHALL
- **検証手段**: tests/test_quality_trace.py（全件カバーPASS、未カバー検知FAIL、マトリクス出力）
- **Revision History**:
  - 1.0 (2026-08-14) 初版起票・承認 (br7.hide)
  - 1.0 (2026-08-14) implementing / tests/test_quality_trace.py 全 PASS により verified 化 (br7.hide)
