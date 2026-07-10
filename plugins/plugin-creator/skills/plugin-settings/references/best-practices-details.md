# ベストプラクティスの詳細（命名・gitignore・デフォルト値・値の検証・再起動）

### 命名

- ✅ `.claude/plugin-name.local.md` 形式。プラグイン名と一致させ、
  `.local.md` サフィックスを使う
- ❌ `.claude/` 以外のフォルダ、不統一な命名、`.local` なしの `.md`
  （コミットされる恐れ）

### gitignore

必ず `.gitignore` に追加し、README にも書く:

```gitignore
.claude/*.local.md
.claude/*.local.json
```

### デフォルト値

ファイルがないときは賢明なデフォルトを使う:

```bash
if [[ ! -f "$STATE_FILE" ]]; then
  ENABLED=true
  MODE=standard
else
  : # ファイルから読む
fi
```

### 値の検証

```bash
MAX=$(echo "$FRONTMATTER" | grep '^max_value:' | sed 's/max_value: *//')

# 数値範囲の検証
if ! [[ "$MAX" =~ ^[0-9]+$ ]] || [[ $MAX -lt 1 ]] || [[ $MAX -gt 100 ]]; then
  echo "⚠️  設定の max_value が不正です（1〜100）" >&2
  MAX=10  # デフォルトを使う
fi
```

### 再起動の必要性

設定変更のフックへの反映には Claude Code の再起動が必要。
README に「編集 → 保存 → Claude Code 終了 → 再起動」と明記する。

