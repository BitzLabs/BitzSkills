---
implements: FLW-CON-002
depends_on: [FLW-TSK-053]
boundary: tests/test_m2_operation_catalog_consistency.py, plugins/bitz-flow/.spec/catalog-consistency-exceptions.json, plugins/bitz-flow/.spec/tasks/FLW-TSK-055.md
status: done
---

### 設計と出荷済みoperation catalogの契約照合

- **作業内容**: SI-FLW-052第1群として、FLW-DSN-012と出荷済みoperation catalogのclass・approval・retry・recoveryを双方向照合し、既知差分だけを縮小専用例外として固定する。
- **検証**: 新規差分と修正後に残った古い例外の双方をpytestでFAILさせる。
