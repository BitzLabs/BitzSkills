---
implements: FLW-NFR-014
depends_on: [FLW-TSK-106,FLW-TSK-111,FLW-TSK-112]
boundary: plugins/bitz-flow/skills/flow-core/scripts/flowlib/worktree_promotion.py,plugins/bitz-flow/skills/flow-core/schemas/worktree-v2/entrypoint-policy-v1.schema.json,plugins/bitz-flow/skills/flow-core/schemas/worktree-v2/entrypoint-evidence-v1.schema.json,plugins/bitz-flow/skills/flow-core/schemas/worktree-v2/promotion-state-v2.schema.json,plugins/bitz-flow/skills/flow-core/schemas/worktree-v2/promotion-receipt-v2.schema.json,plugins/bitz-flow/skills/flow-core/schemas/worktree-v2/activation/promotion-v2.json,plugins/bitz-flow/skills/flow-core/references/worktree-v2-entrypoint-baseline.json,tests/test_flow_m2_promotion.py
status: pending
---

### trusted entrypoint promotion controllerを実装する

- **作業内容**: 署名対象baselineとsupport profileを信頼根に、stable launcher、公開CLI、
  enabled plugin cacheの実体を列挙・測定・probeし、promotion stateとreceiptを所有する。
  - 未知artifactは起動せず、親processが保持handleから測定した一致artifactだけを
    closed environment、timeout、出力上限、process tree監督付きでprobeする。
  - stateのdurability commit直前にregistry generation、identity、artifact digestを再照合する。
  - `canary`は明示repository/targetだけを有効化し、`default-on`はcanary出口条件を
    満たしたsupport profileだけに許可する。
  - 通常applyで完全probeを反復せず、promotion receipt、sentinel、current identityの
    軽量再照合をruntimeへ公開する。Git mutationは行わない。
- **完了条件**: 3platformの正常entrypointをpromotionでき、旧runtime、欠落cache、alias、
  artifact/registry差替え、hang、出力超過、副作用canary、support profile不一致でstateを生成しない。
  audit-onlyからdefault-onの各phaseで許容副作用だけが発生する。
- **実行判定**: sentinelがgreenになった後に開始する。配布信頼根の差異は実装で
  吸収せず設計またはscope裁定へ戻す。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
