# プラットフォーム別配置パス

`skill-packager` がスキルを配置する際の正式なパス表。
スキル機構は [Agent Skills](https://agentskills.io/specification) オープン標準に
準拠しているため、スキルフォルダ自体は無変換でどのプラットフォームにも置ける。

## Claude Code

| 配置場所 | スコープ |
| --- | --- |
| `<workspace-root>/.claude/skills/<skill-folder>/` | ワークスペース単位 |
| `~/.claude/skills/<skill-folder>/` | グローバル（全プロジェクト共通） |

補足:
- プラグイン経由での配布も可能だが、個人利用なら上記への直接配置で足りる。

## Google Antigravity

| 配置場所 | スコープ |
| --- | --- |
| `<workspace-root>/.agents/skills/<skill-folder>/` | ワークスペース単位 |
| `~/.gemini/config/skills/<skill-folder>/` | グローバル（全プロジェクト共通） |

補足:
- Antigravityは現在 `.agents/skills`（複数形）をデフォルトとしているが、
  旧仕様の `.agent/skills`（単数形）も後方互換として引き続きサポートされている。

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
- [Google Antigravity Documentation - Skills](https://antigravity.google/docs/skills)
