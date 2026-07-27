---
id: CORE-FR-017
version: 1.0
status: verified
domain: tooling
priority: medium
origin: SI-CORE-030
verification_method: example-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### CORE-FR-017 sdd-docs docs_inspect の適用境界と資料除外設定

- **説明**: ルート `docs/` に使い方ガイド、過去計画、3プラットフォーム調査、外部資料保全が含まれる一方、`sdd-docs` の `docs_inspect.py` は `docs/` 全体を SDD 管理対象ナラティブとみなすため、正規検査時に不要なエラーが大量発生する。SDD ナラティブとして管理・検証する境界（`docs/01-context/` 等）と、除外・保全対象とする範囲を明示的かつ機械的に設定できるようにする。
- **受入基準 (EARS)**:
  - THEN `docs/` 内の SDD ナラティブ管理対象範囲（`00_はじめに` 〜 `05_リリース・運用` または `01-context/` 等）と、調査報告・外部保全等の検査除外範囲を明示的に宣言できる構造または設定契約が定義されること SHALL
  - WHEN `docs_inspect.py` を実行する THEN 除外宣言されたパスおよび資料群が `FM_ABSENT` / `REG_ORPHAN` などのエラーとして検出されず、管理対象範囲の文書健全性を独立して検証できること SHALL
  - THEN 除外設定の記述またはリポジトリ上の構成ファイルは監査可能であり、暗黙的なハードコード回避が行われること SHALL
  - WHEN `python3 scripts/release_check.py` または `python3 scripts/spec inspect --workspace . plugins/*` を実行する THEN 既存の検証ルールとの互換性が保たれ、すべてのチェックが PASS すること SHALL
- **検証手段**: `docs_inspect.py` に対して除外設定および対照テストケースを与え、除外パスがエラーとして集計されず管理対象パスのエラーのみが正しく検証されることを確認する（example-test）。
- **Revision History**:
  - 1.0 (2026-07-27) 初版（SI-CORE-030 承認に基づき draft 起票）
