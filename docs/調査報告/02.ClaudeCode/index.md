# Claude Code 仕様・機能 調査報告書

本書は、Anthropic 社が提供する自律型コーディングアシスタント **Claude Code** の CLI、SDK、拡張機能（プラグイン、フック、スキル、ツール、サブエージェント）、設定ファイル、内部処理、および Google Antigravity との互換性について詳細に調査した結果をまとめたものです。

> [!NOTE]
> 本書は 2026年7月時点の公式ドキュメント（code.claude.com / platform.claude.com）を確認し、公開情報に照合した内容として整理しています。モデル名、SDK の `maxTurns` / `settingSources`、フックイベント、マッチャー、テレメトリ設定、スラッシュコマンドなどは、公式仕様に沿って最新表現へ更新済みです。

## 目次

1. [概要 (Overview)](./01_overview.md)
   - コンセプトと基本設計 / 主な特徴 / 既存ツールとの違い / セキュリティ設計
2. [CLI リファレンス (CLI Reference)](./02_cli_reference.md)
   - インストール / 認証 / 実行モード / CLI 引数 / スラッシュコマンド
3. [SDK リファレンス (SDK Reference)](./03_sdk_reference.md)
   - インストール / 認証（Bedrock・Vertex）/ `query` API / コード例 / CI/CD 統合
4. [拡張機能とアーキテクチャ (Extensibility & Architecture)](./04_extensibility_architecture.md)
   - プラグイン / スキル / スラッシュコマンド / サブエージェント / フック / MCP / 互換性
5. [設定項目とカスタマイズ (Configuration & Customization)](./05_configuration_customization.md)
   - 設定の階層と優先順位 / settings.json / 変更方法 / local.md 駆動パターン
6. [内部処理とアーキテクチャ詳細 (Internal Processing)](./06_internal_processing.md)
   - 権限評価順序 / コンテキスト圧縮の3層 / CLAUDE.md 遅延ロード / サブエージェント分離 / タスク管理
7. [ベストプラクティス (Best Practices)](./07_best_practices.md)
   - CLAUDE.md / スキル設計 / フック / パーミッション / MCP / コスト最適化 / CI/CD / セキュリティ
8. [トラブルシューティング (Troubleshooting)](./08_troubleshooting.md)
   - コンテキスト溢れ / MCP 接続 / 権限 / 認証 / SDK 特有の落とし穴
9. [引用・参考リンク (References)](./09_references.md)
   - 公式情報ソース / ワークスペース内参照資材
