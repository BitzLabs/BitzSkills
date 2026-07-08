# OpenAI Codex CLI & SDK 調査報告

このドキュメントは、OpenAI が提供するターミナルベースの自律型コーディングエージェント「OpenAI Codex CLI（`codex` コマンド）」および「SDK」の仕様、アーキテクチャ、拡張性、設定方法について調査した包括的な報告書です。

情報量が大きいため、以下の各章ごとに別ファイルに分割して詳細をまとめています。

---

## 📄 各章へのリンク (Table of Contents)

### 1. [概要 (Overview)](./01_overview.md)
- エージェントのコンセプト
- 基本設計（Codex App Server、段階的開示など）
- 安全性と拡張性の特徴

### 2. [CLI リファレンス (CLI Reference)](./02_cli_reference.md)
- コマンドライン引数、オプション、サブコマンド詳細（`exec`, `resume` など）
- 認証（`codex login`）、プロジェクトの初期化（`/init`）
- TUI 内でのスラッシュコマンド一覧

### 3. [SDK リファレンス (SDK Reference)](./03_sdk_reference.md)
- 対応言語（TypeScript, Python）とインストール方法
- 主要 API と基本コード例（スレッド作成、タスク実行、ストリーミング）
- 双方向 JSON-RPC プロトコル（`codex-app-server`）の解説
- CI/CD パイプラインとの統合方法

### 4. [拡張機能とアーキテクチャ (Extensibility & Architecture)](./04_extensibility_architecture.md)
- **Skills**: `SKILL.md` の YAML メタデータ構造と「段階的開示」の動作
- **Plugins**: `.codex-plugin/plugin.json` マニフェストの仕様とフォルダ構成
- **Hooks**: `PreToolUse` や `PostCompact` 等のイベント体系と入出力 JSON 契約（終了コード 2 によるブロック）
- **Tools**: 組み込みツールと Model Context Protocol (MCP) 統合
- **Subagents**: 隔離されたコンテキストによるタスク並列処理設計
- **固有機能**: プラットフォーム別サンドボックス技術（Seatbelt, Landlock, Windows ACLs）およびメモリ・状態管理

### 5. [設定項目とカスタマイズ (Configuration & Customization)](./05_configuration_customization.md)
- グローバルとプロジェクト別の `config.toml` 設定ファイルの優先順位
- 環境変数 (`CODEX_HOME`, `OPENAI_API_KEY`)
- 動作モード（承認レベル: `suggest`, `auto-edit`, `full-auto`）とルールファイル

### 6. [引用・参考リンク (References)](./06_references.md)
- 公式ドキュメント、関連リポジトリ、標準規格（`AGENTS.md` 含む）、セキュリティ情報等の参照元URL

---

## 🛠️ クイックスタート (Quick Start)

### 1. インストール
お使いの環境に応じて以下を実行し、CLIをインストールします。

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
ブラウザが開き、ChatGPTサブスクリプションアカウントまたはAPI認証が完了すると、利用可能になります。

### 3. 実行
インタラクティブに会話を開始するには、ターミナルで `codex` を実行します。
```bash
codex
```
非インタラクティブに実行（自動実行）する場合は `exec` を使用します。
```bash
codex exec "Fix the linting issues in src/utils.ts"
```
