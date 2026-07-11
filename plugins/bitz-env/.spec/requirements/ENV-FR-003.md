---
id: ENV-FR-003
version: 1.0
status: implementing
domain: deploy
priority: high
origin: 製作プラン + 実装 v0.1.0（reverse-derived）
verification_method: example-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### ENV-FR-003 env-init のユーザー確認付き生成

- **説明**: env-init スキルは、生成物（settings.json permissions・AGENTS.md 雛形・
  CLAUDE.md 断片・advisor/worker サブエージェント）をユーザー確認なしに書き出しては
  ならず、既存ファイルがある場合は上書きせず diff を提示してマージ案を出さなければならない。
- **受入基準 (EARS)**:
  - WHEN 生成対象のファイルが存在しない THEN システムは生成内容を提示し ユーザー承認後にのみ書き出す SHALL
  - WHEN 生成対象のファイルが既に存在する THEN システムは上書きせず diff と マージ案を提示する SHALL
  - WHEN 既存の permissions とマージする THEN システムは既存の deny/ask を削除しない SHALL
    （緩和はユーザーの明示判断のみ）
- **検証手段**: evals/env-init/（skill-tester のシナリオテスト: 新規/既存あり/マージ）
- **Revision History**:
  - 1.0 (2026-07-11) 初版（実装 v0.1.0 からの reverse-derived）
  - 1.0 (2026-07-11) 人間裁定により approved 化（チャット指示）
  - 1.0 (2026-07-11) implementing 遷移（実装タスク done 確認・sdd-test 工程開始）
