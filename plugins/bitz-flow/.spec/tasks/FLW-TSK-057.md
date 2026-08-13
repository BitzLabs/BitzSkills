---
implements: FLW-CON-002
depends_on: [FLW-TSK-056]
boundary: plugins/bitz-flow/.spec/design/FLW-DSN-012.md, tests/test_m2_operation_catalog_consistency.py, plugins/bitz-flow/.spec/tasks/FLW-TSK-057.md
status: done
---

### operation classを直交2軸の導出値へ変更

- **作業内容**: SI-FLW-049の裁定に従い、write_targetとreversibilityをclass体系のSSOTとし、従来4値classを互換用の導出値へ変更する。
- **検証**: 全公開operationについて軸の組合せと導出classの一致を機械検証する。
