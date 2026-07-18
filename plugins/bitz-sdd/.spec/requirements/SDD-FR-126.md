---
id: SDD-FR-126
version: 1.0
status: implementing
domain: sync
priority: high
origin: SI-SDD-012
verification_method: unit-test
derived_from:
supersedes: SDD-FR-020
superseded_by:
confidence: high
---

### SDD-FR-126 日本語章へのDiscovery同期

- **説明**: 既存のDiscovery同期契約を日本語6章へ移し、visionとscopeのmtime保護を維持する。
- **受入基準 (EARS)**:
  - WHEN `sdd_sync.py pull` が実行され、`.spec/discovery/vision.md` が同期対象となるとき THEN システムは `docs/00_はじめに/ミッション・ビジョン.md` へ展開する SHALL
  - WHEN `sdd_sync.py pull` が実行され、`.spec/discovery/scope.md` が同期対象となるとき THEN システムは `docs/00_はじめに/対象外.md` へ展開する SHALL
  - IF docs側の同期先がspec側より新しいか等しい THEN システムはdocs側を上書きしない SHALL
- **検証手段**: `tests/test_sdd_sync.py` のpull・mtime保護unit-test。
- **Revision History**:
  - 1.0 (2026-07-18) 初版（draft 起票）
