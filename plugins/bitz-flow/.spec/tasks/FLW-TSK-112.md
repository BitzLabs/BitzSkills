---
implements: FLW-NFR-014
depends_on: [FLW-TSK-106,FLW-TSK-111]
boundary: plugins/bitz-flow/skills/flow-core/scripts/flowlib/worktree_minimum_runtime.py,plugins/bitz-flow/skills/flow-core/schemas/worktree-v2/minimum-runtime-v1.schema.json,plugins/bitz-flow/skills/flow-core/schemas/worktree-v2/activation/minimum-runtime-v1.json,tests/test_flow_m2_minimum_runtime.py
status: pending
---

### minimum-runtime sentinelと起動時gateを実装する

- **作業内容**: common-dirの保護namespaceへowner-only、regular file、hardlink count 1、
  非追随walk、atomic replace/fsyncを適用したversioned sentinelと起動時schema gateを実装する。
  - `audit-only`では観測だけを行いsentinelを書かない。
  - `sentinel-ready`でsentinelだけをdurableに導入し、v2 stateとGit mutationを生成しない。
  - sentinel未対応runtime、schema不明、巻戻り、identity不一致を起動時に停止する。
- **完了条件**: crashの各位置で旧または新sentinelの完全ないずれかに収束し、
  audit-onlyの副作用0件、sentinel-readyのv2 state/Git副作用0件、旧runtimeの起動拒否を確認する。
- **実行判定**: promotionと分離した小さなrollback単位。contract/platformの完了後に開始する。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
