---
id: ENV-FR-007
version: 1.0
status: approved
domain: deploy
priority: medium
origin: 製作プラン + 実装 v0.1.0（reverse-derived）
verification_method: example-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### ENV-FR-007 env-doctor による3層同期診断

- **説明**: env-doctor スキルは、ガードレール3層（settings.json の permissions ⇔
  プラグイン同梱フック ⇔ AGENTS.md のナラティブ）と協調構成（レジストリ ⇔ 有効
  プラグイン ⇔ CLAUDE.md 委譲マトリクス ⇔ .claude/agents/ 実体）の同期ズレを検出し、
  チェックリスト形式で報告して修正案を提案しなければならない。修正の実施は
  ユーザー承認後に限る。
- **受入基準 (EARS)**:
  - WHEN 診断を実行する THEN システムは各検査を PASS / WARN / FAIL で報告し、 FAIL / WARN には修正案を付す SHALL
  - IF 層間に不一致がある THEN システムは「強い方（より制限的な方）に揃える」修正案を 提案し、緩和方向の変更を自動提案しない SHALL
  - WHILE ユーザーの承認が得られていない THE システムは修正を実施しない SHALL
- **検証手段**: evals/env-doctor/（ズレ注入 → 検出・提案方向のアサーション）
- **Revision History**:
  - 1.0 (2026-07-11) 初版（実装 v0.1.0 からの reverse-derived）
  - 1.0 (2026-07-11) 人間裁定により approved 化（チャット指示）
