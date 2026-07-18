---
id: SDD-FR-101
version: 1.0
status: deprecated
domain: sync
priority: medium
origin: skills/sdd-docs/SKILL.md v0.3.0（reverse-derived）
verification_method: example-test
derived_from:
supersedes:
superseded_by: SDD-FR-127
confidence: high
---

### SDD-FR-101 個別ストーリーファイルからストーリードキュメントへの Pull 集約

- **説明**: `sdd_sync.py` は `pull` 実行時に、個別ドメインストーリーファイルを集約して1つのストーリードキュメントを生成し、その際メタデータとなる frontmatter を除去しなければならない。本要件は公開契約に該当する。
- **受入基準 (EARS)**:
  - WHEN `sdd_sync.py pull` が実行された THEN システムは `.spec/design/stories/` 配下の個別ファイルを自動集約し `docs/02-design/domain-story.md` に展開する SHALL
  - WHEN 個別ストーリーファイルの集約を行う THEN システムは個別ファイルから frontmatter を除去する SHALL
- **検証手段**: tests/test_sdd_sync.py
- **Revision History**:
  - 1.0 (2026-07-12) 初版（実装 v1.4.5 からの reverse-derived。ワークスペース新設に伴う逆起票）
  - 1.0 (2026-07-12) 人間裁定により approved 化（チャット指示）
  - 1.0 (2026-07-18) 日本語章への後継 SDD-FR-127 がgreenとなり、人間裁定でdeprecated化
