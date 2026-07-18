---
name: flow-worktree
description: BitzFlow の worktree 並列運用スキル。複数エージェント（または複数作業）を並列で走らせるときの「1エージェント = 1 worktree = 1ブランチ」原則と、worktree の作成・マージバック・後片付け・失敗時破棄の定型手順を規定する。ユーザーが「worktree」「並列で開発」「複数エージェントで作業」「失敗したからやり直したい」に言及したとき、または並列作業の分離手段が必要になったときに使用する。フロー全体の選択とコミット規約は flow-core、Issue 駆動 PR は flow-pr が担当する。
metadata:
  version: "0.2.1"
  author: br7.hide
  created: "2026-07-18"
  updated: "2026-07-18"
---

# flow-worktree — worktree による並列開発の分離

複数エージェントを並列で走らせるときの原則は **1エージェント = 1 worktree = 1ブランチ**。
共有チェックアウトへの同時書き込みは禁止する（インデックス・作業ツリーの競合は
書き込み範囲の取り決めでは防げないため、物理的に分離する）。

## 前提

- 並列投入するのは**依存が解決済みで、書き込み範囲が互いに重ならない**作業単位のみ。
  重なる作業は同時投入せず直列化する
- worktree の置き場所はリポジトリ**外**の兄弟ディレクトリに統一する（リポジトリ内に作ると
  ツール類の走査対象に混入する）。命名: `../<repo>-wt/<作業ID>/`

## 定型手順

### 1. 作成（作業投入時）

```bash
# 作業 #123 用の worktree とブランチを作成（起点は最新のデフォルトブランチ）
git fetch origin
git worktree add ../<repo>-wt/123 -b feat/123-topic origin/main
```

- ブランチ名は flow-core の規約どおり `<type>/<作業ID>-<slug>` 等で統一する
- エージェントには worktree のパスを作業ディレクトリとして渡し、
  書き込みはその作業単位の範囲（対象ファイル + テスト）に限る

### 2. マージバック（作業完了時）

```bash
cd ../<repo>-wt/123
# 検証（テスト・機械チェック）が green であることを確認してから
git push origin feat/123-topic
# PR を作成し squash merge（1 作業単位 = 1 コミット。タイトルは Conventional Commits）
```

- squash merge により、途中の試行錯誤コミットは履歴に残さない
- 自動生成物（インデックス・レポート類）が競合したら手マージせず**再生成で解決**する

### 3. 後片付け（マージ後）

PR を squash merge した場合、元ブランチのコミットはデフォルトブランチの祖先にならない。
そのため通常の `git branch -d` 成否をマージ証跡にせず、PR 番号を指定した guarded cleanup を使う。

```bash
python3 scripts/worktree_ops.py cleanup 123 \
  --branch feat/123-topic --squash-pr 456 --default-branch main \
  --execute --yes
```

- GitHub の PR state が `MERGED` であること、PR の最終 head SHA が存在する
  worktree / local / remote ref と一致すること、merge commit が `origin/<default>` から到達可能なことを
  削除操作より先に検査する。照会失敗や不一致では何も削除せず停止する
- worktree 除去済み・local branch 残存、または両方除去済みの再実行を状態から判定し、
  完了済み段階を skip して前進再開する。削除済み ref は再生成しない
- remote branch は自動削除しない。prune 後に実在と期待 SHA を確認し、同じ場合だけ
  検査時刻・期待 SHA・直前再照会の警告を持つ削除候補として報告する。削除コマンド自体も生成しない
- JSON 監査出力が必要なら `--json`、外部コマンドの上限時間は
  `--timeout-seconds 1..300`、任意の非機密ラベルは `--actor` で指定する

非 squash merge の互換経路では、従来どおり `cleanup`（`--squash-pr` なし）が
`worktree remove` と `git branch -d` を使う。remote 削除オプションもこの経路にだけ残す。

### 4. 失敗時の復元（checkpoint は使わない）

作業が失敗した（検証 red が解消しない・範囲逸脱・暴走）場合は、**修復を試みずに破棄して再投入**する:

```bash
git worktree remove --force ../<repo>-wt/123   # 未コミットの変更ごと破棄
git branch -D feat/123-topic                    # マージしていないので -D
```

- デフォルトブランチ側には何も影響がない（worktree 内の変更は隔離されている）ため、
  `git reset --hard` も `git push --force` も**一切不要**（ガードレールとも衝突しない）
- 再投入時は作業単位の定義を見直してから新しい worktree を作り直す。
  同じ失敗を繰り返す場合は作業の粒度か前提に問題がある — 分割し直すか人間に相談する

## 同梱スクリプト（worktree_ops.py）

上記1〜4の定型手順は同梱の `scripts/worktree_ops.py` で決定的に実行できる
（Python 標準ライブラリのみ・スキル本文の読み込み不要。本文は「いつ・何を」の判断を担い、
コマンド列の組み立てはスクリプトに固定する）:

```bash
python3 scripts/worktree_ops.py add 123 --branch feat/123-topic          # 既定は dry-run（表示のみ）
python3 scripts/worktree_ops.py add 123 --branch feat/123-topic --execute
python3 scripts/worktree_ops.py list
python3 scripts/worktree_ops.py cleanup 123 --branch feat/123-topic --squash-pr 456 --execute --yes
python3 scripts/worktree_ops.py discard 123 --branch feat/123-topic --execute --yes
```

- 状態変更系（add / cleanup / discard）は**既定で dry-run**。`--execute` で実行し、
  破棄・削除を伴う cleanup / discard はさらに `--yes` が無ければ何も実行しない（終了コード 2）
- squash cleanup は `--delete-remote` と併用できない。GitHub 証跡を取得できない、または
  SHA・到達性・worktree 境界を確認できない場合は INDETERMINATE として安全側停止する
- ガードレール禁止操作（`git reset --hard` / `git push --force` 等）は実装に含まれない

## 並列度の管理

- 同時に走らせる worktree 数はコスト予算とマシン資源から決める。目安は 5〜6 まで
- 書き込み範囲が重複する作業は同時投入しない。重複が判明したら片方を保留キューに戻して直列化する

## bitz-sdd 併用時（SDD プロジェクトの接続点）

- 並列投入の対象は `.spec/tasks/` で `depends_on` が解決済み、かつ `boundary` が互いに素な
  タスク群（判定規準は sdd-implement の task-decomposition が正。スコープ・権限は
  sdd-core の parallel-git.md が正）
- 作業 ID はタスク ID（例: `TSK-042`）、ブランチ名は `task/<task-id>` とする
- エージェントの書き込みはタスクの `boundary` + テストディレクトリ + STATE.md 追記に限る
  （権限マトリクスどおり）
- マージコミットのフッターに `Implements: <要件ID>` を含める（flow-core の併用節どおり）
- 失敗の反復はタスク粒度か要件の問題 — sdd-core の failure-protocol に従い spec-issue へ
  エスカレーションする
