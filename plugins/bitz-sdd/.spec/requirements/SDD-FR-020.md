---
id: SDD-FR-020
version: 1.0
status: verified
domain: upstream
priority: high
origin: skills/sdd-discovery/SKILL.md v0.2.2（reverse-derived）
verification_method: example-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### SDD-FR-020 上流探索マスターファイルの同期展開

- **説明**: プロジェクトの上流探索ドキュメントを同期するため、`sdd_sync.py pull` は `.spec/discovery/` 内のマスターファイルを対応する `docs/01-context/` のナラティブファイルへコピーして同期しなければならない。本要件は公開契約に該当する。
- **受入基準 (EARS)**:
  - WHEN `python3 scripts/sdd_sync.py pull` が実行されたとき、かつ `.spec/discovery/` 配下のファイルが `docs/01-context/` の対応するファイルより新しいか docs 側に存在しない場合 THEN システムは `.spec/` 側の内容で `docs/` 側のファイルを上書きまたは新規作成する SHALL
  - WHEN `python3 scripts/sdd_sync.py pull` が実行されたとき、かつ `docs/01-context/` のファイルが `.spec/discovery/` の対応するファイルより新しい場合 THEN システムは `docs/` 側のファイルを上書きしない SHALL
- **検証手段**: tests/test_sdd_sync.py
- **Revision History**:
  - 1.0 (2026-07-12) 初版（実装 v1.4.5 からの reverse-derived。ワークスペース新設に伴う逆起票）
  - 1.0 (2026-07-12) 人間裁定により approved 化（チャット指示）
