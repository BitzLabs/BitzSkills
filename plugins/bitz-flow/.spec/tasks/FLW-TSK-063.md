---
implements: FLW-CON-002
depends_on: [FLW-TSK-062]
boundary: plugins/bitz-flow/.spec/design/FLW-DSN-014.md, plugins/bitz-flow/.spec/design/FLW-DSN-016.md, plugins/bitz-flow/.spec/ROADMAP.md, plugins/bitz-flow/.spec/budget-consistency-exceptions.json, tests/test_m2_budget_consistency.py, plugins/bitz-flow/.spec/tasks/FLW-TSK-063.md
status: done
---

### M2/M3予算と残債移送を整合

- **作業内容**: SI-FLW-053裁定に従い、M2実装枠6/20、設計再整備3/9、M3残債込み8/26を同期し、M2-Qを含むsession配賦とearly quick winを確定する。
- **検証**: flow側予算例外3件を解消し、跨workspace参照1件だけを別PRへ残す。
