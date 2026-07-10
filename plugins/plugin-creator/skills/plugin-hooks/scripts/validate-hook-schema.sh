#!/bin/bash
# フックスキーマバリデータ
# hooks.json の構造を検証し、よくある問題をチェックする

set -euo pipefail

# 使い方
if [ $# -eq 0 ]; then
  echo "使い方: $0 <path/to/hooks.json>"
  echo ""
  echo "検証項目:"
  echo "  - JSON構文の妥当性"
  echo "  - 必須フィールド"
  echo "  - フック種別の妥当性"
  echo "  - matcherパターン"
  echo "  - timeoutの範囲"
  exit 1
fi

HOOKS_FILE="$1"

if [ ! -f "$HOOKS_FILE" ]; then
  echo "❌ エラー: ファイルが見つかりません: $HOOKS_FILE"
  exit 1
fi

echo "🔍 フック設定を検証中: $HOOKS_FILE"
echo ""

# チェック1: 有効なJSONか
echo "JSON構文を確認中..."
if ! jq empty "$HOOKS_FILE" 2>/dev/null; then
  echo "❌ JSON構文が不正です"
  exit 1
fi
echo "✅ 有効なJSON"

# チェック2: ルート構造
echo ""
echo "ルート構造を確認中..."
VALID_EVENTS=("PreToolUse" "PostToolUse" "UserPromptSubmit" "Stop" "SubagentStop" "SessionStart" "SessionEnd" "PreCompact" "Notification")

for event in $(jq -r 'keys[]' "$HOOKS_FILE"); do
  found=false
  for valid_event in "${VALID_EVENTS[@]}"; do
    if [ "$event" = "$valid_event" ]; then
      found=true
      break
    fi
  done

  if [ "$found" = false ]; then
    echo "⚠️  不明なイベント種別: $event"
  fi
done
echo "✅ ルート構造は正常"

# チェック3: 各フックの検証
echo ""
echo "個々のフックを検証中..."

error_count=0
warning_count=0

for event in $(jq -r 'keys[]' "$HOOKS_FILE"); do
  hook_count=$(jq -r ".\"$event\" | length" "$HOOKS_FILE")

  for ((i=0; i<hook_count; i++)); do
    # matcher の存在確認
    matcher=$(jq -r ".\"$event\"[$i].matcher // empty" "$HOOKS_FILE")
    if [ -z "$matcher" ]; then
      echo "❌ $event[$i]: 'matcher' フィールドがありません"
      ((error_count++))
      continue
    fi

    # hooks 配列の存在確認
    hooks=$(jq -r ".\"$event\"[$i].hooks // empty" "$HOOKS_FILE")
    if [ -z "$hooks" ] || [ "$hooks" = "null" ]; then
      echo "❌ $event[$i]: 'hooks' 配列がありません"
      ((error_count++))
      continue
    fi

    # 配列内の各フックを検証
    hook_array_count=$(jq -r ".\"$event\"[$i].hooks | length" "$HOOKS_FILE")

    for ((j=0; j<hook_array_count; j++)); do
      hook_type=$(jq -r ".\"$event\"[$i].hooks[$j].type // empty" "$HOOKS_FILE")

      if [ -z "$hook_type" ]; then
        echo "❌ $event[$i].hooks[$j]: 'type' フィールドがありません"
        ((error_count++))
        continue
      fi

      if [ "$hook_type" != "command" ] && [ "$hook_type" != "prompt" ]; then
        echo "❌ $event[$i].hooks[$j]: 不正なtype '$hook_type'（'command' または 'prompt'）"
        ((error_count++))
        continue
      fi

      # 種別固有フィールドの確認
      if [ "$hook_type" = "command" ]; then
        command=$(jq -r ".\"$event\"[$i].hooks[$j].command // empty" "$HOOKS_FILE")
        if [ -z "$command" ]; then
          echo "❌ $event[$i].hooks[$j]: commandフックには 'command' フィールドが必要です"
          ((error_count++))
        else
          # ハードコードされたパスの検出
          if [[ "$command" == /* ]] && [[ "$command" != *'${CLAUDE_PLUGIN_ROOT}'* ]]; then
            echo "⚠️  $event[$i].hooks[$j]: 絶対パスの決め打ちを検出。\${CLAUDE_PLUGIN_ROOT} の使用を検討してください"
            ((warning_count++))
          fi
        fi
      elif [ "$hook_type" = "prompt" ]; then
        prompt=$(jq -r ".\"$event\"[$i].hooks[$j].prompt // empty" "$HOOKS_FILE")
        if [ -z "$prompt" ]; then
          echo "❌ $event[$i].hooks[$j]: promptフックには 'prompt' フィールドが必要です"
          ((error_count++))
        fi

        # プロンプトフックが対応イベントで使われているか
        if [ "$event" != "Stop" ] && [ "$event" != "SubagentStop" ] && [ "$event" != "UserPromptSubmit" ] && [ "$event" != "PreToolUse" ]; then
          echo "⚠️  $event[$i].hooks[$j]: promptフックは $event では完全対応でない可能性があります（Stop, SubagentStop, UserPromptSubmit, PreToolUse が最適）"
          ((warning_count++))
        fi
      fi

      # timeout の確認
      timeout=$(jq -r ".\"$event\"[$i].hooks[$j].timeout // empty" "$HOOKS_FILE")
      if [ -n "$timeout" ] && [ "$timeout" != "null" ]; then
        if ! [[ "$timeout" =~ ^[0-9]+$ ]]; then
          echo "❌ $event[$i].hooks[$j]: timeoutは数値である必要があります"
          ((error_count++))
        elif [ "$timeout" -gt 600 ]; then
          echo "⚠️  $event[$i].hooks[$j]: timeout ${timeout}秒 は非常に長いです（最大600秒）"
          ((warning_count++))
        elif [ "$timeout" -lt 5 ]; then
          echo "⚠️  $event[$i].hooks[$j]: timeout ${timeout}秒 は非常に短いです"
          ((warning_count++))
        fi
      fi
    done
  done
done

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
