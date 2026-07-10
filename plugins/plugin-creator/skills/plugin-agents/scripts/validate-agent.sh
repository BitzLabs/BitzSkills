#!/bin/bash
# エージェントファイルバリデータ
# エージェントのマークダウンファイルの構造と内容を検証する

set -euo pipefail

# 使い方
if [ $# -eq 0 ]; then
  echo "使い方: $0 <path/to/agent.md>"
  echo ""
  echo "検証項目:"
  echo "  - YAML frontmatter の構造"
  echo "  - 必須フィールド (name, description, model, color)"
  echo "  - フィールドの形式と制約"
  echo "  - システムプロンプトの存在と長さ"
  echo "  - description 内の <example> ブロック"
  exit 1
fi

AGENT_FILE="$1"

echo "🔍 エージェントファイルを検証中: $AGENT_FILE"
echo ""

# チェック1: ファイルの存在
if [ ! -f "$AGENT_FILE" ]; then
  echo "❌ ファイルが見つかりません: $AGENT_FILE"
  exit 1
fi
echo "✅ ファイルが存在します"

# チェック2: --- で始まるか
FIRST_LINE=$(head -1 "$AGENT_FILE")
if [ "$FIRST_LINE" != "---" ]; then
  echo "❌ ファイルは YAML frontmatter (---) で始まる必要があります"
  exit 1
fi
echo "✅ frontmatter で始まっています"

# チェック3: 閉じの --- があるか
if ! tail -n +2 "$AGENT_FILE" | grep -q '^---$'; then
  echo "❌ frontmatter が閉じられていません（2つ目の --- がない）"
  exit 1
fi
echo "✅ frontmatter が正しく閉じられています"

# frontmatter とシステムプロンプトを抽出
FRONTMATTER=$(sed -n '/^---$/,/^---$/{ /^---$/d; p; }' "$AGENT_FILE")
SYSTEM_PROMPT=$(awk '/^---$/{i++; next} i>=2' "$AGENT_FILE")

# チェック4: 必須フィールド
echo ""
echo "必須フィールドを確認中..."

error_count=0
warning_count=0

# name フィールド
NAME=$(echo "$FRONTMATTER" | grep '^name:' | sed 's/name: *//' | sed 's/^"\(.*\)"$/\1/')

if [ -z "$NAME" ]; then
  echo "❌ 必須フィールドがありません: name"
  ((error_count++))
else
  echo "✅ name: $NAME"

  # 形式の検証
  if ! [[ "$NAME" =~ ^[a-zA-Z0-9][a-zA-Z0-9-]*[a-zA-Z0-9]$ ]]; then
    echo "❌ name は英数字で始まり英数字で終わり、英字・数字・ハイフンのみ使用可能です"
    ((error_count++))
  fi

  # 長さの検証
  name_length=${#NAME}
  if [ $name_length -lt 3 ]; then
    echo "❌ name が短すぎます（最低3文字）"
    ((error_count++))
  elif [ $name_length -gt 50 ]; then
    echo "❌ name が長すぎます（最大50文字）"
    ((error_count++))
  fi

  # 汎用的すぎる名前のチェック
  if [[ "$NAME" =~ ^(helper|assistant|agent|tool)$ ]]; then
    echo "⚠️  name が汎用的すぎます: $NAME"
    ((warning_count++))
  fi
fi

# description フィールド
DESCRIPTION=$(echo "$FRONTMATTER" | grep '^description:' | sed 's/description: *//')

if [ -z "$DESCRIPTION" ]; then
  echo "❌ 必須フィールドがありません: description"
  ((error_count++))
else
  desc_length=${#DESCRIPTION}
  echo "✅ description: ${desc_length} 文字"

  if [ $desc_length -lt 10 ]; then
    echo "⚠️  description が短すぎます（最低10文字推奨）"
    ((warning_count++))
  elif [ $desc_length -gt 5000 ]; then
    echo "⚠️  description が非常に長いです（5000文字超）"
    ((warning_count++))
  fi

  # <example> ブロックの有無
  if ! echo "$DESCRIPTION" | grep -q '<example>'; then
    echo "⚠️  description にはトリガー用の <example> ブロックを含めるべきです"
    ((warning_count++))
  fi

  # 「使用する」パターンの有無
  if ! echo "$DESCRIPTION" | grep -qiE 'use this agent when|エージェントを使用' ; then
    echo "⚠️  description は「〜のときにこのエージェントを使用する」で始めるべきです"
    ((warning_count++))
  fi
fi

# model フィールド
MODEL=$(echo "$FRONTMATTER" | grep '^model:' | sed 's/model: *//')

if [ -z "$MODEL" ]; then
  echo "❌ 必須フィールドがありません: model"
  ((error_count++))
else
  echo "✅ model: $MODEL"

  case "$MODEL" in
    inherit|sonnet|opus|haiku)
      # 有効なモデル
      ;;
    *)
      echo "⚠️  不明なmodel: $MODEL（有効: inherit, sonnet, opus, haiku）"
      ((warning_count++))
      ;;
  esac
fi

# color フィールド
COLOR=$(echo "$FRONTMATTER" | grep '^color:' | sed 's/color: *//')

if [ -z "$COLOR" ]; then
  echo "❌ 必須フィールドがありません: color"
  ((error_count++))
else
  echo "✅ color: $COLOR"

  case "$COLOR" in
    blue|cyan|green|yellow|magenta|red)
      # 有効な色
      ;;
    *)
      echo "⚠️  不明なcolor: $COLOR（有効: blue, cyan, green, yellow, magenta, red）"
      ((warning_count++))
      ;;
  esac
fi

# tools フィールド（任意）
TOOLS=$(echo "$FRONTMATTER" | grep '^tools:' | sed 's/tools: *//')

if [ -n "$TOOLS" ]; then
  echo "✅ tools: $TOOLS"
else
  echo "💡 tools: 未指定（エージェントは全ツールにアクセス可能）"
fi

# チェック5: システムプロンプト
echo ""
echo "システムプロンプトを確認中..."

if [ -z "$SYSTEM_PROMPT" ]; then
  echo "❌ システムプロンプトが空です"
  ((error_count++))
else
  prompt_length=${#SYSTEM_PROMPT}
  echo "✅ システムプロンプト: $prompt_length 文字"

  if [ $prompt_length -lt 20 ]; then
    echo "❌ システムプロンプトが短すぎます（最低20文字）"
    ((error_count++))
  elif [ $prompt_length -gt 10000 ]; then
    echo "⚠️  システムプロンプトが非常に長いです（10,000文字超）"
    ((warning_count++))
  fi

  # 二人称のチェック
  if ! echo "$SYSTEM_PROMPT" | grep -qE "You are|You will|Your|あなたは|あなたの"; then
    echo "⚠️  システムプロンプトは二人称（あなたは〜）で書くべきです"
    ((warning_count++))
  fi

  # 構造のチェック
  if ! echo "$SYSTEM_PROMPT" | grep -qiE "responsibilities|process|steps|責務|プロセス|手順"; then
    echo "💡 明確な責務またはプロセスの手順の追加を検討してください"
  fi

  if ! echo "$SYSTEM_PROMPT" | grep -qiE "output|出力"; then
    echo "💡 出力形式の定義を検討してください"
  fi
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ $error_count -eq 0 ] && [ $warning_count -eq 0 ]; then
  echo "✅ 全チェックをパスしました！"
  exit 0
elif [ $error_count -eq 0 ]; then
  echo "⚠️  警告 ${warning_count} 件付きで検証をパスしました"
  exit 0
else
  echo "❌ 検証失敗: エラー ${error_count} 件、警告 ${warning_count} 件"
  exit 1
fi
