---
implements: FLW-NFR-014
depends_on: [FLW-TSK-109]
boundary: plugins/bitz-flow/skills/flow-core/references/operation-catalog.md,plugins/bitz-flow/docs/runbooks/m2-worktree-quarantine.md,tests/test_flow_m2_operability.py
status: pending
---

### receipt SLI・quarantine runbook・E2E fault fixtureを統合する

- **作業内容**: cause別停止件数、lock待機、quarantine滞留、token不連続、receipt chain failureを
  operation catalogとE2E fault fixtureへ接続する。runbookにはaudit/reconcile/解除CLI、一次対応role、
  reviewer承認、通知adapter、24時間超過escalation、解除receipt必須fieldを記載する。
- **完了条件**: 1 operation内token不連続、chain failure、24時間超過、同一cause 3回連続停止の
  各fixtureから正しい運用導線を得る。通知未設定でもreceiptと終了codeを失わず、runbookのコマンドが
  実在する。共有runtime変更のため全pytest、spec inspect、release checkを実行する。
- **実行判定**: 文書・fixtureの量産と最終検証。依存解決後に境界が独立した部分だけ委譲可能だが、
  Claudeは利用せず、検収は司令塔が実行する。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
