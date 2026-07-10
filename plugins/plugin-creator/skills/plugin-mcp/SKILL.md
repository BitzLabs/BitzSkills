---
name: plugin-mcp
description: Claude Code / Antigravity 2.0 プラグインへのMCP（Model Context Protocol）サーバー統合を支援する。「MCPサーバーを追加したい」「MCPを統合したい」「.mcp.jsonの設定」「mcp_config.jsonの設定」「外部サービスと連携したい」と言われたときや、MCPサーバー種別（stdio, SSE, HTTP, WebSocket）・認証・MCPツールの使い方について指針が必要なときに使用する。
metadata:
  version: "0.4.0"
  author: br7.hide
  created: "2026-07-05"
  updated: "2026-07-11"
---

# plugin-mcp

## 目的

MCP（Model Context Protocol）により、プラグインは外部サービス・APIを
構造化されたツールとして統合できる。データベース・API・ファイルシステム
などの機能をエージェントのツールとして公開する。

**主な能力:** 外部サービスへの接続、1サービスから複数ツールの提供、
OAuth等の認証フローの処理、プラグインへのMCPサーバー同梱による自動セットアップ。

本文は Claude Code の設定方法。Antigravity 2.0 は設定ファイル名と
対応トランスポートが異なる（`references/antigravity-config.md` を参照）。

## 設定方法

### 方法1: 専用の .mcp.json（推奨）

プラグインルートに `.mcp.json` を作る:

```json
{
  "database-tools": {
    "command": "${CLAUDE_PLUGIN_ROOT}/servers/db-server",
    "args": ["--config", "${CLAUDE_PLUGIN_ROOT}/config.json"],
    "env": {
      "DB_URL": "${DB_URL}"
    }
  }
}
```

関心の分離が明確で保守しやすく、複数サーバーに向く。

### 方法2: plugin.json にインライン

```json
{
  "name": "my-plugin",
  "version": "1.0.0",
  "mcpServers": {
    "plugin-api": {
      "command": "${CLAUDE_PLUGIN_ROOT}/servers/api-server",
      "args": ["--port", "8080"]
    }
  }
}
```

設定ファイルが1つで済む。単一サーバーの単純なプラグイン向け。

Antigravity 2.0 での設定方法（`mcp_config.json`・対応トランスポート・
両対応プラグインの作り方）は `references/antigravity-config.md` を参照。

各サーバー種別（stdio / SSE / HTTP / WebSocket）の設定例は
`references/server-type-examples.md` を参照。

## 環境変数の展開

すべてのMCP設定は環境変数の置換をサポートする:

- **`${CLAUDE_PLUGIN_ROOT}`** — プラグインフォルダ（パスには必ずこれを使う）
- **ユーザーの環境変数** — `"API_KEY": "${MY_API_KEY}"` のようにシェルから渡す

必要な環境変数は必ずプラグインの README に文書化する。

## MCPツールの命名

MCPサーバーが提供するツールには自動でプレフィックスが付く:

**形式:** `mcp__plugin_<plugin-name>_<server-name>__<tool-name>`

例: プラグイン `asana`・サーバー `asana`・ツール `create_task`
→ `mcp__plugin_asana_asana__asana_create_task`

### コマンドでのMCPツール事前許可

```markdown
---
allowed-tools: [
  "mcp__plugin_asana_asana__asana_create_task",
  "mcp__plugin_asana_asana__asana_search_tasks"
]
---
```

ワイルドカード（`"mcp__plugin_asana_asana__*"`）はセキュリティ上
控えめに使い、具体的なツールを事前許可するのが原則。

## ライフサイクル

1. プラグイン読み込み → 2. MCP設定のパース → 3. サーバー起動（stdio）
または接続確立（SSE/HTTP/ws） → 4. ツールの発見と登録 →
5. `mcp__plugin_...__...` として利用可能に

設定変更には再起動が必要。`/mcp` コマンドでプラグイン提供分を含む
全サーバーを確認できる。

## 認証パターン

- **OAuth（SSE/HTTP）**: Claude Code が自動処理。初回使用時にブラウザで
  認証。追加設定不要
- **トークン（headers）**: `"Authorization": "Bearer ${API_TOKEN}"`。
  必要な環境変数を README に書く
- **環境変数（stdio）**: `env` フィールドでサーバーに設定を渡す

詳細は `references/authentication.md` を参照。

## 統合パターン

1. **シンプルなツールラッパー**: コマンドがユーザーと対話しつつ
   MCPツールを使う（呼び出し前の検証・前処理に向く）
2. **自律エージェント**: エージェントがMCPツールを自律的に使う
   （ユーザー対話なしの多段ワークフロー）
3. **複数サーバープラグイン**: GitHub + Jira のように複数サービスに
   またがるワークフロー

コマンド・エージェントからの使い方の詳細は `references/tool-usage.md` を参照。

## セキュリティ

- **HTTPS/WSS のみ**: `http://` `ws://` は使わない
- **トークン管理**: 環境変数を使い、設定にハードコードしない。
  gitにコミットしない。OAuthに任せられるものは任せる
- **権限の絞り込み**: 必要なMCPツールだけ事前許可する
  （ワイルドカードは避ける）

## エラー処理とパフォーマンス

- **接続失敗**: コマンドにフォールバック動作を用意し、接続問題を
  ユーザーに伝える
- **ツール呼び出しエラー**: 呼び出し前に入力を検証し、レート制限・
  クォータを考慮する
- **遅延接続**: サーバーは初回ツール使用時に接続される
- **バッチ化**: 個別クエリの繰り返しではなく、フィルタ付きの一括クエリを使う

MCPサーバーのテストとデバッグ手順・チェックリスト・よくある問題は
`references/testing-and-troubleshooting.md` を参照。

## 追加リソース

### リファレンス

- **`references/antigravity-config.md`** — Antigravity 2.0 でのMCP設定
- **`references/server-type-examples.md`** — 各サーバー種別の設定例
- **`references/testing-and-troubleshooting.md`** — テスト・デバッグ・よくある問題
- **`references/server-types.md`** — 各サーバー種別の詳細
- **`references/authentication.md`** — 認証パターンとOAuth
- **`references/tool-usage.md`** — コマンド・エージェントでのMCPツール利用

### 設定例

- **`examples/stdio-server.json`** — ローカルstdioサーバー
- **`examples/sse-server.json`** — OAuth付きホスト型SSEサーバー
- **`examples/http-server.json`** — トークン認証のREST API

### 外部リソース

- MCP公式: https://modelcontextprotocol.io/
- Claude Code MCPドキュメント: https://docs.claude.com/en/docs/claude-code/mcp

## 実装ワークフロー

1. サーバー種別を選ぶ（stdio / SSE / HTTP / ws）
2. プラグインルートに `.mcp.json` を作る
3. ファイル参照はすべて `${CLAUDE_PLUGIN_ROOT}` を使う
4. 必要な環境変数を README に文書化する
5. `/mcp` コマンドでローカルテストする
6. 関連コマンドでMCPツールを事前許可する
7. 認証（OAuthまたはトークン）を処理する
8. エラーケース（接続失敗・認証エラー）をテストする
9. プラグインの README にMCP統合を文書化する

自作・ローカルなら stdio、OAuth付きホスト型サービスなら SSE を基本とする。
