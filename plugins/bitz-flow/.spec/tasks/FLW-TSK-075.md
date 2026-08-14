---
implements: FLW-NFR-007, FLW-CON-005, FLW-CON-006
depends_on: [FLW-TSK-074]
boundary: plugins/bitz-flow/skills/flow-core/scripts/flowlib/worktree_capability.py, plugins/bitz-flow/skills/flow-core/SKILL.md, plugins/bitz-flow/.spec/specs/m2-approval-capability/test-spec.md, plugins/bitz-flow/.spec/tasks/FLW-TSK-075.md, tests/test_flow_m2_capability.py, plugins/bitz-flow/.claude-plugin/plugin.json, plugins/bitz-flow/plugin.json, plugins/bitz-flow/.codex-plugin/plugin.json
status: done
---

### M2-2 worktree承認capabilityを実装する

- **作業内容**: 単回署名capability、scope/freshness再照合、nonce状態機械、外部binding変更の
  ORPHAN/quarantine接続、capabilityなしwriteのin-band拒否を実装する。
- **検証**: `M2-FLT-010`〜`015`、M1/M2回帰、全テスト、spec inspection、release check。
