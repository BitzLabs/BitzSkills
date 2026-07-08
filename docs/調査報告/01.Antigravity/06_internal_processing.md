# 6. 内部処理とアーキテクチャ詳細 (Internal Processing)

本章は、Google Antigravity の内部動作を、ワークスペース内の一次資料（`plugins/plugin-creator` および `plugins/skill-creator` 配下の各 `references/*.md`、`SKILL.md`）に忠実に整理し、外部の公開情報（Google Developers Blog、Google Codelabs、GitHub、PyPI 等）で裏取りした範囲で補足したものです。

> [!NOTE]
> **情報源の切り分け**: Google Antigravity は 2025年11月に Gemini 3 と同時に発表された実在の製品で、IDE / CLI `agy` / Python SDK `google-antigravity` の3面構成、`~/.gemini/config/` 配下の管理、`plugin.json`・`hooks.json`・`mcp_config.json`・`skills/`・`.agents/` といった骨格は実態と一致します。一方、Claude Code 互換レイヤーの詳細な対応表など細部は、本リポジトリのワークスペース資料（「実測」ベース）に依拠しており、`agy` のバージョンにより挙動が変わりうる点に留意してください。

---

## 6.1 Customization root の発見と探索アルゴリズム

Antigravity は3つの「customization root」から skills / rules / plugins / hooks / MCP を自動発見します。

1. **ワークスペース root**: `<repo>/.agents/`（別名 `.agent/` `_agents/` `_agent/` も同格）。**カレントディレクトリから `.git` のあるリポジトリルートまで階層的に遡って探索**します。Claude Code の `.claude/` 単一探索と異なり、モノレポのサブディレクトリで `agy` を叩いても親のルートまで正しく捕捉する設計です。
2. **ディレクトリルール**: `GEMINI.md` / `AGENTS.md` / `.agents/rules/*.md` を、編集中ファイルのディレクトリから上位へ遡って収集します。
3. **グローバル root**: `~/.gemini/config/`。

---

## 6.2 名前解決の優先順位（5段階）

同名のスキル・ルール・設定・プラグインが複数箇所にある場合、次の5段階で上位が勝ちます。

1. ワークスペース自動発見（階層探索で先に見つかったもの）
2. ワークスペース宣言的設定（`skills.json` / `plugins.json`）
3. グローバル自動発見（`~/.gemini/config/`）
4. 組み込み（built-in）customization
5. グローバル宣言的設定

この5段階はプラグイン管理（`agy plugin install/enable/disable`）とは独立したレイヤーです（`install` はコピー＋台帳登録、発見順位は別ロジック）。

---

## 6.3 フックの入出力契約（camelCase）の内部設計

Antigravity のフック契約が camelCase なのは、Go バイナリの Protobuf を JSON にマーシャリングした結果と推測されます（Claude Code の snake_case は Node.js/TypeScript 由来）。設計上の重要な差異は次のとおりです。

- **共通入力の `transcriptPath` / `artifactDirectoryPath` は起動元でディレクトリ名が変わる**（CLI は `antigravity-cli/`、Antigravity 本体は `antigravity/`、IDE は `antigravity-ide/`）。同じフックスクリプトを複数の起動元で使い回す際の落とし穴になります。
- **構造の非対称性**: `PreToolUse` / `PostToolUse` は `matcher` ＋ `hooks[]` のグループ構造ですが、`PreInvocation` / `PostInvocation` / `Stop` は配列を直接書くフラット構造です。Claude Code 側にはない仕様です。
- **同期・順次実行**: Claude Code が同一イベント内のフックを並列実行するのに対し、Antigravity のフックは**同期・順次実行でエージェントループをブロック**します。重いフックはそのまま応答遅延に直結します。
- **入力書き換え未実装**: `PreToolUse` でのツール引数の上書き（Claude Code の `updatedInput` 相当）は実装されていません。フックは「許可／拒否／確認」の判定のみが可能で、引数改変によるサニタイズはできません。

---

## 6.4 プラグイン自動発見・名前空間化の内部処理

プラグイン内 `plugin.json` の**存在そのものがプラグイン宣言**（必須フィールドなし）です。Claude Code のようにコンポーネントパスをマニフェストで指定するフィールド（`commands` / `agents` / `hooks` / `mcpServers`）は**解釈されず**、固定パス（`hooks.json`・`mcp_config.json`・`skills/`・`agents/`・`rules/`）のみがスキャン対象です。

名前衝突時は自動的に `<plugin_name>:<component_name>` 形式でプレフィックスされ、MCP ツール名は `mcp__plugin_<plugin_name>_<server_name>__<tool_name>` になります。フック・MCP・ルールはプラグインが有効（enabled）な間のみ作動し、`agy plugin disable` はコンポーネントを削除せず発見・登録フェーズをスキップさせます。

---

## 6.5 Claude Code 互換レイヤーの内部処理（実測ベース）

`agy plugin validate` / `install` はディレクトリ構造をスキャンし、Claude Code 形式のレイアウトを検知した場合に変換します。

- `commands/*.md` → **スキルへ変換**（description がトリガー材料になり、エージェントが自律判断で発動する形に変わる。ユーザーが `/` で明示起動する体験は失われる）
- `agents/*.md` → そのままサブエージェントとして取り込み
- `hooks/hooks.json`・`.mcp.json`・`.claude-plugin/plugin.json` は**いずれも検出されない**（Antigravity 側の固定パス規約に合わないため）

---

## 6.6 宣言的設定のパス解決内部ルール

`skills.json` / `plugins.json` の `entries[].path` は3パターンで解決されます。

1. `/` 始まり → 絶対パス
2. `~/` 始まり → ホームディレクトリ相対
3. それ以外 → **プロジェクトのリポジトリルート（`.git` のあるディレクトリ）相対**（カレントディレクトリ相対ではない）

`inherits[]` は別の設定ファイルを配列順にマージする継承機構で、`include_only` / `exclude` は正規表現によるフォルダ名フィルタです。
