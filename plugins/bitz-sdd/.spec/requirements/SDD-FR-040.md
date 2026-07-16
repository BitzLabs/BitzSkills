---
id: SDD-FR-040
version: 1.0
status: verified
domain: upstream
priority: high
origin: skills/sdd-data/SKILL.md v0.1.0（reverse-derived）
verification_method: example-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### SDD-FR-040 論理データモデル仕様の同期展開

- **説明**: プロジェクトのデータモデル仕様を同期するため、`sdd_sync.py pull` は `.spec/design/data-model.md` 内のマスターファイルを対応する `docs/02-design/data-model.md` のナラティブファイルへコピーして同期しなければならない。本要件は公開契約に該当する。
- **受入基準 (EARS)**:
  - WHEN `python3 scripts/sdd_sync.py pull` が実行されたとき、かつ `.spec/design/data-model.md` が存在する場合 THEN システムはこれを `docs/02-design/data-model.md` にコピーして同期する SHALL
- **検証手段**: tests/test_sdd_sync.py
- **Revision History**:
  - 1.0 (2026-07-12) 初版（実装 v1.4.5 からの reverse-derived。ワークスペース新設に伴う逆起票）
  - 1.0 (2026-07-12) 人間裁定により approved 化（チャット指示）
