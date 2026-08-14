---
id: QLT-FR-026
version: 1.0
status: draft
domain: quality-review
priority: medium
origin: SI-QLT-001 / QLT-DSC-002
verification_method: example-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### QLT-FR-026 レビュー実行の測定定義と履歴

- **説明**: レビュー品質・再現性・コストの測定定義と時系列履歴を成果物化する。
- **受入基準 (EARS)**:
  - WHEN metricを定義する THEN measurand・proxy・分母・除外規則・乖離条件・必要母数を記録すること SHALL
  - WHEN 仮説またはplatform parityを測定する THEN計画はfixture母集団・最低試行数・測定期間・baseline・全数判定または信頼区間・No-Go閾値を実行前に固定すること SHALL
  - WHEN review runが終了する THEN green/red/blocked、run ID、actor、時刻、tool/profile/schema versionをversion付き履歴へ追記し既存runを上書きしないこと SHALL
  - WHEN 履歴schemaを設計する THEN保存場所・保持期間・削除条件・機密情報を含めない規則を宣言すること SHALL
  - IF denominatorが0または母数不足 THEN達成と判定せず測定不能を明示すること SHALL
- **検証手段**: denominator 0、version変更、red履歴、proxy乖離fixtureを検証する。
- **Revision History**:
  - 1.0 (2026-08-14) 初版（draft 起票）
  - 1.0 (2026-08-14) QLT-REV-002 SYN-007/008を反映
