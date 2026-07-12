---
id: SDD-CON-042
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

### SDD-CON-042 データモデリングにおける Mermaid erDiagram 記述制約

- **説明**: Mermaid レンダラーによる構文エラーを防ぎ、データモデルの解釈に一貫性を持たせるため、データモデルの ER図記述において特定の Mermaid erDiagram 規律を遵守しなければならない。
- **受入基準 (EARS)**:
  - WHEN 論理データモデルを Mermaid の `erDiagram` を用いて記述するとき THEN 開発者はエンティティ名および属性名に含まれる非 ASCII 文字を二重引用符（`" "`）で囲み、かつ属性のデータ型を明記し、かつ主キーに `PK`、外部参照に `FK` マーカーを付与する SHALL
- **検証手段**: SKILL.md / references の目視確認 + skill-validator チェックリスト
- **Revision History**:
  - 1.0 (2026-07-12) 初版（実装 v1.4.5 からの reverse-derived。ワークスペース新設に伴う逆起票）
  - 1.0 (2026-07-12) 人間裁定により approved 化（チャット指示）
