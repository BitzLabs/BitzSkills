---
name: flow-core
description: BitzFlow のメインスキル。プロジェクト状況に応じた Git / GitHub 開発フローの選択（単独開発=feature ブランチ / 複数エージェント並列=worktree / チーム・公開開発=GitHub Issue 駆動 + PR）、Conventional Commits のコミット規定、失敗時の復元方針を規定する。ユーザーが「Git フロー」「ブランチ運用」「コミット規約」「開発フローを決めたい」「並列で開発したい」に言及したとき、または開発作業の開始時にフローが未確定のときに使用する。worktree の実手順は flow-worktree、Issue 駆動 PR の実手順は flow-pr が担当する。
metadata:
  version: "0.2.0"
  author: br7.hide
  created: "2026-07-18"
  updated: "2026-07-18"
---

# flow-core — Git / GitHub 開発フローの選択とコミット規約

プロジェクトの状況に合わせて開発フローを選び、コミット履歴の規律を保つためのスキルです。
SDD（仕様駆動開発）を採用していないプロジェクトでも単体で使えます
（bitz-sdd 併用時の接続点は末尾の節を参照）。

## フロー選択の判断表

| 状況 | フロー | 手順の詳細 |
|---|---|---|
| 単独開発（1人 / 1エージェント） | feature ブランチのみ | 本 SKILL.md で完結 |
| 複数エージェント並列 | **1エージェント = 1 worktree = 1ブランチ** | `flow-worktree` スキル |
| チーム開発・公開リポジトリでの開発 | GitHub Issue 駆動 + Draft PR + squash merge | `flow-pr` スキル |

## ブランチ規約（単独開発の最小規定）

- デフォルトブランチ（main 等）へ直接コミットしない。変更は必ず作業ブランチを切る
- ブランチ名は `<type>/<topic>`（例: `feat/user-auth`、`fix/timeout-retry`）。
  type はコミット規定の type と揃える
- マージは squash を基本とし「1 作業単位 = 1 コミット」を保つ

## コミットコメント規定

- **タイトル**: Conventional Commits — `<type>(<scope>): <説明>`
  （type: `feat` / `fix` / `docs` / `refactor` / `test` / `chore`、破壊的変更は `!`）。
  作業単位の ID（Issue 番号・チケット番号など）があればタイトルに含める
  （例: `feat(auth): [#123] トークン更新処理を実装`）
- **本文**: 変更の理由・影響範囲を記述する（日本語可）

## 同梱スクリプト（commit_lint.py）

コミット規定への適合は同梱の `scripts/commit_lint.py` で機械検査できる
（読み取り専用・Python 標準ライブラリのみ・スキル本文の読み込み不要。CI からも呼べる）:

```bash
python3 scripts/commit_lint.py --message "feat(auth): [#123] トークン更新を実装"   # 単一メッセージ
git log -1 --format=%B | python3 scripts/commit_lint.py --file -                  # 標準入力
python3 scripts/commit_lint.py --range origin/main..HEAD --require-implements     # 範囲検査（マージコミット除外）
```

- 終了コード: 適合 0 / 違反 1（`NG` 行で理由を表示）/ 使用法エラー 2
- `--require-task-id` でタイトルの作業 ID `[<ID>]`、`--require-implements` で
  `Implements:` フッター（bitz-sdd 併用時の規定）を追加検査できる

## 失敗時の復元 — 破棄してやり直す

- 作業が失敗したら、修復を試みず**作業ブランチ（worktree 併用時は worktree ごと）を
  破棄して作業単位を再投入**する。作業単位が小さく分割されていれば、やり直しで十分
- `git reset --hard` / `git push --force` / checkpoint 的な巻き戻し規定は**置かない**
  （破壊的操作のガードレールと衝突するため）。エージェント固有の巻き戻し機能
  （セッション内の即時 undo）は自由に使ってよいが、本スキルの規定対象外
- git 履歴は squash により「1 作業単位 = 1 コミット」を保つ

## bitz-sdd 併用時（SDD プロジェクトの接続点）

bitz-sdd を導入しているプロジェクトでは、次を上書き適用する:

- ブランチ規約・競合の構造的回避・権限マトリクスは sdd-core の references/parallel-git.md が**正**
  （本スキルの最小規定より優先する）
- コミットタイトルの作業単位 ID はタスク ID とする（例: `feat(domain): [TSK-042] 検証ロジックを実装`）
- 実装コミットには要件 ID を `Implements:` フッターで宣言し、タスクの `implements` 宣言と一致させる:

  ```
  feat(domain): [TSK-042] タスク完了時の検証ロジックを実装

  <本文（日本語可）>

  Implements: TODO-FR-012
  ```

- 並列投入の可否判定（depends_on 解決済み・boundary が互いに素）は sdd-implement が正
