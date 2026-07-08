# 第4章 拡張機能とアーキテクチャ (Extensibility & Architecture)

Claude Code は、プラグイン、フック、スキル、カスタムツール、サブエージェントから構成される、高い拡張性を持ったアーキテクチャを採用しています。

---

## 4.1 プラグイン (Plugins)

### ディレクトリ構造と自動発見 (Auto-discovery)

プラグインは特定のディレクトリ構造に従って配置されることで、Claude Code 起動時にコンポーネントが自動発見（Auto-discovery）されます。

**標準ディレクトリ構成 (Claude Code):**
```
my-plugin/
├── .claude-plugin/
│   └── plugin.json          # 必須: プラグインマニフェスト
├── commands/                 # スラッシュコマンド（.mdファイル）
├── agents/                   # サブエージェント定義（.mdファイル）
├── skills/                   # エージェントスキル（各スキルごとのサブフォルダ）
│   └── skill-name/
│       └── SKILL.md         # スキルの指示ファイル（必須）
├── hooks/
│   └── hooks.json           # イベントハンドラー設定
└── .mcp.json                # MCP（Model Context Protocol）サーバー定義
```

### マニフェスト (`plugin.json`) の仕様

`.claude-plugin/plugin.json` に記述するメタデータと設定項目の一覧です。

```json
{
  "name": "code-review-assistant",
  "version": "1.0.0",
  "description": "コード品質のレビューと自動修正を支援するプラグイン",
  "author": {
    "name": "Jane Developer",
    "email": "jane@example.com"
  },
  "license": "MIT",
  "keywords": ["testing", "review"],
  "commands": ["./commands"],
  "agents": ["./agents"],
  "hooks": "./hooks/hooks.json",
  "mcpServers": "./.mcp.json"
}
```

- `name`（必須）: 英小文字、数字、ハイフンのみで構成される kebab-case。インストール済みプラグイン間で一意である必要があります。
- `commands`, `agents`（任意）: 追加でスキャンするカスタムパス。`./` から始まる相対パスのみ指定可能です。
- `hooks`, `mcpServers`（任意）: フック設定や MCP サーバー定義のファイルパス。またはオブジェクトとしてインライン記述することも可能です。

---

## 4.2 スキル (Skills)

### Progressive Disclosure (段階的開示)

スキルとは、特定のドメイン知識やワークフローをエージェントに提供するパッケージです。トークン節約のため、**Progressive Disclosure（段階的開示）**設計が導入されています。

1. **第1段階 (メタデータ読み込み)**: スキルフォルダ内の `SKILL.md` の frontmatter（`name` と `description`）のみを常時コンテキストに読み込みます（約100語）。
2. **第2段階 (スキル本文の読み込み)**: ユーザーの指示が description に定義されたトリガーと一致した場合、初めて `SKILL.md` の本文（最大1,500〜2,000語程度を推奨）がコンテキストに展開されます。
3. **第3段階 (バンドルリソースの読み込み)**: スキルフォルダ内の `scripts/`, `references/`, `examples/` などのリソースは、本文中の指示に基づいて必要になった時だけ個別に読み込まれます。

### `SKILL.md` の記述規則

- **frontmatter**: `name` と `description` は必須です。`description` には、エージェントがそのスキルを使用すべき具体的なトリガーフレーズ（「『〇〇したい』と言われたとき」など）を含めます。
- **記述スタイル**: 本文はすべて**三人称の命令形（動詞から始まる指示）**で記述します（例: `「フックを作成する」`。`「あなたは〜すべきです」` のような二人称は避けます）。

---

## 4.3 コマンド (Slash Commands)

`commands/` ディレクトリ直下のマークダウンファイルが、そのままスラッシュコマンドとして定義されます（例: `review.md` → `/review`）。

- **最重要原則**: コマンドの本文は人間向けの説明ではなく、**Claude への指令プロンプト**として記述します。
- **frontmatter フィールド**:
  - `description`: `/help` に表示される説明。
  - `argument-hint`: 引数の補完ヒント（例: `[pr-number] [priority]`）。
  - `allowed-tools`: コマンド内での使用を許可するツールのリスト。
  - `disable-model-invocation`: モデルがこのコマンドを自律的に（自動で）呼び出すのを禁止し、ユーザーによる手動実行のみに制限します。
- **動的引数の展開**: 本文内で `$ARGUMENTS`（全引数）や `$1`, `$2`（位置引数）がプレースホルダとして利用可能です。
- **動的機能**:
  - `@ファイルパス`: ファイルの内容をコマンド実行時にコンテキストへインクルードします。
  - `!コマンド`: 動的なコンテキスト（例: git diff の出力など）を収集するために、インラインで bash コマンドを実行します（例: ``変更ファイル: !`git diff --name-only` ``）。

---

## 4.4 サブエージェント (Subagents)

サブエージェント（`agents/*.md`）は、特定の専門領域に特化し、自律的に複数ステップを実行するためのエージェント定義です。

- **トリガー定義**: frontmatter の `description` 内に、Claude がいつこのエージェントを Task ツールで起動すべきかを判断するための `<example>` ブロックを必ず記述します。
  ```markdown
  description: コードのセキュリティ監査を行うときに使用する。例:
  <example>
  Context: ユーザーがソースコードの脆弱性確認を求めている。
  user: "この関数のセキュリティ上の問題点をチェックして"
  assistant: "了解しました。セキュリティ監査エージェントを起動して検証します。"
  <commentary>
  ユーザーがセキュリティのチェックを求めているため、監査エージェントが最適です。
  </commentary>
  </example>
  ```
- **システムプロンプト**: コマンドやスキルとは異なり、本文は**二人称（「あなたは〜です」）**でエージェントに直接語りかけるように記述します。
- **`model: inherit` の推奨**: 親セッションのモデルを引き継ぐ設定です。これにより、Gemini 等の他モデルで動作する互換レイヤーでも問題なくエージェントが動作します。

---

## 4.5 ライフサイクルフック (Hooks)

フックは、エージェントのイベント（ツール使用前後など）をインターセプトし、検証や自動化を実行する仕組みです。

### イベント体系

| イベント名 | タイミング | 用途 |
| :--- | :--- | :--- |
| `PreToolUse` | ツール（ファイルの編集やコマンド実行など）が実行される直前 | 入力の検証、パストラバーサルの検出、実行の承認/拒否 |
| `PostToolUse` | ツール実行が完了した直後 | 実行結果に対する Linter の適用、ログ収集 |
| `UserPromptSubmit`| ユーザーがプロンプトを入力した直後 | コンテキストの自動付与、クエリの検証 |
| `Stop` | エージェントが処理を終了しようとする直前 | タスクが本当に完了しているかの検証、終了のブロック |
| `SubagentStop` | サブエージェントが終了する直前 | サブタスクの完了検証 |
| `SessionStart` | セッション開始時 | プロジェクト状態の読み込み、環境変数の設定 |
| `SessionEnd` | セッション終了時 | クリーンアップ、ログ送信 |
| `PreCompact` | トークン圧縮処理が行われる直前 | 保持すべき重要コンテキストの保護 |

### フックの種類

1. **プロンプトベースフック (Prompt-based Hook)**: 自然言語のプロンプトを LLM に推論させ、承認判断を行います（`PreToolUse`, `Stop` などで推奨）。
2. **コマンドフック (Command Hook)**: Bash スクリプトを実行し、終了コードと出力 JSON によって厳密かつ決定的に検証します。

### 入出力 JSON 契約 (Command Hook の場合)

コマンドフックが起動されると、標準入力 (stdin) を通じてコンテキスト情報が JSON 形式で渡されます。

**標準入力 (stdin):**
```json
{
  "session_id": "session_123",
  "cwd": "/workspace",
  "hook_event_name": "PreToolUse",
  "tool_name": "Write",
  "tool_input": {
    "file_path": "src/dangerous.js",
    "content": "..."
  }
}
```

**標準出力 (stdout) の期待フォーマット (PreToolUseの例):**
```json
{
  "continue": true,
  "suppressOutput": false,
  "systemMessage": "ファイル書き込みがセキュリティ検証を通過しました。",
  "hookSpecificOutput": {
    "permissionDecision": "allow" 
  }
}
```

- `permissionDecision` の値: `"allow"` (実行を許可)、`"deny"` (実行を即時拒否)、`"ask"` (ユーザーに手動で問い合せる)。
- **終了コードの解釈**:
  - `0`: 正常終了。出力がトランスクリプトに反映されます。
  - `2`: ブロッキングエラー。エラーメッセージ（stderr）がエージェントにフィードバックされ、処理がブロックされます。

---

## 4.6 MCP 統合 (Tools)

**MCP（Model Context Protocol）** を使用して、外部サービスや自作のサーバーをツールとして統合できます。

- **設定ファイル**: プラグインルートの `.mcp.json` または `plugin.json` 内の `mcpServers` で定義します。
- **ツールの自動名前空間化**:
  衝突を避けるため、登録された MCP ツールには以下のプレフィックスが自動で付与されます。
  `mcp__plugin_<plugin_name>_<server_name>__<tool_name>`
- **認証**: API トークンを環境変数（`${MY_API_KEY}`）から渡す構成、または SSE トランスポートを介した自動ブラウザ OAuth 認証が利用できます。

---

## 4.7 プラットフォーム互換性 (Antigravity 2.0 との違い)

ワークスペース内のプラグイン構成案から得られた、**Antigravity 2.0 (agy CLI)** との仕様差の一覧です。両対応プラグインを開発する場合は、これらの違いを吸収する設計が必要です。

| 機能 / 仕様 | Claude Code | Antigravity 2.0 |
| :--- | :--- | :--- |
| **マニフェストのパス** | `.claude-plugin/plugin.json` | ルート直下の `plugin.json` (両対応は両方置く) |
| **スラッシュコマンド** | `commands/*.md` で定義可能 | ネイティブ非対応 (agy がインストール時にスキルへ変換) |
| **フック設定ファイル** | `hooks/hooks.json` (かつ `hooks` キーでラップする) | ルート直下の `hooks.json` (ラッパーなし) |
| **フックイベント** | PreToolUse, PostToolUse, Stop, SessionStart 等 | PreToolUse, PostToolUse, PreInvocation, PostInvocation, Stop の5種のみ |
| **フック種類** | プロンプトベース / コマンドの両対応 | コマンドフックのみ |
| **フック入出力契約** | stdin/stdout のキー名は snake_case | stdin/stdout のキー名は camelCase |
| **MCP設定ファイル** | `.mcp.json` または `plugin.json` 内 | ルート直下の `mcp_config.json` |
| **MCPトランスポート** | stdio, SSE, HTTP, WebSocket | stdio と SSE (`serverUrl` 指定) のみサポート |
| **プラグインパスの参照** | `${CLAUDE_PLUGIN_ROOT}` 環境変数を解決 | 環境変数はなし (フックの cwd が hooks.json の場所になる) |
