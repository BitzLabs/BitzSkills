# よくあるフックパターン集

Claude Code フックの実績あるパターン集。典型的なユースケースの
出発点として使う。

## パターン1: セキュリティ検証

プロンプトベースフックで危険なファイル書き込みをブロックする:

```json
{
  "PreToolUse": [
    {
      "matcher": "Write|Edit",
      "hooks": [
        {
          "type": "prompt",
          "prompt": "ファイルパス: $TOOL_INPUT.file_path。検証する: 1) /etc やシステムディレクトリでないこと 2) .env や認証情報でないこと 3) パスに '..' トラバーサルがないこと。'approve' または 'deny' を返す。"
        }
      ]
    }
  ]
}
```

**用途:** 機微なファイル・システムディレクトリへの書き込み防止。

## パターン2: テストの強制

停止前にテスト実行を保証する:

```json
{
  "Stop": [
    {
      "matcher": "*",
      "hooks": [
        {
          "type": "prompt",
          "prompt": "トランスクリプトをレビューする。コードが変更されていたら（Write/Editツールが使われていたら）、テストが実行されたか検証する。テストが実行されていなければ、理由「コード変更後はテストが必須」でブロックする。"
        }
      ]
    }
  ]
}
```

**用途:** 品質基準の強制と作業の中途半端な終了の防止。

## パターン3: コンテキスト読み込み

セッション開始時にプロジェクト固有のコンテキストを読み込む:

```json
{
  "SessionStart": [
    {
      "matcher": "*",
      "hooks": [
        {
          "type": "command",
          "command": "bash ${CLAUDE_PLUGIN_ROOT}/scripts/load-context.sh"
        }
      ]
    }
  ]
}
```

スクリプトはプロジェクト種別を検出して `$CLAUDE_ENV_FILE` に環境変数を
書く（完全な例は `examples/load-context.sh`）。

## パターン4: 通知ログ

監査・分析のために全通知を記録する:

```json
{
  "Notification": [
    {
      "matcher": "*",
      "hooks": [
        {
          "type": "command",
          "command": "bash ${CLAUDE_PLUGIN_ROOT}/scripts/log-notification.sh"
        }
      ]
    }
  ]
}
```

## パターン5: MCPツールの監視

破壊的なMCP操作から保護する:

```json
{
  "PreToolUse": [
    {
      "matcher": "mcp__.*__delete.*",
      "hooks": [
        {
          "type": "prompt",
          "prompt": "削除操作を検出。検証する: この削除は意図的か？ 取り消せるか？ バックアップはあるか？ 安全な場合のみ 'approve' を返す。"
        }
      ]
    }
  ]
}
```

## パターン6: ビルド検証

コード変更後にビルドが通っているか確認する:

```json
{
  "Stop": [
    {
      "matcher": "*",
      "hooks": [
        {
          "type": "prompt",
          "prompt": "コードが変更されたか確認する。Write/Editツールが使われていたら、プロジェクトがビルドされたか（npm run build, cargo build 等）検証する。ビルドされていなければブロックしてビルドを要求する。"
        }
      ]
    }
  ]
}
```

## パターン7: 権限確認

危険な操作の前にユーザーへ確認する:

```json
{
  "PreToolUse": [
    {
      "matcher": "Bash",
      "hooks": [
        {
          "type": "prompt",
          "prompt": "コマンド: $TOOL_INPUT.command。'rm'・'delete'・'drop' 等の破壊的操作を含むなら、ユーザー確認のため 'ask' を返す。そうでなければ 'approve'。"
        }
      ]
    }
  ]
}
```

## パターン8: コード品質チェック

ファイル編集時にリンタ・フォーマッタを走らせる:

```json
{
  "PostToolUse": [
    {
      "matcher": "Write|Edit",
      "hooks": [
        {
          "type": "command",
          "command": "bash ${CLAUDE_PLUGIN_ROOT}/scripts/check-quality.sh"
        }
      ]
    }
  ]
}
```

```bash
#!/bin/bash
input=$(cat)
file_path=$(echo "$input" | jq -r '.tool_input.file_path')

# 該当する拡張子ならリンタを実行する
if [[ "$file_path" == *.js ]] || [[ "$file_path" == *.ts ]]; then
  npx eslint "$file_path" 2>&1 || true
fi
```

## パターンの組み合わせ

複数パターンを組み合わせて多層防御と自動化を実現する:

```json
{
  "PreToolUse": [
    { "matcher": "Write|Edit", "hooks": [{ "type": "prompt", "prompt": "ファイル書き込みの安全性を検証する" }] },
    { "matcher": "Bash", "hooks": [{ "type": "prompt", "prompt": "bashコマンドの安全性を検証する" }] }
  ],
  "Stop": [
    { "matcher": "*", "hooks": [{ "type": "prompt", "prompt": "テスト実行とビルド成功を検証する" }] }
  ],
  "SessionStart": [
    { "matcher": "*", "hooks": [{ "type": "command", "command": "bash ${CLAUDE_PLUGIN_ROOT}/scripts/load-context.sh" }] }
  ]
}
```

## パターン9: 一時的に有効なフック

フラグファイルで明示的に有効化されたときだけ動くフック:

```bash
#!/bin/bash
# フラグファイルがあるときだけ有効
FLAG_FILE="$CLAUDE_PROJECT_DIR/.enable-security-scan"

if [ ! -f "$FLAG_FILE" ]; then
  # 無効時は即終了
  exit 0
fi

# フラグあり。検証を実行する
input=$(cat)
file_path=$(echo "$input" | jq -r '.tool_input.file_path')

security-scanner "$file_path"
```

有効化/無効化:

```bash
touch .enable-security-scan   # 有効化
rm .enable-security-scan      # 無効化
```

**用途:** 一時的なデバッグフック、開発用フィーチャーフラグ、
オプトインの検証、必要なときだけの重い検査。

**注意:** フラグファイルの作成/削除後もフック自体の設定変更には
Claude Code の再起動が必要（フラグの判定はスクリプト実行時に行われる）。

## パターン10: 設定駆動フック

JSON設定でフックの挙動を制御する:

```bash
#!/bin/bash
CONFIG_FILE="$CLAUDE_PROJECT_DIR/.claude/my-plugin.local.json"

# 設定を読む
if [ -f "$CONFIG_FILE" ]; then
  strict_mode=$(jq -r '.strictMode // false' "$CONFIG_FILE")
  max_file_size=$(jq -r '.maxFileSize // 1000000' "$CONFIG_FILE")
else
  # デフォルト
  strict_mode=false
  max_file_size=1000000
fi

# strict モードでなければスキップ
if [ "$strict_mode" != "true" ]; then
  exit 0
fi

# 設定された制限を適用する
input=$(cat)
file_size=$(echo "$input" | jq -r '.tool_input.content | length')

if [ "$file_size" -gt "$max_file_size" ]; then
  echo '{"decision": "deny", "reason": "ファイルが設定されたサイズ上限を超えています"}' >&2
  exit 2
fi
```

設定ファイル（`.claude/my-plugin.local.json`）:

```json
{
  "strictMode": true,
  "maxFileSize": 500000,
  "allowedPaths": ["/tmp", "/home/user/projects"]
}
```

**用途:** ユーザー設定可能なフック挙動、プロジェクト別設定、
チーム固有ルール、動的な検証基準。
