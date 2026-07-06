# plugin.json マニフェスト リファレンス

`plugin.json` の全フィールドの詳細リファレンス。

## ファイルの位置

**必須パス**: `.claude-plugin/plugin.json`

マニフェストはプラグインルートの `.claude-plugin/` フォルダ内に置く。
この位置にないと Claude Code はプラグインとして認識しない。

## コアフィールド

### name（必須）

**型**: 文字列 / **形式**: kebab-case

プラグインの一意な識別子。プラグインの識別、他プラグインとの競合検出、
コマンドの名前空間（任意）に使われる。

**要件**:

- インストール済みプラグイン全体で一意
- 英小文字・数字・ハイフンのみ。スペース・特殊文字は不可
- 先頭は英字、末尾は英字または数字

**検証パターン**: `/^[a-z][a-z0-9]*(-[a-z0-9]+)*$/`

- ✅ 良い例: `api-tester`, `code-review`, `git-workflow-automation`
- ❌ 悪い例: `API Tester`, `code_review`, `-git-workflow`, `test-`

### version

**型**: 文字列 / **形式**: semver（MAJOR.MINOR.PATCH） / **省略時**: `"0.1.0"`

- **MAJOR**: 互換性を壊す変更
- **MINOR**: 後方互換のある機能追加
- **PATCH**: 後方互換のあるバグ修正

プレリリース版は `"1.0.0-alpha.1"` / `"1.0.0-beta.2"` / `"1.0.0-rc.1"` の形式。

### description

**型**: 文字列 / **推奨長**: 50〜200文字

プラグインの目的と機能の簡潔な説明。「どうやるか」ではなく「何をするか」を
能動的に書き、マーケットプレイス表示を考慮して200文字以内に収める。

- ✅ 「コード解析とカバレッジレポートから網羅的なテストスイートを生成する」
- ❌ 「テスト関係のことを手伝うプラグインです」

## メタデータフィールド

### author

**型**: オブジェクト（`name` 必須、`email` / `url` 任意）または文字列

```json
{
  "author": {
    "name": "Jane Developer",
    "email": "jane@example.com",
    "url": "https://janedeveloper.com"
  }
}
```

文字列形式も可: `"Jane Developer <jane@example.com> (https://janedeveloper.com)"`

### homepage

**型**: 文字列（URL）

ドキュメントサイトや利用ガイドへのリンク。ソースコードは `repository` を使う。

### repository

**型**: 文字列（URL）またはオブジェクト

```json
{ "repository": "https://github.com/user/plugin-name" }
```

詳細形式:

```json
{
  "repository": {
    "type": "git",
    "url": "https://github.com/user/plugin-name.git",
    "directory": "packages/plugin-name"
  }
}
```

### license

**型**: 文字列 / **形式**: SPDX 識別子

よく使うもの: `"MIT"`, `"Apache-2.0"`, `"GPL-3.0"`, `"BSD-3-Clause"`, `"ISC"`,
`"UNLICENSED"`（プロプライエタリ）。一覧は https://spdx.org/licenses/ 。
複数ライセンスは `"(MIT OR Apache-2.0)"` のように書く。

### keywords

**型**: 文字列の配列

プラグインの発見・分類に使うタグ。5〜10個を目安に、機能カテゴリ
（`testing`, `debugging`）、技術名（`typescript`, `docker`）、ワークフロー
（`ci-cd`, `code-review`）を混ぜる。プラグイン名の重複は避ける。

## コンポーネントパスフィールド

### commands

**型**: 文字列または文字列の配列 / **デフォルト**: `["./commands"]`

コマンド定義を含む追加のフォルダまたはファイル。

```json
{
  "commands": ["./commands", "./admin-commands", "./experimental-commands"]
}
```

**挙動**: デフォルトの `commands/` を**置き換えず補完**する。

### agents

**型**: 文字列または文字列の配列 / **デフォルト**: `["./agents"]`

エージェント定義を含む追加パス。形式・挙動は `commands` と同じ。

### hooks

**型**: 文字列（JSONファイルへのパス）またはオブジェクト（インライン定義）
**デフォルト**: `"./hooks/hooks.json"`

```json
{ "hooks": "./config/hooks.json" }
```

インライン定義も可（50行未満の単純な構成向け）:

```json
{
  "hooks": {
    "PreToolUse": [{
      "matcher": "Write",
      "hooks": [{
        "type": "command",
        "command": "bash ${CLAUDE_PLUGIN_ROOT}/scripts/validate.sh",
        "timeout": 30
      }]
    }]
  }
}
```

### mcpServers

**型**: 文字列（JSONファイルへのパス）またはオブジェクト（インライン定義）
**デフォルト**: `./.mcp.json`

```json
{
  "mcpServers": {
    "github": {
      "command": "node",
      "args": ["${CLAUDE_PLUGIN_ROOT}/servers/github-mcp.js"],
      "env": { "GITHUB_TOKEN": "${GITHUB_TOKEN}" }
    }
  }
}
```

サーバーが複数あるなら外部ファイル（`.mcp.json`）に分ける。

## パス解決

### 相対パスのルール

1. **相対パスのみ**（絶対パス不可）
2. **`./` で始める**（プラグインルート基準を示す）
3. **`../` は使えない**（親フォルダへの遡りは不可）
4. **スラッシュのみ**（Windowsでもバックスラッシュ不可）

- ✅ `"./commands"`, `"./src/commands"`, `"./configs/hooks.json"`
- ❌ `"/Users/name/plugin/commands"`, `"commands"`, `"../shared/commands"`, `".\\commands"`

### 解決順序

1. **デフォルトフォルダ**を先にスキャン（`./commands/`, `./agents/`,
   `./skills/`, `./hooks/hooks.json`, `./.mcp.json`）
2. **カスタムパス**（マニフェストで指定したもの）をスキャン
3. **マージ**: すべての場所のコンポーネントが登録される。上書きはなく、
   名前の衝突はエラーになる

## バリデーション

Claude Code はプラグイン読み込み時にマニフェストを検証する:

- JSON として正しくパースできるか、フィールドの型が正しいか
- `name` の存在と形式、`version` の semver 準拠
- パスが `./` 始まりの相対パスか、URL が妥当か
- 参照先のパスが実在するか、フック/MCP設定が妥当か

### よくあるエラーと修正

| エラー | 修正 |
| --- | --- |
| `"name": "My Plugin"`（スペース） | `"my-plugin"` に変更 |
| `"commands": "/abs/path"`（絶対パス） | `"./commands"` に変更 |
| `"hooks": "hooks/hooks.json"`（`./` なし） | `"./hooks/hooks.json"` に変更 |
| `"version": "1.0"`（semver でない） | `"1.0.0"` に変更 |

コマンドラインでの検証: `claude plugin validate <path>`

## 構成例

### 最小

```json
{ "name": "hello-world" }
```

自動発見に全面的に依存する。

### 配布向け（推奨）

```json
{
  "name": "code-review-assistant",
  "version": "1.0.0",
  "description": "スタイルチェックと改善提案でコードレビューを自動化する",
  "author": { "name": "Jane Developer", "email": "jane@example.com" },
  "homepage": "https://docs.example.com/code-review",
  "repository": "https://github.com/janedev/code-review-assistant",
  "license": "MIT",
  "keywords": ["code-review", "automation", "quality", "ci-cd"]
}
```

### フル構成

```json
{
  "name": "enterprise-devops",
  "version": "2.3.1",
  "description": "エンタープライズCI/CDパイプラインの包括的なDevOps自動化",
  "author": {
    "name": "DevOps Team",
    "email": "devops@company.com",
    "url": "https://company.com/devops"
  },
  "homepage": "https://docs.company.com/plugins/devops",
  "repository": { "type": "git", "url": "https://github.com/company/devops-plugin.git" },
  "license": "Apache-2.0",
  "keywords": ["devops", "ci-cd", "automation", "kubernetes", "docker"],
  "commands": ["./commands", "./admin-commands"],
  "agents": "./specialized-agents",
  "hooks": "./config/hooks.json",
  "mcpServers": "./.mcp.json"
}
```

## ベストプラクティス

- **version は必ず入れる**: 変更の追跡と更新判定に必要
- **デフォルトパスを使う**: カスタムパスは本当に必要なときだけ。使う場合は
  README で理由を説明する
- **変更したら version を bump**: semver に従う
- **配布前にメタデータを完成させる**: description / author / license / keywords
  を埋め、LICENSE ファイルと README を同梱し、クリーンインストールで動作確認する
