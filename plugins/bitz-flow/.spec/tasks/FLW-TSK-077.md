---
implements: FLW-NFR-004, FLW-NFR-008, FLW-CON-006
depends_on: [FLW-TSK-076]
boundary: plugins/bitz-flow/skills/flow-core/scripts/flowlib/reconnaissance.py, plugins/bitz-flow/skills/flow-core/SKILL.md, plugins/bitz-flow/.spec/specs/m2-reconnaissance/test-spec.md, plugins/bitz-flow/.spec/tasks/FLW-TSK-077.md, tests/test_flow_m2_reconnaissance.py, plugins/bitz-flow/.claude-plugin/plugin.json, plugins/bitz-flow/plugin.json, plugins/bitz-flow/.codex-plugin/plugin.json
status: done
---

### M2-4 reconnaissance・entry protocol・運用証跡を実装する

- **作業内容**: 全write前in-flight列挙、path重複、上限fail-closed、quarantine滞留上申、
  append-only evidence chain検証を実装する。
- **検証**: `M2-FLT-045`〜`047`、`051`、`052`、`055`、全テスト、spec、release check。
