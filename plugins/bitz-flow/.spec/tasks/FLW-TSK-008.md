---
implements: FLW-FR-004
depends_on: [FLW-TSK-005, FLW-TSK-006]
boundary: plugins/bitz-flow/skills/flow-core/scripts/flowlib/git_read.py
status: done
---

### M0 Git read adapter の実装（machine-readable 出力の parse）

- **作業内容**: FLW-DSN-005 の Read operations 表に従い `flowlib/git_read.py` を実装する。
  M0 が扱うのは次の3経路だけとする。

  | 用途 | Git 入力 | 出力 |
  |---|---|---|
  | repo inspect | `rev-parse`、`status --porcelain=v2 --branch -z` | root、HEAD、branch、upstream、dirty、remote |
  | git status | `status --porcelain=v2 --branch -z` | XY、path、rename、ahead / behind、件数 |
  | git diff-summary | `diff --name-status -z`、`diff --numstat -z` | path、kind、added / deleted、binary |

  path は NUL 区切りを優先し、改行・空白・非 ASCII を含む filename を損なわない。
  Git config による pager・color・external diff を無効化して実行する。
  外部プロセスの実行は必ず FLW-TSK-006 の process runner を経由し、`subprocess` を直接呼ばない。
  読取は暗黙の fetch や ref 更新を行わない（`git.fetch` は M1 の独立 operation）。
  Git command・parse・timeout・path 検証のどの stage で失敗したかを区別し、
  許可語彙 cause と併せて返す。
  repo root は副作用前に canonical 検証する。
- **完了条件**: dirty、rename、binary、conflict、detached HEAD、非 ASCII path、
  空リポジトリ、不正出力の各 fixture を parse できること。read 経路が状態変更を一切行わないこと。
  adapter が result object や renderer に依存しないこと（依存方向は adapters → process runner）。
- **備考**: FLW-FR-004 のうち `git.diff-detail`・`git.fetch`・`git.log`・`git.branches`・
  `git.conflicts` は M1 の担当であり本タスクで実装しない（FLW-DSN-012 の milestone allocation）。
  要件は M1 完了まで implementing のまま保持される。
