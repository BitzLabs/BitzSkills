# AGENTS.md — BitzSkills 共通ルール（マスター）

このファイルが全エージェント（Claude Code / Codex / Antigravity）共通ルールの唯一の正。
Claude Code は CLAUDE.md のインポート経由で、Codex と Antigravity(agy) は本ファイルを直接読む。

## リポジトリの役割

[Agent Skills](https://agentskills.io/specification) オープン標準に準拠したスキルを
Claude Code / Antigravity 2.0 向けの**プラグイン**として開発・配布する**モノレポ**。
リポジトリルートはマーケットプレイス `bitzskills` で、`plugins/` 配下の各フォルダが1つのプラグイン。

導入方法は2系統:

- プラグイン一括インストール（推奨）: Claude Code は
  `/plugin marketplace add <このリポジトリ>` → `/plugin install <plugin名>@bitzskills`、
  Antigravity 2.0 は `agy plugin install <リポジトリ>/plugins/<plugin名>`。手順の正は
  `plugins/skill-creator/skills/skill-packager/references/platform-paths.md`
- スキル単体の直接配置: `skill-packager` で各プラットフォームのパスへコピー

## 構成

```
.claude-plugin/marketplace.json  # マーケットプレイス定義（全プラグインを列挙）
plugins/
├── skill-creator/   # スキル開発ツール群（creator→validator→tester→evaluator→packager と自己改善ループ）
├── plugin-creator/  # プラグイン開発ツール群（構造/コマンド/エージェント/フック/MCP + create-plugin コマンド）
└── bitz-sdd/        # 仕様駆動開発（SDD）ワークフロー（discovery→design→review→infra、docs同期、レポート）
evals/               # tester/evaluator の作業成果物と observer の観察ログ（全プラグイン共用）
docs/                # リポジトリ自身の解説と調査メモ（調査報告/ は3エージェントの検証済み仕様）
scripts/             # エージェント共用の運用スクリプト（bump / release check）
```

各プラグインの正確なスキル一覧は `plugins/*/skills/` の実体が正。本ファイルには個別列挙しない。

## ガードレール（全エージェント共通）

### 禁止（実行しない）

- `rm -rf` / `git push --force` / `git reset --hard` / `git clean -f`
- `main` への直接コミット（変更時は必ずブランチを切る）
- 認証情報・トークン類（`~/.claude/.credentials.json` 等）の読み取り・出力

### 事前確認が必要（ユーザーの明示承認なしに実行しない）

- リポジトリ外への書き込み（`~/.claude/skills/`・`~/.gemini/config/skills/` 等への
  skill-packager による配置・上書き・削除を含む）
- `evals/` 配下の既存成果物の削除・上書き

### 検証義務

- 他エージェントの「成功しました」という自己申告を信用せず、
  `python3 scripts/release_check.py` を自分で再実行して確認する
- skill-improver によるスキル自動修正は、コミット前に人間が diff を確認する

## コミット・PR 規約

- **コミットタイトル**: Conventional Commits に従う —
  `<type>(<scope>): <説明>`。type は `feat` / `fix` / `docs` / `refactor` / `test` / `chore`
  （破壊的変更は `!` を付ける。例: `refactor!:`）。scope はプラグイン名（リポジトリ横断なら省略可）。
  説明・本文は日本語可
- **マージ**: PR は squash merge とし、マージコミットのタイトル = PR タイトル
  （つまり PR タイトルも Conventional Commits 準拠。CI が機械検査する）
- **PR 本文**: 目的 / 変更点 / 検証結果（`release_check.py` と pytest の実出力）を含める
  （`.github/PULL_REQUEST_TEMPLATE.md` 参照）
- **1 PR = 1 関心事**: `git revert` で丸ごと戻せる粒度を保つ。version bump は PR の最終コミットに含める

## 定型手順（手作業せずスクリプトを使う）

- **version bump**: `python3 scripts/bump_version.py <plugin名> [major|minor|patch]`
  — 2つのマニフェスト（`.claude-plugin/plugin.json` と `plugin.json`）を必ず同じ値に保つ
- **リリース前検証**: `python3 scripts/release_check.py`
  — version 整合・marketplace 整合・frontmatter 必須項目・プラグイン validate を一括チェック

## 新しいプラグインの追加手順

1. `plugins/<name>/` を作成し、マニフェストを2つ置く:
   `.claude-plugin/plugin.json`（Claude Code 用）と `plugin.json`（Antigravity 2.0 用）。
   両者の `version` は常に同じ値（以後の bump は `scripts/bump_version.py` で行う）
2. `plugins/<name>/skills/<skill-name>/SKILL.md` を追加する
3. `.claude-plugin/marketplace.json` の `plugins[]` にエントリを追加する（`"source": "./plugins/<name>"`）
4. `python3 scripts/release_check.py` で検証する

## 規約

- 各スキルは自己完結させる（フォルダ単位でコピーされるため、他スキルの
  `references/` を相対パスで参照しない。連携はスキル名の言及で行う）
- SKILL.md の frontmatter 仕様は
  `plugins/skill-creator/skills/skill-creator/references/spec.md` が正
- テスト成果物は `evals/<skill-name>/` に置く
  （書式: `plugins/skill-creator/skills/skill-tester/references/test-design.md`）
- 観察ログは `evals/observations/observations.jsonl` に置く
  （書式: `plugins/skill-creator/skills/skill-observer/references/observation-schema.md`）
- スキルを追加・変更したら skill-validator のチェックリスト
  （`plugins/skill-creator/skills/skill-validator/references/checklist.md`）で検証する
- 全スキルの frontmatter に `metadata`（version/author/created/updated）を必須で持たせる。
  内容を変更したら semver で version を bump し updated を更新する
- スキルを変更したら、そのプラグインの version も `scripts/bump_version.py` で bump する
- インストール状態は配置先 frontmatter の `installed-at` / `installed-from` で自己記述する
  （skill-packager が管理。ライブラリ側には書かない。プラグイン経由の導入分には stamp しない）
- Antigravity 2.0 の仕様で迷ったら `docs/調査報告/01.Antigravity/` が正
  （公式組み込み docs と agy CLI の実測に基づく。Gemini 生成の解説文書は参照しない）。
  Claude Code は `docs/調査報告/02.ClaudeCode/`、Codex は `docs/調査報告/03.Codex/`
