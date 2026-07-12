---
id: SDD-FR-070
version: 1.0
status: approved
domain: execution
priority: high
origin: skills/sdd-implement/SKILL.md v0.1.1（reverse-derived）
verification_method: manual-check
derived_from:
supersedes:
superseded_by:
confidence: high
---

### SDD-FR-070 タスク分解時のトレーサビリティ・境界の宣言

- **説明**: sdd-implement は承認済み要件をタスクに分解する際、各タスクファイルの frontmatter に要件 ID、依存関係、および影響境界を必ず宣言しなければならない（公開契約に該当）。
- **受入基準 (EARS)**:
  - WHEN 要件を `.spec/tasks/` 配下のタスクへ分解する THEN sdd-implement は各タスクの frontmatter に `implements`、`depends_on`、`boundary` を必ず宣言 SHALL
- **検証手段**: SKILL.md / references の目視確認 + skill-validator チェックリスト
- **Revision History**:
  - 1.0 (2026-07-12) 初版（実装 v0.1.1 からの reverse-derived。ワークスペース新設に伴う逆起票）
  - 1.0 (2026-07-12) 人間裁定により approved 化（チャット指示）
