---
id: FLW-FR-002
version: 1.0
status: verified
domain: tooling
priority: medium
origin: SI-CORE-031
verification_method: manual-check
derived_from: CORE-CON-008
supersedes:
superseded_by:
confidence: high
---

### FLW-FR-002 flow-doctor 環境診断スキル

- **説明**: bitz-flow の各フロー（feature ブランチ / worktree 並列 / Issue 駆動 PR）が
  前提とする外部ツール環境を読み取り専用で診断する標準ライフサイクルスキル
  `flow-doctor` を提供する（CORE-CON-008 の doctor 最小契約、DSN-003 のマトリクスに基づく）。
- **受入基準 (EARS)**:
  - THE flow-doctor は読み取り専用で診断を行い、対象プロジェクト・配置先への書き込みを一切行わないこと SHALL
  - WHEN 診断を実行する THEN git の存在とバージョン（worktree 運用に必要な 2.5 以上）を診断すること SHALL
  - WHEN 診断を実行する THEN gh CLI の存在と認証状態（`gh auth status`）を診断し、欠如・未認証の場合は導入・認証手順つきの修正案を報告すること SHALL（flow-pr を使わない運用では警告に留める）
  - WHEN Git リポジトリ内で実行される THEN リモート `origin` の有無とデフォルトブランチの特定可否を診断に含めること SHALL
  - IF すべての診断項目に問題がない THEN OK 判定と各項目の根拠を簡潔に報告すること SHALL
- **検証手段**: skill-validator チェックリスト通過 + SKILL.md の目視確認（読み取り専用の明記・
  診断項目と修正案の記載）+ release_check / spec_inspect PASS。
- **Revision History**:
  - 1.0 (2026-07-19) 初版（draft 起票。SI-CORE-031 / DSN-003 由来）
