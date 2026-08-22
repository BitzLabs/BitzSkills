---
implements: FLW-NFR-014
depends_on: [FLW-TSK-109]
boundary: plugins/bitz-flow/skills/flow-core/scripts/flowlib/worktree_quarantine.py,plugins/bitz-flow/skills/flow-core/scripts/flowlib/worktree_recovery.py,plugins/bitz-flow/skills/flow-core/schemas/worktree-v2/quarantine-release-decision-v2.schema.json,plugins/bitz-flow/skills/flow-core/schemas/worktree-v2/quarantine-release-receipt-v2.schema.json,plugins/bitz-flow/skills/flow-core/schemas/worktree-v2/activation/quarantine-release-v2.json,tests/test_flow_m2_recovery.py
status: pending
---

### recovery controllerとquarantine裁定記録を実装する

- **作業内容**: operation journal、receipt chain、実postconditionを照合し、crash後の
  復旧判定とquarantine管理を、Git mutationから分離したcontrollerに実装する。
  - reconcileは最長有効event chainから証明できる`DONE`補完または取消receiptだけを
    許可し、不確定なchild終了やpostconditionを推測で確定しない。
  - release decisionはrole付きreviewer署名、nonce、registry generation/digest、chain head、
    expected token、postcondition digestを検証する。
  - 同一targetのOS lock下で新tokenを発行し、release receiptだけをdurableに記録する。
    Git childの起動、通常operationの開始、解除後の自動再開は禁止する。
  - quarantine schema、codec、activation manifest、round-trip testを同じrollback単位で揃える。
- **完了条件**: 各crash point、journal gap/branch/改変、並行解除、chain/token差異、
  postcondition不確定、reviewer keyの未登録・失効・role不一致・registry変化を安全側に停止する。
  成功後も新planを要求し、本controllerからGit subprocessを起動できないことを検査する。
- **実行判定**: 復旧安全性の中核。mutation runtimeの完了後に開始し、CLI、SLI、runbookは
  後続のoperations control planeタスクへ委譲する。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
