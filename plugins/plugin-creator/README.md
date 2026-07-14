# plugin-creator

Claude Code / Antigravity 2.0 プラグイン開発の全領域を支援するツールキット。
フック・MCP統合・プラグイン構造・設定管理・コマンド/エージェント/スキル開発の
専門ガイダンスを、両プラットフォームの仕様差を踏まえて提供する。
（[anthropics/claude-code の plugin-dev](https://github.com/anthropics/claude-code/tree/main/plugins/plugin-dev)
を参考に、全編日本語で作成。Antigravity 側の仕様は agy CLI 組み込み
ドキュメントと実測に基づく）

## 概要

高品質なプラグインを作るための7つの専門スキルを提供する:

1. **plugin-structure** — プラグインの構成・マニフェスト・自動発見（両対応の作り方を含む）
2. **plugin-skills** — プラグインへのスキル同梱（配置・自動発見・両対応。作り方は skill-creator プラグインが正）
3. **plugin-commands** — frontmatter・引数・対話機能を持つスラッシュコマンド作成
4. **plugin-agents** — AI支援生成を含む自律エージェント作成
5. **plugin-hooks** — フックAPIとイベント駆動自動化（Antigravity 別仕様を含む）
6. **plugin-mcp** — MCP（Model Context Protocol）サーバー統合
7. **plugin-settings** — `.claude/plugin-name.local.md` による設定管理

## プラットフォーム互換性

| コンポーネント | Claude Code | Antigravity 2.0 |
| --- | --- | --- |
| マニフェスト | `.claude-plugin/plugin.json` | ルートの `plugin.json`（両対応は両方置く） |
| スキル | `skills/<name>/SKILL.md` | 同形式（最もポータブル） |
| コマンド | `commands/*.md` | ネイティブ非対応（agy がスキルに変換） |
| エージェント | `agents/*.md` | agy が同形式を取り込む（`model: inherit` 推奨） |
| フック | `hooks/hooks.json` | ルートの `hooks.json`（**書式・イベント別物**） |
| MCP | `.mcp.json` | ルートの `mcp_config.json`（stdio / SSE のみ） |
| ルール | — | `rules/*.md` を同梱可 |
| パス変数 | `${CLAUDE_PLUGIN_ROOT}` | なし（フックの cwd = hooks.json の場所） |

各スキルは progressive disclosure（リーンな本体 + 詳細リファレンス +
動く実例 + ユーティリティスクリプト）に従う。

## ガイド付きワークフローコマンド

### /plugin-creator:create-plugin

構想から完成まで、プラグイン作成をエンドツーエンドで進める統括コマンド。

**8フェーズのプロセス:**

1. **発見** — プラグインの目的と要件の理解
2. **コンポーネント計画** — 必要なスキル・コマンド・エージェント・フック・MCPの決定
3. **詳細設計** — 各コンポーネントの仕様化と曖昧さの解消
4. **構造作成** — ディレクトリとマニフェストのセットアップ
5. **コンポーネント実装** — AI支援エージェントを使った各コンポーネントの作成
6. **検証** — plugin-validator とコンポーネント別チェックの実行
7. **テスト** — Claude Code 上での動作確認
8. **ドキュメント** — README の仕上げと配布準備

**使い方:**

```bash
/plugin-creator:create-plugin [説明（任意）]

# 例:
/plugin-creator:create-plugin
/plugin-creator:create-plugin データベースマイグレーションを管理するプラグイン
```

## エージェント

| エージェント | 役割 | 色 |
| --- | --- | --- |
| **agent-creator** | 実績あるプロンプトパターンによるAI支援エージェント生成 | magenta |
| **plugin-validator** | マニフェスト・構造・コンポーネント・セキュリティの包括検証 | yellow |

## スキル詳細

### plugin-structure

**トリガー例:** 「プラグインを作りたい」「plugin.jsonの書き方」「プラグイン構成」

構成: SKILL.md（リーン本文）+ references 6本（manifest-reference / component-patterns /
antigravity-directory-structure / antigravity-structure / component-examples / troubleshooting）+
examples 3本（minimal / standard / advanced）

### plugin-skills

**トリガー例:** 「プラグインにスキルを追加」「プラグイン内のスキル構成」

構成: SKILL.md のみ（薄い案内スキル）。スキルの作り方・検証・最適化は
`skill-creator` プラグインが正で、本スキルはプラグイン固有の考慮事項だけを扱う。

### plugin-commands

**トリガー例:** 「スラッシュコマンドを作りたい」「コマンドの引数」「対話的なコマンド」

構成: SKILL.md + references 7本（frontmatter / plugin-features / interactive /
advanced-workflows / documentation / testing / marketplace）+ examples 2本

### plugin-agents

**トリガー例:** 「エージェントを作りたい」「エージェントのfrontmatter」

構成: SKILL.md（リーン本文）+ references 5本（システムプロンプトテンプレート / AI支援生成 /
システムプロンプト設計 / トリガーexample / 生成プロンプト原文）+ examples 2本 +
scripts 1本（validate-agent.sh）

### plugin-hooks

**トリガー例:** 「フックを作りたい」「PreToolUseフック」「危険なコマンドをブロック」

構成: SKILL.md（リーン本文）+ references 7本（event-details / security-and-lifecycle /
antigravity-hooks-overview / antigravity-hooks / patterns / migration / advanced）+
examples 3本（.sh）+ scripts 3本（validate-hook-schema / test-hook / hook-linter）

### plugin-mcp

**トリガー例:** 「MCPサーバーを追加」「.mcp.jsonの設定」「外部サービス連携」

構成: SKILL.md（リーン本文）+ references 6本（antigravity-config / server-type-examples /
testing-and-troubleshooting / server-types / authentication / tool-usage）+
examples 3本（stdio / sse / http の設定JSON）

### plugin-settings

**トリガー例:** 「プラグイン設定を保存」「.local.mdファイル」

構成: SKILL.md（リーン本文）+ references 5本（hook-reading-example / common-patterns /
best-practices-details / parsing-techniques / real-world-examples）+
examples 3本 + scripts 2本（validate-settings / parse-frontmatter）

## インストール

```bash
# Claude Code（マーケットプレイス経由）
/plugin marketplace add BitzLabs/BitzSkills
/plugin install plugin-creator@bitzskills

# Antigravity 2.0
agy plugin install /path/to/BitzSkills/plugins/plugin-creator

# OpenAI Codex CLI（収録スキルを Codex から利用）
codex plugin marketplace add BitzLabs/BitzSkills
codex plugin add plugin-creator@bitzskills

# 開発時（Claude Code ローカル直接指定）
claude --plugin-dir /path/to/BitzSkills/plugins/plugin-creator
```

## クイックスタート

1. **構造を計画する**: 「コマンドとMCP統合を持つプラグインの構成は？」
   → plugin-structure スキルが案内する
2. **コンポーネントを作る**: 「PreToolUseでファイル書き込みを検証するフックを作って」
   → plugin-hooks スキルが実例とツールを提供する
3. **一気通貫で作る**: `/plugin-creator:create-plugin` でガイド付きワークフローを開始する

## 開発ワークフロー

```
構造設計（plugin-structure）
  → コンポーネント追加（各開発スキル）
  → 外部サービス統合（plugin-mcp)
  → 自動化追加（plugin-hooks + ユーティリティ）
  → テストと検証（plugin-validator / 各種 validate スクリプト）
```

## ベストプラクティス（全スキル共通）

- **セキュリティ第一**: フックでの入力検証、MCPは HTTPS/WSS、認証情報は環境変数
- **ポータビリティ**: Claude Code では `${CLAUDE_PLUGIN_ROOT}` を使い、相対パスのみ。
  両対応プラグインは中核をスキルで作り、マニフェストを2つ置き version を同期する
- **テスト**: デプロイ前の設定検証、サンプル入力でのフックテスト、
  `claude --debug` と `agy plugin validate`
- **ドキュメント**: 明確なREADME、環境変数の文書化、使用例の提供

## v1.0.0 移行注記（スキル名変更）

インストール済みユーザー向け。v1.0.0 でスキル名をプラグイン内単一プレフィックスに統一した（破壊的変更）:

| 旧名 | 新名 |
|---|---|
| `command-development` | `plugin-commands` |
| `agent-development` | `plugin-agents` |
| `hook-development` | `plugin-hooks` |
| `mcp-integration` | `plugin-mcp` |

## v1.1.0 移行注記（重複統廃合）

- `skill-development` → **`plugin-skills`** に改名し、プラグイン固有の考慮事項だけの
  薄い案内スキルに縮約（スキルの作り方の方法論は `skill-creator` プラグインに一本化）
- `skill-reviewer` エージェントを**削除**（検証観点は skill-creator の `skill-validator`、
  改善提案は `skill-optimizer` と重複のため。独自観点「記述スタイル」は
  skill-validator のチェックリスト E4 に吸収）
