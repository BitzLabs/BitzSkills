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
2. **skill-development** — progressive disclosure と強いトリガーを持つスキル作成
3. **command-development** — frontmatter・引数・対話機能を持つスラッシュコマンド作成
4. **agent-development** — AI支援生成を含む自律エージェント作成
5. **hook-development** — フックAPIとイベント駆動自動化（Antigravity 別仕様を含む）
6. **mcp-integration** — MCP（Model Context Protocol）サーバー統合
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
| **skill-reviewer** | description品質・progressive disclosure・記述スタイルのレビュー | cyan |

## スキル詳細

### plugin-structure

**トリガー例:** 「プラグインを作りたい」「plugin.jsonの書き方」「プラグイン構成」

構成: SKILL.md + references 2本（manifest-reference / component-patterns）+
examples 3本（minimal / standard / advanced）

### skill-development

**トリガー例:** 「プラグインにスキルを追加」「descriptionを改善」

構成: SKILL.md + references 1本（skill-creator-methodology）。
体系的なスキル開発フローは `skill-creator` プラグインとも連携する。

### command-development

**トリガー例:** 「スラッシュコマンドを作りたい」「コマンドの引数」「対話的なコマンド」

構成: SKILL.md + references 7本（frontmatter / plugin-features / interactive /
advanced-workflows / documentation / testing / marketplace）+ examples 2本

### agent-development

**トリガー例:** 「エージェントを作りたい」「エージェントのfrontmatter」

構成: SKILL.md + references 3本（生成プロンプト / システムプロンプト設計 /
トリガーexample）+ examples 2本 + scripts 1本（validate-agent.sh）

### hook-development

**トリガー例:** 「フックを作りたい」「PreToolUseフック」「危険なコマンドをブロック」

構成: SKILL.md + references 3本（patterns / migration / advanced）+
examples 3本（.sh）+ scripts 3本（validate-hook-schema / test-hook / hook-linter）

### mcp-integration

**トリガー例:** 「MCPサーバーを追加」「.mcp.jsonの設定」「外部サービス連携」

構成: SKILL.md + references 3本（server-types / authentication / tool-usage）+
examples 3本（stdio / sse / http の設定JSON）

### plugin-settings

**トリガー例:** 「プラグイン設定を保存」「.local.mdファイル」

構成: SKILL.md + references 2本（parsing-techniques / real-world-examples）+
examples 3本 + scripts 2本（validate-settings / parse-frontmatter）

## インストール

```bash
# Claude Code（マーケットプレイス経由）
/plugin marketplace add BitzLabs/BitzSkills
/plugin install plugin-creator@bitzskills

# Antigravity 2.0
agy plugin install /path/to/BitzSkills/plugins/plugin-creator

# 開発時（Claude Code ローカル直接指定）
claude --plugin-dir /path/to/BitzSkills/plugins/plugin-creator
```

## クイックスタート

1. **構造を計画する**: 「コマンドとMCP統合を持つプラグインの構成は？」
   → plugin-structure スキルが案内する
2. **コンポーネントを作る**: 「PreToolUseでファイル書き込みを検証するフックを作って」
   → hook-development スキルが実例とツールを提供する
3. **一気通貫で作る**: `/plugin-creator:create-plugin` でガイド付きワークフローを開始する

## 開発ワークフロー

```
構造設計（plugin-structure）
  → コンポーネント追加（各開発スキル）
  → 外部サービス統合（mcp-integration)
  → 自動化追加（hook-development + ユーティリティ）
  → テストと検証（plugin-validator / 各種 validate スクリプト）
```

## ベストプラクティス（全スキル共通）

- **セキュリティ第一**: フックでの入力検証、MCPは HTTPS/WSS、認証情報は環境変数
- **ポータビリティ**: Claude Code では `${CLAUDE_PLUGIN_ROOT}` を使い、相対パスのみ。
  両対応プラグインは中核をスキルで作り、マニフェストを2つ置き version を同期する
- **テスト**: デプロイ前の設定検証、サンプル入力でのフックテスト、
  `claude --debug` と `agy plugin validate`
- **ドキュメント**: 明確なREADME、環境変数の文書化、使用例の提供
