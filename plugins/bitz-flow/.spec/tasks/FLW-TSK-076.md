---
implements: FLW-FR-006, FLW-FR-007, FLW-NFR-007
depends_on: [FLW-TSK-075]
boundary: plugins/bitz-flow/skills/flow-core/scripts/flowlib/worktree.py, plugins/bitz-flow/skills/flow-core/schemas/worktree-state-v1.schema.json, plugins/bitz-flow/skills/flow-core/SKILL.md, plugins/bitz-flow/.spec/specs/m2-worktree-operations/test-spec.md, plugins/bitz-flow/.spec/tasks/FLW-TSK-076.md, tests/test_flow_m2_worktree.py, plugins/bitz-flow/.claude-plugin/plugin.json, plugins/bitz-flow/plugin.json, plugins/bitz-flow/.codex-plugin/plugin.json
status: done
---

### M2-3 create・resume・auditを実装する

- **作業内容**: 外部事実から再構成するworktree/branch直交状態、create crash収束、resume
  instance照合、filesystem capability対称性、設計/schema/実装enum三者照合を実装する。
- **検証**: `M2-FLT-016`〜`023`、`053`、全テスト、spec inspection、release check。
