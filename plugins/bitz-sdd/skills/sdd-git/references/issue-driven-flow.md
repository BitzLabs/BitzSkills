# GitHub Issue 駆動フロー — チーム・別リポジトリ開発

別リポジトリでの開発やチーム開発では、GitHub Issue を作業単位の公開台帳として使い、
`.spec/` の仕様管理と対応付ける。

## 基本フロー

```
Issue 起票 → feat/<issue#>-<slug> ブランチ → Draft PR → CI ゲート
  → レビュー → squash merge → Issue 自動クローズ（Closes #N）
```

### 1. Issue 起票

- 1 Issue = 1 関心事（`git revert` で丸ごと戻せる粒度）。実装 Issue は対象の要件 ID /
  タスク ID を本文に明記する
- `.spec/spec-issues/` 由来の変更提案を GitHub Issue にする場合は、
  **spec-issue ファイル側に Issue URL を記録**して双方向に辿れるようにする:

  ```yaml
  # .spec/spec-issues/SI-012.md の frontmatter に追記
  github_issue: https://github.com/<org>/<repo>/issues/123
  ```

### 2. ブランチと Draft PR

- ブランチ名: `feat/<issue#>-<slug>`（例: `feat/123-task-completion-validation`）。
  type が fix / docs 等なら接頭辞も合わせる
- 着手したら早めに **Draft PR** を開く（進行の可視化と CI の早期実行）。
  PR 本文の末尾に `Closes #<issue#>` を入れ、マージで Issue が自動クローズされるようにする

### 3. CI ゲートとレビュー

- CI にはプロジェクトのテストに加えて、BitzSDD の機械検証
  （`spec_inspect.py`、あれば docs 側の `docs_inspect.py`）を組み込む
- PR タイトルは Conventional Commits 準拠（squash merge でそのままマージコミットの
  タイトルになるため）。タイトル検査を CI に置くことを推奨
- レビューで要件・契約レベルの問題が見つかったら、PR 上で直さず
  `.spec/spec-issues/` に起票して人間の裁定に回す（権限マトリクスどおり）

### 4. squash merge

- **squash merge に統一**し「1 Issue（1タスク）= 1コミット」を保つ
- マージコミットのフッターに `Implements: <要件ID>` を残す（`spec_inspect.py` の
  implements マップと突合するため。書式は SKILL.md のコミット規定）

## worktree 運用との組み合わせ

複数エージェントで並列に Issue を消化する場合は、worktree 運用（references/worktree-operations.md）を
そのまま重ねる: 1 Issue = 1 worktree = 1ブランチ = 1 Draft PR。失敗時は worktree ごと破棄し、
Draft PR をクローズして Issue に失敗理由をコメントしてから再投入する。

## .spec と GitHub の対応表

| .spec 側 | GitHub 側 | 対応付け |
|---|---|---|
| `.spec/spec-issues/SI-*.md` | Issue | SI ファイルの frontmatter `github_issue:` に URL を記録 |
| `.spec/tasks/TSK-*.md` | Draft PR（実装単位） | PR 本文にタスク ID、フッターに `Implements:` |
| `.spec/requirements/*-FR-*.md` | — （GitHub には置かない） | 要件の正は常に `.spec/`。Issue は作業台帳であって仕様の置き場ではない |
