#!/bin/bash
# フックテストヘルパー
# サンプル入力でフックをテストし、出力を表示する

set -euo pipefail

# 使い方
show_usage() {
  echo "使い方: $0 [options] <hook-script> <test-input.json>"
  echo ""
  echo "オプション:"
  echo "  -h, --help      このヘルプを表示"
  echo "  -v, --verbose   詳細な実行情報を表示"
  echo "  -t, --timeout N タイムアウト秒数を指定（既定: 60）"
  echo ""
  echo "例:"
  echo "  $0 validate-bash.sh test-input.json"
  echo "  $0 -v -t 30 validate-write.sh write-input.json"
  echo ""
  echo "サンプル入力の生成:"
  echo "  $0 --create-sample <event-type>"
  exit 0
}

# サンプル入力の生成
create_sample() {
  event_type="$1"

  case "$event_type" in
    PreToolUse)
      cat <<'EOF'
{
  "session_id": "test-session",
  "transcript_path": "/tmp/transcript.txt",
  "cwd": "/tmp/test-project",
  "permission_mode": "ask",
  "hook_event_name": "PreToolUse",
  "tool_name": "Write",
  "tool_input": {
    "file_path": "/tmp/test.txt",
    "content": "Test content"
  }
}
EOF
      ;;
    PostToolUse)
      cat <<'EOF'
{
  "session_id": "test-session",
  "transcript_path": "/tmp/transcript.txt",
  "cwd": "/tmp/test-project",
  "permission_mode": "ask",
  "hook_event_name": "PostToolUse",
  "tool_name": "Bash",
  "tool_result": "Command executed successfully"
}
EOF
      ;;
    Stop|SubagentStop)
      cat <<'EOF'
{
  "session_id": "test-session",
  "transcript_path": "/tmp/transcript.txt",
  "cwd": "/tmp/test-project",
  "permission_mode": "ask",
  "hook_event_name": "Stop",
  "reason": "Task appears complete"
}
EOF
      ;;
    UserPromptSubmit)
      cat <<'EOF'
{
  "session_id": "test-session",
  "transcript_path": "/tmp/transcript.txt",
  "cwd": "/tmp/test-project",
  "permission_mode": "ask",
  "hook_event_name": "UserPromptSubmit",
  "user_prompt": "Test user prompt"
}
EOF
      ;;
    SessionStart|SessionEnd)
      cat <<'EOF'
{
  "session_id": "test-session",
  "transcript_path": "/tmp/transcript.txt",
  "cwd": "/tmp/test-project",
  "permission_mode": "ask",
  "hook_event_name": "SessionStart"
}
EOF
      ;;
    *)
      echo "不明なイベント種別: $event_type"
      echo "有効な種別: PreToolUse, PostToolUse, Stop, SubagentStop, UserPromptSubmit, SessionStart, SessionEnd"
      exit 1
      ;;
  esac
}

# 引数のパース
VERBOSE=false
TIMEOUT=60

while [ $# -gt 0 ]; do
  case "$1" in
    -h|--help)
      show_usage
      ;;
    -v|--verbose)
      VERBOSE=true
      shift
      ;;
    -t|--timeout)
      TIMEOUT="$2"
      shift 2
      ;;
    --create-sample)
      create_sample "$2"
      exit 0
      ;;
    *)
      break
      ;;
  esac
done

if [ $# -ne 2 ]; then
  echo "エラー: 必須の引数がありません"
  echo ""
  show_usage
fi

HOOK_SCRIPT="$1"
TEST_INPUT="$2"

# 入力の検証
if [ ! -f "$HOOK_SCRIPT" ]; then
  echo "❌ エラー: フックスクリプトが見つかりません: $HOOK_SCRIPT"
  exit 1
fi

if [ ! -x "$HOOK_SCRIPT" ]; then
  echo "⚠️  警告: スクリプトに実行権限がありません。bash経由で実行します..."
  HOOK_SCRIPT="bash $HOOK_SCRIPT"
fi

if [ ! -f "$TEST_INPUT" ]; then
  echo "❌ エラー: テスト入力が見つかりません: $TEST_INPUT"
  exit 1
fi

# テスト入力のJSON検証
if ! jq empty "$TEST_INPUT" 2>/dev/null; then
  echo "❌ エラー: テスト入力が有効なJSONではありません"
  exit 1
fi

echo "🧪 フックをテスト中: $HOOK_SCRIPT"
echo "📥 入力: $TEST_INPUT"
echo ""

if [ "$VERBOSE" = true ]; then
  echo "入力JSON:"
  jq . "$TEST_INPUT"
  echo ""
fi

# 環境のセットアップ
export CLAUDE_PROJECT_DIR="${CLAUDE_PROJECT_DIR:-/tmp/test-project}"
export CLAUDE_PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(pwd)}"
export CLAUDE_ENV_FILE="${CLAUDE_ENV_FILE:-/tmp/test-env-$$}"

if [ "$VERBOSE" = true ]; then
  echo "環境変数:"
  echo "  CLAUDE_PROJECT_DIR=$CLAUDE_PROJECT_DIR"
  echo "  CLAUDE_PLUGIN_ROOT=$CLAUDE_PLUGIN_ROOT"
  echo "  CLAUDE_ENV_FILE=$CLAUDE_ENV_FILE"
  echo ""
fi

# フックの実行
echo "▶️  フックを実行中（タイムアウト: ${TIMEOUT}秒）..."
echo ""

start_time=$(date +%s)

set +e
output=$(timeout "$TIMEOUT" bash -c "cat '$TEST_INPUT' | $HOOK_SCRIPT" 2>&1)
exit_code=$?
set -e

end_time=$(date +%s)
duration=$((end_time - start_time))

# 結果の分析
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "結果:"
echo ""
echo "終了コード: $exit_code"
echo "実行時間: ${duration}秒"
echo ""

case $exit_code in
  0)
    echo "✅ フックは承認/成功しました"
    ;;
  2)
    echo "🚫 フックはブロック/拒否しました"
    ;;
  124)
    echo "⏱️  フックは ${TIMEOUT}秒 でタイムアウトしました"
    ;;
  *)
    echo "⚠️  フックが予期しない終了コードを返しました: $exit_code"
    ;;
esac

echo ""
echo "出力:"
if [ -n "$output" ]; then
  echo "$output"
  echo ""

  # JSONとしてパースを試みる
  if echo "$output" | jq empty 2>/dev/null; then
    echo "パース済みJSON出力:"
    echo "$output" | jq .
  fi
else
  echo "（出力なし）"
fi

# 環境ファイルの確認
if [ -f "$CLAUDE_ENV_FILE" ]; then
  echo ""
  echo "環境ファイルが作成されました:"
  cat "$CLAUDE_ENV_FILE"
  rm -f "$CLAUDE_ENV_FILE"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ $exit_code -eq 0 ] || [ $exit_code -eq 2 ]; then
  echo "✅ テスト完了"
  exit 0
else
  echo "❌ テスト失敗"
  exit 1
fi
