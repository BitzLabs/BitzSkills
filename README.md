# BitzSkills — エージェントプラグインのモノレポ

[Agent Skills](https://agentskills.io/specification) オープン標準に準拠したスキルを、
Claude Code と Google Antigravity 2.0 の両方で使える**プラグイン**として開発・配布する
モノレポです。リポジトリルートがマーケットプレイス `bitzskills`、`plugins/` 配下の
各フォルダが1つのプラグインです。

## 収録プラグイン

| プラグイン | 内容 |
| --- | --- |
| [skill-creator](plugins/skill-creator/) | エージェントスキル開発の全工程（作成→検証→テスト→評価→最適化→配置）を支援する7スキル |

### skill-creator プラグインのスキル

| スキル | 役割 |
| --- | --- |
| skill-creator | 新規スキルの設計・雛形作成 |
| skill-validator | 仕様準拠チェック（lint） |
| skill-optimizer | description最適化・本文分離・構造改善 |
| skill-tester | テストケース設計と実行 |
| skill-evaluator | 実行結果の採点・レポート作成 |
| skill-packager | 実環境への配置・配布 |
| skill-pipeline | 全工程を案内する統括スキル |

標準フロー: creator → validator → tester → evaluator →（不合格なら optimizer で
改善して反復）→ packager。全体は skill-pipeline が統括します。

## インストール

### Claude Code

```
/plugin marketplace add <このリポジトリのパスまたは owner/BitzSkills>
/plugin install skill-creator@bitzskills
```

開発中の動作確認はインストール不要で
`claude --plugin-dir <このリポジトリ>/plugins/skill-creator`。
スキル名は `skill-creator:skill-validator` のようにプラグイン名で名前空間化されます。

### Google Antigravity 2.0

```bash
agy plugin install <このリポジトリ>/plugins/skill-creator   # プラグインのフォルダを指定
agy plugin list                                             # 確認
```

`agy plugin install` が使えない環境では、プラグイン内 `skills/` 配下の各スキルフォルダを
`~/.gemini/config/skills/`（グローバル）または `<project>/.agents/skills/`
（ワークスペース）へ直接コピーしてください。

## 使い方の例

インストール後、エージェントに次のように話しかけます。

- 「スキルを作って公開まで面倒を見てほしい」（→ skill-pipeline）
- 「PDFを処理する新しいスキルを作りたい」（→ skill-creator）
- 「skills/foo を検証して」（→ skill-validator）
- 「foo をテストして」→「結果を評価して」（→ skill-tester → skill-evaluator）

詳細は `docs/BitzSkills.md` を参照してください。

## 開発（このリポジトリを編集するとき）

規約と新しいプラグインの追加手順は `CLAUDE.md` を参照してください
（validator による検証、semver での version bump、`evals/` へのテスト成果物の分離）。
