---
name: hook-development
description: Claude Code / Antigravity 2.0 プラグインのフック（hooks/hooks.json / hooks.json）の作成を支援する。「フックを作りたい」「PreToolUse/PostToolUse/Stopフックを追加したい」「ツール使用を検証したい」「危険なコマンドをブロックしたい」と言われたときや、フックイベント（PreToolUse, PostToolUse, Stop, SubagentStop, SessionStart, SessionEnd, UserPromptSubmit, PreCompact, Notification, PreInvocation, PostInvocation）に言及されたときに使用する。プロンプトベースフックを中心に包括的なガイダンスを提供する。
metadata:
  version: "0.2.1"
  author: br7.hide
  created: "2026-07-05"
  updated: "2026-07-10"
---

# hook-development

## 目的

フックはエージェントのイベントに反応して実行されるイベント駆動の自動化
スクリプト。操作の検証・ポリシーの強制・コンテキストの追加・外部ツールの
統合に使う。

本文は Claude Code のフック仕様。**Antigravity 2.0 はイベント体系・
ファイル配置・書式・入出力契約がすべて異なる**（本文末尾の
「Antigravity 2.0 のフック」と `references/antigravity-hooks.md` を参照）。

## フックの種類

### プロンプトベースフック（推奨）

LLMによる文脈対応の判断を使う:

```json
{
  "type": "prompt",
  "prompt": "このツール使用が適切か評価する: $TOOL_INPUT",
  "timeout": 30
}
```

**対応イベント:** Stop, SubagentStop, UserPromptSubmit, PreToolUse

**利点:** 自然言語推論による文脈対応の判断、bashスクリプト不要の柔軟な
評価ロジック、エッジケースへの強さ、保守・拡張の容易さ。

### コマンドフック

決定的なチェックのために bash コマンドを実行する:

```json
{
  "type": "command",
  "command": "bash ${CLAUDE_PLUGIN_ROOT}/scripts/validate.sh",
  "timeout": 60
}
```

**用途:** 高速で決定的な検証、ファイルシステム操作、外部ツール統合、
性能が重要なチェック。

## 設定ファイルの形式

### プラグインの hooks.json（ラッパー形式）

プラグインの `hooks/hooks.json` では **`hooks` ラッパーが必須**:

```json
{
  "description": "コード品質のための検証フック（任意）",
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Write",
        "hooks": [
          {
            "type": "command",
            "command": "${CLAUDE_PLUGIN_ROOT}/hooks/validate.sh"
          }
        ]
      }
    ]
  }
}
```

### settings.json（直接形式）

ユーザー設定 `.claude/settings.json` ではラッパーなしでイベントを
トップレベルに直接書く。

**注意:** 以下の例はイベント構造のみを示す。プラグインの hooks.json では
`{"hooks": {...}}` で包むこと。

## フックイベント

| イベント | タイミング | 用途 |
| --- | --- | --- |
| PreToolUse | ツール実行前 | 検証・許可/拒否・入力の修正 |
| PostToolUse | ツール完了後 | フィードバック・ログ |
| UserPromptSubmit | ユーザー入力時 | コンテキスト追加・検証 |
| Stop | エージェント停止前 | 完了状態の検証 |
| SubagentStop | サブエージェント停止前 | タスク完了の検証 |
| SessionStart | セッション開始 | コンテキスト読み込み |
| SessionEnd | セッション終了 | クリーンアップ・ログ |
| PreCompact | コンテキスト圧縮前 | 重要情報の保全 |
| Notification | 通知送信時 | ログ・リアクション |

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

## 環境変数

- `$CLAUDE_PROJECT_DIR` — プロジェクトルート
- `$CLAUDE_PLUGIN_ROOT` — プラグインフォルダ（**必ずこれでパスを書く**）
- `$CLAUDE_ENV_FILE` — SessionStart のみ: 環境変数の永続化先
- `$CLAUDE_CODE_REMOTE` — リモート実行時に設定される

## matcher

```json
"matcher": "Write"              // 完全一致
"matcher": "Read|Write|Edit"    // 複数ツール
"matcher": "*"                  // 全ツール
"matcher": "mcp__.*__delete.*"  // 正規表現（MCPの削除系ツール全部）
"matcher": "mcp__plugin_asana_.*"  // 特定プラグインのMCPツール
```

matcher は大文字小文字を区別する。

## セキュリティのベストプラクティス

### 入力検証

```bash
#!/bin/bash
set -euo pipefail

input=$(cat)
tool_name=$(echo "$input" | jq -r '.tool_name')

# ツール名の形式を検証する
if [[ ! "$tool_name" =~ ^[a-zA-Z0-9_]+$ ]]; then
  echo '{"decision": "deny", "reason": "不正なツール名"}' >&2
  exit 2
fi
```

### パスの安全性

```bash
file_path=$(echo "$input" | jq -r '.tool_input.file_path')

# パストラバーサルを拒否する
if [[ "$file_path" == *".."* ]]; then
  echo '{"decision": "deny", "reason": "パストラバーサルを検出"}' >&2
  exit 2
fi

# 機微なファイルを拒否する
if [[ "$file_path" == *".env"* ]]; then
  echo '{"decision": "deny", "reason": "機微なファイル"}' >&2
  exit 2
fi
```

完全な例は `examples/validate-write.sh` / `examples/validate-bash.sh` を参照。

### その他

- **変数は必ずクォートする**: `echo "$file_path"`（インジェクション対策）
- **タイムアウトを設定する**: 既定はコマンド60秒 / プロンプト30秒
- **機密情報をログに出さない**

## パフォーマンス

一致するフックは**すべて並列実行**される。フック同士は互いの出力を
見られず、順序も非決定的なので、独立して動くよう設計する。
高速で決定的なチェックはコマンドフック、複雑な推論はプロンプトフックに
分担させる。

## 一時的に有効なフック

フラグファイルや設定で条件付きに動くフックを作れる:

```bash
#!/bin/bash
# フラグファイルがあるときだけ有効
FLAG_FILE="$CLAUDE_PROJECT_DIR/.enable-strict-validation"

if [ ! -f "$FLAG_FILE" ]; then
  exit 0  # フラグなし。検証をスキップ
fi

# フラグあり。検証を実行する
input=$(cat)
# ... 検証ロジック ...
```

有効化の仕組みをプラグインの README に必ず書くこと。

## ライフサイクルと制限

**フックはセッション開始時に読み込まれる。** 設定変更はホットスワップ
できず、Claude Code の再起動が必要:

1. hooks.json やスクリプトを編集する
2. Claude Code を終了して再起動する
3. `claude --debug` でテストする

起動時に検証が走る（不正な JSON は読み込み失敗、スクリプト欠落は警告）。
現在のセッションのフック一覧は `/hooks` コマンドで確認できる。

## デバッグ

```bash
# デバッグモードでフックの登録・実行ログ・入出力JSONを見る
claude --debug

# コマンドフックを単体テストする
echo '{"tool_name": "Write", "tool_input": {"file_path": "/test"}}' | \
  bash ${CLAUDE_PLUGIN_ROOT}/scripts/validate.sh
echo "Exit code: $?"

# JSON出力の妥当性を確認する
output=$(./your-hook.sh < test-input.json)
echo "$output" | jq .
```

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

## 追加リソース

### リファレンス

- **`references/patterns.md`** — 実績あるフックパターン集
- **`references/migration.md`** — 基本フックから発展フックへの移行
- **`references/advanced.md`** — 発展的なユースケースとテクニック
- **`references/antigravity-hooks.md`** — Antigravity 2.0 フックの完全仕様

### 実例

- **`examples/validate-write.sh`** — ファイル書き込み検証
- **`examples/validate-bash.sh`** — bashコマンド検証
- **`examples/load-context.sh`** — SessionStart のコンテキスト読み込み

### スクリプト

- **`scripts/validate-hook-schema.sh`** — hooks.json の構造・構文検証
- **`scripts/test-hook.sh`** — サンプル入力でのフックテスト
- **`scripts/hook-linter.sh`** — フックスクリプトのベストプラクティス検査

## 実装ワークフロー

1. フックするイベントを特定する（PreToolUse / Stop / SessionStart 等）
2. プロンプトベース（柔軟）かコマンド（決定的）かを選ぶ
3. `hooks/hooks.json` に設定を書く（ラッパー形式）
4. コマンドフックならスクリプトを作成する
5. ファイル参照はすべて `${CLAUDE_PLUGIN_ROOT}` を使う
6. `scripts/validate-hook-schema.sh hooks/hooks.json` で検証する
7. `scripts/test-hook.sh` でデプロイ前にテストする
8. `claude --debug` で実環境テストする
9. プラグインの README にフックを文書化する

ほとんどの用途はプロンプトベースフックを使い、性能重視・決定的な
チェックだけコマンドフックにする。
