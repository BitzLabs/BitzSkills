---
implements: FLW-NFR-006, FLW-CON-005, FLW-CON-006
depends_on: [FLW-TSK-073]
boundary: plugins/bitz-flow/skills/flow-core/scripts/flowlib/guard.py, plugins/bitz-flow/skills/flow-core/scripts/flowlib/git_sync.py, plugins/bitz-flow/skills/flow-core/schemas/result-v1.schema.json, plugins/bitz-flow/skills/flow-core/schemas/intent-record-v1.schema.json, plugins/bitz-flow/skills/flow-core/references/output-contract.md, plugins/bitz-flow/skills/flow-core/SKILL.md, plugins/bitz-flow/.spec/specs/m2-guard-core/test-spec.md, plugins/bitz-flow/.spec/tasks/FLW-TSK-074.md, tests/test_flow_m1_guard.py, tests/test_flow_m2_guard.py, plugins/bitz-flow/.claude-plugin/plugin.json, plugins/bitz-flow/plugin.json, plugins/bitz-flow/.codex-plugin/plugin.json
status: done
---

### M2-1 guard coreを実装する

- **作業内容**: worktree-dir/registry identity、opaque worktree ID、binding、index包含、
  root containment、case/Unicode/Windows pathのfail-closed canonicalizationを実装する。
- **検証**: `M2-FLT-001`〜`009`と`057`、M1回帰、全テスト、spec inspection、release check。
