---
id: QLT-FR-001
version: 1.0
status: verified
domain: quality-core
priority: high
origin: アルダグラムQAプラクティス + 設計 v0.1.0
verification_method: example-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### QLT-FR-001 QAプロセスの自律オーケストレーション

- **説明**: `quality-core` は、初期ヒアリングから影響分析・リスクスコアリング・テスト設計・多層ゲート・品質サマリー出力までの品質ライフサイクル全体を対話型で統括し、セッションファイル（`qa-session.json`）で進捗と入出力を管理しなければならない。
- **受入基準 (EARS)**:
  - WHEN ユーザーが品質プロセスを開始した THEN システムは `.spec/quality/sessions/` 配下に `qa-session.json` を生成し Phase 0 から順次進行する SHALL
  - WHEN 各 Phase の工程が完了した THEN システムは 人間の確認・承認を求めてから次 Phase へ遷移する SHALL
  - WHEN 中断されたセッションが存在する THEN システムは `qa-session.json` から状態を復元して再開可能とする SHALL
- **検証手段**: tests/test_quality_core.py（セッション作成・復元・フェーズ進行）
- **Revision History**:
  - 1.0 (2026-08-14) 初版起票 (br7.hide)
  - 1.0 (2026-08-14) 人間裁定・多観点レビュー（QLT-REV-001 PASS）により approved 化 (br7.hide)
  - 1.0 (2026-08-14) implementing / tests/test_quality_core.py 全 PASS により verified 化 (br7.hide)
