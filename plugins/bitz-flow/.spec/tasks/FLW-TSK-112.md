---
implements: FLW-NFR-014
depends_on: [FLW-TSK-106,FLW-TSK-111]
boundary: plugins/bitz-flow/skills/flow-core/scripts/flowlib/worktree_minimum_runtime.py,plugins/bitz-flow/skills/flow-core/schemas/worktree-v2/minimum-runtime-v1.schema.json,tests/test_flow_m2_minimum_runtime.py
status: pending
---

### minimum-runtime gateを実装する

- **作業内容**: owner-only local namespaceへversioned minimum-runtime markerをatomic publishし、
  stable launcherと公開CLIの起動時にcurrent bundleとの互換性を検査する。
  - audit-onlyではmarkerを書かない。
  - pending、未知bundle、非対応runtimeを起動時に`BLOCKED`にする。
- **完了条件**: crashの各位置で旧または新markerの完全ないずれかに収束し、read-only経路の副作用0件、
  非対応runtimeの起動拒否を確認する。
- **見積り**: FLW-TSK-113と実装PR 4へまとめ、1 sessionを上限とする。
- **実行判定**: promotionと分離した小さなrollback単位とする。
