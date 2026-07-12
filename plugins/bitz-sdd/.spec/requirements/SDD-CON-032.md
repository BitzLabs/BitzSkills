---
id: SDD-CON-032
version: 1.0
status: approved
domain: upstream
priority: high
origin: skills/sdd-design/SKILL.md v0.4.1（reverse-derived）
verification_method: manual-check
derived_from:
supersedes:
superseded_by:
confidence: high
---

### SDD-CON-032 設計成果物のマスター配置先およびID/Frontmatter制約

- **説明**: 設計成果物の追跡可能性と一貫性を担保するため、すべての設計成果物は指定されたマスター配置先に作成され、特定のID体系とフロントマターを付与されなければならない。
- **受入基準 (EARS)**:
  - WHEN 設計工程の成果物を作成または更新するとき THEN 開発者またはシステムは `.spec/design/` 配下にマスターファイルを直接作成し、かつ各マスターファイルに `DSN-NNN` の形式のIDおよび共通のYAML frontmatterを付与する SHALL
  - WHEN 設計中に要件の矛盾や追加要件を検出したとき THEN 開発者またはシステムは `.spec/spec-issues/` に問題票を起票する SHALL
- **検証手段**: SKILL.md / references の目視確認 + skill-validator チェックリスト
- **Revision History**:
  - 1.0 (2026-07-12) 初版（実装 v1.4.5 からの reverse-derived。ワークスペース新設に伴う逆起票）
  - 1.0 (2026-07-12) 人間裁定により approved 化（チャット指示）
