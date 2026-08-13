---
implements: SDD-FR-161
depends_on: []
boundary: plugins/bitz-sdd/skills/sdd-core/scripts/spec_inspect.py, plugins/bitz-sdd/skills/sdd-core/scripts/spec_scaffold.py, plugins/bitz-sdd/skills/sdd-core/SKILL.md, plugins/bitz-sdd/skills/sdd-review/, tests/test_spec_inspect.py, tests/test_spec_scaffold_review.py, plugins/bitz-sdd/.spec/tasks/SDD-TSK-057.md, plugins/bitz-sdd/.claude-plugin/plugin.json, plugins/bitz-sdd/plugin.json, plugins/bitz-sdd/.codex-plugin/plugin.json
status: done
---

### GP分類と behavioral EARS 契約の段階導入

- **作業内容**: SI-SDD-042 の裁定に従い、GP を behavioral / artifact / process に分類し、behavioral のみ EARS を必須化する。既存レビューは後方互換のため未分類を許容し、新規 scaffold から分類済み形式へ移行する。
- **検証**: 統制語彙、EARS 欠落・形式不正、非 behavioral の免除、scaffold の既定値を unit-test する。
