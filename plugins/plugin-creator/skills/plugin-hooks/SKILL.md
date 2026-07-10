---
name: plugin-hooks
description: Claude Code / Antigravity 2.0 プラグインのフック（hooks/hooks.json / hooks.json）の作成を支援する。「フックを作りたい」「PreToolUse/PostToolUse/Stopフックを追加したい」「ツール使用を検証したい」「危険なコマンドをブロックしたい」と言われたときや、フックイベント（PreToolUse, PostToolUse, Stop, SubagentStop, SessionStart, SessionEnd, UserPromptSubmit, PreCompact, Notification, PreInvocation, PostInvocation）に言及されたときに使用する。プロンプトベースフックを中心に包括的なガイダンスを提供する。
metadata:
  version: "0.4.0"
  author: br7.hide
  created: "2026-07-05"
  updated: "2026-07-11"
---

# plugin-hooks

## 目的

フックはエージェントのイベントに反応して実行されるイベント駆動の自動化
スクリプト。操作の検証・ポリシーの強制・コンテキストの追加・外部ツールの
統合に使う。

本文は Claude Code のフック仕様。**Antigravity 2.0 はイベント体系・
ファイル配置・書式・入出力契約がすべて異なる**
（`references/antigravity-hooks-overview.md` と `references/antigravity-hooks.md` を参照）。

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

各イベントの詳細な設定例（PreToolUse / Stop / SessionStart）と入出力形式
（stdin JSON・標準出力・終了コード）は `references/event-details.md` を参照。

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

セキュリティのベストプラクティス・パフォーマンス特性・一時的な有効化・
ライフサイクルと制限・デバッグ手順は `references/security-and-lifecycle.md`
を参照。

Antigravity 2.0 のフック仕様の概要は `references/antigravity-hooks-overview.md`、
完全な契約詳細は `references/antigravity-hooks.md` を参照。

## 追加リソース

### リファレンス

- **`references/event-details.md`** — フックイベントの詳細例と入出力形式
- **`references/security-and-lifecycle.md`** — セキュリティ・パフォーマンス・ライフサイクル・デバッグ
- **`references/antigravity-hooks-overview.md`** — Antigravity 2.0 フックの概要
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
