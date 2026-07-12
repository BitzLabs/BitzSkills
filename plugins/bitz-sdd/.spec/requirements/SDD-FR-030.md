---
id: SDD-FR-030
version: 1.0
status: draft
domain: upstream
priority: high
origin: skills/sdd-design/SKILL.md v0.4.1（reverse-derived）
verification_method: example-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### SDD-FR-030 ドメインストーリーの自動集約

- **説明**: 複数のドメインストーリーを一つのドキュメントに統合するため、`sdd_sync.py pull` は `.spec/design/stories/` 配下のファイル群をソート・結合して `docs/02-design/domain-story.md` に集約出力しなければならない。本要件は公開契約に該当する。
- **受入基準 (EARS)**:
  - WHEN `python3 scripts/sdd_sync.py pull` が実行されたとき、かつ `.spec/design/stories/` 配下に `story-*.md` の命名規則に従うファイル群が存在する場合 THEN システムはこれらのストーリーファイルをファイル名のアルファベット順にソートし、かつそれぞれの YAML frontmatter を除去した上で `docs/02-design/domain-story.md` に結合・集約して出力する SHALL
- **検証手段**: tests/test_sdd_sync.py
- **Revision History**:
  - 1.0 (2026-07-12) 初版（実装 v1.4.5 からの reverse-derived。ワークスペース新設に伴う逆起票）
