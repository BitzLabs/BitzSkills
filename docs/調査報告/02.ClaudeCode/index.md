# Claude Code 仕様・機能 調査報告書

本書は、Anthropic社が提供する自律型コーディングアシスタント **Claude Code** の CLI、SDK、拡張機能（プラグイン、フック、スキル、ツール、サブエージェント）、設定ファイル、および Google Antigravity 2.0 との互換性について詳細に調査した結果をまとめたものです。

## 目次

1. [概要 (Overview)](./01_overview.md)
   - 1.1 コンセプトと基本設計
   - 1.2 主な特徴
   - 1.3 既存のコーディングアシスタントとの違い
   - 1.4 セキュリティとプライバシー設計
2. [CLI リファレンス (CLI Reference)](./02_cli_reference.md)
   - 2.1 インストール方法
   - 2.2 認証 (Authentication)
   - 2.3 基本的な実行方法
   - 2.4 CLI 引数とオプション
   - 2.5 主要なサブコマンド
3. [SDK リファレンス (SDK Reference)](./03_sdk_reference.md)
   - 3.1 インストール方法
   - 3.2 認証設定 (Authentication)
   - 3.3 主要 API とオプション
   - 3.4 基本コード例
   - 3.5 CI/CD および外部システムとの統合方法
4. [拡張機能とアーキテクチャ (Extensibility & Architecture)](./04_extensibility_architecture.md)
   - 4.1 プラグイン (Plugins)
   - 4.2 スキル (Skills)
   - 4.3 コマンド (Slash Commands)
   - 4.4 サブエージェント (Subagents)
   - 4.5 ライフサイクルフック (Hooks)
   - 4.6 MCP 統合 (Tools)
   - 4.7 プラットフォーム互換性 (Antigravity 2.0 との違い)
5. [設定項目とカスタマイズ (Configuration & Customization)](./05_configuration_customization.md)
   - 5.1 設定の階層構造と優先順位 (Settings Hierarchy)
   - 5.2 settings.json の主要設定項目
   - 5.3 設定の変更方法
   - 5.4 独自のプラグイン設定パターン (local.md駆動)
6. [引用・参考リンク (References)](./06_references.md)
   - 6.1 公式情報ソース
   - 6.2 ワークスペース内参照資材
