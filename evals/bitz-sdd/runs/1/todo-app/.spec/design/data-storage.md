---
id: DSN-003
title: "ToDo管理Webアプリ データ格納方式・移行計画"
status: draft
version: 1.0
updated: 2026-07-11
owner: br7.hide
---

# データ格納方式・物理スキーマ・移行計画

## 採用技術

- **RDB**: SQLite（ファイルベース、サーバー常駐プロセス不要。個人用MVCアプリに適合）
- 選定根拠は `.spec/design/data-model.md` の格納方式選定表を参照

## 物理スキーマ（DDL概要）

```sql
CREATE TABLE task_list (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL
);

CREATE TABLE task (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_list_id INTEGER NOT NULL REFERENCES task_list(id),
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'todo', -- 'todo' | 'done'
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME
);
```

## マイグレーション計画

- 初期リリースのため、マイグレーションは初回スキーマ作成のみ（`schema.sql` を起動時に適用）
- 将来 Should（削除）・Could（期日・優先度）機能を追加する際は、`ALTER TABLE task ADD COLUMN` による前方互換マイグレーションを想定

## 備考

- data-storage.md は短命の実装詳細のため `docs/` への同期対象外（sdd-data の連携ルールに従う）
