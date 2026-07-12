---
id: SDD-CON-052
version: 1.0
status: draft
domain: upstream
priority: high
origin: skills/sdd-ops/SKILL.md v0.3.0（reverse-derived）
verification_method: manual-check
derived_from:
supersedes:
superseded_by:
confidence: high
---

### SDD-CON-052 運用設計成果物のマスター配置先およびID/Frontmatter制約

- **説明**: 運用設計成果物の一貫性と追跡可能性を担保するため、すべての運用設計成果物は指定されたマスター配置先に作成され、特定のID体系とフロントマターを付与されなければならない。
- **受入基準 (EARS)**:
  - WHEN インフラ・運用設計の成果物を作成または更新するとき THEN 開発者またはシステムは `.spec/design/` 配下に直接マスターファイル（infrastructure.md, security-model.md, observability.md, dr.md, cost-estimate.md）を作成し、かつ各マスターファイルに `INF-NNN` 形式のIDおよび共通のYAML frontmatterを付与する SHALL
- **検証手段**: SKILL.md / references の目視確認 + skill-validator チェックリスト
- **Revision History**:
  - 1.0 (2026-07-12) 初版（実装 v1.4.5 からの reverse-derived。ワークスペース新設に伴う逆起票）
