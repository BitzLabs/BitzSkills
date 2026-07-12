---
id: SDD-FR-071
version: 1.0
status: draft
domain: execution
priority: high
origin: skills/sdd-implement/SKILL.md v0.1.1（reverse-derived）
verification_method: manual-check
derived_from:
supersedes:
superseded_by:
confidence: high
---

### SDD-FR-071 タスクの並列投入条件の厳守

- **説明**: sdd-implement はタスクを複数並列で投入する際、タスク間の競合を避けるために依存関係の解決と境界の独立性を確認しなければならない。
- **受入基準 (EARS)**:
  - WHEN タスク群を並列投入する THEN sdd-implement は `depends_on` が解決済み かつ `boundary` が互いに素なタスク群のみを選択 SHALL
- **検証手段**: SKILL.md / references の目視確認 + skill-validator チェックリスト
- **Revision History**:
  - 1.0 (2026-07-12) 初版（実装 v0.1.1 からの reverse-derived。ワークスペース新設に伴う逆起票）
