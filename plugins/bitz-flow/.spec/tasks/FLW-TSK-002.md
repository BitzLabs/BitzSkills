---
implements: FLW-FR-001
depends_on: []
boundary: plugins/bitz-flow/skills/flow-worktree/scripts/worktree_ops.py, plugins/bitz-flow/skills/flow-worktree/SKILL.md, tests/test_worktree_ops.py
status: done
---

### guarded squash cleanup の実装

- **作業内容**: worktree cleanup に squash merged PR の証跡検証、SHA照合、状態別の冪等再開、remote削除候補報告を追加し、既存非squash契約を維持するテストを先行実装する。
- **完了条件**: 証跡不成立時に削除副作用がなく、initial / cleanup-partial / local-cleaned の再開と既存 CLI 互換性がテストで固定されている。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
