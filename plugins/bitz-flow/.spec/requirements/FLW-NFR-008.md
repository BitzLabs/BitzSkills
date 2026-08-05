---
id: FLW-NFR-008
version: 1.0
status: approved
domain: verification
priority: high
origin: .spec/reports/decision-2026-08-05-si-flw-009-byte-denominator.md
verification_method: benchmark
derived_from:
supersedes: FLW-NFR-002
superseded_by:
confidence: high
---

### FLW-NFR-008 結果出力の情報保持とbyte削減（固定baseline版）

- **説明**: raw Git/gh出力より短いresultを返しながら、次の操作判断に必要なfieldを欠落させない。
  byte削減の分母は**固定baseline command**とし、エージェントのコマンド選択に依存させない
  （`FLW-NFR-002` は分母を「no-skill条件でエージェントが実際に消費した出力」と定めていたが、
  同一rendererがplatform間で5.9%〜75.0%に振れることが実測で判明したため supersede する）。
- **受入基準 (EARS)**:
  - WHEN status fixture corpusをcompact rendererで測定する THEN bitz-flowは固定baseline `git status`（引数なしの長形式）比でmedian byte削減40%以上を記録すること SHALL
  - WHEN diff-summary fixture corpusをcompact rendererで測定する THEN bitz-flowは固定baseline `git diff HEAD`（生unified diff）比でmedian byte削減80%以上を記録すること SHALL
  - WHEN byte削減率を測定する THEN bitz-flowは`truncated`が`false`のresultだけを対象とすること SHALL
  - WHEN compactとJSONをgolden schemaで比較する THEN bitz-flowは必須field保持率100%を記録すること SHALL
  - WHEN blocking項目を含むresultを省略する THEN bitz-flowはblocking項目保持率100%を記録すること SHALL
  - WHEN 出力benchmarkを実行する THEN bitz-flowはoperation別p90とabsolute byte上限をversion管理manifestへ記録すること SHALL
  - WHEN raw stdout、raw stderr、credential、environmentを検査する THEN bitz-flowは公開resultへの混入0件を記録すること SHALL
- **検証閾値**: status median 40%以上削減（分母 `git status` 長形式）、diff-summary median 80%以上削減（分母 生unified diff）、必須field 100%、blocking field 100%、秘密値・raw出力0件。
- **検証手段**: 固定fixture corpus、固定baseline command、median/p90/absolute bytes、schema oracleを用いるbenchmarkで検証する。分母はfixtureから測り、trial時のエージェントの挙動に依存させない。
- **Revision History**:
  - 1.0 (2026-08-05) `FLW-NFR-002` の supersede として起票。SI-FLW-009 の裁定により status の分母を固定baseline `git status`（長形式）へ変更し、閾値を median 70% → 40% へ再校正した。truncation除外を受入基準へ格上げした。情報保持（必須field / blocking項目 100%）と秘密値・raw出力0件、diff-summaryの80%は `FLW-NFR-002` から変更していない
