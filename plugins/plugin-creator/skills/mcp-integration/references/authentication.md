# MCP認証パターン

Claude Code プラグインにおけるMCPサーバーの認証方式の完全ガイド。

## 概要

MCPサーバーは、サーバー種別とサービスの要件に応じて複数の認証方式を
サポートする。ユースケースとセキュリティ要件に合う方式を選ぶ。

## OAuth（自動）

### 仕組み

SSE / HTTP サーバーでは Claude Code が OAuth 2.0 フロー全体を自動処理する:

1. ユーザーがMCPツールを使おうとする
2. Claude Code が認証の必要性を検出する
3. ブラウザで OAuth 同意画面を開く
4. ユーザーがブラウザで認可する
5. トークンは Claude Code が安全に保存する
6. トークンは自動更新される

### 設定

```json
{
  "service": {
    "type": "sse",
    "url": "https://mcp.example.com/sse"
  }
}
```

追加の認証設定は不要。

### OAuthスコープ

スコープはMCPサーバー側が決める。ユーザーは同意フローで必要な
スコープを確認する。**必要な権限は README に文書化する**:

```markdown
## 認証

このプラグインは以下の Asana 権限を必要とします:
- タスクとプロジェクトの読み取り
- タスクの作成と更新
- ワークスペースデータへのアクセス
```

### トークンの保存

トークンは Claude Code が安全に保管する: プラグインからはアクセス不可・
保存時に暗号化・自動更新・サインアウトでクリア。

### OAuth のトラブルシューティング

- **認証ループ**: キャッシュされたトークンをクリア（サインアウト→
  サインイン）、リダイレクトURLとサーバー側のOAuth設定を確認
- **スコープの問題**: 新しいスコープには再認可が必要な場合がある
- **トークン期限切れ**: 自動更新される。更新に失敗すると再認証を促される

## トークンベース認証

### Bearer トークン

HTTP / WebSocket サーバーで最も一般的:

```json
{
  "api": {
    "type": "http",
    "url": "https://api.example.com/mcp",
    "headers": {
      "Authorization": "Bearer ${API_TOKEN}"
    }
  }
}
```

```bash
export API_TOKEN="your-secret-token-here"
```

### APIキー / カスタムヘッダー

```json
{ "headers": { "X-API-Key": "${API_KEY}", "X-API-Secret": "${API_SECRET}" } }
{ "headers": { "X-Auth-Token": "${AUTH_TOKEN}", "X-User-ID": "${USER_ID}", "X-Tenant-ID": "${TENANT_ID}" } }
```

### トークン要件の文書化テンプレート

```markdown
## セットアップ

### 必要な環境変数

プラグインの使用前に設定する:

    export API_TOKEN="your-token-here"
    export API_SECRET="your-secret-here"

### トークンの取得方法

1. https://api.example.com/tokens にアクセスする
2. 新しいAPIトークンを作成する
3. トークンとシークレットをコピーする
4. 上記のとおり環境変数を設定する

### トークンに必要な権限

- リソースの読み取り
- アイテム作成のための書き込み
- 削除（任意。クリーンアップ操作用）
```

## 環境変数認証（stdio）

stdio サーバーには `env` フィールドで認証情報を渡す:

```json
{
  "database": {
    "command": "python",
    "args": ["-m", "mcp_server_db"],
    "env": {
      "DATABASE_URL": "${DATABASE_URL}",
      "DB_USER": "${DB_USER}",
      "DB_PASSWORD": "${DB_PASSWORD}"
    }
  }
}
```

`.env` ファイルを使う場合は必ず `.gitignore` に追加するよう README で
案内する（`source .env` で読み込み）。

## 動的ヘッダー

### headersHelper スクリプト

期限切れ・変化するトークンにはヘルパースクリプトを使う:

```json
{
  "api": {
    "type": "sse",
    "url": "https://api.example.com",
    "headersHelper": "${CLAUDE_PLUGIN_ROOT}/scripts/get-headers.sh"
  }
}
```

```bash
#!/bin/bash
# 動的な認証ヘッダーを生成する

# 新しいトークンを取得する
TOKEN=$(get-fresh-token-from-somewhere)

# JSONヘッダーを出力する
cat <<EOF
{
  "Authorization": "Bearer $TOKEN",
  "X-Timestamp": "$(date -Iseconds)"
}
EOF
```

**用途:** 短命トークンの更新、HMAC署名付きトークン、時刻ベース認証、
テナント/ワークスペースの動的選択。

## セキュリティのベストプラクティス

**DO:**

- ✅ 環境変数を使う（`"Bearer ${API_TOKEN}"`）
- ✅ 必要な変数を README に文書化する
- ✅ 常に HTTPS/WSS を使う
- ✅ トークンローテーションを実装する
- ✅ 使えるなら OAuth に任せる

**DON'T:**

- ❌ トークンのハードコード（`"Bearer sk-abc123..."` は絶対不可）
- ❌ トークンの git コミット
- ❌ ドキュメントでのトークン共有
- ❌ HTTP の使用
- ❌ トークンや機微なヘッダーのログ出力

## マルチテナントパターン

```json
// ヘッダーで指定
{ "headers": { "Authorization": "Bearer ${API_TOKEN}", "X-Workspace-ID": "${WORKSPACE_ID}" } }

// URLで指定
{ "url": "https://${TENANT_ID}.api.example.com/mcp" }
```

ユーザーが自分のワークスペースを環境変数で設定する
（`export WORKSPACE_ID="my-workspace-123"`）。

## トラブルシューティング

| 症状 | 確認事項 |
| --- | --- |
| 401 Unauthorized | トークンの設定・有効期限・権限・ヘッダー形式 |
| 403 Forbidden | トークンは有効だが権限不足。スコープ・テナントIDを確認 |
| トークン未設定 | `echo $API_TOKEN` で確認して設定する |
| 形式間違い | `"Bearer sk-abc123"`（`Bearer` プレフィックスを忘れない） |

**デバッグ:**

```bash
# デバッグモードで認証フロー・トークン更新・エラーを見る
claude --debug

# 認証を単体でテストする
curl -H "Authorization: Bearer $API_TOKEN" https://api.example.com/mcp/health
# 200 OK が返るべき
```

## 移行パターン

### ハードコード → 環境変数

1. 環境変数を README に追記する
2. 設定を `${VAR}` に変更する
3. 変数を設定してテストする
4. ハードコード値を削除する

### Basic認証 → OAuth

`"Authorization": "Basic ${BASE64_CREDENTIALS}"` を
`{ "type": "sse", "url": "https://mcp.example.com/sse" }` に置き換える。
セキュリティ向上・認証情報管理の不要化・自動トークン更新・
スコープ化された権限が得られる。

## 発展的な認証

### mTLS（相互TLS）

MCP設定では直接サポートされない。mTLS を処理する stdio ラッパーで回避する:

```json
{
  "secure-api": {
    "command": "${CLAUDE_PLUGIN_ROOT}/servers/mtls-wrapper",
    "args": ["--cert", "${CLIENT_CERT}", "--key", "${CLIENT_KEY}"],
    "env": { "API_URL": "https://secure.example.com" }
  }
}
```

### JWT / HMAC署名

headersHelper で動的に生成する:

```bash
#!/bin/bash
# HMAC署名の例
TIMESTAMP=$(date -Iseconds)
SIGNATURE=$(echo -n "$TIMESTAMP" | openssl dgst -sha256 -hmac "$SECRET_KEY" | cut -d' ' -f2)

cat <<EOF
{
  "X-Timestamp": "$TIMESTAMP",
  "X-Signature": "$SIGNATURE",
  "X-API-Key": "$API_KEY"
}
EOF
```

## まとめ

- **OAuth**: クラウドサービス向け（ユーザーにとって最も簡単）
- **Bearerトークン**: APIサービス向け
- **環境変数**: stdioサーバー向け
- **動的ヘッダー**: 複雑な認証フロー向け

常にセキュリティを優先し、ユーザー向けの明確なセットアップ手順を
提供すること。
