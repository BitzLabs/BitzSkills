---
id: QLT-FR-022
version: 1.0
status: draft
domain: quality-review
priority: medium
origin: SI-QLT-001 / QLT-DSC-007 H-Q6
verification_method: example-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### QLT-FR-022 部分失敗・timeout・stale入力の安全側判定

- **説明**: 部分失敗、timeout、未知schema、古い入力を暗黙成功にしない。
- **受入基準 (EARS)**:
  - IF 必須Reviewerがtimeout・ERROR・INVALID・STALE・UNSUPPORTEDである THEN synthesisはPASSを返さないこと SHALL
  - WHEN 任意Reviewerが失敗する THEN systemは欠落を明示しprofile規則に従って判定すること SHALL
  - IF 判定に必要な情報が不足する THEN systemは推測せずUNKNOWNまたはBLOCKEDを返すこと SHALL
  - WHEN reviewerがtimeoutまたは時間・token・出力・ディスク上限へ達する THEN systemはgraceful cancel後にprocess groupを固定期限内で強制終了し、当該runをBLOCKEDとして隔離すること SHALL
  - WHEN 複数reviewerを実行する THEN systemはreviewer別作業領域・quota・同時実行上限で障害波及を遮断すること SHALL
- **検証手段**: 各失敗状態と必須/任意組合せのdecision tableを全行検査する。
- **Revision History**:
  - 1.0 (2026-08-14) 初版（draft 起票）
  - 1.0 (2026-08-14) QLT-REV-002 GP-003を反映
