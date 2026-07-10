#!/bin/bash
# PreToolUse フックの例: Bash コマンドの検証
# bashコマンド検証パターンのデモ

set -euo pipefail

# stdin から入力を読む
input=$(cat)

# コマンドを抽出
command=$(echo "$input" | jq -r '.tool_input.command // empty')

# コマンドの存在を確認
if [ -z "$command" ]; then
  echo '{"continue": true}' # 検証対象のコマンドなし
  exit 0
fi

# 明らかに安全なコマンドは即時承認
if [[ "$command" =~ ^(ls|pwd|echo|date|whoami)(\s|$) ]]; then
  exit 0
fi

# 破壊的な操作をチェック
if [[ "$command" == *"rm -rf"* ]] || [[ "$command" == *"rm -fr"* ]]; then
  echo '{"hookSpecificOutput": {"permissionDecision": "deny"}, "systemMessage": "危険なコマンドを検出: rm -rf"}' >&2
  exit 2
fi

# その他の危険なコマンドをチェック
if [[ "$command" == *"dd if="* ]] || [[ "$command" == *"mkfs"* ]] || [[ "$command" == *"> /dev/"* ]]; then
  echo '{"hookSpecificOutput": {"permissionDecision": "deny"}, "systemMessage": "危険なシステム操作を検出"}' >&2
  exit 2
fi

# 権限昇格をチェック
if [[ "$command" == sudo* ]] || [[ "$command" == su* ]]; then
  echo '{"hookSpecificOutput": {"permissionDecision": "ask"}, "systemMessage": "コマンドは昇格した権限を要求しています"}' >&2
  exit 2
fi

# 操作を承認
exit 0
