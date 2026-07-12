---
id: SDD-FR-011
version: 1.0
status: approved
domain: workflow
priority: medium
origin: skills/sdd-core/SKILL.md v1.7.3（reverse-derived）
verification_method: manual-check
derived_from:
supersedes:
superseded_by:
confidence: high
---

### SDD-FR-011 軽量レーン（ショートカット）の適用条件と制限

- **説明**: 軽微な変更については `discovery` / `design` などの工程をスキップする軽量レーンの使用を認めるが、公開契約に触れる変更については通常フローおよび Design Gate を通すことを強制し、品質を維持しなければならない。本要件は公開契約に該当する。
- **受入基準 (EARS)**:
  - WHEN 変更対象が契約（公開API、`.spec` スキーマ、frontmatter 書式）に触れない軽微な変更である THEN エージェントは `discovery` および `design` の工程をスキップして軽量レーンで実装してよい SHALL
  - WHEN 変更対象が契約に触れる変更である THEN エージェントは軽量レーンの使用を禁止し、通常フローおよび Design Gate を通さなければならない SHALL
- **検証手段**: SKILL.md / references の目視確認 + skill-validator チェックリスト
- **Revision History**:
  - 1.0 (2026-07-12) 初版（実装 v1.4.5 からの reverse-derived。ワークスペース新設に伴う逆起票）
  - 1.0 (2026-07-12) 人間裁定により approved 化（チャット指示）
