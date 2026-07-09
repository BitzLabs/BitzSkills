# 5. 設定項目とカスタマイズ (Configuration & Customization)

Codex CLI および SDK は、開発者個人やプロジェクト全体の要件に合わせて、設定ファイル、ルールファイル、環境変数を通じて高度にカスタマイズできます。特に `approval_policy` と `sandbox_mode` は、エージェントの自律性と安全性のバランスを調整する主要な鍵であり、`config.toml` で一元管理できます。

---

## 5.1 設定ファイル (`config.toml`)

Codex の動作設定は、主に **TOML 形式** の設定ファイルで記述されます。

### 1. 設定ファイルの優先順位 (Precedence)
Codex は、以下の順序で設定ファイルを探索・読み込み、後から読み込んだ設定でオーバーライド（上書き）します。

1. **グローバルデフォルト設定**:
   - `~/.codex/config.toml` (ユーザーのホームディレクトリ配下)
2. **プロジェクト別ローカル設定**:
   - `.codex/config.toml` (実行対象のプロジェクトルート直下)
   - *注意*: プロジェクト別の設定は、安全のため対象ディレクトリが「信頼されたワークスペース（Trusted Workspace）」に設定されている場合のみ適用されます。
3. **コマンドライン引数による上書き**:
   - `codex -c key=value` フラグによる指定（最優先）

---

### 2. 設定ファイルの構成例 (`config.toml`)

```toml
# ~/.codex/config.toml

# 基本設定
model = "gpt-5.5"                 # gpt-5.5（推奨）/ gpt-5.4 / gpt-5.4-mini / gpt-5.3-codex 等
approval_policy = "on-request"    # 承認ポリシー（untrusted / on-request / never / {granular=...}）
sandbox_mode = "workspace-write"  # サンドボックスの初期設定

# 機能フラグの切り替え（実在するキーの例）
[features]
hooks = true         # フック（実験的。旧名 codex_hooks）
apps = true          # アプリ連携
multi_agent = true   # サブエージェント（既定で有効）
network_proxy = true # サンドボックス下のネットワーク制御サブシステム

# サンドボックス動作の微調整（書き込み拡張は writable_roots）
[sandbox_workspace_write]
writable_roots = ["/tmp/build-cache"] # ワークスペース外で例外的に書き込みを許可するルート
# ※ネットワーク制御は network_access ではなく [features.network_proxy] 側で行う

# テレメトリ関連（telemetry トップレベルキーは実在しない）
[otel]
# エクスポート先等を設定
[analytics]
enabled = false

# Model Context Protocol (MCP) サーバーの登録
[mcp_servers.sqlite-viewer]
command = "node"
args = ["/usr/local/lib/node_modules/@modelcontextprotocol/server-sqlite/dist/index.js", "./data.db"]

[mcp_servers.web-search]
command = "npx"
args = ["-y", "@modelcontextprotocol/server-web-search"]

# プラグインの有効化設定
[plugins."db-helper-plugin@local"]
enabled = true
```

> [!NOTE]
> 旧記述の `approval_mode` / `[features] plugins・mcp・telemetry` / `sandbox_workspace_write.network_access` / `allowed_write_paths` は、いずれも現行の正しいキーではありません。承認は **`approval_policy`**、書き込み拡張は **`sandbox_workspace_write.writable_roots`**、ネットワークは **`features.network_proxy.*`** サブシステム、テレメトリは **`otel.*` / `analytics.enabled`** で制御します。

---

## 5.2 環境変数 (Environment Variables)

OS や CI/CD ランナーの環境変数を使用して、動作を制御できます。

* **`CODEX_HOME`**
  - Codex の設定ファイルやログインセッション情報（`auth.json`、プラグインキャッシュなど）を格納するディレクトリのパスを指定します。
  - デフォルト値は `~/.codex/`（Windows では `C:\Users\<User>\.codex\`）です。この変数を切り替えることで、同一マシン上で本番用とテスト用の認証セッションを分離することが可能です。
* **`OPENAI_API_KEY`**
  - 認証に ChatGPT アカウントではなく、OpenAI の API キーを使用する場合に指定します。

> [!NOTE]
> 一部の資料で紹介される `CODEX_LOG_LEVEL` / `CODEX_TRUSTED_PROJECTS` は公式では未確認です（要確認）。確実に利用できるのは `CODEX_HOME` と `OPENAI_API_KEY` です。ログ詳細度や信頼済みプロジェクトの制御は、環境変数ではなく `config.toml` 側の設定を確認してください。

---

## 5.3 承認ポリシー (Approval Policy)

エージェントがプログラムの実行やファイルの書き込みといった「副作用」を伴うツールを呼び出す際、ユーザーがどの程度介入するかを設定します。設定キーは **`approval_policy`** で、TUI では **`/permissions`**（プリセット: **Default** / **Auto-review** / **Full access** / **Custom**）から切り替えます。

| 設定値 | 説明 |
| :--- | :--- |
| `untrusted` | 信頼されていない操作について実行前に必ずユーザーの承認を要求します。最も保守的な設定です。 |
| `on-request` | エージェントが必要と判断したタイミングで承認を要求します。標準的な運用に適しています。 |
| `never` | 承認を求めず、サンドボックスの制限内で自律実行します。CI/CD などの無人環境向け。 |
| `{granular=...}` | 操作カテゴリごとに承認要否を細かく指定するグラニュラ設定。 |

> [!NOTE]
> 旧記述の `suggest` / `auto-edit` / `full-auto`（キー `approval_mode`）は現行では使われません。上記 `approval_policy` の値に置き換わっています。

---

## 5.4 ルールファイル (`rules`)

設定ファイルのほかに、エージェントの行動憲法となるルールを設定できます。

* **グローバルルール**: `~/.codex/rules`
* **プロジェクトルール**: `./AGENTS.md` または `.codex/rules`

これらのファイルには、プレーンテキストまたは Markdown で「どのようなファイルを編集してはいけないか」「テストはどのコマンドで実行すべきか」「推奨されるコーディングスタイルは何か」を記述します。エージェントはツール（編集、コマンド実行）を選択する際、これらのルールを読み込み、反するアクションを自己抑制します。
