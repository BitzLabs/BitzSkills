---
name: sdd-data
description: BitzSDD のデータ格納設計を行うスキル。論理データモデル（ER 図）→格納方式の選定（RDB / NoSQL / ファイル / オブジェクトストレージ / キャッシュ）→物理スキーマ・ファイル形式（JSON / CSV / Parquet 等）→永続化戦略（トランザクション境界・整合性）→マイグレーション計画を確立し、成果物を .spec/design/ に作成する。ユーザーが「データ設計」「DB 設計」「ER 図」「スキーマ設計」「テーブル設計」「データ移行」「格納方式」「永続化」に言及したとき、または設計工程で永続データを扱うシステムだと判明したときに使用する。データを永続化しないシステムでは不要（必須工程ではない）。
metadata:
  version: "1.0.0"
  author: br7.hide
  created: "2026-07-11"
  updated: "2026-07-18"
---

# SDD Data — データ格納設計

MVC + Database 型をはじめ、永続データを扱うシステムのデータ格納設計を担当します。
守備範囲は DB に限らず、ファイル形式・オブジェクトストレージを含む**データ格納設計全般**です。
データを永続化しないシステムではこの工程をスキップしてください（必須ステップではない）。

## 前提

*   ドメインモデル（`.spec/design/domain-model.md`）が先にあること。**ストレージはドメインモデルに従わせる**（逆ではない）。
*   成果物は `.spec/design/` 配下に作成し、frontmatter は `sdd-core` の assets/artifact-frontmatter.md（公開契約）に従う（ID は `DSN-NNN`）。

## 設計ステップと references

| # | ステップ | reference | 成果物（マスター） |
|---|---|---|---|
| 1 | 論理データモデル（ER 図・エンティティ整合性） | `references/data-modeling.md` | `.spec/design/data-model.md` |
| 2 | 格納方式の選定（証拠駆動の適合性評価） | `references/storage-selection.md` | `.spec/design/data-storage.md` |
| 3 | ファイル・交換形式の設計（該当時のみ） | `references/format-design.md` | 同上（形式スキーマ節） |
| 4 | 永続化戦略（トランザクション境界・整合性） | `references/data-modeling.md` + `storage-selection.md` | `.spec/design/data-model.md`（戦略節） |
| 5 | マイグレーション計画（スキーマ変更・データ移行） | `references/migration.md` | `.spec/design/data-storage.md`（移行節） |

## 工程内での位置づけ

*   `sdd-design`（ドメイン・API・アーキテクチャ）の後、`sdd-ops`（インフラ・運用設計）の前に実施する。
*   トランザクション境界は ddd-model（bitz-ddd 導入時）の集約境界と一致させる。未導入時はドメインモデルのエンティティ関係から導く。
*   完了したら `sdd-review` の多観点レビュー対象に含める（data-integrity 観点が `.spec/design/data-model.md` を走査する）。
*   `python3 scripts/sdd_sync.py pull` で `.spec/design/data-model.md` が `docs/03_設計仕様/データモデル.md` へ同期される（data-storage.md は短命の実装詳細のため同期しない）。
