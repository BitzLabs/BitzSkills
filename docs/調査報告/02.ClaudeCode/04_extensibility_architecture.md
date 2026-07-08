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
フックはエージェントのアクションやセッションイベントに反応して実行されるスクリプトまたはプロンプトです。プラグインの `hooks/hooks.json` で構成します。

### イベントとタイミング
- **`PreToolUse`**: ツールが実行される直前に介入し、入力の検証や実行許可の判断を行います。
- **`PostToolUse`**: ツールの実行直後にフィードバックを挿入します。
- **`UserPromptSubmit`**: ユーザーがプロンプトを入力した瞬間にコンテキストを追加します。
- **`Stop`**: エージェントが処理を完了し停止する前に介入し、ビルドやテストが正常に通っているか最終確認を行います。
- **`SessionStart` / `SessionEnd`**: セッション開始時の環境変数永続化（`$CLAUDE_ENV_FILE` 経由）やクリーンアップ。

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
| **フック種別** | command および prompt | command のみ |
| **フックイベント** | 9種類 | 5種類 (`PreToolUse`, `PostToolUse`, `PreInvocation`, `PostInvocation`, `Stop`) |
| **Stopフック挙動** | `decision: "block"` で停止防止 | `decision: "continue"` で停止防止（ループ継続） |
| **コマンドファイル** | `/commands` 配下。そのまま解釈。 | スキル（`SKILL.md`）に内部変換して解釈。 |
| **MCP設定ファイル** | `.mcp.json` (マニフェスト指定) | ルート直下の `mcp_config.json` |
