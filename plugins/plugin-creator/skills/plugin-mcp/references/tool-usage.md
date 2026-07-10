# コマンド・エージェントでのMCPツール利用

MCPサーバー設定後、そのツールを効果的に使うためのガイド。

## 概要

設定済みMCPサーバーのツールは
`mcp__plugin_<plugin-name>_<server-name>__<tool-name>` という名前で
利用可能になり、組み込みツールと同じようにコマンド・エージェントから使える。

## ツール命名規則

```
mcp__plugin_<plugin-name>_<server-name>__<tool-name>
```

**例（asana プラグイン + asana サーバー）:**

- `mcp__plugin_asana_asana__asana_create_task`
- `mcp__plugin_asana_asana__asana_search_tasks`

**例（自作プラグイン + database サーバー）:**

- `mcp__plugin_myplug_database__query`
- `mcp__plugin_myplug_database__list_tables`

### ツール名の調べ方

`/mcp` コマンドで、全MCPサーバー・各サーバーのツール・スキーマと説明・
設定に使う完全なツール名を確認できる。

## コマンドでの利用

### ツールの事前許可

```markdown
---
description: 新しいAsanaタスクを作成する
allowed-tools: [
  "mcp__plugin_asana_asana__asana_create_task"
]
---

# タスク作成コマンド

1. ユーザーからタスクの詳細を集める
2. mcp__plugin_asana_asana__asana_create_task を詳細付きで使う
3. 作成をユーザーに確認する
```

複数ツールは配列で列挙する。ワイルドカード
（`"mcp__plugin_asana_asana__*"`）は、本当に全ツールが必要な場合のみ使う。

### コマンド本文での指示例

```markdown
---
description: Asanaタスクの検索と作成
allowed-tools: [
  "mcp__plugin_asana_asana__asana_search_tasks",
  "mcp__plugin_asana_asana__asana_create_task"
]
---

# Asanaタスク管理

## タスク検索

1. mcp__plugin_asana_asana__asana_search_tasks を使う
2. 検索フィルタ（担当者・プロジェクト等）を渡す
3. 結果をユーザーに表示する

## タスク作成

1. タスク詳細（タイトル[必須]・説明・プロジェクト・担当者・期限）を集める
2. mcp__plugin_asana_asana__asana_create_task を使う
3. タスクリンク付きで確認を表示する
```

## エージェントでの利用

エージェントは事前許可なしにMCPツールを自律的に使える:

```markdown
---
name: asana-status-updater
description: 「Asanaのステータスを更新して」「プロジェクトレポートを作って」「Asanaタスクを同期して」と言われたときにこのエージェントを使用する
model: inherit
color: blue
---

## 役割

Asanaプロジェクトのステータスレポートを生成する自律エージェント。

## プロセス

1. **タスク照会**: mcp__plugin_asana_asana__asana_search_tasks で全タスクを取得する
2. **進捗分析**: 完了率を計算しブロッカーを特定する
3. **レポート生成**: 整形されたステータス更新を作成する
4. **Asana更新**: mcp__plugin_asana_asana__asana_create_comment でレポートを投稿する
```

エージェントはコマンドより広いツールアクセスを持つが、
典型的に使うツールをシステムプロンプトに文書化しておく。

## ツール呼び出しパターン

1. **単発呼び出し**: 入力検証 → 呼び出し → エラー確認 → 確認表示
2. **順次連鎖**: 検索 → なければ作成 → メタデータ追加 → ID を返す
3. **バッチ処理**: 対象リスト取得 → 各アイテムに同じツールを適用 →
   成否を記録 → サマリー報告
4. **エラー処理**: 呼び出し失敗（レート制限・ネットワーク等）→
   最大3回リトライ → だめならユーザーに通知し設定確認を提案

## ツールパラメータ

各ツールにはパラメータを定義したスキーマがある（`/mcp` で確認）:

```json
{
  "name": "asana_create_task",
  "description": "新しいAsanaタスクを作成する",
  "inputSchema": {
    "type": "object",
    "properties": {
      "name": { "type": "string", "description": "タスクのタイトル" },
      "notes": { "type": "string", "description": "タスクの説明" },
      "workspace": { "type": "string", "description": "ワークスペースGID" }
    },
    "required": ["name", "workspace"]
  }
}
```

**コマンドでは呼び出し前に検証する**: 必須パラメータの有無・
日付形式などをチェックし、不足があればユーザーに確認してから
ツールを呼ぶ。

## レスポンス処理

- **成功**: レスポンスから必要なデータを抽出し、ユーザー向けに整形して
  リンクやIDを添えて確認を出す
- **エラー**: エラー種別（認証・レート制限・検証等）を判定し、役立つ
  メッセージと対処法を提示する。内部エラーの詳細をそのまま見せない
- **部分的成功**: 「10件中8件を処理。失敗: [item1, item2]（理由）」の
  ように成否を分けて報告し、リトライか手動対応を提案する

## パフォーマンス最適化

```markdown
# ✅ 良い: フィルタ付きの一括クエリ
mcp__plugin_api_server__search を filters（project_id, status, limit: 100）付きで1回呼ぶ

# ❌ 避ける: 個別クエリの繰り返し
各IDごとに mcp__plugin_api_server__get_item を呼ぶ
```

- **キャッシュ**: 高コストな操作の結果は保持して再利用する
- **並列呼び出し**: 依存のないツール呼び出しは並列に行う
  （project / users / tags を同時取得など）

## UXのベストプラクティス

- **フィードバックを出す**: 「Asanaタスクを検索中...」→「15件見つかりました。
  分析中...」のように進捗を伝える
- **長い操作は予告する**: 「1分ほどかかります」と伝えて段階的に更新する
- **良いエラーメッセージ**:

```
✅ 「タスクを作成できませんでした。確認してください:
   1. Asanaにログインしているか
   2. ワークスペース 'Engineering' へのアクセス権があるか
   3. プロジェクト 'Q1 Goals' が存在するか」

❌ 「エラー: MCPツールが403を返しました」
```

- **使用ツールを文書化する**: コマンド内に「このコマンドが使うMCPツール」
  セクションを設け、事前認証の必要性を書く

## テスト

1. `.mcp.json` にサーバーを設定する
2. プラグインをローカルに導入する
3. `/mcp` でツールを確認する
4. ツールを使うコマンドをテストする
5. `claude --debug` の出力を確認する

**テストシナリオ**: 成功呼び出し（テストデータで検証）/
エラーケース（認証なし・無効パラメータ・存在しないリソース）/
エッジケース（空の結果・最大件数・特殊文字・同時アクセス）。

## よくあるパターン

### CRUD操作

```markdown
---
allowed-tools: [
  "mcp__plugin_api_server__create_item",
  "mcp__plugin_api_server__read_item",
  "mcp__plugin_api_server__update_item",
  "mcp__plugin_api_server__delete_item"
]
---

削除は必ずユーザーに確認してから delete_item を使う。
```

### 検索して処理

検索（フィルタ付き）→ 必要ならローカルで追加フィルタ → 各結果を変換 →
整形して表示。

### 多段ワークフロー

情報収集 → 完全性の検証 → ツール呼び出しの連鎖（親リソース作成 →
子リソース作成 → 関連付け → メタデータ追加）→ 全ステップの成功確認 →
サマリー報告。

## トラブルシューティング

- **ツールが出ない**: MCPサーバー設定・接続状態（`/mcp`）・ツール名の
  完全一致（大文字小文字区別）・設定変更後の再起動を確認
- **呼び出しが失敗する**: 認証の有効性・スキーマとのパラメータ整合・
  必須パラメータ・`claude --debug` のログを確認
- **性能問題**: バッチ化・キャッシュ・不要な呼び出しの削減・並列化を確認
