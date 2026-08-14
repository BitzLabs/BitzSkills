---
implements: FLW-FR-006, FLW-CON-006, FLW-NFR-011
depends_on: [FLW-TSK-077]
boundary: plugins/bitz-flow/skills/flow-core/scripts/flowlib/worktree_cleanup.py, plugins/bitz-flow/skills/flow-core/SKILL.md, plugins/bitz-flow/.spec/specs/m2-cleanup/test-spec.md, plugins/bitz-flow/.spec/tasks/FLW-TSK-078.md, tests/test_flow_m2_cleanup.py, evals/flow-core/m2-eval/qualification-2026-08-14.json, plugins/bitz-flow/.claude-plugin/plugin.json, plugins/bitz-flow/plugin.json, plugins/bitz-flow/.codex-plugin/plugin.json
status: done
---

### M2-QとM2-5 finish・discard・retentionを完了する

- **前提**: 3platform actual qualification PASS。compatibility keyを新規eval成果物へ記録。
- **作業内容**: cleanup step prefix、merge/dirty/manifest/instance検査、retention ref、
  quarantine分類、guard再発行停止証明、recovery fail-closedを実装する。
- **検証**: `M2-FLT-024`〜`036`、`050`、`056`、全テスト、spec、release check。
