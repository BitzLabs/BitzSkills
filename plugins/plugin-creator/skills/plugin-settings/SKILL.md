---
name: plugin-settings
description: Claude Codeプラグインのユーザー設定・状態を .claude/plugin-name.local.md に保存するパターンを支援する。「プラグイン設定を保存したい」「設定可能なプラグインにしたい」「.local.mdファイル」「YAML frontmatterの読み取り」「プロジェクトごとのプラグイン設定」と言われたときに使用する。YAML frontmatter + マークダウン本文による設定管理を扱う。
metadata:
  version: "0.1.0"
  author: br7.hide
  created: "2026-07-05"
  updated: "2026-07-05"
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

### フック（bashスクリプト）から

```bash
#!/bin/bash
set -euo pipefail

# 状態ファイルのパス
STATE_FILE=".claude/my-plugin.local.md"

# ファイルがなければ即終了
if [[ ! -f "$STATE_FILE" ]]; then
  exit 0  # プラグイン未設定。スキップ
fi

# YAML frontmatter をパースする（--- の間）
FRONTMATTER=$(sed -n '/^---$/,/^---$/{ /^---$/d; p; }' "$STATE_FILE")

# 個別フィールドの抽出
ENABLED=$(echo "$FRONTMATTER" | grep '^enabled:' | sed 's/enabled: *//' | sed 's/^"\(.*\)"$/\1/')
STRICT_MODE=$(echo "$FRONTMATTER" | grep '^strict_mode:' | sed 's/strict_mode: *//' | sed 's/^"\(.*\)"$/\1/')

# 有効かどうか確認
if [[ "$ENABLED" != "true" ]]; then
  exit 0  # 無効
fi

# 設定をフックのロジックで使う
if [[ "$STRICT_MODE" == "true" ]]; then
  : # 厳格な検証を適用する
fi
```

完全な例は `examples/read-settings-hook.sh` を参照。

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

### パターン1: 一時的に有効なフック

hooks.json の編集（再起動が必要）なしに、設定ファイルでフックの
有効/無効を切り替える:

```bash
STATE_FILE=".claude/security-scan.local.md"
[[ ! -f "$STATE_FILE" ]] && exit 0

FRONTMATTER=$(sed -n '/^---$/,/^---$/{ /^---$/d; p; }' "$STATE_FILE")
ENABLED=$(echo "$FRONTMATTER" | grep '^enabled:' | sed 's/enabled: *//')
[[ "$ENABLED" != "true" ]] && exit 0

# フックのロジックを実行する
```

### パターン2: エージェントの状態管理

```markdown
---
agent_name: auth-agent
task_number: 3.5
pr_number: 1234
coordinator_session: team-leader
enabled: true
dependencies: ["Task 3.4"]
---

# タスク割り当て

APIのJWT認証を実装する。

**成功基準:** 認証エンドポイント作成 / テストパス / PR作成とCIグリーン
```

フックが frontmatter からコーディネータのセッション名を読んで
通知を送る、といった協調に使う。

### パターン3: 設定駆動の挙動

```markdown
---
validation_level: strict
max_file_size: 1000000
allowed_extensions: [".js", ".ts", ".tsx"]
enable_logging: true
---
```

```bash
LEVEL=$(echo "$FRONTMATTER" | grep '^validation_level:' | sed 's/validation_level: *//')

case "$LEVEL" in
  strict)   : ;; # 厳格な検証
  standard) : ;; # 標準の検証
  lenient)  : ;; # 緩やかな検証
esac
```

## 設定ファイルの作成

コマンドから作成できる: ユーザーの希望を質問 →
`.claude/my-plugin.local.md` を frontmatter 付きで作成 → 保存を通知 →
**フックに反映するには Claude Code の再起動が必要**なことを伝える。
実例は `examples/create-settings-command.md` を参照。

プラグインの README にテンプレートを載せておくのも有効
（`examples/example-settings.md` 参照）。

## ベストプラクティス

### 命名

- ✅ `.claude/plugin-name.local.md` 形式。プラグイン名と一致させ、
  `.local.md` サフィックスを使う
- ❌ `.claude/` 以外のフォルダ、不統一な命名、`.local` なしの `.md`
  （コミットされる恐れ）

### gitignore

必ず `.gitignore` に追加し、README にも書く:

```gitignore
.claude/*.local.md
.claude/*.local.json
```

### デフォルト値

ファイルがないときは賢明なデフォルトを使う:

```bash
if [[ ! -f "$STATE_FILE" ]]; then
  ENABLED=true
  MODE=standard
else
  : # ファイルから読む
fi
```

### 値の検証

```bash
MAX=$(echo "$FRONTMATTER" | grep '^max_value:' | sed 's/max_value: *//')

# 数値範囲の検証
if ! [[ "$MAX" =~ ^[0-9]+$ ]] || [[ $MAX -lt 1 ]] || [[ $MAX -gt 100 ]]; then
  echo "⚠️  設定の max_value が不正です（1〜100）" >&2
  MAX=10  # デフォルトを使う
fi
```

### 再起動の必要性

設定変更のフックへの反映には Claude Code の再起動が必要。
README に「編集 → 保存 → Claude Code 終了 → 再起動」と明記する。

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
