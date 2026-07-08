﻿# Google Antigravity 2.0 調査報告書 - インデックス

本書は、Google が提供するエージェントファーストの次世代開発プラットフォーム「**Google Antigravity 2.0**」に関する仕様、動作、アーキテクチャ、および拡張機能（スキル、プラグイン、フック、ツール、サブエージェント）の調査結果をまとめたドキュメント群のインデックスです。

以下の各章ごとに詳細な仕様をまとめています。リンク先より各ドキュメントを参照してください。

---

## 目次 (Table of Contents)

### [1. 概要 (Overview)](file:///d:/44.BitzLabs/BitzSkills/docs/調査報告/01.Antigravity/01_overview.md)
*   Antigravity 2.0 の基本コンセプト（エージェントファースト設計）
*   主要3コンポーネント（Desktop IDE, CLI, SDK）の役割
*   プラットフォーム全体の主要な特徴と動作原理

### [2. CLI リファレンス (CLI Reference)](file:///d:/44.BitzLabs/BitzSkills/docs/調査報告/01.Antigravity/02_cli_reference.md)
*   軽量 Go 製 CLI `agy` コマンドの使い方と主要オプション
*   プラグイン管理サブコマンド（list, install, uninstall, enable, disable, validate, import）
*   TUI（Terminal User Interface）上の対話的スラッシュコマンド（/config, /mcp, /logout 等）
*   認証フロー（ブラウザベース OAuth と SSH/リモート環境での挙動）

### [3. SDK リファレンス (SDK Reference)](file:///d:/44.BitzLabs/BitzSkills/docs/調査報告/01.Antigravity/03_sdk_reference.md)
*   Python SDK (`google-antigravity`) のインストールと基本設定
*   認証方法の切り替え（Application Default Credentials、Vertex AI 統合、API キー）
*   基本実装コード例（非同期チャット、コンテキスト管理）
*   外部システムや CI/CD パイプラインとの統合方法

### [4. 拡張機能とアーキテクチャ (Extensibility & Architecture)](file:///d:/44.BitzLabs/BitzSkills/docs/調査報告/01.Antigravity/04_extensibility_architecture.md)
*   **Skills（スキル）**: `SKILL.md` の仕様、Progressive Disclosure 仕組み
*   **Plugins（プラグイン）**: ディレクトリ構造、マニフェスト（`plugin.json`）定義、Claude Code 互換レイヤー
*   **Hooks（フック）**: ライフサイクルフック（Pre/PostToolUse, Pre/PostInvocation, Stop）、入出力 JSON 契約（camelCase 仕様）、Claude Code との比較
*   **Tools（ツール）**: 組み込みツール一覧、MCP サーバー統合（stdio, SSE, HTTP, WebSocket）および命名規則
*   **Subagents（サブエージェント）**: 設計、システムプロンプト、トリガー条件（`<example>` ブロックの構造と commentary）

### [5. 設定項目とカスタマイズ (Configuration & Customization)](file:///d:/44.BitzLabs/BitzSkills/docs/調査報告/01.Antigravity/05_configuration_customization.md)
*   グローバル設定（`settings.json` の項目詳細: colorScheme, sandbox, toolPermission 等）
*   プロジェクト別設定（`.agents/` ディレクトリ構造、`skills.json` / `plugins.json` 宣言的設定とパス解決ルール）
*   読み込みの優先順位と競合解決ロジック
*   環境変数とプロキシ環境における注意点

### [6. 引用・参考リンク (References)](file:///d:/44.BitzLabs/BitzSkills/docs/調査報告/01.Antigravity/06_references.md)
*   公式ドキュメントおよびソースへの参照リンク
*   ワークスペース内の調査対象ファイル一覧
