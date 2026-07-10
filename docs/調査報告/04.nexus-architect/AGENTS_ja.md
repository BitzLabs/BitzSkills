# AGENTS.md

Claude Code プラグインとの互換性を維持しながら、このリポジトリを Codex で利用するための手順である。

## What This Repository Is

このリポジトリは、元々 Claude Code 向けにパッケージ化された3プラグイン構成のアーキテクチャツールキットである：

- `architect`: システムアーキテクチャ、リファクタリング、設計、マイグレーション、およびレポート作成の Skill
- `scalardb`: ScalarDB アプリケーションの開発、レビュー、設定、およびスキャフォールディングの Skill
- `product`: プロダクトの方向性に関する Skill（プロダクトビジョンから SLA/NFR まで）であり、`skills/product/` 配下にネストされている。プロダクトルールは `rules/product/` 配下にある

Claude Code は引き続き `CLAUDE.md`、`.claude-plugin/`、および `/architect:start` や `/product:start` のようなスラッシュコマンドを使用する。
Codex は、この `AGENTS.md` ファイルと `skills/*/SKILL.md` ファイルを直接使用する。

## Codex Command Mapping

ユーザーが Codex で Claude 形式のコマンドを呼び出した場合、一致するローカル Skill にマッピングすること：

- `/product:<name>` -> `skills/product/<name>/SKILL.md` を読み込み、それに従う（プロダクト Skill は `skills/product/` 配下にネストされており、プロダクトルールは `rules/product/` 配下にネストされている）
- `/architect:<name>` -> `skills/<name>/SKILL.md` を読み込み、それに従う
- `/scalardb:<name>` -> `skills/<name>/SKILL.md` を読み込み、それに従う
- `@rules/...`、`@templates/...`、および `@skills/...` -> リポジトリ相対パスとして解決する

参照された Skill が存在しない場合、それが利用できないことを説明し、最も近い文書化されたフォールバックを選択すること。

## Claude Tool Mapping

多くの Skill ファイルには Claude Code のツールが記載されている。Codex では、それらを以下のように解釈すること：

- `Read`: ファイルの読み込みには `sed`、`cat`、または `rg` を使用する
- `Write`: ファイルの作成には `apply_patch` を使用する
- `Edit` / `MultiEdit`: `apply_patch` を使用する
- `Bash`: シェルコマンドを使用する
- `Grep`: `rg` を使用する
- `Glob`: `rg --files` または `find` を使用する
- `LS`: `ls` を使用する
- `WebFetch` / `WebSearch`: ネットワークアクセスが承認されている場合は、Codex のウェブアクセス、Context7、または `curl` を使用する
- `AskUserQuestion` / `Question`: チャットで番号付きの選択肢を提示し、ユーザーの返答を待つ
- `Task` / `Subagent`: ユーザーが明示的にサブエージェントを要求しない限り、メインの Codex スレッドでステップを実行する
- `Parallel`: 有用な場合は並列シェル読み込みを使用する。コード記述のステップは調整した状態を維持する
- `TodoWrite` / `TodoRead`: タスクが永続的な TODO を必要とする場合にのみ、ローカルの TODO ファイルを使用する
- `Skill`: 参照された `SKILL.md` を開き、それに従う
- `ExitPlanMode`: 無視する

## Runtime Paths

Codex の実行では、リポジトリ相対パスを優先すること：

- レポート: `reports/`
- 生成コード: `generated/`
- パイプライン状態: `work/`
- ルール: `rules/`
- 共通リファレンス: `skills/common/references/`
- サブエージェントのプロンプトテンプレート: `skills/common/subagents/`

Skill は `${CLAUDE_PLUGIN_ROOT}/...`（例：
`${CLAUDE_PLUGIN_ROOT}/skills/common/references/api-reference.md`、
`${CLAUDE_PLUGIN_ROOT}/rules/scalardb-crud-patterns.md`）経由でプラグインファイルを参照する。Codex では、
これらをリポジトリ相対パスとして解決すること（後述の `CLAUDE_PLUGIN_ROOT` に関する注記を参照）。

レガシーなフォールバック（古い Skill のコピーがまだそれらを言及している場合のみ）：

- `.claude/docs/*` -> `skills/common/references/*`
- `.claude/rules/*` -> `rules/*`

`.claude/configuration/databases.env` や `.claude/output/` に言及するマイグレーションの Skill については、ユーザーがランタイム状態のマイグレーションを要求しない限り、それらのパスを維持すること。これらは互換性パスであり、Claude Code と Codex の両方で使用できる。

Skill が `CLAUDE_PLUGIN_ROOT` に言及する場合、Codex ではリポジトリのルートをプラグインのルートとして扱うこと。

- `${CLAUDE_PLUGIN_ROOT}/skills/common/subagents/<db>/` -> `skills/common/subagents/<db>/`（マイグレーションの Skill 向けのサブエージェントプロンプトテンプレート）
- `${CLAUDE_PLUGIN_ROOT}/subagents/<db>/` -> `skills/common/subagents/<db>/`（レガシーなサブエージェントプロンプトパス）

## Pipeline Skill

`skills/pipeline/SKILL.md` はオーケストレーターである。これ自体は分析を実行せず、
`skills/common/skill-dependencies.yaml` を読み込んで実行順序を決定し、その後各フェーズの
`SKILL.md` を順番に呼び出す。Codex でパイプラインを実行する場合は、依存関係グラフを手動でたどること：
各 Skill ファイルを順番に読み込み、実行してから次のフェーズに進む。

そのファイル内の `disable-model-invocation: true` という YAML の Front Matter は、Claude Code プラグインのヒントである。Codex は
これを解釈しないため、上記で説明したオーケストレーションの仕様としてファイルを扱うこと。

## Model Recommendations

Claude Code は、各 Skill の割り当てに基づいてモデルを自動的に切り替える。Codex は
`model:` の設定を無視し、セッションのモデルを一貫して使用するため、可能な限り同等のティアを選択すること：
アーキテクチャの決定、戦略、トレードオフ分析、およびリスクには Opus、標準的な分析、
構造化された生成、およびほとんどのレビューには Sonnet、テンプレートの生成と単純な変換には Haiku。

依存関係の YAML ファイルは、パイプラインの Skill にとって権威がある。単独の Skill は、自身の
`SKILL.md` の Front Matter を使用する。同じ名前の architect の Skill と区別するために、以下では product の Skill 名に
プレフィックスが付けられている。

| Plugin | Opus equivalent | Sonnet equivalent | Haiku equivalent sufficient |
|---|---|---|---|
| architect | define-requirements, analyze, map-domains, redesign, create-domain-story, design-microservices, design-scalardb, design-data-layer, design-api, design-implementation, generate-scalardb-code, design-infrastructure, review-risk | start, pipeline, investigate, investigate-security, analyze-data-model, evaluate-mmi, evaluate-ddd, integrate-evaluations, select-scalardb-edition, design-scalardb-analytics, generate-test-specs, generate-infra-code, design-security, design-observability, design-disaster-recovery, review-consistency, review-scalardb, review-data-integrity, review-operations, review-business, review-synthesizer, review-report, estimate-cost, migrate-database, migrate-oracle, migrate-mysql, migrate-postgresql | init-output, report, render-mermaid |
| scalardb | — | model, config, scaffold, error-handler, crud-ops, jdbc-ops, local-env, docs, build-app, review-code, migrate | — |
| product | product:define-vision, product:define-success-metrics, product:research-landscape, product:design-revenue, product:name-product, product:validate-assumptions, product:generate-persona, product:design-positioning, product:create-domain-story, product:design-system, product:define-data-model, product:map-domains, product:design-api, product:design-architecture, product:review, product:adapt-change | product:start, product:init-output, product:define-scope, product:map-journey, product:generate-ui-mock, product:define-features, product:generate-frontend, product:design-sla, product:define-nfr, product:report | — |

## Interaction Rules

- Claude Code の互換性を維持すること。明示的に要求されない限り、`.claude-plugin/`、`CLAUDE.md`、または Claude 固有の Front Matter を削除しないこと。
- Skill が `AskUserQuestion` を用いて多肢選択式の入力を求めている場合、選択肢を番号付きリストとして表示し、ユーザーの返答を待ってから続行すること。
- Skill が並列の Claude サブエージェントを求めている場合、前提となるステップを順番に実行し、独立したシェル読み込みや明示的にユーザーが承認したエージェントの作業のみを並列化すること。
- 生成された出力は文書化された出力ディレクトリに保持し、Markdown レポートには YAML の Front Matter を含めること。
- レポートの Markdown ファイルや Mermaid ダイアグラムを編集した後は、続行する前に**必ず**検証フックを実行しなければならない：
  - `hooks/validate-frontmatter.sh <file.md>`
  - `hooks/validate-mermaid.sh <file.md>`

  終了コードがゼロ以外の場合は、ファイルに Front Matter またはダイアグラムのエラーがあることを意味する。続行する前に修正すること。
