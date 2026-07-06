#!/bin/bash
# PreToolUse フックの例: Write/Edit 操作の検証
# ファイル書き込み検証パターンのデモ

set -euo pipefail

# stdin から入力を読む
input=$(cat)

# ファイルパスを抽出
file_path=$(echo "$input" | jq -r '.tool_input.file_path // empty')

# パスの存在を確認
if [ -z "$file_path" ]; then
  echo '{"continue": true}' # 検証対象のパスなし
  exit 0
fi

# パストラバーサルをチェック
if [[ "$file_path" == *".."* ]]; then
  echo '{"hookSpecificOutput": {"permissionDecision": "deny"}, "systemMessage": "パストラバーサルを検出: '"$file_path"'"}' >&2
  exit 2
fi

# システムディレクトリをチェック
if [[ "$file_path" == /etc/* ]] || [[ "$file_path" == /sys/* ]] || [[ "$file_path" == /usr/* ]]; then
  echo '{"hookSpecificOutput": {"permissionDecision": "deny"}, "systemMessage": "システムディレクトリへの書き込みは不可: '"$file_path"'"}' >&2
  exit 2
fi

# 機微なファイルをチェック
if [[ "$file_path" == *.env ]] || [[ "$file_path" == *secret* ]] || [[ "$file_path" == *credentials* ]]; then
  echo '{"hookSpecificOutput": {"permissionDecision": "ask"}, "systemMessage": "機微な可能性のあるファイルへの書き込み: '"$file_path"'"}' >&2
  exit 2
fi

# 操作を承認
exit 0
