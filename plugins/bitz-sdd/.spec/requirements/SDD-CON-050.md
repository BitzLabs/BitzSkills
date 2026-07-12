---
id: SDD-CON-050
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

### SDD-CON-050 運用指標の階層別定義と根拠明示制約

- **説明**: 運用設計における目標値の現実性と妥当性を保証するため、可用性や復旧目標などの運用指標はサービス階層（critical / standard / best-effort）ごとに定義され、その数値の根拠や前提が明記されなければならない。
- **受入基準 (EARS)**:
  - WHEN インフラ・運用設計で SLO または RTO/RPO などの運用指標を定義するとき THEN 開発者はサービスをクリティカリティ（critical / standard / best-effort）で階層化し、かつ数値の根拠や前提を明記し、根拠のない数値は `TBD` と明示する SHALL
- **検証手段**: SKILL.md / references の目視確認 + skill-validator チェックリスト
- **Revision History**:
  - 1.0 (2026-07-12) 初版（実装 v1.4.5 からの reverse-derived。ワークスペース新設に伴う逆起票）
