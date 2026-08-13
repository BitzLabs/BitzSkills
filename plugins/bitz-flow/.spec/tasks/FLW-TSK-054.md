---
implements: FLW-CON-002
depends_on: [FLW-TSK-053]
boundary: tests/test_m2_budget_consistency.py, plugins/bitz-flow/.spec/budget-consistency-exceptions.json
status: done
---

### SI-FLW-052第1群のbudget整合検査を実装する

- **作業内容**: `SI-FLW-053` で裁定した M2/M3 budget と上位計画への伝達について、
  現行文書の既知不整合を件数付き例外として固定する。新規不整合と修正後に残る stale 例外を
  ともに FAIL させる。
- **完了条件**: M3 budget、M2 設計再整備別枠、bitz-sdd 側参照値の不整合を検出し、
  全 pytest、canonical spec inspect、release check が PASS すること。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
