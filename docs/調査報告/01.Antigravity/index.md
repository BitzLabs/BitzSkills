# Google Antigravity 調査報告書 - インデックス

本書は、Google が提供するエージェントファーストの開発プラットフォーム「**Google Antigravity**」（本書では発表時の呼称を踏まえ "2.0" 系を対象）に関する仕様、動作、アーキテクチャ、拡張機能（スキル、プラグイン、フック、ツール、サブエージェント）、内部処理の調査結果をまとめたドキュメント群のインデックスです。

> [!NOTE]
> Antigravity は 2025年11月に Gemini 3 と同時発表された実在の製品です。骨格（IDE / CLI `agy` / SDK、`~/.gemini/config/`、`plugin.json`・`hooks.json`・`mcp_config.json` 等）は実態と一致しますが、Claude Code 互換レイヤーの詳細はワークスペース内の「実測」資料に依拠しており `agy` のバージョンで変わりうる点に留意してください。以前は第6章末尾に集約していた正誤・補足（モデルのマルチモデル対応、UX 概念、MCP 接続方式、`toolPermission` 等）は、各章へ最新仕様として反映済みです。

---

## 目次 (Table of Contents)

### [1. 概要 (Overview)](./01_overview.md)
*   エージェントファースト設計 / 主要3コンポーネント（Desktop IDE, CLI, SDK）/ Antigravity Runtime / 主要な特徴

### [2. CLI リファレンス (CLI Reference)](./02_cli_reference.md)
*   `agy` コマンドと主要オプション / プラグイン管理サブコマンド / TUI スラッシュコマンド / 認証フロー

### [3. SDK リファレンス (SDK Reference)](./03_sdk_reference.md)
*   Python SDK (`google-antigravity`) / 認証（ADC・Vertex AI・API キー）/ 実装コード例 / CI/CD 統合

### [4. 拡張機能とアーキテクチャ (Extensibility & Architecture)](./04_extensibility_architecture.md)
*   Skills / Plugins / Hooks（camelCase 契約）/ Tools・MCP / Subagents / Claude Code 互換レイヤー

### [5. 設定項目とカスタマイズ (Configuration & Customization)](./05_configuration_customization.md)
*   グローバル／プロジェクト設定 / 読み込み優先順位 / 宣言的設定（skills.json・plugins.json）/ 環境変数・プロキシ

### [6. 内部処理とアーキテクチャ詳細 (Internal Processing)](./06_internal_processing.md)
*   customization root 探索 / 5段階の名前解決 / フック内部契約 / 名前空間化 / 互換レイヤー内部 / 宣言的設定のパス解決

### [7. ベストプラクティス (Best Practices)](./07_best_practices.md)
*   両対応プラグイン設計 / フックのアダプタ構成 / MCP 書き分け / 宣言的設定 / 配布前の二重検証

### [8. トラブルシューティング (Troubleshooting)](./08_troubleshooting.md)
*   互換レイヤーの非検出 / install=実体コピー / 名前空間衝突 / プロキシ / 起動元差異

### [9. 引用・参考リンク (References)](./09_references.md)
*   公式ドキュメント / ワークスペース内参照ソース
