---
implements: FLW-FR-004, FLW-FR-005, FLW-NFR-003
depends_on: [FLW-TSK-042]
boundary: plugins/bitz-flow/skills/flow-core/scripts/flowlib/git_sync.py, tests/test_flow_m1_git_sync.py
status: pending
---

### git.fetch / git.syncとREC-FETCH・REC-SYNC

- **作業内容**: `flowlib/git_sync.py` に `git.fetch` と `git.sync` の plan / apply / reconcile を実装する。

  - **`git.fetch`**: 明示した remote だけを fetch する。canonical mutation target は
    common-dir の **remote-tracking ref 集合と `FETCH_HEAD`**。
    plan は remote・refspec・prune 有無を返し、apply 後に更新された ref 集合と鮮度証跡を返す。
  - **REC-FETCH**: ref 集合の一部だけが更新された場合は `PARTIAL` とし、
    **completed / remaining の ref 集合を確定**する。**fetch の再実行を next action にしない**。
  - **`git.sync`**: fetch 後に `merge --ff-only`。canonical mutation target は
    **branch ref・index・remote-tracking ref 集合の複数**で、target guard は canonical 昇順で取得する。
  - **REC-SYNC**: fetch 済み・branch 未更新の状態は `PARTIAL` とし、
    `completed=fetch` / `remaining=branch-update` を提示する。**自動で branch を更新しない**。
    fast-forward できない場合は `non-fast-forward` cause で停止し、merge / rebase を代替提示しない。

- **完了条件**: 実 Git リポジトリ（ローカル bare を remote に見立てる）を使う単体テストが PASS し、
  次が確認できること — plan の副作用が 0、ref 集合の一部更新で `PARTIAL` と completed / remaining が
  確定すること、fetch 済み・branch 未更新で自動 branch 更新をしないこと、
  non-fast-forward で停止し代替を提示しないこと、複数 target が canonical 昇順で取得されること。
  `.venv/bin/pytest -q` が全件 PASS すること。

- **備考**: **公開 operation を増やさない**（M2 未完了のため）。外部ネットワークへ接続せず、
  ローカル bare リポジトリを remote として検証する。
