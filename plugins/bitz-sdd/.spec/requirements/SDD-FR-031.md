---
id: SDD-FR-031
version: 1.0
status: approved
domain: upstream
priority: medium
origin: skills/sdd-design/SKILL.md v0.4.1（reverse-derived）
verification_method: manual-check
derived_from:
supersedes:
superseded_by:
confidence: high
---

### SDD-FR-031 API設計における下向き非循環依存と層規制

- **説明**: APIの再利用性と保守性を最大化するため、API設計は Experience、Process、System の3層による関心分離および非循環な依存構造を維持しなければならない。
- **受入基準 (EARS)**:
  - WHEN API設計を定義するとき THEN 開発者は Experience層から Process層、Process層から System層への下向き非循環の依存関係を維持し、かつ System API を UI に対して直接公開しない SHALL
  - WHEN API設計を定義するとき THEN 開発者は各 API の層、名前、目的、依存関係、および OpenAPI スケッチ（主要パス、メソッド、リクエスト/レスポンス）を明記する SHALL
- **検証手段**: SKILL.md / references の目視確認 + skill-validator チェックリスト
- **Revision History**:
  - 1.0 (2026-07-12) 初版（実装 v1.4.5 からの reverse-derived。ワークスペース新設に伴う逆起票）
  - 1.0 (2026-07-12) 人間裁定により approved 化（チャット指示）
