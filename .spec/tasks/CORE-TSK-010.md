---
implements: CORE-FR-006
depends_on: [CORE-TSK-009]
boundary: plugins/bitz-sdd/skills/sdd-core/SKILL.md, plugins/bitz-env/skills/env-orchestration/SKILL.md
status: done
---

### Execute 入口のサーフェシング（sdd-core ルーティング表 ＋ env-orchestration クロス参照）

- **作業内容**: DSN-001 §7 に従い、sdd-core/SKILL.md のフェーズ・ルーティング表 Execute 行から
  env-orchestration を明示クロス参照し、env-orchestration/SKILL.md に Execute からの想起点を追記する。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
