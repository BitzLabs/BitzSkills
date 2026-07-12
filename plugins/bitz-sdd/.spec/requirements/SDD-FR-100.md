---
id: SDD-FR-100
version: 1.0
status: draft
domain: sync
priority: high
origin: skills/sdd-docs/SKILL.md v0.3.0（reverse-derived）
verification_method: example-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### SDD-FR-100 双方向同期コマンドにおける mtime 比較による上書き制御

- **説明**: `.spec/` と `docs/` の間の双方向同期を行う `sdd_sync.py` は、ファイルの更新日時（mtime）を比較し、より新しい内容を保持するように同期および逆反映を制御しなければならない。本要件は公開契約に該当する。
- **受入基準 (EARS)**:
  - WHEN `sdd_sync.py pull` が実行された IF `.spec/` 側のソースファイルが `docs/` 側の同期先ファイルより新しい THEN システムは同期先ファイルを上書き更新する SHALL
  - WHEN `sdd_sync.py pull` が実行された IF `docs/` 側の同期先ファイルが `.spec/` 側のソースファイルより新しいか等しい THEN システムは同期先ファイルを上書きしない SHALL
  - WHEN `sdd_sync.py push` が実行された IF `docs/` 側の同期先ファイルが `.spec/` 側のソースファイルより新しい THEN システムはソースファイルへ逆反映（上書き）する SHALL
  - WHEN `sdd_sync.py push` が実行された IF `.spec/` 側のソースファイルが `docs/` 側の同期先ファイルより新しいか等しい THEN システムはソースファイルを更新しない SHALL
- **検証手段**: tests/test_sdd_sync.py
- **Revision History**:
  - 1.0 (2026-07-12) 初版（実装 v1.4.5 からの reverse-derived。ワークスペース新設に伴う逆起票）
