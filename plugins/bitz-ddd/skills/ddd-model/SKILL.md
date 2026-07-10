---
name: ddd-model
description: BitzDDD — DDD の戦略設計・戦術設計（Entity / Value Object / Aggregate、Bounded Context（境界づけられたコンテキスト）、2パス導出）でドメインモデルを確立し、.spec/design/domain-model.md を作成する設計手法スキル。ユーザーが「ドメインモデル」「DDD」「集約」「境界づけられたコンテキスト」「エンティティ設計」に言及したとき、または ddd-story のストーリー完成後にモデル化へ進むときに使用する。bitz-sdd プラグインとの併用が前提。
metadata:
  version: "0.1.0"
  author: br7.hide
  created: "2026-07-10"
  updated: "2026-07-10"
---

# DDD Model — ドメインモデリング（戦略設計 + 2パス導出）

ドメインストーリー等の上流成果物からドメインモデルを導出します。
**ドメインをモデル化する。DB スキーマをモデル化しない**（ストレージはモデルに従わせる）。

## 前提（bitz-sdd との契約）

*   本スキルは **bitz-sdd プラグインとの併用が前提**です。成果物は `.spec/design/domain-model.md` に書き込みます。
*   frontmatter 書式は bitz-sdd の `sdd-core` スキルにある assets/artifact-frontmatter.md（公開契約）に従い、ID は `DSN-NNN` 体系を使います。
*   上流にドメインストーリーがあれば（`ddd-story` の成果物）、それを Pass 1 の第一の入力にします。

## 実行手順

1.  手法の詳細は `references/domain-modeling.md` を読みます。Entity / Value Object / Aggregate の判断基準と「トランザクション境界 = 集約境界」の規律に従います。
2.  **2パス導出は必須**: Pass 1（上流成果物からの明示的導出）→ Pass 2（機能×エンティティの CRUD マトリクスによる暗黙概念の洗い出し。追加要素には根拠を必ず記録）。
3.  作成後は bitz-sdd 側の工程に戻ります: `sdd-design` の API・アーキテクチャ設計へ進み、`sdd-docs` の pull で `docs/02-design/domain-model.md` に同期されます。
