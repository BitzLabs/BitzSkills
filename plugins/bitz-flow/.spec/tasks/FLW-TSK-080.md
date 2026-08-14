---
implements: FLW-FR-006, FLW-CON-005, FLW-CON-006
depends_on: FLW-TSK-079
boundary: plugins/bitz-flow/skills/flow-core/scripts/flowlib/worktree_runtime.py, plugins/bitz-flow/skills/flow-core/scripts/flowlib/worktree_capability.py, plugins/bitz-flow/skills/flow-core/scripts/flowlib/recovery.py, plugins/bitz-flow/skills/flow-core/scripts/flowlib/cli.py, plugins/bitz-flow/skills/flow-core/scripts/flowlib/__init__.py, plugins/bitz-flow/skills/flow-core/scripts/flow.py, plugins/bitz-flow/skills/flow-core/references/operation-catalog.md, plugins/bitz-flow/skills/flow-core/SKILL.md, plugins/bitz-flow/.spec/specs/m2-runtime/test-spec.md, plugins/bitz-flow/.spec/tasks/FLW-TSK-080.md, plugins/bitz-flow/.spec/spec-issues/SI-FLW-056.md, plugins/bitz-flow/.spec/reports/decision-2026-08-14-si-flw-056.md, plugins/bitz-flow/.spec/STATE.md, tests/test_flow_contract.py, tests/test_flow_m1_contract_rows.py, tests/test_flow_m1_write_faults.py, tests/test_flow_m2_runtime.py, plugins/bitz-flow/.claude-plugin/plugin.json, plugins/bitz-flow/plugin.json, plugins/bitz-flow/.codex-plugin/plugin.json
status: done
---

### M2 worktree実動adapterとdispatcherを統合する

- **作業内容**: create/resume/finish/discardのplan/apply、Ed25519 capability、nonce ledger、
  receipt chain、公開dispatcher、独立tmp repository E2Eを実装する。
- **検証**: capability fail-closed、実Git副作用、retention、receipt prefix、全pytest、spec inspect、release check。
