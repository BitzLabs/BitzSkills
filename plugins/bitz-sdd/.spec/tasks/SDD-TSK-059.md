---
implements: SDD-FR-168
depends_on: [SDD-TSK-058]
boundary: plugins/bitz-sdd/skills/sdd-core/scripts/spec_inspect.py, plugins/bitz-sdd/skills/sdd-core/SKILL.md, tests/test_spec_inspect.py, plugins/bitz-sdd/.spec/requirements/SDD-FR-168.md, plugins/bitz-sdd/.spec/tasks/SDD-TSK-059.md
status: done
---

### ガバナンス主張の汎用検査を追加

- **作業内容**: SI-FLW-052裁定に従い、裁定記録実在、topic別SSOT一意性、設計とverified制約の整合を任意導入の機械可読manifestとしてspec_inspectへ追加する。
- **検証**: 正常系と各fail-closed経路、およびmanifest未導入workspaceの後方互換をunit-testで固定する。
