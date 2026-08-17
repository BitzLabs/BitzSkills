---
implements: FLW-FR-012
depends_on: [FLW-TSK-091]
boundary: evals/flow-core/m2-eval/record_run.py,evals/flow-core/m2-eval/run-manifest-m2-remediation.json,plugins/bitz-flow/.spec/STATE.md,plugins/bitz-flow/.spec/tasks/FLW-TSK-092.md,tests/test_flow_m2_run_manifest.py
status: done
---

### M2是正manifestを実績と裁定参照へ追随させる

- **作業内容**: 重複した実績entryと未記録のPR #294を、裁定記録と最新レビューへ整合する
  一度限りのreconciliation snapshotへ置き換える。以後の記録器はappend-onlyとし、同じPR番号の
  二重記録、上限解除後の旧予算による誤停止、既存entryと矛盾する裁定参照を拒否する。確定できない
  過去のsession数は推測せず`null`として明示する。
- **完了条件**: manifestが現行裁定とPR #289〜294の実績を一意に保持し、重複PRと旧上限に
  よる停止をテストで検出する。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
