---
id: SDD-CON-043
version: 1.0
status: approved
domain: upstream
priority: high
origin: skills/sdd-data/SKILL.md v0.1.0（reverse-derived）
verification_method: manual-check
derived_from:
supersedes:
superseded_by:
confidence: high
---

### SDD-CON-043 製品非依存の論理データモデル先行設計制約

- **説明**: 特定のデータストア技術への早期ロックインを防ぎ、ドメイン構造の整合性を担保するため、データ設計は製品非依存の論理設計を物理設計に先行させ、ドメインモデルに従わなければならない。
- **受入基準 (EARS)**:
  - WHEN データ格納設計フェーズを実施するとき THEN 開発者は特定のデータベース製品 of 機能を依存しない論理データモデルを物理ストレージ設計より前に構築し、かつドメインモデルの集約境界とトランザクション境界を一致させる SHALL
- **検証手段**: SKILL.md / references の目視確認 + skill-validator チェックリスト
- **Revision History**:
  - 1.0 (2026-07-12) 初版（実装 v1.4.5 からの reverse-derived。ワークスペース新設に伴う逆起票）
  - 1.0 (2026-07-12) 人間裁定により approved 化（チャット指示）
