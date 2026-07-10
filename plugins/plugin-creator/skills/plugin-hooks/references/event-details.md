# フックイベント詳細と入出力形式

### PreToolUse

```json
{
  "PreToolUse": [
    {
      "matcher": "Write|Edit",
      "hooks": [
        {
          "type": "prompt",
          "prompt": "ファイル書き込みの安全性を検証する。システムパス・認証情報・パストラバーサル・機微な内容をチェックし、'approve' または 'deny' を返す。"
        }
      ]
    }
  ]
}
```

**PreToolUse の出力:**

```json
{
  "hookSpecificOutput": {
    "permissionDecision": "allow|deny|ask",
    "updatedInput": {"field": "修正後の値"}
  },
  "systemMessage": "Claudeへの説明"
}
```

### Stop

```json
{
  "Stop": [
    {
      "matcher": "*",
      "hooks": [
        {
          "type": "prompt",
          "prompt": "タスク完了を検証する: テスト実行済みか、ビルド成功か、質問に答えたか。停止してよければ 'approve'、続行すべきなら理由付きで 'block' を返す。"
        }
      ]
    }
  ]
}
```

**判定出力:**

```json
{
  "decision": "approve|block",
  "reason": "説明",
  "systemMessage": "追加コンテキスト"
}
```

### SessionStart

```json
{
  "SessionStart": [
    {
      "matcher": "*",
      "hooks": [
        {
          "type": "command",
          "command": "bash ${CLAUDE_PLUGIN_ROOT}/scripts/load-context.sh",
          "timeout": 10
        }
      ]
    }
  ]
}
```

**特殊機能:** `$CLAUDE_ENV_FILE` に書けば環境変数を永続化できる:

```bash
echo "export PROJECT_TYPE=nodejs" >> "$CLAUDE_ENV_FILE"
```

完全な例は `examples/load-context.sh` を参照。

## 入出力形式

### 入力（stdin の JSON）

```json
{
  "session_id": "abc123",
  "transcript_path": "/path/to/transcript.txt",
  "cwd": "/current/working/dir",
  "permission_mode": "ask|allow",
  "hook_event_name": "PreToolUse"
}
```

イベント固有フィールド: PreToolUse/PostToolUse は `tool_name` /
`tool_input` / `tool_result`、UserPromptSubmit は `user_prompt`、
Stop/SubagentStop は `reason`。プロンプト内では `$TOOL_INPUT`
`$TOOL_RESULT` `$USER_PROMPT` 等で参照できる。

### 標準出力（全フック共通）

```json
{
  "continue": true,
  "suppressOutput": false,
  "systemMessage": "Claudeへのメッセージ"
}
```

### 終了コード

- `0` — 成功（stdout がトランスクリプトに表示される）
- `2` — ブロッキングエラー（stderr が Claude にフィードバックされる）
- その他 — 非ブロッキングエラー

