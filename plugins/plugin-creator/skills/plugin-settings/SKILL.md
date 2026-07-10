---
name: plugin-settings
description: プラグインのユーザー設定・状態を .claude/plugin-name.local.md に保存するパターンを支援する。「プラグイン設定を保存したい」「設定可能なプラグインにしたい」「.local.mdファイル」「YAML frontmatterの読み取り」「プロジェクトごとのプラグイン設定」と言われたときに使用する。YAML frontmatter + マークダウン本文による設定管理を扱う（Claude Code の慣習だが Antigravity 2.0 にも応用可能）。
metadata:
  version: "0.3.0"
  author: br7.hide
  created: "2026-07-05"
  updated: "2026-07-11"
---

# plugin-settings

## 目的

プラグインはユーザー設定・状態をプロジェクト内の
`.claude/plugin-name.local.md` に保存できる。YAML frontmatter で構造化
設定を、マークダウン本文でプロンプトや補足コンテキストを持つ。

**特徴:**

- **場所**: プロジェクトルートの `.claude/plugin-name.local.md`
- **構造**: YAML frontmatter + マークダウン本文
- **目的**: プロジェクト単位のプラグイン設定・状態
- **利用**: フック・コマンド・エージェントから読む
- **ライフサイクル**: ユーザー管理（gitに入れない。`.gitignore` に追加する）

`.claude/` 配下に置くのは Claude Code の慣習。Antigravity 2.0 に公式の
プラグイン設定機構はないため、両対応プラグインで同パターンを使う場合は
`.agents/plugin-name.local.md` など**プラットフォーム側の root** に置き、
読み取りスクリプトが両方のパスを順に探すようにする。

## ファイル構造

```markdown
---
enabled: true
setting1: value1
numeric_setting: 42
list_setting: ["item1", "item2"]
---

# 補足コンテキスト

マークダウン本文には以下を書ける:
- タスクの説明
- 追加の指示
- Claude にフィードバックするプロンプト
- ドキュメントやメモ
```

## 設定ファイルの読み取り

フックからbashで読み取る完全な例は `references/hook-reading-example.md` を参照。

### コマンド・エージェントから

コマンドは Read ツールで設定を読み、frontmatter をパースして挙動を
カスタマイズする。エージェントはシステムプロンプトに
「`.claude/my-plugin.local.md` があれば frontmatter をパースし、
enabled / mode 等に応じて挙動を変える」と書いておく。

## パース技法（要点）

```bash
# frontmatter の抽出（--- の間）
FRONTMATTER=$(sed -n '/^---$/,/^---$/{ /^---$/d; p; }' "$FILE")

# 文字列フィールド（クォート除去付き）
VALUE=$(echo "$FRONTMATTER" | grep '^field_name:' | sed 's/field_name: *//' | sed 's/^"\(.*\)"$/\1/')

# 真偽値: [[ "$ENABLED" == "true" ]] で比較
# 数値: [[ $MAX -gt 100 ]] で比較

# マークダウン本文の抽出（2つ目の --- の後）
BODY=$(awk '/^---$/{i++; next} i>=2' "$FILE")
```

詳細は `references/parsing-techniques.md` を参照。

## よくあるパターン

一時的に有効なフック・エージェントの状態管理・設定駆動の挙動の実例は
`references/common-patterns.md` を参照。

## 設定ファイルの作成

コマンドから作成できる: ユーザーの希望を質問 →
`.claude/my-plugin.local.md` を frontmatter 付きで作成 → 保存を通知 →
**フックに反映するには Claude Code の再起動が必要**なことを伝える。
実例は `examples/create-settings-command.md` を参照。

プラグインの README にテンプレートを載せておくのも有効
（`examples/example-settings.md` 参照）。

## ベストプラクティス

命名規則・gitignore・デフォルト値・値の検証・再起動の必要性の詳細は
`references/best-practices-details.md` を参照。

## セキュリティ

- **ユーザー入力のサニタイズ**: 設定ファイルへ書くときはクォートを
  エスケープする（`sed 's/"/\\"/g'`）
- **パスの検証**: 設定にファイルパスが含まれる場合は `..` を拒否する
- **パーミッション**: ユーザーのみ読める（`chmod 600`）、gitに入れない、
  ユーザー間で共有しない

## 実例

**multi-agent-swarm プラグイン**: エージェント名・タスク番号・PR番号・
コーディネータセッションを保存し、Stop フックが frontmatter を読んで
コーディネータへ tmux 通知を送る。`enabled: true/false` で即座に
有効/無効を切り替えられる。

**ralph-wiggum プラグイン**: `iteration` / `max_iterations` /
`completion_promise` を frontmatter に、本文にループで再投入する
プロンプトを保存する。Stop フックがループ制御に使う。

詳細は `references/real-world-examples.md` を参照。

## 追加リソース

### リファレンス

- **`references/hook-reading-example.md`** — フックからの設定読み取りの完全な例
- **`references/common-patterns.md`** — よくある設定パターン集
- **`references/best-practices-details.md`** — ベストプラクティスの詳細
- **`references/parsing-techniques.md`** — frontmatter・本文パースの完全ガイド
- **`references/real-world-examples.md`** — 実プラグインの実装詳解

### 実例

- **`examples/read-settings-hook.sh`** — 設定を読んで使うフック
- **`examples/create-settings-command.md`** — 設定ファイルを作るコマンド
- **`examples/example-settings.md`** — 設定ファイルのテンプレート

### スクリプト

- **`scripts/validate-settings.sh`** — 設定ファイルの構造検証
- **`scripts/parse-frontmatter.sh`** — frontmatter フィールドの抽出

## 実装ワークフロー

1. 設定スキーマを設計する（フィールド・型・デフォルト）
2. プラグインのドキュメントにテンプレートを載せる
3. `.claude/*.local.md` の gitignore エントリを追加する
4. フック・コマンドに設定パースを実装する
5. quick-exit パターンを使う（ファイル存在 → enabled を確認）
6. README にテンプレート付きで設定を文書化する
7. 変更には再起動が必要なことをユーザーに伝える

設定はシンプルに保ち、ファイルがないときの良いデフォルトを用意すること。
