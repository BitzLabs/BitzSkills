---
id: <PREFIX>-000               # プレフィックス: DSC(Discovery), DSN(Design), INF(Infra), REV(Review)
title: "<人間が判読可能なタイトル>"
status: draft                  # draft | in-review | active | revised | archived
version: 1.0                   # 意味的バージョン
updated: YYYY-MM-DD            # ISO 8601
owner: <担当者ハンドル>
---

# BitzSDD Artifact Frontmatter 共通仕様

BitzSDDの `.spec/` 内のファイル（Requirementsを除く）は、一貫したトレーサビリティと機械的検証を可能にするため、上記のYAML frontmatterを必須とします。

## プレフィックス規約

| 領域 | プレフィックス | 備考 |
|---|---|---|
| Discovery | `DSC` | ビジョン、スコープ、仮説などの成果物 |
| Design | `DSN` | ドメインモデル、API設計、ストーリーなどの成果物 |
| Infra | `INF` | インフラ構成、セキュリティ、DR設計などの成果物 |
| Review | `REV` | レビューの統合レポート |
| Tasks | `TSK` | 実行タスク |

*Requirements (`FR`, `NFR`, `CON`) は独自のより詳細なfrontmatterを持つため、この共通仕様の対象外ですが、ID体系の規律は共有します。*
