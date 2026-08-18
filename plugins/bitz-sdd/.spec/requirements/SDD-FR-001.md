---
id: SDD-FR-001
version: 1.1
status: implementing
domain: verification
priority: medium
origin: SI-CORE-003（ルート .spec/spec-issues/、実装 v1.4.x からの reverse-derived）
verification_method: example-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### SDD-FR-001 spec_inspect のタスク ID 既知化（幽霊判定からの除外）

- **説明**: spec_inspect.py の幽霊参照判定は、`.spec/tasks/` 配下のファイル名 stem を
  既知 ID として扱い、タスク間の depends_on 参照や specs/ 文書からのタスク ID 言及を
  幽霊参照として誤検知しない。複数 workspace を一括検査するときは、検査対象すべての
  タスク ID を既知として扱う。存在しないタスク ID への参照は引き続き幽霊として検出する。
- **受入基準 (EARS)**:
  - WHEN タスクファイルが depends_on で実在する他タスクの ID を参照する THEN spec_inspect は当該 ID を幽霊参照として報告しないこと SHALL
  - WHEN .spec/specs/ の文書が実在するタスク ID に言及する THEN spec_inspect は当該 ID を幽霊参照として報告しないこと SHALL
  - WHEN 複数 workspace を一括検査し文書が別 workspace の実在タスク ID に言及する THEN spec_inspect は当該 ID を幽霊参照として報告しないこと SHALL
  - WHEN 単一 workspace を検査する THEN spec_inspect は検査対象外 workspace のタスク ID を既知として扱わないこと SHALL
  - WHEN 文書が存在しないタスク ID を参照する THEN spec_inspect は幽霊参照として FAIL を報告 SHALL
- **検証手段**: tests/test_spec_inspect.py::test_task_to_task_depends_on_is_not_ghost /
  test_spec_doc_referencing_task_id_is_not_ghost / test_multi_workspace_task_reference_resolves_sibling_task /
  test_single_workspace_does_not_resolve_external_task / test_missing_task_reference_still_detected
- **Revision History**:
  - 1.0 (2026-07-12) 初版（SI-CORE-003 の実装済み修正からの reverse-derived。
    ワークスペース新設に伴うペーパートレイル補完）
  - 1.0 (2026-07-12) 人間裁定により approved 化（チャット指示）
  - 1.1 (2026-08-18) 正規の複数 workspace 検査で全対象 workspace の実在タスク ID を
    既知として扱う条件を明文化（裁定記録: decision-2026-08-18-sdd-fr-001-canonical-reentry.md）
