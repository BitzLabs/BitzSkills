---
id: DSN-000
title: "設計作業台帳"
status: draft
version: 1.0
updated: YYYY-MM-DD
owner:
---

# 設計作業台帳（.spec/design/worksheet.md にコピーして使う）

短命の作業成果物。人間向けの結論は docs/02-design/ の proposed ドラフトへ落とし、この台帳は feature 完了時にアーカイブされる。

## CRUD マトリクス（Pass 2 用）

> bitz-ddd（`ddd-model`）導入時のみ記入。未導入（軽量デフォルト設計）ならこの節はスキップしてよい。

| 機能 \ エンティティ | <Ent1> | <Ent2> | … |
|---|---|---|---|
| <機能1> | CR | R | |

暗黙エンティティの追加記録（Pass 2）:

| 追加した概念 | 種別（中間/履歴/監査/状態機械） | 根拠（機能上の関係） |
|---|---|---|

## サブドメイン分類

> bitz-ddd（`ddd-model`）導入時のみ記入。未導入（軽量デフォルト設計）ならこの節はスキップしてよい。

| サブドメイン | 分類（Core/Supporting/Generic） | 投資判断 | 理由 |
|---|---|---|---|

## コンテキストマップ

> bitz-ddd（`ddd-model`）導入時のみ記入。未導入（軽量デフォルト設計）ならこの節はスキップしてよい。

| From | To | 関係型（ACL/OHS-PL/Shared Kernel/Customer-Supplier/Conformist/Partnership） | 備考 |
|---|---|---|---|

整合性ヒント:

| コンテキスト | Strong / Eventual / TBD | 理由（1行） |
|---|---|---|

## API 導出表

| API | 層（System/Process/Experience） | 依存（エンティティ/API） | 由来（機能/ジャーニー） |
|---|---|---|---|

## 技術適合性マトリクス

| 候補技術 | カテゴリ | 適合性（High/Med/Low/None） | 根拠シグナル（設計要素/要件を引用） | 判断（Adopt/Conditional/Reject） | 条件/リスク |
|---|---|---|---|---|---|

## Open Questions / TBD

- [ ] <未決事項と、誰が/いつ決めるか>
