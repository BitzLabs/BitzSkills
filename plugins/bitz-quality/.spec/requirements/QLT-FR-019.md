---
id: QLT-FR-019
version: 1.0
status: approved
domain: quality-review
priority: medium
origin: SI-QLT-001 / QLT-DSC-003
verification_method: example-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### QLT-FR-019 Reviewer invocation manifestの固定

- **説明**: 1回のレビューを再現・監査するinvocation manifestを固定する。
- **受入基準 (EARS)**:
  - WHEN reviewを開始する THEN manifestはreview ID・target identity/SHA・scope・profile digest・adapter・model identity・timeout・入力digestを含むこと SHALL
  - WHEN 入力digestを計算する THEN systemはschema versionで固定したhash algorithm・canonical byte表現・対象path集合と順序・symlink方針を用い、検証済みsnapshotをadapterへ渡すこと SHALL
  - WHEN 同一reviewerをretryする THEN manifestは単調増加するattempt世代とcreated/started時刻・利用可能なexecutor identityを記録すること SHALL
  - IF targetまたはprofileが計画後に変化した THEN systemはSTALEとして実行または昇格を拒否すること SHALL
  - WHEN adapter実行が終了する THEN systemは入力snapshotのdigestを再照合し、不一致をSTALEとして公開不能にすること SHALL
  - WHEN manifestを再利用する THEN compatibility keyとrun固有evidence IDを分離すること SHALL
- **検証手段**: manifest schema、STALE、compatibility/evidence ID分離をfixtureで検証する。
- **Revision History**:
  - 1.0 (2026-08-14) 初版（draft 起票）
  - 1.0 (2026-08-14) QLT-REV-002 GP-002/004を反映
