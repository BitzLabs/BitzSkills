---
name: flow-pr
description: BitzFlow の GitHub Issue 駆動 PR フロースキル。Issue 起票 → feature ブランチ → Draft PR → CI ゲート → レビュー → squash merge の基本フロー、PR タイトル規約、未マージ依存の原則（スタック PR の禁止と例外時の安全手順）を規定する。ユーザーが「Issue 駆動」「PR フロー」「Draft PR」「squash merge」「プルリクの運用」「スタック PR」に言及したとき、またはチーム開発・公開リポジトリでの開発フローが必要になったときに使用する。フロー全体の選択とコミット規約は flow-core、worktree 並列は flow-worktree が担当する。
metadata:
  version: "0.1.0"
  author: br7.hide
  created: "2026-07-18"
  updated: "2026-07-18"
---

# flow-pr — GitHub Issue 駆動フロー

チーム開発や公開リポジトリでの開発では、GitHub Issue を作業単位の公開台帳として使う。

## 基本フロー

```
Issue 起票 → feat/<issue#>-<slug> ブランチ → Draft PR → CI ゲート
  → レビュー → squash merge → Issue 自動クローズ（Closes #N）
```

### 1. Issue 起票

- 1 Issue = 1 関心事（`git revert` で丸ごと戻せる粒度）。実装 Issue は対象の
  仕様・チケットへの参照を本文に明記する

### 2. ブランチと Draft PR

- ブランチ名: `feat/<issue#>-<slug>`（例: `feat/123-task-completion-validation`）。
  type が fix / docs 等なら接頭辞も合わせる（flow-core のコミット規定と揃える）
- 着手したら早めに **Draft PR** を開く（進行の可視化と CI の早期実行）。
  PR 本文の末尾に `Closes #<issue#>` を入れ、マージで Issue が自動クローズされるようにする

### 3. CI ゲートとレビュー

- CI にはプロジェクトのテストとリリース前検証を組み込む
- PR タイトルは Conventional Commits 準拠（squash merge でそのままマージコミットの
  タイトルになるため）。タイトル検査を CI に置くことを推奨
- PR 本文には目的 / 変更点 / 検証結果（テスト・機械チェックの実出力）を含める

### 4. squash merge

- **squash merge に統一**し「1 Issue（1 作業単位）= 1 コミット」を保つ
- マージコミットのタイトル = PR タイトル（Conventional Commits 準拠を CI で担保）

## 未マージ依存の原則 — 前提を先に land する

着手対象の作業が「**まだデフォルトブランチにマージされていない別 PR**」に依存する場合、
**依存先 PR を先に land し、更新後のデフォルトブランチからブランチを切る**のを既定とする。
本フローは「1 PR = デフォルトブランチ分岐 = squash merge」のフラット構成を前提にしており、
この前提を崩さない。

- **やってはいけない**: 未マージ PR のブランチを base にした**スタック PR** を安易に作ること。
  上段 PR をブランチ削除付きでマージ（`gh pr merge --delete-branch` 等）すると base ブランチが
  消え、下段 PR は retarget されず **GitHub により自動クローズ**される
- **どうしてもスタックが必要な例外時**:
  - 上段マージ時に **`--delete-branch` を付けない**（下段が巻き添えで close される）
  - 上段マージ後は下段を **デフォルトブランチへ retarget
    （`git rebase --onto origin/main <旧base先頭>`）** してから独立にマージする
  - force-push はガードレール対象。履歴書き換えが要るなら**新ブランチ＋新 PR** で出し直す方が安全
- 依存が未マージのままの作業は並列投入の対象にしない（先に依存を land し終えるのを待つ）

## worktree 運用との組み合わせ

複数エージェントで並列に Issue を消化する場合は、flow-worktree の運用をそのまま重ねる:
1 Issue = 1 worktree = 1ブランチ = 1 Draft PR。失敗時は worktree ごと破棄し、
Draft PR をクローズして Issue に失敗理由をコメントしてから再投入する。

## bitz-sdd 併用時（SDD プロジェクトの接続点）

- `.spec/spec-issues/` 由来の変更提案を GitHub Issue にする場合は、
  **spec-issue ファイル側に Issue URL を記録**して双方向に辿れるようにする:

  ```yaml
  # .spec/spec-issues/SI-012.md の frontmatter に追記
  github_issue: https://github.com/<org>/<repo>/issues/123
  ```

- CI の機械検証に BitzSDD の `spec_inspect.py`（あれば docs 側の `docs_inspect.py`）を組み込む
- レビューで要件・契約レベルの問題が見つかったら、PR 上で直さず
  `.spec/spec-issues/` に起票して人間の裁定に回す（権限マトリクスどおり）
- マージコミットのフッターに `Implements: <要件ID>` を残す（spec_inspect.py の
  implements マップと突合するため。書式は flow-core の併用節）
- `.spec` と GitHub の対応表:

| .spec 側 | GitHub 側 | 対応付け |
|---|---|---|
| `.spec/spec-issues/SI-*.md` | Issue | SI ファイルの frontmatter `github_issue:` に URL を記録 |
| `.spec/tasks/TSK-*.md` | Draft PR（実装単位） | PR 本文にタスク ID、フッターに `Implements:` |
| `.spec/requirements/*-FR-*.md` | — （GitHub には置かない） | 要件の正は常に `.spec/`。Issue は作業台帳であって仕様の置き場ではない |
