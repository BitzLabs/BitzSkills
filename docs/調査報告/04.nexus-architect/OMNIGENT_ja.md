# OMNIGENT.md

Claude Code プラグインとの互換性を維持しながら、汎用マルチエージェントオーケストレーターである **Omnigent** 配下でこのリポジトリを実行するための手順である。

このファイルは、[`AGENTS.md`](AGENTS.md) (Codex 対象) および [`CLAUDE.md`](CLAUDE.md) (Claude Code 対象) に対応する、Omnigent 向けのファイルである。3つとも**同じ** Skill について説明しており、ランタイムの解釈のみが異なる。ここでは Skill を一切変更しない。Omnigent は既存の `skills/*/SKILL.md` ファイルを直接読み込む。

## What This Repository Is

元々 Claude Code 向けにパッケージ化された3プラグイン構成のシステムアーキテクチャツールキットである：

- **architect** — システムアーキテクチャ、リファクタリング、設計、データベースのマイグレーション、レポート作成
- **scalardb** — ScalarDB アプリケーションの開発、レビュー、設定、スキャフォールディング
- **product** — プロダクトの方向性に関する Skill (ビジョン → SLA/NFR)。`skills/product/` 配下にネストされている

約90個の `SKILL.md` ファイルが存在する。各ファイルは自己完結型の指示書である。Claude Code ではこれらをスラッシュコマンド (例：`/architect:investigate`) として呼び出すが、Omnigent ではワーカーがコマンドをファイルに解決し、それを読み込んで従う。

## Quick Start: the loader

ワーカーは後述の解決ルールを記憶する必要はない。パスを解決し、解釈用プリアンブルを出力し、`${CLAUDE_PLUGIN_ROOT}` を展開した状態で Skill の本体を出力するローダーを呼び出すことができる：

```bash
bash tools/omnigent/load-skill.sh architect:investigate     # flat (architect) skill
bash tools/omnigent/load-skill.sh scalardb:model            # flat (scalardb) skill
bash tools/omnigent/load-skill.sh product:define-vision     # nested product skill
bash tools/omnigent/load-skill.sh investigate               # bare name → architect namespace
bash tools/omnigent/load-skill.sh --list                    # enumerate every skill
```

Skill が存在しない場合、ローダーは非ゼロで終了する (検索内容を示す stderr メッセージを出力する)。[`tools/omnigent/README.md`](tools/omnigent/README.md) を参照のこと。

## Slash → Path Resolution

ユーザーが Claude 形式のコマンドを呼び出した場合、一致するローカルファイルにマッピングする。**3つ**のプラグインがあり、`product` のみがネストされている。

| Command form        | Resolves to                          |
|---------------------|--------------------------------------|
| `/architect:<name>` | `skills/<name>/SKILL.md`             |
| `/scalardb:<name>`  | `skills/<name>/SKILL.md`             |
| `/product:<name>`   | `skills/product/<name>/SKILL.md`     |

`architect` と `scalardb` はフラットな `skills/` ディレクトリを共有している。そのため、両方のプレフィックス (およびプレフィックスのない単独の `<name>`) は、フラットな Skill を同一に解決する。`product` の Skill のみが `skills/product/` 配下にネストされている。

**ネストされたサブ Skill。** マイグレーションルーター (`migrate-oracle`、`migrate-mysql`、`migrate-postgresql`) は、スラッシュコマンドでは*ない*サブ Skill に委譲する。これらはパスによって読み込まれる (例：`skills/migrate-oracle/migrate-oracle-to-scalardb/SKILL.md`)。ルーターの本体は `${CLAUDE_PLUGIN_ROOT}/skills/...` パス経由でこれらを参照し、ローダーがそれを自動的に展開する。これらは直接読み込むことも可能である：
`load-skill.sh architect:migrate-oracle/migrate-oracle-to-scalardb`。

参照された Skill が存在しない場合、それが利用できないことを説明し、最も近い文書化されたフォールバックを選択すること。

## Path Resolution: `${CLAUDE_PLUGIN_ROOT}` and `@`-prefixes

リポジトリのルートは**絶対パス**である。ローダーはプリアンブルでこれを `CLAUDE_PLUGIN_ROOT == <absolute root>` として出力する。`${CLAUDE_PLUGIN_ROOT}`、`@rules/`、`@templates/`、`@skills/` などのリポジトリ相対パスは、この絶対ルートに対して解決すること。**カレントディレクトリ (CWD) がそれと等しいと思い込まないこと** (ローダーが `cd` することはない)。リポジトリのルートをプラグインのルートとして扱うこと：

- `${CLAUDE_PLUGIN_ROOT}` → 絶対リポジトリルート。ローダーは、Skill の本体にあるリテラルの `${CLAUDE_PLUGIN_ROOT}` を絶対ルートで置換してから出力するため、ローダーを使用するワーカーがこの生のトークンを目にすることはない。ワーカーが `SKILL.md` を直接 (ローダーなしで) 読み込む場合は、この置換を自身で実行しなければならない。
- `@rules/...`、`@templates/...`、`@skills/...` → リポジトリ相対パスとして解決する。

ランタイム出力ディレクトリ (リポジトリ相対)：

| Purpose            | Path                          |
|--------------------|-------------------------------|
| レポート            | `reports/`                    |
| 生成コード         | `generated/`                  |
| パイプライン状態   | `work/`                       |
| ルール              | `rules/`                      |
| 共通リファレンス  | `skills/common/references/`   |
| サブエージェントのテンプレート | `skills/common/subagents/`    |

## Claude Tool → Omnigent Tool Mapping

Skill の本体には Claude Code のツールが記載されている。これらを Omnigent のツールとして解釈すること：

| Claude tool        | Omnigent tool   | Notes                                    |
|--------------------|-----------------|------------------------------------------|
| `Read`             | `sys_os_read`   | ファイルを読み込む                              |
| `Write`            | `sys_os_write`  | ファイルを作成 / 上書きする                  |
| `Edit` / `MultiEdit` | `sys_os_edit` | インプレース編集を行う                            |
| `Bash`             | `sys_os_shell`  | シェルコマンドを実行する                      |
| `Grep`             | `sys_os_shell`  | シェル内で `rg` / `grep` を実行する           |
| `Glob`             | `sys_os_shell`  | シェル内で `rg --files` / `find` を実行する   |
| `LS`               | `sys_os_shell`  | `ls` を実行する                                    |
| `WebFetch` / `WebSearch` | (オーケストレーターのウェブ機能) | ネットワークアクセスが承認されている場合      |

## `Task(...)` Blocks → Sequential Bodies or Orchestrator Dispatch

いくつかの Skill (特に5つの視点による並列レビューやマイグレーションルーター) は、`Task(...)` を介して Claude のサブエージェントを生成する。Omnigent では、各 `Task` のプロンプト本体に対して以下のように扱う：

- **デフォルト (シーケンシャル):** 各プロンプト本体を同じワーカー内で1つずつ順に実行し、オーケストレーターに結果を集約させる。
- **並列 (オーケストレーター機能):** 真の並行サブエージェント実行は、単なるワーカーではなく、**オーケストレーター**がセッション / サブエージェントのディスパッチ API (例：`sys_session_send`) を介して実行する。

> **Note:** `sys_call_async` は、登録されたローカルの **Python ツール** をディスパッチするものであり、エージェント / サブエージェントのセッションではない。`Task(...)` のプロンプト本体を実行するためにこれを使用しては**ならない**。

いずれにせよ、**オーケストレーター**はすべての結果を収集した*後*に複合スコアを計算する。個々のサブエージェントは自身の調査結果のみを返す (例：各レビューは `reports/review/individual/review-<perspective>.json` を書き込み、シンセサイザーがそれらをマージする)。

## `AskUserQuestion` → Orchestrator ↔ Human Gate

Skill が多肢選択式の質問 (`AskUserQuestion`) を尋ねる場合、あるいはその他に人間の入力を必要とする場合：

1. 選択肢を**番号付きリスト**として提示する。
2. 実行を**一時停止**し、オーケストレーターのゲートを通じて人間に質問を提示する。
3. 人間が返答した時点で、その選択を利用して**再開**する。

Skill が `--auto` で (またはプロダクトパイプラインで `--profile=...` を伴って) 実行された場合、インタラクティブな操作はバイパスされる：各ゲートの文書化されたデフォルトを選択し、一時停止することなく続行すること。

## Hooks → Explicit Validation Gate

Claude Code では、`Write`/`Edit` の後に2つの `PostToolUse` フックが自動的に起動する (`hooks/hooks.json` を参照)：

- `hooks/validate-frontmatter.sh` — すべての `reports/**/*.md` は、`title`、`schema_version`、`skill` を含む有効な YAML の Front Matter で始まらなければならない。
- `hooks/validate-mermaid.sh` — Mermaid のダイアグラム構文。

**これらは Omnigent では自動起動しない。** レポートの `.md` を書き込んだ後は、明示的なゲートとしてこれらを実行すること (どちらのスクリプトもすでに CLI モードをサポートしているため、引数としてファイルパスを渡す)：

```bash
bash hooks/validate-frontmatter.sh <file.md>
bash hooks/validate-mermaid.sh <file.md>
```

**終了コードがゼロ以外**の場合は、ファイルに Front Matter またはダイアグラムのエラーがあることを意味する。続行する前に修正すること。最後にまとめて実行するのではなく、各レポートを書き込んだ後に両方を実行すること。

## `model:` Frontmatter

各 `SKILL.md` には `model:` のティア (opus / sonnet / haiku) が記載されている。Omnigent では以下のいずれかを行う：

- **これを無視し**、単一の有能なセッションモデルを一貫して使用する (最もシンプル)。
- オーケストレーターがモデル選択をサポートしている場合、**ティアを**ディスパッチごとのモデルに**マッピングする**。

推奨されるティア (Skill の Front Matter による)：判断を多く要する作業 (`analyze`、`redesign`、`design-microservices`、`design-scalardb`、`design-api`、`map-domains`、`review-risk`、およびプロダクト戦略の Skill) には **opus**、標準的な分析 / 生成 / レビューには **sonnet**、テンプレート化 (`init-output`、`render-mermaid`) には **haiku**。明示的に haiku ティアと指定されていないものには、Sonnet 以上のモデルを優先すること。

## Pipeline Sequencing

`skills/pipeline/SKILL.md` (および `skills/start/SKILL.md`) はオーケストレーターである。これら自体は分析を実行しない。Omnigent でパイプラインを実行するには：

1. `skills/common/skill-dependencies.yaml` (architect パイプライン) または `skills/product/common/skill-dependencies.yaml` (product パイプライン) から DAG を読み込む。各エントリには `depends_on`、`parallel_with`、`conditions`、`outputs`、および `model` が記載されている。
2. フェーズを依存関係の順に実行する。`parallel_with` のグループは並行して実行する (`Task` のディスパッチセクションを参照)。`conditions` を尊重する (例：`scalardb_enabled` の場合は `review-scalardb` を選択し、`scalardb_disabled` の場合は `review-data-integrity` を選択する)。
3. `work/pipeline-progress.json` (プレーンなデータであり、Claude の構造体ではない) で進行状況を追跡する。これは `options.output_language` (デフォルトは `en`、`ja` をサポート) も保持する。

オーケストレーターファイルの `disable-model-invocation: true` という Front Matter は Claude Code のヒントである。Omnigent はこれを無視し、ファイルを上記のオーケストレーション仕様として扱う。

## Interaction Rules

- **非侵襲的 (Non-invasive)。** `.claude-plugin/`、`CLAUDE.md`、`AGENTS.md`、`SKILL.md` の本体、`rules/`、`templates/`、または `hooks/` を変更しないこと。Omnigent はこのファイルと `tools/omnigent/` のヘルパーのみを追加し、Claude Code の互換性は維持される。
- (`--auto` でない限り) `AskUserQuestion` の選択肢を番号付きリストとして提示し、人間の返答を待つこと。
- 生成された出力は文書化された出力ディレクトリに保持し、YAML の Front Matter を含めること。
- レポートの `.md` や Mermaid ダイアグラムを書き込んだ後は、**両方の**検証フックを実行し、終了コードがゼロ以外の場合は続行する前に修正すること。

## Output Language

プロジェクトごとに `work/pipeline-progress.json` (`options.output_language`: デフォルトは `en`、`ja` をサポート) で設定可能である。レポートの文章は設定された言語を使用するが、YAML の Front Matter のキーと Mermaid のノード ID は英語のまま維持する。[`rules/output-conventions.md`](rules/output-conventions.md) を参照のこと。
