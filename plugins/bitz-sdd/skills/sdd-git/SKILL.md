---
name: sdd-git
description: BitzSDD 利用プロジェクトの Git / GitHub 開発フローを規定・実行するスキル。状況に応じたフロー選択（単独開発=ブランチ / 複数エージェント並列=worktree / チーム・別リポジトリ開発=GitHub Issue 駆動 + PR）、worktree の作成・破棄・マージバック、コミットコメント規定（Conventional Commits + Implements フッター）、失敗時の復元（worktree 破棄 → タスク再投入）を扱う。ユーザーが「worktree」「並列で開発」「ブランチ運用」「コミット規約」「Issue 駆動」「PR フロー」「失敗したからやり直したい」に言及したとき、または sdd-implement で depends_on が空のタスク群を並列投入するときに使用する。
metadata:
  version: "0.1.0"
  author: br7.hide
  created: "2026-07-11"
  updated: "2026-07-11"
---

# SDD Git — Git / GitHub 開発フロー

BitzSDD の実装工程を支える Git 運用を規定します。
**ブランチ規約・競合の構造的回避・権限マトリクスは `sdd-core` の references/parallel-git.md が正**であり、
本スキルはそれを実行フローに拡張します（矛盾が出たら parallel-git.md 側の改訂として扱い、二重規定を作らない）。

## フロー選択の判断表

| 状況 | フロー | 手順の詳細 |
|---|---|---|
| 単独開発（1人 / 1エージェント） | feature ブランチのみ（`sdd-core` のブランチ規約どおり） | 本 SKILL.md で完結 |
| 複数エージェント並列 | **1エージェント = 1 worktree = 1ブランチ** | `references/worktree-operations.md` |
| チーム開発・別リポジトリでの開発 | GitHub Issue 駆動 + Draft PR + squash merge | `references/issue-driven-flow.md` |

## コミットコメント規定

- **タイトル**: Conventional Commits — `<type>(<scope>): <説明>`
  （type: `feat` / `fix` / `docs` / `refactor` / `test` / `chore`、破壊的変更は `!`）。
  タスク由来のコミットはタイトルにタスク ID を含める（例: `feat(domain): [TSK-042] 検証ロジックを実装`）
- **フッター**: 実装コミットには要件 ID を `Implements:` フッターで宣言する

  ```
  feat(domain): [TSK-042] タスク完了時の検証ロジックを実装

  <本文（日本語可）>

  Implements: TODO-FR-012
  ```

- フッターの要件 ID は `sdd-core` 同梱 `spec_inspect.py` の implements マップと突合可能にするためのもの。
  タスクの `implements` 宣言と一致させる（実装規律の詳細は `sdd-implement` が正）

## 失敗時の復元 — worktree 破棄に一本化

- タスクが失敗したら **worktree ごと破棄（`git worktree remove` + ブランチ削除）して
  タスクを再投入**する。タスクは `.spec/tasks/` で小さく分解されている前提なので、
  タスク単位のやり直しで十分
- `git reset --hard` / `git push --force` / checkpoint 的な巻き戻し規定は**置かない**
  （ガードレールと衝突するため）。エージェント固有の巻き戻し機能（セッション内の即時 undo）は
  自由に使ってよいが、本スキルの規定対象外
- git 履歴は squash により「1タスク = 1コミット」を保つ

## 工程内での位置づけ

- `sdd-implement` がタスク分解（depends_on / boundary）を終えた後、並列投入の実行手段として本スキルを使う
- 並列投入できるのは `depends_on` が解決済みかつ `boundary` が互いに素なタスク群のみ（判定は `sdd-implement` が正）
