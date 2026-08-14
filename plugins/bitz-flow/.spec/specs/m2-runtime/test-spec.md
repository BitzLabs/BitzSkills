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
