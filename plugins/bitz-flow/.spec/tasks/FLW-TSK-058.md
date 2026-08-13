---
implements: FLW-CON-002
depends_on: [FLW-TSK-057]
boundary: plugins/bitz-flow/.spec/design/FLW-DSN-014.md, plugins/bitz-flow/.spec/design/FLW-DSN-016.md, tests/test_m2_operation_catalog_consistency.py, plugins/bitz-flow/.spec/tasks/FLW-TSK-058.md
status: done
---

### 従属設計をoperation 2軸SSOTへ接続

- **作業内容**: FLW-DSN-016の独自class列を削除し、FLW-DSN-014のconfirmation区分をwrite_target軸から導出する。
- **検証**: class再宣言の不在とlocal/remote confirmation区分を機械検証する。
