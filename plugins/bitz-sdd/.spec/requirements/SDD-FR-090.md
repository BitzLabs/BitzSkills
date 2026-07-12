---
id: SDD-FR-090
version: 1.0
status: draft
domain: verification
priority: high
origin: skills/sdd-test/SKILL.md v0.1.0（reverse-derived）
verification_method: manual-check
derived_from:
supersedes:
superseded_by:
confidence: high
---

### SDD-FR-090 テスト実装時の ID 付与と境界内配置

- **説明**: sdd-test はテストを実装する際、要件へのトレーサビリティを確保しつつ、タスクで宣言された影響境界を越えないようテストコードを配置しなければならない。
- **受入基準 (EARS)**:
  - WHEN テストを実装する THEN sdd-test はテストケース名に要件 ID を含める SHALL
  - AND THEN sdd-test はテストコードの配置をタスクの `boundary` 宣言内に収める SHALL
- **検証手段**: SKILL.md / references の目視確認 + skill-validator チェックリスト
- **Revision History**:
  - 1.0 (2026-07-12) 初版（実装 v0.1.0 からの reverse-derived。ワークスペース新設に伴う逆起票）
