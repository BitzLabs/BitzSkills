# プラットフォーム別配置パス

`skill-packager` がスキルを配置する際の正式なパス表。
スキル機構は [Agent Skills](https://agentskills.io/specification) オープン標準に
準拠しているため、スキルフォルダ自体は無変換でどのプラットフォームにも置ける。

配置方法は2系統ある:
- **スキル単体の直接配置**（下表のパスへコピー/シンボリックリンク）— 個別に選んで入れたいとき
- **プラグイン一括インストール** — このリポジトリはマーケットプレイス `bitzskills`
  を持つモノレポで、`plugins/skill-creator/` が両プラットフォーム対応のプラグイン
  になっており、7スキルをまとめて導入できる（後述「プラグインとしての配布」）

## Claude Code

| 配置場所 | スコープ |
| --- | --- |
| `<workspace-root>/.claude/skills/<skill-folder>/` | ワークスペース単位 |
| `~/.claude/skills/<skill-folder>/` | グローバル（全プロジェクト共通） |

補足:
- プラグイン経由で入れた場合、スキル名は `skill-creator:skill-validator` のように
  プラグイン名で名前空間化される。

## Google Antigravity

| 配置場所 | スコープ |
| --- | --- |
| `<workspace-root>/.agents/skills/<skill-folder>/` | ワークスペース単位 |
| `~/.gemini/config/skills/<skill-folder>/` | グローバル（全プロジェクト共通） |

補足:
- Antigravityは現在 `.agents/skills`（複数形）をデフォルトとしているが、
  旧仕様の `.agent/skills`（単数形）も後方互換として引き続きサポートされている。

## プラグインとしての配布

リポジトリはモノレポ構成で、ルートの `.claude-plugin/marketplace.json` が
マーケットプレイス `bitzskills`、`plugins/<plugin名>/` がプラグイン本体。
各プラグインのマニフェストは両プラットフォームで別ファイルなので共存する。

| プラットフォーム | マニフェスト | プラグインの実体が置かれる場所 |
| --- | --- | --- |
| Claude Code | `plugins/<plugin名>/.claude-plugin/plugin.json`（＋リポジトリ直下の `.claude-plugin/marketplace.json`） | marketplace 経由のインストール先（Claude Code が管理） |
| Antigravity 2.0 | `plugins/<plugin名>/plugin.json` | `~/.gemini/config/plugins/<plugin_name>/`（実測。台帳は `~/.gemini/config/import_manifest.json`） |

### Claude Code へのインストール

```
# 開発中の動作確認（インストール不要。プラグインのフォルダを指す）
claude --plugin-dir /home/hide/Dev/BitzSkills/plugins/skill-creator

# マーケットプレイス登録してインストール（リポジトリのルートを指す。GitHub リポジトリでも可）
/plugin marketplace add /home/hide/Dev/BitzSkills
/plugin install skill-creator@bitzskills
```

### Antigravity 2.0 へのインストール

```
# プラグインとして導入（agy CLI。targetはプラグインのディレクトリまたは plugin@marketplace 形式）
agy plugin validate /home/hide/Dev/BitzSkills/plugins/skill-creator   # 事前チェック
agy plugin install /home/hide/Dev/BitzSkills/plugins/skill-creator
agy plugin list        # 確認
```

`agy plugin install` が使えない環境では、従来どおりプラグイン内 `skills/` 配下の
各スキルを上表のスキルパスへ直接コピーする（フォールバック）。

### プラグイン運用の注意

- プラグイン導入分はプラットフォーム側がバージョン管理するため、
  `installed-at` / `installed-from` の stamp は**行わない**（stampは直接配置のみ）
- プラグインのバージョンは `plugins/<plugin名>/` 直下の `.claude-plugin/plugin.json`
  と `plugin.json` の `version` フィールド（両者を常に同じ値に保つ）。スキルを
  変更したら各スキルの `metadata.version` に加えてプラグイン version も semver で
  bump する

## スコープの使い分けの目安

| スコープ | 向いているスキル |
| --- | --- |
| ワークスペース | プロジェクト固有のワークフロー（チームのデプロイ手順・テスト規約など）。リポジトリにコミットしてチームで共有できる |
| グローバル | 個人的な汎用ツール（フォーマッタ、UUID生成など）。どのプロジェクトでも使う |

## コピー vs シンボリックリンク

| 方式 | 特徴 | 注意 |
| --- | --- | --- |
| シンボリックリンク | ライブラリ側の更新が即反映。開発中のスキルに最適 | ライブラリを移動・削除するとリンク切れ。環境によってはsymlinkを辿らない実装があり得るため、配置後に動作確認する |
| コピー | 配置先が自己完結。配布に近い扱い | ライブラリ側を更新しても反映されない。更新時は再コピーが必要 |

## 出典

- [Agent Skills - Specification](https://agentskills.io/specification)
- [Claude Code - Skills](https://code.claude.com/docs/en/skills)
- [Claude Code - Plugins](https://code.claude.com/docs/en/plugins)
- [Google Antigravity Documentation - Skills](https://antigravity.google/docs/skills)
- [Google Antigravity Documentation - CLI Plugins](https://antigravity.google/docs/cli/plugins)
