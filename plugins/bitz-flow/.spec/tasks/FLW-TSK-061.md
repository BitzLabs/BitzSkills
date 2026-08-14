---
implements: FLW-CON-002
depends_on: [FLW-TSK-060]
boundary: plugins/bitz-flow/.spec/design/FLW-DSN-012.md, plugins/bitz-flow/.spec/design/FLW-DSN-014.md, plugins/bitz-flow/.spec/design/FLW-DSN-016.md, plugins/bitz-flow/.spec/ROADMAP.md, plugins/bitz-flow/.spec/consistency-exceptions.json, tests/test_m2_spec_consistency.py, plugins/bitz-flow/.spec/tasks/FLW-TSK-061.md
status: done
---

### worktree状態を直交軸へ分離

- **作業内容**: SI-FLW-050の裁定に従い、worktree_stateを物理4値へ縮小し、branch/work unit軸との決定表でfinish/discard許可を定義する。
- **検証**: 状態集合、決定表、dirty finishの退避receipt必須化を機械検証する。
