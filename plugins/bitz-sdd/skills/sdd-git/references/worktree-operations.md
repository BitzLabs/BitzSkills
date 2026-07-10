# worktree 運用 — 複数エージェント並列の分離手段

複数エージェントを並列で走らせるときの原則は **1エージェント = 1 worktree = 1ブランチ**。
共有チェックアウトへの同時書き込みは禁止する（インデックス・作業ツリーの競合は
`boundary` 宣言では防げないため、物理的に分離する）。

## 前提

- 並列投入の対象は `.spec/tasks/` で `depends_on` が解決済み、かつ `boundary` が互いに素なタスク群
  （判定規準は `sdd-implement` の task-decomposition が正。スコープ・権限は `sdd-core` の parallel-git.md が正）
- worktree の置き場所はリポジトリ**外**の兄弟ディレクトリに統一する（リポジトリ内に作ると
  ツール類の走査対象に混入する）。命名: `../<repo>-wt/<task-id>/`

## 定型手順

### 1. 作成（タスク投入時）

```bash
# タスク TSK-042 用の worktree とブランチを作成（起点は最新 main）
git fetch origin
git worktree add ../<repo>-wt/TSK-042 -b task/TSK-042 origin/main
```

- ブランチ名は `task/<task-id>`。feature 単位でまとめる場合は `feat/<feature>/<task-id>`
- エージェントには worktree のパスを作業ディレクトリとして渡し、
  書き込みはタスクの `boundary` + テストディレクトリ + STATE.md 追記に限る（権限マトリクスどおり）

### 2. マージバック（タスク完了時）

```bash
cd ../<repo>-wt/TSK-042
# 検証（テスト・spec_inspect の implements 突合）が green であることを確認してから
git push origin task/TSK-042
# PR を作成し squash merge（1タスク = 1コミット。タイトルは Conventional Commits + [TSK-042]）
```

- squash merge により、途中の試行錯誤コミットは履歴に残さない
- マージコミットのフッターに `Implements: <要件ID>` を含める（SKILL.md のコミット規定どおり）
- `_index.md` / `inspection-report.md` 等の自動生成物が競合したら手マージせず**再生成で解決**
  （parallel-git.md の規定どおり）

### 3. 後片付け（マージ後）

```bash
git worktree remove ../<repo>-wt/TSK-042
git branch -d task/TSK-042          # マージ済みなので -d で消える
git push origin --delete task/TSK-042
```

### 4. 失敗時の復元（checkpoint は使わない）

タスクが失敗した（検証 red が解消しない・境界violation・暴走）場合は、**修復を試みずに破棄して再投入**する:

```bash
git worktree remove --force ../<repo>-wt/TSK-042   # 未コミットの変更ごと破棄
git branch -D task/TSK-042                          # マージしていないので -D
```

- main 側には何も影響がない（worktree 内の変更は隔離されている）ため、
  `git reset --hard` も `git push --force` も**一切不要**（ガードレールとも衝突しない）
- 再投入時はタスク定義（`.spec/tasks/`）を見直してから新しい worktree を作り直す。
  同じ失敗を繰り返す場合はタスクの粒度か要件に問題がある — `sdd-core` の failure-protocol に従い
  spec-issue へエスカレーションする

## 並列度の管理

- 同時に走らせる worktree 数はコスト予算（parallel-git.md の feature 単位予算）と
  マシン資源から決める。目安は 5〜6 まで
- `boundary` が重複するタスクは同時投入しない（`sdd-implement` の判定規準）。
  重複が判明したら片方を保留キューに戻して直列化する
