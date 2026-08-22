---
implements: FLW-NFR-014
depends_on: [FLW-TSK-106]
boundary: plugins/bitz-flow/skills/flow-core/scripts/flowlib/worktree_platform.py,plugins/bitz-flow/skills/flow-core/references/worktree-v2-platform-support.json,plugins/bitz-flow/skills/flow-core/schemas/worktree-v2/platform-evidence-v2.schema.json,plugins/bitz-flow/skills/flow-core/schemas/worktree-v2/support-profile-v1.schema.json,plugins/bitz-flow/skills/flow-core/schemas/worktree-v2/activation/platform-evidence-v2.json,tests/test_flow_m2_platform_adapter.py
status: pending
---

### platform evidence adapterとsupport profileを固定する

- **作業内容**: Linux、macOS、WindowsのOS観測と安全primitiveを上位policyから分離する。
  - root/parent handleからの非追随walk、native component、resource identity、owner/ACL、
    file/directory durability、OS lock、child process tree監督のclosed evidenceを返す。
  - adapterは`BLOCKED`、`STALE`、承認modeなどのpolicy resultを選択せず、
    success / unavailable / changed / semantic-unknownの観測と保持handleだけを返す。
  - 署名対象support profileと起動時semantic self-testを照合し、未登録filesystemを
    自動的にsupportedへ格上げしない。
- **完了条件**: 3platformの正常fixtureで同一logical evidence契約を返し、symlink/reparse point、
  identity差替え、owner/ACL取得不能、lock semantics不明、network/unknown filesystemを誤って
  supportedにしない。policy層への逆依存がないことをarchitecture testで検査する。
- **実行判定**: OS別の高難度境界。contract kernel完了後に開始し、platform差異が
  設計matrixを超える場合は推測実装せずscope裁定へ戻す。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
