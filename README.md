# BitzSkills — エージェントプラグインのモノレポ

[Agent Skills](https://agentskills.io/specification) オープン標準に準拠したスキルを、
Claude Code、Google Antigravity 2.0、OpenAI Codex CLI で使える**プラグイン**として開発・配布する
モノレポです。リポジトリルートがマーケットプレイス `bitzskills`、`plugins/` 配下の
各フォルダが1つのプラグインです。

## 収録プラグイン

| プラグイン | 内容 | スキル数 |
| --- | --- | --- |
| [bitz-sdd](plugins/bitz-sdd/) | 仕様駆動開発（SDD）の運用ワークフロー。上流探索→設計→データ格納設計→レビュー→運用設計→実装→テスト→レポートの一気通貫 + Git/GitHub フロー | 11 |
| [bitz-ddd](plugins/bitz-ddd/) | DDD 設計手法プロバイダ。ドメインストーリーテリング・戦略設計・成熟度評価を bitz-sdd の設計工程へ差し込む（併用前提） | 3 |
| [skill-creator](plugins/skill-creator/) | エージェントスキル開発の全工程（作成→検証→テスト→評価→最適化→配置）+ 配置後の自己改善ループ | 10 |
| [plugin-creator](plugins/plugin-creator/) | プラグイン開発の全領域（構造 / コマンド / エージェント / フック / MCP / 設定）を両プラットフォームの仕様差込みで支援 | 7 |
| [bitz-env](plugins/bitz-env/) | 開発環境の展開。ガードレール（同梱フック + permissions/AGENTS.md 生成）とモデル非依存の協調運用（委譲型・相談型・合議型、協調アダプタ連携） | 4 |

プラグイン間の関係: `bitz-ddd` → `.spec` → `bitz-sdd` の一方向依存
（bitz-sdd は bitz-ddd を知らず、未導入でも単体で完結する）。
`skill-creator` / `plugin-creator` は独立して使える開発ツール。

## インストール

### Claude Code

```
/plugin marketplace add BitzLabs/BitzSkills
/plugin install bitz-sdd@bitzskills        # 使いたいプラグインを個別に
/plugin install skill-creator@bitzskills
```

開発中の動作確認はインストール不要で
`claude --plugin-dir <このリポジトリ>/plugins/<plugin名>`。
スキル名は `skill-creator:skill-validator` のようにプラグイン名で名前空間化されます。

### Google Antigravity 2.0

```bash
agy plugin install <このリポジトリ>/plugins/<plugin名>
agy plugin list    # 確認
```

`agy plugin install` が使えない環境では、プラグイン内 `skills/` 配下の各スキルフォルダを
`~/.gemini/config/skills/`（グローバル）または `<project>/.agents/skills/`
（ワークスペース）へ直接コピーしてください。

### OpenAI Codex CLI

```bash
codex plugin marketplace add BitzLabs/BitzSkills
codex plugin add bitz-sdd@bitzskills        # 使いたいプラグインを個別に
codex plugin add skill-creator@bitzskills
```

インストール後は新しい Codex セッションを開始してください。Codex CLI は各プラグインの
`.codex-plugin/plugin.json` から `skills/` を読み込みます。

## まず読むもの

- **[使い方ガイド](docs/使い方ガイド.md)** — インストールから最初のプロジェクトまで
- **[ユースケース集](docs/ユースケース.md)** — 「何ができるか」をシナリオ別に
- 各プラグインの README — スキル一覧と使い方の流れ

## リポジトリ構成

```
.claude-plugin/marketplace.json  # Claude Code / Codex CLI 共有マーケットプレイス
plugins/                         # 各プラグイン（マニフェスト3つ + skills/）
.spec/                           # このリポジトリ自身の要件・タスク（sdd-core 準拠のドッグフーディング）
evals/                           # skill-tester / evaluator の成果物と観察ログ
docs/                            # 使い方ガイド・ユースケース・調査報告・翻訳規約
scripts/                         # 運用スクリプト（bump_version / release_check）
tests/                           # 運用スクリプトと同梱ツールの pytest
```

## 開発（このリポジトリを編集するとき）

共通ルールの正は [AGENTS.md](AGENTS.md)（役割・ガードレール・コミット/PR 規約・定型手順）。
要点:

- コミット / PR タイトルは Conventional Commits（CI が機械検査）、PR は squash merge
- スキルを変更したら metadata と プラグイン version を bump（`python3 scripts/bump_version.py`）
- マージ前に `python3 scripts/release_check.py` と `pytest tests/` が通ること（CI でも実行）
- 主要規約は EARS 要件として `.spec/requirements/`（CORE-*）に起票済みで、
  `spec_inspect.py` で機械検証できる
