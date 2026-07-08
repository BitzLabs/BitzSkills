# AI開発エージェント (CLI / SDK) 詳細調査報告書

本報告書は、AIを活用した自律型開発エージェントを代表する3つのプラットフォーム「**Google Antigravity 2.0**」「**Claude Code**」「**OpenAI Codex**」のCLI、SDK、拡張機能（プラグイン、フック、スキル、ツール、サブエージェント）、設定項目について詳細に調査した結果をまとめたものです。

各エージェントの個別調査結果へは、以下のリンクからアクセスできます。

---

## 📂 調査報告書インデックス

### 1. [Google Antigravity 2.0 調査報告書](file:///d:/44.BitzLabs/BitzSkills/docs/調査報告/01.Antigravity/index.md)
*   **特徴**: エージェントファースト設計。Desktop IDE、Go製 CLI (`agy`)、Python SDKが同一の「Antigravity Runtime」で動作。
*   **拡張仕様**: Skills規格準拠、`plugin.json`、`hooks.json`（camelCase JSON契約）、stdio/SSE による MCP 統合。

### 2. [Claude Code 調査報告書](file:///d:/44.BitzLabs/BitzSkills/docs/調査報告/02.ClaudeCode/index.md)
*   **特徴**: ターミナルネイティブな自律エージェントループ。非インタラクティブ実行や、多様な認証オプション（SSO、Console、長期トークン）を提供。
*   **拡張仕様**: `skills/`（Progressive Disclosure）、`commands/`（プロンプト＆!実行）、`agents/`（トリガー例）、`hooks/hooks.json`（snake_case JSON契約）、MCP統合。

### 3. [OpenAI Codex 調査報告書](file:///d:/44.BitzLabs/BitzSkills/docs/調査報告/03.Codex/index.md)
*   **特徴**: 自律型開発エージェント。TUIと自動化(`exec`)モード、OSカーネルレベルの強固なサンドボックス（Seatbelt, Landlock等）、ChatGPT契約連携。
*   **拡張仕様**: `SKILL.md`（YAMLフロントマター）、`.codex-plugin/plugin.json`、`config.toml` を介したフックとMCPサーバーの登録、コンテキストを分離したSubagents。

---

## 📊 3大エージェント主要機能比較表

| 評価項目 | Google Antigravity 2.0 | Claude Code | OpenAI Codex |
| :--- | :--- | :--- | :--- |
| **開発元** | Google | Anthropic | OpenAI |
| **主要 CLI** | `agy` (Go言語製) | `claude` (Node.js製) | `codex` (Node.js製) |
| **サポート SDK** | `google-antigravity` (Python) | `claude-agent-sdk` (Python / TypeScript) | `@openai/codex-sdk` (TypeScript) / `openai-codex` (Python) |
| **プラグイン設定** | `plugin.json` (ルート直下) | `.claude-plugin/plugin.json` | `.codex-plugin/plugin.json` |
| **ライフサイクルフック** | `hooks.json` (ルート直下)<br>※`Pre/PostToolUse` 等5種 | `hooks/hooks.json`<br>※`PreToolUse`, `UserPromptSubmit` 等9種 | `config.toml` での定義 または プラグイン内 `hooks` 設定 |
| **フック JSON 命名規則**| `camelCase` | `snake_case` | `camelCase` |
| **フック種別** | コマンドフックのみ | コマンド / プロンプトベースの両対応 | コマンド（スクリプト）フックのみ |
| **MCP サーバー統合** | stdio, SSE | stdio, SSE, HTTP, WebSocket | stdio, SSE, HTTP, WebSocket |
| **サブエージェント** | `agents/*.md` (互換インポート) | `agents/*.md` (YAML description トリガー例) | `delegate_to_subagent` (スレッド・コンテキスト分離) |
| **動作設定ファイル** | `settings.json` / `skills.json` 等 | `settings.json` / `.local.md` パターン | `config.toml` |
| **セキュリティ・サンドボックス** | Terminal Sandbox | Permission Mode (`acceptEdits` 等の制御) | OSカーネルのサンドボックス (`Seatbelt` / `Landlock` / Windows ACL) |

---

## 📝 調査を通じて得られた設計の共通パターン

1.  **段階的開示 (Progressive Disclosure)**
    *   3つのエージェントすべてにおいて、LLM のコンテキストウィンドウ（Token長）を節約するため、スキルのメタデータ（名前・説明）だけを最初に提示し、必要になったタイミングで詳細（本文やスクリプト）を読み込む設計が共通して採用されています。
2.  **Model Context Protocol (MCP) の標準採用**
    *   外部リソース（データベース、検索、外部API）をエージェントに公開する通信規格として、MCPがデファクトスタンダードとして組み込まれています。
3.  **自律アクションと人間によるコントロールの両立**
    *   「全自動（フルオート）」から「確認あり（プロンプト表示）」まで、セキュリティおよび安全性の観点から実行時の承認レベルを細かく制御する仕組み（Permission Mode, Approval Mode, Tool Permission）が各CLI/SDKに配備されています。
