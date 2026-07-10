---
id: DSN-001
title: "ToDo管理Webアプリ ドメインモデル（軽量スケッチ）"
status: draft
version: 1.0
updated: 2026-07-11
owner: br7.hide
---

# ドメインモデル（軽量スケッチ）

> bitz-ddd 未導入のため、sdd-design の graceful degradation 分岐に従い、
> 主要エンティティと関係の一覧のみを記述する軽量スケッチとする。

## 主要エンティティ

| エンティティ | 属性 | 説明 |
|---|---|---|
| Task | id, title, status（未完了/完了）, createdAt, completedAt | 管理対象のタスク本体 |
| TaskList | id, name | タスクの一覧表示の単位（MVPでは単一の暗黙リスト） |

## 関係

- `TaskList` 1 -- 0..* `Task`（1つのリストが複数のタスクを保持する）

## 振る舞い（操作）

- タスクを追加する（Task を新規作成し status=未完了）
- タスクを完了にする（status を 完了 に遷移。completedAt を記録）
- タスク一覧を取得する（status によるフィルタは MVP では対象外、MoSCoW の Could）

## ギャップ・要根拠事項

- タスク削除（MoSCoW の Should）はエンティティ定義に含めるが、UIフローは未確定 → `.spec/spec-issues/` 起票候補
