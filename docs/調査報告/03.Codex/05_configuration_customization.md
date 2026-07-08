# 5. 設定項目とカスタマイズ (Configuration & Customization)

Codex CLI および SDK は、開発者個人やプロジェクト全体の要件に合わせて、設定ファイル、ルールファイル、環境変数を通じて高度にカスタマイズできます。

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
model = "gpt-5.2-codex"
approval_mode = "auto-edit"  # 承認モード
sandbox_mode = "workspace-write"  # サンドボックスの初期設定

# 特徴量（機能）フラグの切り替え
[features]
plugins = true
mcp = true
telemetry = false

# サンドボックス動作の微調整
[sandbox_workspace_write]
network_access = false  # ワークスペース書き込みモード時のネットワークアクセス制限
allowed_write_paths = ["/tmp/build-cache"] # ワークスペース外で例外的に書き込みを許可するパス

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

---

## 5.2 環境変数 (Environment Variables)

OS や CI/CD ランナーの環境変数を使用して、動作を制御できます。

* **`CODEX_HOME`**
  - Codex の設定ファイルやログインセッション情報（`auth.json`、プラグインキャッシュなど）を格納するディレクトリのパスを指定します。
  - デフォルト値は `~/.codex/`（Windows では `C:\Users\<User>\.codex\`）です。この変数を切り替えることで、同一マシン上で本番用とテスト用の認証セッションを分離することが可能です。
* **`OPENAI_API_KEY`**
  - 認証に ChatGPT アカウントではなく、OpenAI の API キーを使用する場合に指定します。
* **`CODEX_LOG_LEVEL`**
  - エージェントおよび `codex-app-server` のログ詳細度を制御します。（値: `debug`, `info`, `warn`, `error`）
* **`CODEX_TRUSTED_PROJECTS`**
  - ローカルの `.codex/config.toml` を自動的に信頼するディレクトリパスのリストをコロン（Windows ではセミコロン）区切りで指定します。

---

## 5.3 承認モード (Approval Modes)

エージェントがプログラムの実行やファイルの書き込みといった「副作用」を伴うツールを呼び出す際、ユーザーがどの程度介入するかを設定するモードです。

| モード名 | 設定値 | 説明 |
| :--- | :--- | :--- |
| **Suggest (提案のみ)** | `suggest` | ファイルの書き込みを含め、ツール実行のすべてについて実行前に必ずユーザーの承認を要求します。エージェントは提案を行い、人間が承諾したアクションのみ実行されます。 |
| **Auto Edit (編集自動・実行確認)** | `auto-edit` | ファイルの新規作成やコードの書き換え（編集ツール）は自動で実行されます。ただし、シェルコマンドの実行（Bashツール）や外部への通信が発生するツールのみ、実行前にユーザーの承認を要求します。（**デフォルト**） |
| **Full Auto (全自動)** | `full-auto` | サンドボックスの制限内であれば、コマンド実行を含めて人間の介入なしですべて自律実行します。CI/CDなどの無人環境で使用します。 |

---

## 5.4 ルールファイル (`rules`)

設定ファイルのほかに、エージェントの行動憲法となるルールを設定できます。

* **グローバルルール**: `~/.codex/rules`
* **プロジェクトルール**: `./AGENTS.md` または `.codex/rules`

これらのファイルには、プレーンテキストまたは Markdown で「どのようなファイルを編集してはいけないか」「テストはどのコマンドで実行すべきか」「推奨されるコーディングスタイルは何か」を記述します。エージェントはツール（編集、コマンド実行）を選択する際、これらのルールを読み込み、反するアクションを自己抑制します。
