---
id: FLW-NFR-002
version: 1.0
status: deprecated
domain: verification
priority: high
origin: .spec/reports/decision-2026-07-29-bitz-flow-v2-design-gate.md
verification_method: benchmark
derived_from:
supersedes:
superseded_by: FLW-NFR-008
confidence: high
---

### FLW-NFR-002 結果出力の情報保持とbyte削減

- **説明**: raw Git/gh出力より短いresultを返しながら、次の操作判断に必要なfieldを欠落させない。
- **受入基準 (EARS)**:
  - WHEN status fixture corpusをcompact rendererで測定する THEN bitz-flowはraw baseline比median byte削減70%以上を記録すること SHALL
  - WHEN diff-summary fixture corpusをcompact rendererで測定する THEN bitz-flowはraw baseline比median byte削減80%以上を記録すること SHALL
  - WHEN compactとJSONをgolden schemaで比較する THEN bitz-flowは必須field保持率100%を記録すること SHALL
  - WHEN blocking項目を含むresultを省略する THEN bitz-flowはblocking項目保持率100%を記録すること SHALL
  - WHEN 出力benchmarkを実行する THEN bitz-flowはoperation別p90とabsolute byte上限をversion管理manifestへ記録すること SHALL
  - WHEN raw stdout、raw stderr、credential、environmentを検査する THEN bitz-flowは公開resultへの混入0件を記録すること SHALL
- **検証閾値**: status median 70%以上削減、diff-summary median 80%以上削減、必須field 100%、blocking field 100%、秘密値・raw出力0件。
- **検証手段**: 固定fixture corpus、raw baseline command、median/p90/absolute bytes、schema oracleを用いるbenchmarkで検証する。
- **Revision History**:
  - 1.0 (2026-07-29) FLW-DSC-004とFLW-DSN-003/014からdraft起票
  - deprecated (2026-08-05) SI-FLW-009 の裁定により FLW-NFR-008 へ supersede。status の byte 削減の分母（no-skill でエージェントが実際に消費した出力）が platform のコマンド選択に依存し、同一 renderer が 5.9%〜75.0% に振れることが実測で判明したため。裁定記録: .spec/reports/decision-2026-08-05-si-flw-009-byte-denominator.md
