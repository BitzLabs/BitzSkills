# skill-creator — スキル開発ライフサイクル

エージェントスキル（[Agent Skills](https://agentskills.io/specification) 準拠の SKILL.md +
フォルダ一式）の**開発の全工程**を支援するツールキット。作成から検証・テスト・評価・配置、
そして配置後の自己改善ループまでを 10 スキルで担当する。

## 収録スキル

### 開発パイプライン（作成 → 配置）

| スキル | 役割 |
|---|---|
| `skill-pipeline` | 全工程を案内する統括スキル。どの工程から始めるべきか不明なときの入口 |
| `skill-creator` | 新規スキルの対話的な設計・雛形作成 |
| `skill-validator` | Agent Skills 仕様準拠のチェックリスト検査（構造 / name / description / 本文 / 設計品質 / metadata） |
| `skill-tester` | テストケース設計と「スキルあり / なしベースライン」両方の実行。結果は `evals/<skill-name>/` へ |
| `skill-evaluator` | テスト結果の採点と report.md 作成。実装を要する改善提案は `.spec/spec-issues/` へ起票 |
| `skill-optimizer` | description の発動精度改善・長い本文の references/ 分離（progressive disclosure）・構造改善 |
| `skill-packager` | 実環境への配置（コピー / シンボリックリンク / プラグイン一括）、バージョンアップ、配布 |

### 自己改善ループ（配置後）

| スキル | 役割 |
|---|---|
| `skill-instrumenter` | 監視対象スキルへ自己観察ステップを注入（計装）/ 除去 |
| `skill-observer` | スキル実行結果の自己観察。問題があった場合のみ `evals/observations/observations.jsonl` に構造化ログを追記 |
| `skill-improver` | 蓄積ログの分析（Ingest → Inspect → Propose → Amend → Evaluate）。`.spec/` があるリポジトリでは直接修正せず spec-issue 起票 → 人間の裁定後に修正 |

## 標準フロー

```
skill-creator → skill-validator → skill-tester → skill-evaluator
      ↑                                              │
      └── 不合格なら skill-optimizer で改善して反復 ──┘
                        ↓ 合格
                  skill-packager（配置）
                        ↓
  skill-instrumenter（計装）→ 実運用 → skill-observer（観察ログ）
                        ↓
  skill-improver（分析・提案）→ .spec/spec-issues/ 起票 → 人間裁定 → 修正
```

- テスト成果物は `evals/<skill-name>/`（cases.md / runs/ / report.md）、
  観察ログは `evals/observations/observations.jsonl` に置く（生データ収集層）
- 改善は**提案と実装を分離**する: evals から導かれた改善提案は `.spec/spec-issues/` に
  起票し、人間が要件化（draft → approved）して初めて実装に進む（bitz-sdd の権限分離と接続）

## インストール

```
# Claude Code
/plugin marketplace add BitzLabs/BitzSkills
/plugin install skill-creator@bitzskills

# Antigravity 2.0
agy plugin install <このリポジトリ>/plugins/skill-creator

# OpenAI Codex CLI
codex plugin marketplace add BitzLabs/BitzSkills
codex plugin add skill-creator@bitzskills
```

## 使い方の例

- 「スキルを作って公開まで面倒を見てほしい」（→ `skill-pipeline` が工程を案内）
- 「PDF を処理する新しいスキルを作りたい」（→ `skill-creator`）
- 「skills/foo を検証して」（→ `skill-validator`）
- 「foo をテストして」→「結果を評価して」（→ `skill-tester` → `skill-evaluator`）
- 「このスキルに observer を追加して」（→ `skill-instrumenter`）
- 「溜まったフィードバックでスキルを改善して」（→ `skill-improver`）

## 規約（このプラグインが前提とするもの）

- SKILL.md の frontmatter 仕様は `skills/skill-creator/references/spec.md` が正
- 検査項目の正式な一覧は `skills/skill-validator/references/checklist.md`
- テスト成果物の書式は `skills/skill-tester/references/test-design.md`
- 観察ログの書式は `skills/skill-observer/references/observation-schema.md`
