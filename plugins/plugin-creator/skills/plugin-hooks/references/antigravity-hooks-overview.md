# Antigravity 2.0 のフック（概要）

## Antigravity 2.0 のフック

Antigravity のフックは別仕様。要点:

- **配置**: プラグイン**ルート直下**の `hooks.json`（`hooks/` フォルダではない）。
  customization root（`.agents/` や `~/.gemini/config/`）にも置ける
- **書式**: トップレベルは「フック名 → 設定」のマップ。
  `{"hooks": {...}}` ラッパーは使わない

```json
{
  "lint-checker": {
    "enabled": true,
    "PostToolUse": [
      {
        "matcher": "run_command",
        "hooks": [
          { "type": "command", "command": "./scripts/lint.sh", "timeout": 10 }
        ]
      }
    ]
  }
}
```

- **イベントは5種のみ**: `PreToolUse` / `PostToolUse`（matcher + hooks の
  グループ形式）、`PreInvocation` / `PostInvocation` / `Stop`（ハンドラ配列を
  直接書くフラット形式）。SessionStart / UserPromptSubmit 等はない
- **matcher は Antigravity のツール名**（`run_command`, `view_file`,
  `browser_.*` 等）に対する正規表現。Claude Code の `Write|Edit` は一致しない
- **コマンドフックのみ**（`type: "command"`。プロンプトベースフックはない）。
  timeout の既定は30秒。フックは同期実行でループをブロックする
- **cwd は hooks.json のあるディレクトリ**。`${CLAUDE_PLUGIN_ROOT}` は
  存在しないため、スクリプトは相対パス（`./scripts/...`）で参照する
- **入出力契約が異なる**: stdin/stdout の JSON キーは camelCase。
  PreToolUse の出力は `{"decision": "allow|deny|ask|force_ask"}`、
  Stop は `{"decision": "continue"}` で停止をブロック、
  PreInvocation / PostInvocation は `injectSteps` でステップ注入が可能

両対応プラグインでは、フックスクリプト本体（検証ロジック）を共通化し、
Claude Code 用 `hooks/hooks.json` と Antigravity 用 `hooks.json` の2つの
設定ファイルからそれぞれの入出力契約に合わせた薄いラッパーで呼び出す。
イベント一覧・全契約の詳細は `references/antigravity-hooks.md` を参照。

