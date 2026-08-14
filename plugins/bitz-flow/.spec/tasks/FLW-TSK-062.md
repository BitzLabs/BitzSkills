---
implements: FLW-CON-002
depends_on: [FLW-TSK-061]
boundary: plugins/bitz-flow/.spec/design/FLW-DSN-014.md, plugins/bitz-flow/.spec/design/FLW-DSN-016.md, plugins/bitz-flow/.spec/ROADMAP.md, tests/test_m2_spec_consistency.py, plugins/bitz-flow/.spec/tasks/FLW-TSK-062.md
status: done
---

### 機械強制責務とqualification順序を是正

- **作業内容**: SI-FLW-051案Dに従いplatform固有hookを責務外とし、in-band capabilityとaudit/quarantineへ担保を寄せる。qualificationをM2-4直後へ分離する。
- **検証**: hook/permissions非所有、in-band安全境界、M2-Q順序を機械検証する。
