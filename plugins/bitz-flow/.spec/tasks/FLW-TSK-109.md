---
implements: FLW-NFR-014
depends_on: [FLW-TSK-107,FLW-TSK-108]
boundary: plugins/bitz-flow/skills/flow-core/scripts/flowlib/worktree_runtime.py,plugins/bitz-flow/skills/flow-core/schemas/worktree-v2/mutation-receipt-v2.schema.json,plugins/bitz-flow/skills/flow-core/schemas/worktree-v2/activation/mutation-receipt-v2.json,tests/test_flow_m2_runtime.py
status: pending
---

### approval bindingと永続leaseをM2 runtimeへ結線する

- **作業内容**: 先行タスクのbinding reader、capability v2、process間leaseを`RuntimePlan`と`apply()`へ
  結線する。
  - plan時、承認後かつlease取得直後、各Git child起動直前にbindingを再照合する。
  - 最終再照合を承認線形化点としてreceiptへphase/digest/cause/tokenを記録する。
  - digest差異を`STALE`、検証不能を`BLOCKED`/`UNSUPPORTED`、postcondition不確定を
    `INDETERMINATE`へ写像し、停止点以後のGit副作用を0件にする。
  - 現在のprocess内`TargetGuardManager`は先行検査として残し、永続leaseの代替にはしない。
  - mutation receipt schema、codec、round-trip testを同じ変更で揃え、owner activation manifestをactive化する。
- **完了条件**: boundとabsentの正常系、各再照合点での作成・削除・内容変更・inode置換、別process
  競合、parent/child crashを通し、result/receiptと実Git副作用が要件の分類に一致する。
- **実行判定**: 統合タスク。先行2タスクがdoneになるまで開始せず、中央runtime境界のため直列で自己実行する。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
