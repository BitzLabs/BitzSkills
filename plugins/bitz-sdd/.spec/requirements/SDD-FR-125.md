---
id: SDD-FR-125
version: 1.0
status: implementing
domain: sync
priority: high
origin: SI-SDD-012
verification_method: unit-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### SDD-FR-125 日本語6章文書構成と宣言式拡張

- **説明**: `sdd-docs` は、人間向け文書の正規レイアウトを日本語の必須6章とし、参照資料および
  管理対象外パスを `MASTER.md` で明示的に宣言できなければならない。`MASTER.md`、文書ID、
  frontmatterのキーと統制値は機械契約として英語を維持する。
- **受入基準 (EARS)**:
  - WHEN 標準テンプレートを展開したとき THEN システムは `00_はじめに`、`01_システム仕様`、`02_ユースケース`、`03_設計仕様`、`04_テスト仕様`、`05_リリース・運用` の6章を生成する SHALL
  - WHEN `docs_inspect.py --strict` が日本語6章の文書ツリーを検査したとき THEN システムは各章と英語の機械areaの対応、MASTERレジストリ、project_typeを決定的に検証する SHALL
  - WHILE `MASTER.md` が `optional_chapters: reference` を宣言している間 THE SYSTEM SHALL `06_リファレンス` を正規の任意章として許容し、宣言と実在が不一致ならエラーにする
  - WHILE `MASTER.md` が `excluded_paths` を宣言している間 THE SYSTEM SHALL 指定された調査・アーカイブ配下をfrontmatterおよびレジストリ検査の対象外にする
  - IF 旧英語8章または未宣言の番号章が混在する THEN システムは構造エラーとして報告する SHALL
- **検証手段**: `tests/test_docs_inspect.py` によるテンプレートstrict検査、任意章・除外パス・
  legacy混在のunit-test。
- **Revision History**:
  - 1.0 (2026-07-18) 初版（draft 起票）
