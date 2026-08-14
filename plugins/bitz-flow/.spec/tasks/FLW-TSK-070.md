---
implements: FLW-CON-002, FLW-CON-006
depends_on: [FLW-TSK-069]
boundary: plugins/bitz-flow/.spec/design/FLW-DSN-012.md, plugins/bitz-flow/.spec/tasks/FLW-TSK-070.md, tests/test_m2_operation_catalog_consistency.py
status: done
---

### M2 safety operationを契約SSOTへ登録

- **作業内容**: SI-FLW-054/049で追加した監査readとretention pruneをFLW-DSN-012の公開action catalogへ登録する。
- **検証**: 直交2軸からclassを導出し、M2詳細表の全safety operationが契約SSOTに存在することを固定する。
