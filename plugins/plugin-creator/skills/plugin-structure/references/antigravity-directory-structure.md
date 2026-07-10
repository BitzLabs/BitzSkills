# Antigravity 2.0 のディレクトリ構造と両対応プラグインの作り方

## ディレクトリ構造（Antigravity 2.0）

Antigravity のプラグインは customization root（プロジェクトの
`.agents/plugins/` またはグローバルの `~/.gemini/config/plugins/`）配下に置く:

```
plugin-name/
├── plugin.json          # 必須: ルート直下（このファイルの存在がプラグインの印）
├── mcp_config.json      # 任意: MCPサーバー定義
├── hooks.json           # 任意: フック（ルート直下。hooks/ フォルダではない）
├── rules/               # 任意: プラグイン有効時にマージされるルール（*.md）
└── skills/              # スキル（Claude Code と同形式）
    └── skill-name/
        └── SKILL.md
```

**Claude Code との主な違い:**

- マニフェストは**ルート直下**の `plugin.json`（`.claude-plugin/` は読まれない）。
  必須フィールドはなく、`name` 省略時はフォルダ名が使われる
- ネイティブのコンポーネントは skills / rules / hooks / MCP。
  `commands/` は agy CLI がインストール時に**スキルへ変換**し、
  `agents/*.md` はサブエージェントとして処理される（Claude 互換レイヤー）
- フックは `hooks.json`（書式も異なる。`plugin-hooks` スキル参照）、
  MCP は `mcp_config.json`（`.mcp.json` は読まれない）
- `${CLAUDE_PLUGIN_ROOT}` に相当する環境変数はない

### 両対応（クロスプラットフォーム）プラグインの作り方

1. **マニフェストを2つ置く**: `.claude-plugin/plugin.json`（Claude Code 用）と
   ルートの `plugin.json`（Antigravity 用）。`version` は常に同じ値に保つ
2. **中核はスキルで作る**: `skills/<name>/SKILL.md` は両プラットフォーム共通
   （Agent Skills 標準）で、最もポータブルなコンポーネント
3. **コマンドは「スキルに変換されても成立する」内容にする**: Claude Code 固有
   機能（`!` bash実行・`${CLAUDE_PLUGIN_ROOT}` 参照）に依存しすぎない
4. **フック・MCP を両対応させる場合はファイルを2系統置く**:
   `hooks/hooks.json` + `.mcp.json`（Claude Code）と
   `hooks.json` + `mcp_config.json`（Antigravity）
5. **両方で検証する**: `claude plugin validate <path>` と
   `agy plugin validate <path>`

配置場所・優先順位・plugins.json による宣言的登録などの詳細は
`references/antigravity-structure.md` を参照。

