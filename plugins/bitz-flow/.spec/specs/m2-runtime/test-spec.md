# M2 worktree実動統合テスト仕様

### FLW-FR-006 worktree-first lifecycle

- **導出元種別**: Event-Driven / State-Driven
- **Verification Method**: unit-test
- **テスト**: 実tmp repositoryでcreate/resume/finish/discardをdispatcher/runtime経由で実行し、
  worktree、branch、retention ref、receiptのpostconditionを再観測する。

### FLW-CON-005 explicit human approval

- **導出元種別**: Unwanted Behavior
- **Verification Method**: unit-test
- **テスト**: capability署名不正、operation ID不一致、nonce再利用、trusted key registry不正を
  最初のGit副作用前に拒否する。

### FLW-CON-006 destructive boundary

- **導出元種別**: Unwanted Behavior
- **Verification Method**: unit-test
- **テスト**: discardはtip retention後だけ除去し、fault injectionはreceipt prefixとnonceを
  quarantineへ確定して自動再実行しない。

### FLW-NFR-012 mutation境界の例外分類（SI-FLW-057）

- **導出元種別**: Unwanted Behavior
- **Verification Method**: unit-test
- **テスト**: 副作用適用後に素の `ValueError` / `KeyError` が起きたとき、`BLOCKED`（副作用前に停止）
  ではなく `PARTIAL` を返し、completed steps を伴うこと。旧実装で落ちる陽性対照を同梱する。
- **テスト**: `create` / `resume` の receipt が cleanup 核の step 列の真の前置として
  reconcile できること。未知 operation は既定へ倒さず `INDETERMINATE` にすること。

### FLW-FR-007 公開dispatcher経由のworktree検証（SI-FLW-059）

- **導出元種別**: Event-Driven / Unwanted Behavior
- **Verification Method**: unit-test
- **テスト**: fixture が `{**_HANDLERS, **_GATED_HANDLERS}` を注入し、`create` → `resume` を
  公開経路の plan/apply で通して実 worktree の postcondition を再観測する。
- **テスト**: confirm 不一致・承認の使い回し・confirm 欠如が公開経路で副作用0のまま停止すること。
- **テスト**: 注入しなければ公開経路から worktree へ到達できないこと（出荷面は不変）。
- **テスト**: `worktree.audit` が失敗を result（`UNAVAILABLE`）にし、`--limit` を尊重すること。
  operation 外の変更検出は receipt の `target` と `git worktree list` を突き合わせて行う
  （`SI-FLW-064`）。陽性対照（外部作成の worktree を検出して `BLOCKED`）と
  陰性対照（operation が作った worktree は外部変更にしない）を両方持つこと。
