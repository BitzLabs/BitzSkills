---
implements: FLW-FR-012
depends_on: [FLW-TSK-091,FLW-TSK-092]
boundary: plugins/bitz-flow/.spec/STATE.md,plugins/bitz-flow/.spec/tasks/FLW-TSK-093.md,tests/test_m2_budget_consistency.py
status: done
---

### M2統制記録の現況不整合を機械検査する

- **作業内容**: M2の現況を示す統制記録（ROADMAP / 設計 / 決定記録）と、実績manifestの
  予算モード・裁定参照・PR一意性・未確定sessionの表現を同じ期待値で検査する。
- **完了条件**: 最新レビューの判定、M2 Completion Gate保留、`FLW-REV-019:GP-006` の
  未裁定、および PR #289〜294 の実績表現が不整合になった場合に pytest が失敗する。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
