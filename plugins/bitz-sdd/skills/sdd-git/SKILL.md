---
name: sdd-git
description: BitzSDD 利用プロジェクトの Git / GitHub 開発フローの入口スキル（薄い委譲ポインタ）。フロー選択（単独開発=ブランチ / 複数エージェント並列=worktree / チーム・別リポジトリ開発=GitHub Issue 駆動 + PR）の判断表と、SDD 固有の接続点（コミットの Implements フッター、.spec/tasks のタスク並列投入条件、失敗時の worktree 破棄復元）だけを規定し、実行手順の正は bitz-flow プラグイン（flow-core / flow-worktree / flow-pr）に委譲する。ユーザーが「worktree」「並列で開発」「ブランチ運用」「コミット規約」「Issue 駆動」「PR フロー」「失敗したからやり直したい」に言及したとき、または sdd-implement で depends_on が空のタスク群を並列投入するときに使用する。
metadata:
  version: "0.3.0"
  author: br7.hide
  created: "2026-07-11"
  updated: "2026-07-18"
---

# SDD Git — Git フローの入口（正は bitz-flow）

Git / GitHub 開発フローの**実行手順の正は bitz-flow プラグイン**
（`flow-core` / `flow-worktree` / `flow-pr`。bitz-sdd はマニフェストで bitz-flow に依存を宣言している）。
本スキルはフロー選択の判断表と **SDD 固有の接続点**だけを規定する薄い委譲ポインタであり、
ここに実行手順を書き足さない（二重規定を作らない）。
**ブランチ規約・競合の構造的回避・権限マトリクスは `sdd-core` の references/parallel-git.md が正**。

## フロー選択の判断表

| 状況 | フロー | 実行手順の正 |
|---|---|---|
| 単独開発（1人 / 1エージェント） | feature ブランチのみ | bitz-flow の `flow-core` |
| 複数エージェント並列 | **1エージェント = 1 worktree = 1ブランチ** | bitz-flow の `flow-worktree`（定型操作は同梱 worktree_ops.py） |
| チーム開発・別リポジトリでの開発 | GitHub Issue 駆動 + Draft PR + squash merge | bitz-flow の `flow-pr` |

各 flow スキルの「bitz-sdd 併用時」節が SDD プロジェクト向けの上書き規定
（task/<task-id> ブランチ名・spec-issue ⇔ Issue 対応表・CI への spec_inspect 組み込み）を含む。

## SDD 固有の接続点

### コミットの Implements フッター（公開契約）

実装コミットはタイトルにタスク ID、フッターに要件 ID を宣言する
（`spec_inspect.py` の implements マップと突合するため。タスクの `implements` 宣言と一致させる）:

```
feat(domain): [TSK-042] タスク完了時の検証ロジックを実装

<本文（日本語可）>

Implements: TODO-FR-012
```

適合検査は bitz-flow の flow-core 同梱 `commit_lint.py`（`--require-task-id --require-implements`）で行える。

### タスク並列投入の条件

並列投入できるのは `.spec/tasks/` で `depends_on` が解決済みかつ `boundary` が互いに素な
タスク群のみ（判定は `sdd-implement` が正）。エージェントの書き込みはタスクの `boundary` +
テストディレクトリ + STATE.md 追記に限る（権限マトリクスどおり）。

### 失敗時の復元 — worktree 破棄に一本化

タスクが失敗したら worktree ごと破棄してタスクを再投入する（手順は flow-worktree の正のとおり。
`git reset --hard` / `git push --force` 等の巻き戻し規定は置かない）。失敗が反復するなら
タスク粒度か要件の問題 — `sdd-core` の failure-protocol に従い spec-issue へエスカレーションする。
