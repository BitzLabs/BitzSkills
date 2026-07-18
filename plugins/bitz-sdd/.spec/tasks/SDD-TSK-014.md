---
implements: SDD-FR-125, SDD-FR-126, SDD-FR-127, SDD-FR-128, SDD-FR-129
depends_on: [SDD-TSK-012, SDD-TSK-013]
boundary: plugins/bitz-sdd/skills, plugins/bitz-sdd/.spec, plugins/bitz-sdd/.claude-plugin/plugin.json, plugins/bitz-sdd/plugin.json, plugins/bitz-sdd/.codex-plugin/plugin.json, .claude-plugin/marketplace.json
status: pending
---

### 文書契約の結線とmajor release

- **作業内容**: 関連スキルの同期先と運用規約を日本語6章へ揃え、旧要件を後継化し、
  スキルmetadataとbitz-sdd pluginをsemver majorで更新して全体検証する。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
