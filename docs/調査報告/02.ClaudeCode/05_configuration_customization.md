# 5. 設定項目とカスタマイズ (Configuration & Customization)

## 5.1 設定の階層構造と優先順位 (Settings Hierarchy)
Claude Code は、起動時に以下の順序で設定をマージします。優先度の高い（Managed / CLI）設定は、優先度の低い（User）設定を上書きします。

1. **Managed Policies** (最優先)
   - `/etc/claude-code/policies.json` や `managed-settings.json` など、企業の管理者によって配置されるグローバルポリシー。
2. **CLI Flags**
   - 起動時に指定された `--model` や `--disallowed-tools` などの引数。
3. **Project Settings (Local)**
   - プロジェクトフォルダ内の `.claude/settings.local.json`。通常 gitignore に指定して個人用のローカル上書き設定として使います。
4. **Project Settings (Shared)**
   - プロジェクトフォルダ内の `.claude/settings.json`。Git 経由で共有され、チーム全体に適用されます。
5. **User Settings (Global)**
   - ユーザーのホームディレクトリ配下 `~/.claude/settings.json`。そのマシン上で動くすべてのセッションに適用されます。

## 5.2 settings.json の主要設定項目
設定ファイルでは、動作オプションや環境変数を定義できます。

```json
{
  "theme": "dark",
  "verbose": false,
  "env": {
    "ANTHROPIC_MODEL": "claude-sonnet-5",
    "DISABLE_TELEMETRY": "1",
    "BASH_DEFAULT_TIMEOUT_MS": "60000"
  }
}
```

- **`theme`**: `dark` または `light`。
- **`verbose`**: 詳細ログの出力。
- **`env`**: プロセス内で有効にする環境変数のキーバリュー。

> [!NOTE]
> 一部の資料で紹介される `telemetry` / `maxThinkingTokens` といったトップレベルキーは、一次情報（公式ドキュメント）では確認できていません。**テレメトリの無効化は `env.DISABLE_TELEMETRY="1"` が公式手段**です。推論トークンの制御が必要な場合も、トップレベルキーではなく環境変数経由の設定を確認してください。

## 5.3 設定の変更方法
設定を変更するには以下のいずれかのアプローチを取ります。

### 1. インタラクティブ変更
セッション中に `/config` コマンドを実行して設定用の TUI（Terminal UI）を開きます。
また、直接 `/config key=value` を実行することで、UI を開かずに素早く値を上書きすることも可能です。
```bash
project-root > /config verbose=true
```

### 2. 手動編集
プロジェクトの `.claude/settings.json` またはグローバルの `~/.claude/settings.json` を任意のテキストエディタで直接編集します。

## 5.4 独自のプラグイン設定パターン (local.md駆動)
フックやコマンド、サブエージェントなどから参照できる、プロジェクト固有の動的設定ファイルパターンです。

### 設定ファイル: `.claude/[plugin-name].local.md`
YAML frontmatter とマークダウン本文を組み合わせたファイルを用意します。
```markdown
---
enabled: true
strict_mode: true
max_file_size: 500000
---

# プロジェクトメモ
ここに書かれたテキストは、フックやコマンドから必要に応じて読み取られ、
Claude へのコンテキスト注入用のプロンプトとして使用されます。
```

### 読み取りスクリプトの例 (Bash)
```bash
#!/bin/bash
set -euo pipefail

# 1. 状態ファイルの存在チェック
STATE_FILE=".claude/my-plugin.local.md"
if [[ ! -f "$STATE_FILE" ]]; then
  # Google Antigravity 向けに .agents/ パスもフォールバック探索
  STATE_FILE=".agents/my-plugin.local.md"
fi

if [[ ! -f "$STATE_FILE" ]]; then
  exit 0 # 設定ファイルなし。デフォルトで動作
fi

# 2. YAML frontmatter の抽出
FRONTMATTER=$(sed -n '/^---$/,/^---$/{ /^---$/d; p; }' "$STATE_FILE")

# 3. フィールドのパース
ENABLED=$(echo "$FRONTMATTER" | grep '^enabled:' | sed 's/enabled: *//' | sed 's/^"\(.*\)"$/\1/')
STRICT_MODE=$(echo "$FRONTMATTER" | grep '^strict_mode:' | sed 's/strict_mode: *//' | sed 's/^"\(.*\)"$/\1/')

if [[ "$ENABLED" != "true" ]]; then
  exit 0 # プラグインが無効化されている
fi

# 4. マークダウン本文の抽出 (必要に応じて使用)
BODY=$(awk '/^---$/{i++; next} i>=2' "$STATE_FILE")
```

このパターンは、ユーザーが容易にテキストエディタで設定を編集でき、かつ Git に含めないローカルファイルとして非常に扱いやすいため、Claude Code プラグイン開発で広く採用されています。
