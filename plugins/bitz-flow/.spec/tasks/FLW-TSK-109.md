---
implements: FLW-NFR-014
depends_on: [FLW-TSK-107,FLW-TSK-108,FLW-TSK-113]
boundary: plugins/bitz-flow/skills/flow-core/scripts/flowlib/worktree_runtime.py,tests/test_flow_m2_runtime.py
status: pending
---

### plan-digest・TargetTransaction・Git mutationを結線する

- **作業内容**: approval context、platform evidence、TargetTransactionを`RuntimePlan`と`apply()`へ結線する。
  - allowlist済みread-only Git commandだけを起動する`RepositoryObserver`を実装し、plan、各再照合、
    audit、reconcileへ同じmachine-readable snapshotを供給する。
  - plan時、lease取得直後、各Git child起動直前にsnapshotとtarget identityを再照合する。
  - promotion lock下でcurrent bundleを再照合し、active operation markerをdurable登録してからGitへ進む。
  - promotion lockとtarget lockを同時保持せず、marker登録後にpromotion lockを解放してからtarget lockを取得する。
  - write-capable Git childを起動できる公開経路をMutationCoordinatorへ限定し、RepositoryObserverから
    write option、未知command、非machine-readable出力要求を拒否する。
  - runtimeからcounter、journal、receipt fileを直接編集しない。
  - `STALE`、`BLOCKED`、`UNSUPPORTED`、`INDETERMINATE`をclosed resultへ写像する。
- **完了条件**: 正常系、各再照合点の差替え、別process競合、parent/child crashでresult、receipt、
  実Git副作用が一致し、緊急receiptを伴わないGit mutationが0件となる。promotion中のapply開始と
  active operation中のpromotionが相互に停止し、lock timeoutが副作用なしで収束する。
- **見積り**: 単独の実装PR 5とし、3 sessionを上限とする。
- **実行判定**: 先行task完了後に直列で実施する統合境界。
