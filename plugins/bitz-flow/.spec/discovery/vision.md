---
id: FLW-DSC-001
title: "bitz-flow v2 プロダクトビジョン"
status: draft
version: 2.0
updated: 2026-07-29
owner: hide
---

# bitz-flow v2 プロダクトビジョン

## Vision

Claude Code、OpenAI Codex CLI、Antigravity 2.0 のいずれを使っても、エージェントが
Git / GitHub のコマンド列を毎回即興で組み立てず、同じ入口・同じ安全判定・同じ圧縮出力で
開発作業を進められる状態を作る。

bitz-flow v2 は Git の別実装でも GitHub の汎用 API クライアントでもない。Git / `gh` CLI を
決定論的な実行エンジンとして使い、AI エージェント向けに次の不足を補う
「操作カーネル + 開発フロー」である。

1. 操作前提と入力を検証する。
2. 生出力を判断に必要な情報へ正規化する。
3. 状態変更を dry-run、明示実行、再照会の段階に分ける。
4. 中断後も外部状態から安全に再開する。
5. Git / GitHub / BitzSDD の責務境界を固定する。

## Target Group

- **主要**: Claude Code / Codex CLI / Antigravity 2.0 で GitHub リポジトリを開発する個人・
  小規模チーム。AI モデルが変わっても同じ操作品質を求める利用者。
- **主要**: 複数エージェントの並列作業を前提に、単独作業も worktree で隔離したい利用者。
- **二次**: BitzSDD を使い、`.spec` の裁定・要件・タスクと GitHub Issue / PR を
  二重管理せず接続したい利用者。
- **除外**: GitHub 以外の forge を主要な遠隔台帳として使うチーム、独自 Git 基盤を
  強制する大規模組織、Git / `gh` CLI を導入できない環境。

## Needs

- モデルごとに Git / `gh` のコマンド、例外処理、出力解釈が揺れる。
- SKILL.md にスクリプトと生コマンドの両方があると、エージェントが生コマンドを選び、
  スクリプトの安全判定と構造化出力を迂回する。
- `git status`、diff、PR、CI などの生出力が会話へ蓄積し、判断に不要なトークンを消費する。
- worktree の置き場所、命名、再開、完了後 cleanup、失敗時保全が毎回即興になる。
- `.spec/spec-issues`、requirements、tasks と GitHub Issue の役割が曖昧だと、
  どちらが正か分からない二重台帳になる。
- PR 作成から merge、release、CHANGELOG までの各段階が中断可能である一方、
  現行スキルには共通の再開状態機械がない。

## Product

v2 の利用者向け構成は次の2スキルとする。

| スキル | 責務 |
|---|---|
| `flow-core` | Git / GitHub の全通常操作と、worktree・Issue・PR・release のフローを扱う唯一の入口 |
| `flow-doctor` | Git / `gh` / Python / remote / 権限スコープを変更せず診断する独立ライフサイクルスキル |

`flow-core` はエージェントが直接実行する単一 dispatcher
`python3 scripts/flow.py <domain> <action>` を持つ。dispatcher の内部は Git 読取、Git 状態変更、
GitHub 読取、GitHub 状態変更、worktree、Issue、PR、release のモジュールへ分割する。
SKILL.md と workflow reference に通常経路の生 `git` / `gh` コマンドは掲載しない。

## Goals

- 同じ入力状態に対し、3プラットフォームで同じ判定コードと許可リスト出力を返す。
- 通常の Git / GitHub 作業で最初にdispatcherを使う割合を評価可能にし、95%以上を目標にする。
- 既定出力を生 CLI より大幅に小さくしながら、次の行動に必要な情報を欠落させない。
- 書込み作業は単独でも worktree を既定とし、後から並列化できる構造にする。
- GitHub Issue は実行・協調台帳、`.spec` は仕様・裁定の SSOT として役割を分ける。
- PR と release を一発自動化せず、再開可能な段階として決定論的に実行する。

## Non-goals

- Git / GitHub API の完全なラッパー。
- 任意の `git` / `gh api` を無検査で通す escape hatch。
- LLM の会話履歴そのものを圧縮・削除するコンテキスト管理システム。
- プロジェクト固有の version bump、ビルド、署名、配布処理を汎用スクリプトが推測して実行すること。

## PR-FAQ 圧力試験

### なぜスキルを細かく分けないのか

現行は `flow-core`、`flow-worktree`、`flow-pr` に操作手順とスクリプトが分散し、発動した
スキルによってスクリプトを使うか生コマンドを使うかが変わる。利用者向け入口を1つにし、
内部実装だけを分割する方が、実行率と出力契約を揃えやすい。

### なぜ worktree を単独作業にも使うのか

共有 checkout を変更しないため、途中から別エージェントを追加でき、失敗した作業を
既定ブランチから物理的に隔離できる。作成コストより並列可能性と復旧容易性を優先する。

### 何をもって「均一」とするのか

モデルの説明文が同一であることではなく、同一 fixture に対する dispatcher の
終了コード、判定、許可リスト JSON、状態変更の有無が一致することを意味する。
