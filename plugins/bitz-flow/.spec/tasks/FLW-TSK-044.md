---
implements: FLW-FR-005, FLW-CON-005, FLW-CON-006
depends_on: [FLW-TSK-043]
boundary: plugins/bitz-flow/skills/flow-core/scripts/flowlib/git_publish.py, tests/test_flow_m1_git_publish.py
status: pending
---

### git.publish-branch / delete-remote-branchとREC-PUSH

- **作業内容**: `flowlib/git_publish.py` に remote-write の plan / apply / reconcile を実装する。

  - **`git.publish-branch`**: force なし push。plan は remote・branch・**expected HEAD**・upstream を返す。
    apply 直前に remote ref を**再照会**し、expected HEAD と一致した場合だけ push する。
    canonical mutation target は **repository ID + remote branch ref**（local identity を混ぜない）。
  - **`git.delete-remote-branch`**: **独立 operation**とし、finish / merge へ自動連結しない。
    exact ref だけを削除し、**expected remote SHA を再照会**して一致した場合だけ実行する。
    `approval` は `explicit-human`（`FLW-CON-005`）。
  - **REC-PUSH**: remote ref が expected と違えば `STALE` とし、**remote ref 全件の再照会と新 plan**へ導く。
    **force / update の再実行を next action にしない**。応答喪失時は `BLOCKED` とし、
    成否を推定しない（remote の CAS 結果を確認できない限り `INDETERMINATE`）。
  - **remote CAS を提供できない platform では publish を `UNSUPPORTED`** とする。
  - 禁止 command（force push・`reset --hard`・`clean -f`）は実装せず、
    診断・next action にも現れないこと（`FLW-CON-006`）。

- **完了条件**: ローカル bare リポジトリを remote に見立てた単体テストが PASS し、
  次が確認できること — expected HEAD 不一致で副作用 0 の `STALE`、
  delete が exact ref 以外を消さないこと、expected remote SHA 不一致で削除しないこと、
  応答喪失時に成否を推定しないこと、force push が実装にも next action にも現れないこと、
  remote CAS 非対応で `UNSUPPORTED` になること。
  `.venv/bin/pytest -q` が全件 PASS すること。

- **備考**: **公開 operation を増やさない**（M2 未完了のため）。実 GitHub へは接続せず、
  ローカル bare リポジトリで検証する。実接続は M1-6 confirmation が扱う。
