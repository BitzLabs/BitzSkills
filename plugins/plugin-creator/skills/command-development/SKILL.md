---
name: command-development
description: Claude Codeのスラッシュコマンド（commands/*.md）の作成を支援する。「スラッシュコマンドを作りたい」「コマンドを追加したい」「コマンドの引数を定義したい」「frontmatterの書き方」「対話的なコマンド」と言われたときや、コマンド構造・動的引数・ファイル参照・bash実行・コマンド整理の指針が必要なときに使用する。
metadata:
  version: "0.1.0"
  author: br7.hide
  created: "2026-07-05"
  updated: "2026-07-05"
---

# command-development

## 目的

スラッシュコマンドは、マークダウンファイルとして定義された「よく使うプロンプト」
であり、対話セッション中に呼び出して実行する。コマンド構造・frontmatter・
動的機能を理解することで、強力で再利用可能なワークフローを作れる。

## 最重要原則: コマンドは「Claudeへの指示」

**コマンドは人間向けではなくエージェント向けに書く。**

ユーザーが `/command-name` を実行すると、コマンドの内容がそのまま Claude への
指示になる。「ユーザーへの説明」ではなく「Claude への指令」として書くこと。

```markdown
✅ 正しい（Claudeへの指示）:
このコードのセキュリティ脆弱性をレビューする:
- SQLインジェクション
- XSS攻撃
具体的な行番号と重大度を提示する。

❌ 間違い（ユーザーへの説明）:
このコマンドはコードのセキュリティ問題をレビューします。
脆弱性の詳細レポートが得られます。
```

## コマンドの配置場所

| 種類 | 場所 | スコープ | /help での表示 |
| --- | --- | --- | --- |
| プロジェクト | `.claude/commands/` | そのプロジェクトのみ | (project) |
| 個人 | `~/.claude/commands/` | 全プロジェクト | (user) |
| プラグイン | `plugin-name/commands/` | プラグイン導入時 | (plugin-name) |

## ファイル形式

`.md` ファイル1つが1コマンド（`review.md` → `/review`）。
シンプルなコマンドは frontmatter なしの本文だけでよい。
設定が必要なら YAML frontmatter を付ける:

```markdown
---
description: コードのセキュリティ問題をレビューする
allowed-tools: Read, Grep, Bash(git:*)
model: sonnet
---

このコードのセキュリティ脆弱性をレビューする...
```

## frontmatter フィールド

| フィールド | 目的 | 例 |
| --- | --- | --- |
| `description` | `/help` に表示される説明（60文字以内推奨） | `PRのコード品質をレビューする` |
| `allowed-tools` | コマンドが使えるツールの指定 | `Read, Write, Bash(git:*)` |
| `model` | 実行モデルの指定 | `haiku`（軽量）/ `sonnet` / `opus`（複雑な分析） |
| `argument-hint` | 引数の補完ヒント | `[pr-number] [priority]` |
| `disable-model-invocation` | モデルからの自動呼び出しを禁止 | `true` |

全フィールドの詳細は `references/frontmatter-reference.md` を参照。

## 動的引数

### $ARGUMENTS（全引数を1つの文字列で）

```markdown
---
argument-hint: [issue-number]
---

イシュー #$ARGUMENTS をコーディング規約に従って修正する。
```

`/fix-issue 123` → 「イシュー #123 を…修正する」

### 位置引数（$1, $2, $3, …）

```markdown
---
argument-hint: [pr-number] [priority] [assignee]
---

PR #$1 を優先度 $2 でレビューする。
レビュー後、フォローアップを $3 に割り当てる。
```

`/review-pr 123 high alice` → 各プレースホルダが展開される。

## ファイル参照（@構文）

`@パス` でファイル内容をコマンドに含める:

```markdown
---
argument-hint: [file-path]
---

@$1 を以下の観点でレビューする:
- コード品質
- ベストプラクティス
- 潜在的なバグ
```

複数参照（`@src/old.js と @src/new.js を比較する`）や、
固定ファイルの参照（`@package.json と @tsconfig.json の整合性を確認する`）も可能。

## bash実行によるコンテキスト収集

コマンド内でインラインの bash を実行し、Claude が処理する前に動的な
コンテキスト（git の状態、環境情報など）を集められる。

```markdown
---
allowed-tools: Read, Bash(git:*)
---

変更ファイル: !`git diff --name-only`

各ファイルについてコード品質・バグ・テストカバレッジをレビューする。
```

正確な構文と注意点は `references/plugin-features-reference.md` の
bash実行セクションを参照。

## プラグイン固有の機能

### ${CLAUDE_PLUGIN_ROOT}

プラグインのコマンドからは `${CLAUDE_PLUGIN_ROOT}`（プラグインの絶対パス）が
使える。プラグイン内のスクリプト実行・設定読み込み・テンプレート参照に必ず
これを使う:

```markdown
# プラグインスクリプトの実行
!`bash ${CLAUDE_PLUGIN_ROOT}/scripts/script.sh`

# プラグイン設定の読み込み
@${CLAUDE_PLUGIN_ROOT}/config/settings.json

# プラグインテンプレートの利用
@${CLAUDE_PLUGIN_ROOT}/templates/report.md
```

### 名前空間

`commands/` のサブフォルダは名前空間になる
（`commands/utils/helper.md` → `/helper (plugin:plugin-name:utils)`）。

### 他コンポーネントとの連携

- **エージェント連携**: 「code-reviewer エージェントで詳細分析を行う」のように
  本文でエージェント名を指示すると、Claude が Task ツールで起動する
- **スキル連携**: 本文でスキル名に言及するとスキルが読み込まれる
- **フック連携**: コマンドが状態を準備し、フックがツールイベントで自動処理する

複数コンポーネントを組み合わせた多段ワークフローの例は
`references/advanced-workflows.md` と `examples/plugin-commands.md` を参照。

## バリデーションパターン

処理前に入力とリソースを検証する:

```markdown
環境の検証: !`echo "$1" | grep -E "^(dev|staging|prod)$" || echo "INVALID"`

$1 が有効な環境なら: $1 へデプロイする
そうでなければ: 有効な環境（dev / staging / prod）と使い方を説明する
```

ファイル存在チェック（`test -f $1 && echo "EXISTS" || echo "MISSING"`）、
プラグインリソース検証、エラーハンドリング
（`... 2>&1 || echo "BUILD_FAILED"`）も同様のパターンで書ける。

## ベストプラクティス

- **単一責務**: 1コマンド1タスク
- **明確な description**: `/help` だけで内容がわかるように
- **引数を文書化**: `argument-hint` を必ず付ける
- **命名は動詞-名詞**: `review-pr`, `fix-issue`
- **bashのスコープを絞る**: `Bash(git:*)` を使い `Bash(*)` を避ける
- **破壊的操作を避ける**: コマンド内の bash は安全なものに限定する
- **エッジケースを考慮**: 引数欠落・無効値への対応を本文に書く

## トラブルシューティング

- **コマンドが出てこない**: 配置フォルダ・`.md` 拡張子・frontmatter の
  YAML 構文を確認し、Claude Code を再起動する
- **引数が展開されない**: `$1` `$2` の構文と `argument-hint` の整合を確認する
- **bash実行が失敗する**: `allowed-tools` に Bash が含まれるか、コマンドを
  ターミナルで単体テストしたかを確認する
- **ファイル参照が働かない**: `@` 構文・パスの妥当性・Read ツールの許可を確認する

## 追加リソース

### リファレンス

- **`references/frontmatter-reference.md`** — frontmatter 全フィールド詳細
- **`references/plugin-features-reference.md`** — bash実行・${CLAUDE_PLUGIN_ROOT}・プラグイン機能
- **`references/interactive-commands.md`** — AskUserQuestion を使う対話的コマンド
- **`references/advanced-workflows.md`** — 多段・複数コンポーネントのワークフロー
- **`references/documentation-patterns.md`** — コマンドの文書化パターン
- **`references/testing-strategies.md`** — コマンドのテスト戦略
- **`references/marketplace-considerations.md`** — 配布時の考慮事項

### 実例

- **`examples/simple-commands.md`** — 基本的なコマンド例集
- **`examples/plugin-commands.md`** — プラグイン機能を使うコマンド例集
