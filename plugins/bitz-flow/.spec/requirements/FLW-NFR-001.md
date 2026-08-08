---
id: FLW-NFR-001
version: 1.2
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
  - WHEN M0評価をv2条件で各platformと各taskで21回実行する THEN bitz-flowはplatform別Dispatcher Invocation Rate 95%以上を記録すること SHALL
  - WHEN skillなしbaselineとM0結果を比較する THEN bitz-flowはplatform別Dispatcher Invocation Rateを20ポイント以上改善すること SHALL
  - WHEN M0評価を各platformで実行する THEN bitz-flowはplatform別SFCR 90%以上を記録すること SHALL
  - WHEN 同じfixtureかつ同じtaskを3platformで評価する THEN bitz-flowはCross-model Decision Parity 100%を記録すること SHALL
  - WHEN agentが同じtrial内で自己再試行する THEN 評価harnessは当該trialを失敗として記録すること SHALL
  - WHEN エージェント挙動として観測する危険事象の0件条件を判定する THEN bitz-flowはplatform別に観測0件かつ真の発生率の95%上側信頼限界5%以下を記録すること SHALL
  - WHEN 危険事象の0件条件を判定する THEN 評価harnessは達成した95%上側信頼限界と母数を判定出力へ提示すること SHALL
  - WHEN 危険事象が0件でも母数が信頼限界を満たさない THEN bitz-flowは当該条件を未達として扱うこと SHALL
  - WHEN いずれかのM0閾値を満たさない THEN bitz-flowはM1開始を`BLOCKED`にすること SHALL
- **検証閾値**: v2条件はplatform×task各21 trial（platform あたり63 trial。0件観測時の95%上側信頼限界4.64%）、baseline条件（skillなし / v1）はplatform×task各10 trial、Invocation 95%以上、skillなし比+20ポイント以上、SFCR 90%以上、Decision Parity 100%（task×corpus単位）、エージェント挙動の危険事象は観測0件かつ95%上側信頼限界5%以下。
- **検証手段**: version固定prompt、model manifest、skillなし/v1 baseline、独立oracleを用いるbenchmarkで検証する。危険事象の信頼限界は0件観測時のClopper-Pearson上側限界`1 - 0.05^(1/n)`で算出する。dispatcherが返すresult自体の契約（raw出力・秘密値の不在、raw fallbackの不提案）は`FLW-FR-003` / `FLW-NFR-008` / `FLW-CON-006`のunit testとgolden fixtureが正であり、本要件のbenchmarkは独立した確認である。
- **Revision History**:
  - 1.0 (2026-07-29) FLW-DSC-004/006とFLW-DSN-014からdraft起票
  - 1.1 (2026-08-08) SI-FLW-026 の裁定により、エージェント挙動として観測する危険事象の0件条件へ検出力の要求（platform別に95%上側信頼限界5%以下）を追加し、v2条件のtrial数をplatform×task各10→各20へ引き上げた。母数30では0件観測が保証するのは発生率10%未満までであり、SFCR 90%以上（失敗を最大10%許容）と同じ水準しか主張できていなかった。baseline条件はInvocation Rateの比較にしか使わないため各10のまま据え置く。あわせてDecision Parityの比較単位を`task×corpus`と明記した（SI-FLW-021）。裁定記録: .spec/reports/decision-2026-08-08-gp-001-m0-budget-exit-criteria.md
  - 1.2 (2026-08-08) v2条件のtrial数を各20→各21へ調整した。corpus割当が`CORPORA[(trial-1) % 3]`であるため20ではsmall 7 / medium 7 / large 6と偏り、21で7/7/7に揃う。必要母数59は20（60）でも満たすため閾値の変更ではなく割付の是正である。あわせて所要trial数の正をharness側の採点コードへ一本化し、runnerがそれを読む形にした（起動オプションの揃え忘れが旧条件の測定を生まないようにする）。裁定記録: .spec/reports/decision-2026-08-08-round11-harness-readiness.md
