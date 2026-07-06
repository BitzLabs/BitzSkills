#!/bin/bash
# frontmatter パーサユーティリティ
# .local.md ファイルから YAML frontmatter を抽出する

set -euo pipefail

# 使い方
show_usage() {
  echo "使い方: $0 <settings-file.md> [field-name]"
  echo ""
  echo "例:"
  echo "  # frontmatter 全体を表示"
  echo "  $0 .claude/my-plugin.local.md"
  echo ""
  echo "  # 特定フィールドを抽出"
  echo "  $0 .claude/my-plugin.local.md enabled"
  echo ""
  echo "  # スクリプト内で使う"
  echo "  ENABLED=\$($0 .claude/my-plugin.local.md enabled)"
  exit 0
}

if [ $# -eq 0 ] || [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
  show_usage
fi

FILE="$1"
FIELD="${2:-}"

# ファイルの検証
if [ ! -f "$FILE" ]; then
  echo "エラー: ファイルが見つかりません: $FILE" >&2
  exit 1
fi

# frontmatter の抽出
FRONTMATTER=$(sed -n '/^---$/,/^---$/{ /^---$/d; p; }' "$FILE")

if [ -z "$FRONTMATTER" ]; then
  echo "エラー: $FILE に frontmatter がありません" >&2
  exit 1
fi

# フィールド指定がなければ全体を出力
if [ -z "$FIELD" ]; then
  echo "$FRONTMATTER"
  exit 0
fi

# 特定フィールドの抽出
VALUE=$(echo "$FRONTMATTER" | grep "^${FIELD}:" | sed "s/${FIELD}: *//" | sed 's/^"\(.*\)"$/\1/' | sed "s/^'\\(.*\\)'$/\\1/")

if [ -z "$VALUE" ]; then
  echo "エラー: frontmatter にフィールド '$FIELD' がありません" >&2
  exit 1
fi

echo "$VALUE"
exit 0
