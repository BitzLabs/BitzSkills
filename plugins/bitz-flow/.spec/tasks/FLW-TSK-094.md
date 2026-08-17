---
implements: FLW-FR-012
depends_on: []
boundary: plugins/bitz-flow/.spec/ROADMAP.md,plugins/bitz-flow/.spec/STATE.md,plugins/bitz-flow/.spec/design/FLW-DSN-014.md,plugins/bitz-flow/.spec/reports/decision-2026-08-17-v2-operational-integrity-scope.md,plugins/bitz-flow/.spec/spec-issues/SI-FLW-072.md,plugins/bitz-flow/.spec/tasks/FLW-TSK-094.md,tests/test_m2_budget_consistency.py
status: done
---

### V2の運用品質スコープを統制記録と検査へ固定する

- **作業内容**: 強い改ざん耐性をV2の対象外とする人間裁定を記録し、ROADMAP、M2設計、
  spec-issueの対象範囲を通常運用の検出へ揃える。統制記録との乖離はpytestで検出する。
- **完了条件**: V2のCompletion Gateが強い真正性保証を要求せず、将来必要になった場合だけ
  新規security設計として再検討することを、裁定記録と機械検査から確認できる。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
