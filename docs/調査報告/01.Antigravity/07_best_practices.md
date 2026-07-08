# 7. ベストプラクティス (Best Practices)

本章は、Claude Code と Antigravity の両対応プラグイン／スキルを設計するための実務指針を、ワークスペース内の一次資料（`plugin-structure`・`hook-development`・`agent-development`・`mcp-integration`・`command-development` の各 SKILL.md / references）から抽出したものです。本リポジトリ（`bitzskills`）が両プラットフォーム配布を目的とするため、互換性を軸に整理します。

---

## 7.1 プラグイン／スキル設計

**中核はスキルで作る。** `skills/<name>/SKILL.md` は Agent Skills 標準準拠で両プラットフォーム完全共通の、最もポータブルなコンポーネントです。両対応プラグインの中心に据えます。

**マニフェストは2つ、version は同期。** `.claude-plugin/plugin.json`（Claude Code 用）とルート直下 `plugin.json`（Antigravity 用）を両方置き、`name` / `description` / `version` を常に一致させます。リリースチェックリストに version 同期を明記します。

**コマンドは「スキルに変換されても成立する」内容にする。** `commands/*.md` は Antigravity で自動的にスキルへ変換されるため、`$ARGUMENTS` / `$1` の引数展開や Claude Code 固有機能（`!` bash 実行、`${CLAUDE_PLUGIN_ROOT}`）に依存しすぎず、description に「いつ使うか」をトリガーフレーズ込みで強く書きます。

**サブエージェントは `model: inherit` を使う。** `sonnet` / `opus` / `haiku` は Claude Code 固有のモデル名で、Antigravity は Gemini 系（＋マルチモデル）で動くため、両対応プラグインでは必ず `inherit` にします。`tools` 制限フィールドは Claude Code 固有の可能性が高く、Antigravity 側で解釈されない前提で、安全性を `tools` 制限だけに依存させないようにします。

---

## 7.2 フック活用（両対応構成）

フック本体（検証ロジック）を共通化し、プラットフォーム別の薄いアダプタから呼ぶ構成が推奨されます。

```
plugin-name/
├── hooks/hooks.json     # Claude Code 用
├── hooks.json           # Antigravity 用
└── scripts/
    ├── check-core.sh    # 共通ロジック（引数受け取り・終了コードで返す）
    ├── cc-adapter.sh    # snake_case stdin → check-core → CC 形式 stdout
    └── agy-adapter.sh   # camelCase stdin → check-core → AGY 形式 stdout
```

- **matcher はツール名体系が別物**（Claude Code: `Write`/`Edit`/`Bash`、Antigravity: `run_command`/`view_file`/`browser_.*`）。同じ正規表現を使い回すと誤ってマッチしません。
- **同期実行前提でタイムアウトを短く**。Antigravity のフックは並列実行されず順次ブロッキングなので、command 型のみで完結する軽量な検証に絞ります。
- **cwd は `hooks.json` のあるディレクトリ**なので、スクリプト参照は相対パス（`./scripts/...`）で統一します（`${CLAUDE_PLUGIN_ROOT}` 相当の変数はありません）。

---

## 7.3 MCP 設定の書き分け

MCP 設定は `.mcp.json`（Claude Code）と `mcp_config.json`（Antigravity）を両方用意します。**SSE サーバーはキー名の違い**（Claude Code は `type: "sse"` ＋ `url`、Antigravity は `serverUrl` のみ）に注意して書き分けます。Antigravity は stdio と SSE のみ対応（HTTP/WebSocket 非対応）なので、両対応を狙うプラグインは HTTP/WebSocket 専用サーバーを Antigravity 側の必須機能にしません。

---

## 7.4 宣言的設定の使い方

標準の発見場所（`.agents/`・`~/.gemini/config/`）以外にチーム共有ディレクトリを参照したい場合のみ `skills.json` / `plugins.json` を使います。過剰に使うと優先順位の把握が難しくなるため、まずは自動発見に頼る設計を基本とします。`inherits` で他チームの設定を継承する際は `include_only` で明示的に絞り込み、意図しないプラグインの巻き込みを防ぎます。

---

## 7.5 配布前の二重検証

両対応プラグインでは、配布前に **`agy plugin validate <path>` と `claude plugin validate <path>` の両方**を実行します。互換レイヤーで検出されない配置（第8章参照）はエラーにならずサイレントに無視されるため、実際に両プラットフォームで起動して動作確認するまでを配布フローに含めます。
