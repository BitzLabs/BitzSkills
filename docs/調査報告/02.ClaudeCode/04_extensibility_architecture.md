# 4. 拡張機能とアーキテクチャ (Extensibility & Architecture)

## 4.1 プラグイン (Plugins)
Claude Code はプラグイン構造によって大幅に拡張することができます。ひとつのプラグインは、スキル、カスタムコマンド、サブエージェント、MCPサーバー定義、ライフサイクルフックなどをパッケージ化したものです。

### マニフェストファイル (`.claude-plugin/plugin.json`)
プラグインの認識に必須となるマニフェストファイルです。プラグインのルートにある `.claude-plugin/` フォルダ内に配置します。

```json
{
  "name": "enterprise-devops",
  "version": "1.0.0",
  "description": "Enterprise CI/CD pipeline DevOps automation plugin",
  "author": {
    "name": "DevOps Team",
    "email": "devops@company.com"
  },
  "license": "Apache-2.0",
  "keywords": ["devops", "ci-cd", "automation"],
  "commands": ["./commands", "./admin-commands"],
  "agents": "./specialized-agents",
  "hooks": "./config/hooks.json",
  "mcpServers": "./.mcp.json"
}
```

- **`name`**: kebab-case 形式の一意の識別子（検証パターン: `/^[a-z][a-z0-9]*(-[a-z0-9]+)*$/`）。
- **`version`**: セマンティックバージョニング（semver）に準拠。
- **`commands` / `agents` / `hooks` / `mcpServers`**: 各コンポーネントが配置されている相対パスを指定します。`./` から始める必要があります（`../` や絶対パスは不可）。

## 4.2 スキル (Skills)
スキルは [Agent Skills](https://agentskills.io/specification) オープン標準に準拠した指示メタデータです。エージェントが特定のドメインの作業を行う際に、コンテキストに追加するインストラクション群を定義します。

### 構造
ひとつのフォルダとして独立し、中に `SKILL.md` を必須とします。
```text
skill-name/
├── SKILL.md          # 必須: メタデータ(frontmatter) + 指示
├── scripts/           # 任意: スクリプトコード (Python/Bashなど)
└── references/        # 任意: 詳細仕様、ベストプラクティス
```

### `SKILL.md` の構成例
```yaml
---
name: skill-name
description: このスキルが何をするか、いつ使うかの説明。エージェントが発見段階で読み込みます。
metadata:
  version: "0.1.0"
  author: dev-name
  created: "2026-07-08"
  updated: "2026-07-08"
---

# skill-name

## 目的
このスキルは、特定のタスクを効率的に実行するための手順を定義します。

## 手順
1. ...
```

### Progressive Disclosure (段階的開示)
エージェントは会話開始時にすべてのスキルの内容を読み込みません。
1. **Discovery (発見)**: `name` と `description` のみを読み込みます。
2. **Activation (活性化)**: タスクに関係があると推論された場合のみ、`SKILL.md` 本文全体を読み込みます。
3. **Execution (実行)**: さらに深い詳細が必要になったときのみ、`references/` や `scripts/` にアクセスします。

## 4.3 コマンド (Slash Commands)
スラッシュコマンドは、対話シェルからユーザーが明示的に実行する、テンプレート化された指示またはワークフローです。プラグイン内の `commands/` ディレクトリ配下にマークダウンファイル（例: `commands/deploy.md`）として定義します。

```markdown
---
description: アプリケーションを環境へデプロイする
argument-hint: [environment] [version]
allowed-tools: Bash(kubectl:*), Bash(helm:*), Read
model: sonnet
disable-model-invocation: false
---

$1 環境へバージョン $2 をデプロイします。

現在のクラスタ情報を確認: !`kubectl cluster-info`
設定を確認: @${CLAUDE_PLUGIN_ROOT}/config/$1.json

上記設定に基づき、デプロイを行ってください。
```

- **`!` 構文 (インラインコマンド)**: `!` の後にシェルコマンドを記述することで、プロンプト生成時にそのコマンドの stdout 結果をインクルードします。
- **`@` 構文 (ファイルインクルード)**: パスを指定して、ファイルの内容をプロンプトにインクルードします。
- **`${CLAUDE_PLUGIN_ROOT}`**: プラグインの絶対パスに展開される特殊環境変数。ポータブルなファイル参照に必須です。
- **`disable-model-invocation`**: `true` に設定すると、Claude による自動（自律的）実行を禁止し、人間がシェルに `/deploy` と打ったときだけ実行できるようにします。安全用のセーフガードになります。

## 4.4 サブエージェント (Subagents)
サブエージェントは、複雑で時間がかかるサブタスクを自律的にこなす専用の別プロセスです。プラグインの `agents/` ディレクトリ配下にマークダウンファイル（例: `agents/code-reviewer.md`）として定義します。

### frontmatter のトリガー定義
サブエージェントがいつトリガーされるかを LLM に判断させるため、`description` に具体的な `<example>` ブロックを含める必要があります。

```markdown
---
name: code-reviewer
description: コードの品質レビューを求められたときにこのエージェントを使用する。例:
<example>
Context: ユーザーが新機能を実装し、レビューを求めている
user: "実装したコードに問題がないかレビューして"
assistant: "code-reviewer エージェントで徹底レビューを行います。"
<commentary>
ユーザーが明示的にコードレビューを依頼しているため、code-reviewerを起動します。
</commentary>
</example>
model: inherit
color: blue
tools: ["Read", "Grep", "Glob"]
---

あなたは品質管理を専門とするシニアコードレビュアーです。

**中心的な責務:**
1. 静的解析結果の確認
2. コードの保守性と可読性の評価

**プロセス:**
1. Read ツールで対象コードを読み込みます...
```

- **`model: inherit`**: Antigravity など他プラットフォームとの互換性を保つため、親モデルを継承する `inherit` の指定が推奨されます。

## 4.5 ライフサイクルフック (Hooks)
フックはエージェントのアクションやセッションイベントに反応して実行される、スクリプト・HTTP エンドポイント・MCP ツール・プロンプト・サブエージェントのいずれかです。プラグインの `hooks/hooks.json` で構成します。ひとつのフック定義は「**フックイベント**（発火するライフサイクル上の一点）」「**マッチャーグループ**（いつ発火するかを絞り込むフィルタ）」「**フックハンドラ**（実際に走る処理）」の3層から成ります。

### フックイベント（約30種類）
現行の Hooks reference では**約30種類**のフックイベントが定義されており、セットは活発に拡張中です。以下は代表的なもので、正確な一覧は公式リファレンスを正とします。

セッションと入力の境界:
- **`SessionStart` / `SessionEnd`**: セッション開始・終了。開始時の環境変数永続化（`$CLAUDE_ENV_FILE` 経由）やクリーンアップに使用。
- **`Setup`**: `--init-only`、または `-p` モードでの `--init` / `--maintenance` 起動時。CI/スクリプトでの一度きりの準備向け。
- **`UserPromptSubmit`**: ユーザーがプロンプトを送信した瞬間（Claude 処理前）にコンテキストを追加。
- **`UserPromptExpansion`**: ユーザーが打ったコマンドがプロンプトへ展開される直前。展開自体をブロック可能。

エージェンティックループ内:
- **`PreToolUse`**: ツール実行直前に介入し、入力の検証や実行許可の判断を行う。ブロック可能。
- **`PermissionRequest` / `PermissionDenied`**: 許可ダイアログ表示時／自動モードの分類器が拒否した時。`PermissionDenied` は `{retry: true}` を返すとモデルに再試行を許可できる。
- **`PostToolUse` / `PostToolUseFailure`**: ツール成功後／失敗後。実行は取り消せず、フィードバックの注入のみ。
- **`PostToolBatch`**: 並列ツール呼び出しのバッチが解決した後、次のモデル呼び出しの前。
- **`SubagentStart` / `SubagentStop`**: サブエージェントの起動・終了。
- **`TaskCreated` / `TaskCompleted`**: `TaskCreate` によるタスク作成時／完了マーク時。

応答・圧縮・その他:
- **`Stop` / `StopFailure`**: Claude が応答を完了した時／API エラーで打ち切られた時。`Stop` は `decision: "block"` で停止を防ぎ最終確認（ビルド・テスト）に使える。
- **`PreCompact` / `PostCompact`**: コンテキスト圧縮の前後。
- **`InstructionsLoaded`**: `CLAUDE.md` や `.claude/rules/*.md` がコンテキストに読み込まれた時。セッション開始時と遅延ロード時の双方で発火。
- **`Notification` / `MessageDisplay`**: 通知送信時／アシスタントのメッセージテキスト表示中。
- **`ConfigChange` / `CwdChanged` / `FileChanged`**: 設定ファイル変更時／作業ディレクトリ変更時（`cd` 等）／監視対象ファイルの変更時。
- **`WorktreeCreate` / `WorktreeRemove`**: worktree の作成・削除時。既定の git 挙動を置き換える。
- **`Elicitation` / `ElicitationResult`**: MCP サーバーがツール呼び出し中にユーザー入力を要求した時／その応答が返される前。
- **`TeammateIdle`**: エージェントチームのメンバーがアイドルになる直前。

### フックハンドラの5種別 (`type`)
内側の `hooks` 配列の各要素がハンドラで、`type` により5種類あります（旧世代の command / prompt の2種から拡張されています）。

- **`command`**: シェルコマンドを実行。JSON 入力を stdin で受け取り、終了コードと stdout で結果を返す。
- **`http`**: イベントの JSON 入力を HTTP POST で URL へ送信し、レスポンスボディで結果を返す。
- **`mcp_tool`**: 接続済み MCP サーバーのツールを呼び出す。ツールのテキスト出力を command の stdout と同様に扱う。
- **`prompt`**: Claude モデルに単一ターンの評価を依頼し、yes/no の判断を JSON で受け取る。
- **`agent`**: Read/Grep/Glob 等を使えるサブエージェントを起動し、条件を検証させてから判断を返す（実験的機能）。

一致したハンドラはすべて並列実行され、同一のハンドラは自動で重複排除されます。

### マッチャー (Matcher) の詳細
`matcher` フィールドは「そのイベントを**いつ発火させるか**」を絞り込むフィルタです。含まれる文字によって評価方法が変わります。

| matcher の値 | 評価方法 | 例 |
| :--- | :--- | :--- |
| `"*"` / `""` / 省略 | すべてに一致 | イベントの全発生で発火 |
| 英数字・`_`・`-`・空白・`,`・`\|` のみ | 完全一致、または `\|` / `,` 区切りの完全一致リスト（前後空白は許容） | `Bash` は Bash ツールのみ、`Edit\|Write` や `Edit, Write` はどちらかのツールに一致 |
| それ以外の文字を含む | JavaScript 正規表現（アンカーなし） | `^Notebook` は Notebook で始まるツール名、`mcp__memory__.*` は memory サーバーの全ツール |

正規表現パスは `RegExp.prototype.test` で評価され、値の**どこか**に一致すれば成立します。したがって `Edit.*` は `Edit` と `NotebookEdit` の両方に一致し、完全一致させたい場合は `^Edit$` のように `^` と `$` で囲みます。なお、カンマ区切りと前後空白の許容は Claude Code v2.1.191 以降、完全一致セットでのハイフンは v2.1.195 以降が必要です（それ以前はハイフン名も正規表現扱いになります）。`FileChanged` と `StopFailure` は例外で、`_` と `|` のみの狭い完全一致セットを使い、区切りは `|` のみです。

**イベントごとに matcher が照合する対象フィールドが異なります**。tool 系イベントでは `tool_name` に対して照合されます。

| イベント | matcher が絞り込む対象 | matcher 値の例 |
| :--- | :--- | :--- |
| `PreToolUse` / `PostToolUse` / `PostToolUseFailure` / `PermissionRequest` / `PermissionDenied` | ツール名 | `Bash`, `Edit\|Write`, `mcp__.*` |
| `SessionStart` | セッションの開始方法 | `startup`, `resume`, `clear`, `compact` |
| `Setup` | 起動した CLI フラグ | `init`, `maintenance` |
| `SessionEnd` | 終了理由 | `clear`, `resume`, `logout`, `prompt_input_exit`, `other` ほか |
| `Notification` | 通知種別 | `permission_prompt`, `idle_prompt`, `auth_success`, `agent_completed` ほか |
| `SubagentStart` / `SubagentStop` | エージェント種別 | `general-purpose`, `Explore`, `Plan`, カスタム名、`^my-plugin:reviewer$` 等 |
| `PreCompact` / `PostCompact` | 圧縮の契機 | `manual`, `auto` |
| `ConfigChange` | 設定ソース | `user_settings`, `project_settings`, `local_settings`, `policy_settings`, `skills` |
| `StopFailure` | エラー種別 | `rate_limit`, `overloaded`, `authentication_failed`, `server_error` ほか |
| `InstructionsLoaded` | 読み込み理由 | `session_start`, `nested_traversal`, `path_glob_match`, `include`, `compact` |
| `FileChanged` | 監視するファイル名（リテラル） | `.envrc\|.env` |
| `UserPromptSubmit` / `PostToolBatch` / `Stop` / `TaskCreated` / `TaskCompleted` / `CwdChanged` / `WorktreeCreate` / `WorktreeRemove` / `MessageDisplay` / `TeammateIdle` | matcher 非対応 | 常に全発生で発火（`matcher` を書いても無視される） |

MCP ツールは `mcp__<server>__<tool>` の形で通常ツールと同様に照合できます。サーバー配下の全ツールに一致させるには `mcp__memory__.*` のように末尾へ `.*` が**必須**です（`mcp__memory` だけでは完全一致扱いとなり何にも一致しません）。tool 系イベントでは、ハンドラ個別の `if` フィールド（permission ルール構文）で `Bash(git *)` や `Edit(*.ts)` のように引数まで含めてさらに絞り込めます。

**入出力契約の例**（`type: "command"` の `PreToolUse`。`matcher` で Bash に絞り込む場合）:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          { "type": "command", "command": "/path/to/block-rm.sh" }
        ]
      }
    ]
  }
}
```

### コマンドフックの入出力契約 (JSON)
`type: "command"` の場合、スクリプトは標準入力（stdin）から JSON を受け取り、検証結果を標準出力（stdout）に JSON で返します。

**入力 JSON（例）**:
```json
{
  "session_id": "abc123",
  "tool_name": "Write",
  "tool_input": {
    "file_path": "src/index.js",
    "content": "..."
  },
  "hook_event_name": "PreToolUse"
}
```

**出力 JSON（例）**:
```json
{
  "hookSpecificOutput": {
    "permissionDecision": "allow",
    "updatedInput": {}
  },
  "systemMessage": "ファイル書き込みが許可されました。"
}
```

終了コードとして `0` は成功、`2` はブロッキングエラー（処理を即時ブロックし、stderr のエラーを Claude にフィードバック）を意味します。

## 4.6 ツール (Tools) と MCP 統合

### 1. 組み込みツール (Built-in Tools)
Claude Code は、ファイルシステムやシェル環境と対話するための以下の基礎的な内部ツールをデフォルトで備えています。

*   **`Read`**: 指定されたパスのファイルを読み込み、エージェントのコンテキストに展開します。
*   **`Grep`**: 指定されたディレクトリ内のファイルから、特定のパターンや文字列を検索します（`git grep -nI` 相当）。
*   **`Glob`**: ワイルドカードパターンに一致するファイルパスの一覧を取得します。
*   **`Bash`**: シェルコマンドを実行します。単なるコマンド実行だけでなく、引数のヒントや実行許可コマンドの制限（例: `Bash(kubectl:*)` や `Bash(helm:*)` などのように特定のプレフィックスのみ許可する等）を細かく制御できます。
*   **`!` (インラインコマンド構文)**: スラッシュコマンドなどのプロンプトテンプレート生成時に、`!` に続くコマンドを実行し、その標準出力（stdout）の結果を直接プロンプトにインクルードする内部的なマクロツールです。
*   **`@` (ファイルインクルード構文)**: 指定されたファイルの内容をプロンプトに直接インクルードする内部的なマクロツールです。

### 2. MCP 統合 (Model Context Protocol)
Model Context Protocol (MCP) を通じて、外部サービス（GitHub, PostgreSQL, Slack, Sentry など）を Claude Code にツールとして追加できます。プラグインの `.mcp.json` またはマニフェストの `mcpServers` で構成します。

```json
{
  "mcpServers": {
    "postgres-db": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-postgres", "postgresql://localhost/mydb"]
    }
  }
}
```

これによって、Claude は `mcp__postgres-db__query` などのツールを自律的に呼び出せるようになります。

## 4.7 プラットフォーム互換性 (Antigravity 2.0 との違い)
Google Antigravity 2.0 は Claude Code の多くの拡張レイアウトをエミュレートしますが、設計上の思想の違いによる差異があります。

| 項目 | Claude Code | Google Antigravity 2.0 |
| :--- | :--- | :--- |
| **マニフェスト** | `.claude-plugin/plugin.json` (詳細設定) | プラグインルートの `plugin.json` (ほぼ人間用メタデータ) |
| **フックファイル** | `hooks/hooks.json` | ルート直下の `hooks.json` |
| **フック JSONキー** | `snake_case` | `camelCase` |
| **フック種別 (`type`)** | command / http / mcp_tool / prompt / agent の5種 | command のみ |
| **フックイベント** | 約30種類（`PreToolUse`, `PostToolUse`, `UserPromptSubmit`, `SubagentStart/Stop`, `PreCompact/PostCompact`, `SessionStart/End`, `InstructionsLoaded` ほか。4.5 参照） | 5種類 (`PreToolUse`, `PostToolUse`, `PreInvocation`, `PostInvocation`, `Stop`) |
| **Stopフック挙動** | `decision: "block"` で停止防止 | `decision: "continue"` で停止防止（ループ継続） |
| **コマンドファイル** | `/commands` 配下。そのまま解釈。 | スキル（`SKILL.md`）に内部変換して解釈。 |
| **MCP設定ファイル** | `.mcp.json` (マニフェスト指定) | ルート直下の `mcp_config.json` |
