# よくある設定パターン集

## よくあるパターン

### パターン1: 一時的に有効なフック

hooks.json の編集（再起動が必要）なしに、設定ファイルでフックの
有効/無効を切り替える:

```bash
STATE_FILE=".claude/security-scan.local.md"
[[ ! -f "$STATE_FILE" ]] && exit 0

FRONTMATTER=$(sed -n '/^---$/,/^---$/{ /^---$/d; p; }' "$STATE_FILE")
ENABLED=$(echo "$FRONTMATTER" | grep '^enabled:' | sed 's/enabled: *//')
[[ "$ENABLED" != "true" ]] && exit 0

# フックのロジックを実行する
```

### パターン2: エージェントの状態管理

```markdown
---
agent_name: auth-agent
task_number: 3.5
pr_number: 1234
coordinator_session: team-leader
enabled: true
dependencies: ["Task 3.4"]
---

# タスク割り当て

APIのJWT認証を実装する。

**成功基準:** 認証エンドポイント作成 / テストパス / PR作成とCIグリーン
```

フックが frontmatter からコーディネータのセッション名を読んで
通知を送る、といった協調に使う。

### パターン3: 設定駆動の挙動

```markdown
---
validation_level: strict
max_file_size: 1000000
allowed_extensions: [".js", ".ts", ".tsx"]
enable_logging: true
---
```

```bash
LEVEL=$(echo "$FRONTMATTER" | grep '^validation_level:' | sed 's/validation_level: *//')

case "$LEVEL" in
  strict)   : ;; # 厳格な検証
  standard) : ;; # 標準の検証
  lenient)  : ;; # 緩やかな検証
esac
```

