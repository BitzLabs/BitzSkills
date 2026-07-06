# 設定ファイルのパース技法

`.claude/plugin-name.local.md` を bash スクリプトでパースするための
完全ガイド。

## ファイル構造

```markdown
---
field1: value1
field2: "空白を含む値"
numeric_field: 42
boolean_field: true
list_field: ["item1", "item2", "item3"]
---

# マークダウン本文

本文は別途抽出できる。プロンプト・ドキュメント・補足コンテキストに使う。
```

## frontmatter のパース

### frontmatter ブロックの抽出

```bash
FILE=".claude/my-plugin.local.md"

# --- の間をすべて抽出する（マーカー自体は除く）
FRONTMATTER=$(sed -n '/^---$/,/^---$/{ /^---$/d; p; }' "$FILE")
```

**仕組み:** `sed -n` で自動出力を抑制し、`/^---$/,/^---$/` で最初の
`---` から2つ目の `---` までを範囲指定し、`{ /^---$/d; p; }` で
`---` 行を削除して残りを出力する。

### 個別フィールドの抽出

```bash
# 文字列（クォート除去付き）
VALUE=$(echo "$FRONTMATTER" | grep '^field_name:' | sed 's/field_name: *//' | sed 's/^"\(.*\)"$/\1/')

# 真偽値
ENABLED=$(echo "$FRONTMATTER" | grep '^enabled:' | sed 's/enabled: *//')
if [[ "$ENABLED" == "true" ]]; then :; fi

# 数値（検証付き）
MAX=$(echo "$FRONTMATTER" | grep '^max_value:' | sed 's/max_value: *//')
if [[ "$MAX" =~ ^[0-9]+$ ]] && [[ $MAX -gt 100 ]]; then :; fi

# リスト（単純チェック）
LIST=$(echo "$FRONTMATTER" | grep '^list:' | sed 's/list: *//')
if [[ "$LIST" == *"item1"* ]]; then :; fi
```

### リストの正確なパース（yq）

```bash
# yq が必要（複雑な構造向け）
LIST=$(echo "$FRONTMATTER" | yq -o json '.list' 2>/dev/null)

echo "$LIST" | jq -r '.[]' | while read -r item; do
  echo "処理中: $item"
done
```

## マークダウン本文のパース

```bash
# 2つ目の --- の後をすべて抽出する
BODY=$(awk '/^---$/{i++; next} i>=2' "$FILE")
```

**仕組み:** `---` 行でカウンタを増やしてスキップし、カウンタが2以上に
なった後の行をすべて出力する。**本文中に `---` があっても正しく動く**
（最初の2つだけを数えるため）。

### 本文をプロンプトとして使う

```bash
PROMPT=$(awk '/^---$/{i++; next} i>=2' "$FILE")

# 安全なJSON構築には jq -n --arg を使う
jq -n --arg prompt "$PROMPT" '{
  "decision": "block",
  "reason": $prompt
}'
```

## よくあるパースパターン

```bash
# デフォルト値付き
VALUE=$(echo "$FRONTMATTER" | grep '^field:' | sed 's/field: *//')
VALUE=${VALUE:-default_value}

# 任意フィールド（あるときだけ使う）
if [[ -n "$OPTIONAL" ]] && [[ "$OPTIONAL" != "null" ]]; then :; fi

# 複数フィールドの一括パース
while IFS=': ' read -r key value; do
  value=$(echo "$value" | sed 's/^"\(.*\)"$/\1/')
  case "$key" in
    enabled)  ENABLED="$value" ;;
    mode)     MODE="$value" ;;
    max_size) MAX_SIZE="$value" ;;
  esac
done <<< "$FRONTMATTER"
```

## 設定ファイルの更新

### アトミック更新

破損防止のため必ず一時ファイル + アトミックな mv を使う:

```bash
FILE=".claude/my-plugin.local.md"
TEMP_FILE="${FILE}.tmp.$$"

sed "s/^field_name: .*/field_name: $NEW_VALUE/" "$FILE" > "$TEMP_FILE"
mv "$TEMP_FILE" "$FILE"
```

### カウンタのインクリメント

```bash
CURRENT=$(echo "$FRONTMATTER" | grep '^iteration:' | sed 's/iteration: *//')
NEXT=$((CURRENT + 1))

TEMP_FILE="${FILE}.tmp.$$"
sed "s/^iteration: .*/iteration: $NEXT/" "$FILE" > "$TEMP_FILE"
mv "$TEMP_FILE" "$FILE"
```

### 複数フィールドの一括更新

```bash
sed -e "s/^iteration: .*/iteration: $NEXT_ITERATION/" \
    -e "s/^pr_number: .*/pr_number: $PR_NUMBER/" \
    -e "s/^status: .*/status: $NEW_STATUS/" \
    "$FILE" > "$TEMP_FILE"
mv "$TEMP_FILE" "$FILE"
```

## 検証技法

```bash
# ファイルの存在・読み取り可能性
[[ ! -f "$FILE" ]] && { echo "設定ファイルなし" >&2; exit 1; }
[[ ! -r "$FILE" ]] && { echo "設定ファイルが読めない" >&2; exit 1; }

# frontmatter 構造（--- が2つ以上）
MARKER_COUNT=$(grep -c '^---$' "$FILE" 2>/dev/null || echo "0")
[[ $MARKER_COUNT -lt 2 ]] && { echo "frontmatterマーカーがない" >&2; exit 1; }

# 列挙値の検証
case "$MODE" in
  strict|standard|lenient) ;;
  *) echo "無効なmode: $MODE" >&2; exit 1 ;;
esac

# 数値範囲の検証
if ! [[ "$MAX_SIZE" =~ ^[0-9]+$ ]] || [[ $MAX_SIZE -lt 1 ]] || [[ $MAX_SIZE -gt 10000000 ]]; then
  echo "max_size が範囲外（1〜10000000）" >&2
  exit 1
fi
```

## エッジケースと注意点

### 値のクォート

YAML はクォートあり/なしの両方を許す。両方に対応する:

```bash
VALUE=$(echo "$FRONTMATTER" | grep '^field:' | sed 's/field: *//' | sed 's/^"\(.*\)"$/\1/' | sed "s/^'\\(.*\\)'$/\\1/")
```

### 空の値

```yaml
field1:
field2: ""
field3: null
```

```bash
if [[ -z "$VALUE" ]] || [[ "$VALUE" == "null" ]]; then
  VALUE="default"
fi
```

### 特殊文字

`"Error: Something!"` やパス・正規表現などを含む値は、
**使うときに必ずクォートする**（`echo "$MESSAGE"`）。

## パフォーマンス

- **一度パースして使い回す**: フィールドごとにファイルを読み直さない
- **遅延読み込み**: 先にファイルI/O不要のチェック（tool_name の判定等）を
  済ませ、必要になってから設定ファイルを読む

## yq の利用

複雑な YAML には `yq` を検討する:

```bash
ENABLED=$(echo "$FRONTMATTER" | yq '.enabled')
LIST=$(echo "$FRONTMATTER" | yq -o json '.list_field')
```

**利点**: 正確なYAMLパース・複雑な構造・リスト/オブジェクトの扱い。
**欠点**: 追加の依存・全環境にあるとは限らない。

**推奨**: 単純なフィールドは sed/grep、複雑な構造は yq。

## 完全な例

```bash
#!/bin/bash
set -euo pipefail

SETTINGS_FILE=".claude/my-plugin.local.md"

# 未設定なら即デフォルト
if [[ ! -f "$SETTINGS_FILE" ]]; then
  ENABLED=true
  MODE=standard
  MAX_SIZE=1000000
else
  # frontmatter のパース
  FRONTMATTER=$(sed -n '/^---$/,/^---$/{ /^---$/d; p; }' "$SETTINGS_FILE")

  # デフォルト付きで抽出
  ENABLED=$(echo "$FRONTMATTER" | grep '^enabled:' | sed 's/enabled: *//')
  ENABLED=${ENABLED:-true}

  MODE=$(echo "$FRONTMATTER" | grep '^mode:' | sed 's/mode: *//' | sed 's/^"\(.*\)"$/\1/')
  MODE=${MODE:-standard}

  MAX_SIZE=$(echo "$FRONTMATTER" | grep '^max_size:' | sed 's/max_size: *//')
  MAX_SIZE=${MAX_SIZE:-1000000}

  # 値の検証（不正ならデフォルトに戻す）
  if [[ "$ENABLED" != "true" ]] && [[ "$ENABLED" != "false" ]]; then
    echo "⚠️  enabled が不正。デフォルトを使用" >&2
    ENABLED=true
  fi

  if ! [[ "$MAX_SIZE" =~ ^[0-9]+$ ]]; then
    echo "⚠️  max_size が不正。デフォルトを使用" >&2
    MAX_SIZE=1000000
  fi
fi

# 無効なら即終了
[[ "$ENABLED" != "true" ]] && exit 0

# 設定を使う
echo "設定を読み込み: mode=$MODE, max_size=$MAX_SIZE" >&2

case "$MODE" in
  strict)   : ;; # 厳格な検証
  standard) : ;; # 標準の検証
  lenient)  : ;; # 緩やかな検証
esac
```

デフォルト・検証・エラー回復を備えた堅牢な設定処理の完成形。
