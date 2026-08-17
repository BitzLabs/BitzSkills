---
implements: FLW-FR-012
depends_on: []
boundary: plugins/bitz-flow/.spec/ROADMAP.md,plugins/bitz-flow/.spec/STATE.md,plugins/bitz-flow/.spec/design/FLW-DSN-014.md,plugins/bitz-flow/.spec/requirements/FLW-FR-012.md,plugins/bitz-flow/.spec/reports/decision-2026-08-17-m2-integrity-boundary-and-control-plane.md,plugins/bitz-flow/.spec/spec-issues/SI-FLW-074.md,plugins/bitz-flow/.spec/tasks/FLW-TSK-091.md
status: done
---

### M2統制層の設計・現況記録を最新の裁定へ追随させる

- **作業内容**: `FLW-REV-019` と 2026-08-17 の裁定を、M2 の現況・出口条件・予算の
  読み方へ反映する。M2 は receipt store と保護境界の双方を書き換えられる攻撃者への真正性を
  主張しないこと、Completion Gate は保留であること、予算の再校正は `GP-006` として未裁定で
  あることを一つの状態として記録する。実績manifestの修正と再発防止の機械検査は後続タスクへ
  分離する。
- **完了条件**: ROADMAP と M2 出口条件×証拠の対応表が `FLW-REV-019` を最新の判定として
  参照し、`FLW-FR-012` の status が未充足を表す。`spec inspect --check-only` が通る。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
