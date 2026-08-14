---
id: QLT-FR-021
version: 1.0
status: approved
domain: quality-review
priority: medium
origin: SI-QLT-001 / SDD-FR-158 / SDD-FR-159 / SDD-FR-161
verification_method: example-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### QLT-FR-021 synthesis・finding・Gate前提schemaの固定

- **説明**: synthesis、ReviewFinding、GatePreconditionを機械検査可能な公開schemaへ固定する。
- **受入基準 (EARS)**:
  - WHEN synthesisを生成する THEN systemは入力result一覧・重複排除対応・verdict・finding・Gate前提・carried-overを記録すること SHALL
  - WHEN finding IDを採番する THEN review横断で一意な`<REV-ID>:SYN-NNN`形式にすること SHALL
  - IF 未追跡P0/P1、assumed blocking GP、未応答blocking GPがある THEN PASSを返さないこと SHALL
  - WHEN synthesisとquality-resultを公開する THEN systemは検証済みの単一run世代だけをcommit manifest経由で原子的に公開し、部分世代をconsumerへ提示しないこと SHALL
  - IF publishが中断されcommit markerを欠く THEN systemは当該世代をquarantineし、直前の完全世代を保持すること SHALL
  - WHEN SDD consumerへ渡す THEN SDD-FR-158/159/161の必須意味を保持すること SHALL
- **検証手段**: 現行sdd-review golden corpusと陽性対照でschema・ID・Gate規則を検証する。
- **Revision History**:
  - 1.0 (2026-08-14) 初版（draft 起票）
  - 1.0 (2026-08-14) QLT-REV-002 GP-001を反映
