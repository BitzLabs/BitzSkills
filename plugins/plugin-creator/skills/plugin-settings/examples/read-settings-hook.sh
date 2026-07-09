#!/bin/bash
# .claude/my-plugin.local.md からプラグイン設定を読むフックの例
# 設定駆動のフック挙動の完全なパターンを示す

set -euo pipefail

# 設定ファイルのパス
SETTINGS_FILE=".claude/my-plugin.local.md"

# 設定ファイルがなければ即終了
if [[ ! -f "$SETTINGS_FILE" ]]; then
  # プラグイン未設定 — デフォルトを使うかスキップ
  exit 0
fi

# YAML frontmatter をパースする（--- の間）
FRONTMATTER=$(sed -n '/^---$/,/^---$/{ /^---$/d; p; }' "$SETTINGS_FILE")

# 設定フィールドの抽出
ENABLED=$(echo "$FRONTMATTER" | grep '^enabled:' | sed 's/enabled: *//' | sed 's/^"\(.*\)"$/\1/')
STRICT_MODE=$(echo "$FRONTMATTER" | grep '^strict_mode:' | sed 's/strict_mode: *//' | sed 's/^"\(.*\)"$/\1/')
MAX_SIZE=$(echo "$FRONTMATTER" | grep '^max_file_size:' | sed 's/max_file_size: *//')

# 無効なら即終了
if [[ "$ENABLED" != "true" ]]; then
  exit 0
fi

# フック入力を読む
input=$(cat)
file_path=$(echo "$input" | jq -r '.tool_input.file_path // empty')

# 設定された検証を適用する
if [[ "$STRICT_MODE" == "true" ]]; then
  # 厳格モード: 全チェックを適用
  if [[ "$file_path" == *".."* ]]; then
    echo '{"hookSpecificOutput": {"permissionDecision": "deny"}, "systemMessage": "パストラバーサルをブロック（厳格モード）"}' >&2
    exit 2
  fi

  if [[ "$file_path" == *".env"* ]] || [[ "$file_path" == *"secret"* ]]; then
    echo '{"hookSpecificOutput": {"permissionDecision": "deny"}, "systemMessage": "機微なファイルをブロック（厳格モード）"}' >&2
    exit 2
  fi
else
  # 標準モード: 基本チェックのみ
  if [[ "$file_path" == "/etc/"* ]] || [[ "$file_path" == "/sys/"* ]]; then
    echo '{"hookSpecificOutput": {"permissionDecision": "deny"}, "systemMessage": "システムパスをブロック"}' >&2
    exit 2
  fi
fi

# 設定されていればファイルサイズをチェック
if [[ -n "$MAX_SIZE" ]] && [[ "$MAX_SIZE" =~ ^[0-9]+$ ]]; then
  content=$(echo "$input" | jq -r '.tool_input.content // empty')
  content_size=${#content}

  if [[ $content_size -gt $MAX_SIZE ]]; then
    echo '{"hookSpecificOutput": {"permissionDecision": "deny"}, "systemMessage": "設定された上限サイズを超過: '"$MAX_SIZE"' バイト"}' >&2
    exit 2
  fi
fi

# 全チェックをパス
exit 0
