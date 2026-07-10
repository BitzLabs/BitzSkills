# AI開発エージェント (CLI / SDK) 詳細調査報告書

本報告書は、AIを活用した自律型開発エージェントを代表する3プラットフォーム「**Google Antigravity**」「**Claude Code**」「**OpenAI Codex**」の CLI、SDK、拡張機能（プラグイン、フック、スキル、ツール、サブエージェント）、設定項目、および**内部処理**について詳細に調査した結果をまとめたものです。

各エージェントの調査は、以下の統一された **9章構成** に整理されています。第6〜8章は 2026年7月時点の公式ドキュメントで裏取りした「内部処理・ベストプラクティス・トラブルシューティング」、第9章が参考リンクです。第1〜5章に含まれる旧世代の情報の正誤は、各レポートの第6章末尾「正誤一覧」に集約しています。

| 章 | 内容 |
| :--- | :--- |
| 1 | 概要 (Overview) |
| 2 | CLI リファレンス |
| 3 | SDK リファレンス |
| 4 | 拡張機能とアーキテクチャ |
| 5 | 設定項目とカスタマイズ |
| 6 | 内部処理とアーキテクチャ詳細（＋正誤一覧） |
| 7 | ベストプラクティス |
| 8 | トラブルシューティング |
| 9 | 引用・参考リンク |

---

## 📂 調査報告書インデックス

### 1. [Google Antigravity 調査報告書](./01.Antigravity/index.md)
*   **特徴**: エージェントファースト設計。Desktop IDE、CLI (`agy`)、Python SDK が同一の「Antigravity Runtime」で動作。2026年時点は Gemini 3 系を主軸に Claude / GPT-OSS 等を含む**マルチモデル**対応。
*   **拡張仕様**: Agent Skills 規格準拠、`plugin.json`、`hooks.json`（camelCase JSON 契約、5イベント）、stdio/SSE による MCP 統合、Claude Code 互換レイヤー。

### 2. [Claude Code 調査報告書](./02.ClaudeCode/index.md)
*   **特徴**: ターミナルネイティブな自律エージェントループ。非インタラクティブ実行、多様な認証。主力モデルは Claude Sonnet 5 / Opus 4.8 系（2026年7月時点）。
*   **拡張仕様**: `skills/`（Progressive Disclosure）、`commands/`、`agents/`、`hooks/hooks.json`（snake_case JSON 契約、多数のイベント）、MCP 統合。

### 3. [OpenAI Codex 調査報告書](./03.Codex/index.md)
*   **特徴**: 自律型開発エージェント。TUI と自動化（`exec`）モード、OS カーネルレベルの強固なサンドボックス、ChatGPT 契約連携。主力モデルは `gpt-5.5` 系（2026年7月時点）。
*   **拡張仕様**: `SKILL.md`（YAML フロントマター）、`.codex-plugin/plugin.json`、`config.toml` / `hooks.json`（Experimental フック）、MCP サーバー、`spawn_agent` 系のマルチエージェント。

### 4. [nexus-architect 退避スナップショット](./04.nexus-architect/_provenance.md)
*   **位置づけ**: 本報告書シリーズとは別枠の**参照資料**。bitz-sdd プラグインの蒸留元
    （MIT License）で、ローカル日本語訳 `*_ja.md` と Database 系スキル群の保全が目的。
    詳細は `_provenance.md` を参照。編集禁止のスナップショット。

---

## 📊 3大エージェント主要機能比較表

| 評価項目 | Google Antigravity | Claude Code | OpenAI Codex |
| :--- | :--- | :--- | :--- |
| **開発元** | Google | Anthropic | OpenAI |
| **主要 CLI** | `agy`（単一バイナリ） | `claude`（Node.js 製） | `codex`（Node.js 製） |
| **サポート SDK** | `google-antigravity` (Python) | `claude-agent-sdk` (Python / TypeScript) | `@openai/codex-sdk` (TS) / `openai-codex` (Python) |
| **主要モデル（2026-07）** | Gemini 3 系＋Claude/GPT-OSS（マルチモデル） | Claude Sonnet 5 / Opus 4.8 / Fable 5 等 | `gpt-5.5` / `gpt-5.4` / `gpt-5.4-mini` 等 |
| **プラグイン設定** | `plugin.json`（ルート直下） | `.claude-plugin/plugin.json` | `.codex-plugin/plugin.json` |
| **ライフサイクルフック** | `hooks.json`（ルート直下）※5イベント | `hooks/hooks.json`※多数のイベント（現行仕様で拡大） | `config.toml` / `hooks.json`（Experimental・Bash 中心・Windows 無効） |
| **フック JSON 命名規則** | `camelCase` | `snake_case` | `permissionDecision` 系＋exit code 2 |
| **フック種別** | command のみ | command / http / mcp_tool / prompt / agent | command（スクリプト） |
| **MCP サーバー統合** | stdio, SSE | stdio, SSE, HTTP, WebSocket | stdio, SSE, HTTP, WebSocket |
| **サブエージェント** | `agents/*.md`（互換インポート） | `agents/*.md`＋`Task` ツール（コンテキスト分離） | `spawn_agent` 系（`multi_agent`、明示起動のみ） |
| **動作設定ファイル** | `settings.json` / `skills.json` 等 | `settings.json` / `.local.md` パターン | `config.toml` |
| **セキュリティ・サンドボックス** | Terminal Sandbox | Permission Mode（deny 優先の評価順序） | OS カーネル（Seatbelt / Bubblewrap+seccomp / Windows 専用低権限ユーザー） |

> [!NOTE]
> 上表のフックイベント数・種別・サブエージェント内部名などは、各レポート第6章の裏取り結果を反映しています。特に Claude Code のフックイベントは旧版の「9種類」から現行仕様で大きく拡張されており、Codex のフック／プラグイン／サブエージェントは実在するものの Experimental・明示起動のみといった制約があります。詳細と出典は各章を参照してください。

---

## 📝 調査を通じて得られた設計の共通パターン

1.  **段階的開示 (Progressive Disclosure)**
    *   3エージェントすべてで、コンテキスト（トークン長）を節約するため、スキルのメタデータ（名前・説明）のみを最初に提示し、必要時に詳細（本文・スクリプト）を読み込む設計が共通採用されています。
2.  **Model Context Protocol (MCP) の標準採用**
    *   外部リソース（データベース、検索、外部 API）をエージェントに公開する通信規格として、MCP がデファクトスタンダードとして組み込まれています。
3.  **自律アクションと人間によるコントロールの両立**
    *   「全自動」から「確認あり」まで、実行時の承認レベルを細かく制御する仕組み（Permission Mode / Approval Mode / Tool Permission）が各 CLI/SDK に配備されています。
4.  **コンテキスト管理と圧縮**
    *   長時間セッションでのコンテキスト劣化（context rot）を避けるため、自動コンパクション、サブエージェントへのノイズ隔離、プロジェクト規約ファイル（CLAUDE.md / AGENTS.md / GEMINI.md）の永続注入が共通のテーマになっています。
5.  **決定論的ガードレールとしてのフック**
    *   モデルの曖昧判断に依存しない安全境界として、`PreToolUse` 等のフックでツール実行を機械的に allow/deny する設計が各プラットフォームで採用されています（ただし完全な強制境界ではなくガードレールと位置づけられます）。
