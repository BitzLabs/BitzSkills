---
implements: FLW-NFR-007, FLW-CON-006
depends_on: [FLW-TSK-068]
boundary: plugins/bitz-flow/.spec/design/FLW-DSN-014.md, plugins/bitz-flow/.spec/design/FLW-DSN-016.md, plugins/bitz-flow/.spec/ROADMAP.md, plugins/bitz-flow/.spec/tasks/FLW-TSK-069.md
status: done
---

### path別名とABA分類を最終整合

- **作業内容**: Unicode/Windows pathの別名をstable identityへ収束またはfail-closedにし、ABA経路Cを恒久非対応へ限定する。
- **検証**: `M2-FLT-057`で別名経由のroot escape/二重guardを拒否し、fixture最大値を全参照先で一致させる。
