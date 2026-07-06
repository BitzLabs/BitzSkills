---
name: plugin-structure
description: Claude Code / Antigravity 2.0 プラグインのディレクトリ構造・plugin.jsonマニフェスト・コンポーネント（commands/agents/skills/hooks/rules）の自動発見・${CLAUDE_PLUGIN_ROOT}の使い方を案内する。「プラグインを作りたい」「プラグインの構成を知りたい」「plugin.jsonの書き方」「コンポーネントの配置」「自動発見の仕組み」「両対応プラグインにしたい」について聞かれたとき、または新規プラグインの雛形を作るときに使用する。
metadata:
  version: "0.2.0"
  author: br7.hide
  created: "2026-07-05"
  updated: "2026-07-06"
---

# plugin-structure

## 目的

Claude Code / Antigravity 2.0 プラグインの標準ディレクトリ構造と自動発見
（auto-discovery）の仕組みを理解し、整理された保守しやすいプラグインを
設計・作成できるようにする。

**中心概念:**

- 規約に従ったディレクトリ配置による自動発見
- マニフェスト駆動の設定（Claude Code は `.claude-plugin/plugin.json`、
  Antigravity はルートの `plugin.json`。両対応プラグインは**両方を置く**）
- コンポーネント単位の整理（commands / agents / skills / hooks / rules）
- `${CLAUDE_PLUGIN_ROOT}` によるポータブルなパス参照（Claude Code のみ）

## ディレクトリ構造（Claude Code）

```
plugin-name/
├── .claude-plugin/
│   └── plugin.json          # 必須: プラグインマニフェスト
├── commands/                 # スラッシュコマンド（.mdファイル）
├── agents/                   # サブエージェント定義（.mdファイル）
├── skills/                   # エージェントスキル（スキルごとのサブフォルダ）
│   └── skill-name/
│       └── SKILL.md         # 各スキルに必須
├── hooks/
│   └── hooks.json           # イベントハンドラ設定
├── .mcp.json                # MCPサーバー定義
└── scripts/                 # 補助スクリプト
```

**重要なルール:**

1. **マニフェストの位置**: `plugin.json` は必ず `.claude-plugin/` フォルダ内に置く
2. **コンポーネントの位置**: commands / agents / skills / hooks はプラグインの
   **ルート直下**に置く（`.claude-plugin/` の中に入れない）
3. **必要なものだけ作る**: 実際に使うコンポーネントのフォルダだけ作成する
4. **命名規則**: フォルダ名・ファイル名はすべて kebab-case

## ディレクトリ構造（Antigravity 2.0）

Antigravity のプラグインは customization root（プロジェクトの
`.agents/plugins/` またはグローバルの `~/.gemini/config/plugins/`）配下に置く:

```
plugin-name/
├── plugin.json          # 必須: ルート直下（このファイルの存在がプラグインの印）
├── mcp_config.json      # 任意: MCPサーバー定義
├── hooks.json           # 任意: フック（ルート直下。hooks/ フォルダではない）
├── rules/               # 任意: プラグイン有効時にマージされるルール（*.md）
└── skills/              # スキル（Claude Code と同形式）
    └── skill-name/
        └── SKILL.md
```

**Claude Code との主な違い:**

- マニフェストは**ルート直下**の `plugin.json`（`.claude-plugin/` は読まれない）。
  必須フィールドはなく、`name` 省略時はフォルダ名が使われる
- ネイティブのコンポーネントは skills / rules / hooks / MCP。
  `commands/` は agy CLI がインストール時に**スキルへ変換**し、
  `agents/*.md` はサブエージェントとして処理される（Claude 互換レイヤー）
- フックは `hooks.json`（書式も異なる。`hook-development` スキル参照）、
  MCP は `mcp_config.json`（`.mcp.json` は読まれない）
- `${CLAUDE_PLUGIN_ROOT}` に相当する環境変数はない

### 両対応（クロスプラットフォーム）プラグインの作り方

1. **マニフェストを2つ置く**: `.claude-plugin/plugin.json`（Claude Code 用）と
   ルートの `plugin.json`（Antigravity 用）。`version` は常に同じ値に保つ
2. **中核はスキルで作る**: `skills/<name>/SKILL.md` は両プラットフォーム共通
   （Agent Skills 標準）で、最もポータブルなコンポーネント
3. **コマンドは「スキルに変換されても成立する」内容にする**: Claude Code 固有
   機能（`!` bash実行・`${CLAUDE_PLUGIN_ROOT}` 参照）に依存しすぎない
4. **フック・MCP を両対応させる場合はファイルを2系統置く**:
   `hooks/hooks.json` + `.mcp.json`（Claude Code）と
   `hooks.json` + `mcp_config.json`（Antigravity）
5. **両方で検証する**: `claude plugin validate <path>` と
   `agy plugin validate <path>`

配置場所・優先順位・plugins.json による宣言的登録などの詳細は
`references/antigravity-structure.md` を参照。

## マニフェスト（plugin.json / Claude Code）

最小構成は `name` のみ:

```json
{
  "name": "plugin-name"
}
```

配布するなら以下のメタデータを推奨:

```json
{
  "name": "plugin-name",
  "version": "1.0.0",
  "description": "プラグインの目的の簡潔な説明",
  "author": { "name": "作者名", "email": "author@example.com" },
  "homepage": "https://docs.example.com",
  "repository": "https://github.com/user/plugin-name",
  "license": "MIT",
  "keywords": ["testing", "automation"]
}
```

- `name` は kebab-case・インストール済みプラグイン間で一意
- `version` は semver（MAJOR.MINOR.PATCH）
- カスタムパス指定（`commands` / `agents` / `hooks` / `mcpServers` フィールド）は
  デフォルトフォルダを**置き換えず補完する**。パスは `./` 始まりの相対パスのみ

全フィールドの詳細は `references/manifest-reference.md` を参照
（Antigravity 用マニフェストの仕様も同ファイルに記載）。

## コンポーネントの整理

### コマンド（commands/）

`.md` ファイル1つが1コマンド。ファイル名がコマンド名になる
（`review.md` → `/review`）。YAML frontmatter（`description` 等）+ 本文が
実行時の指示になる。詳細は `command-development` スキルが担当。

### エージェント（agents/）

`.md` ファイル1つが1サブエージェント。frontmatter に `description`（いつ使うか）
を書き、本文がシステムプロンプトになる。詳細は `agent-development` スキルが担当。

### スキル（skills/）

スキルごとにサブフォルダを作り、中に `SKILL.md`（必須）を置く。
`scripts/` `references/` `examples/` `assets/` などの補助ファイルを同フォルダに
バンドルできる。詳細は `skill-development` スキルが担当。

```
skills/
└── api-testing/
    ├── SKILL.md
    ├── scripts/test-runner.py
    └── references/api-spec.md
```

### フック（hooks/hooks.json）

イベント（PreToolUse / PostToolUse / Stop / SessionStart 等）に対する
ハンドラを JSON で定義する。プラグイン有効化時に自動登録される。

```json
{
  "PreToolUse": [{
    "matcher": "Write|Edit",
    "hooks": [{
      "type": "command",
      "command": "bash ${CLAUDE_PLUGIN_ROOT}/hooks/scripts/validate.sh",
      "timeout": 30
    }]
  }]
}
```

詳細は `hook-development` スキルが担当。

### MCPサーバー（.mcp.json）

外部サービス連携のための MCP サーバーをプラグインルートの `.mcp.json`
（またはマニフェスト内インライン）で定義する。プラグイン有効化時に自動起動する。
詳細は `mcp-integration` スキルが担当。

## ${CLAUDE_PLUGIN_ROOT}（Claude Code のみ）

Claude Code でプラグイン内のファイルを参照するパスには必ず
`${CLAUDE_PLUGIN_ROOT}` 環境変数を使う。プラグインのインストール先は導入方法・OS・ユーザー設定によって
変わるため、絶対パスの決め打ちは動かなくなる。

**使う場所**: フックのコマンドパス、MCPサーバーの引数、スクリプト実行の参照、
リソースファイルのパス。

**使ってはいけない書き方**:

- 絶対パスの決め打ち（`/Users/name/plugins/...`）
- 作業ディレクトリ基準の相対パス（コマンド内の `./scripts/...`）
- ホームディレクトリ省略記法（`~/plugins/...`）

スクリプト内では環境変数として参照できる:

```bash
#!/bin/bash
source "${CLAUDE_PLUGIN_ROOT}/lib/common.sh"
```

Antigravity には相当する変数がない。フックの cwd は `hooks.json` のある
ディレクトリになるため、相対パスで書く（詳細は `hook-development` スキル）。

## 自動発見の仕組み

プラグイン有効化時に Claude Code は次を自動で読み込む:

1. `.claude-plugin/plugin.json`（マニフェスト）
2. `commands/` 内の `.md` ファイル
3. `agents/` 内の `.md` ファイル
4. `skills/` 内の `SKILL.md` を持つサブフォルダ
5. `hooks/hooks.json` またはマニフェスト内のフック定義
6. `.mcp.json` またはマニフェスト内のMCP定義

変更は次回セッションから反映される。マニフェストのカスタムパスは
デフォルトフォルダに**追加**される（置き換えではない）。

## よくある構成パターン

| パターン | 構成 | 用途 |
| --- | --- | --- |
| 最小 | manifest + commands/ 1ファイル | プロトタイプ・単機能ツール |
| 標準 | commands + agents + skills + hooks | 配布用の本格プラグイン |
| スキル特化 | manifest + skills/ のみ | 知識・手順の提供が主目的 |
| フル装備 | 全コンポーネント + .mcp.json + lib/ | エンタープライズ・多機能 |

具体例は `examples/minimal-plugin.md` / `examples/standard-plugin.md` /
`examples/advanced-plugin.md` を参照。
コンポーネント整理の発展パターンは `references/component-patterns.md` を参照。

## トラブルシューティング

**コンポーネントが読み込まれない**:
正しいフォルダ・拡張子か、frontmatter の YAML が正しいか、スキルのファイル名が
`SKILL.md` か（README.md 等は不可）、プラグインが有効化されているかを確認。

**パス解決エラー**:
決め打ちパスを `${CLAUDE_PLUGIN_ROOT}` に置き換える。マニフェスト内のパスが
`./` 始まりの相対パスかを確認。

**自動発見が働かない**:
コンポーネントフォルダがプラグインルート直下にあるか（`.claude-plugin/` 内は不可）、
命名が規約どおりかを確認し、Claude Code を再起動する。

**プラグイン間の競合**:
一意で説明的なコンポーネント名を使う。必要ならコマンドにプラグイン名の
プレフィックスを付ける。

## ベストプラクティス

- **シンプルに始める**: まずフラット構成にし、必要になってから整理する
- **マニフェストは最小限**: 標準レイアウトなら自動発見に任せ、カスタムパスは
  必要なときだけ指定する
- **一貫した命名**: 関連コンポーネントは名前を揃える（`test-runner` コマンドと
  `test-runner-agent` など）
- **バージョン管理**: リリースごとに `version` を semver で更新する
- **README を置く**: プラグインルートに目的と使い方を書く
