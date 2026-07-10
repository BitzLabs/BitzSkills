---
id: CORE-CON-006
version: 1.0
status: draft
domain: governance
priority: high
origin: AGENTS.md（リポジトリ共通規約からの reverse-derived）
verification_method: example-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### CORE-CON-006 コミット・PR タイトルの Conventional Commits 準拠

- **説明**: コミットタイトルと PR タイトル（squash merge によりマージコミットのタイトルになる）は Conventional Commits に従う（AGENTS.md コミット・PR 規約）。
- **受入基準 (EARS)**:
  - WHEN PR を作成・更新する THEN CI は タイトルの Conventional Commits 準拠を検査し非準拠を FAIL に SHALL
- **検証手段**: .github/workflows/ci.yml の pr-title ジョブ
- **Revision History**:
  - 1.0 (2026-07-11) 初版（AGENTS.md の既存規約を要件化）
