# フックからの設定読み取りの完全な例

### フック（bashスクリプト）から

```bash
#!/bin/bash
set -euo pipefail

# 状態ファイルのパス
STATE_FILE=".claude/my-plugin.local.md"

# ファイルがなければ即終了
if [[ ! -f "$STATE_FILE" ]]; then
  exit 0  # プラグイン未設定。スキップ
fi

# YAML frontmatter をパースする（--- の間）
FRONTMATTER=$(sed -n '/^---$/,/^---$/{ /^---$/d; p; }' "$STATE_FILE")

# 個別フィールドの抽出
ENABLED=$(echo "$FRONTMATTER" | grep '^enabled:' | sed 's/enabled: *//' | sed 's/^"\(.*\)"$/\1/')
STRICT_MODE=$(echo "$FRONTMATTER" | grep '^strict_mode:' | sed 's/strict_mode: *//' | sed 's/^"\(.*\)"$/\1/')

# 有効かどうか確認
if [[ "$ENABLED" != "true" ]]; then
  exit 0  # 無効
fi

# 設定をフックのロジックで使う
if [[ "$STRICT_MODE" == "true" ]]; then
  : # 厳格な検証を適用する
fi
```

完全な例は `examples/read-settings-hook.sh` を参照。

