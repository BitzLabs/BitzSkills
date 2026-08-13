---
implements: FLW-CON-002
depends_on: [FLW-TSK-055]
boundary: plugins/bitz-flow/.spec/design/FLW-DSN-012.md, plugins/bitz-flow/.spec/catalog-consistency-exceptions.json, tests/test_m2_operation_catalog_consistency.py, plugins/bitz-flow/.spec/tasks/FLW-TSK-056.md
status: done
---

### 出荷済みoperation catalogへ設計契約を整合

- **作業内容**: SI-FLW-055の裁定に従い、publish/deleteのapproval・retry・recoveryを出荷済みcatalogの安全側契約へ合わせる。
- **検証**: 設計と出荷済みcatalogの既知例外を4件から0件へ縮小し、機械照合を通す。
