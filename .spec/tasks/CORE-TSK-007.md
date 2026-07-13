---
implements: CORE-FR-009
depends_on: []
boundary: CLAUDE.md
status: done
---

### Claude 委譲レジストリの形式化（ティアはしご＋役割→委譲先→ティア表）

- **作業内容**: DSN-001 §3 に従い CLAUDE.md 委譲マトリクスを形式化。ティアはしご
  （Fable5 > Opus > Sonnet > Haiku）を明示し、役割→委譲先(agent)→ティアの表を機械可読な形で置く。
  これを Claude 委譲レジストリ（SSOT）とする。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
