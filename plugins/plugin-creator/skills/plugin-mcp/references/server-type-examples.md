# MCP サーバー種別の詳細と設定例

## サーバー種別

| 種別 | 通信 | 適する用途 | 認証 | 対応 |
| --- | --- | --- | --- | --- |
| stdio | 子プロセス | ローカルツール・自作サーバー | 環境変数 | 両方 |
| SSE | HTTP | ホスト型サービス・クラウドAPI | OAuth | 両方 |
| HTTP | REST | APIバックエンド | トークン | Claude Code のみ |
| ws | WebSocket | リアルタイム・ストリーミング | トークン | Claude Code のみ |

### stdio（ローカルプロセス）

```json
{
  "filesystem": {
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-filesystem", "/allowed/path"],
    "env": { "LOG_LEVEL": "debug" }
  }
}
```

Claude Code がプロセスを起動・管理し、stdin/stdout で通信する。
終了時にプロセスも終了する。ファイルシステムアクセス・ローカルDB・
自作サーバー・npmパッケージ型サーバーに向く。

### SSE（Server-Sent Events）

```json
{
  "asana": {
    "type": "sse",
    "url": "https://mcp.asana.com/sse"
  }
}
```

公式ホスト型サーバー（Asana, GitHub 等）向け。OAuth フローは自動処理され、
初回使用時にユーザーがブラウザで認証する。ローカルインストール不要。

### HTTP（REST API）

```json
{
  "api-service": {
    "type": "http",
    "url": "https://api.example.com/mcp",
    "headers": {
      "Authorization": "Bearer ${API_TOKEN}"
    }
  }
}
```

トークン認証のRESTベースサーバー・ステートレスなやり取りに向く。

### WebSocket（リアルタイム）

```json
{
  "realtime-service": {
    "type": "ws",
    "url": "wss://mcp.example.com/ws",
    "headers": { "Authorization": "Bearer ${TOKEN}" }
  }
}
```

リアルタイムのデータストリーミング・永続接続・低レイテンシ要件に向く。

