# MCPサーバー種別の詳細

Claude Code プラグインが対応する全MCPサーバー種別の詳細リファレンス。

## stdio（標準入出力）

### 概要

ローカルのMCPサーバーを子プロセスとして起動し、stdin/stdout で通信する。
ローカルツール・自作サーバー・npmパッケージに最適。

### 設定

```json
{
  "my-server": {
    "command": "${CLAUDE_PLUGIN_ROOT}/servers/custom-server",
    "args": ["--config", "${CLAUDE_PLUGIN_ROOT}/config.json"],
    "env": {
      "API_KEY": "${MY_API_KEY}",
      "LOG_LEVEL": "debug",
      "DATABASE_URL": "${DB_URL}"
    }
  }
}
```

### プロセスライフサイクル

1. **起動**: `command` と `args` でプロセス生成
2. **通信**: stdin/stdout 経由の JSON-RPC メッセージ
3. **稼働**: Claude Code セッションの間ずっと動く
4. **終了**: Claude Code 終了時にプロセスも終了

### ユースケース

```json
// npmパッケージ
{ "filesystem": { "command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path"] } }

// 自作スクリプト
{ "custom": { "command": "${CLAUDE_PLUGIN_ROOT}/servers/my-server.js", "args": ["--verbose"] } }

// Pythonサーバー
{ "python-server": { "command": "python", "args": ["-m", "my_mcp_server"], "env": { "PYTHONUNBUFFERED": "1" } } }
```

### ベストプラクティス

1. 絶対パスまたは `${CLAUDE_PLUGIN_ROOT}` を使う
2. Pythonサーバーには `PYTHONUNBUFFERED=1` を設定する
3. 設定は args か env で渡す（stdin ではない）
4. サーバークラッシュに丁寧に対処する
5. **ログは stderr に出す**（stdout は MCP プロトコル専用）

### トラブルシューティング

- **起動しない**: コマンドの存在と実行権限・パス・`claude --debug` のログを確認
- **通信失敗**: stdout への余計な print / console.log がないか、
  JSON-RPC 形式が正しいかを確認

## SSE（Server-Sent Events）

### 概要

HTTP + SSE でホスト型MCPサーバーに接続する。クラウドサービスと
OAuth認証に最適。

### 設定

```json
{
  "service": {
    "type": "sse",
    "url": "https://mcp.example.com/sse",
    "headers": {
      "X-API-Version": "v1",
      "X-Client-ID": "${CLIENT_ID}"
    }
  }
}
```

### 接続ライフサイクル

1. URL へのHTTP接続確立 → 2. MCPプロトコルのネゴシエーション →
3. SSE によるサーバーからのイベント配信 → 4. ツール呼び出しは HTTP POST →
5. 切断時は自動再接続

### 認証

**OAuth（自動）**: URL を指定するだけで Claude Code が OAuth フローを処理。
初回使用時にブラウザで認証し、トークンは安全に保存・自動更新される。

**カスタムヘッダー**: `"Authorization": "Bearer ${API_TOKEN}"` も指定可能。

### ベストプラクティス

1. 必ず HTTPS を使う
2. 使えるなら OAuth に認証を任せる
3. トークンは環境変数で渡す
4. 接続失敗に丁寧に対処する
5. 必要な OAuth スコープを文書化する

### トラブルシューティング

- **接続拒否**: URL・HTTPS証明書・ネットワーク・ファイアウォールを確認
- **OAuth失敗**: キャッシュされたトークンのクリア・スコープ・
  リダイレクトURLを確認して再認証

## HTTP（REST API）

### 概要

標準的なHTTPリクエストでRESTfulなMCPサーバーに接続する。
トークン認証・ステートレスなやり取りに最適。

### 設定

```json
{
  "api": {
    "type": "http",
    "url": "https://api.example.com/mcp",
    "headers": {
      "Authorization": "Bearer ${API_TOKEN}",
      "Content-Type": "application/json",
      "X-API-Version": "2024-01-01"
    }
  }
}
```

### リクエスト/レスポンスの流れ

1. **ツール発見**: GET で利用可能なツールを発見
2. **ツール呼び出し**: ツール名とパラメータで POST
3. **レスポンス**: 結果またはエラーの JSON
4. **ステートレス**: 各リクエストは独立

### 認証のバリエーション

```json
{ "headers": { "Authorization": "Bearer ${API_TOKEN}" } }  // Bearerトークン
{ "headers": { "X-API-Key": "${API_KEY}" } }                // APIキー
{ "headers": { "X-Auth-Token": "${AUTH_TOKEN}", "X-User-ID": "${USER_ID}" } }  // カスタム
```

### トラブルシューティング

| HTTPエラー | 確認事項 |
| --- | --- |
| 401 | 認証ヘッダー |
| 403 | 権限 |
| 429 | レート制限への対応 |
| 500 | サーバーログ |

## WebSocket（リアルタイム）

### 概要

WebSocket でリアルタイムの双方向通信を行う。ストリーミング・
低レイテンシ用途に最適。

### 設定

```json
{
  "realtime": {
    "type": "ws",
    "url": "wss://mcp.example.com/ws",
    "headers": {
      "Authorization": "Bearer ${TOKEN}",
      "X-Client-ID": "${CLIENT_ID}"
    }
  }
}
```

### 接続ライフサイクル

WebSocket アップグレード → 永続双方向チャネル → JSON-RPC over WebSocket →
ハートビート（keep-alive） → 切断時の自動再接続。

### ベストプラクティス

1. 必ず WSS を使う（WS は不可）
2. ハートビート/ping-pong を実装する
3. 再接続ロジックを持つ
4. 切断中のメッセージをバッファする
5. 接続タイムアウトを設定する

## 比較表

| 項目 | stdio | SSE | HTTP | WebSocket |
| --- | --- | --- | --- | --- |
| 通信 | プロセス | HTTP/SSE | HTTP | WebSocket |
| 方向 | 双方向 | サーバー→クライアント | 要求/応答 | 双方向 |
| 状態 | ステートフル | ステートフル | ステートレス | ステートフル |
| 認証 | 環境変数 | OAuth/ヘッダー | ヘッダー | ヘッダー |
| 用途 | ローカルツール | クラウドサービス | REST API | リアルタイム |
| レイテンシ | 最小 | 中 | 中 | 低 |
| 再接続 | プロセス再起動 | 自動 | 不要 | 自動 |

## 種別の選び方

- **stdio**: ローカル・自作・プラグイン同梱のサーバー。最小レイテンシ。
  ファイルシステム・ローカルDB
- **SSE**: ホスト型サービス。OAuth。公式サーバー（Asana, GitHub）。自動再接続
- **HTTP**: REST API 統合。ステートレス。トークン認証。単純な要求/応答
- **WebSocket**: リアルタイム更新。協調機能。低レイテンシ必須。双方向ストリーミング

## 発展的な設定

### 複数サーバーの組み合わせ

```json
{
  "local-db": {
    "command": "npx",
    "args": ["-y", "mcp-server-sqlite", "./data.db"]
  },
  "cloud-api": {
    "type": "sse",
    "url": "https://mcp.example.com/sse"
  },
  "internal-service": {
    "type": "http",
    "url": "https://api.example.com/mcp",
    "headers": { "Authorization": "Bearer ${API_TOKEN}" }
  }
}
```

### 環境変数によるサーバー切り替え

```json
{
  "api": {
    "type": "http",
    "url": "${API_URL}",
    "headers": { "Authorization": "Bearer ${API_TOKEN}" }
  }
}
```

開発: `API_URL=http://localhost:8080/mcp` /
本番: `API_URL=https://api.production.com/mcp`

## セキュリティ

- **stdio**: コマンドパスを検証する。ユーザー提供のコマンドを実行しない。
  環境変数・ファイルシステムへのアクセスを制限する
- **ネットワーク**: 常に HTTPS/WSS。SSL証明書の検証をスキップしない
- **トークン**: ハードコードしない。環境変数を使う。定期的にローテートする。
  必要なスコープを文書化する
