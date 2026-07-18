---
implements: CORE-FR-015
depends_on: [CORE-TSK-022]
boundary: plugins/bitz-flow/skills/*/SKILL.md, plugins/bitz-flow/*plugin.json
status: pending
---

### SKILL.md スクリプト参照節と bitz-flow minor bump

- **作業内容**: TODO
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
