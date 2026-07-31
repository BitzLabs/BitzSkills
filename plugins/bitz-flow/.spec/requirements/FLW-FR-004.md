---
id: FLW-FR-004
version: 1.0
status: approved
domain: tooling
priority: high
origin: SI-FLW-002
verification_method: unit-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### FLW-FR-004 Git読み取りと工程別診断

- **説明**: Gitの状態把握を状態変更から分離し、許可リスト形式の短い診断を返す。
- **受入基準 (EARS)**:
  - WHEN `repo.inspect`またはGit read operationを実行する THEN bitz-flowはGitのmachine-readable出力だけをparseしてsnapshot付きresultを返すこと SHALL
  - WHEN `git.status`を実行する THEN bitz-flowはbranch、upstream、ahead、behind、変更種別、repo相対pathを返すこと SHALL
  - WHEN `git.diff-summary`を実行する THEN bitz-flowは変更件数、path、変更種別、binary判定、追加削除行数を上限付きで返すこと SHALL
  - WHEN `git.diff-detail`を実行する THEN bitz-flowは明示されたpathまたはhunkだけをsnapshot照合後に返すこと SHALL
  - WHEN read operationを実行する THEN bitz-flowは暗黙のfetchまたはref更新を行わないこと SHALL
  - WHEN remote情報の更新を要求する THEN bitz-flowは`git.fetch`を独立operationとしてplanし、更新後snapshotと鮮度証跡を返すこと SHALL
  - WHEN Git command、parse、timeout、path検証のいずれかが失敗する THEN bitz-flowは失敗stageと許可語彙causeを区別して返すこと SHALL
- **検証手段**: dirty、rename、binary、conflict、detached HEAD、stale remote、timeout、不正出力のfixtureをunit testで検証する。
- **Revision History**:
  - 1.0 (2026-07-29) accepted SI-FLW-002とFLW-DSN-005からdraft起票
