# Antigravity 2.0 プラグイン仕様（検証済み）

2026-07-06 調査。以下の一次情報に基づく（LLM の回答ではない）。

- **公式組み込みドキュメント**: `~/.gemini/antigravity-cli/builtin/skills/agy-customizations/`
  （`SKILL.md` と `docs/plugins.md` / `hooks.md` / `skills.md` / `rules.md` /
  `mcp_servers.md` / `json_configs.md`）
- **agy CLI の実挙動**: `agy plugin validate` / `install` / `uninstall` を
  最小フィクスチャと本リポジトリのプラグインで実測

> ⚠️ 同フォルダの `Antigravityプラグインとは？.md` / `Antigravityプラグインとは何か.md`
> （Gemini 生成）には実仕様と食い違う内容が多い。巻末の「Gemini 生成ドキュメントとの
> 相違点」を参照。

## プラグイン構造（公式）

プラグインは customization root（後述）内の `plugins/` 配下に置く1フォルダ。

```text
plugins/<plugin_name>/
├── plugin.json       # 必須: マニフェスト（ファイルの存在自体がプラグインの印）
├── mcp_config.json   # 任意: MCPサーバー定義
├── hooks.json        # 任意: ライフサイクルフック（ルート直下。hooks/ フォルダではない）
├── rules/            # 任意: プラグイン有効時にマージされるルール（*.md）
└── skills/           # 任意: スキル
    └── <skill_name>/
        └── SKILL.md
```

- **マニフェストはルート直下の `plugin.json`**。`.claude-plugin/plugin.json` は
  読まれない（実測: ルート `plugin.json` がないと `agy plugin validate` は
  `missing plugin.json` でエラー）。
- マニフェストの必須フィールドはなし。`name` すら省略可（省略時はフォルダ名）。
- スキルの `SKILL.md` 形式（frontmatter の `name` / `description` 必須、
  `scripts/` `references/` `examples/` `resources/` の同梱、progressive
  disclosure）は Claude Code / Agent Skills 標準と同じ。

## Claude Code 形式との互換レイヤー（agy CLI）

`agy plugin validate` / `install` は Claude Code レイアウトのプラグインを
そのまま受け付ける（実測）:

- `skills/` — そのまま処理
- `agents/*.md` — 処理される（サブエージェントとして）
- `commands/*.md` — **スキルに変換**して処理（Antigravity にプラグイン同梱の
  スラッシュコマンドという概念はない）
- `mcpServers` / `hooks` — Claude 形式（`hooks/hooks.json`・`.mcp.json`・
  マニフェスト内インライン）は **検出されない**（実測: すべて
  `skipped (not found)`）。Antigravity で有効にするにはルート直下の
  `hooks.json` / `mcp_config.json` が必要
- `agy plugin install <ローカルdir>` の実体は
  `~/.gemini/config/plugins/<name>/` への**そのままコピー** +
  `~/.gemini/config/import_manifest.json` への登録

## 配置場所（customization roots）と優先順位

1. **ワークスペース**: プロジェクトルートの `.agents/`（`.agent/` `_agents/`
   `_agent/` も可）→ プラグインは `.agents/plugins/<name>/`
2. **宣言的設定**: ワークスペースの `skills.json` / `plugins.json`
   （`entries[].path` で任意パスを登録、`inherits` で共有設定を継承、
   `include_only` / `exclude` は正規表現）
3. **グローバル**: `~/.gemini/config/` → プラグインは `~/.gemini/config/plugins/<name>/`
4. 組み込み → グローバル宣言的設定 の順に優先度が下がる。名前衝突は高優先が勝つ

## hooks.json（Claude Code と書式が異なる）

ルート直下の `hooks.json`。**トップレベルは「フック名 → 設定」のマップ**
（Claude Code の `{"hooks": {イベント: [...]}}` ラッパー形式ではない）:

```json
{
  "lint-checker": {
    "enabled": true,
    "PostToolUse": [
      {
        "matcher": "run_command",
        "hooks": [
          { "type": "command", "command": "./scripts/lint.sh", "timeout": 10 }
        ]
      }
    ]
  }
}
```

- **イベントは5種**: `PreToolUse` / `PostToolUse` / `PreInvocation` /
  `PostInvocation` / `Stop`（Claude Code の SessionStart / UserPromptSubmit /
  SubagentStop / PreCompact / Notification は存在しない）
- `PreToolUse` / `PostToolUse` は `matcher` + `hooks` のグループ形式、
  残り3イベントはハンドラ配列を直接書くフラット形式
- **matcher の対象は Antigravity のツール名**（`run_command`, `view_file`,
  `browser_.*` 等）。Claude Code の `Write|Edit` ではない
- ハンドラは `type: "command"` のみ（プロンプト型フックはない）。
  `timeout` の既定は 30 秒。**cwd は hooks.json のあるディレクトリ**
  （`${CLAUDE_PLUGIN_ROOT}` に相当する環境変数はない）
- 入出力は stdin/stdout の JSON（キーは **camelCase**）。
  `PreToolUse` の出力は `decision: "allow" | "deny" | "ask" | "force_ask"`、
  `Stop` は `decision: "continue"` で停止をブロック、
  `PreInvocation` / `PostInvocation` は `injectSteps` でステップ注入、
  `PostInvocation` は `terminationBehavior: "force_continue" | "terminate"` も可
- フックは**同期実行**でエージェントループをブロックする

## mcp_config.json

ルート直下の `mcp_config.json`（グローバルは `~/.gemini/config/mcp_config.json`）:

```json
{
  "mcpServers": {
    "sqlite-helper": {
      "command": "sqlite-mcp-server",
      "args": ["/path/to/database.db"],
      "env": { "DB_READONLY": "true" }
    },
    "remote-service": { "serverUrl": "https://mcp.mycompany.com/sse" }
  }
}
```

- 対応トランスポートは **stdio**（`command` / `args` / `env`）と
  **SSE**（`serverUrl`）の2種のみ。Claude Code の `type: http` / `ws` はない
- プラグイン提供ツールは必要に応じて自動で名前空間化される

## Rules（Claude Code のプラグインにない要素）

- プラグイン内 `rules/*.md` はプラグイン有効時にルールセットへマージされる
- ワークスペースでは `GEMINI.md` / `AGENTS.md`（ディレクトリ階層を遡って収集）
  や `.agents/rules/*.md` も使われる

## agy plugin サブコマンド（実測）

```text
list / import [source](gemini|claude) / install <target>（ローカルdir。
plugin@marketplace 表記対応） / uninstall <name> / enable <name> /
disable <name> / validate [path] / link <mp> <target>
```

## Gemini 生成ドキュメントとの相違点

`docs/Antigravityプラグインとは？.md` / `同 とは何か.md` の以下の記述は
実仕様に確認できない（誤りとして扱うこと）:

| Gemini の記述 | 実仕様 |
| --- | --- |
| `agent.json` / `subagents/*.json` / `presets/` / `extends` | 該当する仕組みは組み込みドキュメント・CLI に存在しない |
| `$schema: https://antigravity.google/...` 等のスキーマURL | 存在しない |
| hooks.json の `events` / `filters` / `action` / `redirect_to_sandbox` 書式 | 実書式は上記「hooks.json」の通り |
| `agy plugin install <GitHub URL>` | install はローカルディレクトリ（および marketplace 表記）のみ |
| `~/.gemini/antigravity-cli/plugins/` への配置 | グローバルは `~/.gemini/config/plugins/` |
| `ag call <subagent>` コマンド | 存在しない |
| プラグインへの `agent.json` 同梱可否の議論 | そもそもエージェント定義は `agents/*.md`（agy の Claude 互換レイヤー）で扱われる |

なお `.agents/plugins/` への配置、スキル/ルール/フック/MCP を束ねるという
プラグインの位置づけ、GEMINI.md 等のルールの説明はおおむね正しい。
