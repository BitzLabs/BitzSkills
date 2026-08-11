---
implements: FLW-FR-004
depends_on: []
boundary: plugins/bitz-flow/skills/flow-core/scripts/flowlib/git_read_ext.py, tests/test_flow_m1_git_read_ext.py
status: pending
---

### 残るGit read operation（diff-detail・log・branches・conflicts・worktree list）

- **作業内容**: M0 で未実装だった Git read を `flowlib/git_read_ext.py` に実装する。
  出力 field の正は `FLW-DSN-005` の Read operations 表、共通規律は既存 read adapter に合わせる。

  | operation | Git 入力 | 既定出力 |
  |---|---|---|
  | `git.diff-detail` | `diff --no-ext-diff --unified=1` | 指定 path / hunk の変更行、snapshot |
  | `git.log` | `log --format` + NUL separator | short SHA、subject、author date、parents |
  | `git.branches` | `for-each-ref --format` | local / remote、SHA、upstream、ahead / behind |
  | `git.conflicts` | `diff --name-only --diff-filter=U -z` | conflict path 一覧 |
  | `worktree.list` | `worktree list --porcelain` | path、HEAD、branch、locked / prunable |

  - path は NUL 区切りを優先し、改行・空白・非 ASCII を含む filename を損なわない。
  - pager・color・external diff を無効化する（read adapter の共通 flags を共有する）。
  - `git.diff-detail` は最大 bytes / 最大 hunks を受け、**超過を明示**する。
    summary と detail の canonical bytes から snapshot fingerprint を計算し、
    呼出時の `--snapshot` と再計算値が違えば `STALE` を返す。
  - 失敗は許可語彙 cause へ正規化し、生の stderr を公開しない。

- **完了条件**: 実 Git リポジトリを使う単体テストが PASS すること。
  非 ASCII path・改行を含む path・binary・rename・conflict・detached HEAD・空リポジトリで
  出力が壊れないこと。`git.diff-detail` の上限超過が明示されること。
  snapshot 不一致で `STALE` になること。副作用が 0 であること。
  `.venv/bin/pytest -q` が全件 PASS すること。

- **備考**: **公開 operation を増やさない**（M2 未完了のため。`FLW-DSN-014` 縮退規則3）。
  dispatcher へ結線せず、内部 adapter の実装と検証にとどめる。
