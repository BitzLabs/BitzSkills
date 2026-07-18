---
id: SDD-FR-127
version: 1.0
status: verified
domain: sync
priority: high
origin: SI-SDD-012
verification_method: unit-test
derived_from:
supersedes: SDD-FR-030
superseded_by:
confidence: high
---

### SDD-FR-127 日本語章へのドメインストーリー集約

- **説明**: 既存のドメインストーリー集約契約を日本語の設計章へ移し、ソートとfrontmatter除去を維持する。
- **受入基準 (EARS)**:
  - WHEN `sdd_sync.py pull` が実行され、`.spec/design/stories/story-*.md` が存在するとき THEN システムはファイル名順に本文を集約して `docs/03_設計仕様/ドメインストーリー.md` へ出力する SHALL
  - WHEN 個別ストーリーを集約するとき THEN システムは個別frontmatterを除去し、集約文書には日本語章と整合する機械frontmatterを付与する SHALL
- **検証手段**: `tests/test_sdd_sync.py` のストーリー集約unit-test。
- **Revision History**:
  - 1.0 (2026-07-18) 初版（draft 起票）
