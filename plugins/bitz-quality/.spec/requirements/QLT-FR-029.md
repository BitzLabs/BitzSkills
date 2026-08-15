---
id: QLT-FR-029
version: 1.0
status: verified
domain: quality-review
priority: high
origin: SI-QLT-002
verification_method: example-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### QLT-FR-029 レビュー実行安全性と世代公開fencing

- **説明**: reviewerの部分失敗・競合・入力変化・公開中断を安全側に収束させる。
- **受入基準 (EARS)**:
  - WHEN任意Reviewerがtimeoutまたはquota超過する THEN systemはattemptをBLOCKEDとして隔離し、run verdictはprofile decision tableに従い、必須ReviewerのtimeoutだけはPASSを禁止すること SHALL
  - WHEN retryまたは旧writerが結果を書き込む THEN systemは永続generationとfencing tokenをcompare-and-swapで検証し、current attempt以外をactive化しないこと SHALL
  - WHEN adapterを実行する THEN systemは唯一のread rootであるcontent-addressed read-only snapshot以外を読めないこと SHALL
  - WHEN成果物を公開する THEN systemはimmutable generation manifestをfsync後に単一`current` pointerでatomic replaceし、consumerはpointer経由だけを読むこと SHALL
  - WHEN raw logを保存する THEN systemは明示opt-in、streaming redaction、最小権限、容量上限、TTL、削除監査を満たし、redaction失敗時は保存しないこと SHALL
- **検証手段**: timeout decision table、fencing race、snapshot escape、crash injection、raw log redaction/TTL fault injectionで検証する。
- **Revision History**:
  - 1.0 (2026-08-14) 初版（draft 起票）
