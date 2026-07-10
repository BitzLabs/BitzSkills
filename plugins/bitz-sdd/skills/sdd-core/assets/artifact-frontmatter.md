---
id: <PREFIX>-000               # プレフィックス: DSC(Discovery), DSN(Design), INF(Infra), REV(Review)
title: "<人間が判読可能なタイトル>"
status: draft                  # draft | in-review | active | revised | archived
version: 1.0                   # 意味的バージョン
updated: YYYY-MM-DD            # ISO 8601
owner: <担当者ハンドル>
---

# BitzSDD Artifact Frontmatter 共通仕様（公開契約）

> **公開契約**: 本書式は、外部プラグイン（設計手法プロバイダ bitz-ddd など）が
> `.spec/` に成果物を書き込む際の公開仕様である。依存方向は
> 外部プラグイン → `.spec` → bitz-sdd の一方向で、bitz-sdd は外部プラグインを知らない。
> 本書式と `.spec/` のファイル配置に従う成果物は、書き手を問わず
> sdd-review / sdd-report / sdd-docs の処理対象として同一に扱われる。

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
