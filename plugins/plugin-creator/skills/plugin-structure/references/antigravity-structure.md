# Antigravity 2.0 プラグイン構造 リファレンス

Antigravity 2.0（agy CLI / IDE）のプラグイン・customization システムの詳細。
出典は Antigravity 組み込みドキュメント
（`~/.gemini/antigravity-cli/builtin/skills/agy-customizations/docs/`）と
agy CLI の実測挙動。

## Customization roots（発見場所）

Antigravity は次の場所から customization（skills / rules / plugins /
hooks / MCP）を自動発見する:

1. **ワークスペース**: プロジェクトルートの `.agents/`
   （`.agent/` `_agents/` `_agent/` も可）。カレントディレクトリから
   リポジトリルート（`.git` のあるフォルダ）まで遡って探索される。
   チーム共有は VCS にコミットして行う
2. **ディレクトリ・ルール**: `GEMINI.md` / `AGENTS.md` / `.agents/rules/*.md`。
   編集中ファイルのディレクトリから上位へ遡って収集される
3. **グローバル**: `~/.gemini/config/`。マシン上の全プロジェクトに適用

各 root 内の配置:

| 種類 | 場所（root 相対） |
| --- | --- |
| スキル | `skills/<skill_name>/SKILL.md` |
| ルール | `rules/*.md`、または単体の `GEMINI.md` / `AGENTS.md` |
| プラグイン | `plugins/<plugin_name>/` |
| MCP | `mcp_config.json` |
| フック | `hooks.json` |

## 読み込み優先順位

名前が衝突した場合、高優先の customization が勝つ:

1. ワークスペース（CWD からリポジトリルートへの階層探索）
2. ワークスペースの宣言的設定（`skills.json` / `plugins.json`）
3. グローバル発見（`~/.gemini/config/`）
4. 組み込み customization
5. グローバルの宣言的設定

## プラグイン構造

```text
plugins/<plugin_name>/
├── plugin.json       # 必須: マニフェスト
├── mcp_config.json   # 任意: MCPサーバー
├── hooks.json        # 任意: ライフサイクルフック
├── rules/            # 任意: *.md（プラグイン有効時にマージ）
└── skills/
    └── <skill_name>/
        └── SKILL.md
```

### マニフェスト（plugin.json）

ルート直下に置く。**このファイルの存在自体が「プラグインである」宣言**。

```json
{ "name": "team-developer-kit" }
```

- `name`（文字列、任意）: 表示名。省略時はフォルダ名
- 必須フィールドはない。`version` / `description` / `author` などを
  書いても害はない（agy は無視するが、人間向けメタデータとして有効）

### 動作

プラグインが発見・有効化されると:

1. **自動取り込み**: skills / rules / hooks / MCP がすべて読み込まれる
2. **名前空間化**: ツール・スキル名は衝突時に自動でプレフィックスされる
3. **ライフサイクルスコープ**: フック・MCP・ルールはプラグイン有効時のみ動く

## 宣言的設定（skills.json / plugins.json）

標準の発見場所以外に置いた customization を登録する。customization root
（`.agents/` またはグローバル `~/.gemini/config/`）に置く。両ファイル共通スキーマ:

```json
{
  "inherits": [
    {
      "path": "/path/to/shared/plugins.json",
      "include_only": ["linter-.*"],
      "exclude": ["deprecated-.*"]
    }
  ],
  "entries": [
    { "path": "tools/agents/plugins" },
    { "path": "~/personal-plugins" }
  ]
}
```

- `entries[].path`: スキャンするディレクトリ。`/` 始まり=絶対、`~/` 始まり=
  ホーム相対、それ以外=**リポジトリルート相対**
- `inherits[].path`: 別の設定ファイルを継承（記載順に処理・マージ）
- `include_only` / `exclude`: フォルダ名に対する正規表現パターンの配列

## agy CLI でのプラグイン管理

```bash
agy plugin list                    # インポート済み一覧
agy plugin install <ローカルdir>    # ~/.gemini/config/plugins/ へコピー+登録
agy plugin uninstall <name>
agy plugin enable <name> / disable <name>
agy plugin validate [path]         # 構造検証（Claude形式レイアウトも処理）
agy plugin import [gemini|claude]  # 他環境からのインポート
```

`install` の実体は対象フォルダの**そのままコピー** +
`~/.gemini/config/import_manifest.json` への登録（実測）。
インストール元とはリンクされないため、更新には再インストールが必要。

## Claude Code 形式との互換レイヤー（実測）

`agy plugin validate` / `install` は Claude Code レイアウトを受け付ける:

| Claude Code のコンポーネント | agy での扱い |
| --- | --- |
| `skills/` | そのまま処理 |
| `agents/*.md` | サブエージェントとして処理 |
| `commands/*.md` | **スキルに変換**して処理 |
| `hooks/hooks.json` | **検出されない**（ルートの `hooks.json` が必要） |
| `.mcp.json` / マニフェストの `mcpServers` | **検出されない**（`mcp_config.json` が必要） |
| `.claude-plugin/plugin.json` | 読まれない（ルートの `plugin.json` が必須） |

## Progressive disclosure

スキルは Claude Code と同様、常時コンテキストに載るのは name + description
のみで、本文は発動時に読み込まれる。`trigger: model_decision` のルールも
同様（`always_on` ルールのみ無条件で読み込まれる）。
