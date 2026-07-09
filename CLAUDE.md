# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Conversation Guidelines

- 常に日本語で会話してください。
- 技術的な説明も日本語で行ってください。
- エラーメッセージの解説やドキュメント生成も日本語で行ってください。

## リポジトリの役割

[Agent Skills](https://agentskills.io/specification) オープン標準に準拠したスキルを
Claude Code / Antigravity 2.0 向けの**プラグイン**として開発・配布する**モノレポ**。
リポジトリルートはマーケットプレイス `bitzskills` で、`plugins/` 配下の各フォルダが
1つのプラグイン。導入方法は2系統:

- プラグイン一括インストール（推奨）: Claude Code は
  `/plugin marketplace add <このリポジトリ>` → `/plugin install <plugin名>@bitzskills`、
  Antigravity 2.0 は `agy plugin install <リポジトリ>/plugins/<plugin名>`。手順の正は
  `plugins/skill-creator/skills/skill-packager/references/platform-paths.md`
- スキル単体の直接配置: `skill-packager` で各プラットフォームのパスへコピー

## 構成

```
.claude-plugin/
└── marketplace.json        # マーケットプレイス定義（全プラグインを列挙）
plugins/
├── skill-creator/          # プラグイン: スキル開発ツール群
│   ├── .claude-plugin/
│   │   └── plugin.json     # Claude Code プラグインマニフェスト
│   ├── plugin.json         # Antigravity 2.0 プラグインマニフェスト
│   └── skills/             # プラグインに含まれる10スキル（両プラットフォーム共通）
│       ├── skill-creator/      # 新規スキルの設計・雛形作成
│       ├── skill-validator/    # 仕様準拠チェック（lint）
│       ├── skill-optimizer/    # description最適化・本文分離・構造改善
│       ├── skill-tester/       # テストケース設計と実行
│       ├── skill-evaluator/    # 実行結果の採点・レポート作成
│       ├── skill-packager/     # 実環境への配置・配布用zip化
│       ├── skill-pipeline/     # 全工程を案内する統括スキル
│       ├── skill-instrumenter/ # 監視対象スキルへの観察ステップ注入（計装）
│       ├── skill-observer/     # 実行直後の自己観察・観察ログ記録
│       └── skill-improver/     # 観察ログ分析→スキル修正（自己改善）
├── plugin-creator/         # プラグイン: プラグイン開発ツール群（plugin-dev の日本語版）
│   ├── .claude-plugin/plugin.json
│   ├── plugin.json
│   ├── commands/create-plugin.md   # ガイド付きプラグイン作成ワークフロー
│   ├── agents/                     # agent-creator / plugin-validator / skill-reviewer
│   └── skills/             # プラグイン開発の7スキル
│       ├── plugin-structure/       # 構造・マニフェスト・自動発見
│       ├── skill-development/      # プラグイン同梱スキルの作成
│       ├── command-development/    # スラッシュコマンドの作成
│       ├── agent-development/      # サブエージェントの作成
│       ├── hook-development/       # フックとイベント駆動自動化
│       ├── mcp-integration/        # MCPサーバー統合
│       └── plugin-settings/        # .local.md による設定管理
└── bitz-sdd/               # プラグイン: 仕様駆動開発（SDD）ワークフロー
    ├── .claude-plugin/plugin.json
    ├── plugin.json
    └── skills/             # SDD の6スキル
        ├── bitz-sdd/           # SDD常時運用（EARS検証・3ゲート・spec_inspect.py）
        ├── sdd-docs/           # docs/（人間ナラティブ層）の初期化・検証（docs_inspect.py）
        ├── sdd-discovery/      # 上流探索（ビジョン→成功指標→スコープ→ペルソナ）
        ├── sdd-design/         # 設計（ドメインモデル・API・アーキテクチャ）
        ├── sdd-review/         # 設計ドキュメントの多観点並列レビューと統合判定
        └── sdd-infra/          # インフラ・運用設計（IaC生成はしない）
evals/                      # tester/evaluator の作業成果物と observer の観察ログ（全プラグイン共用）
docs/                       # リポジトリ自身の解説と調査メモ
```

## 新しいプラグインの追加手順

1. `plugins/<name>/` を作成し、マニフェストを2つ置く:
   - `.claude-plugin/plugin.json`（Claude Code 用。name / description / version / author）
   - `plugin.json`（Antigravity 2.0 用。name / version / description）
   - 両マニフェストの `version` は**常に同じ値**に保つ
2. `plugins/<name>/skills/<skill-name>/SKILL.md` を追加する
   （スキル開発フロー・規約は既存のものをそのまま適用）
3. `.claude-plugin/marketplace.json` の `plugins[]` にエントリを追加する
   （`"source": "./plugins/<name>"`）
4. `claude plugin validate .` と `agy plugin validate plugins/<name>` で検証する

スキル開発の標準フロー: creator → validator → tester → evaluator →
（不合格なら optimizer で改善して反復）→ packager。全体は `skill-pipeline` が統括する。
配置後の自己改善ループ: instrumenter で計装したスキルを実行のたびに observer が
自己観察（問題のみ `evals/observations/observations.jsonl` に記録）→ 溜まったログを
improver が分析してスキルを修正する。

## 規約

- 各スキルは自己完結させる（フォルダ単位でコピーされるため、他スキルの
  `references/` を相対パスで参照しない。連携はスキル名の言及で行う）
- SKILL.md の frontmatter 仕様は
  `plugins/skill-creator/skills/skill-creator/references/spec.md` が正
- テスト成果物はスキルフォルダ内ではなく `evals/<skill-name>/` に置く
  （書式は `plugins/skill-creator/skills/skill-tester/references/test-design.md` で定義）
- 観察ログは `evals/observations/observations.jsonl` に置く（書式は
  `plugins/skill-creator/skills/skill-observer/references/observation-schema.md` で定義）
- スキルを追加・変更したら `skill-validator` のチェックリスト
  （`plugins/skill-creator/skills/skill-validator/references/checklist.md`）で検証する
- 全スキルの frontmatter に `metadata`（version/author/created/updated）を必須で
  持たせる。内容を変更したら semver で version を bump し updated を更新する
  （規則は `plugins/skill-creator/skills/skill-creator/references/spec.md` の
  「metadata運用規約」）
- インストール状態は配置先 frontmatter の `installed-at` / `installed-from` で
  自己記述する（`skill-packager` が管理。ライブラリ側には書かない）。
  プラグイン経由の導入分には stamp しない
- プラグイン配下のスキルを変更したら、そのプラグインの version
  （`plugins/<name>/.claude-plugin/plugin.json` と `plugins/<name>/plugin.json`、
  **両方を同じ値に**）も semver で bump する
- Antigravity 2.0 のプラグイン仕様で迷ったら
  `docs/Antigravityプラグイン仕様（検証済み）.md` が正（公式組み込み docs と
  agy CLI の実測に基づく。Gemini 生成の解説文書は実仕様と食い違うため参照しない）
