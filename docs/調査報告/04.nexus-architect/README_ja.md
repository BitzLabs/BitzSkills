# Nexus Architect

Claude CodeおよびCodex向けのシステムアーキテクチャツールキット。Claude Codeはこのリポジトリを80のSkillを持つ3つのPluginとして使用し、Codexは`AGENTS.md`の互換性ルールを通じて同じスキルファイルを使用する。

- **product** (26 Skill) — 製品の方向性：検証駆動型の対話ベースのPipeline。製品ビジョンからSLA/NFRまで。システム実装設計のためにarchitectに引き継ぐ。
- **architect** (43 Skill) — legacy refactoring (レガシーリファクタリング)、greenfield (新規開発)の設計、データベース移行、コンサルティングの成果物。
- **scalardb** (11 Skill) — ScalarDBアプリケーション開発ツールキット。

## Installation

### As a Claude Code Plugin (Recommended)

```bash
# 1. Add the marketplace
claude plugin marketplace add wfukatsu/nexus-architect

# 2. Install the plugins
claude plugin install product@nexus-architect --scope user
claude plugin install architect@nexus-architect --scope user
claude plugin install scalardb@nexus-architect --scope user
```

インストール後、コマンドは`/product:skill-name`、`/architect:skill-name`、および`/scalardb:skill-name`として利用可能だ。

最新バージョンに更新するには：

```bash
claude plugin update product@nexus-architect
claude plugin update architect@nexus-architect
claude plugin update scalardb@nexus-architect
```

### Manual Installation

```bash
# 1. Clone the repository
git clone https://github.com/wfukatsu/nexus-architect.git

# 2. Add as a local marketplace
claude plugin marketplace add ./nexus-architect

# 3. Install the plugins
claude plugin install product@nexus-architect --scope user
claude plugin install architect@nexus-architect --scope user
claude plugin install scalardb@nexus-architect --scope user
```

### Verify Installation

Claude Codeセッションで、確認のために任意のコマンドを入力する：

```bash
/product:start
/architect:start
/scalardb:model
```

Skillが認識されれば、インストールは成功だ。

### Using with Codex

Codexは、Claude Code Pluginをインストールせずに同じスキルファイルを使用できる。

```bash
# 1. Clone the repository
git clone https://github.com/wfukatsu/nexus-architect.git
cd nexus-architect

# 2. Optional Python dependencies
pip install -r requirements.txt
```

リポジトリのルートでCodexを開く。`AGENTS.md`は、Claude Codeの規約をどのように変換するかをCodexに指示する：

- `/product:<name>` -> `skills/product/<name>/SKILL.md` (productのSkillは`skills/product/`の下にネストされている)
- `/architect:<name>` -> `skills/<name>/SKILL.md`
- `/scalardb:<name>` -> `skills/<name>/SKILL.md`
- `CLAUDE_PLUGIN_ROOT` -> リポジトリのルート
- `.claude/docs/*` -> `skills/common/references/*`
- `.claude/rules/*` -> `rules/*` (productのルールは`rules/product/*`の下にネストされている)
- `${CLAUDE_PLUGIN_ROOT}/subagents/*` -> `skills/common/subagents/*`

その後、チャットで同じコマンドテキストを呼び出す：

```bash
/product:start
/architect:start ./path/to/target
/architect:pipeline ./path/to/target
/scalardb:model
/scalardb:review-code ./path/to/app
```

SkillがClaudeツールを使用するように求めた場合、Codexは以下のマッピングに従う：

| Claude Code reference | Codex behavior |
|---|---|
| `Read`, `Glob`, `Grep`, `LS` | シェルでの読み取り、`rg`、`rg --files`、`find`、または`ls`を使用する |
| `Write`, `Edit`, `MultiEdit` | `apply_patch`を使用してファイルを編集する |
| `Bash` | シェルコマンドを実行する |
| `AskUserQuestion` | チャットで番号付きの選択肢を提示し、返答を待つ |
| `Task`, `Subagent` | ユーザーが明示的にサブエージェントを要求しない限り、メインのCodexスレッドで実行する |
| `WebFetch`, `WebSearch` | Codexのウェブアクセス、Context7、または承認された`curl`を使用する |

Codexで生成されたレポートやMermaid図を編集した後、関連する場合は手動でフックを実行する：

```bash
hooks/validate-frontmatter.sh reports/before/example/technology-stack.md
hooks/validate-mermaid.sh reports/before/example/codebase-structure.md
```

Claude Codeは引き続きプラグインメタデータとスラッシュコマンドを変更なしで使用する。Codexの完全なガイドについては、[Using Nexus Architect with Codex](docs/codex-usage.md)を参照してほしい。

## Quick Start

```bash
# Product direction (greenfield: start here, then hand off to /architect:define-requirements)
/product:start

# Interactive workflow (recommended)
/architect:start ./path/to/target

# Automated full pipeline
/architect:pipeline ./path/to/target

# Individual skills
/architect:investigate ./path/to/target
/architect:analyze ./path/to/target
/architect:evaluate-mmi ./path/to/target

# ScalarDB development
/scalardb:scaffold
/scalardb:model
/scalardb:build-app
```

## Commands

### Product Direction (`/product:*`)

製品ビジョンからSLA/NFRまでの検証駆動型Pipeline。システム実装設計のために`/architect:define-requirements`に引き継ぐ。

| Command | Description |
|---------|-------------|
| `/product:start` | 製品方向性の設計を対話形式で開始する (`--profile=mvp\|core-only\|ux-to-spec\|full`; `--frontend`/`--no-frontend`による選択可能なフロントエンドコード生成) |
| `/product:init-output` | 製品の出力ツリー、進捗ファイル、およびトレーサビリティグラフを初期化する |
| `/product:define-vision` | 対話を通じて製品のコア（ビジョン/ミッション/バリュー）を定義する |
| `/product:name-product` | 製品をアクロニム（頭字語）として命名する — 英単語の頭文字を取り、発音可能なラテン文字の名前とし、価値を示すフレーズに展開する（オプション; `full`に含まれる） |
| `/product:define-success-metrics` | 1つのNorth Star Metric（ノーススターメトリック）と3〜5つのインプット指標 |
| `/product:research-landscape` | 市場/競合調査：規模設定（TAM/SAM/SOM）、トレンド |
| `/product:design-revenue` | 収益/ビジネスモデルと再計算可能な利益評価テンプレート |
| `/product:define-scope` | 制約を正規化し、製品のスコープ（対象内/対象外）を決定する |
| `/product:validate-assumptions` | 最もリスクの高い仮説、最も低コストなテスト、Go/No-Goのゲートを抽出する（再実行可能） |
| `/product:generate-persona` | Jobs-to-be-Done (ジョブ理論)にアンカーされたペルソナ（ジョブストーリー + ペルソナカード） |
| `/product:map-journey` | ステージ × レイヤーのグリッドとしてのカスタマージャーニー |
| `/product:design-positioning` | ポジショニング（Dunfordキャンバス）、タッチポイント × デバイス × タイミングのマトリクス |
| `/product:create-domain-story` | ペルソナにアンカーされたDomain Storytelling (ドメインストーリーテリング)；UIモックがレンダリングされる軸 |
| `/product:design-system` | 個別に管理されるデザインシステム（DTCGトークン + コンポーネント + ガイドライン）を構築または`--import`する |
| `/product:generate-ui-mock` | 主要画面のためのナビゲーション可能なUIモック（ドメインストーリー駆動、デザインシステムによるスタイリング） |
| `/product:define-features` | UIモックから機能を抽出する（各画面のアクション → コマンド/機能） |
| `/product:define-data-model` | UIモックと機能からデータモデルを導出する（明示的 → 暗黙的、2パス） |
| `/product:generate-frontend` | UIモックとデザインシステムを実行可能なReact + Storybookのフロントエンドに変換する（Atomic Design、トークンによるスタイリング、react-router） |
| `/product:map-domains` | 機能/エンティティをBounded Context (境界づけられたコンテキスト)に抽象化する（DDD戦略的設計） |
| `/product:design-api` | 3つのAPI-Ledレイヤー（System/Process/Experience）における論理APIサーフェス |
| `/product:design-architecture` | アーキテクチャと技術適合性の統合（ドメイン/API/データ + NFRの集大成） |
| `/product:design-sla` | サービスごとのSLI/SLO/SLAとerror budget (エラーバジェット) |
| `/product:define-nfr` | SLOを測定可能なNFRに変換する（可用性、レイテンシp95/p99、...） |
| `/product:review` | 製品の成果物をレビューする（一貫性、トレーサビリティ、拡張性、戦略） |
| `/product:report` | 成果物を1つの自己完結型HTMLレポートに統合する（検証ステータスを先頭に） |
| `/product:adapt-change` | 再伝播エンジン：影響を受ける範囲を計算し、影響を受けるSkillのみを再実行する |

### Orchestration

| Command | Description |
|---------|-------------|
| `/architect:start` | システム分析と設計を対話形式で開始する |
| `/architect:pipeline` | 自動化されたPipeline実行 (`--resume-from`, `--rerun-from`, `--skip-{phase}`, `--no-scalardb`, `--lang`) |
| `/architect:init-output` | 出力ディレクトリを初期化する |

### Requirements

| Command | Description |
|---------|-------------|
| `/architect:define-requirements` | 要件定義：FR/NFRの分類、データ/トランザクション要件、ScalarDBの適用可能性（greenfieldのエントリーポイント） |

### Investigation & Analysis

| Command | Description |
|---------|-------------|
| `/architect:investigate` | 技術スタック、構造、負債、DDD準備状況の調査 |
| `/architect:investigate-security` | OWASP Top 10、アクセス制御の評価 |
| `/architect:analyze` | Ubiquitous Language (ユビキタス言語)、アクター、ドメインマッピング |
| `/architect:analyze-data-model` | データモデル、DB設計、ER図 |

### Evaluation

| Command | Description |
|---------|-------------|
| `/architect:evaluate-mmi` | MMI 4軸の定性的評価 |
| `/architect:evaluate-ddd` | DDD 12基準 3レイヤーの評価 |
| `/architect:integrate-evaluations` | MMI+DDDの統合、改善計画 |

### Design

| Command | Description |
|---------|-------------|
| `/architect:map-domains` | ドメイン分類、BC（Bounded Context）マッピング |
| `/architect:redesign` | Bounded Contextの再設計 |
| `/architect:create-domain-story` | Domain Storytelling：ドメインごとのビジネスプロセスを視覚化する（オプション） |
| `/architect:design-microservices` | ターゲットアーキテクチャ |
| `/architect:select-scalardb-edition` | ScalarDBエディションの選択 |
| `/architect:design-scalardb` | ScalarDBのスキーマとトランザクション設計 |
| `/architect:design-scalardb-analytics` | HTAP分析プラットフォーム設計 |
| `/architect:design-data-layer` | 汎用DB設計（非ScalarDB） |
| `/architect:design-api` | REST/GraphQL/gRPC/AsyncAPI仕様 |

### Implementation & Codegen

| Command | Description |
|---------|-------------|
| `/architect:design-implementation` | 実装仕様 |
| `/architect:generate-test-specs` | BDD/ユニット/統合テスト仕様 |
| `/architect:generate-scalardb-code` | Spring Boot + ScalarDBコード生成 |
| `/architect:generate-infra-code` | Kubernetes/Terraform/Helmコード生成 |

### Infrastructure

| Command | Description |
|---------|-------------|
| `/architect:design-infrastructure` | Kubernetes、IaC、マルチ環境 |
| `/architect:design-security` | 認証、認可、シークレット管理 |
| `/architect:design-observability` | モニタリング、トレーシング、アラート |
| `/architect:design-disaster-recovery` | RTO/RPO、バックアップ、DR |

### Review (5-perspective parallel)

| Command | Description |
|---------|-------------|
| `/architect:review-consistency` | 構造的一貫性 |
| `/architect:review-scalardb` | ScalarDBの制約 |
| `/architect:review-data-integrity` | データ整合性（非ScalarDB） |
| `/architect:review-operations` | 運用準備状況 |
| `/architect:review-risk` | 分散システムのリスク |
| `/architect:review-business` | ビジネス要件 |
| `/architect:review-synthesizer` | 統合と品質ゲート |

### Reporting

| Command | Description |
|---------|-------------|
| `/architect:report` | MarkdownからHTMLへの統合レポート |
| `/architect:review-report` | 生成されたHTMLレポートの品質をレビューする |
| `/architect:render-mermaid` | MermaidからPNG/SVGへの変換 + 構文修正 |
| `/architect:estimate-cost` | インフラストラクチャ、ライセンス、および運用コスト |

### Database Migration

| Command | Description |
|---------|-------------|
| `/architect:migrate-database` | 統合マイグレーションルーター（Oracle/MySQL/PostgreSQL） |
| `/architect:migrate-oracle` | OracleからScalarDBへ（スキーマ、分析、AQ、SP/トリガー） |
| `/architect:migrate-mysql` | MySQLからScalarDBへ（スキーマ、分析、SP/トリガー） |
| `/architect:migrate-postgresql` | PostgreSQLからScalarDBへ（スキーマ、分析、SP/トリガー） |

### ScalarDB Development (`/scalardb:*`)

| Command | Description |
|---------|-------------|
| `/scalardb:model` | 対話型スキーマ設計ウィザード |
| `/scalardb:config` | 設定ファイル生成（6つのインターフェースの組み合わせ） |
| `/scalardb:scaffold` | 完全なスタータープロジェクト生成 |
| `/scalardb:error-handler` | 例外処理コードの生成とレビュー |
| `/scalardb:crud-ops` | CRUD APIオペレーションパターンガイド |
| `/scalardb:jdbc-ops` | JDBC/SQLオペレーションパターンガイド |
| `/scalardb:local-env` | Docker Composeローカル環境セットアップ |
| `/scalardb:docs` | ScalarDBドキュメント検索 |
| `/scalardb:build-app` | 要件から完全なアプリをビルドする |
| `/scalardb:review-code` | Javaコードレビュー（16のチェックカテゴリ） |
| `/scalardb:migrate` | マイグレーションアドバイザー（Core/Cluster、CRUD/JDBC、1PC/Two-Phase Commit (二相コミット)） |

## Workflows

### Product Direction

システム設計の前に製品の方向性を決定する：最もリスクの高い仮説を早期に検証し、UX、仕様、ドメイン、API、SLA/NFRを導き出す。`/architect:define-requirements`を通じてgreenfieldパスに引き継ぐ。

```
vision -> success-metrics / revenue -> scope -> validate-assumptions [gate]
  -> personas/journey/positioning -> ui-mock/features/data-model
  -> domains/API -> SLA/NFR -> review -> report -> /architect:define-requirements
```

### Legacy Refactoring

既存のシステムを分析し、アーキテクチャの成熟度を評価し、マイクロサービスへの変換を設計する。

```
investigate -> analyze -> evaluate -> redesign -> implement -> review -> report
```

### Greenfield Design

要件からScalarDBアーキテクチャ、デプロイメントに至るまで、新しいシステムを設計する。

```
requirements -> domain modeling -> ScalarDB design -> infra -> deploy
```

### ScalarDB Application Development

ガイド付きのスキーマ設計、コード生成、およびコードレビューを利用してScalarDBアプリケーションを構築する。

```
/scalardb:model -> /scalardb:config -> /scalardb:scaffold -> /scalardb:review-code
```

### Database Migration to ScalarDB

既存のOracle、MySQL、またはPostgreSQLデータベースを、自動化されたスキーマ分析、移行計画、およびJavaコード生成を伴ってScalarDBに移行する。

```
migrate-database -> schema extraction -> migration analysis -> SP/trigger conversion -> (AQ integration)
```

## Pipeline Dependency Graph

```
investigate -> analyze -> [evaluate-mmi, evaluate-ddd] -> integrate-evaluations
  -> redesign -> [create-domain-story (optional, per domain)]
  -> design-microservices -> [design-scalardb | design-data-layer, design-api]
  -> [review-consistency, review-scalardb | review-data-integrity,
     review-operations, review-risk, review-business]
  -> review-synthesizer -> report -> review-report
```

## Output Language

出力言語はプロジェクトごとに設定可能だ。`/architect:start`の初期化時またはフラグで設定する：

```bash
/architect:pipeline ./path/to/project --lang=ja
```

サポート対象：`en`（英語、デフォルト）、`ja`（日本語）。

### Documentation language policy

すべてのSkillインストラクション（`SKILL.md`）、ルールファイル、および埋め込みプロンプトは**英語**で書かれている；`output_language`は生成されるレポート成果物にのみ適用される。`docs/`の下のユーザーガイドはEN/JAのペア（`getting-started`、`skill-reference`、`scalardb-development`、`database-migration`、`codex-usage`）として保守されている。設計による例外：`docs/design.md`（内部設計仕様、ENのみ）および`docs/codex-*`監査記録（特定の時点の内部監査、JAのみ）。

## Output Structure

すべての出力はgitで無視されるディレクトリに書き込まれる：

```
reports/          # Analysis and design documents
generated/        # Generated code per service
work/             # Pipeline state and intermediate files
```

## Requirements

- Claude Code CLI（最新版）、Claude Code Plugin使用向け
- Codex、Codex使用向け
- Python 3.9以上
- Node.js 18以上（オプション、Mermaidレンダリング用）

## Optional MCP Servers

- **Serena**: ASTレベルの理解を備えた高度なコード分析
- **Context7**: 最新のScalarDBドキュメント

## Documentation

| Document | Description |
|----------|-------------|
| [Getting Started](docs/getting-started.md) | インストールと最初のステップ |
| [Codex Usage](docs/codex-usage.md) | Codexから同じSkillを使用する |
| [Skill Reference](docs/skill-reference.md) | 完全なSkillカタログ |
| [ScalarDB Development](docs/scalardb-development.md) | ScalarDB開発ガイド |
| [Database Migration](docs/database-migration.md) | 移行ガイド（Oracle/MySQL/PostgreSQL） |
| [Changelog](CHANGELOG.md) | リリースノートとバージョン履歴 |

Japanese translations:
[Getting Started (日本語)](docs/getting-started_ja.md) |
[Codex Usage (日本語)](docs/codex-usage_ja.md) |
[Skill Reference (日本語)](docs/skill-reference_ja.md) |
[ScalarDB Development (日本語)](docs/scalardb-development_ja.md) |
[Database Migration (日本語)](docs/database-migration_ja.md) |
[Changelog (日本語)](CHANGELOG_ja.md)

## License

MIT
