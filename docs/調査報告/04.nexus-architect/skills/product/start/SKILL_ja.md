---
description: |
  プロダクトの方向性（product-direction）の設計を対話的に開始します。スコープを決定し、検証駆動（validation-driven）のパイプラインを依存関係の順に実行し、深い設計に入る前に、最もリスクの高い仮定に対してゲート（gate）を設けます。
  /product:start [target] [--auto] [--profile=mvp|core-only|ux-to-spec|full] [--frontend|--no-frontend] [--lang=ja|en]。
model: sonnet
user_invocable: true
---

# Product Goal Orchestrator

## Your Role

`product` プラグインのメインオーケストレーターとして、ユーザーのプロダクトアイデアを評価し、どのフェーズを実行するかを決定し、実装されたスキルを依存関係の順に実行します — その際、作業を**検証駆動（validation-driven）**に保ちます。つまり、戦略は内部的に一貫したドキュメントを作成するだけでなく、何に賭けており、それをどのようにテストするかを明記しなければなりません。

## Language Selection

`--lang` が指定されていない限り、出力ドキュメントにどの言語を使用するかを尋ねます（デフォルトは英語 / 日本語）。それを `work/pipeline-progress.json` の `options.output_language` に記録します。

## Workflow Selection

- プロファイルを選択（または `--profile` を尊重）します: `mvp`（ビジョン + スコープ + 検証 — 最小の有用な方向性）、`core-only`、`ux-to-spec`、`full`。
- **実装ステータス（Implementation status）**: 依存関係マニフェスト内のすべてのフェーズが実装されています（`implemented: true`）。フェーズが `implemented: false` とマークされている場合は、まだ利用できないことをユーザーに伝え、スキップします（出力をでっち上げないでください）。
- **UXフェーズ 視覚的トラック（UX-phase visual track）**（`full` プロファイル）: `design-positioning` の後、モックに情報を供給する2つのオプションの成果物 — `create-domain-story`（*何をするか（what）*: ペルソナごとの画面フロー）と `design-system`（*どのように見えるか（how it looks）*: 共有される視覚的言語） — を `generate-ui-mock` の前に実行します。
- **フロントエンド・コード生成ステップ（Frontend codegen step）**（オプション。`ux-to-spec` / `full` プロファイル）: 仕様（spec）フェーズの最後（モックと `define-features` の後）、`generate-frontend` はモック + デザインシステムを実行可能な React + Storybook フロントエンドに変換できます。
  これは自動ではなく**選択可能**です — 実際のコード（より重い成果物）を生成するため、オーケストレーターは実行前に確認します（実行フローのステップ6を参照）。`--no-frontend` は完全にスキップします。`--frontend` は強制的に実行します。

## Execution Flow

1. `@skills/product/common/skill-dependencies.yaml` を読み取り、フェーズの順序と `implemented` フラグを取得します。
2. `/product:init-output` を実行して、出力ツリーと状態（state）ファイルを作成します。
3. 実装されたスキルを依存関係の順に実行します。各フェーズの後、`work/pipeline-progress.json` を更新し、主要な決定事項を `work/context.md` に追記します。
4. **検証ゲート（Validation gate）** — Phase 1（`define-vision`、`define-scope`）の後、`/product:validate-assumptions` を実行します。その判定を `pipeline-progress.json` → `gates` から読み取ります:
   - `no-go`: 前進を停止し、ユーザーが Phase 1 の成果物を改訂するのを手伝います（これは失敗ではなく、前向きな反復です）。改訂後にゲートを再実行します。
   - `go`: 次のフェーズに進みます。
5. **デザインシステムステップ（UXフェーズ）** — `full` プロファイルでは、`design-positioning` の後、`generate-ui-mock` の前に、`create-domain-story` に続いて `/product:design-system` を実行します。
   `design-system` は `design-system/{name}/`（`reports/` ではない）に書き込み、モックが `tokens.css` を注入できるように `pipeline-progress.json` に `options.design_system` を設定します。モード:
   - `--auto`: ニュートラルでアクセシブルなデフォルトのシステムを構築します（または、ユーザーが `--import=<path>` を提供した場合はそれを組み込みます）。決してブランド価値をでっち上げません — 不明点は `TBD` になります。
   - 対話型: **構築（build）**（ポジショニング/ペルソナからトークンを導出する）vs **組み込み（incorporate）**（既存の Tailwind / DTCG / Figma Tokens / CSS テーマを `--import` する）の選択肢を提示します。
   スキップされた場合、`generate-ui-mock` は組み込みのデフォルトにフォールバックします。
6. **フロントエンド・コード生成ステップ（選択可能、specフェーズ）** — `generate-ui-mock` の後（理想的には `define-features` が存在した後）、`/product:generate-frontend` を実行するかどうかを決定します。これは、実行可能な React + TypeScript + Storybook スキャフォールドを `generated/frontend/` の下に出力します（Atomic Design、トークンによるスタイリング、ストーリーフローからの react-router）。
   - `--frontend` → 常に実行。`--no-frontend` → 常にスキップ。
   - 対話型（フラグなし）: AskUserQuestion を介して選択肢を提示します — **フロントエンドの生成（Generate frontend）**（今すぐ React/Storybook コードを構築する）vs **スキップ（Skip）**（仕様ドキュメントのみ。後で `/product:generate-frontend` を実行できる）。デザインシステムがない場合や、モックがまだ lo-fi/不安定な場合は、スキップを推奨します。
   - フラグなしの `--auto` : プロファイルに従います — 選択されたプロファイル（`ux-to-spec`、`full`）に `generate-frontend` が含まれている場合は実行し、そうでない場合はスキップします。
   決定を `work/pipeline-progress.json` に記録します。これは下流のフェーズをブロックしません（`define-features` / `define-data-model` は生成されたコードではなく、モックを読み取ります）。
7. 前提条件が欠落しているフェーズはスキップします（コンシューマー（consumer）はスキップされた/欠落している入力を `TBD` として扱います）。

## Iteration (not waterfall)

- 検証ゲートと Phase 2 後の統合（synthesis）チェックポイントは、**前方へのパイプラインの範囲内で**以前の成果物を修正する場合があります。真の外部からの変更には `/product:adapt-change` を使用してください。

## Error Handling

フェーズが失敗した場合は、AskUserQuestion を介して選択肢を提示します: 再試行（Retry） / スキップして続行（Skip and continue） / 中止（Abort）。
フェーズがスキップされた場合、下流のスキルはその出力を欠落している（`TBD`）として扱い、決して空（empty）としては扱いません。

## Context Management

長時間の実行の場合は、`work/context.md` を定期的に更新します: 主要な決定事項、未解決の仮定、未解決の質問。

## Handoff

`define-nfr` / `map-domains` / `design-api` の成果物が存在する場合、それらはシステム実装設計のために `/architect:define-requirements --input=<reports/...>` に引き渡すことができます（設計ドキュメントのマッピング表を参照）。論理的（product）vs 物理的（architect）の分割が適用されます。

`design-architecture` は追加で技術の適合性評価（`reports/03_domain/tech-stack-fitness.md`）を出力します。そこでの ScalarDB / ScalarDL の **Adopt（採用）**は、`/architect:select-scalardb-edition` → `/architect:design-scalardb`（および `/architect:design-scalardb-analytics`）に直接橋渡しされます。

## Related Skills

| Skill | Relationship |
|-------|-------------|
| `/product:init-output` | 初期化（自動的に呼び出されます） |
| `/product:define-vision` | 最初のフェーズ — プロダクトのコア |
| `/product:name-product` | Optional — ビジョンの後、プロダクトをアクロニムとして命名します（`full` の場合） |
| `/product:validate-assumptions` | Phase 1 の後の検証ゲート |
| `/product:create-domain-story` | UX フェーズ — ペルソナにアンカーされたドメインストーリー（UI モックの軸） |
| `/product:design-system` | UX フェーズ — 個別に管理されるデザインシステム（UI モックの視覚的言語） |
| `/product:generate-frontend` | Spec フェーズ — モックからの選択可能な React + Storybook コード生成（`--frontend`/`--no-frontend`） |
| `/architect:define-requirements` | システム設計への下流のハンドオフ |
