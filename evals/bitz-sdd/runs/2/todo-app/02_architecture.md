# アーキテクチャ設計

## 全体構成（MVC 3層）

```
[ブラウザ (View)]
      │ HTTP(JSON)
      ▼
[サーバー (Controller/Model)]  -- Node.js + Express を想定
      │ SQL
      ▼
[データベース (SQLite/PostgreSQL)]
```

## レイヤー責務
- View: タスク一覧・追加フォーム・完了チェックボックスを持つSPA的な画面。
  サーバーのREST APIをfetchで呼び出す。
- Controller: HTTPリクエストを受け取り、入力検証をしてModelに委譲、
  結果をJSONで返す。ルーティングは `/api/tasks` 配下に集約。
- Model: タスクのCRUDロジックとDBアクセス（ORMまたは素のSQL）を担当。

## ディレクトリ構成案
```
server/
  controllers/task_controller.js
  models/task_model.js
  routes/task_routes.js
  db/schema.sql
public/ (or client/)
  index.html
  app.js
  style.css
```

## 技術選定理由
- 個人用・小規模なので軽量なSQLiteをデフォルトとし、環境変数でPostgreSQLへ切替可能にする。
- フロントは追加のビルドチェーンを避けるため、素のHTML/JSでも成立する構成にする
  （React等は将来の拡張として選択肢に残す）。
