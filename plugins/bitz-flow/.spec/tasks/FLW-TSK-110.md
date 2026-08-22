---
implements: FLW-NFR-014
depends_on: [FLW-TSK-108,FLW-TSK-109]
boundary: plugins/bitz-flow/skills/flow-core/scripts/flowlib/worktree_recovery.py,tests/test_flow_m2_recovery.py,plugins/bitz-flow/skills/flow-core/SKILL.md,plugins/bitz-flow/.claude-plugin/plugin.json,plugins/bitz-flow/plugin.json,plugins/bitz-flow/.codex-plugin/plugin.json,.claude-plugin/marketplace.json
status: pending
---

### read-only auditと明示確認付きreconcileを実装する

- **作業内容**: RepositoryObserverが返すGit state、最長有効journal prefix、terminal receiptから
  `confirmed-complete` / `confirmed-incomplete` / `indeterminate`を判定する。
  - auditはread-onlyとする。
  - reconcileは新planと明示確認を要求し、TargetTransaction経由で冪等なclosure eventだけを追記する。
  - active marker操作とtarget lockを同時保持せず、runtimeと同じ非重複lock規則を使う。
  - Git mutation、自動解除、自動削除、自動再実行、署名reviewer decisionを実装しない。
- **完了条件**: 全crash point、journal破損、同一decision retry、異decision、token/state差替えで
  安全側へ収束し、本moduleからGit subprocessを直接起動できない。
- **見積り**: FLW-TSK-114と実装PR 6へまとめ、2 sessionを上限とする。
- **実行判定**: mutation runtime完了後に開始する。archiveや鍵管理要求は別scopeへ戻す。
  実装PR 6のrelease integration ownerとしてplugin/skillをpatch bumpする。
