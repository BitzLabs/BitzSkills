---
implements: FLW-CON-006
depends_on: [FLW-TSK-067]
boundary: plugins/bitz-flow/.spec/design/FLW-DSN-013.md, plugins/bitz-flow/.spec/design/FLW-DSN-014.md, plugins/bitz-flow/.spec/design/FLW-DSN-016.md, plugins/bitz-flow/.spec/ROADMAP.md, plugins/bitz-flow/.spec/tasks/FLW-TSK-068.md
status: done
---

### 削除前のlocal branch tipを保全

- **作業内容**: SI-FLW-049裁定に従い、finish/discardでlocal branchを削除する前にtip OIDの保全refをCAS作成し、90日retentionとlist/prune operationを定義する。
- **検証**: 未push commit、期限前ref、未解決quarantineに対する削除0を`M2-FLT-056`で固定する。
