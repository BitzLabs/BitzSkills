# 5. 設定項目とカスタマイズ (Configuration & Customization)

Antigravity 2.0 は、個人の開発環境設定を行うグローバル設定ファイルと、プロジェクトチームやリポジトリ単位で共有するプロジェクト別設定ファイルの2層構造で動作します。

---

## 5.1 設定ファイルとディレクトリ構造

### 1. グローバル設定
グローバルに有効な設定や、インストールしたプラグインはホームディレクトリ配下の特定のパスで管理されます。

*   **設定フォルダ**: `~/.gemini/config/`
*   **CLI 設定ファイル**: `~/.gemini/antigravity-cli/settings.json`
*   **グローバルプラグインの保存先**: `~/.gemini/config/plugins/<plugin_name>/`
*   **グローバルスキル保存先**: `~/.gemini/config/skills/`
*   **インポート台帳**: `~/.gemini/config/import_manifest.json`

### 2. プロジェクト別設定（ワークスペース設定）
プロジェクト単位での設定は、リポジトリのルートディレクトリに配置してバージョン管理システム（Git等）にコミットすることで、チームメンバー間で共有できます。

*   **プロジェクト設定ルート (Customization Root)**: `.agents/`
    > [!NOTE]
    > プラットフォームの仕様上、`.agents/` 以外にも以下の別名フォルダが同格のルートディレクトリとして許容されます：
    > `.agent/`, `_agents/`, `_agent/`
*   **配置構造**:
    *   `.agents/skills/` (プロジェクト専用スキル)
    *   `.agents/rules/` (プロジェクト専用ルールMarkdownファイル)
    *   `.agents/hooks.json` (プロジェクト専用フック定義)
    *   `.agents/mcp_config.json` (プロジェクト専用 MCP 設定)
    *   `.agents/skills.json` または `.agents/plugins.json` (宣言的設定ファイル)

---

## 5.2 読み込み優先順位と競合解決
同じ名前のスキル、ルール、設定、プラグインが複数箇所に存在する場合、以下の優先順位に従って上位が優先され、下位は上書きまたは無視されます。

1.  **ワークスペース自動発見** (カレントディレクトリからリポジトリルートまでの階層探索で先に見つかったもの)
2.  **ワークスペース宣言的設定** (`skills.json` / `plugins.json` で明示的に指定されたパス)
3.  **グローバル自動発見** (`~/.gemini/config/` 配下)
4.  **組み込み機能 (Built-in)** (Antigravity 自体に最初から内包されているシステム設定)
5.  **グローバル宣言的設定** (`~/.gemini/config/` 以下の宣言的設定)

---

## 5.3 宣言的設定 (`skills.json` / `plugins.json`) の仕様
標準の発見場所以外のディレクトリにあるスキルやプラグインを読み込ませたい場合、または他チームが公開している共有共有ディレクトリを参照したい場合に、`skills.json` または `plugins.json` に記述して読み込み先を拡張します。

### スキーマと記述例
```json
{
  "inherits": [
    {
      "path": "/path/to/shared/plugins.json",
      "include_only": ["linter-.*", "security-.*"],
      "exclude": ["deprecated-.*"]
    }
  ],
  "entries": [
    { "path": "tools/internal/plugins" },
    { "path": "~/personal-plugins" }
  ]
}
```

### パラメータ解説
*   `entries[].path` (必須): スキャン対象のディレクトリパス。
*   `inherits` (任意): 別の設定ファイルをロードしてマージするための継承設定。配列の記載順に処理されます。
*   `include_only` / `exclude` (任意): 正規表現パターンを用い、合致するフォルダ名のみをインポート対象とする（または除外する）フィルタ機能。

### 相対パスの解決ルール
`path` フィールドに指定されたパスの起点は以下のように解決されます。
1.  **絶対パス**: `/` で始まる場合。
2.  **ホーム相対パス**: `~/` で始まる場合、ユーザーのホームディレクトリを起点に解決。
3.  **リポジトリルート相対**: 上記以外（例: `"tools/internal/plugins"`) の場合、**プロジェクトのリポジトリルート（`.git` が置かれているディレクトリ）**を起点とした相対パスとして処理されます。

---

## 5.4 グローバル設定項目 (`settings.json`)
`~/.gemini/antigravity-cli/settings.json` に格納される、CLI 全体の主要な設定パラメータです。対話的スラッシュコマンド `/config` で編集できます。

*   **`colorScheme`** (string): TUI のカラーテーマを設定します（例: `"dark"`, `"light"`, `"solarized dark"`）。
*   **`model`** (string): デフォルトで使用する Gemini LLM モデル（例: `"gemini-2.5-pro"` 等）。
*   **`enableTerminalSandbox`** (boolean): エージェントが実行するシェルコマンドを安全なサンドボックス内に隔離するかどうか（デフォルト: `true`）。
*   **`toolPermission`** (string): ツール実行時の自律権限を設定します。
    *   `"strict"` または `"request-review"`: コマンドや重要ファイルの編集を実行する前に必ずユーザーに確認を求めます。
    *   `"always-proceed"`: 警告なしで自動的にツール実行を許可します。
*   **`verbosity`** (string): ツールの実行プロセスにおけるログ詳細レベル（`"low"`, `"high"`）。
*   **`trustedWorkspaces`** (array of strings): エージェントに対してフルアクセスを無条件に信頼するディレクトリパスのホワイトリスト。

---

## 5.5 環境変数とプロキシ環境の制約

### 動作モードの変更
以下の環境変数を設定することで、実行時の動作を変更できます。
*   `ANTIGRAVITY_ENV` (または `AGY_ENV`): `"development"` に設定するとデバッグログや冗長なシステムスタックトレースが有効になります。

### プロキシ（Proxy）環境での注意点
Antigravity CLI は一部のバージョンにおいて、標準的なネットワークプロキシ環境変数（`HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY`）を正しく認識・適用しない挙動が報告されています。
*   エンタープライズの社内ネットワーク等でプロキシを通過する必要がある場合、接続エラー（タイムアウトや SSL 疎通エラー）が発生することがあります。
*   この場合は、システムのネットワーク設定に依存するか、プロキシをバイパスするようローカル環境を設定する必要があります（Cloud Shell 等の自動マネージド環境ではプロキシは透過的に処理されます）。
