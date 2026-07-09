#!/bin/bash
# 設定ファイルバリデータ
# .claude/plugin-name.local.md の構造を検証する

set -euo pipefail

# 使い方
if [ $# -eq 0 ]; then
  echo "使い方: $0 <path/to/settings.local.md>"
  echo ""
  echo "検証項目:"
  echo "  - ファイルの存在と読み取り可能性"
  echo "  - YAML frontmatter の構造"
  echo "  - 必須の --- マーカー"
  echo "  - フィールドの形式"
  echo ""
  echo "例: $0 .claude/my-plugin.local.md"
  exit 1
fi

SETTINGS_FILE="$1"

echo "🔍 設定ファイルを検証中: $SETTINGS_FILE"
echo ""

# チェック1: ファイルの存在
if [ ! -f "$SETTINGS_FILE" ]; then
  echo "❌ ファイルが見つかりません: $SETTINGS_FILE"
  exit 1
fi
echo "✅ ファイルが存在します"

# チェック2: 読み取り可能か
if [ ! -r "$SETTINGS_FILE" ]; then
  echo "❌ ファイルが読み取れません"
  exit 1
fi
echo "✅ ファイルは読み取り可能"

# チェック3: frontmatter マーカーの有無
MARKER_COUNT=$(grep -c '^---$' "$SETTINGS_FILE" 2>/dev/null || echo "0")

if [ "$MARKER_COUNT" -lt 2 ]; then
  echo "❌ 不正な frontmatter: '---' マーカーが ${MARKER_COUNT} 個（最低2個必要）"
  echo "   期待される形式:"
  echo "   ---"
  echo "   field: value"
  echo "   ---"
  echo "   本文..."
  exit 1
fi
echo "✅ frontmatter マーカーあり"

# チェック4: frontmatter の抽出と検証
FRONTMATTER=$(sed -n '/^---$/,/^---$/{ /^---$/d; p; }' "$SETTINGS_FILE")

if [ -z "$FRONTMATTER" ]; then
  echo "❌ frontmatter が空です（--- の間に何もない）"
  exit 1
fi
echo "✅ frontmatter は空でない"

# チェック5: YAML風の構造か
if ! echo "$FRONTMATTER" | grep -q ':'; then
  echo "⚠️  警告: frontmatter に key:value のペアがありません"
fi

# チェック6: 検出されたフィールドの表示
echo ""
echo "検出されたフィールド:"
echo "$FRONTMATTER" | grep '^[a-z_][a-z0-9_]*:' | while IFS=':' read -r key value; do
  echo "  - $key: ${value:0:50}"
done

# チェック7: 代表的な真偽値フィールドの検証
for field in enabled strict_mode; do
  VALUE=$(echo "$FRONTMATTER" | grep "^${field}:" | sed "s/${field}: *//" || true)
  if [ -n "$VALUE" ]; then
    if [ "$VALUE" != "true" ] && [ "$VALUE" != "false" ]; then
      echo "⚠️  フィールド '$field' は真偽値（true/false）であるべきです: $VALUE"
    fi
  fi
done

# チェック8: 本文の有無
BODY=$(awk '/^---$/{i++; next} i>=2' "$SETTINGS_FILE")

echo ""
if [ -n "$BODY" ]; then
  BODY_LINES=$(echo "$BODY" | wc -l | tr -d ' ')
  echo "✅ マークダウン本文あり（${BODY_LINES} 行）"
else
  echo "⚠️  マークダウン本文なし（frontmatterのみ）"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ 設定ファイルの構造は正常です"
echo ""
echo "注意: このファイルの変更には Claude Code の再起動が必要です"
exit 0
