---
id: SDD-FR-128
version: 1.0
status: implementing
domain: sync
priority: high
origin: SI-SDD-012
verification_method: unit-test
derived_from:
supersedes: SDD-FR-040
superseded_by:
confidence: high
---

### SDD-FR-128 日本語章への設計・データ同期

- **説明**: 既存の設計・データ同期契約を日本語の設計章へ移し、双方向同期とmtime保護を維持する。
- **受入基準 (EARS)**:
  - WHEN `sdd_sync.py pull` または `push` が実行されたとき THEN システムは `domain-model.md`、`api-design.md`、`architecture.md`、`data-model.md` をそれぞれ `docs/03_設計仕様/ドメインモデル.md`、`公開API.md`、`アーキテクチャ.md`、`データモデル.md` と双方向同期する SHALL
  - IF 同期先または同期元の一方が新しいか等しい THEN システムはSDD-FR-100のmtime上書き制御を
    日本語パスでも維持する SHALL
- **検証手段**: `tests/test_sdd_sync.py` のpull / push / diff unit-test。
- **Revision History**:
  - 1.0 (2026-07-18) 初版（draft 起票）
