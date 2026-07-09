#!/bin/bash
# フックリンタ
# フックスクリプトのよくある問題とベストプラクティス違反をチェックする

set -euo pipefail

# 使い方
if [ $# -eq 0 ]; then
  echo "使い方: $0 <hook-script.sh> [hook-script2.sh ...]"
  echo ""
  echo "検査項目:"
  echo "  - shebang の有無"
  echo "  - set -euo pipefail の使用"
  echo "  - stdin からの入力読み取り"
  echo "  - 適切なエラー処理"
  echo "  - 変数のクォート"
  echo "  - 終了コードの使用"
  echo "  - ハードコードされたパス"
  echo "  - 長時間実行の可能性"
  exit 1
fi

check_script() {
  local script="$1"
  local warnings=0
  local errors=0

  echo "🔍 リント中: $script"
  echo ""

  if [ ! -f "$script" ]; then
    echo "❌ エラー: ファイルが見つかりません"
    return 1
  fi

  # チェック1: 実行権限
  if [ ! -x "$script" ]; then
    echo "⚠️  実行権限がありません（chmod +x $script）"
    ((warnings++))
  fi

  # チェック2: shebang
  first_line=$(head -1 "$script")
  if [[ ! "$first_line" =~ ^#!/ ]]; then
    echo "❌ shebang がありません（#!/bin/bash）"
    ((errors++))
  fi

  # チェック3: set -euo pipefail
  if ! grep -q "set -euo pipefail" "$script"; then
    echo "⚠️  'set -euo pipefail' がありません（安全のため推奨）"
    ((warnings++))
  fi

  # チェック4: stdin からの読み取り
  if ! grep -q "cat\|read" "$script"; then
    echo "⚠️  stdin から入力を読んでいないようです"
    ((warnings++))
  fi

  # チェック5: JSONパースに jq を使っているか
  if grep -q "tool_input\|tool_name" "$script" && ! grep -q "jq" "$script"; then
    echo "⚠️  フック入力をパースしているのに jq を使っていません"
    ((warnings++))
  fi

  # チェック6: クォートされていない変数
  if grep -E '\$[A-Za-z_][A-Za-z0-9_]*[^"]' "$script" | grep -v '#' | grep -q .; then
    echo "⚠️  クォートされていない変数の可能性（インジェクションリスク）"
    echo "   必ずダブルクォートを使う: \"\$variable\""
    ((warnings++))
  fi

  # チェック7: ハードコードされたパス
  if grep -E '^[^#]*/home/|^[^#]*/usr/|^[^#]*/opt/' "$script" | grep -q .; then
    echo "⚠️  絶対パスの決め打ちを検出"
    echo "   \$CLAUDE_PROJECT_DIR または \$CLAUDE_PLUGIN_ROOT を使う"
    ((warnings++))
  fi

  # チェック8: CLAUDE_PLUGIN_ROOT の使用
  if ! grep -q "CLAUDE_PLUGIN_ROOT\|CLAUDE_PROJECT_DIR" "$script"; then
    echo "💡 ヒント: プラグイン相対パスには \$CLAUDE_PLUGIN_ROOT を使う"
  fi

  # チェック9: 終了コード
  if ! grep -q "exit 0\|exit 2" "$script"; then
    echo "⚠️  明示的な終了コードがありません（0 または 2 で終了すべき）"
    ((warnings++))
  fi

  # チェック10: 判定フックのJSON出力
  if grep -q "PreToolUse\|Stop" "$script"; then
    if ! grep -q "permissionDecision\|decision" "$script"; then
      echo "💡 ヒント: PreToolUse/Stop フックは判定JSONを出力すべき"
    fi
  fi

  # チェック11: 長時間実行のコード
  if grep -E 'sleep [0-9]{3,}|while true' "$script" | grep -v '#' | grep -q .; then
    echo "⚠️  長時間実行の可能性があるコードを検出"
    echo "   フックは素早く完了すべき（60秒未満）"
    ((warnings++))
  fi

  # チェック12: エラーメッセージのstderr出力
  if grep -q 'echo.*".*error\|Error\|denied\|Denied\|エラー\|拒否' "$script"; then
    if ! grep -q '>&2' "$script"; then
      echo "⚠️  エラーメッセージは stderr（>&2）に出力すべき"
      ((warnings++))
    fi
  fi

  # チェック13: 入力検証
  if ! grep -q "if.*empty\|if.*null\|if.*-z" "$script"; then
    echo "💡 ヒント: 入力フィールドが空でないかの検証を検討"
  fi

  echo ""
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

  if [ $errors -eq 0 ] && [ $warnings -eq 0 ]; then
    echo "✅ 問題なし"
    return 0
  elif [ $errors -eq 0 ]; then
    echo "⚠️  警告 ${warnings} 件"
    return 0
  else
    echo "❌ エラー ${errors} 件、警告 ${warnings} 件"
    return 1
  fi
}

echo "🔎 フックスクリプトリンタ"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

total_errors=0

for script in "$@"; do
  if ! check_script "$script"; then
    ((total_errors++))
  fi
  echo ""
done

if [ $total_errors -eq 0 ]; then
  echo "✅ 全スクリプトがリントをパスしました"
  exit 0
else
  echo "❌ ${total_errors} 個のスクリプトにエラーがあります"
  exit 1
fi
