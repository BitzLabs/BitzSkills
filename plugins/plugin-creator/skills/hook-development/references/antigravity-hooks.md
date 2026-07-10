# Antigravity 2.0 ライフサイクルフック 完全仕様

出典: Antigravity 組み込みドキュメント
（`~/.gemini/antigravity-cli/builtin/skills/agy-customizations/docs/hooks.md`）。
Claude Code のフックとはイベント・書式・入出力契約が別物なので、
両対応プラグインでは設定ファイルを2系統用意する。

## 配置場所

- customization root 直下の `hooks.json`
  （例: `.agents/hooks.json`、`~/.gemini/config/hooks.json`）
- プラグイン内では**プラグインルート直下**の `hooks.json`
  （Claude Code の `hooks/hooks.json` は検出されない）

## ファイル書式

トップレベルは「**フック名 → 設定**」のマップ:

```json
{
  "lint-checker": {
    "PostToolUse": [
      {
        "matcher": "run_command",
        "hooks": [
          { "type": "command", "command": "./scripts/lint.sh", "timeout": 10 }
        ]
      }
    ]
  },
  "safety-gate": {
    "enabled": false,
    "PreToolUse": [
      {
        "matcher": "run_command",
        "hooks": [{ "command": "./scripts/safety-check.sh" }]
      }
    ]
  },
  "reminder": {
    "PreInvocation": [
      { "type": "command", "command": "./scripts/reminder.sh" }
    ]
  }
}
```

- **マージ**: 複数の設定元（プラグイン・root）の同一イベントのフックは
  マージされ順次実行される
- **無効化**: フック単位の `"enabled": false` で一時停止できる

## イベント一覧

| イベント | 発火タイミング | 構造 |
| --- | --- | --- |
| `PreToolUse` | ツール実行前 | グループ形式（`matcher` + `hooks`） |
| `PostToolUse` | ツール完了後 | グループ形式（`matcher` + `hooks`） |
| `PreInvocation` | モデル呼び出し前 | フラット形式（ハンドラ配列を直接） |
| `PostInvocation` | ツール呼び出し完了後 | フラット形式 |
| `Stop` | 実行ループ終了時 | フラット形式 |

Claude Code にある SessionStart / SessionEnd / UserPromptSubmit /
SubagentStop / PreCompact / Notification は存在しない。

### matcher（PreToolUse / PostToolUse）

ツール名に対する正規表現:

- `"*"` または `""` — 全ツール
- `"run_command"` — 完全一致
- `"run_command|view_file"` — いずれか
- `"browser_.*"` — 前方一致

ツール名は Antigravity の内部ステップ種別を小文字化したもの
（`run_command`, `view_file`, `browser_*` など）。**Claude Code のツール名
（Write / Edit / Bash）とは別体系**。

## ハンドラのフィールド

- `type`（任意）: 既定は `"command"`。現在 command のみ対応
  （プロンプト型・HTTP型はない）
- `command`（必須）: シェルコマンド（Unix は `sh -c`、Windows は `cmd /c`）。
  `~` はホームに展開。**cwd は hooks.json のあるディレクトリ**
- `timeout`（任意）: 秒。既定は 30

## 入出力契約

フックは stdin で JSON を受け取り、stdout に JSON を返す。
**キーはすべて camelCase**（protojson）。

### 共通入力フィールド

```json
{
  "conversationId": "ec33ebf9-...",
  "workspacePaths": ["/path/to/workspace"],
  "transcriptPath": "/path/to/workspace/.gemini/antigravity/transcript.jsonl",
  "artifactDirectoryPath": "/path/to/workspace/.gemini/antigravity/artifacts",
  "modelName": "auto"
}
```

パス中のディレクトリ名は製品で異なる: CLI は `antigravity-cli/`、
Antigravity 2.0 は `antigravity/`、IDE は `antigravity-ide/`。

### PreToolUse

入力（追加分）: `toolCall.name` / `toolCall.args` / `stepIdx`

出力:

```json
{
  "decision": "ask",
  "reason": "テスト実行には確認が必要",
  "permissionOverrides": ["command(npm test)"]
}
```

- `decision`（必須）: `"allow"`（自動許可）/ `"deny"`（即ブロック）/
  `"ask"`（ユーザーに確認。Always Allow キャッシュを尊重）/
  `"force_ask"`（キャッシュを無視して必ず確認）
- `reason`（任意）: ユーザー/エージェントに表示する説明
- `permissionOverrides`（任意）: 一時的な許可の付与
- 入力の書き換え（Claude Code の `updatedInput` 相当）は未実装

### PostToolUse

入力（追加分）: `stepIdx`、失敗時は `error`。
出力: 空オブジェクト `{}` を返す。

### PreInvocation / PostInvocation

入力（追加分）: `invocationNum` / `initialNumSteps`

出力:

```json
{
  "injectSteps": [
    { "ephemeralMessage": "コミット前に lint エラーを確認すること。" }
  ],
  "terminationBehavior": "force_continue"
}
```

- `injectSteps[]`: 注入するステップ。
  `{"toolCall": {...}}` / `{"userMessage": "..."}` /
  `{"ephemeralMessage": "..."}`（一時的なシステムメッセージ）
- `terminationBehavior`（PostInvocation のみ）: `"force_continue"` /
  `"terminate"` / 省略（既定動作）

### Stop

入力（追加分）: `executionNum` / `terminationReason`
（`model_stop` / `max_steps_exceeded` / `error`）/ `error` / `fullyIdle`

出力:

```json
{ "decision": "continue", "reason": "バックグラウンドのテストが未完了。" }
```

`decision: "continue"` で停止をブロックしてループを再開する。
それ以外の値なら停止を許可。`reason` は継続時にシステムメッセージとして注入。

## 制限事項

- `type: "command"` のみ（HTTP・プロンプトフックはない）
- フックは同期実行でエージェントループをブロックする（非同期はない）
- PreToolUse での入力の overwrite（上書き）は未実装

## Claude Code フックとの対応表

| 観点 | Claude Code | Antigravity 2.0 |
| --- | --- | --- |
| 配置 | `hooks/hooks.json`（`hooks` ラッパー必須） | ルート直下 `hooks.json`（名前付きマップ） |
| イベント数 | 9 | 5 |
| フック種別 | command / prompt | command のみ |
| matcher 対象 | Write / Edit / Bash / mcp__* | run_command / view_file / browser_* |
| JSONキー | snake_case（入力） | camelCase |
| 許可判定 | `permissionDecision: allow\|deny\|ask` | `decision: allow\|deny\|ask\|force_ask` |
| 停止ブロック | Stop で `decision: block` | Stop で `decision: continue` |
| パス参照 | `${CLAUDE_PLUGIN_ROOT}` | cwd = hooks.json のディレクトリ（相対パス） |
| 実行 | 一致フックは並列 | 同期・順次 |

## 両対応の実装パターン

検証ロジック本体を共通スクリプトに置き、プラットフォーム別の薄い
アダプタから呼ぶ:

```text
plugin-name/
├── hooks/hooks.json        # Claude Code 用設定
├── hooks.json              # Antigravity 用設定
└── scripts/
    ├── check-core.sh       # 共通ロジック（引数で受け取り、終了コードで返す）
    ├── cc-adapter.sh       # stdin(snake_case) → check-core → CC形式のstdout
    └── agy-adapter.sh      # stdin(camelCase) → check-core → AGY形式のstdout
```
