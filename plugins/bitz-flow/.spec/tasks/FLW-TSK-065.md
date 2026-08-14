---
implements: FLW-CON-002, FLW-CON-006
depends_on: [FLW-TSK-064]
boundary: plugins/bitz-flow/.spec/design/FLW-DSN-012.md, plugins/bitz-flow/.spec/design/FLW-DSN-013.md, plugins/bitz-flow/.spec/design/FLW-DSN-016.md, plugins/bitz-flow/.spec/consistency-exceptions.json, tests/test_m2_spec_consistency.py, plugins/bitz-flow/.spec/tasks/FLW-TSK-065.md
status: done
---

### worktree recovery IDと収束契約を統一

- **作業内容**: SI-FLW-049裁定に従い、5件の別名を`REC-WORKTREE-*` / `REC-REMOTE-DELETE`へ統一し、resume固有の回復手順、4 operationのreceipt・identity・manifest照合とreconcile-onlyを確定する。
- **検証**: operation catalogのRecovery IDがregistryに全件存在することを機械検査し、構造例外を0件にする。
