---
implements: FLW-FR-012
depends_on: []
boundary: evals/flow-core/m2-eval/record_run.py,evals/flow-core/m2-eval/run-manifest-m2-remediation.json,plugins/bitz-flow/.spec/STATE.md,plugins/bitz-flow/.spec/design/FLW-DSN-014.md,plugins/bitz-flow/.spec/reports/decision-2026-08-17-si-flw-076-m2-budget-exception.md,plugins/bitz-flow/.spec/requirements/FLW-FR-012.md,plugins/bitz-flow/.spec/spec-issues/SI-FLW-076.md,plugins/bitz-flow/.spec/tasks/FLW-TSK-095.md,tests/test_flow_m2_run_manifest.py,tests/test_m2_budget_consistency.py
status: done
---

### M2限定の上限なし例外を要件契約へ同期する

- **作業内容**: `FLW-REV-018`のfindingを解消するM2 remediationだけを上限なしに限定し、
  scopeと裁定referenceがないmanifestを記録器が拒否する。M3〜M5の上限・再校正・停止契約は維持する。
- **完了条件**: 要件・設計・manifest・記録器・テストが同じM2限定例外を示し、scopeの欠落または
  変更がpytestで失敗する。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
