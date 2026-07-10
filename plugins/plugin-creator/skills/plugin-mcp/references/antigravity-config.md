# Antigravity 2.0 での MCP 設定

### Antigravity 2.0 での設定

Antigravity はプラグイン**ルート直下の `mcp_config.json`** を読む
（`.mcp.json` とマニフェストの `mcpServers` は検出されない）。
グローバル設定は `~/.gemini/config/mcp_config.json`。

```json
{
  "mcpServers": {
    "database-tools": {
      "command": "./servers/db-server",
      "args": ["--config", "./config.json"],
      "env": { "DB_URL": "${DB_URL}" }
    },
    "remote-service": { "serverUrl": "https://mcp.mycompany.com/sse" }
  }
}
```

- 対応トランスポートは **stdio**（`command` / `args` / `env`）と
  **SSE**（`serverUrl`）の2種のみ。`type: http` / `ws` はない
- `${CLAUDE_PLUGIN_ROOT}` はないため、パスは相対または絶対で書く
- 両対応プラグインは `.mcp.json`（Claude Code 用）と `mcp_config.json`
  （Antigravity 用）を両方置く。SSE サーバーなら中身はほぼ共通化できる
  （Claude Code は `type: "sse"` + `url`、Antigravity は `serverUrl` と
  キー名が異なる点に注意）

