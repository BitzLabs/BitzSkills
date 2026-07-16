---
id: SDD-FR-061
version: 1.0
status: verified
domain: verification
priority: medium
origin: skills/sdd-review/SKILL.md v0.2.2（reverse-derived）
verification_method: manual-check
derived_from:
supersedes:
superseded_by:
confidence: high
---

### SDD-FR-061 Consistency 観点の指摘事項のプレフィックス分離

- **説明**: sdd-review は Consistency 観点でのレビュー指摘事項を記録する際、制約要件（CON）との ID 衝突を避けるため専用のプレフィックスを使用しなければならない。
- **受入基準 (EARS)**:
  - WHEN Consistency 観点の指摘事項を記録する THEN sdd-review は ID に `RVC-` プレフィックスを使用 SHALL
- **検証手段**: SKILL.md / references の目視確認 + skill-validator チェックリスト
- **Revision History**:
  - 1.0 (2026-07-12) 初版（実装 v0.2.2 からの reverse-derived。ワークスペース新設に伴う逆起票）
  - 1.0 (2026-07-12) 人間裁定により approved 化（チャット指示）
