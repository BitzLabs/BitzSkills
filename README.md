# BitzSkills — BitzLabsの標準エージェント開発環境

BitzSkills は、**BitzLabs でAIエージェントを用いて開発する際の標準作業環境**を定義・検証・配布する
モノレポです。[Agent Skills](https://agentskills.io/specification) オープン標準に準拠したスキルを、
Claude Code、Google Antigravity 2.0、OpenAI Codex CLI で使えるプラグインとして提供します。
リポジトリルートがマーケットプレイス `bitzskills`、`plugins/` 配下の各フォルダが1つのプラグインです。

目標は、利用するAIエージェントが変わっても、安全性・仕様・Git・品質の基準を揃え、
開発者がプロジェクト固有の価値に集中できる状態をつくることです。

## 標準環境の構成

標準環境は全プラグインの一括導入ではなく、用途に合わせたプロファイルで構成します。

| プロファイル | 導入するプラグイン | 用途 |
| --- | --- | --- |
| **標準開発** | `bitz-env` + `bitz-sdd` | ガードレールと仕様駆動開発を使うBitzLabsの既定 |
| **DDD拡張** | 標準開発 + `bitz-ddd` | 複雑なドメイン設計、DDD成熟度評価 |
| **軽量Git** | `bitz-env` + `bitz-flow` | `.spec` を採用せず、安全なGit運用だけを標準化 |
| **スキル開発** | 標準開発 + `skill-creator` | Agent Skills の作成・検証・改善・配置 |
| **プラグイン開発** | 標準開発 + `plugin-creator` | Claude Code / Antigravity 向けプラグインの開発 |

`bitz-sdd` は現時点で `sdd-git` を含むため、同じ目的で `bitz-flow` を重複導入する必要はありません。
このリポジトリが扱う標準環境はAIエージェントの作業規律・ワークフロー・検証・配布の層です。
OS、IDE本体、言語ランタイム、クラウド基盤、認証情報管理は対象外です。

3プラットフォームへインストールできますが、全機能が同等とは限りません。現時点で `bitz-env` の
機械フックと `env-init` は Claude Code / Antigravity が対象です。Codexでは収録スキルと
AGENTS.mdの規律を利用し、Codexネイティブの機械ガード対応は `SI-ENV-023` で追跡しています。

## 収録プラグイン

| プラグイン | 内容 | スキル数 |
| --- | --- | --- |
| [bitz-sdd](plugins/bitz-sdd/) | 仕様駆動開発（SDD）の運用ワークフロー。上流探索→設計→データ格納設計→レビュー→運用設計→実装→テスト→レポートの一気通貫 + Git/GitHub フロー | 13 |
| [bitz-ddd](plugins/bitz-ddd/) | DDD 設計手法プロバイダ。ドメインストーリーテリング・戦略設計・成熟度評価を bitz-sdd の設計工程へ差し込む（併用前提） | 3 |
| [skill-creator](plugins/skill-creator/) | エージェントスキル開発の全工程（作成→検証→テスト→評価→最適化→配置）+ 配置後の自己改善ループ | 10 |
| [plugin-creator](plugins/plugin-creator/) | Claude Code / Antigravity 2.0 のプラグイン開発全般（構造 / コマンド / エージェント / フック / MCP / 設定）を支援。収録スキルは Codex CLI からも利用可能 | 7 |
| [bitz-env](plugins/bitz-env/) | 開発環境の展開・診断・撤去。ガードレール（同梱フック + permissions/AGENTS.md 生成）とモデル非依存の協調運用（委譲型・相談型・合議型、協調アダプタ連携） | 5 |
| [bitz-flow](plugins/bitz-flow/) | Git / GitHub 開発フロー。状況に応じたフロー選択、Conventional Commits、worktree 並列運用、Issue 駆動 PR + squash merge | 3 |

プラグイン間の関係: `bitz-ddd` → `.spec` → `bitz-sdd` の一方向依存
（bitz-sdd は bitz-ddd を知らず、未導入でも単体で完結する）。
`skill-creator` / `plugin-creator` / `bitz-env` / `bitz-flow` は独立して使えます。

## インストール

### Claude Code

```
/plugin marketplace add BitzLabs/BitzSkills
/plugin install <プラグイン名>@bitzskills
```

開発中の動作確認はインストール不要で
`claude --plugin-dir <このリポジトリ>/plugins/<plugin名>`。
スキル名は `skill-creator:skill-validator` のようにプラグイン名で名前空間化されます。

### Google Antigravity 2.0

```bash
agy plugin install <このリポジトリ>/plugins/<plugin名>
agy plugin list
```

`agy plugin install` が使えない環境では、プラグイン内 `skills/` 配下の各スキルフォルダを
`~/.gemini/config/skills/`（グローバル）または `<project>/.agents/skills/`
（ワークスペース）へ直接コピーしてください。

### OpenAI Codex CLI

```bash
codex plugin marketplace add BitzLabs/BitzSkills
codex plugin add <プラグイン名>@bitzskills
codex plugin list
```

インストール後は新しい Codex セッションを開始してください。Codex CLI は各プラグインの
`.codex-plugin/plugin.json` から `skills/` を読み込みます。

## アップデート

プラグイン経由で導入した場合は、各プラットフォームの管理コマンドで更新します。更新を
反映するには、コマンド実行後にクライアントを再起動するか、新しいセッションを開始してください。

### Claude Code

```bash
claude plugin update <プラグイン名>@bitzskills
claude plugin list
```

### Google Antigravity 2.0

Antigravity の `install` はプラグインを実体コピーするため、先にこのリポジトリを更新してから
同じプラグインを再インストールします。

```bash
git -C <このリポジトリ> pull --ff-only
agy plugin install <このリポジトリ>/plugins/<プラグイン名>
agy plugin list
```

### OpenAI Codex CLI

Codex CLI はプラグイン単位の `update` ではなく、Git マーケットプレイスのスナップショットを
更新します。マーケットプレイス名を省略すると、登録済みの全 Git マーケットプレイスが対象です。

```bash
codex plugin marketplace upgrade bitzskills
codex plugin list
```

プラグインではなく `skills/` 配下を直接コピーして導入した場合、これらの更新コマンドは
適用されません。コピー元とのバージョンとローカル変更を確認してから、スキルフォルダを
再配置してください。

## まず読むもの

- **[使い方ガイド](docs/使い方ガイド.md)** — 標準プロファイルの選択から最初の開発サイクルまで
- **[ミッションとビジョン](docs/01-context/mission-vision.md)** — なぜ標準環境を提供するか
- **[非目標と境界](docs/01-context/non-goals.md)** — BitzSkills が扱う範囲・扱わない範囲
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
