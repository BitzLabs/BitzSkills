---
implements: SDD-FR-161
depends_on: [SDD-TSK-057]
boundary: plugins/bitz-sdd/skills/sdd-core/scripts/spec_inspect.py, plugins/bitz-sdd/skills/sdd-core/scripts/spec_scaffold.py, plugins/bitz-sdd/skills/sdd-core/SKILL.md, plugins/bitz-sdd/skills/sdd-review/, tests/test_spec_inspect.py, tests/test_spec_scaffold_review.py, plugins/bitz-sdd/.spec/tasks/SDD-TSK-058.md, plugins/bitz-sdd/.claude-plugin/plugin.json, plugins/bitz-sdd/plugin.json, plugins/bitz-sdd/.codex-plugin/plugin.json
status: done
---

### blocking GP の受領応答契約を追加

- **作業内容**: SI-SDD-042 の裁定に従い、分類済み blocking GP へ accepted / rejected / deferred の応答を必須化し、原文の逐語一致と状態別の必須証跡を検査する。
- **検証**: 応答欠落、原文改変、各状態の必須キー、延期期限・Gate語彙、scaffold既定値を unit-test する。
