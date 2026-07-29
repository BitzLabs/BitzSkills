---
id: FLW-FR-008
version: 1.0
status: draft
domain: sync
priority: high
origin: FLW-DSN-007
verification_method: unit-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### FLW-FR-008 GitHub IssueとSDDの双方向リンク

- **説明**: GitHub Issueを協調・実行状態として扱い、`.spec`の仕様・裁定責務と競合しない型付きリンクを提供する。
- **受入基準 (EARS)**:
  - WHEN Issue operationを要求する THEN bitz-flowはlist、view、search、prepare、publish、edit、comment、close、verify-link、reconcile-linkの固定actionだけを受理すること SHALL
  - WHEN Issueをpublishする THEN bitz-flowはsource kind、source ID、idempotency markerを本文へ記録すること SHALL
  - WHEN repository capabilityを検査する THEN bitz-flowはIssue type、sub-issue、dependency、Projectsの状態を`AVAILABLE`、`DEGRADED`、`UNSUPPORTED`、`UNAVAILABLE`で返すこと SHALL
  - WHEN 高水準gh commandでMust capabilityを満たせない THEN bitz-flowはsource codeでmethod、path、fieldを固定したallowlist adapterだけを使用すること SHALL
  - WHEN IssueLinkを検証する THEN bitz-flowはsource kind、source ID、Issue URLのcardinalityと両方向markerを照合すること SHALL
  - WHEN リンクの片側欠落または重複を検出する THEN bitz-flowは`.spec`を変更せずread-only reconcile planを返すこと SHALL
  - WHEN GitHubから`.spec`のstatus変更を要求する THEN bitz-flowは操作を`UNSUPPORTED`にすること SHALL
- **検証手段**: capability差異、marker重複、片側欠落、stale URL、pagination不完備、権限不足のunit testで検証する。
- **Revision History**:
  - 1.0 (2026-07-29) Design Gate承認済みFLW-DSN-007/013/014からdraft起票
