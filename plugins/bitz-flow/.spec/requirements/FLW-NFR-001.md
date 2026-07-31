---
id: FLW-NFR-001
version: 1.0
status: implementing
domain: verification
priority: high
origin: .spec/reports/decision-2026-07-29-bitz-flow-v2-design-gate.md
verification_method: benchmark
derived_from:
supersedes:
superseded_by:
confidence: high
---

### FLW-NFR-001 モデル横断の実行率と判断一致

- **説明**: Claude Code、Codex CLI、Antigravity 2.0でdispatcherが選択され、同じ事実から同じ判断を返すことをM0で実証する。
- **受入基準 (EARS)**:
  - WHEN M0評価を各platformと各taskで10回実行する THEN bitz-flowはplatform別Dispatcher Invocation Rate 95%以上を記録すること SHALL
  - WHEN skillなしbaselineとM0結果を比較する THEN bitz-flowはplatform別Dispatcher Invocation Rateを20ポイント以上改善すること SHALL
  - WHEN M0評価を各platformで実行する THEN bitz-flowはplatform別SFCR 90%以上を記録すること SHALL
  - WHEN 同じfixtureを3platformで評価する THEN bitz-flowはCross-model Decision Parity 100%を記録すること SHALL
  - WHEN agentが同じtrial内で自己再試行する THEN 評価harnessは当該trialを失敗として記録すること SHALL
  - WHEN いずれかのM0閾値を満たさない THEN bitz-flowはM1開始を`BLOCKED`にすること SHALL
- **検証閾値**: platform×task各10 trial、Invocation 95%以上、skillなし比+20ポイント以上、SFCR 90%以上、Decision Parity 100%。
- **検証手段**: version固定prompt、model manifest、skillなし/v1 baseline、独立oracleを用いるbenchmarkで検証する。
- **Revision History**:
  - 1.0 (2026-07-29) FLW-DSC-004/006とFLW-DSN-014からdraft起票
