# CLAUDE.md

**nexus-architect** リポジトリにおける Claude Code 向けのガイダンスである。

## What This Is

3プラグイン構成のシステムアーキテクチャツールキットである：
- **product** — プロダクトの方向性エージェント：プロダクトビジョンから SLA/NFR までの、検証駆動型かつ対話ベースのパイプライン。システム実装設計は architect に引き継ぐ
- **architect** — legacy refactoring (レガシーリファクタリング)、greenfield (新規開発) の設計、およびコンサルティング成果物のためのシステムアーキテクチャエージェント
- **scalardb** — ScalarDB アプリケーション開発ツールキット

ワークフロー：
- **Product direction**: ビジョン -> 成功指標 / 収益 -> スコープ -> 検証 -> ペルソナ / ジャーニー / ポジショニング -> domain-stories/design-system -> UI / 機能 / データ / フロントエンド -> ドメイン / API -> SLA/NFR -> アーキテクチャ / 技術的適合性 -> レビュー / レポート (`/architect:define-requirements` へ引き継ぎ)
- **Legacy refactoring**: 調査 -> 分析 -> 評価 -> 再設計 -> 実装
- **Greenfield design**: 要件 -> ドメインモデリング -> ScalarDB 設計 -> インフラ -> デプロイ
- **Consulting deliverables**: レポート、コスト見積もり、ドメインストーリー

プロダクトの方向性に関する Skill：`/product:skill-name`。アーキテクチャの Skill：`/architect:skill-name`。ScalarDB 開発ツール：`/scalardb:skill-name`。
プロダクトの方向性を設計するには `/product:start` を、インタラクティブなシステム分析 / 設計の選択には `/architect:start` を、自動実行には `/architect:pipeline` を使用する。

## Output Language

出力言語はプロジェクトごとに設定可能である。`work/pipeline-progress.json` に設定する：
```json
{ "options": { "output_language": "ja" } }
```
サポート対象：`en` (英語、デフォルト)、`ja` (日本語)。`/architect:start` オーケストレーターは、プロジェクトの初期化時にユーザーに言語を選択するよう促す。

## Command Reference

### Product Direction (`/product:*`)
プロダクトビジョンから SLA/NFR までの検証駆動型パイプラインである。Skill は `skills/product/` 配下に、ルールは `rules/product/` 配下に名前空間が分けられている。インタラクティブまたは自動実行には `/product:start` を使用し、システム実装設計のために `/architect:define-requirements` へ引き継ぐ。

- `/product:start [target] [--auto] [--profile=mvp|core-only|ux-to-spec|full] [--frontend|--no-frontend] [--lang=ja|en]` — プロダクトの方向性設計をインタラクティブに開始する。最もリスクの高い仮説に対するゲートを設けながら、検証駆動型パイプラインを依存関係の順に実行する。UI モックの後に、選択可能な `generate-frontend` ステップ (React + Storybook のコード生成) を提示する。`--frontend`/`--no-frontend` で選択を強制できる
- `/product:init-output [project]` — プロダクトの出力ツリー、パイプライン進行状況ファイル、およびトレーサビリティグラフを初期化する
- `/product:define-vision` — 対話を通じて、プロダクトのコア (ビジョン / ミッション / バリュー) をプロダクトビジョンとして定義する
- `/product:name-product` — アルファベットの頭字語としてプロダクトを命名する：各文字が英単語の頭文字となり、名前が価値を表すフレーズに展開される、短く発音可能なラテン文字の名前。ビジョン / ポジショニングに基づき、候補を絞り込んで1つを推奨する
- `/product:define-success-metrics` — 1つのノーススター指標 (North Star Metric) と3〜5つの入力指標
- `/product:research-landscape` — 市場 / 競合調査：市場規模 (TAM/SAM/SOM)、トレンド
- `/product:design-revenue` — 収益 / ビジネスモデルと再計算可能なベネフィット評価テンプレート
- `/product:define-scope` — 制約を正規化し、プロダクトのスコープ (対象内 / 対象外) を決定する
- `/product:validate-assumptions` — 最もリスクの高い仮説を抽出し、最も安価なテストを紐付け、Go/No-Go ゲートを設ける (再実行可能)
- `/product:generate-persona` — Jobs-to-be-Done (ジョブ理論) に基づくペルソナ (ジョブストーリー + ペルソナカード)
- `/product:map-journey` — ステージ × レイヤーのグリッドとしてのカスタマージャーニー (タッチポイント、行動、感情)
- `/product:design-positioning` — ポジショニング (Dunford の5コンポーネントキャンバス)、タッチポイント × デバイス × タイミングのマトリックス
- `/product:create-domain-story` — ペルソナに基づく Domain Storytelling (ドメインストーリーテリング) (アクター=ペルソナ、アクティビティ=ジョブストーリー / ジャーニー)。これを軸に UI モックがレンダリングされる
- `/product:design-system` — 独立して管理されるデザインシステムを構築するか `--import` する (DTCG トークン + コンポーネント + ガイドライン)。これを視覚言語として UI モックが低〜中程度の忠実度でレンダリングされる
- `/product:generate-ui-mock` — ドメインストーリーによって駆動し、デザインシステムによってスタイル設定された、主要画面向けのナビゲーション可能な UI モック (各アクティビティが画面になり、ストーリー順にステップ実行できるクリック可能なフローに接続される。トークンが注入される)
- `/product:generate-frontend` — UI モックとデザインシステムを、実行可能な React + TypeScript フロントエンドに変換する：Atomic Design に基づく分解 (トークン→アトム→モレキュール→オーガニズム→テンプレート→ページ)、トークンでスタイル設定されたコンポーネント (CSS Modules + CSS 変数)、ストーリーフローからの react-router 接続、およびコンポーネントのバリアント / 状態ごとの Storybook ストーリー (`generated/frontend/` を出力する)
- `/product:define-features` — UI モックから機能を抽出する (各画面のアクションが Command/機能になる)
- `/product:define-data-model` — UI モックと機能からデータモデルを導出する (明示的 → 暗黙的、2パス)
- `/product:map-domains` — 機能 / エンティティを Bounded Context (境界づけられたコンテキスト) に抽象化する (DDD 戦略的設計。コアドメイン / サブドメイン (Supporting/Generic))
- `/product:design-api` — 3つの API-Led レイヤー (System/Process/Experience) における論理 API サーフェス
- `/product:design-sla` — 顧客の期待値から導出された error budget (エラーバジェット) を伴うサービスごとの SLI/SLO/SLA
- `/product:define-nfr` — SLO を測定可能な NFR (可用性、レイテンシの p95/p99 など) に変換する
- `/product:design-architecture` — コンテキスト / API / データ / NFR をランタイムアーキテクチャ (コンテナ、クリティカルパスシーケンス、デプロイメントビュー) に統合し、プラットフォーム技術の適合性 (Kong、ScalarDB、ScalarDB Analytics、ScalarDL) を Adopt/Conditional/Reject の判断で評価する
- `/product:review` — 4つのレンズ (一貫性、トレーサビリティなど) を通じてプロダクトの成果物をレビューする
- `/product:report [--auto] [--lang=ja|en]` — 成果物を1つの自己完結型 HTML レポートに統合する (最初に検証ステータスを表示)
- `/product:adapt-change` — 再伝播エンジン：変更による影響範囲を計算し、影響を受ける Skill のみを再実行する

### Orchestration
- `/architect:start [target_path]` — インタラクティブにシステム分析と設計を開始する
- `/architect:pipeline [target_path]` — 自動化されたパイプラインの実行 (--resume-from, --rerun-from, --skip-{phase}, --no-scalardb, --lang=en|ja)
- `/architect:init-output [project]` — 出力ディレクトリを初期化する

### Requirements
- `/architect:define-requirements [target_path] [--input=<file|dir>] [--auto] [--no-scalardb]` — 要件定義：FR/NFR の分類、データ / トランザクション要件、ScalarDB の適用可能性 (greenfield のエントリーポイント)

### Investigation & Analysis
- `/architect:investigate [target_path]` — 技術スタック、構造、負債、DDD 対応度
- `/architect:investigate-security [target_path]` — OWASP Top 10、アクセス制御
- `/architect:analyze [target_path]` — Ubiquitous Language (ユビキタス言語)、アクター、ドメインマッピング
- `/architect:analyze-data-model [target_path]` — データモデル、DB 設計、ER 図

### Evaluation
- `/architect:evaluate-mmi [target_path]` — MMI 4軸定性評価
- `/architect:evaluate-ddd [target_path]` — DDD 12基準 3レイヤー評価
- `/architect:integrate-evaluations` — MMI+DDD の統合、改善計画

### Design
- `/architect:map-domains` — ドメイン分類、境界づけられたコンテキスト (BC) のマッピング
- `/architect:redesign` — 境界づけられたコンテキストの再設計
- `/architect:create-domain-story [--domain=<name>] [--auto]` — Domain Storytelling：ドメインごとのビジネスプロセスの可視化 (インタラクティブな7段階のファシリテーション、または分析ファイルからの自動生成)
- `/architect:design-microservices` — ターゲットアーキテクチャ
- `/architect:select-scalardb-edition` — ScalarDB エディションの選択
- `/architect:design-scalardb` — ScalarDB スキーマとトランザクションの設計
- `/architect:design-scalardb-analytics` — HTAP 分析プラットフォームの設計
- `/architect:design-data-layer` — 汎用的な DB 設計 (非 ScalarDB)
- `/architect:design-api` — REST/GraphQL/gRPC/AsyncAPI の仕様

### Implementation & Codegen
- `/architect:design-implementation` — 実装仕様
- `/architect:generate-test-specs` — BDD / ユニット / 統合テストの仕様
- `/architect:generate-scalardb-code` — Spring Boot + ScalarDB のコード生成
- `/architect:generate-infra-code` — Kubernetes / Terraform / Helm のコード生成

### Infrastructure
- `/architect:design-infrastructure` — Kubernetes、IaC、マルチ環境
- `/architect:design-security` — 認証、シークレット管理
- `/architect:design-observability` — モニタリング、トレーシング、アラート
- `/architect:design-disaster-recovery` — RTO / RPO、バックアップ、DR

### Review (5つの並列レビュー — scalardb と data-integrity は排他的)
- `/architect:review-consistency` — 構造的整合性 (CON-)
- `/architect:review-scalardb` — ScalarDB の制約 (SDB-) — scalardb_enabled の場合に実行される
- `/architect:review-data-integrity` — データ整合性 (DIN-) — scalardb_disabled の場合に実行される
- `/architect:review-operations` — 運用の準備状況 (OPS-)
- `/architect:review-risk` — 分散システムのリスク (RSK-)
- `/architect:review-business` — ビジネス要件 (BIZ-)
- `/architect:review-synthesizer` — 統合および品質ゲート

### Reporting
- `/architect:report` — Markdown から HTML への統合レポート
- `/architect:review-report` — 生成された HTML レポートの品質レビュー (完全性、スコアの正確性、Mermaid の構文、言語、構造)
- `/architect:render-mermaid [target_path]` — Mermaid から PNG/SVG への変換 + 構文修正
- `/architect:estimate-cost` — インフラ、ライセンス、運用コスト

### ScalarDB Development (`/scalardb:*`)
- `/scalardb:model` — インタラクティブなスキーマ設計ウィザード (キー、インデックス、データ型)
- `/scalardb:config` — 設定ファイルジェネレーター (Core/Cluster、CRUD/JDBC、1PC/2PC)
- `/scalardb:scaffold` — 完全なスタータープロジェクトジェネレーター (6つのインターフェースの組み合わせすべて)
- `/scalardb:error-handler` — 例外処理コードのジェネレーターおよびコードレビュアー
- `/scalardb:crud-ops` — CRUD API の操作パターン (Get、Scan、Insert、Upsert、Update、Delete)
- `/scalardb:jdbc-ops` — JDBC / SQL の操作パターン (SELECT、INSERT、JOIN、集計)
- `/scalardb:local-env` — ローカルの Docker Compose 環境のセットアップ
- `/scalardb:docs` — ScalarDB ドキュメントの検索と参照
- `/scalardb:build-app` — 要件から完全な ScalarDB アプリケーションを構築する
- `/scalardb:review-code` — ScalarDB の正確性について Java コードをレビューする (16個のチェック)
- `/scalardb:migrate` — マイグレーションアドバイザー (Core→Cluster、CRUD→JDBC、1PC→2PC)

### Database Migration (Oracle/MySQL/PostgreSQL → ScalarDB)
- `/architect:migrate-database` — 統合マイグレーションルーター (DB タイプを検出し、委譲する)
- `/architect:migrate-oracle` — Oracle → ScalarDB (スキーマ抽出、分析、AQ 統合、ストアドプロシージャ / トリガーの Java 変換)
- `/architect:migrate-mysql` — MySQL → ScalarDB (スキーマ抽出、分析、ストアドプロシージャ / トリガーの Java 変換)
- `/architect:migrate-postgresql` — PostgreSQL → ScalarDB (スキーマ抽出、分析、ストアドプロシージャ / トリガーの Java 変換)

## Pipeline Dependencies

```
investigate -> analyze -> [evaluate-mmi, evaluate-ddd] -> integrate-evaluations
  -> redesign -> [create-domain-story (optional, per domain)]
  -> design-microservices -> [design-scalardb | design-data-layer, design-api]
  -> [review-consistency, review-scalardb|review-data-integrity, review-operations, review-risk, review-business]
  -> review-synthesizer -> report -> review-report
```

依存関係マニフェスト (architect)：@skills/common/skill-dependencies.yaml

このマニフェストはコアパイプラインのみを対象としている。残りの architect の Skill である、
`investigate-security`、`select-scalardb-edition`、`design-scalardb-analytics`、
`design-implementation`、`generate-test-specs`、`generate-scalardb-code`、
`generate-infra-code`、`design-infrastructure`、`design-security`、
`design-observability`、`design-disaster-recovery`、`estimate-cost` は、
**手動拡張層 (manual extension tier)** を形成する：これらは `/architect:pipeline` によって実行されず、
個別に（通常はコアパイプラインの後に）または `/architect:start` を通じて呼び出される。

**product** プラグインは独自のパイプラインとマニフェストを持つ：`skills/product/common/skill-dependencies.yaml` (ビジョン -> 成功指標 / 収益 -> スコープ -> 仮説検証 [ゲート] -> ペルソナ / ジャーニー / ポジショニング -> ドメインストーリー / デザインシステム -> UI モック / 機能 / データモデル / フロントエンド -> ドメインマッピング / API -> SLA/NFR -> アーキテクチャ設計 -> レビュー -> レポート。必要に応じて `adapt-change`)。これは最後に `/architect:define-requirements` に引き継がれる。

## Output Conventions

すべての出力は Git で無視 (git-ignored) される：

```
reports/                    # 分析および設計ドキュメント
generated/                  # サービスごとの生成コード
work/                       # パイプラインの状態、中間ファイル
```

命名規則と Front Matter ルール：@rules/output-conventions.md

## Model Assignment

| Model | Use For | Examples |
|-------|---------|----------|
| **opus** | アーキテクチャの決定、トレードオフ分析、リスク | analyze, review-risk, redesign, design-microservices |
| **sonnet** | 標準的な分析、ドキュメント生成、レビュー | investigate, review-consistency, evaluate-mmi |
| **haiku** | テンプレート生成、ステータスチェック、単純な変換 | init-output, render-mermaid, report |

**product** プラグインも同じ階層に従う（`skills/product/common/skill-dependencies.yaml` に Skill ごとの `model` を定義）：戦略 / 判断には **opus** (16個の Skill：`define-vision`、`define-success-metrics`、`research-landscape`、`design-revenue`、`name-product`、`validate-assumptions`、`generate-persona`、`design-positioning`、`create-domain-story`、`design-system`、`define-data-model`、`map-domains`、`design-api`、`design-architecture`、`review`、`adapt-change`)、構造化された生成とオーケストレーションには **sonnet** (10個の Skill：`define-scope`、`map-journey`、`generate-ui-mock`、`generate-frontend`、`define-features`、`design-sla`、`define-nfr`、`report`、および `start` オーケストレーターと `init-output`)。

## Tool Priority

1. **Serena MCP** (get_symbols_overview, find_symbol) — 構造の理解
2. **Glob/Grep** — ファイルの発見とパターン検索
3. **Read** — 対象を絞ったファイルの読み込み
4. **Task (sub-agent)** — 多数のファイルにわたる大規模な探索

## Rules & References

「When to Read」の条件が当てはまる場合、Read ツールを使用してオンデマンドでこれらのファイルを読み込むこと。
セッションのコンテキストを小さく保つために、これらは意図的に自動インポートされない（`@` プレフィックスなし）。
非 ScalarDB の作業のために ScalarDB のルールをロードしないこと。

| Resource | Location | When to Read |
|----------|----------|--------------|
| ScalarDB の例外処理 | rules/scalardb-exception-handling.md | 例外処理、リトライロジック |
| ScalarDB CRUD パターン | rules/scalardb-crud-patterns.md | CRUD API 操作 |
| ScalarDB JDBC パターン | rules/scalardb-jdbc-patterns.md | JDBC / SQL 操作 |
| ScalarDB 2PC パターン | rules/scalardb-2pc-patterns.md | Two-Phase Commit (二相コミット) プロトコル |
| ScalarDB 設定検証 | rules/scalardb-config-validation.md | 設定の正確性 |
| ScalarDB スキーマ設計 | rules/scalardb-schema-design.md | スキーマとキーの設計 |
| ScalarDB Java のベストプラクティス | rules/scalardb-java-best-practices.md | Java のコーディング標準 |
| ScalarDB コーディングパターン | rules/scalardb-coding-patterns.md | コード生成、design-scalardb、generate-scalardb-code |
| ScalarDB エディションプロファイル | rules/scalardb-edition-profiles.md | エディションの選択 |
| 評価フレームワーク | rules/evaluation-frameworks.md | MMI / DDD スコアリング |
| Mermaid のベストプラクティス | rules/mermaid-best-practices.md | ダイアグラムの作成 |
| Spring Boot 統合 | rules/spring-boot-integration.md | Java のコード生成 |
| 出力構造のコントラクト | templates/output-structure.md | ファイルの依存関係 |
| サブエージェントのパターン | skills/common/sub-agent-patterns.md | サブエージェントの生成 |
| 進行状況レジストリ | skills/common/progress-registry.md | pipeline-progress.json のスキーマと再開の動作 |
| API リファレンス | skills/common/references/api-reference.md | ScalarDB API の詳細 |
| インターフェースマトリックス | skills/common/references/interface-matrix.md | 6つのインターフェースの組み合わせ |
| 例外の階層 | skills/common/references/exception-hierarchy.md | 例外の決定ツリー |
| SQL リファレンス | skills/common/references/sql-reference.md | SQL の文法と制限 |
| スキーマフォーマット | skills/common/references/schema-format.md | JSON / SQL スキーマフォーマット |
| 設定リファレンス | skills/common/references/configuration-reference.md | バックエンドごとのすべての ScalarDB 設定プロパティ |
| コードパターン | skills/common/references/code-patterns/ | 6つのインターフェースの組み合わせすべてに対応する完全なアプリテンプレート |

## Conventions

- **出力言語**: プロジェクトごとに設定可能 (デフォルトは `en`、`ja` をサポート)
- **ファイルの命名規則**: すべての生成されたファイルにケバブケース (kebab-case) を使用する
- **Front Matter**: すべての出力ファイルには、`schema_version` を含む YAML の Front Matter を含めなければならない
- **ダイアグラム**: すべてのダイアグラムで Mermaid の構文を使用する (フックによって検証される)
- **即時出力**: 各 Skill のステップは、完了時に自身の出力ファイルを書き込む
- **ScalarDB のオプション化**: ScalarDB が使用されない場合、ScalarDB 固有の Skill はスキップされ、review-scalardb の代わりに review-data-integrity が実行される
