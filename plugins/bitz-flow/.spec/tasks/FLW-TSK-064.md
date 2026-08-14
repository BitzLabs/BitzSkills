---
implements: FLW-CON-002
depends_on: [FLW-TSK-063]
boundary: plugins/bitz-sdd/.spec/ROADMAP.md, plugins/bitz-flow/.spec/budget-consistency-exceptions.json, tests/test_m2_budget_consistency.py, plugins/bitz-flow/.spec/tasks/FLW-TSK-064.md
status: done
---

### bitz-sddのV2予算参照を同期

- **作業内容**: SI-FLW-053裁定に従い、bitz-sdd ROADMAPをbitz-flowの予算SSOTへ接続し、実装30/100とM2設計再整備3/9の合計33/109を明記する。
- **検証**: 最後の跨workspace予算例外を解消し、例外リストを0件にする。
