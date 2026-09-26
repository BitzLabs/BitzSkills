# AGENTS.md — BitzSkills 共通ルール

このファイルが全エージェント（Claude Code / Codex / Antigravity）共通ルールの唯一の正。
Claude Code は `CLAUDE.md` のインポート経由で、Codex と Antigravity は本ファイルを直接読む。

## リポジトリの役割

BitzSkills 2 系の開発リポジトリ。現在は Core 1.0（CLI `bitz`: doctor / context / check / verify、
要件記述言語 EARS-AI）を、ADR と適合 fixture で仕様を先に固めてから実装している。

- 計画の正本: `docs/04.提案資料/12_Core-1.0実装計画.md`
- 決定記録: `docs/02.設計書/10_決定記録/ADR-*.md`
- 用語: `docs/用語集.md`
- 前バージョン（1 系: bitz-sdd / bitz-flow ほか）はブランチ `archive/v1`・tag `v1-final` に凍結している。
  参照は読み取りのみとし、1 系のルール・スクリプトをこのリポジトリへ持ち込まない

## 構成

```
docs/                # 検討資料・設計書・詳細設計・提案資料（規範の正）
fixtures/            # 適合 fixture と参照適合 harness（Core に依存しない。ADR-049）
plugins/bitz-core/   # Core 1.0 の実装（uv project、CPython 3.12 以上）
tests/bitz-core/     # Core の単体試験と Gate B 認定
.spec/               # bitz-core 自身の要件・タスク（自己適用）
```

## ガードレール

### 禁止（実行しない）

- `rm -rf` / `git push --force` / `git reset --hard` / `git clean -f` / `sudo`
- `main` への直接コミット（変更時は必ずブランチを切る）
- 認証情報・トークン類（`~/.claude/.credentials.json`・`.env` 等）の読み取り・出力

### 事前確認が必要（ユーザーの明示承認なしに実行しない）

- リポジトリ外への書き込み・上書き・削除
- `git push`（外部公開）
- 承認済み（`approved`）要件の意味の変更。変更するときは先に `draft` へ戻す

### 検証義務

- 他エージェントの「成功しました」という自己申告を信用せず、下記の検証コマンドを自分で再実行する
- Step の完了判定・Gate 判定・是正後の「解消済み」判定は、作業者と独立したコンテキストで検分する
  （自己レビューは甘く出る）

## 検証コマンド

| 目的 | コマンド |
|---|---|
| 適合 fixture の監査 | `uv run fixtures/validate_conformance.py`（exit 1 と pending 1 件が正常） |
| Core の適合試験 | `uv run fixtures/run_conformance.py --core plugins/bitz-core --step N` |
| Core の単体試験 | `uv run --project plugins/bitz-core python tests/bitz-core/run_test_files.py tests/bitz-core/test_*.py` |
| Gate A 認定 | `uv run fixtures/certify_gate_a.py`（clean tree 必須） |
| Gate B 認定 | `uv run tests/bitz-core/certify_gate_b.py --step N`（clean tree 必須） |

- fixture を変更したら Gate A を再認定する（ADR-051）
- 対象環境は Linux / macOS、CPython 3.12 以上（ADR-053 / ADR-055）

## 並行開発

メインの作業ツリーは共有され、worktree が同時に動く前提で作業する。

- ブランチは `origin/main` から明示的に切る: `git checkout -b <name> origin/main`
- `git add -A` と広いパス指定を使わない。自分が触れたファイルだけを個別に指定する
- コミット直前に `git diff --cached --name-only` を確認し、関心事以外のファイルを除く
- 成果物へ記録する事実（件数・hash 等）は、作業ツリーではなく確定した ref か clean な状態で測る

## コミット・PR 規約

- **コミットタイトル**: `<type>: <説明>`。type は `feat` / `fix` / `spec` / `test` / `docs` / `chore`
  （`spec` は規範文書・ADR の変更）。説明は日本語で、何をするかを文で書く
- **fixture の変更と Core の実装は別コミットにする**
- **PR の統合は rebase merge**。squash merge は上の規則を崩すため使わない
- **1 PR = 1 関心事**。PR 本文には目的・変更点・検証結果（上記コマンドの実出力）を含める
