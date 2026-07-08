# 4. 拡張機能とアーキテクチャ (Extensibility & Architecture)

Antigravity 2.0 は柔軟なプラグインシステムを備えており、プロジェクト内の `.agents/` やグローバルディレクトリから多様な拡張を自動発見して読み込みます。

---

## 4.1 Skills (スキル)
スキルは、特定のワークフローや規約に従ってエージェントがタスクを完了するための専門知識の集まりです。Agent Skills オープン規格（[agentskills.io](https://agentskills.io/specification)）に準拠しています。

### 1. 配置場所
*   **ワークスペース**: `<workspace-root>/.agents/skills/<skill-folder>/SKILL.md`
*   **グローバル**: `~/.gemini/config/skills/<skill-folder>/SKILL.md`

### 2. メタデータと動作 (`SKILL.md` の仕様)
スキルフォルダのルートには必ず `SKILL.md` を置きます。このファイルには、スキルの名前、概要、バージョン情報などのメタデータ（通常 Markdown Frontmatter 形式）と、エージェントへの指示本文を記述します。

```markdown
---
name: code-validator
description: 提出前のソースコードに対して構文木検証とセキュリティ脆弱性の検証を行うスキル
version: 1.2.0
---

# code-validator 指示書

このスキルがロードされたとき、あなたは以下の手順に従ってコードを検証しなければなりません。
1. 静的解析ツールを呼び出し、ASTエラーがないかチェックする。
2. セキュリティチェックツールによりOWASP Top 10脆弱性を評価する。
```

### 3. Progressive Disclosure (段階的開示)
エージェントのコンテキスト効率を最大化するための機構です。スキルが多数あっても、起動時にすべての `SKILL.md` 本文がコンテキストに読み込まれるわけではありません。
*   **初期状態**: スキルの `name` と `description` のみがエージェントの利用可能ツール一覧（システムプロンプト内）として提示されます。
*   **トリガー時**: エージェントがタスクの文脈から「このスキルが必要だ」と判断した瞬間（あるいはユーザーが明示的にスキルの使用を促した瞬間）に、初めて `SKILL.md` の本文（詳細指示）が実行時コンテキストへ動的に展開されます。

---

## 4.2 Plugins (プラグイン)
プラグインは、スキル、ルール、フック、MCPサーバーなどを一つのフォルダにパッケージングしたものです。

### 1. ディレクトリ構造
```text
plugins/<plugin_name>/
├── plugin.json       # 必須: マニフェストファイル（この存在がプラグインであることの宣言）
├── mcp_config.json   # 任意: MCPサーバー設定
├── hooks.json        # 任意: ライフサイクルフック
├── rules/            # 任意: *.md（プラグイン有効時にシステムルールへマージ）
└── skills/
    └── <skill_name>/
        └── SKILL.md  # 任意: プラグイン専用スキル
```

### 2. マニフェスト (`plugin.json`)
プラグインのルート直下に配置します。Antigravity においては必須のフィールドはなく、空のオブジェクト `{}` または名前のみの指定でも機能します。

```json
{
  "name": "enterprise-devops-kit",
  "version": "1.0.0",
  "description": "Enterprise CI/CD and linting customizations",
  "author": "BitzLabs Team"
}
```

### 3. 動作ライフサイクル
*   **自動取り込み**: プラグインが有効化されると、内包される `skills/`, `rules/`, `hooks.json`, `mcp_config.json` がすべて自動スキャンされます。
*   **名前空間化**: ツール名やスキル名が他と衝突するのを防ぐため、自動的に `<plugin_name>:<component_name>` のように名前空間がプレフィックスされます。
*   **ライフサイクルスコープ**: フックや MCP サーバーは、そのプラグイン自体が「有効（Enabled）」に設定されている期間中のみ作動します。

### 4. Claude Code 形式との互換レイヤー
`agy plugin validate` / `install` は Claude Code 形式のレイアウトを自動検知し、互換処理を行います。

| Claude Code コンポーネント | Antigravity 2.0 での互換処理・扱い |
| --- | --- |
| `skills/` | そのまま処理される。 |
| `agents/*.md` | サブエージェントとして処理される。 |
| `commands/*.md` | **スキルに変換**されて内部的に処理される。 |
| `hooks/hooks.json` | **検出されない**。プラグイン直下の `hooks.json` への配置が必要。 |
| `.mcp.json` / `mcpServers` | **検出されない**。プラグイン直下の `mcp_config.json` への配置が必要。 |
| `.claude-plugin/plugin.json` | 読み込まれない。プラグイン直下の `plugin.json` が必須。 |

---

## 4.3 Hooks (フック)
ライフサイクルフックにより、エージェントのツール実行前後やモデルの入出力前後に任意の外部スクリプトを割り込ませることができます。

### 1. 配置と書式 (`hooks.json`)
`hooks.json` は、customization root の直下、またはプラグインルートの直下に置きます。トップレベルは「フック名 → 設定オブジェクト」のマップ構造です。

```json
{
  "project-linter": {
    "PostToolUse": [
      {
        "matcher": "run_command",
        "hooks": [
          { "type": "command", "command": "./scripts/lint.sh", "timeout": 10 }
        ]
      }
    ]
  },
  "security-gate": {
    "enabled": true,
    "PreToolUse": [
      {
        "matcher": "run_command",
        "hooks": [
          { "command": "./scripts/safety-check.sh" }
        ]
      }
    ]
  }
}
```

*   `enabled` (任意): `false` に設定することで、そのフック全体を一時的に無効化できます。
*   `matcher` (Pre/PostToolUse で必須): ツール名に対する正規表現（例: `run_command`, `view_file`, `browser_.*`。`*` は全ツール）。
*   `type`: デフォルトは `"command"`。現在は command 起動型フックのみ対応しています。
*   `command`: 実行するシェルコマンド。**実行時のカレントディレクトリ (cwd) は hooks.json が置かれているディレクトリ**になります。

### 2. イベント体系一覧

| イベント名 | 発火タイミング | 設定の構造 |
| --- | --- | --- |
| `PreToolUse` | ツール実行の直前 | グループ形式 (`matcher` + `hooks` 配列) |
| `PostToolUse` | ツール完了の直後 | グループ形式 (`matcher` + `hooks` 配列) |
| `PreInvocation` | LLM モデル呼び出し（推論）の直前 | フラット形式 (ハンドラ配列を直接指定) |
| `PostInvocation` | LLM 推論および全ステップ完了後 | フラット形式 (ハンドラ配列を直接指定) |
| `Stop` | エージェントの実行ループ終了時 | フラット形式 (ハンドラ配列を直接指定) |

### 3. 入出力 JSON 契約 (camelCase 仕様)
フックとして起動されたスクリプトは、**標準入力 (stdin)** から JSON データを読み込み、処理結果を **標準出力 (stdout)** に JSON 形式で出力してエージェントに返します。JSON のキーは **camelCase** で統一されています。

#### 共通入力パラメータ
```json
{
  "conversationId": "ec33ebf9-abcd-1234-efgh-567890abcdef",
  "workspacePaths": ["/path/to/workspace"],
  "transcriptPath": "/path/to/workspace/.gemini/antigravity/transcript.jsonl",
  "artifactDirectoryPath": "/path/to/workspace/.gemini/antigravity/artifacts",
  "modelName": "auto"
}
```

#### イベント別の挙動・入出力

##### A. `PreToolUse`
*   **追加入力**: `toolCall.name` (実行予定のツール名), `toolCall.args` (引数), `stepIdx` (現在のステップ番号)
*   **期待する出力**:
    ```json
    {
      "decision": "ask",
      "reason": "テストの実行にはユーザーの明示的同意が必要です",
      "permissionOverrides": ["command(npm test)"]
    }
    ```
    *   `decision` (必須):
        *   `"allow"`: ユーザー確認なしで自動実行を許可。
        *   `"deny"`: ツールの実行を即座にブロックして失敗扱いにします。
        *   `"ask"`: ユーザーに確認プロンプトを表示（キャッシュされた Always Allow 設定があれば従う）。
        *   `"force_ask"`: Always Allow キャッシュを無視し、必ずユーザー確認を行います。

##### B. `PostToolUse`
*   **追加入力**: `stepIdx`、ツールが失敗した場合は `error` 文字列。
*   **期待する出力**: 空の JSON オブジェクト `{}`。

##### C. `PreInvocation` / `PostInvocation`
*   **追加入力**: `invocationNum` (LLM呼び出し回数), `initialNumSteps` (初期ステップ数)
*   **期待する出力**:
    ```json
    {
      "injectSteps": [
        { "ephemeralMessage": "注意: 変更内容に認証キーが含まれていないか確認してください。" }
      ],
      "terminationBehavior": "force_continue"
    }
    ```
    *   `injectSteps`: 途中で割り込ませるメッセージやツールコール。`ephemeralMessage`（一時的なシステムプロンプトメッセージ）を挿入できます。
    *   `terminationBehavior` (PostInvocation のみ): `"force_continue"`（エージェントループの継続を強制）または `"terminate"`（終了を強制）。

##### D. `Stop`
*   **追加入力**: `executionNum`, `terminationReason` (`model_stop` / `max_steps_exceeded` / `error`), `error` (エラー内容), `fullyIdle` (実行キューの空き状況)
*   **期待する出力**:
    ```json
    {
      "decision": "continue",
      "reason": "バックグラウンドの非同期処理が未完了のため処理を継続します"
    }
    ```
    *   `decision` を `"continue"` にすると、ループの終了を防ぎ再実行させることができます。その際 `reason` がシステムメッセージとしてエージェントに入力されます。

---

## 4.4 Tools (ツール) と MCP 統合

### 1. 組み込みツール (Built-in Tools)
Antigravity Runtime は、デフォルトで以下のセキュアな基礎ツールを内包しています。

*   **`run_command`**: 指定されたシェルコマンドをユーザーのワークスペース内で実行します。実行前に `PreToolUse` フックによる介入やポリシー適用が行われます。
*   **`view_file`**: 指定されたファイルのコンテンツを読み込みます。
*   **`browser_.*`（例: `browser_page` など）**: エージェントがWebブラウジングを行い、外部ドキュメントの参照やWebアプリケーションのレンダリング結果の検証、動的なページの確認を実行します。

### 2. MCP サーバー接続方式の比較

| 方式 | 通信プロトコル | 認証方法 | 主なユースケース | 特徴・レイテンシ |
| --- | --- | --- | --- | --- |
| **stdio** | 標準入出力 (stdin/stdout) | 環境変数 / 引数 | ローカルスクリプト、同梱DB、CLI | 最小レイテンシ、ローカル完結 |
| **SSE** | Server-Sent Events + HTTP | OAuth / カスタムヘッダー | クラウドサービス (Git, Asana) | 中レイテンシ、自動再接続サポート |
| **HTTP** | RESTful HTTP POST/GET | APIトークンヘッダー | ステートレス外部 API 連携 | 中レイテンシ、ステートレス |
| **WebSocket** | 永続双方向 WebSocket | APIトークンヘッダー | 双方向ストリーミング、低遅延同期 | 低レイテンシ、双方向通信 |

### 3. 設定書式 (`mcp_config.json`)
マニフェストと同じく、customization root またはプラグイン直下に配置します。

```json
{
  "mcpServers": {
    "local-helper": {
      "command": "node",
      "args": ["${CLAUDE_PLUGIN_ROOT}/servers/helper.js"],
      "env": {
        "DB_PATH": "${WORKSPACE_ROOT}/db.sqlite"
      }
    },
    "external-service": {
      "type": "sse",
      "url": "https://api.example.com/mcp/sse",
      "headers": {
        "Authorization": "Bearer ${SECRET_TOKEN}"
      }
    }
  }
}
```

### 4. ツール命名規則
MCP を通じて提供されるツールの名称は、以下のルールで自動的に一意の名前空間へとマッピングされます。
```
mcp__plugin_<plugin_name>_<server_name>__<tool_name>
```
*   **例**: プラグイン名 `asana-sync` 内の MCP サーバー `asana` が提供する `create_task` ツールは、`mcp__plugin_asanasync_asana__create_task` としてエージェントから呼び出し可能になります。

---

## 4.5 Subagents (サブエージェント)
サブエージェントは、特定の専門業務（コードレビュー、テスト生成、APIドキュメント作成など）をこなすための自律的な作業ユニットです。

### 1. 設計と配置
プラグインの `agents/` ディレクトリ配下に Markdown 形式（例: `agents/pr-reviewer.md`）で定義します。

### 2. トリガー構造とメタデータ
ファイルの先頭に Frontmatter 形式で定義し、特にトリガー条件となる `description` の中には `<example>` ブロックと判定解説 (`<commentary>`) を記述します。

```markdown
---
name: pr-reviewer
description: プルリクエストの作成時や、コード品質のチェックを要求されたときにこのエージェントを使用する。例:

<example>
Context: ユーザーが新しいモジュールを追加し、レビューを求めたとき
user: "追加した認証ロジックをレビューして"
assistant: "pr-reviewer エージェントで認証ロジックのレビューを行います。"
<commentary>
コード変更に対する明示的なレビュー要求があるため、pr-reviewer エージェントをトリガーする。
</commentary>
</example>

model: inherit
color: blue
---

# システムプロンプト (指示本文)
あなたは卓越したコードレビュアーです。以下の手順に従ってレビューを実施してください...
```
*   **`model: inherit`**: メインセッションで使用しているLLMモデル設定をそのまま引き継ぐ指示です。
*   **`<commentary>`**: エージェントがこのサブエージェントを起動するかどうかを自律判定する際の「思考判断基準」を LLM に学習させるための重要なブロックです。
