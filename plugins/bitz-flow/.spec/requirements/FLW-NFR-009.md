---
id: FLW-NFR-009
version: 1.0
status: verified
domain: verification
priority: high
origin: SI-FLW-036
verification_method: unit-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### FLW-NFR-009 M0評価の全採点proxy台帳と乖離防止

- **説明**: M0評価の合否に使う全proxyについて、measurand、母集団、oracle、選択・除外規則、
  乖離条件、歯止め、証跡を仕様と実装で対応付け、被測定物の欠陥と測定系の誤判定を分離する。
- **受入基準 (EARS)**:
  - WHEN M0の評価指標を設計または変更する THEN bitz-flowは当該proxyのmeasurand、母集団、oracle、
    選択・除外規則、乖離条件、歯止め、実装とテストの証跡をproxy台帳へ記録すること SHALL
  - WHEN captured outputからcompact result envelopeを採点する THEN 評価harnessは先行する補助出力を
    許容しつつ、published result codeと対象operationが一致するenvelopeだけを採点対象にすること SHALL
  - WHEN result envelopeが無いか複数候補が曖昧である THEN 評価harnessは当該trialを成功にせず、
    探索・選択の根拠をobservationまたは自己診断へ記録すること SHALL
  - WHEN compact resultが`truncated: false`である THEN 評価harnessはoracleの全itemと必須fieldを
    出力と照合すること SHALL
  - WHEN compact resultが`truncated: true`である THEN 評価harnessはenvelopeの集計値、
    `TRUNCATED shown=N total=M`、実際の表示件数、表示済みitemの必須fieldをoracleと照合し、
    省略済みitemの出力上の存在は要求しないこと SHALL
  - WHEN proxyの判定ロジックを変更する THEN bitz-flowはtrue positive、false positive防止、
    false negative防止の回帰テストを持ち、保存済みtrialの新旧判定を`scoring_rule_version`で追跡可能にすること SHALL
- **検証手段**: proxy台帳と実装の対応検査、result envelope探索、全量/省略compact出力、曖昧候補、
  保存済みtrialの再採点を`tests/test_m0_eval_scoring.py`のunit testで検証する。
- **Revision History**:
  - 1.0 (2026-08-11) SI-FLW-036のaccept裁定により初版をdraft起票。既存FLW-NFR-001/008の
    閾値は変更せず、それらを測るproxyの健全性を独立要件とした。
  - 1.0 (2026-08-11) ユーザーが要件説明後にapprove。裁定記録:
    `.spec/reports/decision-2026-08-11-si-flw-036-proxy-inventory.md`
