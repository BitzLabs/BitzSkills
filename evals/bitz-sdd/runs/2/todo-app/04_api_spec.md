# API仕様（REST / JSON）

ベースパス: `/api/tasks`

## 一覧取得
- `GET /api/tasks`
- クエリ: `?done=true|false`（省略時は全件）
- レスポンス 200:
```json
[
  { "id": 1, "title": "牛乳を買う", "description": null, "is_done": false,
    "created_at": "2026-07-10T09:00:00Z" }
]
```

## 追加
- `POST /api/tasks`
- リクエストボディ: `{ "title": "牛乳を買う", "description": "低脂肪" }`
- 検証: `title` は必須・空文字不可
- レスポンス 201: 作成されたタスクのJSON
- レスポンス 400: バリデーションエラー時 `{ "error": "title is required" }`

## 完了状態の切り替え
- `PATCH /api/tasks/:id`
- リクエストボディ: `{ "is_done": true }`
- レスポンス 200: 更新後のタスクJSON
- レスポンス 404: 該当タスクが存在しない場合

## 削除
- `DELETE /api/tasks/:id`
- レスポンス 204: 成功時（本文なし）
- レスポンス 404: 該当タスクが存在しない場合

## エラーレスポンス共通形式
```json
{ "error": "説明メッセージ" }
```
