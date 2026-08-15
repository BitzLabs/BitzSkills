---
implements: QLT-FR-027
depends_on: [QLT-TSK-010]
boundary: plugins/bitz-quality/skills/quality-review/profile/, tests/test_quality_review_profile.py
status: done
---

### SDD V4レビューprofile実装

- **作業内容**: `bitz-sdd-v4@1` profileの定義、profile resolver、閾値・必須観点・Charter pending判定、profile digestと測定母数の記録を実装する。V4 Charter未確定時は互換PASSを発行しない。
- **完了条件**: 7観点、総合4.50、各観点4.00、critical/major 0、未追跡P0/P1 0をfixtureで検証し、観点欠落・閾値未達・Charter pendingをfail-closedで判定できる。profile digest・threshold・perspectives・sample sizeを保存し、pytestがPASSする。
- **備考**: Charter確定時のprofile version bumpと再qualificationを後続運用条件とする。
