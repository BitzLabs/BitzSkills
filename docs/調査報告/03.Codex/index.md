# OpenAI Codex CLI & SDK 調査報告

本書は、OpenAI が提供するターミナルベースの自律型コーディングエージェント「OpenAI Codex CLI（`codex` コマンド）」および SDK の仕様、アーキテクチャ、拡張性、設定、内部処理について調査した包括的な報告書です。

> [!NOTE]
> 第6〜8章は 2026年7月時点の公式ドキュメント（developers.openai.com/codex、openai/codex GitHub、OpenAI Blog）で裏取りしています。第1〜5章に含まれる旧世代・不正確な記述（承認モードの用語、モデル名、SDK API、サンドボックス実装、サブエージェント内部ツール名など）の正誤は、第6章末尾の「正誤一覧」に集約しています。

---

## 📄 各章へのリンク (Table of Contents)

### [1. 概要 (Overview)](./01_overview.md)
- エージェントのコンセプト / Codex App Server / 段階的開示 / 安全性と拡張性

### [2. CLI リファレンス (CLI Reference)](./02_cli_reference.md)
- サブコマンド（`exec`, `resume`, `apply`, `mcp` 等）/ グローバルオプション / 認証 / `/init` / スラッシュコマンド

### [3. SDK リファレンス (SDK Reference)](./03_sdk_reference.md)
- TypeScript / Python SDK / スレッド・ターン API / ストリーミング / JSON-RPC / CI/CD 統合

### [4. 拡張機能とアーキテクチャ (Extensibility & Architecture)](./04_extensibility_architecture.md)
- Skills / Plugins / Hooks / Tools・MCP / Subagents / サンドボックス技術 / AGENTS.md

### [5. 設定項目とカスタマイズ (Configuration & Customization)](./05_configuration_customization.md)
- `config.toml` の優先順位と項目 / 環境変数 / 承認モード / ルールファイル

### [6. 内部処理とアーキテクチャ詳細 (Internal Processing)](./06_internal_processing.md)
- AGENTS.md マージ / コンパクション / サブエージェントと context rot / Auto-review / ネットワーク制御 / OS 別サンドボックス実装 / **正誤一覧**

### [7. ベストプラクティス (Best Practices)](./07_best_practices.md)
- 承認モード / `--yolo` 運用 / AGENTS.md 設計 / Auto-review / サブエージェント / MCP / CI/CD / コスト / セキュリティ

### [8. トラブルシューティング (Troubleshooting)](./08_troubleshooting.md)
- Linux サンドボックス / 承認ハング / ネットワーク / Hooks / 認証 / MCP タイムアウト

### [9. 引用・参考リンク (References)](./09_references.md)
- 公式ドキュメント / リポジトリ / 標準規格 / セキュリティ情報

---

## 🛠️ クイックスタート (Quick Start)

### 1. インストール
* **Node.js (npm):** `npm install -g @openai/codex`
* **macOS / Linux (Homebrew):** `brew install --cask codex`
* **Windows (PowerShell):**
  ```powershell
  powershell -ExecutionPolicy ByPass -c "irm https://chatgpt.com/codex/install.ps1 | iex"
  ```

### 2. ログイン認証
```bash
codex login
```

### 3. 実行
```bash
codex                                      # インタラクティブ TUI
codex exec "Fix the linting issues in src/utils.ts"   # 非インタラクティブ（自動実行）
```
