# データベース設計

## テーブル: tasks

| カラム名 | 型 | 制約 | 説明 |
|---|---|---|---|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | タスクID |
| title | TEXT | NOT NULL | タスクのタイトル |
| description | TEXT | NULL可 | 補足説明 |
| is_done | BOOLEAN | NOT NULL DEFAULT 0 | 完了フラグ |
| created_at | DATETIME | NOT NULL DEFAULT CURRENT_TIMESTAMP | 作成日時 |
| updated_at | DATETIME | NOT NULL DEFAULT CURRENT_TIMESTAMP | 更新日時 |

## DDL（SQLite想定）

```sql
CREATE TABLE tasks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  description TEXT,
  is_done BOOLEAN NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_tasks_is_done ON tasks (is_done);
```

## 拡張余地
- 将来ユーザー認証を追加する場合は `user_id INTEGER` を追加し、
  `users` テーブルへの外部キーとする想定。
- 期限管理を追加する場合は `due_date DATETIME` を追加する。
