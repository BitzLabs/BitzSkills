---
id: SDD-FR-041
version: 1.0
status: verified
domain: upstream
priority: medium
origin: skills/sdd-data/SKILL.md v0.1.0（reverse-derived）
verification_method: example-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### SDD-FR-041 物理格納設計仕様の同期対象外化

- **説明**: 実装詳細である物理格納設計情報をドキュメント同期から保護するため、`sdd_sync.py pull` は `.spec/design/data-storage.md` を同期対象外としてスキップしなければならない。本要件は公開契約に該当する。
- **受入基準 (EARS)**:
  - WHEN `python3 scripts/sdd_sync.py pull` が実行されたとき THEN システムは `.spec/design/data-storage.md` のファイルを同期対象から除外し、`docs/` 配下にコピーしない SHALL
- **検証手段**: tests/test_sdd_sync.py
- **Revision History**:
  - 1.0 (2026-07-12) 初版（実装 v1.4.5 からの reverse-derived。ワークスペース新設に伴う逆起票）
  - 1.0 (2026-07-12) 人間裁定により approved 化（チャット指示）
